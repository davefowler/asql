"""Test fixtures and example datasets for ASQL tests."""

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
    "from users take 10",
    
    # Complex pipelines
    'from users where status == "active" group by country ( # as total_users ) order by -total_users take 10',
    'from sales where status == "completed" group by region ( sum(amount) as revenue ) order by -revenue take 5',
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
