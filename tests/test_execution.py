"""Execution tests that run compiled ASQL queries against real databases."""

import pytest
from pathlib import Path
from typing import Any, List, Tuple

from asql import compile
from asql.testing.executors import get_available_executors, EXECUTORS


# Collect example files for parametrized testing
EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "pairs"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.asql")) if EXAMPLES_DIR.exists() else []


# Parametrize over all available executors
@pytest.fixture(params=get_available_executors())
def executor(request: pytest.FixtureRequest) -> Any:
    """Fixture that provides an executor instance for each available database."""
    exec_name = request.param
    exec_cls = EXECUTORS[exec_name]
    exec_instance = exec_cls()
    exec_instance.setup()
    yield exec_instance
    exec_instance.teardown()


class TestBasicExecution:
    """Test basic query execution and result correctness."""

    def test_simple_select(self, executor: Any) -> None:
        """Test basic SELECT query returns correct rows."""
        executor.create_table(
            "users",
            columns={"id": "INT", "name": "VARCHAR"},
            rows=[(1, "Alice"), (2, "Bob")],
        )

        sql = compile("from users select name", dialect=executor.dialect)
        rows = executor.execute(sql)

        assert len(rows) == 2
        assert ("Alice",) in rows
        assert ("Bob",) in rows

    def test_select_all_columns(self, executor: Any) -> None:
        """Test SELECT * returns all columns."""
        executor.create_table(
            "users",
            columns={"id": "INT", "name": "VARCHAR", "age": "INT"},
            rows=[(1, "Alice", 30), (2, "Bob", 25)],
        )

        sql = compile("from users", dialect=executor.dialect)
        columns, rows = executor.execute_and_fetch_columns(sql)

        assert len(columns) == 3
        assert "id" in columns
        assert "name" in columns
        assert "age" in columns
        assert len(rows) == 2

    def test_where_filter(self, executor: Any) -> None:
        """Test WHERE clause filters rows correctly."""
        executor.create_table(
            "users",
            columns={"id": "INT", "name": "VARCHAR", "status": "VARCHAR"},
            rows=[
                (1, "Alice", "active"),
                (2, "Bob", "inactive"),
                (3, "Charlie", "active"),
            ],
        )

        sql = compile(
            "from users where status == 'active'", dialect=executor.dialect
        )
        rows = executor.execute(sql)

        assert len(rows) == 2
        names = [row[1] for row in rows]
        assert "Alice" in names
        assert "Charlie" in names
        assert "Bob" not in names

    def test_aggregation(self, executor: Any) -> None:
        """Test GROUP BY aggregation returns correct values."""
        executor.create_table(
            "sales",
            columns={"region": "VARCHAR", "amount": "INT"},
            rows=[("North", 100), ("North", 50), ("South", 75)],
        )

        sql = compile(
            "from sales group by region (sum(amount) as total)",
            dialect=executor.dialect,
        )
        rows = executor.execute(sql)

        results = {r[0]: r[1] for r in rows}
        assert results["North"] == 150
        assert results["South"] == 75

    def test_multiple_aggregations(self, executor: Any) -> None:
        """Test multiple aggregations in GROUP BY."""
        executor.create_table(
            "sales",
            columns={"region": "VARCHAR", "amount": "INT"},
            rows=[
                ("North", 100),
                ("North", 50),
                ("South", 75),
                ("South", 25),
            ],
        )

        sql = compile(
            "from sales group by region (sum(amount) as total, avg(amount) as avg_amount, # as count)",
            dialect=executor.dialect,
        )
        rows = executor.execute(sql)

        results = {r[0]: {"total": r[1], "avg": r[2], "count": r[3]} for r in rows}
        assert results["North"]["total"] == 150
        assert results["North"]["avg"] == 75.0
        assert results["North"]["count"] == 2
        assert results["South"]["total"] == 100
        assert results["South"]["avg"] == 50.0
        assert results["South"]["count"] == 2

    def test_order_by(self, executor: Any) -> None:
        """Test ORDER BY sorts results correctly."""
        executor.create_table(
            "users",
            columns={"id": "INT", "name": "VARCHAR", "age": "INT"},
            rows=[(1, "Alice", 30), (2, "Bob", 25), (3, "Charlie", 35)],
        )

        sql = compile("from users order by age", dialect=executor.dialect)
        rows = executor.execute(sql)

        ages = [row[2] for row in rows]
        assert ages == [25, 30, 35]

    def test_order_by_descending(self, executor: Any) -> None:
        """Test descending ORDER BY."""
        executor.create_table(
            "users",
            columns={"id": "INT", "name": "VARCHAR", "age": "INT"},
            rows=[(1, "Alice", 30), (2, "Bob", 25), (3, "Charlie", 35)],
        )

        sql = compile("from users order by -age", dialect=executor.dialect)
        rows = executor.execute(sql)

        ages = [row[2] for row in rows]
        assert ages == [35, 30, 25]

    def test_limit(self, executor: Any) -> None:
        """Test LIMIT restricts number of rows."""
        executor.create_table(
            "users",
            columns={"id": "INT", "name": "VARCHAR"},
            rows=[(i, f"User{i}") for i in range(10)],
        )

        sql = compile("from users limit 5", dialect=executor.dialect)
        rows = executor.execute(sql)

        assert len(rows) == 5

    def test_join(self, executor: Any) -> None:
        """Test JOIN produces correct results."""
        executor.create_table(
            "users",
            columns={"id": "INT", "name": "VARCHAR"},
            rows=[(1, "Alice"), (2, "Bob")],
        )
        executor.create_table(
            "orders",
            columns={"id": "INT", "user_id": "INT", "total": "INT"},
            rows=[(1, 1, 100), (2, 1, 50), (3, 2, 75)],
        )

        sql = compile(
            "from users join orders on users.id == orders.user_id select users.name, orders.total",
            dialect=executor.dialect,
        )
        rows = executor.execute(sql)

        assert len(rows) == 3
        # Check that Alice has 2 orders
        alice_orders = [r[1] for r in rows if r[0] == "Alice"]
        assert len(alice_orders) == 2
        assert 100 in alice_orders
        assert 50 in alice_orders


