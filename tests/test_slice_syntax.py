"""Tests for python-style slice syntax in ASQL (dialect-native)."""

from asql import compile
from tests.fixtures import assert_sql_contains, assert_valid_sql


class TestSliceSyntax:
    """Test slice syntax compilation to SUBSTRING/LEFT/RIGHT."""

    def test_basic_slice(self) -> None:
        sql = compile("from users select email[1:5] as prefix")
        assert_sql_contains(sql, "SUBSTRING", "email", "1", "5")
        assert_valid_sql(sql)

    def test_slice_length_calculation(self) -> None:
        # email[3:8] means characters 3-8, which is 6 characters
        sql = compile("from users select email[3:8] as middle")
        assert_sql_contains(sql, "SUBSTRING", "email", "3", "6")
        assert_valid_sql(sql)

    def test_slice_to_end(self) -> None:
        sql = compile("from users select email[1:] as suffix")
        assert_sql_contains(sql, "SUBSTRING", "email", "1")
        assert_valid_sql(sql)

    def test_slice_from_start(self) -> None:
        sql = compile("from users select email[:5] as prefix")
        assert_sql_contains(sql, "LEFT", "email", "5")
        assert_valid_sql(sql)

    def test_negative_slice(self) -> None:
        sql = compile("from users select email[-5:] as last_five")
        assert_sql_contains(sql, "RIGHT", "email", "5")
        assert_valid_sql(sql)

    def test_slice_with_qualified_column(self) -> None:
        sql = compile("from users select users.email[1:5] as prefix")
        assert_sql_contains(sql, "SUBSTRING", "users.email", "1", "5")
        assert_valid_sql(sql)

    def test_multiple_slices(self) -> None:
        sql = compile("from users select email[1:5] as prefix, name[:3] as initials")
        assert_sql_contains(sql, "SUBSTRING", "LEFT")
        assert_valid_sql(sql)

    def test_slice_in_where_clause(self) -> None:
        sql = compile("from users where email[1:5] = 'test@'")
        assert_sql_contains(sql, "WHERE", "SUBSTRING", "email")
        assert_valid_sql(sql)


