"""Basic ASQL query examples."""

from asql import compile

# Example 1: Simple FROM
def example_simple_from():
    """Basic FROM clause."""
    asql = "from users"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 2: FROM with WHERE
def example_from_where():
    """FROM with WHERE clause."""
    asql = 'from users where status == "active"'
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 3: FROM with SELECT
def example_from_select():
    """FROM with SELECT clause."""
    asql = "from users select name, email"
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 4: FROM WHERE SELECT
def example_from_where_select():
    """FROM, WHERE, and SELECT together."""
    asql = 'from users where status == "active" select name, email'
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 5: Multiple WHERE conditions
def example_multiple_where():
    """Multiple WHERE conditions with AND."""
    asql = 'from users where status == "active" and age >= 18 and email is not null'
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 6: OR conditions
def example_or_conditions():
    """WHERE with OR conditions."""
    asql = 'from users where status == "active" or status == "pending"'
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 7: NOT operator
def example_not_operator():
    """WHERE with NOT operator."""
    asql = 'from users where not status == "inactive"'
    sql = compile(asql)
    print("ASQL:", asql)
    print("SQL:", sql)
    return asql, sql

# Example 8: Comparison operators
def example_comparisons():
    """Various comparison operators."""
    examples = [
        ('from users where age < 18', "Less than"),
        ('from users where age > 65', "Greater than"),
        ('from users where age <= 18', "Less than or equal"),
        ('from users where age >= 18', "Greater than or equal"),
        ('from users where status != "inactive"', "Not equal"),
        ('from users where email is null', "IS NULL"),
        ('from users where email is not null', "IS NOT NULL"),
    ]
    
    for asql, desc in examples:
        sql = compile(asql)
        print(f"\n{desc}:")
        print("ASQL:", asql)
        print("SQL:", sql)
    
    return examples

if __name__ == "__main__":
    print("=== Basic ASQL Examples ===\n")
    example_simple_from()
    print()
    example_from_where()
    print()
    example_from_select()
    print()
    example_from_where_select()
    print()
    example_multiple_where()
    print()
    example_or_conditions()
    print()
    example_not_operator()
    print()
    example_comparisons()
