#!/usr/bin/env python3
"""Fetch real SQL queries from Fivetran dbt repositories.

This script fetches actual SQL model files from Fivetran's dbt packages
and saves them with proper naming: dbt_<repo>_<model>_<dialect>.sql

Then creates ASQL equivalents and tests that they compile.
"""

import subprocess
from pathlib import Path
from typing import Tuple, Optional
import time
import sys

# Fivetran dbt repos and their models
REPOS = {
    "dbt_shopify": {
        "base_url": "https://raw.githubusercontent.com/fivetran/dbt_shopify/main/models",
        "models": [
            "shopify_gql/line_item_enhanced.sql",
            "shopify_gql/order_line_enhanced.sql",
            "shopify_gql/order_enhanced.sql",
            "shopify_gql/customer_enhanced.sql",
            "shopify_gql/product_enhanced.sql",
            "shopify_gql/transaction_enhanced.sql",
            "shopify_gql/refund_enhanced.sql",
            "shopify_gql/discount_code_enhanced.sql",
            "shopify_gql/fulfillment_enhanced.sql",
            "shopify_gql/order_line_item_enhanced.sql",
        ],
        "dialect": "snowflake"  # Most Fivetran packages use Snowflake
    },
    "dbt_stripe": {
        "base_url": "https://raw.githubusercontent.com/fivetran/dbt_stripe/main/models",
        "models": [
            "stripe/balance_transaction_enriched.sql",
            "stripe/customer_enriched.sql",
            "stripe/invoice_enriched.sql",
            "stripe/invoice_line_item_enriched.sql",
            "stripe/payment_method_enriched.sql",
            "stripe/subscription_enriched.sql",
            "stripe/charge_enriched.sql",
            "stripe/refund_enriched.sql",
            "stripe/dispute_enriched.sql",
            "stripe/payout_enriched.sql",
        ],
        "dialect": "snowflake"
    },
    "dbt_salesforce": {
        "base_url": "https://raw.githubusercontent.com/fivetran/dbt_salesforce/main/models",
        "models": [
            "salesforce/account_enriched.sql",
            "salesforce/contact_enriched.sql",
            "salesforce/opportunity_enriched.sql",
            "salesforce/lead_enriched.sql",
            "salesforce/case_enriched.sql",
            "salesforce/user_enriched.sql",
            "salesforce/campaign_enriched.sql",
            "salesforce/event_enriched.sql",
            "salesforce/task_enriched.sql",
            "salesforce/opportunity_line_item_enriched.sql",
        ],
        "dialect": "snowflake"
    },
    "dbt_zendesk": {
        "base_url": "https://raw.githubusercontent.com/fivetran/dbt_zendesk/main/models",
        "models": [
            "zendesk/ticket_enriched.sql",
            "zendesk/user_enriched.sql",
            "zendesk/organization_enriched.sql",
            "zendesk/ticket_comment_enriched.sql",
            "zendesk/ticket_field_history_enriched.sql",
            "zendesk/ticket_metric_enriched.sql",
            "zendesk/satisfaction_rating_enriched.sql",
            "zendesk/ticket_audit_enriched.sql",
            "zendesk/ticket_schedule_enriched.sql",
            "zendesk/ticket_tag_enriched.sql",
        ],
        "dialect": "snowflake"
    },
    "dbt_google_ads": {
        "base_url": "https://raw.githubusercontent.com/fivetran/dbt_google_ads/main/models",
        "models": [
            "google_ads/account_performance.sql",
            "google_ads/ad_group_performance.sql",
            "google_ads/ad_performance.sql",
            "google_ads/campaign_performance.sql",
            "google_ads/keyword_performance.sql",
            "google_ads/search_query_performance.sql",
        ],
        "dialect": "snowflake"
    },
    "dbt_marketo": {
        "base_url": "https://raw.githubusercontent.com/fivetran/dbt_marketo/main/models",
        "models": [
            "marketo/activity_enriched.sql",
            "marketo/lead_enriched.sql",
            "marketo/campaign_enriched.sql",
            "marketo/email_enriched.sql",
            "marketo/program_enriched.sql",
        ],
        "dialect": "snowflake"
    },
}


def extract_model_name(file_path: str) -> str:
    """Extract model name from file path."""
    # e.g., "shopify_gql/line_item_enhanced.sql" -> "line_item_enhanced"
    return Path(file_path).stem


