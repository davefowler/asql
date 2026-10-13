"""ASQLValidator base class for testing ASQL → SQL compilation.

This module provides a testing pattern inspired by SQLGlot's Validator class.
It enables:
- Single-dialect validation: `validate_asql(asql, expected_sql)`
- Cross-dialect validation: `validate_all(asql, write={dialect: expected_sql})`
- Expected errors via `validate_all` exception-type entries
  (e.g. `write={"mysql": ASQLDialectError}`)
- AST-based comparison for more robust tests

Example usage:
    class TestBasicQueries(ASQLValidator):
        target_dialect = "postgres"

        def test_simple_from(self):
            self.validate_asql(
                "from users",
                "SELECT * FROM users"
            )

        def test_coalesce_cross_dialect(self):
            self.validate_all(
                "from users select name ?? 'Unknown' as display_name",
                write={
                    "postgres": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                    "duckdb": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                    "mysql": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                }
            )
"""

from __future__ import annotations

import unittest
from typing import Any

import sqlglot

from asql.config import CompileSettings
from asql.errors import ASQLCompilationError, ASQLDialectError, ASQLSyntaxError

from .fixtures import transpile as asql_transpile

# Type alias for expected outputs - can be SQL string or exception type
ExpectedOutput = str | type[Exception]


def normalize_sql(sql: str, dialect: str | None = None) -> str:
    """Normalize SQL for comparison by parsing and regenerating.

    This handles differences in:
    - Whitespace and formatting
    - Identifier quoting
    - Expression ordering (in some cases)

    Args:
        sql: SQL string to normalize
        dialect: SQL dialect for parsing/generation

    Returns:
        Normalized SQL string
    """
    try:
        return sqlglot.parse_one(sql, dialect=dialect).sql(dialect=dialect)
    except Exception:  # noqa: BLE001
        # If parsing fails, fall back to basic string normalization
        return " ".join(sql.split()).upper()


def compare_sql_ast(actual: str, expected: str, dialect: str | None = None) -> bool:
    """Compare two SQL statements by their AST structure.

    This is more robust than string comparison because it ignores:
    - Whitespace differences
    - Identifier quoting differences
    - Some expression reorderings

    Args:
        actual: Actual generated SQL
        expected: Expected SQL
        dialect: SQL dialect for parsing

    Returns:
        True if ASTs are equivalent, False otherwise
    """
    try:
        actual_ast = sqlglot.parse_one(actual, dialect=dialect)
        expected_ast = sqlglot.parse_one(expected, dialect=dialect)
        # Compare normalized SQL strings (SQLGlot's canonical form)
        return actual_ast.sql(dialect=dialect) == expected_ast.sql(dialect=dialect)
    except Exception:  # noqa: BLE001
        # Fall back to normalized string comparison
        return normalize_sql(actual, dialect) == normalize_sql(expected, dialect)


def sql_diff(actual: str, expected: str, dialect: str | None = None) -> str:
    """Generate a human-readable diff between two SQL statements.

    Args:
        actual: Actual generated SQL
        expected: Expected SQL
        dialect: SQL dialect for parsing

    Returns:
        Formatted diff string for error messages
    """
    actual_norm = normalize_sql(actual, dialect)
    expected_norm = normalize_sql(expected, dialect)

    return (
        f"\n{'=' * 60}\n"
        f"Expected SQL:\n{expected}\n"
        f"{'=' * 60}\n"
        f"Actual SQL:\n{actual}\n"
        f"{'=' * 60}\n"
        f"Expected (normalized):\n{expected_norm}\n"
        f"{'=' * 60}\n"
        f"Actual (normalized):\n{actual_norm}\n"
        f"{'=' * 60}"
    )


