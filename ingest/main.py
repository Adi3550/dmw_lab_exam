import os
import re
import io
import time
import hashlib

from pathlib import Path
from datetime import datetime

import pandas as pd
import boto3
from botocore.client import Config


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

DATA_DIR = Path("/data/sales")

MINIO_ENDPOINT = "http://minio:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"

BUCKET = "sales"


# ---------------------------------------------------------
# CONNECT TO MINIO
# ---------------------------------------------------------

def get_minio_client():

    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name="us-east-1",
        config=Config(signature_version="s3v4")
    )


# ---------------------------------------------------------
# CREATE BUCKET IF IT DOES NOT EXIST
# ---------------------------------------------------------

def ensure_bucket(s3):

    buckets = s3.list_buckets()["Buckets"]

    existing = {b["Name"] for b in buckets}

    if BUCKET not in existing:
        s3.create_bucket(Bucket=BUCKET)
        print(f"Created bucket: {BUCKET}")
    else:
        print(f"Bucket already exists: {BUCKET}")


# ---------------------------------------------------------
# EXTRACT STORE + BUSINESS DATE FROM FILENAME
# ---------------------------------------------------------

def parse_filename(filename):

    name = Path(filename).name

    pattern = r"SALES_(S\d{2})_(\d{8})"

    match = re.search(pattern, name)

    if not match:
        raise ValueError(f"Invalid sales filename: {name}")

    store_id = match.group(1)

    business_date = datetime.strptime(
        match.group(2),
        "%Y%m%d"
    ).date()

    return store_id, business_date


# ---------------------------------------------------------
# READ CSV
# ---------------------------------------------------------

def read_csv_file(path):

    # First try comma
    df = pd.read_csv(path)

    # If only one column was detected,
    # try semicolon.
    if len(df.columns) == 1:

        df = pd.read_csv(
            path,
            sep=";"
        )

    return df


# ---------------------------------------------------------
# READ ANY SALES FILE
# ---------------------------------------------------------

def read_sales_file(path):

    suffix = path.suffix.lower()

    if suffix == ".parquet":

        df = pd.read_parquet(path)

    elif suffix == ".csv":

        df = read_csv_file(path)

    else:

        raise ValueError(
            f"Unsupported file format: {path}"
        )

    return df


# ---------------------------------------------------------
# NORMALIZE COLUMN NAMES
# ---------------------------------------------------------

def normalize_columns(df):

    mapping = {

        "bill_no": "bill_no",
        "line_no": "line_no",

        "product_code": "product_code",
        "item_code": "product_code",

        "qty": "qty",
        "quantity": "qty",

        "unit_price": "unit_price",
        "rate": "unit_price",

        "line_type": "line_type",
        "type": "line_type",

        "ts": "ts",
        "txn_time": "ts"
    }

    df = df.rename(columns=mapping)

    required = [
        "bill_no",
        "line_no",
        "product_code",
        "qty",
        "unit_price",
        "line_type",
        "ts"
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            f"Missing columns: {missing}"
        )

    return df[required]


# ---------------------------------------------------------
# NORMALIZE DATA TYPES
# ---------------------------------------------------------

