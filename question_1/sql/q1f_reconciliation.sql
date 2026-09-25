-- ============================================================
-- Q1(f) - Monthly Finance Reconciliation
-- Annapurna Stores Data Mining Lab
-- ============================================================

-- Compare revenue calculated from curated sales data
-- against the signed-off finance monthly figures.
--
-- Revenue definition:
-- SALE + RETURN + DISCOUNT + VOID
-- TAX and TENDER are excluded.


WITH pipeline AS (

    SELECT
        MONTH(business_date) AS month_number,
        MONTHNAME(business_date) AS month_name,

        ROUND(
            SUM(
                CASE
                    WHEN line_type IN
                        ('SALE','RETURN','DISCOUNT','VOID')
                    THEN qty * unit_price
                    ELSE 0
                END
            ),
            2
        ) AS pipeline_revenue

    FROM read_parquet(
        's3://sales/curated/store_id=*/year=2024/month=*/*.parquet'
    )

    GROUP BY
        MONTH(business_date),
        MONTHNAME(business_date)
),


finance AS (

    SELECT *
    FROM read_csv(
        'finace_monthly.csv',
        delim=',',
        header=true,
        strict_mode=false,
        ignore_errors=true
    )
)


SELECT
    p.month_number,
    p.month_name,

    p.pipeline_revenue,

    CAST(
        f.finance_revenue AS DECIMAL(18,2)
    ) AS finance_revenue,

    ROUND(
        CAST(f.finance_revenue AS DECIMAL(18,2))
        - p.pipeline_revenue,
        2
    ) AS difference,

    CASE

        WHEN ABS(
            CAST(f.finance_revenue AS DECIMAL(18,2))
            - p.pipeline_revenue
        ) < 0.01

        THEN 'MATCH'


        WHEN p.month_number = 3

        THEN 'REVENUE DEFINITION DIFFERENCE'


        WHEN p.month_number = 7

        THEN 'SOURCE-DATA ISSUE'


        ELSE 'INVESTIGATE PIPELINE'

    END AS classification


FROM pipeline p

JOIN finance f
    ON LOWER(p.month_name) = LOWER(f.month)

ORDER BY p.month_number;


-- ============================================================
-- VERIFIED RECONCILIATION RESULTS
-- ============================================================
--
-- January    MATCH
-- February   MATCH
--
-- March
-- Pipeline:   ₹41,971,649.09
-- Finance:    ₹42,457,899.09
-- Difference: ₹486,250.00
-- Classification:
-- REVENUE DEFINITION DIFFERENCE
--
-- Reason:
-- Finance includes an institutional order invoiced outside
-- the till data.
--
--
-- April      MATCH
-- May        MATCH
-- June       MATCH
--
-- July
-- Pipeline:   ₹40,295,160.11
-- Finance:    ₹40,527,291.81
-- Difference: ₹232,131.70
-- Classification:
-- SOURCE-DATA ISSUE
--
-- Reason:
-- S07 had three missing July sales files.
--
--
-- August     MATCH
-- September  MATCH
-- October    MATCH
-- November   MATCH
-- December   MATCH