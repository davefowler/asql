"""Tests for # count shorthand syntax in ASQL.

The # symbol is a shorthand for COUNT in ASQL.
Variations:
- # → COUNT(*)
- #col or # col → COUNT(col)
- ##col or ## col → COUNT(DISTINCT col)
- #(col) → COUNT(col)
- #(distinct col) → COUNT(DISTINCT col)
- uniq(col) or uniq col → COUNT(DISTINCT col)
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
    """Test #col count shorthand for COUNT(col)."""
    
    def test_hash_column_no_space(self) -> None:
        """#col becomes COUNT(col)."""
        self.validate_contains(
            "from users select #email as has_email",
            "COUNT", "email", "has_email"
        )
    
    def test_hash_column_with_space(self) -> None:
        """# col becomes COUNT(col)."""
        self.validate_contains(
            "from users select # email as has_email",
            "COUNT", "email", "has_email"
        )
    
    def test_hash_parens(self) -> None:
        """#(col) becomes COUNT(col)."""
        self.validate_contains(
            "from users select #(email) as has_email",
            "COUNT", "email", "has_email"
        )


class TestCountDistinctShorthand(ASQLValidator):
    """Test ##col count distinct shorthand."""
    
    def test_double_hash_no_space(self) -> None:
        """##col becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select ##user_id as unique_customers",
            "COUNT", "DISTINCT", "user_id", "unique_customers"
        )
    
    def test_double_hash_with_space(self) -> None:
        """## col becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select ## user_id as unique_customers",
            "COUNT", "DISTINCT", "user_id", "unique_customers"
        )
    
    def test_hash_parens_distinct(self) -> None:
        """#(distinct col) becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select #(distinct user_id) as unique_customers",
            "COUNT", "DISTINCT", "user_id"
        )


class TestUniqFunction(ASQLValidator):
    """Test uniq() function for COUNT(DISTINCT col)."""
    
    def test_uniq_with_parens(self) -> None:
        """uniq(col) becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select uniq(user_id) as unique_customers",
            "COUNT", "DISTINCT", "user_id", "unique_customers"
        )
    
    def test_uniq_space_notation(self) -> None:
        """uniq col becomes COUNT(DISTINCT col)."""
        self.validate_contains(
            "from orders select uniq user_id as unique_customers",
            "COUNT", "DISTINCT", "user_id", "unique_customers"
        )
    
    def test_uniq_in_group_by(self) -> None:
        """uniq in GROUP BY aggregate block."""
        self.validate_contains(
            "from orders group by region ( uniq(user_id) as unique_customers )",
            "COUNT", "DISTINCT", "user_id", "unique_customers", "GROUP BY"
        )


class TestCountShorthandStar(ASQLValidator):
    """Test explicit * count shorthand."""
    
    def test_hash_explicit_star(self) -> None:
        """# * becomes COUNT(*) (explicit row count)."""
        self.validate_contains(
            "from orders select # * as row_count",
            "COUNT(*)"
        )
    
    def test_hash_star_no_space(self) -> None:
        """#* becomes COUNT(*)."""
        self.validate_contains(
            "from orders select #* as row_count",
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
    
    def test_double_hash_cross_dialect(self) -> None:
        """Test ## works across dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from orders select ##user_id as uniq_users",
                "COUNT", "DISTINCT", "user_id",
                dialect=dialect
            )
    
    def test_uniq_cross_dialect(self) -> None:
        """Test uniq() works across dialects."""
        for dialect in ["duckdb", "postgres", "mysql", "sqlite"]:
            self.validate_contains(
                "from orders select uniq(user_id) as uniq_users",
                "COUNT", "DISTINCT", "user_id",
                dialect=dialect
            )
