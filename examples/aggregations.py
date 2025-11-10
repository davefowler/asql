"""ASQL aggregation examples."""

from asql import compile

# Example 1: GROUP BY with COUNT (#)
def example_group_by_count():
    """GROUP BY with # (COUNT(*))."""
    asql = "from users group by country ( # as total_users )"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 2: GROUP BY with SUM
def example_group_by_sum():
    """GROUP BY with SUM aggregation."""
    asql = "from sales group by region ( sum(amount) as revenue )"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 3: GROUP BY with AVG
def example_group_by_avg():
    """GROUP BY with AVG aggregation."""
    asql = "from users group by country ( avg(age) as avg_age )"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 4: Multiple aggregations
def example_multiple_aggregations():
    """GROUP BY with multiple aggregations."""
    asql = "from sales group by region ( sum(amount) as revenue, # as orders, avg(amount) as avg_order )"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 5: Multiple grouping columns
def example_multiple_grouping():
    """GROUP BY with multiple columns."""
    asql = "from sales group by region, month ( sum(amount) as revenue )"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 6: GROUP BY with WHERE
def example_group_by_where():
    """GROUP BY with WHERE filter."""
    asql = 'from sales where year == 2024 group by region ( sum(amount) as revenue )'
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 7: All aggregation functions
def example_all_aggregations():
    """All aggregation functions."""
    asql = """from sales group by region (
    sum(amount) as total_revenue,
    avg(amount) as avg_order,
    # as order_count,
    min(amount) as min_order,
    max(amount) as max_order
)"""
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

if __name__ == "__main__":
    print("=== Aggregation Examples ===\n")
    example_group_by_count()
    print()
    example_group_by_sum()
    print()
    example_group_by_avg()
    print()
    example_multiple_aggregations()
    print()
    example_multiple_grouping()
    print()
    example_group_by_where()
    print()
    example_all_aggregations()
