"""ASQL DERIVE examples."""

from asql import compile

# Example 1: Simple DERIVE
def example_derive_simple():
    """Simple DERIVE with column reference."""
    asql = "from users derive age as age"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 2: DERIVE with WHERE
def example_derive_with_where():
    """DERIVE with WHERE clause."""
    asql = 'from users where status == "active" derive age as age'
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 3: Multiple DERIVE
def example_multiple_derive():
    """Multiple DERIVE clauses."""
    asql = """from users 
derive full_name as name
derive age_category as age"""
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

if __name__ == "__main__":
    print("=== Derived Columns Examples ===\n")
    example_derive_simple()
    print()
    example_derive_with_where()
    print()
    example_multiple_derive()
