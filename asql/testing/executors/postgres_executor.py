"""PostgreSQL executor for testing compiled ASQL queries.

Connects to the database named by ``ASQL_TEST_POSTGRES_URL`` (a libpq URL such
as ``postgresql://postgres:postgres@localhost:5432/postgres``). Each executor
instance works in a schema of its own, created in ``setup`` and dropped in
``teardown``, so tests that create a ``users`` table never collide.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any

try:
    import psycopg
except ImportError:
    psycopg = None  # type: ignore[assignment]

from asql.testing.executors.base import ExecutorBase

ENV_VAR = "ASQL_TEST_POSTGRES_URL"

# Tests declare columns in DuckDB's spelling; map the names PostgreSQL lacks.
_TYPES = {"DOUBLE": "DOUBLE PRECISION"}


class PostgresExecutor(ExecutorBase):
    """Run SQL against the PostgreSQL server named by ``ASQL_TEST_POSTGRES_URL``."""

    def __init__(self) -> None:
        if psycopg is None:
            raise ImportError(
                "psycopg is not installed; install asql with the 'dev' extra"
            )
        url = os.environ.get(ENV_VAR)
        if not url:
            raise RuntimeError(f"{ENV_VAR} is not set; no PostgreSQL to test against")
        self.conn = psycopg.connect(url, autocommit=True)
        self.schema = f"asql_test_{uuid.uuid4().hex[:12]}"

    @property
    def dialect(self) -> str:
        return "postgres"

    def setup(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {self.schema}")
            cur.execute(f"SET search_path TO {self.schema}")

    def teardown(self) -> None:
        try:
            with self.conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE")
        finally:
            self.conn.close()

    def execute(self, sql: str) -> list[tuple[Any, ...]]:
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall())

    def execute_and_fetch_columns(
        self, sql: str
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        with self.conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc.name for desc in cur.description or []]
            return columns, list(cur.fetchall())

    def create_table(
        self, name: str, columns: dict[str, str], rows: list[tuple[Any, ...]]
    ) -> None:
        col_defs = ", ".join(
            f"{col} {_TYPES.get(dtype.upper(), dtype)}"
            for col, dtype in columns.items()
        )
        with self.conn.cursor() as cur:
            cur.execute(f"CREATE TABLE {name} ({col_defs})")
            if rows:
                placeholders = ", ".join(["%s"] * len(columns))
                cur.executemany(f"INSERT INTO {name} VALUES ({placeholders})", rows)

    def validate_syntax(self, sql: str) -> bool:
        clean_sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        statements = [s.strip() for s in clean_sql.split(";") if s.strip()]
        try:
            with self.conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(f"EXPLAIN {stmt}")
            return True
        except psycopg.Error:
            return False
