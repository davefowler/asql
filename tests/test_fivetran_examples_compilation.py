"""Test that Fivetran examples compile correctly to ASQL.

This test file is auto-generated. Run scripts/generate_fivetran_tests.py to regenerate.
"""

import pytest
from playground import strip_jinja_templates  # exported from playground package
from asql.reverse_compiler import reverse_compile
from asql.errors import ASQLCompilationError
from pathlib import Path

REAL_EXAMPLES_DIR = Path(__file__).parent.parent / 'examples' / 'real'

# 60 passing examples
PASSING_EXAMPLES = [
    'dbt_google_ads_google_ads__account_report_snowflake.sql',
    'dbt_google_ads_google_ads__ad_group_report_snowflake.sql',
    'dbt_google_ads_google_ads__ad_report_snowflake.sql',
    'dbt_google_ads_google_ads__campaign_report_snowflake.sql',
    'dbt_google_ads_google_ads__keyword_report_snowflake.sql',
    'dbt_google_ads_google_ads__search_term_report_snowflake.sql',
    'dbt_google_ads_google_ads__url_report_snowflake.sql',
    'dbt_google_ads_stg_google_ads__account_history_snowflake.sql',
    'dbt_google_ads_stg_google_ads__account_stats_snowflake.sql',
    'dbt_google_ads_stg_google_ads__ad_group_criterion_history_snowflake.sql',
    'dbt_marketo_int_marketo__lead_snowflake.sql',
    'dbt_marketo_marketo__bounces__by_sent_email_snowflake.sql',
    'dbt_marketo_marketo__change_data_details_snowflake.sql',
    'dbt_marketo_marketo__change_data_pivot_snowflake.sql',
    'dbt_marketo_marketo__change_data_scd_snowflake.sql',
    'dbt_marketo_marketo__clicks__by_sent_email_snowflake.sql',
    'dbt_marketo_marketo__deliveries__by_sent_email_snowflake.sql',
    'dbt_marketo_marketo__email_sends_deduped_snowflake.sql',
    'dbt_marketo_marketo__email_stats__by_campaign_snowflake.sql',
    'dbt_marketo_marketo__email_stats__by_email_template_snowflake.sql',
    'dbt_salesforce_int_salesforce__date_spine_snowflake.sql',
    'dbt_salesforce_int_salesforce__opportunity_aggregation_by_owner_snowflake.sql',
    'dbt_salesforce_salesforce__contact_enhanced_snowflake.sql',
    'dbt_salesforce_salesforce__daily_activity_snowflake.sql',
    'dbt_salesforce_salesforce__manager_performance_snowflake.sql',
    'dbt_salesforce_salesforce__opportunity_enhanced_snowflake.sql',
    'dbt_salesforce_salesforce__opportunity_line_item_enhanced_snowflake.sql',
    'dbt_salesforce_salesforce__owner_performance_snowflake.sql',
    'dbt_salesforce_salesforce__sales_snapshot_snowflake.sql',
    'dbt_salesforce_stg_salesforce__account_snowflake.sql',
    'dbt_shopify_int_shopify_gql__abandoned_checkout_snowflake.sql',
    'dbt_shopify_int_shopify_gql__collection_snowflake.sql',
    'dbt_shopify_int_shopify_gql__customer_email_rollup_snowflake.sql',
    'dbt_shopify_int_shopify_gql__customer_snowflake.sql',
    'dbt_shopify_int_shopify_gql__customers_order_aggregates_snowflake.sql',
    'dbt_shopify_int_shopify_gql__order_adjustment_snowflake.sql',
    'dbt_shopify_int_shopify_gql__order_discount_code_snowflake.sql',
    'dbt_shopify_int_shopify_gql__order_line_snowflake.sql',
    'dbt_shopify_int_shopify_gql__order_snowflake.sql',
    'dbt_shopify_int_shopify_gql__product_variant_snowflake.sql',
    'dbt_stripe_int_stripe__account_daily_snowflake.sql',
    'dbt_stripe_int_stripe__account_partitions_snowflake.sql',
    'dbt_stripe_int_stripe__account_rolling_totals_snowflake.sql',
    'dbt_stripe_int_stripe__date_spine_snowflake.sql',
    'dbt_stripe_int_stripe__deduped_subscription_item_snowflake.sql',
    'dbt_stripe_int_stripe__incomplete_charges_snowflake.sql',
    'dbt_stripe_stg_stripe__account_snowflake.sql',
    'dbt_stripe_stg_stripe__balance_transaction_snowflake.sql',
    'dbt_stripe_stg_stripe__card_snowflake.sql',
    'dbt_stripe_stg_stripe__charge_snowflake.sql',
    'dbt_zendesk_int_zendesk__assignee_updates_snowflake.sql',
    'dbt_zendesk_int_zendesk__comment_metrics_snowflake.sql',
    'dbt_zendesk_int_zendesk__latest_ticket_form_snowflake.sql',
    'dbt_zendesk_int_zendesk__organization_aggregates_snowflake.sql',
    'dbt_zendesk_int_zendesk__requester_updates_snowflake.sql',
    'dbt_zendesk_int_zendesk__schedule_history_snowflake.sql',
    'dbt_zendesk_int_zendesk__schedule_holiday_snowflake.sql',
    # 'dbt_zendesk_int_zendesk__schedule_spine_snowflake.sql',  # File doesn't exist
    'dbt_zendesk_int_zendesk__ticket_work_time_business_snowflake.sql',
    'dbt_zendesk_int_zendesk__ticket_work_time_calendar_snowflake.sql',
]


@pytest.mark.parametrize("filename", PASSING_EXAMPLES)
def test_fivetran_example_compiles(filename):
    """Test that a Fivetran example compiles to ASQL."""
    sql_file = REAL_EXAMPLES_DIR / filename
    assert sql_file.exists(), f"File {filename} does not exist"
    
    content = sql_file.read_text()
    cleaned = strip_jinja_templates(content)
    
    # Should not have any macros remaining
    import re
    macro_count = len(re.findall(r'\{\{[^}]+\}\}', cleaned)) + len(re.findall(r'\{%[^%]+%\}', cleaned))
    assert macro_count == 0, f"File {filename} still contains {macro_count} dbt macros"
    
    # Should compile to ASQL
    asql = reverse_compile(cleaned, source_dialect='snowflake')
    assert asql.strip(), f"File {filename} generated empty ASQL"
