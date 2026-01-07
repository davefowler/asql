# ASQL Example Pairs

This directory contains SQL/ASQL query pairs demonstrating how ASQL simplifies complex SQL queries. Each example includes both the original SQL and its ASQL equivalent.

## Structure

Each example consists of two files:
- `##_description.sql` - Original SQL query
- `##_description.asql` - ASQL equivalent

## Examples

### 01-10: Core Patterns
- **01_multi_table_join** - Multi-table joins with customers, orders, and products
- **02_complex_aggregations** - Complex aggregations with HAVING clauses
- **03_cte_with_aggregation** - Using CTEs (WITH statements) for complex queries
- **04_window_functions** - Window functions for running totals and rankings
- **05_date_time_analysis** - Date/time functions for time-series analysis
- **06_case_statements** - CASE statements for customer segmentation
- **07_self_join** - Self-joins for hierarchical data (employee managers)
- **08_union_query** - UNION queries combining multiple data sources
- **09_cohort_analysis** - Cohort analysis for user retention
- **10_funnel_analysis** - Funnel analysis for conversion tracking

### 11-20: Advanced Analytics
- **11_ranking_top_n** - Ranking queries with TOP N results
- **12_string_operations** - String manipulation and analysis
- **13_nested_subqueries** - Nested subqueries and EXISTS clauses
- **14_product_analytics** - Product performance analytics
- **15_marketing_attribution** - Marketing attribution models
- **16_financial_reporting** - Financial reporting and P&L statements
- **17_user_segmentation** - RFM analysis and user segmentation
- **18_revenue_recognition** - Revenue recognition and deferred revenue
- **19_retention_analysis** - User retention analysis
- **20_complex_filtering** - Complex multi-condition filtering

## Sources

Many examples are inspired by or adapted from real-world dbt models:

- **Fivetran dbt packages**: Examples inspired by patterns from:
  - [dbt_shopify](https://github.com/fivetran/dbt_shopify)
  - [dbt_stripe](https://github.com/fivetran/dbt_stripe)
  - [dbt_zendesk](https://github.com/fivetran/dbt_zendesk)
  - [dbt_salesforce](https://github.com/fivetran/dbt_salesforce)

These examples demonstrate how ASQL's pipeline syntax simplifies complex SQL queries commonly found in production dbt models.

## Usage

These examples can be used for:
- **Documentation**: Showing ASQL capabilities
- **Testing**: Validating ASQL compiler output
- **Learning**: Understanding ASQL syntax patterns
- **Comparison**: Side-by-side SQL vs ASQL comparison

## Notes

- Some ASQL examples may include comments indicating features that need implementation
- Examples are designed to be educational and may be simplified from production queries
- All examples follow ASQL syntax conventions as specified in `docs/spec.md`

