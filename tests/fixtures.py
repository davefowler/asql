"""Test fixtures and example datasets for ASQL tests."""

import sqlglot
from typing import Optional



def transpile(
    query: str,
    dialect: str = "duckdb",
    pretty: bool = False,
    settings=None,
    **kwargs,
) -> str:
    """Transpile ASQL to SQL using asql.transpile().
    
    This is a test helper that wraps asql.transpile() with defaults.
    Uses the full ASQL pipeline including dialect-aware transforms.
    
    Args:
        query: ASQL query string
        dialect: Target SQL dialect (default: duckdb)
        pretty: Format output SQL
        settings: CompileSettings object (converted to kwargs)
        **kwargs: Passed to asql.transpile()
    
    Returns:
        SQL string for target dialect
    """
    import asql
    from asql.errors import ASQLSyntaxError
    from asql.config import CompileSettings
    
    if not query or not query.strip():
        raise ASQLSyntaxError("Empty query")
    
    # Convert CompileSettings to kwargs
    if settings is not None:
        defaults = CompileSettings()
        if settings.schema is not None:
            kwargs.setdefault('schema', settings.schema)
        if settings.week_start != defaults.week_start:
            kwargs.setdefault('week_start', settings.week_start)
        if settings.relative_date_type != defaults.relative_date_type:
            kwargs.setdefault('relative_date_type', settings.relative_date_type)
        if settings.alias_template:
            kwargs.setdefault('alias_template', settings.alias_template)
        if settings.alias_prefixes:
            kwargs.setdefault('alias_prefixes', settings.alias_prefixes)
        if settings.alias_templates:
            kwargs.setdefault('alias_templates', settings.alias_templates)
        if settings.infer_join_keys:
            kwargs.setdefault('infer_join_keys', settings.infer_join_keys)
        if hasattr(settings, 'include_transpilation_comments'):
            kwargs.setdefault('include_transpilation_comments', settings.include_transpilation_comments)
        # Always pass passthrough_comments if it's set (handles False explicitly)
        kwargs.setdefault('passthrough_comments', settings.passthrough_comments)
    
    try:
        # Use asql.transpile() for full pipeline (including dialect-aware transforms)
        results = asql.transpile(
            query,
            write=dialect,
            pretty=pretty,
            **kwargs,
        )
        return results[0] if results else ""
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(str(e)) from e


def parse_one(query: str, **kwargs) -> sqlglot.exp.Expression:
    """Parse ASQL to AST.
    
    This is a test helper equivalent to sqlglot.parse_one(query, dialect="asql").
    
    Args:
        query: ASQL query string
        **kwargs: Passed to ASQL dialect constructor
    
    Returns:
        SQLGlot expression AST
    """
    from asql import ASQL
    asql_dialect = ASQL(**kwargs) if kwargs else "asql"
    return sqlglot.parse_one(query, dialect=asql_dialect)

# Example table schemas and sample data descriptions
# These are used for testing query generation and validation

EXAMPLE_SCHEMAS = {
    "users": {
        "columns": ["id", "name", "email", "status", "age", "country", "created_at", "updated_at"],
        "description": "User table with basic profile information"
    },
    "sales": {
        "columns": ["id", "user_id", "amount", "region", "month", "year", "status", "product_category", "created_at"],
        "description": "Sales transactions table"
    },
    "orders": {
        "columns": ["id", "user_id", "total", "status", "created_at"],
        "description": "Order table"
    },
    "events": {
        "columns": ["id", "user_id", "event_type", "created_at"],
        "description": "User events table"
    },
    "opportunities": {
        "columns": ["id", "owner_id", "amount", "status", "org_type", "created_at"],
        "description": "Sales opportunities table"
    },
    "owners": {
        "columns": ["id", "name", "is_active"],
        "description": "Sales owners/representatives table"
    },
}

# Common test queries that should work
VALID_ASQL_QUERIES = [
    # Basic queries
    "from users",
    "from users select name, email",
    'from users where status == "active"',
    
    # WHERE with comparisons
    "from users where age < 18",
    "from users where age > 65",
    "from users where age >= 18",
    "from users where age <= 65",
    'from users where status != "inactive"',
    
    # NULL checks
    "from users where email is null",
    "from users where email is not null",
    
    # Logical operators
    'from users where status == "active" and age >= 18',
    'from users where status == "active" or status == "pending"',
    'from users where not status == "inactive"',
    
    # IN / NOT IN
    'from users where status in ("active", "pending")',
    'from users where status not in ("inactive", "deleted")',
    "from users where age in (18, 19, 20)",
    
    # GROUP BY
    "from users group by country ( # as total_users )",
    "from sales group by region ( sum(amount) as revenue )",
    "from sales group by region ( sum(amount) as revenue, # as orders )",
    "from sales group by region, month ( sum(amount) as revenue )",
    
    # ORDER BY
    "from users order by name",
    "from users order by -total_users",
    "from users order by -updated_at, name",
    "from users order by month(created_at)",
    
    # TAKE
    "from users limit 10",
    
    # Complex pipelines
    'from users where status == "active" group by country ( # as total_users ) order by -total_users limit 10',
    'from sales where status == "completed" group by region ( sum(amount) as revenue ) order by -revenue limit 5',
]

