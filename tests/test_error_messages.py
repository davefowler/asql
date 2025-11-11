"""Test error message quality and clarity."""

import pytest
from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError


class TestErrorMessages:
    """Test that error messages are clear and helpful."""
    
    def test_empty_query_message(self) -> None:
        """Test empty query error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("")
        assert "empty" in str(exc_info.value).lower()
    
    def test_missing_from_message(self) -> None:
        """Test missing FROM error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("select * from users")
        error_msg = str(exc_info.value).lower()
        assert "from" in error_msg or "expected" in error_msg
    
    def test_incomplete_where_message(self) -> None:
        """Test incomplete WHERE error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("from users where")
        error_msg = str(exc_info.value).lower()
        assert "where" in error_msg or "expected" in error_msg or "expression" in error_msg
    
    def test_incomplete_group_by_message(self) -> None:
        """Test incomplete GROUP BY error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("from users group by")
        error_msg = str(exc_info.value).lower()
        assert "group" in error_msg or "expected" in error_msg
    
    def test_missing_aggregation_block_message(self) -> None:
        """Test missing aggregation block error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("from users group by country")
        error_msg = str(exc_info.value).lower()
        assert "(" in error_msg or "aggregation" in error_msg or "expected" in error_msg
    
    def test_incomplete_in_list_message(self) -> None:
        """Test incomplete IN list error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile('from users where status in (')
        error_msg = str(exc_info.value).lower()
        assert "in" in error_msg or "expected" in error_msg or ")" in error_msg
    
    def test_empty_in_list_message(self) -> None:
        """Test empty IN list error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile('from users where status in ()')
        error_msg = str(exc_info.value).lower()
        assert "empty" in error_msg or "expected" in error_msg
    
    def test_missing_sort_column_message(self) -> None:
        """Test missing sort column error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("from users sort")
        error_msg = str(exc_info.value).lower()
        assert "sort" in error_msg or "expected" in error_msg
    
    def test_missing_take_number_message(self) -> None:
        """Test missing TAKE number error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("from users take")
        error_msg = str(exc_info.value).lower()
        assert "take" in error_msg or "expected" in error_msg or "number" in error_msg
    
    def test_invalid_number_message(self) -> None:
        """Test invalid number error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("from users take abc")
        error_msg = str(exc_info.value).lower()
        assert "number" in error_msg or "invalid" in error_msg or "expected" in error_msg
    
    def test_unclosed_string_message(self) -> None:
        """Test unclosed string literal error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile('from users where status == "active')
        error_msg = str(exc_info.value).lower()
        assert "string" in error_msg or "unclosed" in error_msg or "quote" in error_msg
    
    def test_missing_function_argument_message(self) -> None:
        """Test missing function argument error message."""
        with pytest.raises(ASQLSyntaxError) as exc_info:
            compile("from users sort month()")
        error_msg = str(exc_info.value).lower()
        assert "argument" in error_msg or "expected" in error_msg or "month" in error_msg.lower()
