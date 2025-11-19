# Example Pairs Index

Quick reference for all SQL/ASQL example pairs.

## By Pattern Type

### Joins
- `01_multi_table_join` - Multi-table joins
- `07_self_join` - Self-joins for hierarchies
- `08_union_query` - UNION queries

### Aggregations
- `02_complex_aggregations` - Complex aggregations with HAVING
- `03_cte_with_aggregation` - CTEs with aggregations
- `14_product_analytics` - Product performance analytics

### Window Functions
- `04_window_functions` - Running totals and rankings
- `11_ranking_top_n` - Top N rankings

### Date/Time
- `05_date_time_analysis` - Time-series analysis
- `09_cohort_analysis` - Cohort retention
- `19_retention_analysis` - User retention

### Analytics Patterns
- `06_case_statements` - Customer segmentation
- `10_funnel_analysis` - Conversion funnels
- `15_marketing_attribution` - Attribution models
- `17_user_segmentation` - RFM analysis

### Business Logic
- `12_string_operations` - String manipulation
- `13_nested_subqueries` - Nested queries
- `16_financial_reporting` - P&L reporting
- `18_revenue_recognition` - Revenue recognition
- `20_complex_filtering` - Complex filters

## By Source

### Fivetran dbt_shopify
- `01_multi_table_join`
- `05_date_time_analysis`
- `09_cohort_analysis`
- `10_funnel_analysis`
- `11_ranking_top_n`
- `14_product_analytics`
- `19_retention_analysis`

### Fivetran dbt_stripe
- `01_multi_table_join`
- `02_complex_aggregations`
- `03_cte_with_aggregation`
- `04_window_functions`
- `06_case_statements`
- `10_funnel_analysis`
- `15_marketing_attribution`
- `16_financial_reporting`
- `17_user_segmentation`
- `18_revenue_recognition`

### Fivetran dbt_zendesk
- `05_date_time_analysis`
- `19_retention_analysis`

### Fivetran dbt_salesforce
- `04_window_functions`
- `06_case_statements`
- `15_marketing_attribution`
- `17_user_segmentation`

## Usage in Tests

These examples can be loaded and tested:

```python
from pathlib import Path
from asql import compile

# Load SQL/ASQL pair
sql_file = Path("examples/pairs/01_multi_table_join.sql")
asql_file = Path("examples/pairs/01_multi_table_join.asql")

sql_query = sql_file.read_text()
asql_query = asql_file.read_text()

# Compile ASQL and compare
compiled_sql = compile(asql_query)
# Compare with original SQL (semantically, not exact match)
```

## Usage in Documentation

Examples can be included in documentation:

```markdown
### Multi-Table Joins

**SQL:**
```sql
[content from 01_multi_table_join.sql]
```

**ASQL:**
```asql
[content from 01_multi_table_join.asql]
```
```

