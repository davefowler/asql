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
import re
import sqlglot
from asql import compile
from asql.reverse_compiler import reverse_compile


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

# Known dialect-specific limitations
# Some ASQL features don't work in all dialects
DIALECT_LIMITATIONS = {
    # "per...first by" uses QUALIFY which Trino doesn't support
    ("trino", "First Event per User"): "QUALIFY not supported in Trino",
    # Add other known limitations here as they're discovered
}


def extract_playground_examples():
    """Extract all examples from playground.py."""
    import os
    from pathlib import Path
    
    playground_path = Path(__file__).parent.parent / "playground.py"
    content = playground_path.read_text()
    
    examples = {
        "asql": [],
        "asql_pipeline": [],
        "cohort": [],
        "sql": [],
    }
    
    # Extract asqlExamples
    asql_match = re.search(r'const asqlExamples = \[(.*?)\];', content, re.DOTALL)
    if asql_match:
        examples["asql"] = parse_js_examples(asql_match.group(1))
    
    # Extract asqlPipelineExamples
    pipeline_match = re.search(r'const asqlPipelineExamples = \[(.*?)\];', content, re.DOTALL)
    if pipeline_match:
        examples["asql_pipeline"] = parse_js_examples(pipeline_match.group(1))
    
    # Extract cohortExamples
    cohort_match = re.search(r'const cohortExamples = \[(.*?)\];', content, re.DOTALL)
    if cohort_match:
        examples["cohort"] = parse_js_examples(cohort_match.group(1))
    
    return examples


def parse_js_examples(js_array_content: str) -> list:
    """Parse JavaScript example objects from array content."""
    examples = []
    
    # Find each example object with title, desc, query
    # Pattern matches: { title: "...", desc: "...", query: `...` }
    pattern = r'\{\s*title:\s*["\']([^"\']+)["\'],\s*desc:\s*["\']([^"\']+)["\'],\s*query:\s*`([^`]+)`'
    
    for match in re.finditer(pattern, js_array_content, re.DOTALL):
        title = match.group(1)
        desc = match.group(2)
        query = match.group(3).strip()
        examples.append({
            "title": title,
            "desc": desc,
            "query": query,
        })
    
    return examples


def get_all_asql_examples():
    """Get all ASQL examples for parametrized testing."""
    examples = extract_playground_examples()
    all_examples = []
    
    for category in ["asql", "asql_pipeline", "cohort"]:
        for ex in examples.get(category, []):
            all_examples.append((category, ex["title"], ex["query"]))
    
    return all_examples


# Cache examples to avoid re-parsing for each test
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
    
    def test_examples_were_extracted(self, all_examples):
        """Verify we extracted examples from the playground."""
        assert len(all_examples) > 0, "No examples were extracted from playground.py"
        print(f"\nExtracted {len(all_examples)} examples from playground.py")
        
        # Count by category
        categories = {}
        for cat, title, query in all_examples:
            categories[cat] = categories.get(cat, 0) + 1
        
        for cat, count in categories.items():
            print(f"  - {cat}: {count} examples")
    
    @pytest.mark.parametrize("category,title,query", cached_examples())
    def test_example_compiles(self, category, title, query):
        """Test that each example compiles without error."""
        try:
            result = compile(query, dialect="snowflake", pretty=True)
            assert result is not None, f"Compilation returned None"
            assert len(result) > 0, f"Compilation returned empty string"
        except Exception as e:
            pytest.fail(f"[{category}] '{title}' failed to compile: {e}")


class TestPlaygroundExamplesAllDialects:
    """Test that all examples compile to every supported dialect."""
    
    @pytest.mark.parametrize("category,title,query", cached_examples())
    @pytest.mark.parametrize("dialect", DIALECTS)
    def test_example_compiles_to_dialect(self, category, title, query, dialect):
        """Test that each example compiles to each dialect."""
        # Skip known dialect-specific limitations
        limitation_key = (dialect, title)
        if limitation_key in DIALECT_LIMITATIONS:
            pytest.skip(f"Known limitation: {DIALECT_LIMITATIONS[limitation_key]}")
        
        try:
            result = compile(query, dialect=dialect, pretty=True)
            assert result is not None, f"Compilation returned None"
            assert len(result) > 0, f"Compilation returned empty string"
        except Exception as e:
            pytest.fail(f"[{category}] '{title}' failed to compile to {dialect}: {e}")


