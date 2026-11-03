# Rebuilding the dashboard in Power BI or Tableau

The Streamlit app is the reference dashboard. If you need the same thing in Power BI or Tableau,
`python scripts/export_bi.py` writes a star schema to `exports/` that loads straight into either tool.

> There is no `.pbix` / `.twbx` file in this repo on purpose: both are binary formats that can't be
> diffed or reviewed. You build the report from the extracts with the model, measures and page layout below.
> It takes about 30–45 minutes.

## 1. Files

| File | Grain | Role |
|---|---|---|
| `fact_order_lines.csv` | one row per order line | main fact: revenue, profit, units, category |
| `fact_orders.csv` | one row per order | AOV, promo and status analysis |
| `fact_sessions.csv` | one row per web session | funnel, conversion, A/B test |
| `dim_customer.csv` | one row per customer | segmentation attributes |
| `dim_product.csv` | one row per product | category, price, list margin |
| `dim_date.csv` | one row per day (2024–2025) | calendar for time intelligence |
| `customer_rfm_segments.csv` | one row per buyer | RFM scores and segment |
| `recommendations.csv` | one row per recommendation | text for an "Actions" page |

## 2. Data model (Power BI: Model view / Tableau: Relationships)

```
dim_date[date] 1 ──* fact_order_lines[order_date]
dim_date[date] 1 ──* fact_orders[order_date]      (convert order_date to Date first)
dim_date[date] 1 ──* fact_sessions[session_date]  (add column: DATE(session_start))
dim_customer[customer_id] 1 ──* fact_order_lines / fact_orders / fact_sessions [customer_id]
dim_customer[customer_id] 1 ──1 customer_rfm_segments[customer_id]
dim_product[product_id]   1 ──* fact_order_lines[product_id]
```

Mark `dim_date` as the date table (Power BI: *Table tools → Mark as date table*).
Keep every filter single-direction, from the dimensions to the facts.

## 3. Power BI DAX measures

```DAX
Net Revenue      = SUM ( fact_order_lines[net_revenue] )
Gross Profit     = SUM ( fact_order_lines[gross_profit] )
Gross Margin %   = DIVIDE ( [Gross Profit], [Net Revenue] )
Completed Orders = CALCULATE ( DISTINCTCOUNT ( fact_orders[order_id] ), fact_orders[status] = "Completed" )
AOV              = DIVIDE ( [Net Revenue], [Completed Orders] )
Buyers           = CALCULATE ( DISTINCTCOUNT ( fact_orders[customer_id] ), fact_orders[status] = "Completed" )
Units Sold       = CALCULATE ( SUM ( fact_order_lines[quantity] ), fact_order_lines[status] = "Completed" )

Return Rate % =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[status] = "Returned" ),
    CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[status] <> "Cancelled" )
)

-- Time intelligence
Revenue PY    = CALCULATE ( [Net Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )
Revenue YoY % = DIVIDE ( [Net Revenue] - [Revenue PY], [Revenue PY] )
Revenue PM    = CALCULATE ( [Net Revenue], DATEADD ( dim_date[date], -1, MONTH ) )
Revenue MoM % = DIVIDE ( [Net Revenue] - [Revenue PM], [Revenue PM] )
Revenue YTD   = TOTALYTD ( [Net Revenue], dim_date[date] )
Revenue 3M Avg =
AVERAGEX ( DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -3, MONTH ), [Net Revenue] )

-- Conversion
Sessions          = COUNTROWS ( fact_sessions )
Purchases         = SUM ( fact_sessions[purchased] )
Conversion Rate % = DIVIDE ( [Purchases], [Sessions] )
Add-to-Cart %     = DIVIDE ( SUM ( fact_sessions[added_to_cart] ), [Sessions] )
Cart Abandonment % = 1 - DIVIDE ( [Purchases], SUM ( fact_sessions[added_to_cart] ) )
Checkout Completion % = DIVIDE ( [Purchases], SUM ( fact_sessions[began_checkout] ) )

-- Retention
Repeat Customer Rate % =
VAR t = SUMMARIZE ( FILTER ( fact_orders, fact_orders[status] = "Completed" ),
                    fact_orders[customer_id], "n", COUNTROWS ( fact_orders ) )
RETURN DIVIDE ( COUNTROWS ( FILTER ( t, [n] > 1 ) ), COUNTROWS ( t ) )

-- Pareto: cumulative revenue share by product (use with product_name on the axis, sorted by revenue)
Cumulative Revenue % =
VAR cur = [Net Revenue]
VAR tbl = ADDCOLUMNS ( ALLSELECTED ( dim_product[product_name] ), "rev", [Net Revenue] )
RETURN DIVIDE ( SUMX ( FILTER ( tbl, [rev] >= cur ), [rev] ), SUMX ( tbl, [rev] ) )

-- Two-proportion z-test for the A/B page (variant filter applied in the measure)
AB z-score =
VAR sA = CALCULATE ( SUM ( fact_sessions[purchased] ), fact_sessions[checkout_variant] = "A", fact_sessions[began_checkout] = 1 )
VAR nA = CALCULATE ( COUNTROWS ( fact_sessions ), fact_sessions[checkout_variant] = "A", fact_sessions[began_checkout] = 1 )
VAR sB = CALCULATE ( SUM ( fact_sessions[purchased] ), fact_sessions[checkout_variant] = "B", fact_sessions[began_checkout] = 1 )
VAR nB = CALCULATE ( COUNTROWS ( fact_sessions ), fact_sessions[checkout_variant] = "B", fact_sessions[began_checkout] = 1 )
VAR p  = DIVIDE ( sA + sB, nA + nB )
RETURN DIVIDE ( DIVIDE ( sB, nB ) - DIVIDE ( sA, nA ), SQRT ( p * ( 1 - p ) * ( 1 / nA + 1 / nB ) ) )
AB p-value (two-sided) = 2 * ( 1 - NORM.S.DIST ( ABS ( [AB z-score] ), TRUE ) )
```

