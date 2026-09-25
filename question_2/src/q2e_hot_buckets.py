import os
import sys
import hashlib
import time

import numpy as np
import pandas as pd
import psycopg2

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from normalize import normalize_text, word_shingles


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

NOTICE_DIR = os.path.join(DATA_DIR, "notices")

os.makedirs(RESULTS_DIR, exist_ok=True)


# ============================================================
# SETTINGS
# ============================================================

NUM_HASHES = 384
BANDS = 48
ROWS = 8


print("=" * 60)
print("Q2(e) - FULL CORPUS HOT-BUCKET ANALYSIS")
print("=" * 60)


# ============================================================
# LOAD NOTICES
# ============================================================

print("\nLoading notices...")

files = [
    os.path.join(NOTICE_DIR, f)
    for f in os.listdir(NOTICE_DIR)
    if f.endswith(".csv")
]

notices = pd.concat(
    [pd.read_csv(f) for f in files],
    ignore_index=True
)

notices["notice_id"] = notices["notice_id"].astype(str)

print(f"Total notices: {len(notices)}")


# ============================================================
# HASHING
# ============================================================

def hash_shingle(shingle):

    value = " ".join(shingle).encode("utf-8")

    digest = hashlib.blake2b(
        value,
        digest_size=8
    ).digest()

    return int.from_bytes(digest, "big")


# ============================================================
# MINHASH PARAMETERS
# ============================================================

rng = np.random.default_rng(42)

A = rng.integers(
    1,
    2**63 - 1,
    size=NUM_HASHES,
    dtype=np.uint64
)

B = rng.integers(
    0,
    2**63 - 1,
    size=NUM_HASHES,
    dtype=np.uint64
)

PRIME = np.uint64(18446744073709551557)


def create_signature(shingles):

    if not shingles:
        return np.full(
            NUM_HASHES,
            np.uint64(2**64 - 1)
        )

    hashes = np.array(
        [hash_shingle(s) for s in shingles],
        dtype=np.uint64
    )

    signature = np.full(
        NUM_HASHES,
        np.uint64(2**64 - 1)
    )

    for i in range(NUM_HASHES):

        values = (
            A[i] * hashes + B[i]
        ) % PRIME

        signature[i] = values.min()

    return signature


# ============================================================
# BUILD LSH BUCKETS
# ============================================================

print("\nBuilding LSH buckets...")

buckets = {}

notice_portal = {}

start_time = time.perf_counter()

for index, row in notices.iterrows():

    notice_id = str(row["notice_id"])

    notice_portal[notice_id] = str(
        row["portal_id"]
    )

    text = normalize_text(
        row["title"],
        row["body"]
    )

    shingles = word_shingles(
        text,
        5
    )

    signature = create_signature(shingles)

    for band in range(BANDS):

        start = band * ROWS
        end = start + ROWS

        band_values = signature[start:end]

        bucket_hash = hashlib.blake2b(
            band_values.tobytes(),
            digest_size=8
        ).hexdigest()

        key = (
            band,
            bucket_hash
        )

        if key not in buckets:
            buckets[key] = []

        buckets[key].append(notice_id)

    if (index + 1) % 1000 == 0:
        print(
            f"  Processed "
            f"{index + 1}/{len(notices)}"
        )


build_time = time.perf_counter() - start_time


# ============================================================
# BUCKET STATISTICS
# ============================================================

sizes = np.array(
    [len(v) for v in buckets.values()]
)

print("\n" + "=" * 60)
print("BUCKET DISTRIBUTION")
print("=" * 60)

print(f"\nTotal LSH buckets : {len(buckets):,}")
print(f"Total memberships : {sizes.sum():,}")

print(f"Mean bucket size  : {sizes.mean():.2f}")
print(f"Median bucket size: {np.median(sizes):.2f}")
print(f"95th percentile   : {np.percentile(sizes, 95):.2f}")
print(f"Maximum bucket    : {sizes.max():,}")


# ============================================================
# HOT BUCKETS
# ============================================================

bucket_rows = []

