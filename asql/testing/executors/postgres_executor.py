"""PostgreSQL executor for testing compiled ASQL queries."""

import os
from typing import Any, Dict, List, Tuple

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # type: ignore

from asql.testing.executors.base import ExecutorBase


class PostgresExecutor(ExecutorBase):
    """PostgreSQL executor that runs SQL queries against a PostgreSQL database.
    
    PostgreSQL is a good proxy for Redshift since Redshift is PostgreSQL-based.
    Connection URL is read from POSTGRES_URL environment variable, with a
    sensible default for local Docker development.
    """

    def __init__(self) -> None:
        """Initialize PostgreSQL connection."""
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is not installed. Install it with: pip install psycopg2-binary"
            )
        
        # Use env var or default to local Docker
        connection_url = os.environ.get(
            'POSTGRES_URL',
            'postgresql://postgres:postgres@localhost:5432/test'
        )
        
        try:
            self.conn = psycopg2.connect(connection_url)
            # Enable autocommit for simpler transaction handling in tests
            self.conn.autocommit = True
        except psycopg2.OperationalError as e:
            raise ImportError(
                f"Could not connect to PostgreSQL: {e}. "
                "Ensure PostgreSQL is running or set POSTGRES_URL environment variable."
            ) from e
        
        self._created_tables: List[str] = []

    @property
    def dialect(self) -> str:
        """Return the ASQL dialect name."""
        return "postgres"

    def execute(self, sql: str) -> List[Tuple[Any, ...]]:
        """Execute SQL and return rows as tuples."""
        with self.conn.cursor() as cursor:
            cursor.execute(sql)
            if cursor.description is not None:
                result: List[Tuple[Any, ...]] = cursor.fetchall()
                return result
            return []

    def execute_and_fetch_columns(
        self, sql: str
    ) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        """Execute SQL and return column names and rows."""
        with self.conn.cursor() as cursor:
            cursor.execute(sql)
            if cursor.description is None:
                return [], []
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return columns, rows

    def create_table(
        self, name: str, columns: Dict[str, str], rows: List[Tuple[Any, ...]]
    ) -> None:
        """Create a table with given schema and data."""
        # Map common types to PostgreSQL types
        type_mapping = {
            "VARCHAR": "VARCHAR(255)",
            "DOUBLE": "DOUBLE PRECISION",
        }
        
        # Build CREATE TABLE statement
        col_defs = ", ".join(
            f"{col} {type_mapping.get(dtype.upper(), dtype)}"
            for col, dtype in columns.items()
        )
        
        # Drop table if exists to ensure clean state
        with self.conn.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {name}")
            cursor.execute(f"CREATE TABLE {name} ({col_defs})")
        
        self._created_tables.append(name)

        # Insert data if provided
        if rows:
            placeholders = ", ".join(["%s"] * len(columns))
            insert_sql = f"INSERT INTO {name} VALUES ({placeholders})"
            with self.conn.cursor() as cursor:
                cursor.executemany(insert_sql, rows)

    def validate_syntax(self, sql: str) -> bool:
        """Check if SQL is syntactically valid without executing.
        
        Uses EXPLAIN to validate syntax without actually running the query.
        """
        try:
            import re
            # Strip all comments before processing (they can contain semicolons)
            clean_sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
            
            # Handle multiple statements separated by semicolons
            statements = [s.strip() for s in clean_sql.split(";") if s.strip()]
            for stmt in statements:
                # Use EXPLAIN to validate syntax without executing
                with self.conn.cursor() as cursor:
                    cursor.execute(f"EXPLAIN {stmt}")
            return True
        except Exception:
            return False

    def teardown(self) -> None:
        """Clean up created tables and close PostgreSQL connection."""
        if hasattr(self, "conn") and self.conn:
            try:
                with self.conn.cursor() as cursor:
                    for table in self._created_tables:
                        cursor.execute(f"DROP TABLE IF EXISTS {table}")
            except Exception:
                pass  # Ignore cleanup errors
            finally:
                self.conn.close()