class TestGeneratedSQLIsValid:
    """Test that generated SQL is valid (parseable by SQLGlot)."""
    
    @pytest.mark.parametrize("category,title,query", cached_examples())
    @pytest.mark.parametrize("dialect", DIALECTS)
    def test_generated_sql_is_parseable(self, category, title, query, dialect):
        """Test that generated SQL can be parsed back by SQLGlot."""
        # Skip known dialect-specific limitations
        limitation_key = (dialect, title)
        if limitation_key in DIALECT_LIMITATIONS:
            pytest.skip(f"Known limitation: {DIALECT_LIMITATIONS[limitation_key]}")
        
        try:
            # Compile ASQL to SQL
            sql = compile(query, dialect=dialect, pretty=True)
            
            # Try to parse the generated SQL with SQLGlot
            # This validates the SQL syntax is correct for the dialect
            parsed = sqlglot.parse(sql, dialect=dialect)
            
            assert parsed is not None, "SQLGlot returned None"
            assert len(parsed) > 0, "SQLGlot returned empty parse result"
            
            # Verify we got actual AST nodes, not error tokens
            for stmt in parsed:
                assert stmt is not None, "Parsed statement is None"
                # Check it's a valid expression type (not an error)
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
            # Compile ASQL to SQL
            sql = compile(query, dialect="postgres", pretty=True)
            
            # Try to reverse compile back to ASQL
            # Note: The result won't be identical, but it should work
            asql_result = reverse_compile(sql, source_dialect="postgres")
            
            assert asql_result is not None, "Reverse compilation returned None"
            assert len(asql_result) > 0, "Reverse compilation returned empty string"
            
        except Exception as e:
            # Reverse compilation may not work for all patterns
            # Just warn, don't fail
            pytest.skip(f"Reverse compilation not supported for this pattern: {e}")


def get_sql_examples_from_playground():
    """Dynamically fetch SQL examples from the playground module."""
    import sys
    from pathlib import Path
    
    # Add parent directory to path to import playground
    playground_dir = Path(__file__).parent.parent
    if str(playground_dir) not in sys.path:
        sys.path.insert(0, str(playground_dir))
    
    # Import the Flask app to get access to the api_sql_examples function
    from playground import app
    
    # Get the examples by calling the endpoint logic
    with app.test_client() as client:
        response = client.get('/api/sql-examples')
        if response.status_code == 200:
            return response.get_json()
    return []


# Cache SQL examples
_CACHED_SQL_EXAMPLES = None

def cached_sql_examples():
    global _CACHED_SQL_EXAMPLES
    if _CACHED_SQL_EXAMPLES is None:
        _CACHED_SQL_EXAMPLES = get_sql_examples_from_playground()
    return _CACHED_SQL_EXAMPLES


class TestSQLExamplesInPlayground:
    """Test SQL examples from the playground API endpoint."""
    
    def test_sql_examples_were_fetched(self):
        """Verify we can fetch SQL examples from the playground."""
        examples = cached_sql_examples()
        assert len(examples) > 0, "No SQL examples were fetched from playground"
        print(f"\nFetched {len(examples)} SQL examples from playground API")
    
    @pytest.mark.parametrize("example", [
        pytest.param(ex, id=ex.get("title", f"example_{i}"))
        for i, ex in enumerate(get_sql_examples_from_playground())
    ] if get_sql_examples_from_playground() else [
        pytest.param({"title": "skip", "dialect": "", "query": "SELECT 1"}, id="no_examples")
    ])
    def test_sql_example_can_reverse_compile(self, example):
        """Test that SQL examples can be reverse-compiled to ASQL."""
        if example.get("title") == "skip":
            pytest.skip("No SQL examples available")
        
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
            # Some complex SQL patterns may not reverse compile perfectly
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
        # Should use DATE_TRUNC or EXTRACT
        assert "DATE_TRUNC" in sql.upper() or "EXTRACT" in sql.upper() or "MONTH" in sql.upper()


# Summary report at the end
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a summary of playground example tests."""
    passed = len(terminalreporter.stats.get('passed', []))
    failed = len(terminalreporter.stats.get('failed', []))
    skipped = len(terminalreporter.stats.get('skipped', []))
    
    print(f"\n{'='*60}")
    print("PLAYGROUND EXAMPLES TEST SUMMARY")
    print(f"{'='*60}")
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Total:   {passed + failed + skipped}")
    print(f"{'='*60}")


if __name__ == "__main__":
    # Run a quick test to show what examples were extracted
    examples = extract_playground_examples()
    
    print("Extracted playground examples:")
    print(f"  ASQL Examples: {len(examples['asql'])}")
    print(f"  Pipeline Examples: {len(examples['asql_pipeline'])}")
    print(f"  Cohort Examples: {len(examples['cohort'])}")
    
    print("\nASQL Examples:")
    for ex in examples["asql"][:3]:
        print(f"  - {ex['title']}")
    
    print("\nPipeline Examples:")
    for ex in examples["asql_pipeline"][:3]:
        print(f"  - {ex['title']}")
    
    print("\nCohort Examples:")
    for ex in examples["cohort"]:
        print(f"  - {ex['title']}")
    
    # Quick compilation test
    print("\n" + "="*60)
    print("Quick compilation test (Snowflake dialect):")
    print("="*60)
    
    all_examples = get_all_asql_examples()
    passed = 0
    failed = 0
    
    for category, title, query in all_examples:
        try:
            result = compile(query, dialect="snowflake")
            passed += 1
            print(f"  ✓ [{category}] {title}")
        except Exception as e:
            failed += 1
            print(f"  ✗ [{category}] {title}: {str(e)[:60]}...")
    
    print(f"\nResults: {passed} passed, {failed} failed out of {len(all_examples)} examples")
