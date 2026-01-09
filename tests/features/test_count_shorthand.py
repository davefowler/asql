"""Tests for # count shorthand syntax in ASQL.

The # symbol is a shorthand for COUNT(*) in ASQL.
Variations:
- # → COUNT(*)
- #(col) → COUNT(col)
- # table → COUNT(DISTINCT table_id)
- # of table → COUNT(DISTINCT table_id)
- # * → COUNT(*) (explicit row count)
"""

from tests.validator import ASQLValidator


class TestCountShorthandBasic(ASQLValidator):
    """Test basic # count shorthand."""
    
    def test_standalone_hash_to_count_star(self) -> None:
        """# becomes COUNT(*) - may be auto-aliased as 'num'."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite", "bigquery", "snowflake"]:
            self.validate_contains(
                "from users select #",
                "COUNT(*)", "FROM", "users",
                dialect=dialect
            )
    
    def test_hash_with_alias(self) -> None:
        """# as alias becomes COUNT(*) AS alias."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from users select # as total",
                "COUNT(*)", "AS", "total", "FROM", "users",
                dialect=dialect
            )
    
    def test_hash_in_group_by(self) -> None:
        """# in GROUP BY aggregate block."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from users group by country ( # as total )",
                "country", "COUNT(*)", "total", "GROUP BY",
                dialect=dialect
            )


class TestCountShorthandColumn(ASQLValidator):
    """Test #(column) count shorthand."""
    
    def test_hash_column(self) -> None:
        """#(col) becomes COUNT(col)."""
        self.validate_contains(
            "from users select #(email) as has_email",
            "COUNT", "email", "has_email"
        )


class TestCountShorthandTable(ASQLValidator):
    """Test # table count distinct shorthand."""
    
    def test_hash_table_name(self) -> None:
        """# table becomes COUNT(DISTINCT table_id)."""
        self.validate_contains(
            "from orders select # users as unique_customers",
            "COUNT", "DISTINCT", "USER_ID"
        )
    
    def test_hash_of_table(self) -> None:
        """# of table becomes COUNT(DISTINCT table_id)."""
        self.validate_contains(
            "from orders select # of users as unique_customers",
            "COUNT", "DISTINCT", "USER_ID"
        )
    
    def test_hash_explicit_star(self) -> None:
        """# * becomes COUNT(*) (explicit row count)."""
        self.validate_contains(
            "from orders select # * as row_count",
            "COUNT(*)"
        )


class TestCountShorthandOrderBy(ASQLValidator):
    """Test # in ORDER BY clause."""
    
    def test_order_by_count_hash(self) -> None:
        """ORDER BY -# for descending count order."""
        self.validate_contains(
            "from users group by country ( # ) order by -#",
            "ORDER BY", "COUNT", "DESC"
        )
    
    def test_order_by_count_hash_alias(self) -> None:
        """ORDER BY -alias where alias is from # as alias."""
        self.validate_contains(
            "from users group by country ( # as cnt ) order by -cnt",
            "ORDER BY", "cnt", "DESC"
        )


class TestCountShorthandCrossDialect(ASQLValidator):
    """Cross-dialect tests for count shorthand."""
    
    def test_group_by_with_count_and_sum(self) -> None:
        """Test # combined with other aggregates."""
        for dialect in ["duckdb", "postgres", "mysql"]:
            self.validate_contains(
                "from sales group by region ( # as orders, sum(amount) as revenue )",
                "region", "COUNT(*)", "orders", "SUM", "amount", "revenue", "GROUP BY",
                dialect=dialect
            )
