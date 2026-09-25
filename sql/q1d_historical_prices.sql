-- ============================================================
-- Q1(d) - Historical Prices
-- Annapurna Stores Data Mining Lab
-- ============================================================

-- Historical price must depend on the reporting period.
--
-- Product identification:
-- product_code + business_date
--        ↓
-- product_sk
--
-- Historical price:
-- product_sk + business_date
--        ↓
-- price_revisions
--
-- This prevents a current price from being incorrectly applied
-- to historical sales.


-- ============================================================
-- 1. Historical Product + Price Lookup
-- ============================================================

SELECT
    s.product_code,

    CAST(s.business_date AS DATE) AS business_date,

    p.product_sk,

    p.product_name,

    pr.selling_price AS historical_price,

    pr.effective_from,
    pr.effective_to

FROM read_parquet(
    's3://sales/curated/store_id=*/year=2024/month=03/*.parquet'
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
    'price_revisions'
) pr
    ON p.product_sk = pr.product_sk

   AND CAST(s.business_date AS DATE) >= pr.effective_from
   AND CAST(s.business_date AS DATE) <= pr.effective_to

LIMIT 20;


-- ============================================================
-- 2. Historical Price-Based Revenue
-- ============================================================

-- Example: calculate October revenue using the authoritative
-- historical selling price instead of the printed till price.

SELECT
    ROUND(
        SUM(
            CASE
                WHEN s.line_type IN
                    ('SALE','RETURN','DISCOUNT','VOID')
                THEN s.qty * pr.selling_price
                ELSE 0
            END
        ),
        2
    ) AS october_historical_revenue

FROM read_parquet(
    's3://sales/curated/store_id=*/year=2024/month=10/*.parquet'
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
    'price_revisions'
) pr
    ON p.product_sk = pr.product_sk

   AND CAST(s.business_date AS DATE) >= pr.effective_from
   AND CAST(s.business_date AS DATE) <= pr.effective_to;


-- Verified October historical-price revenue:
--
-- ₹56,916,225.40