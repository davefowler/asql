"""SQL executors for testing compiled ASQL queries against real databases."""

from asql.testing.executors.base import ExecutorBase
from asql.testing.executors.duckdb_executor import DuckDBExecutor
from asql.testing.executors.postgres_executor import PostgresExecutor

# Registry of available executors
EXECUTORS: dict[str, type[ExecutorBase]] = {
    "duckdb": DuckDBExecutor,
    "postgres": PostgresExecutor,
}


def get_available_executors() -> list[str]:
    """Return list of available executor names (those that can be instantiated).

    Returns:
        List of executor names that are available (dependencies installed).
    """
    available: list[str] = []
    for name, cls in EXECUTORS.items():
        try:
            # Try to instantiate to check if dependencies are available
            instance = cls()
            available.append(name)
        # Feature detection probe — swallow all init errors so missing deps just hide the executor.
        except Exception:  # noqa: BLE001, S110
            pass
        else:
            instance.teardown()
    return available


__all__ = [
    "ExecutorBase",
    "DuckDBExecutor",
    "PostgresExecutor",
    "EXECUTORS",
    "get_available_executors",
]
