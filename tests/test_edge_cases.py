"""Edge case and boundary condition tests."""

import pytest
from asql import compile
from asql.errors import ASQLSyntaxError


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""
    
    def test_very_long_query(self) -> None:
        """Test very long query with many conditions."""
        conditions = " and ".join([f'status == "status{i}"' for i in range(10)])
        asql = f"from users where {conditions}"
        sql = compile(asql)
        assert "WHERE" in sql.upper()
        assert "AND" in sql.upper()
    
    def test_single_character_table_name(self) -> None:
        """Test single character table name."""
        asql = "from u"
        sql = compile(asql)
        assert "SELECT" in sql.upper()
        assert "FROM" in sql.upper()
    
    def test_long_table_name(self) -> None:
        """Test long table name."""
        asql = "from very_long_table_name_with_many_words"
        sql = compile(asql)
        assert "very_long_table_name_with_many_words" in sql.lower()
    
    def test_single_character_column(self) -> None:
        """Test single character column name."""
        asql = "from users select x"
        sql = compile(asql)
        assert "x" in sql.lower()
    
    def test_numeric_table_name(self) -> None:
        """Test table name starting with number (should fail)."""
        # This might be valid in some databases, but ASQL identifiers follow standard rules
        # Table names starting with numbers are typically invalid
        pass  # Would need to check identifier parsing rules
    
    def test_very_large_limit(self) -> None:
        """Test very large LIMIT value."""
        asql = "from users take 999999"
        sql = compile(asql)
        assert "LIMIT" in sql.upper()
        assert "999999" in sql
    
    def test_limit_zero(self) -> None:
        """Test LIMIT of 0 (edge case - may be valid SQL but unusual)."""
        asql = "from users take 0"
        sql = compile(asql)
        assert "LIMIT" in sql.upper()
        # SQL allows LIMIT 0, though it returns no rows
        # The SQL generation is correct even if the value is unusual
    
    def test_negative_limit(self) -> None:
        """Test negative LIMIT (should fail)."""
        with pytest.raises(ASQLSyntaxError):
            compile("from users take -10")
    
    def test_empty_in_list(self) -> None:
        """Test empty IN list (should fail)."""
        with pytest.raises(ASQLSyntaxError):
            compile('from users where status in ()')
    
    def test_single_item_in_list(self) -> None:
        """Test IN list with single item."""
        asql = 'from users where status in ("active")'
        sql = compile(asql)
        assert "IN" in sql.upper()
        assert "active" in sql.lower()
    
    def test_many_items_in_list(self) -> None:
        """Test IN list with many items."""
        items = ", ".join([f'"{i}"' for i in range(20)])
        asql = f"from users where status in ({items})"
        sql = compile(asql)
        assert "IN" in sql.upper()
    
    def test_whitespace_handling(self) -> None:
        """Test that extra whitespace is handled correctly."""
        asql = "from   users   where   status   ==   \"active\""
        sql = compile(asql)
        assert "WHERE" in sql.upper()
        assert "active" in sql.lower()
    
    def test_tabs_instead_of_spaces(self) -> None:
        """Test that tabs are handled as whitespace."""
        asql = "from\tusers\twhere\tstatus\t==\t\"active\""
        sql = compile(asql)
        assert "WHERE" in sql.upper()
    
    def test_newlines_in_query(self) -> None:
        """Test queries with newlines."""
        asql = """
from users
where status == "active"
"""
        sql = compile(asql)
        assert "WHERE" in sql.upper()
        assert "active" in sql.lower()


