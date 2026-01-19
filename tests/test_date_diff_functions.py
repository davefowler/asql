"""Tests for date difference functions: days_since, months_until, etc.

These functions support 3 syntax variants:
1. Function call: days_since(created_at)
2. Space notation: days since created_at
3. Underscore alias: days_since_created_at (preparser, needs schema for optimizer)
"""

from tests.fixtures import transpile


class TestFunctionCallSyntax:
    """Test standard function call syntax: func(col)"""
    
    def test_days_since(self):
        """days_since(col) → DATEDIFF(...) or DATE_DIFF(...)"""
        result = transpile("from users select days_since(created_at)")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "CREATED_AT" in result.upper()
    
    def test_months_since(self):
        """months_since(col) → DATEDIFF(..., MONTH) or DATE_DIFF(...)"""
        result = transpile("from users select months_since(signup_date)")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "SIGNUP_DATE" in result.upper()
    
    def test_years_since(self):
        """years_since(col) → DATEDIFF(..., YEAR) or DATE_DIFF(...)"""
        result = transpile("from users select years_since(birth_date)")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "BIRTH_DATE" in result.upper()
    
    def test_weeks_since(self):
        """weeks_since(col) → DATEDIFF(..., WEEK) or DATE_DIFF(...)"""
        result = transpile("from users select weeks_since(last_login)")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "LAST_LOGIN" in result.upper()
    
    def test_days_until(self):
        """days_until(col) → DATEDIFF(...)"""
        result = transpile("from tasks select days_until(due_date)")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "DUE_DATE" in result.upper()
    
    def test_months_until(self):
        """months_until(col) → DATEDIFF(..., MONTH)"""
        result = transpile("from subscriptions select months_until(renewal_date)")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "RENEWAL_DATE" in result.upper()
    
    def test_hours_since(self):
        """hours_since(col) → DATEDIFF(..., HOUR)"""
        result = transpile("from events select hours_since(event_time)")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "EVENT_TIME" in result.upper()


class TestSpaceNotationSyntax:
    """Test space notation syntax: unit since/until col"""
    
    def test_days_since_space(self):
        """days since col → DATEDIFF(...)"""
        result = transpile("from users select days since created_at")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "CREATED_AT" in result.upper()
    
    def test_months_since_space(self):
        """months since col → DATEDIFF(..., MONTH)"""
        result = transpile("from users select months since signup_date")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "SIGNUP_DATE" in result.upper()
    
    def test_years_since_space(self):
        """years since col → DATEDIFF(..., YEAR)"""
        result = transpile("from users select years since birth_date")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "BIRTH_DATE" in result.upper()
    
    def test_weeks_since_space(self):
        """weeks since col → DATEDIFF(..., WEEK)"""
        result = transpile("from users select weeks since last_login")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "LAST_LOGIN" in result.upper()
    
    def test_days_until_space(self):
        """days until col → DATEDIFF(...)"""
        result = transpile("from tasks select days until due_date")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "DUE_DATE" in result.upper()
    
    def test_months_until_space(self):
        """months until col → DATEDIFF(..., MONTH)"""
        result = transpile("from subscriptions select months until renewal_date")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "RENEWAL_DATE" in result.upper()
    
    def test_hours_since_space(self):
        """hours since col → DATEDIFF(..., HOUR)"""
        result = transpile("from events select hours since event_time")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "EVENT_TIME" in result.upper()
    
    def test_singular_form_space(self):
        """Singular forms work too: day since, month until"""
        result = transpile("from users select day since created_at")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        
        result = transpile("from tasks select month until due_date")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()


class TestUnderscoreAliasSyntax:
    """Test underscore alias syntax: unit_since_col (preparser)"""
    
    def test_days_since_underscore(self):
        """days_since_col → DATEDIFF(...)"""
        result = transpile("from users select days_since_created_at")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "CREATED_AT" in result.upper()
    
    def test_months_since_underscore(self):
        """months_since_col → DATEDIFF(..., MONTH)"""
        result = transpile("from users select months_since_signup_date")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "SIGNUP_DATE" in result.upper()
    
    def test_years_since_underscore(self):
        """years_since_col → DATEDIFF(..., YEAR)"""
        result = transpile("from users select years_since_birth_date")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "BIRTH_DATE" in result.upper()
    
    def test_days_until_underscore(self):
        """days_until_col → DATEDIFF(...)"""
        result = transpile("from tasks select days_until_due_date")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "DUE_DATE" in result.upper()
    
    def test_months_until_underscore(self):
        """months_until_col → DATEDIFF(..., MONTH)"""
        result = transpile("from subscriptions select months_until_renewal_date")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "RENEWAL_DATE" in result.upper()


class TestUnderscoreAliasSchemaAwareness:
    """Underscore aliases should not rewrite if the full identifier is a real column."""

    def test_preserve_real_column_name(self) -> None:
        from asql import CompileSettings
        from asql.schema import Schema, Table

        schema = Schema()
        schema.add_table(Table.from_column_list("users", ["id", "created_at", "days_since_created_at"]))

        sql = transpile("from users select days_since_created_at", settings=CompileSettings(schema=schema))

        # Should preserve the real column name, not rewrite to DATEDIFF(...)
        assert "DATEDIFF" not in sql.upper()
        assert "DAYS_SINCE_CREATED_AT" in sql.upper()


class TestAllSyntaxesEquivalent:
    """Verify all 3 syntaxes produce equivalent results."""
    
    def test_days_since_all_syntaxes(self):
        """All 3 syntaxes for days_since should work."""
        # Function call
        r1 = transpile("from users select days_since(created_at) as days")
        # Space notation
        r2 = transpile("from users select days since created_at as days")
        # Underscore alias
        r3 = transpile("from users select days_since_created_at as days")
        
        # All should contain DATEDIFF and CREATED_AT
        for result in [r1, r2, r3]:
            assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
            assert "CREATED_AT" in result.upper()
    
    def test_months_until_all_syntaxes(self):
        """All 3 syntaxes for months_until should work."""
        # Function call
        r1 = transpile("from tasks select months_until(due_date) as months_left")
        # Space notation
        r2 = transpile("from tasks select months until due_date as months_left")
        # Underscore alias
        r3 = transpile("from tasks select months_until_due_date as months_left")
        
        # All should contain DATEDIFF and DUE_DATE
        for result in [r1, r2, r3]:
            assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
            assert "DUE_DATE" in result.upper()


class TestInWhereClause:
    """Test date diff functions in WHERE clause."""
    
    def test_function_call_in_where(self):
        """days_since(col) in WHERE clause."""
        result = transpile("from users where days_since(last_login) > 30")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "WHERE" in result.upper()
    
    def test_space_notation_in_where(self):
        """days since col in WHERE clause."""
        result = transpile("from users where days since last_login > 30")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "WHERE" in result.upper()
    
    def test_underscore_in_where(self):
        """days_since_col in WHERE clause."""
        result = transpile("from users where days_since_last_login > 30")
        assert "DATEDIFF" in result.upper() or "DATE_DIFF" in result.upper()
        assert "WHERE" in result.upper()

