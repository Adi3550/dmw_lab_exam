-- ============================================================
-- Q1(e) - Cross-System Query
-- Annapurna Stores Data Mining Lab
-- ============================================================

-- DuckDB acts as the analytical query engine.
--
-- MinIO:
--     read_parquet(...)
--
-- PostgreSQL:
--     postgres_scan(...)
--
-- The data is queried directly from both systems in ONE query.
-- No sales data is copied into PostgreSQL.


-- ============================================================
-- 1. Cross-System Revenue by Store and Category
-- ============================================================

SELECT
    s.store_id,

    c.category_name,

    ROUND(
        SUM(
            CASE
                WHEN s.line_type IN
                    ('SALE','RETURN','DISCOUNT','VOID')
                THEN s.qty * s.unit_price
                ELSE 0
            END
        ),
        2
    ) AS revenue

FROM read_parquet(
    's3://sales/curated/store_id=S05/year=2024/month=10/*.parquet'
) s

-- PostgreSQL: products
JOIN postgres_scan(
    'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna',
    'public',
    'products'
) p

    ON s.product_code = p.product_code

   AND CAST(s.business_date AS DATE) >= p.valid_from
   AND CAST(s.business_date AS DATE) <= p.valid_to


-- PostgreSQL: product categories
JOIN postgres_scan(
    'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna',
    'public',
    'product_categories'
) c

    ON p.category_id = c.category_id

GROUP BY
    s.store_id,
    c.category_name

ORDER BY revenue DESC;


-- ============================================================
-- 2. Query Plan Evidence
-- ============================================================

EXPLAIN ANALYZE

SELECT
    s.store_id,
    c.category_name,

    ROUND(
        SUM(
            CASE
                WHEN s.line_type IN
                    ('SALE','RETURN','DISCOUNT','VOID')
                THEN s.qty * s.unit_price
                ELSE 0
            END
        ),
        2
    ) AS revenue

FROM read_parquet(
    's3://sales/curated/store_id=S05/year=2024/month=10/*.parquet'
) s

JOIN postgres_scan(
    'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna',
    'public',
    'products'
) p

    ON s.product_code = p.product_code

   AND CAST(s.business_date AS DATE) >= p.valid_from
   AND CAST(s.business_date AS DATE) <= p.valid_to

JOIN postgres_scan(
    'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna',
    'public',
    'product_categories'
) c

    ON p.category_id = c.category_id

GROUP BY
    s.store_id,
    c.category_name

ORDER BY revenue DESC;


-- ============================================================
-- VERIFIED EXPLAIN ANALYZE EVIDENCE
-- ============================================================
--
-- MinIO / Parquet:
--     Total Files Read: 1
--     Rows scanned: 4,588
--
-- PostgreSQL:
--     products scan: 1,224 rows
--     product_categories scan
--
-- Join operators:
--     HASH_JOIN
--
-- HTTPFS:
--     #GET: 2
--
-- Total execution time:
--     approximately 0.0778 seconds
--
-- This proves DuckDB evaluated a single query across:
--
--     MinIO Parquet
--           +
--     PostgreSQL
--
-- without first copying the sales data into PostgreSQL.