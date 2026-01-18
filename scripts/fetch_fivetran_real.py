#!/usr/bin/env python3
"""Fetch real SQL queries from Fivetran dbt repositories by discovering actual files.

This script discovers and fetches actual SQL model files from Fivetran's dbt packages.
"""

import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional
import time

# Repos to fetch from
REPOS = [
    "dbt_shopify",
    "dbt_stripe", 
    "dbt_salesforce",
    "dbt_zendesk",
    "dbt_google_ads",
    "dbt_marketo",
]


def fetch_github_api(path: str) -> Optional[Dict]:
    """Fetch from GitHub API."""
    url = f"https://api.github.com/repos/fivetran/{path}"
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", url],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception:
        return None


def discover_sql_files(repo: str, base_path: str = "models") -> List[str]:
    """Recursively discover SQL files in a repo."""
    files = []
    contents = fetch_github_api(f"{repo}/contents/{base_path}")
    
    if not contents:
        return files
    
    # Handle both single file and list of files
    if not isinstance(contents, list):
        contents = [contents]
    
    for item in contents:
        if item.get("type") == "file" and item["name"].endswith(".sql"):
            files.append(item["path"])
        elif item.get("type") == "dir":
            # Recursively search subdirectories
            sub_files = discover_sql_files(repo, item["path"])
            files.extend(sub_files)
    
    return files


def fetch_sql_content(repo: str, file_path: str) -> Optional[str]:
    """Fetch SQL file content."""
    url = f"https://raw.githubusercontent.com/fivetran/{repo}/main/{file_path}"
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", url],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout and not result.stdout.startswith("404"):
            return result.stdout
        return None
    except Exception:
        return None


def extract_model_name(file_path: str) -> str:
    """Extract model name from file path."""
    # e.g., "models/shopify_gql/line_item_enhanced.sql" -> "line_item_enhanced"
    return Path(file_path).stem


def main():
    """Main function."""
    output_dir = Path(__file__).parent.parent / "examples" / "real"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_fetched = 0
    
    for repo in REPOS:
        print(f"\n{'='*60}")
        print(f"Discovering files in {repo}...")
        print(f"{'='*60}")
        
        sql_files = discover_sql_files(repo)
        print(f"Found {len(sql_files)} SQL files")
        
        # Limit to first 10 per repo to avoid too many files
        for file_path in sql_files[:10]:
            model_name = extract_model_name(file_path)
            print(f"  Fetching {model_name}...", end=" ")
            
            sql_content = fetch_sql_content(repo, file_path)
            if sql_content and len(sql_content) > 100:  # Valid SQL file
                # Determine dialect (most Fivetran packages use Snowflake)
                dialect = "snowflake"
                
                # Create filename
                repo_short = repo.replace("dbt_", "")
                filename = f"dbt_{repo_short}_{model_name}_{dialect}.sql"
                filepath = output_dir / filename
                
                # Add header
                header = f"""-- Source: {repo}
-- Model: {model_name}
-- Dialect: {dialect}
-- Repository: https://github.com/fivetran/{repo}
-- File: {file_path}

"""
                
                filepath.write_text(header + sql_content)
                print("✅ Saved")
                total_fetched += 1
                time.sleep(0.3)
            else:
                print("❌ Failed or empty")
            time.sleep(0.2)
    
    print(f"\n{'='*60}")
    print(f"✅ Fetched {total_fetched} SQL queries")
    print(f"Saved to: {output_dir}")


if __name__ == "__main__":
    main()

