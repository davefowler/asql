"""Examples of string matching operators in ASQL."""

from asql import compile


def example_contains() -> None:
    """Example: contains operator for substring matching."""
    asql = 'from users where email contains "@gmail.com"'
    sql = compile(asql, dialect="postgres")
    print("=== Contains Operator ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_icontains() -> None:
    """Example: icontains operator for case-insensitive substring matching."""
    asql = 'from users where email icontains "gmail"'
    sql = compile(asql, dialect="postgres")
    print("=== IContains Operator (Case-Insensitive) ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_starts_with() -> None:
    """Example: starts with operator for prefix matching."""
    asql = 'from users where name starts with "John"'
    sql = compile(asql, dialect="postgres")
    print("=== Starts With Operator ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_istarts_with() -> None:
    """Example: istarts with operator for case-insensitive prefix matching."""
    asql = 'from users where domain istarts with "https://"'
    sql = compile(asql, dialect="postgres")
    print("=== IStarts With Operator (Case-Insensitive) ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_ends_with() -> None:
    """Example: ends with operator for suffix matching."""
    asql = 'from users where filename ends with ".pdf"'
    sql = compile(asql, dialect="postgres")
    print("=== Ends With Operator ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_iends_with() -> None:
    """Example: iends with operator for case-insensitive suffix matching."""
    asql = 'from users where email iends with ".com"'
    sql = compile(asql, dialect="postgres")
    print("=== IEnds With Operator (Case-Insensitive) ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_matches() -> None:
    """Example: matches operator for LIKE pattern matching."""
    asql = 'from users where email matches "%@gmail.com"'
    sql = compile(asql, dialect="postgres")
    print("=== Matches Operator (LIKE Pattern) ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_matches_with_underscore() -> None:
    """Example: matches operator with underscore wildcard."""
    asql = 'from users where phone matches "555-___-____"'
    sql = compile(asql, dialect="postgres")
    print("=== Matches Operator with Underscore Wildcard ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_with_logical_operators() -> None:
    """Example: string matching operators with AND/OR."""
    asql = 'from users where email contains "@gmail.com" and status == "active"'
    sql = compile(asql, dialect="postgres")
    print("=== String Matching with Logical Operators ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_with_function_calls() -> None:
    """Example: string matching operators with function calls."""
    asql = 'from users where upper(name) contains "JOHN"'
    sql = compile(asql, dialect="postgres")
    print("=== String Matching with Function Calls ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


def example_multiple_operators() -> None:
    """Example: multiple string matching operators in one query."""
    asql = 'from users where email contains "@gmail.com" and name starts with "John"'
    sql = compile(asql, dialect="postgres")
    print("=== Multiple String Matching Operators ===")
    print(f"ASQL: {asql}")
    print(f"SQL:  {sql}\n")


if __name__ == "__main__":
    example_contains()
    example_icontains()
    example_starts_with()
    example_istarts_with()
    example_ends_with()
    example_iends_with()
    example_matches()
    example_matches_with_underscore()
    example_with_logical_operators()
    example_with_function_calls()
    example_multiple_operators()
