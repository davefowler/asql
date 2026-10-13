"""SQL executors for testing compiled ASQL queries against real databases."""

from asql.testing.executors.base import ExecutorBase
from asql.testing.executors.duckdb_executor import DuckDBExecutor

# Registry of available executors
EXECUTORS: dict[str, type[ExecutorBase]] = {
    "duckdb": DuckDBExecutor,
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
            cls()
            available.append(name)
        # Feature detection probe — swallow all init errors so missing deps just hide the executor.
        except Exception:  # noqa: BLE001, S110
            pass
    return available


__all__ = [
    "ExecutorBase",
    "DuckDBExecutor",
    "EXECUTORS",
    "get_available_executors",
]