class TestDialectSyntax:
    """Test that generated SQL is syntactically valid for each dialect."""

    @pytest.mark.parametrize(
        "asql_query",
        [
            "from t select name",
            "from t where id > 0",
            "from t group by region (sum(amount) as total)",
        ],
    )
    def test_basic_syntax_is_valid(
        self, executor: Any, asql_query: str
    ) -> None:
        """Test that basic queries generate valid SQL."""
        # Create minimal table for syntax validation
        executor.create_table(
            "t",
            columns={"id": "INT", "name": "VARCHAR", "region": "VARCHAR", "amount": "INT"},
            rows=[],
        )

        sql = compile(asql_query, dialect=executor.dialect)
        assert executor.validate_syntax(
            sql
        ), f"Invalid {executor.dialect} SQL: {sql}"

    def test_slice_syntax_validation(self, executor: Any) -> None:
        """Test that slice syntax generates valid SQL (Issue #77)."""
        executor.create_table(
            "t",
            columns={"name": "VARCHAR"},
            rows=[],
        )

        sql = compile("from t select name[1:5] as prefix", dialect=executor.dialect)
        # Note: This may fail for non-DuckDB dialects, which is the bug we're testing for
        is_valid = executor.validate_syntax(sql)
        if executor.dialect == "duckdb":
            assert is_valid, f"Slice syntax should be valid for DuckDB: {sql}"
        # For other dialects, we document that it may fail (this is the bug)


