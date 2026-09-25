-- ============================================================
-- Q1(a) - Object Store, Partitioning and Query Pruning
-- Annapurna Stores Data Mining Lab
-- ============================================================

-- MinIO stores the curated sales data as Parquet.
--
-- Partition layout:
-- s3://sales/curated/
--     store_id=S01/year=2024/month=01/
--     store_id=S01/year=2024/month=02/
--     ...
--     store_id=S12/year=2024/month=12/
--
-- This allows a query for one store and one month to target
-- only the required partition instead of scanning all sales.

-- ------------------------------------------------------------
-- Query: October revenue for Store S05
-- ------------------------------------------------------------

SELECT
    store_id,

    ROUND(
        SUM(
            CASE
                WHEN line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
                THEN qty * unit_price
                ELSE 0
            END
        ),
        2
    ) AS revenue

FROM read_parquet(
    's3://sales/curated/store_id=S05/year=2024/month=10/*.parquet'
)

WHERE business_date >= '2024-10-01'
  AND business_date < '2024-11-01'

GROUP BY store_id;


-- ------------------------------------------------------------
-- Query-plan evidence
-- ------------------------------------------------------------
-- Run EXPLAIN ANALYZE on the same query.
--
-- Expected evidence from our completed run:
--
-- Total Files Read: 1
--
-- File:
-- s3://sales/curated/store_id=S05/year=2024/month=10/*.parquet
--
-- This demonstrates partition pruning.
-- ------------------------------------------------------------

EXPLAIN ANALYZE
SELECT
    store_id,

    ROUND(
        SUM(
            CASE
                WHEN line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
                THEN qty * unit_price
                ELSE 0
            END
        ),
        2
    ) AS revenue

FROM read_parquet(
    's3://sales/curated/store_id=S05/year=2024/month=10/*.parquet'
)

WHERE business_date >= '2024-10-01'
  AND business_date < '2024-11-01'

GROUP BY store_id;