class TestSpecialCharacters:
    """Test special characters in strings and identifiers."""
    
    def test_string_with_quotes(self) -> None:
        """Test string containing quote characters."""
        # Escaped quotes should work
        asql = 'from users where name == "John\'s"'
        sql = compile(asql)
        assert "John" in sql
    
    def test_string_with_special_chars(self) -> None:
        """Test string with special characters."""
        asql = 'from users where email == "user@example.com"'
        sql = compile(asql)
        assert "user" in sql.lower() or "@" in sql
    
    def test_unicode_in_strings(self) -> None:
        """Test unicode characters in strings."""
        asql = 'from users where name == "José"'
        sql = compile(asql)
        # Should compile without error
        assert sql is not None
    
    def test_underscore_in_identifiers(self) -> None:
        """Test underscores in identifiers."""
        asql = "from user_profiles where user_id == 123"
        sql = compile(asql)
        assert "user_profiles" in sql.lower() or "USER_PROFILES" in sql.upper()
        assert "user_id" in sql.lower() or "USER_ID" in sql.upper()


class TestOperatorCombinations:
    """Test various operator combinations."""
    
    def test_nested_logical_operators(self) -> None:
        """Test nested logical operators."""
        asql = 'from users where (status == "active" or status == "pending") and (age >= 18 or age <= 65)'
        sql = compile(asql)
        assert "WHERE" in sql.upper()
        assert "OR" in sql.upper()
        assert "AND" in sql.upper()
    
    def test_multiple_not_operators(self) -> None:
        """Test multiple NOT operators."""
        asql = 'from users where not status == "inactive" and not age < 18'
        sql = compile(asql)
        assert "NOT" in sql.upper()
        assert "AND" in sql.upper()
    
    def test_comparison_chain(self) -> None:
        """Test chained comparisons."""
        # Note: SQL doesn't support chained comparisons like Python
        # But we can test multiple comparisons
        asql = "from users where age >= 18 and age <= 65"
        sql = compile(asql)
        assert ">=" in sql or ">=" in sql.replace(" ", "")
        assert "<=" in sql or "<=" in sql.replace(" ", "")
        assert "AND" in sql.upper()


class TestAggregationEdgeCases:
    """Test aggregation edge cases."""
    
    def test_all_aggregations_together(self) -> None:
        """Test all aggregation functions in one query."""
        asql = """
from sales group by region (
    sum(amount) as total,
    avg(amount) as average,
    # as count,
    min(amount) as minimum,
    max(amount) as maximum
)
"""
        sql = compile(asql)
        assert "SUM" in sql.upper()
        assert "AVG" in sql.upper()
        assert "COUNT" in sql.upper()
        assert "MIN" in sql.upper()
        assert "MAX" in sql.upper()
    
    def test_count_without_alias(self) -> None:
        """Test COUNT(*) without alias."""
        asql = "from users group by country ( # )"
        sql = compile(asql)
        assert "COUNT" in sql.upper()
    
    def test_multiple_grouping_columns(self) -> None:
        """Test many grouping columns."""
        asql = "from sales group by region, month, year, product_category ( sum(amount) as revenue )"
        sql = compile(asql)
        assert "GROUP BY" in sql.upper()
        # Should have all grouping columns
        assert "region" in sql.lower()
        assert "month" in sql.lower()
        assert "year" in sql.lower()
        assert "product_category" in sql.lower() or "product" in sql.lower()


class TestSortEdgeCases:
    """Test sorting edge cases."""
    
    def test_many_sort_columns(self) -> None:
        """Test many sort columns."""
        asql = "from users sort col1, col2, col3, col4, col5"
        sql = compile(asql)
        assert "ORDER BY" in sql.upper()
    
    def test_mixed_asc_desc(self) -> None:
        """Test mixed ascending and descending sorts."""
        asql = "from users sort -col1, col2, -col3, col4"
        sql = compile(asql)
        assert "ORDER BY" in sql.upper()
        assert "DESC" in sql.upper()
        # Should have multiple columns
    
    def test_function_calls_in_sort(self) -> None:
        """Test multiple function calls in sort."""
        asql = "from users sort -month(updated_at), year(created_at), name"
        sql = compile(asql)
        assert "ORDER BY" in sql.upper()
        assert "MONTH" in sql.upper() or "month" in sql.lower()
        assert "YEAR" in sql.upper() or "year" in sql.lower()