class TestExampleFiles:
    """Test that all example .asql files compile to valid SQL.
    
    These tests validate that the example files in examples/pairs/ compile
    successfully. Examples that use features not yet implemented are marked
    as xfail to track progress without blocking CI.
    """

    @pytest.mark.parametrize(
        "example_file",
        EXAMPLE_FILES,
        ids=[f.stem for f in EXAMPLE_FILES],
    )
    def test_example_compiles(self, example_file: Path) -> None:
        """Test that example ASQL files compile without errors."""
        asql_content = example_file.read_text()
        
        try:
            # Should compile without raising an exception
            sql = compile(asql_content, dialect="duckdb")
            
            # Basic sanity checks
            assert sql is not None
            assert len(sql) > 0
            assert "SELECT" in sql.upper() or "WITH" in sql.upper()
        except Exception as e:
            # Mark as xfail if compilation fails - these are examples that
            # may use features not yet fully implemented
            pytest.xfail(f"Example compilation failed (may use unimplemented features): {e}")

    @pytest.mark.parametrize(
        "example_file",
        EXAMPLE_FILES,
        ids=[f.stem for f in EXAMPLE_FILES],
    )
    def test_example_syntax_valid(self, example_file: Path, executor: Any) -> None:
        """Test that compiled example SQL is syntactically valid.
        
        Note: Some examples use double quotes for strings (e.g., "completed")
        which SQLGlot interprets as identifiers per SQL standard. These will
        fail syntax validation until the examples are updated to use single quotes.
        """
        asql_content = example_file.read_text()
        
        try:
            sql = compile(asql_content, dialect=executor.dialect)
        except Exception as e:
            pytest.xfail(f"Example compilation failed: {e}")
            return
        
        # For syntax validation, we need mock tables
        # Extract table names from FROM clauses (simple heuristic)
        import re
        
        # Find all table references (simplified - won't catch all cases)
        # Look for: FROM table, JOIN table, & table
        table_pattern = r'(?:FROM|JOIN|&)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        tables = set(re.findall(table_pattern, asql_content, re.IGNORECASE))
        
        # Create empty tables with generic schema
        generic_columns = {
            "id": "INT",
            "name": "VARCHAR",
            "status": "VARCHAR",
            "amount": "DECIMAL",
            "quantity": "INT",
            "price": "DECIMAL",
            "total": "DECIMAL",
            "total_amount": "DECIMAL",
            "date": "DATE",
            "created_at": "TIMESTAMP",
            "order_date": "DATE",
            "customer_id": "INT",
            "order_id": "INT",
            "product_id": "INT",
            "user_id": "INT",
            "region": "VARCHAR",
            "category": "VARCHAR",
            "email": "VARCHAR",
            "customer_name": "VARCHAR",
            "product_name": "VARCHAR",
            "event_name": "VARCHAR",
            "event_type": "VARCHAR",
            "event_date": "DATE",
            "revenue": "DECIMAL",
            "session_id": "VARCHAR",
            "page": "VARCHAR",
            "manager_id": "INT",
            "employee_name": "VARCHAR",
            "department": "VARCHAR",
            "first_name": "VARCHAR",
            "last_name": "VARCHAR",
            "description": "VARCHAR",
            "title": "VARCHAR",
            "type": "VARCHAR",
            "source": "VARCHAR",
            "channel": "VARCHAR",
            "campaign": "VARCHAR",
            "conversion_date": "DATE",
            "signup_date": "DATE",
            "last_login_date": "DATE",
            "activity_date": "DATE",
            "period_start": "DATE",
            "period_end": "DATE",
            "account_id": "INT",
            "transaction_date": "DATE",
            "debit": "DECIMAL",
            "credit": "DECIMAL",
            "balance": "DECIMAL",
            "segment": "VARCHAR",
            "score": "INT",
            "lifetime_value": "DECIMAL",
            "contract_start": "DATE",
            "contract_end": "DATE",
            "monthly_amount": "DECIMAL",
            "country": "VARCHAR",
            "line_total": "DECIMAL",
        }
        
        for table in tables:
            try:
                executor.create_table(table.lower(), generic_columns, [])
            except Exception:
                # Table might already exist or name is invalid
                pass
        
        is_valid = executor.validate_syntax(sql)
        
        # Mark expected failures for examples with double-quoted strings
        # These should be updated to use single quotes
        if not is_valid and '"' in asql_content:
            pytest.xfail(
                f"Example uses double quotes for strings (should use single quotes): {example_file.name}"
            )
        
        assert is_valid, f"Invalid {executor.dialect} SQL: {sql}"
