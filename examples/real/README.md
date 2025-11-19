# Real Fivetran dbt SQL Queries

This directory contains **actual SQL queries** fetched directly from Fivetran's dbt packages on GitHub. These are production queries used by thousands of companies.

## Structure

Each query pair consists of:
- `dbt_<repo>_<model>_<dialect>.sql` - Original SQL from Fivetran dbt package
- `dbt_<repo>_<model>_<dialect>.asql` - ASQL equivalent (when created)

## Naming Convention

Files are named: `dbt_{repo}_{model}_{dialect}.sql`

Examples:
- `dbt_shopify_int_shopify_gql__order_snowflake.sql`
- `dbt_stripe_stg_stripe__charge_snowflake.sql`
- `dbt_salesforce_salesforce__contact_enhanced_snowflake.sql`

## Sources

All queries are fetched from:
- [dbt_shopify](https://github.com/fivetran/dbt_shopify)
- [dbt_stripe](https://github.com/fivetran/dbt_stripe)
- [dbt_salesforce](https://github.com/fivetran/dbt_salesforce)
- [dbt_zendesk](https://github.com/fivetran/dbt_zendesk)
- [dbt_google_ads](https://github.com/fivetran/dbt_google_ads)
- [dbt_marketo](https://github.com/fivetran/dbt_marketo)

## Important Notes

### dbt Jinja Templating

The original SQL files contain **dbt Jinja templating** (e.g., `{{ ref('table') }}`, `{{ config() }}`). These are dbt-specific macros that:
- Reference other models: `{{ ref('stg_table') }}`
- Include conditional logic: `{% if var('enabled') %}`
- Use dbt functions: `{{ dbt.type_string() }}`

**ASQL equivalents** strip out the Jinja and focus on the core SQL logic, making them:
- ✅ Testable with ASQL compiler
- ✅ Understandable without dbt knowledge
- ✅ Demonstrative of ASQL's pipeline syntax

### Creating ASQL Equivalents

When creating ASQL equivalents:

1. **Remove Jinja macros**: Replace `{{ ref('table') }}` with direct table names
2. **Simplify CTEs**: Convert `WITH ... AS` to ASQL's `with` syntax
3. **Use pipeline syntax**: Convert nested queries to pipeline operations
4. **Test compilation**: All ASQL files should compile successfully

### Testing

Run the test script to validate all ASQL files compile:

```bash
python3 scripts/test_real_examples.py
```

## Usage

These examples are invaluable for:
- **Testing**: Validating ASQL compiler against real-world queries
- **Documentation**: Showing ASQL capabilities with production examples
- **Development**: Identifying missing ASQL features
- **Comparison**: Side-by-side SQL vs ASQL readability

## Fetching More Queries

To fetch more queries:

```bash
python3 scripts/fetch_fivetran_real.py
```

This will discover and fetch SQL files from Fivetran repos.

