"""SELECT-first compatibility: standard SQL is valid ASQL.

Pins the behavior matrix of the select-first initiative:
expression sugar works inside SELECT-first queries, trailing pipeline
transforms continue them, and ambiguous or silently-droppable constructs
error loudly instead of emitting wrong-but-plausible SQL.
"""

import pytest

from asql.errors import ASQLSyntaxError

from .fixtures import transpile


class TestSugarInSelectFirst:
    """ASQL expression sugar compiles identically inside SELECT-first queries."""

    def test_count_shorthand(self) -> None:
        sql = transpile("select country, # as n from users group by country")
        assert "COUNT(*) AS n" in sql

    def test_order_by_desc_prefix(self) -> None:
        sql = transpile("select * from users order by -created_at")
        assert "created_at DESC" in sql

    def test_double_equals(self) -> None:
        sql = transpile('select * from users where status == "active"')
        assert "status = 'active'" in sql

    def test_trailing_stash(self) -> None:
        sql = transpile(
            "select country, # as n from users group by country stash as counts"
        )
        assert "WITH counts AS" in sql
        assert "SELECT * FROM counts" in sql


class TestAggregateBlockRejected:
    """An ASQL aggregate block after a SELECT-first GROUP BY is ambiguous:
    the query already has a projection the block would replace. Reject it
    loudly — today it misparses as a function call (GROUP BY REGION(...))."""

    def test_aggregate_block_after_select_raises(self) -> None:
        with pytest.raises(ASQLSyntaxError, match="aggregate"):
            transpile("select * from orders group by region ( sum(amount) as rev )")

    def test_error_names_both_rewrites(self) -> None:
        with pytest.raises(ASQLSyntaxError, match=r"(?s)start.*from.*SELECT"):
            transpile("select * from orders group by region ( sum(amount) as rev )")

    def test_count_shorthand_block_raises(self) -> None:
        with pytest.raises(ASQLSyntaxError, match="aggregate"):
            transpile("select * from users group by country ( # as n )")

    def test_function_call_group_by_still_works(self) -> None:
        sql = transpile(
            "SELECT date_trunc('month', created_at) AS m, COUNT(*) AS n "
            "FROM orders GROUP BY date_trunc('month', created_at)"
        )
        assert "DATE_TRUNC" in sql

    def test_from_first_block_still_works(self) -> None:
        sql = transpile("from orders group by region ( sum(amount) as rev )")
        assert "GROUP BY region" in sql
        assert "SUM(amount) AS rev" in sql


class TestTrailingWhereAfterGroupBy:
    """A top-level `where` after `group by` is invalid standard SQL, so the
    pipeline reading (post-aggregation filter via CTE) is the only sensible
    one — SELECT-first must match FROM-first exactly."""

    def test_matches_from_first(self) -> None:
        select_first = transpile(
            "select region, sum(amount) as rev from orders "
            "group by region where rev > 100"
        )
        from_first = transpile(
            "from orders group by region ( sum(amount) as rev ) where rev > 100"
        )
        assert select_first == from_first
        assert "WITH" in select_first  # post-aggregation filter is CTE-wrapped

    def test_transforms_continue_after_trailing_where(self) -> None:
        sql = transpile(
            "select region, sum(amount) as rev from orders "
            "group by region where rev > 100 order by -rev limit 5"
        )
        assert "WITH" in sql
        assert "rev DESC" in sql
        assert "LIMIT 5" in sql

    def test_having_untouched(self) -> None:
        sql = transpile(
            "select region, sum(amount) as rev from orders "
            "group by region having sum(amount) > 100"
        )
        assert "HAVING" in sql
        assert "WITH" not in sql

    def test_where_before_group_by_untouched(self) -> None:
        sql = transpile(
            "select region, sum(amount) as rev from orders "
            "where amount > 0 group by region"
        )
        assert "WHERE amount > 0" in sql
        assert "WITH" not in sql

    def test_union_second_branch_where_untouched(self) -> None:
        sql = transpile(
            "select region from a group by region "
            "union select region from b where x > 1"
        )
        assert "UNION" in sql
        assert "WHERE x > 1" in sql
        assert "WITH" not in sql

    def test_union_second_branch_group_by_then_where(self) -> None:
        """The GROUP BY *and* WHERE both live in the trailing set-op branch —
        the WHERE belongs to that branch, not the outer Union. Must not be
        treated as a trailing pipeline filter (which would emit an invalid
        `... GROUP BY b WHERE ...` on the Union node)."""
        sql = transpile(
            "select a from t union all select b from t2 group by b where b > 1"
        )
        assert "UNION ALL" in sql
        assert "WITH" not in sql
        # WHERE must land before GROUP BY (valid), not after it
        assert sql.index("WHERE") < sql.index("GROUP BY")


class TestHiveOnlyModifiersRejected:
    """Hive-only ordering modifiers would be silently dropped by every
    non-Hive generator — reject them with an `order by` hint instead."""

    def test_sort_by_raises(self) -> None:
        with pytest.raises(ASQLSyntaxError, match="order by"):
            transpile("select * from users sort by -created_at")

    def test_cluster_by_raises(self) -> None:
        with pytest.raises(ASQLSyntaxError, match="order by"):
            transpile("select * from users cluster by created_at")

    def test_distribute_by_raises(self) -> None:
        with pytest.raises(ASQLSyntaxError, match="order by"):
            transpile("select * from users distribute by created_at")
