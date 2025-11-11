"""Complex ASQL query examples combining multiple features."""

from asql import compile

# Example 1: Complex analytics query
def example_complex_analytics():
    """Complex analytics query with filtering, grouping, and sorting."""
    asql = """from sales 
where status == "completed" and amount > 100
group by region, month ( 
    sum(amount) as revenue,
    # as order_count,
    avg(amount) as avg_order
)
sort -revenue
take 20"""
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 2: User analytics
def example_user_analytics():
    """User analytics with multiple conditions."""
    asql = """from users
where status == "active" and age >= 18 and email is not null
group by country (
    # as total_users,
    avg(age) as avg_age
)
sort -total_users"""
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 3: Sales report
def example_sales_report():
    """Sales report with complex filtering."""
    asql = """from sales
where (status == "completed" or status == "pending") 
    and amount >= 50 
    and created_at is not null
group by product_category (
    sum(amount) as total_revenue,
    # as total_orders,
    avg(amount) as avg_order_value,
    max(amount) as max_order_value
)
sort -total_revenue
take 10"""
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 4: Time-based analysis
def example_time_analysis():
    """Time-based analysis with grouping."""
    asql = """from events
where event_type == "signup" and created_at is not null
group by month (
    # as signups
)
sort month"""
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

if __name__ == "__main__":
    print("=== Complex Query Examples ===\n")
    example_complex_analytics()
    print("\n" + "="*60 + "\n")
    example_user_analytics()
    print("\n" + "="*60 + "\n")
    example_sales_report()
    print("\n" + "="*60 + "\n")
    example_time_analysis()
