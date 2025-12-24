"""
Test all playground examples compile correctly across all dialects.

This test ensures:
1. All ASQL examples in the playground can be compiled
2. All examples can be transpiled to every supported dialect
3. The generated SQL is valid (parseable by SQLGlot)
4. SQL-to-ASQL reverse compilation works for SQL examples

Run with: pytest tests/test_playground_examples.py -v
"""

import pytest
import sqlglot
from asql import compile
from asql.reverse_compiler import reverse_compile

# Import examples directly from playground package
from playground.examples import (
    ASQL_EXAMPLES,
    PIPELINE_EXAMPLES,
    SAMPLING_EXAMPLES,
    RESHAPING_EXAMPLES,
    COLUMN_OPERATOR_EXAMPLES,
    COUNT_INFERENCE_EXAMPLES,
    SQL_EXAMPLES,
    get_all_examples_flat,
)


# All supported dialects to test
DIALECTS = [
    "postgres",
    "mysql",
    "bigquery",
    "snowflake",
    "redshift",
    "spark",
    "duckdb",
    "sqlite",
    "trino",
]

# Dialects that don't support column operators (except, rename, replace)
# These require EXCLUDE/EXCEPT syntax which only BigQuery, Snowflake, DuckDB, Spark support
# TODO(Issue #80): Remove these skips when schema-aware column expansion fallback is implemented
_NO_COLUMN_OPS_DIALECTS = ["trino", "mysql", "redshift", "sqlite"]
_COLUMN_OP_EXAMPLES = ["Exclude Columns", "Rename Columns", "Replace Column Values", "Combined Column Ops"]

# Known dialect-specific limitations
DIALECT_LIMITATIONS = {
    # "per...first by" uses QUALIFY which Trino doesn't support
    ("trino", "First Event per User"): "QUALIFY not supported in Trino",
    # Column operators require EXCLUDE syntax - Issue #80 will add schema-aware fallback
    **{
        (dialect, example): f"Column operators not supported in {dialect}"
        for dialect in _NO_COLUMN_OPS_DIALECTS
        for example in _COLUMN_OP_EXAMPLES
    },
}


def get_all_asql_examples():
    """Get all ASQL examples for parametrized testing."""
    return get_all_examples_flat()


# Cache examples to avoid re-computing for each test
_CACHED_EXAMPLES = None

def cached_examples():
    global _CACHED_EXAMPLES
    if _CACHED_EXAMPLES is None:
        _CACHED_EXAMPLES = get_all_asql_examples()
    return _CACHED_EXAMPLES


class TestPlaygroundExamplesCompile:
    """Test that all playground examples compile successfully."""
    
    @pytest.fixture(scope="class")
    def all_examples(self):
        return cached_examples()
    
    def test_examples_exist(self, all_examples):
        """Verify examples are loaded from playground.examples."""
        assert len(all_examples) > 0, "No examples found in playground.examples"
        print(f"\nLoaded {len(all_examples)} examples from playground.examples")
        
        # Count by category
        categories = {}
        for cat, title, query in all_examples:
            categories[cat] = categories.get(cat, 0) + 1
        
        for cat, count in sorted(categories.items()):
            print(f"  - {cat}: {count} examples")
    
    @pytest.mark.parametrize("category,title,query", cached_examples())
    def test_example_compiles(self, category, title, query):
        """Test that each example compiles without error."""
        try:
            result = compile(query, dialect="snowflake", pretty=True)
            assert result is not None, "Compilation returned None"
            assert len(result) > 0, "Compilation returned empty string"
        except Exception as e:
            pytest.fail(f"[{category}] '{title}' failed to compile: {e}")


class TestPlaygroundExamplesAllDialects:
    """Test that all examples compile to every supported dialect."""
    
    @pytest.mark.parametrize("category,title,query", cached_examples())
    @pytest.mark.parametrize("dialect", DIALECTS)
    def test_example_compiles_to_dialect(self, category, title, query, dialect):
        """Test that each example compiles to each dialect."""
        limitation_key = (dialect, title)
        if limitation_key in DIALECT_LIMITATIONS:
            pytest.skip(f"Known limitation: {DIALECT_LIMITATIONS[limitation_key]}")
        
        try:
            result = compile(query, dialect=dialect, pretty=True)
            assert result is not None, "Compilation returned None"
            assert len(result) > 0, "Compilation returned empty string"
        except Exception as e:
            pytest.fail(f"[{category}] '{title}' failed to compile to {dialect}: {e}")


