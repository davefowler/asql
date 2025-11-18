#!/usr/bin/env python3
"""Helper script to generate SQL for multiple dialects from ASQL queries."""

from asql import compile
from typing import Dict

DIALECTS = {
    "PostgreSQL": "postgres",
    "MySQL": "mysql",
    "BigQuery": "bigquery",
    "Snowflake": "snowflake",
    "Redshift": "redshift",
}


def generate_sql_for_dialects(asql_query: str) -> Dict[str, str]:
    """Generate SQL for all supported dialects."""
    results = {}
    for name, dialect in DIALECTS.items():
        try:
            sql = compile(asql_query, dialect=dialect, pretty=True)
            results[name] = sql
        except Exception as e:
            results[name] = f"Error: {str(e)}"
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python generate_example_sql.py '<asql_query>'")
        sys.exit(1)
    
    asql = sys.argv[1]
    results = generate_sql_for_dialects(asql)
    
    for dialect, sql in results.items():
        print(f"\n{dialect}:")
        print(sql)

