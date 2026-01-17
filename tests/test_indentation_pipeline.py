"""Dialect-native tests for indentation/newline pipeline parsing (PRQL-style chaining)."""

import sqlglot


class TestIndentationPipelines:
    def test_multiline_where_select_limit_without_pipes(self) -> None:

        query = """
        from orders
          where active
          select id, amount
          limit 10
        """

        expr = sqlglot.parse_one(query, dialect="asql")
        sql = expr.sql()
        assert "FROM orders" in sql
        assert "WHERE active" in sql
        assert "SELECT id, amount" in sql
        assert "LIMIT 10" in sql