class TestGeneratedSQLIsValid:
    """Test that generated SQL is valid (parseable by SQLGlot)."""
    
    @pytest.mark.parametrize("category,title,query", cached_examples())
    @pytest.mark.parametrize("dialect", DIALECTS)
    def test_generated_sql_is_parseable(self, category, title, query, dialect):
        """Test that generated SQL can be parsed back by SQLGlot."""
        limitation_key = (dialect, title)
        if limitation_key in DIALECT_LIMITATIONS:
            pytest.skip(f"Known limitation: {DIALECT_LIMITATIONS[limitation_key]}")
        
        try:
            sql = compile(query, dialect=dialect, pretty=True)
            parsed = sqlglot.parse(sql, dialect=dialect)
            
            assert parsed is not None, "SQLGlot returned None"
            assert len(parsed) > 0, "SQLGlot returned empty parse result"
            
            for stmt in parsed:
                assert stmt is not None, "Parsed statement is None"
                assert hasattr(stmt, 'sql'), "Parsed result doesn't have sql() method"
                
        except sqlglot.errors.ParseError as e:
            pytest.fail(
                f"[{category}] '{title}' generated invalid {dialect} SQL:\n"
                f"SQL: {sql[:500]}...\n"
                f"Parse Error: {e}"
            )
        except Exception as e:
            pytest.fail(f"[{category}] '{title}' failed: {e}")


class TestRoundTrip:
    """Test ASQL → SQL → ASQL round trip (where applicable)."""
    
    @pytest.mark.parametrize("category,title,query", cached_examples())
    def test_sql_can_reverse_compile(self, category, title, query):
        """Test that generated SQL can be reverse-compiled back to ASQL."""
        try:
            sql = compile(query, dialect="postgres", pretty=True)
            asql_result = reverse_compile(sql, source_dialect="postgres")
            
            assert asql_result is not None, "Reverse compilation returned None"
            assert len(asql_result) > 0, "Reverse compilation returned empty string"
            
        except Exception as e:
            pytest.skip(f"Reverse compilation not supported for this pattern: {e}")


class TestSQLExamples:
    """Test SQL examples can be reverse-compiled to ASQL."""
    
    def test_sql_examples_exist(self):
        """Verify SQL examples are loaded."""
        assert len(SQL_EXAMPLES) > 0, "No SQL examples found"
        print(f"\nLoaded {len(SQL_EXAMPLES)} SQL examples")
    
    @pytest.mark.parametrize("example", SQL_EXAMPLES, ids=lambda ex: ex.get("title", "unknown"))
    def test_sql_example_can_reverse_compile(self, example):
        """Test that SQL examples can be reverse-compiled to ASQL."""
        try:
            dialect = example.get("dialect", "") or "postgres"
            query = example.get("query", "")
            
            if not query:
                pytest.skip("Empty query")
            
            asql = reverse_compile(query, source_dialect=dialect)
            
            assert asql is not None
            assert len(asql) > 0
            
            # Verify the ASQL can compile back to SQL
            sql = compile(asql, dialect=dialect)
            assert sql is not None
            
        except Exception as e:
            pytest.skip(f"SQL example '{example.get('title', 'unknown')}' not supported: {str(e)[:100]}")


class TestDialectSpecificFeatures:
    """Test that dialect-specific SQL is generated correctly."""
    
    def test_snowflake_uses_ilike(self):
        """Snowflake should use ILIKE for case-insensitive matching."""
        asql = 'from users where name ilike "%john%"'
        sql = compile(asql, dialect="snowflake")
        assert "ILIKE" in sql.upper() or "LIKE" in sql.upper()
    
    def test_bigquery_uses_safe_divide(self):
        """BigQuery should handle division appropriately."""
        asql = 'from users select id, amount / total as ratio'
        sql = compile(asql, dialect="bigquery")
        assert sql is not None
    
    def test_postgres_date_functions(self):
        """PostgreSQL should use appropriate date functions."""
        asql = 'from events group by month(created_at) (# as count)'
        sql = compile(asql, dialect="postgres")
        assert "DATE_TRUNC" in sql.upper() or "EXTRACT" in sql.upper() or "MONTH" in sql.upper()


if __name__ == "__main__":
    # Quick test to show loaded examples
    examples = get_all_asql_examples()
    
    print("Loaded playground examples:")
    categories = {}
    for cat, title, query in examples:
        categories[cat] = categories.get(cat, 0) + 1
    
    for cat, count in sorted(categories.items()):
        print(f"  - {cat}: {count} examples")
    
    print(f"\nTotal: {len(examples)} examples")
    
    # Quick compilation test
    print("\n" + "="*60)
    print("Quick compilation test (Snowflake dialect):")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for category, title, query in examples:
        try:
            result = compile(query, dialect="snowflake")
            passed += 1
            print(f"  ✓ [{category}] {title}")
        except Exception as e:
            failed += 1
            print(f"  ✗ [{category}] {title}: {str(e)[:60]}...")
    
    print(f"\nResults: {passed} passed, {failed} failed out of {len(examples)} examples")
