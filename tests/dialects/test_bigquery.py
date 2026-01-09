"""BigQuery-specific tests for ASQL.

Tests ASQL compilation targeting BigQuery dialect.
"""

from tests.validator import ASQLValidator


class TestBigQueryBasic(ASQLValidator):
    """Basic BigQuery compilation tests."""
    
    target_dialect = "bigquery"
    
    def test_simple_from(self) -> None:
        """Test simple FROM clause."""
        self.validate_asql(
            "from users",
            "SELECT * FROM users"
        )
    
    def test_from_with_select(self) -> None:
        """Test FROM with explicit SELECT."""
        self.validate_asql(
            "from users select name, email",
            "SELECT name, email FROM users"
        )
    
    def test_from_with_where(self) -> None:
        """Test FROM with WHERE clause."""
        self.validate_asql(
            "from users where active = true",
            "SELECT * FROM users WHERE active = TRUE"
        )
    
    def test_from_with_limit(self) -> None:
        """Test FROM with LIMIT clause."""
        self.validate_asql(
            "from users limit 10",
            "SELECT * FROM users LIMIT 10"
        )
    
    def test_order_by_ascending(self) -> None:
        """Test ORDER BY ascending (default)."""
        self.validate_asql(
            "from users order by name",
            "SELECT * FROM users ORDER BY name"
        )
    
    def test_order_by_descending(self) -> None:
        """Test ORDER BY descending with - prefix."""
        self.validate_asql(
            "from users order by -created_at",
            "SELECT * FROM users ORDER BY created_at DESC"
        )


class TestBigQueryGroupBy(ASQLValidator):
    """BigQuery GROUP BY tests."""
    
    target_dialect = "bigquery"
    
    def test_group_by_count(self) -> None:
        """Test GROUP BY with COUNT shorthand."""
        self.validate_contains(
            "from users group by country ( # as total )",
            "country", "COUNT(*)", "total", "GROUP BY"
        )
    
    def test_group_by_sum(self) -> None:
        """Test GROUP BY with SUM."""
        self.validate_contains(
            "from sales group by region ( sum(amount) as revenue )",
            "region", "SUM", "amount", "revenue", "GROUP BY"
        )


class TestBigQueryCoalesce(ASQLValidator):
    """BigQuery coalesce operator tests."""
    
    target_dialect = "bigquery"
    
    def test_simple_coalesce(self) -> None:
        """Test ?? coalesce operator."""
        self.validate_asql(
            "from users select name ?? 'Unknown' as display_name",
            "SELECT COALESCE(name, 'Unknown') AS display_name FROM users"
        )


class TestBigQueryJoins(ASQLValidator):
    """BigQuery JOIN tests."""
    
    target_dialect = "bigquery"
    
    def test_inner_join_operator(self) -> None:
        """Test & operator for INNER JOIN."""
        self.validate_contains(
            "from users & orders on users.id = orders.user_id",
            "JOIN", "users", "orders", "ON"
        )
    
    def test_left_join_operator(self) -> None:
        """Test &? operator for LEFT JOIN."""
        self.validate_contains(
            "from users &? orders on users.id = orders.user_id",
            "LEFT", "JOIN", "users", "orders"
        )


class TestBigQueryPivot(ASQLValidator):
    """BigQuery PIVOT tests."""
    
    target_dialect = "bigquery"
    
    def test_pivot_with_values(self) -> None:
        """Test pivot with explicit values - BigQuery uses native PIVOT."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "PIVOT"
        )


class TestBigQueryWhen(ASQLValidator):
    """BigQuery WHEN conditional tests."""
    
    target_dialect = "bigquery"
    
    def test_simple_when(self) -> None:
        """Test simple when expression."""
        self.validate_contains(
            'from users select when status is "active" then 1 else 0 as is_active',
            "CASE", "WHEN", "status", "active", "THEN", "ELSE", "END"
        )


class TestBigQueryExplode(ASQLValidator):
    """BigQuery explode/unnest tests."""
    
    target_dialect = "bigquery"
    
    def test_explode_array(self) -> None:
        """Test explode syntax for arrays."""
        self.validate_contains(
            "from posts explode tags as tag select id, tag",
            "UNNEST"
        )