def normalize_types(df):

    df["bill_no"] = df["bill_no"].astype(str)

    df["line_no"] = pd.to_numeric(
        df["line_no"],
        errors="coerce"
    ).astype("Int64")

    df["product_code"] = (
        df["product_code"]
        .astype(str)
        .str.strip()
    )

    df["qty"] = pd.to_numeric(
        df["qty"],
        errors="coerce"
    )

    df["unit_price"] = pd.to_numeric(
        df["unit_price"],
        errors="coerce"
    )

    df["line_type"] = (
        df["line_type"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    return df


# ---------------------------------------------------------
# NORMALIZE TIMESTAMP
# ---------------------------------------------------------

def normalize_timestamp(df):

    # Make a fresh object column first so that
    # strings and datetime values can be handled safely.

    raw_ts = df["ts"].astype(str)

    numeric_ts = pd.to_numeric(
        raw_ts,
        errors="coerce"
    )

    numeric_mask = numeric_ts.notna()

    # Start with an empty datetime column.
    result = pd.Series(
        pd.NaT,
        index=df.index,
        dtype="datetime64[ns, UTC]"
    )

    # Epoch timestamps
    if numeric_mask.any():

        result.loc[numeric_mask] = pd.to_datetime(
            numeric_ts.loc[numeric_mask],
            unit="s",
            utc=True,
            errors="coerce"
        )

    # Normal date/time strings
    normal_mask = ~numeric_mask

    if normal_mask.any():

        result.loc[normal_mask] = pd.to_datetime(
            raw_ts.loc[normal_mask],
            errors="coerce",
            dayfirst=True,
            utc=True
        )

    df["ts"] = result

    return df

# ---------------------------------------------------------
# PROCESS ONE FILE
# ---------------------------------------------------------

def process_file(path):

    print(f"Processing: {path.name}")

    store_id, business_date = parse_filename(
        path.name
    )

    df = read_sales_file(path)

    print(
        f"  Raw rows: {len(df)}"
    )

    df = normalize_columns(df)

    df = normalize_types(df)

    df = normalize_timestamp(df)

    df["store_id"] = store_id

    df["business_date"] = pd.Timestamp(
        business_date
    )

    # Safe line identity
    df["line_key"] = (
        df["bill_no"].astype(str)
        + "|"
        + df["line_no"].astype(str)
    )

    return df


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    print("Starting Annapurna ingestion...")

    # Connect to MinIO
    s3 = get_minio_client()

    # Wait for MinIO
    for attempt in range(30):

        try:

            s3.list_buckets()

            print("MinIO connection successful.")

            break

        except Exception as e:

            print(
                f"Waiting for MinIO... "
                f"attempt {attempt + 1}"
            )

            time.sleep(2)

    else:

        raise RuntimeError(
            "Could not connect to MinIO."
        )

    ensure_bucket(s3)

    # Find input files
    files = sorted(
        list(DATA_DIR.glob("*.csv"))
        + list(DATA_DIR.glob("*.parquet"))
    )

    print(
        f"Found {len(files)} sales files."
    )

    if not files:

        raise RuntimeError(
            "No sales files found in /data/sales"
        )

    all_data = []

    for file in files:

        df = process_file(file)

        all_data.append(df)

    # Combine everything
    sales = pd.concat(
        all_data,
        ignore_index=True
    )

    print(
        f"Rows before deduplication: "
        f"{len(sales)}"
    )

    # -----------------------------------------------------
    # DEDUPLICATION
    # -----------------------------------------------------

    before = len(sales)

    sales = sales.drop_duplicates(
        subset=[
            "store_id",
            "bill_no",
            "line_no"
        ],
        keep="first"
    )

    after = len(sales)

    print(
        f"Duplicate rows removed: "
        f"{before - after}"
    )

    print(
        f"Rows after deduplication: "
        f"{after}"
    )

# -----------------------------------------------------
# DATASET CHECKSUM
# -----------------------------------------------------

    checksum = calculate_checksum(sales)

    print("========================================")
    print(f"Final row count: {len(sales)}")
    print(f"Dataset SHA-256 checksum: {checksum}")
    print("========================================")

    

    # -----------------------------------------------------
    # WRITE PARTITIONED PARQUET
    # -----------------------------------------------------

    for (
        store_id,
        year,
        month
    ), group in sales.groupby(
        [
            "store_id",
            sales["business_date"].dt.year,
            sales["business_date"].dt.month
        ]
    ):

        partition_path = (
            f"curated/"
            f"store_id={store_id}/"
            f"year={year}/"
            f"month={month:02d}/"
        )

        buffer = io.BytesIO()

        group.to_parquet(
            buffer,
            index=False
        )

        buffer.seek(0)

        object_name = (
            partition_path
            + "sales.parquet"
        )

        s3.put_object(
            Bucket=BUCKET,
            Key=object_name,
            Body=buffer.getvalue()
        )

        print(
            f"Uploaded: s3://{BUCKET}/{object_name} "
            f"rows={len(group)}"
        )

    print()
    print("INGESTION COMPLETE")
    print(
        f"Final row count: {len(sales)}"
    )

# ---------------------------------------------------------
# CREATE DETERMINISTIC CHECKSUM
# ---------------------------------------------------------

def calculate_checksum(df):

    checksum_df = df[
        [
            "store_id",
            "bill_no",
            "line_no",
            "product_code",
            "qty",
            "unit_price",
            "line_type",
            "business_date"
        ]
    ].copy()

    checksum_df = checksum_df.sort_values(
        [
            "store_id",
            "bill_no",
            "line_no"
        ]
    ).reset_index(drop=True)

    data = checksum_df.to_csv(
        index=False
    ).encode("utf-8")

    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    main()