class ASQLValidator(unittest.TestCase):
    """Base class for ASQL validation tests.

    Subclasses can set:
        target_dialect: Default dialect for single-dialect tests
        settings: Default CompileSettings for tests

    Methods:
        validate_asql: Validate ASQL compiles to expected SQL for target dialect
        validate_all: Validate ASQL compiles correctly for multiple dialects
        validate_contains: Validate that compiled SQL contains expected substrings
    """

    # Default target dialect for single-dialect tests
    target_dialect: str | None = None

    # Default compile settings for simpler test output
    # Note: Using None as default to avoid mutable default argument issues
    settings: CompileSettings | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.settings is None:
            self.settings = CompileSettings()

    def validate_asql(
        self,
        asql: str,
        expected_sql: str,
        dialect: str | None = None,
        settings: CompileSettings | None = None,
        pretty: bool = False,
    ) -> str:
        """Validate that ASQL compiles to expected SQL.

        Args:
            asql: ASQL query to compile
            expected_sql: Expected SQL output
            dialect: SQL dialect (defaults to target_dialect)
            settings: Compile settings (defaults to self.settings)
            pretty: Whether to use pretty printing

        Returns:
            The compiled SQL string

        Raises:
            AssertionError: If compilation fails or output doesn't match
        """
        dialect = dialect or self.target_dialect
        settings = settings or self.settings

        try:
            actual_sql = asql_transpile(
                asql,
                dialect=dialect,
                pretty=pretty,
                settings=settings,
            )
        except Exception as e:  # noqa: BLE001
            self.fail(
                f"ASQL compilation failed:\n"
                f"  ASQL: {asql}\n"
                f"  Dialect: {dialect}\n"
                f"  Error: {type(e).__name__}: {e}"
            )

        # Compare using AST comparison
        if not compare_sql_ast(actual_sql, expected_sql, dialect):
            self.fail(
                f"SQL mismatch for dialect '{dialect}':\n"
                f"  ASQL: {asql}\n"
                f"{sql_diff(actual_sql, expected_sql, dialect)}"
            )

        return actual_sql

    def validate_all(
        self,
        asql: str,
        write: dict[str, ExpectedOutput],
        settings: CompileSettings | None = None,
        pretty: bool = False,
    ) -> dict[str, str]:
        """Validate ASQL compiles correctly for multiple dialects.

        Args:
            asql: ASQL query to compile
            write: Dict mapping dialect names to expected SQL or exception types
            settings: Compile settings (defaults to self.settings)
            pretty: Whether to use pretty printing

        Returns:
            Dict mapping dialect names to compiled SQL strings

        Example:
            self.validate_all(
                "from users select year(created_at) as yr",
                write={
                    "postgres": "SELECT EXTRACT(YEAR FROM created_at) AS yr FROM users",
                    "duckdb": "SELECT YEAR(created_at) AS yr FROM users",
                    "bigquery": "SELECT EXTRACT(YEAR FROM created_at) AS yr FROM users",
                    "mysql": ASQLDialectError,  # Feature not supported
                }
            )
        """
        settings = settings or self.settings
        results: dict[str, str] = {}
        errors: list[str] = []

        for dialect, expected in write.items():
            with self.subTest(dialect=dialect):
                if isinstance(expected, type):
                    # Expect an error
                    try:
                        actual_sql = asql_transpile(
                            asql,
                            dialect=dialect,
                            pretty=pretty,
                            settings=settings,
                        )
                        errors.append(
                            f"Dialect '{dialect}': Expected {expected.__name__} "
                            f"but got SQL: {actual_sql}"
                        )
                    except expected:
                        # Expected error was raised, test passes
                        pass
                    except Exception as e:  # noqa: BLE001
                        errors.append(
                            f"Dialect '{dialect}': Expected {expected.__name__} "
                            f"but got {type(e).__name__}: {e}"
                        )
                else:
                    # Expect SQL string
                    try:
                        actual_sql = asql_transpile(
                            asql,
                            dialect=dialect,
                            pretty=pretty,
                            settings=settings,
                        )
                        results[dialect] = actual_sql

                        if not compare_sql_ast(actual_sql, expected, dialect):
                            errors.append(
                                f"Dialect '{dialect}': SQL mismatch\n"
                                f"{sql_diff(actual_sql, expected, dialect)}"
                            )
                    except Exception as e:  # noqa: BLE001
                        errors.append(
                            f"Dialect '{dialect}': Compilation failed\n"
                            f"  Error: {type(e).__name__}: {e}"
                        )

        if errors:
            self.fail(
                f"Cross-dialect validation failed for:\n"
                f"  ASQL: {asql}\n\n" + "\n\n".join(errors)
            )

        return results

    def validate_contains(
        self,
        asql: str,
        *substrings: str,
        dialect: str | None = None,
        settings: CompileSettings | None = None,
        case_sensitive: bool = False,
    ) -> str:
        """Validate that compiled SQL contains expected substrings.

        This is useful for partial validation when exact SQL match is impractical.

        Args:
            asql: ASQL query to compile
            *substrings: Substrings that should appear in output
            dialect: SQL dialect (defaults to target_dialect)
            settings: Compile settings (defaults to self.settings)
            case_sensitive: Whether substring matching is case-sensitive

        Returns:
            The compiled SQL string
        """
        dialect = dialect or self.target_dialect
        settings = settings or self.settings

        try:
            actual_sql = asql_transpile(asql, dialect=dialect, settings=settings)
        except Exception as e:  # noqa: BLE001
            self.fail(
                f"ASQL compilation failed:\n"
                f"  ASQL: {asql}\n"
                f"  Dialect: {dialect}\n"
                f"  Error: {type(e).__name__}: {e}"
            )

        check_sql = actual_sql if case_sensitive else actual_sql.lower()

        for substring in substrings:
            check_sub = substring if case_sensitive else substring.lower()
            assert check_sub in check_sql, (
                f"Expected substring '{substring}' not found in SQL:\n{actual_sql}"
            )

        return actual_sql


# Re-export common error types for use in tests
__all__ = [
    "ASQLValidator",
    "compare_sql_ast",
    "normalize_sql",
    "sql_diff",
    "ASQLDialectError",
    "ASQLSyntaxError",
    "ASQLCompilationError",
]