def fetch_sql_file(url: str) -> Optional[str]:
    """Fetch SQL file from URL using curl."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", url],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout
        else:
            print(f"Error fetching {url}: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def test_asql_compiles(asql_content: str) -> Tuple[bool, Optional[str]]:
    """Test that ASQL compiles successfully."""
    try:
        # Import here to avoid circular imports
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from asql import compile
        
        compiled_sql = compile(asql_content)
        return True, compiled_sql
    except Exception as e:
        return False, str(e)


def save_query(
    repo_name: str,
    model_name: str,
    dialect: str,
    sql_content: str,
    asql_content: Optional[str],
    output_dir: Path
) -> Tuple[bool, Optional[str]]:
    """Save SQL query and ASQL equivalent, test compilation."""
    # Remove "dbt_" prefix if repo_name already has it
    repo_short = repo_name.replace("dbt_", "") if repo_name.startswith("dbt_") else repo_name
    sql_filename = f"dbt_{repo_short}_{model_name}_{dialect}.sql"
    sql_filepath = output_dir / sql_filename
    
    # Add source attribution header
    header = f"""-- Source: {repo_name}
-- Model: {model_name}
-- Dialect: {dialect}
-- Repository: https://github.com/fivetran/{repo_name}
-- File: models/{model_name}.sql

"""
    
    sql_filepath.write_text(header + sql_content)
    print(f"  Saved SQL: {sql_filename}")
    
    # Save ASQL if provided
    if asql_content:
        asql_filename = f"dbt_{repo_short}_{model_name}_{dialect}.asql"
        asql_filepath = output_dir / asql_filename
        
        asql_header = f"""-- ASQL equivalent of {sql_filename}
-- Source: {repo_name}
-- Model: {model_name}
-- Dialect: {dialect}
-- Repository: https://github.com/fivetran/{repo_name}

"""
        
        asql_filepath.write_text(asql_header + asql_content)
        print(f"  Saved ASQL: {asql_filename}")
        
        # Test compilation
        compiles, result = test_asql_compiles(asql_content)
        if compiles:
            print("  ✅ ASQL compiles successfully")
            return True, None
        else:
            print(f"  ⚠️  ASQL compilation failed: {result}")
            return False, result
    
    return True, None


def create_asql_equivalent(sql_content: str) -> Optional[str]:
    """Create ASQL equivalent from SQL (basic conversion).
    
    This is a placeholder - real conversion would require full SQL parsing.
    For now, we'll create a note that ASQL needs to be written manually.
    """
    # TODO: Implement proper SQL to ASQL conversion
    # For now, return None to indicate manual conversion needed
    return None


def main():
    """Main function to fetch all queries."""
    output_dir = Path(__file__).parent.parent / "examples" / "real"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_fetched = 0
    total_compiled = 0
    failed_compiles = []
    
    for repo_name, repo_info in REPOS.items():
        print(f"\n{'='*60}")
        print(f"Fetching from {repo_name}...")
        print(f"{'='*60}")
        base_url = repo_info["base_url"]
        dialect = repo_info["dialect"]
        
        for model_path in repo_info["models"]:
            model_name = extract_model_name(model_path)
            url = f"{base_url}/{model_path}"
            
            print(f"\n  Fetching {model_name}...")
            sql_content = fetch_sql_file(url)
            
            if sql_content:
                # For now, save SQL only - ASQL will be written manually
                # and tested separately
                asql_content = None  # Will be written manually later
                success, error = save_query(
                    repo_name, model_name, dialect, sql_content, asql_content, output_dir
                )
                total_fetched += 1
                if success and asql_content:
                    total_compiled += 1
                elif not success:
                    failed_compiles.append((repo_name, model_name, error))
                time.sleep(0.3)  # Be nice to GitHub
            else:
                print(f"  ❌ Failed to fetch {model_name}")
    
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  ✅ Fetched {total_fetched} SQL queries")
    print(f"  ✅ Compiled {total_compiled} ASQL queries")
    if failed_compiles:
        print(f"  ⚠️  {len(failed_compiles)} ASQL queries failed to compile")
    print(f"\nSaved to: {output_dir}")
    
    if failed_compiles:
        print("\nFailed compilations:")
        for repo, model, error in failed_compiles:
            print(f"  - {repo}/{model}: {error}")


if __name__ == "__main__":
    main()

