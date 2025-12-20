"""Abstract base class for SQL executors."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


class ExecutorBase(ABC):
    """Abstract base for SQL executors that run compiled SQL against databases."""

    @property
    @abstractmethod
    def dialect(self) -> str:
        """Return the ASQL dialect name (e.g., 'duckdb', 'postgres').
        
        Returns:
            Dialect name string that matches ASQL dialect names.
        """
        pass

    @abstractmethod
    def execute(self, sql: str) -> List[Tuple[Any, ...]]:
        """Execute SQL and return rows as tuples.
        
        Args:
            sql: SQL query string to execute.
            
        Returns:
            List of tuples, where each tuple represents a row.
        """
        pass

    @abstractmethod
    def execute_and_fetch_columns(
        self, sql: str
    ) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        """Execute SQL and return column names and rows.
        
        Args:
            sql: SQL query string to execute.
            
        Returns:
            Tuple of (column_names, rows) where column_names is a list of strings
            and rows is a list of tuples.
        """
        pass

    @abstractmethod
    def create_table(
        self, name: str, columns: Dict[str, str], rows: List[Tuple[Any, ...]]
    ) -> None:
        """Create a table with given schema and data.
        
        Args:
            name: Table name.
            columns: Dictionary mapping column names to their SQL types (e.g., 'INT', 'VARCHAR').
            rows: List of tuples representing data rows to insert.
        """
        pass

    @abstractmethod
    def validate_syntax(self, sql: str) -> bool:
        """Check if SQL is syntactically valid without executing.
        
        Args:
            sql: SQL query string to validate.
            
        Returns:
            True if SQL is syntactically valid, False otherwise.
        """
        pass

    def setup(self) -> None:
        """Called before test suite runs. Override for initialization."""
        pass

    def teardown(self) -> None:
        """Called after test suite completes. Override for cleanup."""
        pass