for key, members in buckets.items():

    band, bucket_hash = key

    portals = [
        notice_portal[n]
        for n in members
    ]

    portal_counts = pd.Series(
        portals
    ).value_counts()

    dominant_portal = portal_counts.index[0]
    dominant_count = int(
        portal_counts.iloc[0]
    )

    bucket_rows.append({
        "band": band,
        "bucket": bucket_hash,
        "size": len(members),
        "dominant_portal": dominant_portal,
        "dominant_portal_count": dominant_count
    })


bucket_df = pd.DataFrame(bucket_rows)

hot = bucket_df.sort_values(
    "size",
    ascending=False
).head(20)


print("\n" + "=" * 60)
print("TOP 20 HOT BUCKETS")
print("=" * 60)

print(
    hot.to_string(index=False)
)


# ============================================================
# PORTAL CONTRIBUTION
# ============================================================

portal_counts = (
    notices["portal_id"]
    .astype(str)
    .value_counts()
)

print("\n" + "=" * 60)
print("TOP PORTALS BY NOTICE COUNT")
print("=" * 60)

print(
    portal_counts.head(15).to_string()
)


# ============================================================
# ESTIMATE CANDIDATE WORK
# ============================================================

# Every notice in a bucket can potentially be a candidate
# for every other notice in that bucket.

candidate_work = np.sum(
    sizes * (sizes - 1)
)

print("\n" + "=" * 60)
print("CANDIDATE WORK")
print("=" * 60)

print(
    f"\nTotal bucket candidate comparisons: "
    f"{candidate_work:,}"
)

print(
    f"All-pairs comparisons avoided: "
    f"{71994000 - candidate_work:,}"
)

print(
    f"Fraction of all pairs examined: "
    f"{candidate_work / 71994000:.6%}"
)

print(
    f"\nLSH construction time: "
    f"{build_time:.2f} seconds"
)


# ============================================================
# SAVE RESULTS
# ============================================================

bucket_file = os.path.join(
    RESULTS_DIR,
    "q2e_bucket_distribution.csv"
)

bucket_df.to_csv(
    bucket_file,
    index=False
)

hot_file = os.path.join(
    RESULTS_DIR,
    "q2e_hot_buckets.csv"
)

hot.to_csv(
    hot_file,
    index=False
)


# ============================================================
# POSTGRESQL PERSISTENCE
# ============================================================

print("\nConnecting to PostgreSQL...")

connection = psycopg2.connect(
    host="localhost",
    port=5432,
    database="annapurna",
    user="annapurna",
    password="annapurna"
)

cursor = connection.cursor()

print("Connected.")


# Count existing retrieval rows
cursor.execute("""
SELECT COUNT(*)
FROM tender_retrieval.lsh_bucket;
""")

before_count = cursor.fetchone()[0]

print(
    f"Existing PostgreSQL LSH rows: "
    f"{before_count:,}"
)


# Insert actual bucket memberships
print("\nWriting LSH buckets to PostgreSQL...")

insert_sql = """
INSERT INTO tender_retrieval.lsh_bucket
    (band, bucket_key, notice_id)
VALUES
    (%s, %s, %s)
ON CONFLICT DO NOTHING;
"""

inserted = 0

for key, members in buckets.items():

    band, bucket_hash = key

    for notice_id in members:

        cursor.execute(
            insert_sql,
            (
                int(band),
                bucket_hash,
                notice_id
            )
        )

        inserted += 1

        if inserted % 10000 == 0:
            connection.commit()
            print(
                f"  Inserted {inserted:,} rows"
            )

connection.commit()


cursor.execute("""
SELECT COUNT(*)
FROM tender_retrieval.lsh_bucket;
""")

after_count = cursor.fetchone()[0]

print(
    f"\nPostgreSQL LSH rows after load: "
    f"{after_count:,}"
)


# ============================================================
# DATABASE HOT-BUCKET QUERY
# ============================================================

print("\nTop PostgreSQL buckets:")

cursor.execute("""
SELECT
    band,
    bucket_key,
    COUNT(*) AS bucket_size
FROM tender_retrieval.lsh_bucket
GROUP BY band, bucket_key
ORDER BY bucket_size DESC
LIMIT 10;
""")

for row in cursor.fetchall():
    print(row)


cursor.close()
connection.close()


# ============================================================
# FINISH
# ============================================================

print("\nResults saved:")

print(bucket_file)
print(hot_file)

print("\n" + "=" * 60)
print("Q2(e) COMPLETED")
print("=" * 60)