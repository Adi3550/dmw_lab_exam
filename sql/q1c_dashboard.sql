-- ============================================================
-- Q1(c) - Dashboard Tables / Star Schema
-- Annapurna Stores Data Mining Lab
-- ============================================================

-- Star-schema design:
--
--                 dim_store
--                     |
--                     |
-- dim_date ---- fact_sales ---- dim_product ---- dim_category
--
-- The large fact table stores keys and measures.
-- Descriptive information is kept in dimension tables.
--
-- Product_code is NOT unique, so product_sk is resolved using
-- product_code + business_date against valid_from / valid_to.


-- ============================================================
-- 1. Store Dimension
-- ============================================================

CREATE OR REPLACE TABLE dim_store AS
SELECT *
FROM postgres_scan(
    'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna',
    'public',
    'stores'
);

-- Expected:
-- 12 stores


-- ============================================================
-- 2. Category Dimension
-- ============================================================

CREATE OR REPLACE TABLE dim_category AS
SELECT *
FROM postgres_scan(
    'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna',
    'public',
    'product_categories'
);

-- Expected:
-- 14 categories


-- ============================================================
-- 3. Product Dimension
-- ============================================================

CREATE OR REPLACE TABLE dim_product AS
SELECT
    product_sk,
    product_code,
    product_name,
    category_id,
    valid_from,
    valid_to,
    is_current
FROM postgres_scan(
    'host=localhost port=5432 dbname=annapurna user=annapurna password=annapurna',
    'public',
    'products'
);

-- Expected:
-- 1,224 product records


-- ============================================================
-- 4. Fact Sales
-- ============================================================

-- TAX and TENDER are not revenue, but they are retained in the
-- fact table for complete auditability.
--
-- DISCOUNT and VOID may use the special product code DISC.
-- Therefore product_sk is allowed to be NULL for non-product
-- transaction lines.

CREATE OR REPLACE TABLE fact_sales AS
SELECT
    s.store_id,

    CAST(
        STRFTIME(
            CAST(s.business_date AS DATE),
            '%Y%m%d'
        ) AS INTEGER
    ) AS date_sk,

    p.product_sk,

    s.product_code,

    s.bill_no,
    s.line_no,

    s.qty,
    s.unit_price,

    CASE
        WHEN s.line_type IN ('SALE','RETURN','DISCOUNT','VOID')
        THEN s.qty * s.unit_price
        ELSE 0
    END AS revenue_amount,

    s.line_type,

    CAST(s.business_date AS DATE) AS business_date

FROM read_parquet(
    's3://sales/curated/store_id=*/year=2024/month=*/*.parquet'
) s

LEFT JOIN dim_product p
    ON s.product_code = p.product_code
   AND CAST(s.business_date AS DATE) >= p.valid_from
   AND CAST(s.business_date AS DATE) <= p.valid_to;


-- ============================================================
-- 5. Verify Dimension and Fact Sizes
-- ============================================================

SELECT
    (SELECT COUNT(*) FROM dim_store) AS stores,
    (SELECT COUNT(*) FROM dim_category) AS categories,
    (SELECT COUNT(*) FROM dim_product) AS products,
    (SELECT COUNT(*) FROM fact_sales) AS fact_rows;


-- Expected:
--
-- stores       = 12
-- categories   = 14
-- products     = 1,224
-- fact_rows    = 1,120,924


-- ============================================================
-- 6. Verify Fact Line Types
-- ============================================================

SELECT
    line_type,
    COUNT(*) AS rows
FROM fact_sales
GROUP BY line_type
ORDER BY line_type;


-- Verified result:
--
-- DISCOUNT    22,603
-- RETURN      16,161
-- SALE       745,860
-- TAX        165,704
-- TENDER     165,704
-- VOID         4,892


-- ============================================================
-- 7. Dashboard Query
-- ============================================================

SELECT
    f.store_id,
    c.category_name,

    STRFTIME(
        f.business_date,
        '%A'
    ) AS day_of_week,

    MONTH(f.business_date) AS month_number,

    ROUND(
        SUM(f.revenue_amount),
        2
    ) AS revenue

FROM fact_sales f

JOIN dim_product p
    ON f.product_sk = p.product_sk

JOIN dim_category c
    ON p.category_id = c.category_id

GROUP BY
    f.store_id,
    c.category_name,
    day_of_week,
    month_number

ORDER BY
    month_number,
    f.store_id,
    c.category_name,
    day_of_week;