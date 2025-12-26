"""SQL executors for testing compiled ASQL queries against real databases."""

from typing import List, Type

from asql.testing.executors.base import ExecutorBase
from asql.testing.executors.duckdb_executor import DuckDBExecutor
from asql.testing.executors.postgres_executor import PostgresExecutor
from asql.testing.executors.sqlite_executor import SQLiteExecutor

# Registry of available executors
EXECUTORS: dict[str, Type[ExecutorBase]] = {
    "duckdb": DuckDBExecutor,
    "postgres": PostgresExecutor,
    "sqlite": SQLiteExecutor,
    # Future executors:
    # 'snowflake': SnowflakeExecutor,
}


def get_available_executors() -> List[str]:
    """Return list of available executor names (those that can be instantiated).
    
    Returns:
        List of executor names that are available (dependencies installed).
    """
    available: List[str] = []
    for name, cls in EXECUTORS.items():
        try:
            # Try to instantiate to check if dependencies are available
            cls()
            available.append(name)
        except (ImportError, Exception):
            # Dependency not installed or other initialization error
            pass
    return available


__all__ = [
    "ExecutorBase",
    "DuckDBExecutor",
    "PostgresExecutor",
    "SQLiteExecutor",
    "EXECUTORS",
    "get_available_executors",
]
