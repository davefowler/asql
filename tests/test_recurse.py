"""Tests for recursive query syntax."""

import pytest
from asql import compile
from asql.preparse import preparse_asql


class TestRecursePreparser:
    """Test that recurse() is correctly transformed by the preparser."""

    def test_basic_recurse_preparsing(self) -> None:
        """Test basic recurse transformation to CTE."""
        asql = """
        from employees
          where id = 1
          recurse(manager_id)
        """
        result = preparse_asql(asql)
        
        # Should generate WITH RECURSIVE
        assert "WITH RECURSIVE" in result
        assert "_recurse_employees" in result
        assert "_level" in result
        assert "UNION ALL" in result
        assert "manager_id" in result

    def test_recurse_with_max_depth(self) -> None:
        """Test recurse with explicit max depth."""
        asql = """
        from employees
          where id = 1
          recurse(manager_id, 5)
        """
        result = preparse_asql(asql)
        
        assert "WITH RECURSIVE" in result
        assert "_level < 5" in result

    def test_recurse_default_max_depth(self) -> None:
        """Test that recurse without max_depth defaults to 100."""
        asql = """
        from employees
          where id = 1
          recurse(manager_id)
        """
        result = preparse_asql(asql)
        
        # Default max depth should be 100
        assert "_level < 100" in result

    def test_recurse_with_different_fk(self) -> None:
        """Test recurse with different FK column name."""
        asql = """
        from categories
          where slug = 'electronics'
          recurse(parent_id)
        """
        result = preparse_asql(asql)
        
        assert "WITH RECURSIVE" in result
        assert "_recurse_categories" in result
        assert "parent_id" in result

    def test_recurse_with_continuation(self) -> None:
        """Test recurse with clauses after it."""
        asql = """
        from employees
          where id = 1
          recurse(manager_id, 3)
          order by _level
          limit 10
        """
        result = preparse_asql(asql)
        
        assert "WITH RECURSIVE" in result
        # Case-insensitive check for ORDER BY and LIMIT
        assert "order by" in result.lower()
        assert "limit" in result.lower()


class TestRecurseCompilation:
    """Test that recurse() compiles to valid SQL."""

    def test_compile_basic_recurse(self) -> None:
        """Test compiling a basic recursive query."""
        asql = """
        from employees
          where id = 1
          recurse(manager_id)
        """
        sql = compile(asql, dialect="duckdb")
        
        # Should be valid SQL with recursive CTE
        assert "WITH RECURSIVE" in sql
        assert "UNION ALL" in sql

    def test_compile_recurse_postgres(self) -> None:
        """Test compiling recursive query for PostgreSQL."""
        asql = """
        from employees
          where id = 1
          recurse(manager_id, 5)
        """
        sql = compile(asql, dialect="postgres")
        
        assert "WITH RECURSIVE" in sql
        assert "UNION ALL" in sql

    def test_compile_recurse_bigquery(self) -> None:
        """Test compiling recursive query for BigQuery."""
        asql = """
        from categories
          where id = 100
          recurse(parent_id, 10)
        """
        sql = compile(asql, dialect="bigquery")
        
        # BigQuery also supports WITH RECURSIVE
        assert "WITH RECURSIVE" in sql

    def test_compile_recurse_with_select(self) -> None:
        """Test recursive query with explicit select."""
        asql = """
        from employees
          where id = 1
          recurse(manager_id)
          select id, name, _level
        """
        sql = compile(asql, dialect="duckdb")
        
        # The outer select should include the specified columns
        assert "WITH RECURSIVE" in sql


class TestRecurseSemantics:
    """Test the semantic correctness of generated recursive CTEs."""

    def test_anchor_condition_preserved(self) -> None:
        """Test that the anchor condition is preserved in the CTE."""
        asql = """
        from employees
          where department = 'Engineering' and active = true
          recurse(manager_id)
        """
        result = preparse_asql(asql)
        
        # The anchor condition should be in the base case
        assert "department" in result
        assert "active" in result

    def test_fk_to_id_join(self) -> None:
        """Test that the recursive join is FK -> id."""
        asql = """
        from employees
          where id = 1
          recurse(manager_id)
        """
        result = preparse_asql(asql)
        
        # Should join FK column to id
        assert "manager_id" in result
        # The join should reference the CTE's id column
        assert "_recurse_employees.id" in result

    def test_level_column_increments(self) -> None:
        """Test that _level column increments in recursive part."""
        asql = """
        from employees
          where id = 1
          recurse(manager_id)
        """
        result = preparse_asql(asql)
        
        # Base case starts at 1
        assert "1 AS _level" in result
        # Recursive case increments
        assert "_level + 1" in result


class TestRecurseSyntaxVariants:
    """Test different syntax variants for recurse."""

    def test_recurse_on_syntax(self) -> None:
        """Test the 'recurse on column' syntax."""
        asql = """
        from employees
          where id = 1
          recurse on manager_id
        """
        result = preparse_asql(asql)
        
        assert "WITH RECURSIVE" in result
        assert "_level" in result
        assert "manager_id" in result

    def test_recurse_on_with_max_depth(self) -> None:
        """Test 'recurse on column, max_depth' syntax."""
        asql = """
        from employees
          where id = 1
          recurse on manager_id, 5
        """
        result = preparse_asql(asql)
        
        assert "WITH RECURSIVE" in result
        assert "_level < 5" in result

    def test_all_syntaxes_equivalent(self) -> None:
        """Test that all recurse syntax variants produce same output."""
        asql_parens = "from employees where id = 1 recurse(manager_id, 3)"
        asql_on = "from employees where id = 1 recurse on manager_id, 3"
        asql_bare = "from employees where id = 1 recurse manager_id, 3"
        
        result_parens = preparse_asql(asql_parens)
        result_on = preparse_asql(asql_on)
        result_bare = preparse_asql(asql_bare)
        
        # All should produce the same CTE structure
        assert result_parens == result_on == result_bare

    def test_recurse_bare_syntax(self) -> None:
        """Test 'recurse column' syntax (no 'on' keyword)."""
        asql = """
        from employees
          where id = 1
          recurse manager_id
        """
        result = preparse_asql(asql)
        
        assert "WITH RECURSIVE" in result
        assert "_level" in result


class TestRecurseEdgeCases:
    """Test edge cases and error handling."""

    def test_no_where_clause(self) -> None:
        """Test recurse without a WHERE clause (all rows as roots)."""
        asql = """
        from employees
          recurse(manager_id)
        """
        result = preparse_asql(asql)
        
        # Should still work, using 1=1 as anchor
        assert "WITH RECURSIVE" in result

    def test_multiple_roots(self) -> None:
        """Test that multiple anchor rows work correctly."""
        asql = """
        from employees
          where department = 'Engineering'
          recurse(manager_id, 3)
        """
        result = preparse_asql(asql)
        
        # Should work - creates a forest of trees
        assert "WITH RECURSIVE" in result
        assert "department" in result

    def test_recurse_not_affected_by_other_transforms(self) -> None:
        """Test that recurse works with other ASQL features."""
        asql = """
        from employees
          where id == 1
          recurse(manager_id)
        """
        # The == should be transformed to = by the preparser
        result = preparse_asql(asql)
        
        assert "WITH RECURSIVE" in result
        # == should be converted to =
        assert "id = 1" in result

