"""Tests for ?? coalesce operator in ASQL.

The ?? operator provides a concise syntax for COALESCE:
- a ?? b → COALESCE(a, b)
- a ?? b ?? c → COALESCE(a, b, c)
"""

from tests.validator import ASQLValidator


class TestCoalesceBasic(ASQLValidator):
    """Test basic ?? coalesce operator."""
    
    def test_simple_coalesce(self) -> None:
        """a ?? b becomes COALESCE(a, b)."""
        self.validate_all(
            "from users select name ?? 'Unknown' as display_name",
            write={
                "duckdb": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                "postgres": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                "mysql": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                "sqlite": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                "bigquery": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                "snowflake": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
            }
        )
    
    def test_chained_coalesce(self) -> None:
        """a ?? b ?? c becomes COALESCE(a, b, c)."""
        self.validate_contains(
            "from users select first_name ?? nickname ?? 'Unknown' as name",
            "COALESCE", "first_name", "nickname", "Unknown"
        )


class TestCoalesceInClauses(ASQLValidator):
    """Test ?? in different SQL clauses."""
    
    def test_coalesce_in_where(self) -> None:
        """Test ?? in WHERE clause."""
        self.validate_contains(
            "from users where (is_deleted ?? false) = false",
            "COALESCE", "is_deleted", "WHERE"
        )
    
    def test_coalesce_in_select(self) -> None:
        """Test ?? in SELECT clause."""
        self.validate_contains(
            "from users select email ?? phone ?? 'no contact' as contact",
            "COALESCE", "email", "phone", "contact"
        )
    
    def test_coalesce_with_not(self) -> None:
        """Test NOT (expr ?? default)."""
        self.validate_contains(
            "from users where not (is_deleted ?? false)",
            "NOT", "COALESCE", "is_deleted"
        )


class TestCoalesceWithFunctions(ASQLValidator):
    """Test ?? with function calls."""
    
    def test_coalesce_with_function_result(self) -> None:
        """Test ?? with function as operand."""
        self.validate_contains(
            "from users select upper(name) ?? 'UNKNOWN' as upper_name",
            "COALESCE", "UPPER", "name"
        )


class TestCoalesceCrossDialect(ASQLValidator):
    """Cross-dialect coalesce tests."""
    
    def test_coalesce_numeric_default(self) -> None:
        """Test ?? with numeric default across dialects."""
        self.validate_all(
            "from orders select amount ?? 0 as amount_safe",
            write={
                "duckdb": "SELECT COALESCE(amount, 0) AS amount_safe FROM orders",
                "postgres": "SELECT COALESCE(amount, 0) AS amount_safe FROM orders",
                "mysql": "SELECT COALESCE(amount, 0) AS amount_safe FROM orders",
                "sqlite": "SELECT COALESCE(amount, 0) AS amount_safe FROM orders",
            }
        )