## 4. Tableau calculated fields

```
Gross Margin %        SUM([gross_profit]) / SUM([net_revenue])
Completed Orders      COUNTD(IF [status] = "Completed" THEN [order_id] END)
AOV                   SUM([net_revenue]) / [Completed Orders]
Return Rate %         COUNTD(IF [status]="Returned" THEN [order_id] END) / COUNTD(IF [status]<>"Cancelled" THEN [order_id] END)
Conversion Rate %     SUM([purchased]) / COUNT([session_id])
Revenue YoY %         (ZN(SUM([net_revenue])) - LOOKUP(ZN(SUM([net_revenue])), -1)) / ABS(LOOKUP(ZN(SUM([net_revenue])), -1))
                      -- table calc: compute using YEAR(order_date), with MONTH on Columns
Cumulative Rev %      RUNNING_SUM(SUM([net_revenue])) / TOTAL(SUM([net_revenue]))   -- Pareto, sort products desc
Cohort Month          DATETRUNC('month', {FIXED [customer_id] : MIN([order_date])})
Months Since First    DATEDIFF('month', [Cohort Month], DATETRUNC('month', [order_date]))
Retention %           COUNTD([customer_id]) / LOOKUP(COUNTD([customer_id]), FIRST())  -- along Months Since First
```

## 5. Report pages (mirrors the Streamlit tabs)

1. **Overview**: KPI cards (Net Revenue, Gross Profit, Margin %, Orders, AOV, Buyers, Conversion %, Return Rate %),
   each with YoY %. Then a monthly revenue column chart with the 3M average line, revenue by category (bar),
   revenue by channel (donut) and a funnel.
2. **Sales & Trends**: revenue by month, line split by year (YoY), MoM % columns, quarterly clustered bar,
   weekday × hour matrix with conditional formatting.
3. **Customers**: treemap of `customer_rfm_segments[segment]`, segment table with actions, and revenue per
   buyer by acquisition channel, region and age group.
4. **Products**: revenue vs profit by category, margin-vs-revenue scatter, Pareto line (Cumulative Revenue %),
   return rate by category, top-N product table (Top N filter).
5. **Retention & Conversion**: funnel, conversion by channel and device, cohort matrix (Cohort Month ×
   Months Since First, Retention %).
6. **A/B & Hypothesis**: checkout completion by variant, AB z-score and p-value cards, with a text box that
   says "significant at α = 0.05" when p < 0.05.
7. **Actions**: a table visual over `recommendations.csv`, sorted by priority then impact.

Slicers to sync across pages: date range, category, channel, region, device, loyalty member.

## 6. Colour palette

Use these in this order. The order was checked for colour-vision deficiency, so don't reshuffle it:

`#2a78d6` `#eb6834` `#1baf7a` `#eda100` `#e87ba4` `#008300` `#6250d6` `#e34948`

Sequential (heatmaps, cohort matrix): `#cde2fb` → `#104281`. Use red `#e34948` only for declines and alerts.
