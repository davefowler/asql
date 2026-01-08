"""PostgreSQL-specific tests for ASQL.

Tests ASQL compilation targeting PostgreSQL dialect.
"""

from tests.validator import ASQLValidator, ASQLDialectError


class TestPostgresBasic(ASQLValidator):
    """Basic PostgreSQL compilation tests."""
    
    target_dialect = "postgres"
    
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


class TestPostgresGroupBy(ASQLValidator):
    """PostgreSQL GROUP BY tests."""
    
    target_dialect = "postgres"
    
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
    
    def test_group_by_multiple_aggregates(self) -> None:
        """Test GROUP BY with multiple aggregations."""
        self.validate_contains(
            "from sales group by region ( sum(amount) as revenue, # as orders )",
            "GROUP BY", "SUM", "COUNT", "region", "revenue", "orders"
        )


class TestPostgresCoalesce(ASQLValidator):
    """PostgreSQL coalesce operator tests."""
    
    target_dialect = "postgres"
    
    def test_simple_coalesce(self) -> None:
        """Test ?? coalesce operator."""
        self.validate_asql(
            "from users select name ?? 'Unknown' as display_name",
            "SELECT COALESCE(name, 'Unknown') AS display_name FROM users"
        )
    
    def test_chained_coalesce(self) -> None:
        """Test chained ?? operators."""
        self.validate_contains(
            "from users select first_name ?? nickname ?? 'Unknown' as name",
            "COALESCE", "first_name", "nickname", "Unknown"
        )


class TestPostgresJoins(ASQLValidator):
    """PostgreSQL JOIN tests."""
    
    target_dialect = "postgres"
    
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
    
    def test_cross_join_operator(self) -> None:
        """Test * operator for CROSS JOIN."""
        self.validate_contains(
            "from users * roles",
            "CROSS JOIN", "users", "roles"
        )


class TestPostgresPivot(ASQLValidator):
    """PostgreSQL PIVOT tests."""
    
    target_dialect = "postgres"
    
    def test_pivot_with_values(self) -> None:
        """Test pivot with explicit values - PostgreSQL uses CASE/WHEN fallback."""
        self.validate_contains(
            "from sales pivot sum(amount) by category values ('A', 'B')",
            "CASE WHEN"
        )


class TestPostgresWhen(ASQLValidator):
    """PostgreSQL WHEN conditional tests."""
    
    target_dialect = "postgres"
    
    def test_simple_when(self) -> None:
        """Test simple when expression."""
        self.validate_contains(
            'from users select when status is "active" then 1 else 0 as is_active',
            "CASE", "WHEN", "status", "active", "THEN", "ELSE", "END"
        )
    
    def test_when_with_comparison(self) -> None:
        """Test when with comparison operators."""
        self.validate_contains(
            'from users select when age < 18 then "minor" else "adult" as age_group',
            "CASE", "WHEN", "age", "<", "18", "THEN", "ELSE", "END"
        )


class TestPostgresDateFunctions(ASQLValidator):
    """PostgreSQL date function tests."""
    
    target_dialect = "postgres"
    
    def test_date_literal(self) -> None:
        """Test @date literal syntax."""
        self.validate_contains(
            "from users where created_at >= @2024-01-15",
            "2024-01-15"
        )
    
    def test_relative_date(self) -> None:
        """Test relative date syntax."""
        self.validate_contains(
            "from users where created_at >= 7 days ago",
            "INTERVAL"
        )


class TestPostgresExplode(ASQLValidator):
    """PostgreSQL explode/unnest tests."""
    
    target_dialect = "postgres"
    
    def test_explode_array(self) -> None:
        """Test explode syntax for arrays."""
        self.validate_contains(
            "from posts explode tags as tag select id, tag",
            "UNNEST"
        )


class TestPostgresSlice(ASQLValidator):
    """PostgreSQL slice syntax tests."""
    
    target_dialect = "postgres"
    
    def test_basic_slice(self) -> None:
        """Test basic slice [start:end]."""
        self.validate_contains(
            "from users select email[1:5] as prefix",
            "SUBSTRING"
        )
    
    def test_slice_from_start(self) -> None:
        """Test slice [:end] becomes LEFT."""
        self.validate_contains(
            "from users select email[:5] as prefix",
            "LEFT"
        )
    
    def test_negative_slice(self) -> None:
        """Test slice [-n:] becomes RIGHT."""
        self.validate_contains(
            "from users select email[-5:] as last_five",
            "RIGHT"
        )
