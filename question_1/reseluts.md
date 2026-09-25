# Architecture

```text
                    ┌─────────────────────┐
                    │   Raw Sales Files   │
                    │ CSV + Parquet       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Python Ingestion    │
                    │ Normalize + Dedup   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       MinIO         │
                    │ Curated Parquet     │
                    │ store/year/month    │
                    └──────────┬──────────┘
                               │
                               │ read_parquet()
                               ▼
                    ┌─────────────────────┐
                    │      DuckDB         │
                    │ Analytical Engine   │
                    └──────────┬──────────┘
                               │
                  postgres_scan()
                               │
                               ▼
                    ┌─────────────────────┐
                    │    PostgreSQL      │
                    │ Master Data        │
                    │ Products / Stores  │
                    │ Categories / Price │
                    └─────────────────────┘

Q1(a) — Object Store and Partitioning
Sales data is stored in MinIO as Parquet files using the following
partitioning layout:
s3://sales/curated/
    store_id=S01/year=2024/month=01/
    store_id=S01/year=2024/month=02/
    ...
    store_id=S12/year=2024/month=12/

This allows queries for a particular store and month to target the
corresponding partition.
Example:
s3://sales/curated/store_id=S05/year=2024/month=10/*.parquet

The verified EXPLAIN ANALYZE result for the S05 October query showed:
Total Files Read: 1
Rows read: 6,625

This demonstrates partition-level file pruning.
SQL:
sql/q1a_partition.sql

Evidence:
results/q1a_partition_evidence.txt

Q1(b) — Idempotent Ingestion
The safe line identity is:
(store_id, bill_no, line_no)

The ingestion process combines available files and removes duplicate
line identities rather than simply choosing the newest resend file.
Final curated dataset:
1,120,924 rows

Three ingestion runs produced the same result.
Run 1:
1,120,924 rows
SHA-256:
b573734dd50d5fb3095f96f29f37372a760b163594560b42972d31b040841fe8

Run 2:
1,120,924 rows
SHA-256:
b573734dd50d5fb3095f96f29f37372a760b163594560b42972d31b040841fe8

Run 3:
1,120,924 rows
SHA-256:
b573734dd50d5fb3095f96f29f37372a760b163594560b42972d31b040841fe8

The identical row count and SHA-256 checksum demonstrate reproducible
output across repeated ingestion runs.
SQL/evidence:
sql/q1b_idempotency.sql
results/q1b_idempotency_evidence.txt

Q1(c) — Dashboard Star Schema
A dashboard-oriented star schema was created in dashboard.duckdb.
Dimensions:
dim_store       → 12 rows
dim_category    → 14 rows
dim_product     → 1,224 rows

Fact table:
fact_sales      → 1,120,924 rows

The fact table contains transaction-level measures and keys rather than
repeating descriptive information.
The dashboard supports slicing revenue by:
- Store
- Product category
- Day of week
- Month
Product history is resolved using:
product_code
+
business_date
+
valid_from / valid_to

and the resulting product_sk is stored in the fact table.
Revenue calculation uses:
SALE
RETURN
DISCOUNT
VOID

and excludes:
TAX
TENDER

The complete line-type distribution in the fact table is:
DISCOUNT    22,603
RETURN      16,161
SALE       745,860
TAX        165,704
TENDER     165,704
VOID         4,892

SQL/evidence:
sql/q1c_dashboard.sql
results/q1c_dashboard_evidence.txt

Q1(d) — Historical Prices
Historical prices are obtained from PostgreSQL's price_revisions
table.
The product is resolved using the product validity period:
product_code
+
business_date
+
products.valid_from
+
products.valid_to

The historical price is then resolved using:
product_sk
+
business_date
+
price_revisions.effective_from
+
price_revisions.effective_to

This allows the same query structure to be used for different reporting
periods while selecting the price applicable to that period.
Verified October historical-price revenue:
₹56,916,225.40

SQL/evidence:
sql/q1d_historical_prices.sql
results/q1d_historical_price_evidence.txt

Q1(e) — Cross-System Query
DuckDB queries MinIO and PostgreSQL in the same analytical query.
MinIO is accessed using:
read_parquet(...)

PostgreSQL is accessed using:
postgres_scan(...)

The demonstrated query combines:
MinIO
  └── sales Parquet
        │
        ▼
     DuckDB
        │
        ├── PostgreSQL products
        │
        └── PostgreSQL product_categories

EXPLAIN ANALYZE evidence showed:
MinIO / Parquet:
Total Files Read: 1

PostgreSQL products:
1,224 rows

PostgreSQL product_categories:
scanned

Join:
HASH_JOIN

HTTPFS:
#GET = 2

Approximate total execution time:
0.0778 seconds

The sales data was queried directly from MinIO without first copying it
into PostgreSQL.
SQL/evidence:
sql/q1e_cross_system.sql
results/q1e_explain_evidence.txt

Q1(f) — Finance Reconciliation
Monthly revenue calculated from the curated sales data was compared
against the finance figures.
The reconciliation produced matches for the other months and identified
two documented differences.
March
Pipeline revenue:
₹41,971,649.09

Finance revenue:
₹42,457,899.09

Difference:
₹486,250.00

Classification:
REVENUE DEFINITION DIFFERENCE

The difference corresponds to an institutional order invoiced outside
the till data.
July
Pipeline revenue:
₹40,295,160.11

Finance revenue:
₹40,527,291.81

Difference:
₹232,131.70

Classification:
SOURCE-DATA ISSUE

The July difference is associated with three missing S07 sales export
files.
SQL/evidence:
sql/q1f_reconciliation.sql
results/q1f_reconciliation.csv

Project Results
Metric	Result
Stores	12
Categories	14
Products	1,224
Raw lines	1,137,585
Curated unique lines	1,120,924
Price revisions	4,320
Reissued product codes	24


Revenue Rules
The revenue calculation follows the documented billing rules.
Included:
SALE
RETURN
DISCOUNT
VOID

Excluded:
TAX
TENDER

TENDER represents customer payment and is not treated as revenue.
TAX is also excluded from revenue.
VOID lines are retained because they cancel corresponding item lines.
Repository Structure
annapurna-dm/
│
├── README.md
├── docker-compose.yml
│
├── postgres/
│   └── masters.sql
│
├── ingest/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
│
├── sql/
│   ├── q1a_partition.sql
│   ├── q1b_idempotency.sql
│   ├── q1c_dashboard.sql
│   ├── q1d_historical_prices.sql
│   ├── q1e_cross_system.sql
│   └── q1f_reconciliation.sql
│
├── results/
│   ├── q1a_partition_evidence.txt
│   ├── q1b_idempotency_evidence.txt
│   ├── q1c_dashboard_evidence.txt
│   ├── q1d_historical_price_evidence.txt
│   ├── q1e_explain_evidence.txt
│   └── q1f_reconciliation.csv
│
└── data/
    └── sales/

Running the Infrastructure
From the project root:
docker compose up --build

PostgreSQL:
localhost:5432

MinIO API:
localhost:9000

MinIO Console:
localhost:9001

PostgreSQL credentials:
Username: annapurna
Password: annapurna
Database: annapurna

MinIO credentials:
Username: minioadmin
Password: minioadmin

Analytical Engine
DuckDB is used for analytical queries.
Required extensions:
INSTALL httpfs;
LOAD httpfs;

MinIO credentials are configured using an S3 secret:
CREATE SECRET minio_secret (
    TYPE S3,
    KEY_ID 'minioadmin',
    SECRET 'minioadmin',
    ENDPOINT 'localhost:9000',
    USE_SSL false,
    URL_STYLE 'path'
);

Q1 Evidence Map
Question	SQL	Evidence
Q1(a)	sql/q1a_partition.sql	results/q1a_partition_evidence.txt
Q1(b)	sql/q1b_idempotency.sql	results/q1b_idempotency_evidence.txt
Q1(c)	sql/q1c_dashboard.sql	results/q1c_dashboard_evidence.txt
Q1(d)	sql/q1d_historical_prices.sql	results/q1d_historical_price_evidence.txt
Q1(e)	sql/q1e_cross_system.sql	results/q1e_explain_evidence.txt
Q1(f)	sql/q1f_reconciliation.sql	results/q1f_reconciliation.csv


Notes
The repository contains the implementation, SQL queries, and measured
results used to demonstrate Q1.
The raw sales dataset is not reproduced in the repository because of
its size. The provided local data directory is used as the input to
the ingestion pipeline.