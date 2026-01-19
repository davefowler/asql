"""Tests for column operators in ASQL.

Column operators:
- except col1, col2 → SELECT * EXCEPT(col1, col2) (or EXCLUDE on DuckDB)
- rename col1 as new_col1 → SELECT * EXCEPT(col1), col1 AS new_col1
- replace col with expr → SELECT * EXCEPT(col), expr AS col
- extend expr as new_col → SELECT *, expr AS new_col
"""

from tests.validator import ASQLValidator


class TestExceptOperator(ASQLValidator):
    """Test except column operator.
    
    Note: DuckDB/Snowflake use EXCLUDE; BigQuery/Postgres use EXCEPT.
    """
    
    def test_except_single(self) -> None:
        """Except single column (BigQuery uses EXCEPT)."""
        self.validate_contains(
            "from users except email",
            "EXCEPT", "EMAIL",
            dialect="bigquery"
        )
    
    def test_except_multiple(self) -> None:
        """Except multiple columns (BigQuery uses EXCEPT)."""
        self.validate_contains(
            "from users except email, phone, ssn",
            "EXCEPT", "EMAIL", "PHONE", "SSN",
            dialect="bigquery"
        )
    
    def test_exclude_duckdb(self) -> None:
        """DuckDB/Snowflake use EXCLUDE syntax instead of EXCEPT."""
        self.validate_contains(
            "from users except email",
            "EXCLUDE", "EMAIL",
            dialect="duckdb"
        )


class TestRenameOperator(ASQLValidator):
    """Test rename column operator."""
    
    def test_rename_single(self) -> None:
        """Rename single column."""
        # Use bigquery for EXCEPT syntax
        self.validate_contains(
            "from users rename id as user_id",
            "USER_ID", "EXCEPT",
            dialect="bigquery"
        )
    
    def test_rename_multiple(self) -> None:
        """Rename multiple columns."""
        self.validate_contains(
            "from users rename id as user_id, name as user_name",
            "USER_ID", "USER_NAME"
        )


class TestReplaceOperator(ASQLValidator):
    """Test replace column operator."""
    
    def test_replace_single(self) -> None:
        """Replace single column."""
        # Use bigquery for EXCEPT syntax
        self.validate_contains(
            "from users replace name with upper(name)",
            "UPPER(NAME)", "EXCEPT",
            dialect="bigquery"
        )
    
    def test_replace_multiple(self) -> None:
        """Replace multiple columns."""
        self.validate_contains(
            "from users replace name with upper(name), email with lower(email)",
            "UPPER(NAME)", "LOWER(EMAIL)"
        )
    
    def test_replace_with_function_args(self) -> None:
        """Replace with function that has comma in args."""
        self.validate_contains(
            "from users replace price with round(price, 2)",
            "ROUND(PRICE, 2)"
        )


class TestExtendOperator(ASQLValidator):
    """Test extend operator for adding computed columns."""
    
    def test_extend_simple_expression(self) -> None:
        """Extend with simple expression."""
        self.validate_contains(
            "from users extend age > 15 as is_adult",
            "SELECT", "AGE > 15", "IS_ADULT"
        )
    
    def test_extend_function_call(self) -> None:
        """Extend with function call."""
        self.validate_contains(
            "from users extend upper(name) as name_upper",
            "UPPER(NAME)", "NAME_UPPER"
        )
    
    def test_extend_multiple(self) -> None:
        """Multiple extend statements."""
        self.validate_contains(
            "from users extend age > 15 as is_adult extend age > 65 as is_senior",
            "IS_ADULT", "IS_SENIOR"
        )


class TestCombinedOperators(ASQLValidator):
    """Test combining multiple column operators."""
    
    def test_combined_except_rename_replace(self) -> None:
        """Combine except, rename, replace."""
        self.validate_contains(
            "from users except password rename id as user_id replace name with upper(name)",
            "PASSWORD", "USER_ID", "UPPER(NAME)"
        )


class TestStarColumnOverride(ASQLValidator):
    """Test SELECT *, expr AS col → SELECT * EXCEPT(col), expr AS col."""
    
    def test_single_override(self) -> None:
        """Single column override adds EXCEPT (or EXCLUDE on DuckDB)."""
        # Use bigquery for EXCEPT syntax
        self.validate_contains(
            "from users select *, upper(name) as name",
            "EXCEPT", "NAME",
            dialect="bigquery"
        )
    
    def test_multiple_overrides(self) -> None:
        """Multiple column overrides."""
        # Use bigquery for EXCEPT syntax
        self.validate_contains(
            "from users select *, upper(name) as name, lower(email) as email",
            "EXCEPT",
            dialect="bigquery"
        )
