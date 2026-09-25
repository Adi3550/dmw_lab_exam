-- ============================================================
-- Q1(b) - Idempotent / Safe Ingestion
-- Annapurna Stores Data Mining Lab
-- ============================================================

-- Safe line identity:
-- (store_id, bill_no, line_no)
--
-- Resend files can contain duplicate or incomplete data.
-- Therefore we do not simply choose the newest file.
-- All available files are combined and duplicate line identities
-- are removed using the safe key above.

-- ------------------------------------------------------------
-- Final row count
-- ------------------------------------------------------------

SELECT COUNT(*) AS final_row_count
FROM read_parquet(
    's3://sales/curated/store_id=*/year=2024/month=*/*.parquet'
);


-- ------------------------------------------------------------
-- Line identity check
-- ------------------------------------------------------------

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT (store_id, bill_no, line_no)) AS unique_line_keys
FROM read_parquet(
    's3://sales/curated/store_id=*/year=2024/month=*/*.parquet'
);


-- ------------------------------------------------------------
-- Idempotency evidence from three ingestion runs
-- ------------------------------------------------------------

-- Run 1:
-- Row count: 1,120,924
-- SHA-256:
-- b573734dd50d5fb3095f96f29f37372a760b163594560b42972d31b040841fe8
--
-- Run 2:
-- Row count: 1,120,924
-- SHA-256:
-- b573734dd50d5fb3095f96f29f37372a760b163594560b42972d31b040841fe8
--
-- Run 3:
-- Row count: 1,120,924
-- SHA-256:
-- b573734dd50d5fb3095f96f29f37372a760b163594560b42972d31b040841fe8
--
-- Same row count + same SHA-256 across all three runs
-- demonstrates deterministic/idempotent output.


-- ------------------------------------------------------------
-- Checksum calculation used by the ingestion program
-- ------------------------------------------------------------

-- The Python ingestion program calculates SHA-256 over a
-- deterministic, sorted representation of the key sales columns:
--
-- store_id
-- bill_no
-- line_no
-- product_code
-- qty
-- unit_price
-- line_type
-- business_date
--
-- The implementation is in:
-- ingest/main.py