# Queries that should fail with specific errors
INVALID_ASQL_QUERIES = [
    ("", "Empty query"),
    # Note: The following are no longer strict ASQL requirements with the new SQLGlot-based parser
    # The new parser is more permissive and accepts valid SQL even if it doesn't follow ASQL conventions
    ("from", "Missing table name"),
    ("from users where", "Missing WHERE condition"),
    ("from users order by", "Missing ORDER BY columns"),
]

# Edge cases to test
EDGE_CASES = [
    # Very long queries
    'from users where status == "active" and age >= 18 and email is not null and country == "US"',
    
    # Multiple conditions
    'from users where status == "active" or status == "pending" or status == "verified"',
    
    # Complex IN lists
    'from users where status in ("active", "pending", "verified", "approved", "confirmed")',
    
    # Nested logical operators
    'from users where (status == "active" or status == "pending") and age >= 18',
    
    # Multiple aggregations
    "from sales group by region ( sum(amount) as revenue, avg(amount) as avg_order, # as orders, min(amount) as min_order, max(amount) as max_order )",
    
    # Multiple ORDER BY columns
    "from users order by -total_users, name, -age",

    # Function calls in ORDER BY
    "from users order by -month(updated_at), year(created_at), name",
]


def assert_valid_sql(sql: str, dialect: Optional[str] = None) -> None:
    """
    Assert that SQL can be parsed by SQLGlot.
    
    Args:
        sql: SQL string to validate
        dialect: Optional SQL dialect (defaults to None for auto-detection)
    
    Raises:
        AssertionError: If SQL cannot be parsed
    """
    try:
        parsed = sqlglot.parse_one(sql, dialect=dialect)
        assert parsed is not None, f"SQLGlot returned None for SQL: {sql}"
        assert hasattr(parsed, 'sql'), "Parsed result doesn't have sql() method"
    except sqlglot.errors.ParseError as e:
        raise AssertionError(f"SQLGlot couldn't parse generated SQL: {e}\nSQL: {sql}") from e


def assert_sql_contains(sql: str, *substrings: str, case_sensitive: bool = False) -> None:
    """
    Assert that SQL contains all specified substrings.
    
    Args:
        sql: SQL string to check
        *substrings: Substrings that must be present
        case_sensitive: Whether to do case-sensitive matching
    
    Raises:
        AssertionError: If any substring is not found
    """
    check_sql = sql if case_sensitive else sql.lower()
    for substring in substrings:
        check_substring = substring if case_sensitive else substring.lower()
        assert check_substring in check_sql, (
            f"Expected substring '{substring}' not found in SQL:\n{sql}"
        )


def assert_sql_structure(sql: str, **kwargs: str) -> None:
    """
    Assert that SQL has correct structural elements in order.
    
    Args:
        sql: SQL string to check
        **kwargs: Keyword arguments mapping element names to their expected order
                   e.g., FROM=0, WHERE=1, GROUP_BY=2 means FROM comes before WHERE, etc.
    
    Raises:
        AssertionError: If structure is incorrect
    """
    import re
    # Strip block comments /* ... */ before checking structure
    # This prevents transpilation comments from interfering with structure checks
    sql_no_comments = re.sub(r'/\*[^*]*\*/', '', sql)
    sql_upper = sql_no_comments.upper()
    positions = {}
    for element, _ in kwargs.items():
        pos = sql_upper.find(element.replace('_', ' '))
        if pos == -1:
            raise AssertionError(f"Element '{element}' not found in SQL:\n{sql}")
        positions[element] = pos
    
    # Check ordering
    sorted_elements = sorted(positions.items(), key=lambda x: x[1])
    expected_order = list(kwargs.keys())
    actual_order = [elem for elem, _ in sorted_elements]
    
    # Verify order matches (allowing for elements that can be in any order)
    for i, expected in enumerate(expected_order):
        if expected in actual_order:
            expected_pos = actual_order.index(expected)
            # Check that elements that should come before this one do
            for j in range(i):
                if expected_order[j] in actual_order:
                    prev_pos = actual_order.index(expected_order[j])
                    if prev_pos > expected_pos:
                        raise AssertionError(
                            f"Element '{expected_order[j]}' should come before '{expected}' "
                            f"in SQL:\n{sql}"
                        )
