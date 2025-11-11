"""ASQL sorting and limiting examples."""

from asql import compile

# Example 1: Simple SORT ascending
def example_sort_ascending():
    """SORT in ascending order."""
    asql = "from users sort name"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 2: SORT descending
def example_sort_descending():
    """SORT in descending order."""
    asql = "from users sort -total_users"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 3: Multiple sort columns
def example_sort_multiple():
    """SORT with multiple columns."""
    asql = "from users sort -total_users, name"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 4: TAKE/LIMIT
def example_take():
    """TAKE to limit results."""
    asql = "from users take 10"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 5: GROUP BY + SORT
def example_group_by_sort():
    """GROUP BY followed by SORT."""
    asql = "from users group by country ( # as total_users ) sort -total_users"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 6: Complete pipeline
def example_complete_pipeline():
    """Complete pipeline: WHERE, GROUP BY, SORT, TAKE."""
    asql = """from users 
where status == "active" 
group by country ( # as total_users ) 
sort -total_users 
take 10"""
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 7: Top N by revenue
def example_top_n():
    """Top N results by revenue."""
    asql = "from sales group by region ( sum(amount) as revenue ) sort -revenue take 5"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 8: Sort by column descending
def example_sort_by_column_descending():
    """SORT by column in descending order."""
    asql = "from users sort -updated_at"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 9: Sort by column with multiple columns
def example_sort_column_multiple():
    """SORT by column with multiple columns."""
    asql = "from users sort -updated_at, name"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

if __name__ == "__main__":
    print("=== Sorting and Limiting Examples ===\n")
    example_sort_ascending()
    print()
    example_sort_descending()
    print()
    example_sort_multiple()
    print()
    example_take()
    print()
    example_group_by_sort()
    print()
    example_complete_pipeline()
    print()
    example_top_n()
    print()
    example_sort_by_column_descending()
    print()
    example_sort_column_multiple()
