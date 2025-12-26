"""SQLite executor for testing compiled ASQL queries."""

import sqlite3
from typing import Any, Dict, List, Tuple

from asql.testing.executors.base import ExecutorBase


class SQLiteExecutor(ExecutorBase):
    """SQLite executor that runs SQL queries in an in-memory database.
    
    SQLite is built into Python's standard library, so no external dependencies
    are required. Uses in-memory database for fast, isolated testing.
    """

    def __init__(self) -> None:
        """Initialize SQLite in-memory connection."""
        self.conn = sqlite3.connect(":memory:")
        # Enable foreign keys for more complete SQL support
        self.conn.execute("PRAGMA foreign_keys = ON")

    @property
    def dialect(self) -> str:
        """Return the ASQL dialect name."""
        return "sqlite"

    def execute(self, sql: str) -> List[Tuple[Any, ...]]:
        """Execute SQL and return rows as tuples."""
        cursor = self.conn.execute(sql)
        return cursor.fetchall()

    def execute_and_fetch_columns(
        self, sql: str
    ) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        """Execute SQL and return column names and rows."""
        cursor = self.conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows

    def create_table(
        self, name: str, columns: Dict[str, str], rows: List[Tuple[Any, ...]]
    ) -> None:
        """Create a table with given schema and data."""
        # Map common types to SQLite types (SQLite has flexible typing)
        type_mapping = {
            "VARCHAR": "TEXT",
            "VARCHAR(255)": "TEXT",
            "DOUBLE": "REAL",
            "DOUBLE PRECISION": "REAL",
        }
        
        # Build CREATE TABLE statement
        col_defs = ", ".join(
            f"{col} {type_mapping.get(dtype.upper(), dtype)}"
            for col, dtype in columns.items()
        )
        create_sql = f"CREATE TABLE {name} ({col_defs})"
        self.conn.execute(create_sql)

        # Insert data if provided
        if rows:
            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f"INSERT INTO {name} VALUES ({placeholders})"
            self.conn.executemany(insert_sql, rows)
        
        self.conn.commit()

    def validate_syntax(self, sql: str) -> bool:
        """Check if SQL is syntactically valid without executing.
        
        SQLite doesn't have EXPLAIN for pure syntax validation, so we use
        sqlite3_prepare to parse without executing.
        """
        try:
            import re
            # Strip all comments before processing (they can contain semicolons)
            clean_sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
            
            # Handle multiple statements separated by semicolons
            statements = [s.strip() for s in clean_sql.split(";") if s.strip()]
            for stmt in statements:
                # Use EXPLAIN to validate syntax without executing
                self.conn.execute(f"EXPLAIN {stmt}")
            return True
        except Exception:
            return False

    def teardown(self) -> None:
        """Close SQLite connection."""
        if hasattr(self, "conn"):
            self.conn.close()

