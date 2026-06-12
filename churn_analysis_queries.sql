-- It identifies customers who have gone silent (no orders in the last 6 months of the dataset)

SELECT
    C.C_CUSTKEY,
    C.C_NAME,
    C.C_MKTSEGMENT,
    MAX(O.O_ORDERDATE) AS last_order_date,
    COUNT(O.O_ORDERKEY) AS total_orders,
    SUM(O.O_TOTALPRICE) AS total_revenue
FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER C
LEFT JOIN SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS O
    ON C.C_CUSTKEY = O.O_CUSTKEY
GROUP BY C.C_CUSTKEY, C.C_NAME, C.C_MKTSEGMENT
HAVING MAX(O.O_ORDERDATE) < '1998-01-01'
   OR MAX(O.O_ORDERDATE) IS NULL
ORDER BY total_revenue DESC
LIMIT 20;

--customers who used to buy but have gone quiet

SELECT
    C.C_CUSTKEY,
    C.C_NAME,
    C.C_MKTSEGMENT,
    COUNT(O.O_ORDERKEY)                                    AS total_orders,
    SUM(O.O_TOTALPRICE)                                    AS total_revenue,
    MAX(O.O_ORDERDATE)                                     AS last_order_date,
    MIN(O.O_ORDERDATE)                                     AS first_order_date,
    DATEDIFF('day', MAX(O.O_ORDERDATE), '1998-12-31')     AS days_since_last_order
FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER C
JOIN SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS O
    ON C.C_CUSTKEY = O.O_CUSTKEY
GROUP BY C.C_CUSTKEY, C.C_NAME, C.C_MKTSEGMENT
HAVING days_since_last_order > 300
ORDER BY total_revenue DESC
LIMIT 20;

-- it builds the churn risk scoring logic by segment, which is the executive-level view

SELECT
    C_MKTSEGMENT,
    COUNT(*)                                               AS churned_customers,
    ROUND(SUM(total_revenue), 2)                          AS revenue_at_risk,
    ROUND(AVG(total_revenue), 2)                          AS avg_customer_value,
    ROUND(AVG(days_since_last_order), 0)                  AS avg_days_silent,
    ROUND(SUM(total_revenue) / SUM(SUM(total_revenue)) 
          OVER () * 100, 2)                               AS pct_of_total_risk
FROM (
    SELECT
        C.C_MKTSEGMENT,
        SUM(O.O_TOTALPRICE)                               AS total_revenue,
        DATEDIFF('day', MAX(O.O_ORDERDATE), '1998-12-31') AS days_since_last_order
    FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER C
    JOIN SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS O
        ON C.C_CUSTKEY = O.O_CUSTKEY
    GROUP BY C.C_CUSTKEY, C.C_MKTSEGMENT
    HAVING days_since_last_order > 300
) churned
GROUP BY C_MKTSEGMENT
ORDER BY revenue_at_risk DESC;

--This one adds a churn risk tier (High/Medium/Low) per customer based on recency and value - the final input your AI layer will summarize

SELECT
    C_MKTSEGMENT,
    churn_risk_tier,
    COUNT(*)                        AS customers,
    ROUND(SUM(total_revenue), 2)    AS revenue_at_risk
FROM (
    SELECT
        C.C_MKTSEGMENT,
        SUM(O.O_TOTALPRICE)                                AS total_revenue,
        DATEDIFF('day', MAX(O.O_ORDERDATE), '1998-12-31') AS days_since_last_order,
        CASE
            WHEN DATEDIFF('day', MAX(O.O_ORDERDATE), '1998-12-31') > 400
                 AND SUM(O.O_TOTALPRICE) > 1500000 THEN 'HIGH'
            WHEN DATEDIFF('day', MAX(O.O_ORDERDATE), '1998-12-31') BETWEEN 300 AND 400
                 AND SUM(O.O_TOTALPRICE) > 1000000 THEN 'MEDIUM'
            ELSE 'LOW'
        END                                                AS churn_risk_tier
    FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER C
    JOIN SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS O
        ON C.C_CUSTKEY = O.O_CUSTKEY
    GROUP BY C.C_CUSTKEY, C.C_MKTSEGMENT
    HAVING days_since_last_order > 300
) tiered
GROUP BY C_MKTSEGMENT, churn_risk_tier
ORDER BY C_MKTSEGMENT, churn_risk_tier;