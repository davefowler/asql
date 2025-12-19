"""DuckDB executor for testing compiled ASQL queries."""

from typing import Any, Dict, List, Tuple

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore

from asql.testing.executors.base import ExecutorBase


class DuckDBExecutor(ExecutorBase):
    """DuckDB executor that runs SQL queries in an in-memory database."""

    def __init__(self) -> None:
        """Initialize DuckDB connection."""
        if duckdb is None:
            raise ImportError(
                "duckdb is not installed. Install it with: pip install duckdb"
            )
        self.conn = duckdb.connect(":memory:")

    @property
    def dialect(self) -> str:
        """Return the ASQL dialect name."""
        return "duckdb"

    def execute(self, sql: str) -> List[Tuple[Any, ...]]:
        """Execute SQL and return rows as tuples."""
        return self.conn.execute(sql).fetchall()

    def execute_and_fetch_columns(
        self, sql: str
    ) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        """Execute SQL and return column names and rows."""
        result = self.conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return columns, rows

    def create_table(
        self, name: str, columns: Dict[str, str], rows: List[Tuple[Any, ...]]
    ) -> None:
        """Create a table with given schema and data."""
        # Build CREATE TABLE statement
        col_defs = ", ".join(f"{col} {dtype}" for col, dtype in columns.items())
        create_sql = f"CREATE TABLE {name} ({col_defs})"
        self.conn.execute(create_sql)

        # Insert data if provided
        if rows:
            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f"INSERT INTO {name} VALUES ({placeholders})"
            self.conn.executemany(insert_sql, rows)

    def validate_syntax(self, sql: str) -> bool:
        """Check if SQL is syntactically valid without executing."""
        try:
            # Handle multiple statements separated by semicolons
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            for stmt in statements:
                # Use EXPLAIN to validate syntax without executing
                self.conn.execute(f"EXPLAIN {stmt}")
            return True
        except Exception:
            return False

    def teardown(self) -> None:
        """Close DuckDB connection."""
        if hasattr(self, "conn"):
            self.conn.close()
