"""ASQLValidator base class for testing ASQL → SQL compilation.

This module provides a testing pattern inspired by SQLGlot's Validator class.
It enables:
- Single-dialect validation: `validate_asql(asql, expected_sql)`
- Cross-dialect validation: `validate_all(asql, write={dialect: expected_sql})`
- AST-based comparison for more robust tests
- Support for expected errors (UnsupportedError, ASQLDialectError)

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

import unittest
from typing import Dict, Optional, Type, Union

import sqlglot
from sqlglot import exp

from asql import compile as asql_compile
from asql.config import CompileSettings
from asql.errors import ASQLDialectError, ASQLSyntaxError, ASQLCompilationError


# Type alias for expected outputs - can be SQL string or exception type
ExpectedOutput = Union[str, Type[Exception]]


def normalize_sql(sql: str, dialect: Optional[str] = None) -> str:
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
        parsed = sqlglot.parse_one(sql, dialect=dialect)
        if parsed is None:
            return sql.strip().upper()
        # Generate normalized SQL
        return parsed.sql(dialect=dialect)
    except Exception:
        # If parsing fails, fall back to basic string normalization
        return " ".join(sql.split()).upper()


def compare_sql_ast(actual: str, expected: str, dialect: Optional[str] = None) -> bool:
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
        
        if actual_ast is None or expected_ast is None:
            return False
        
        # Compare normalized SQL strings (SQLGlot's canonical form)
        return actual_ast.sql(dialect=dialect) == expected_ast.sql(dialect=dialect)
    except Exception:
        # Fall back to normalized string comparison
        return normalize_sql(actual, dialect) == normalize_sql(expected, dialect)


def sql_diff(actual: str, expected: str, dialect: Optional[str] = None) -> str:
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
        f"\n{'='*60}\n"
        f"Expected SQL:\n{expected}\n"
        f"{'='*60}\n"
        f"Actual SQL:\n{actual}\n"
        f"{'='*60}\n"
        f"Expected (normalized):\n{expected_norm}\n"
        f"{'='*60}\n"
        f"Actual (normalized):\n{actual_norm}\n"
        f"{'='*60}"
    )


class ASQLValidator(unittest.TestCase):
    """Base class for ASQL validation tests.
    
    Subclasses can set:
        target_dialect: Default dialect for single-dialect tests
        settings: Default CompileSettings for tests
        
    Methods:
        validate_asql: Validate ASQL compiles to expected SQL for target dialect
        validate_all: Validate ASQL compiles correctly for multiple dialects
        validate_error: Validate that ASQL raises expected error
    """
    
    # Default target dialect for single-dialect tests
    target_dialect: Optional[str] = None
    
    # Default compile settings - auto_spine disabled for simpler test output
    settings: Optional[CompileSettings] = CompileSettings(auto_spine=False)
    
    def validate_asql(
        self,
        asql: str,
        expected_sql: str,
        dialect: Optional[str] = None,
        settings: Optional[CompileSettings] = None,
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
            actual_sql = asql_compile(
                asql,
                dialect=dialect,
                pretty=pretty,
                settings=settings,
            )
        except Exception as e:
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
        write: Dict[str, ExpectedOutput],
        settings: Optional[CompileSettings] = None,
        pretty: bool = False,
    ) -> Dict[str, str]:
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
        results: Dict[str, str] = {}
        errors: list[str] = []
        
        for dialect, expected in write.items():
            with self.subTest(dialect=dialect):
                if isinstance(expected, type) and issubclass(expected, Exception):
                    # Expect an error
                    try:
                        actual_sql = asql_compile(
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
                    except Exception as e:
                        errors.append(
                            f"Dialect '{dialect}': Expected {expected.__name__} "
                            f"but got {type(e).__name__}: {e}"
                        )
                else:
                    # Expect SQL string
                    try:
                        actual_sql = asql_compile(
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
                    except Exception as e:
                        errors.append(
                            f"Dialect '{dialect}': Compilation failed\n"
                            f"  Error: {type(e).__name__}: {e}"
                        )
        
        if errors:
            self.fail(
                f"Cross-dialect validation failed for:\n"
                f"  ASQL: {asql}\n\n" +
                "\n\n".join(errors)
            )
        
        return results
    
    def validate_error(
        self,
        asql: str,
        expected_error: Type[Exception],
        dialect: Optional[str] = None,
        settings: Optional[CompileSettings] = None,
        error_contains: Optional[str] = None,
    ) -> None:
        """Validate that ASQL raises an expected error.
        
        Args:
            asql: ASQL query to compile
            expected_error: Expected exception type
            dialect: SQL dialect (defaults to target_dialect)
            settings: Compile settings (defaults to self.settings)
            error_contains: Optional substring that error message should contain
        """
        dialect = dialect or self.target_dialect
        settings = settings or self.settings
        
        with self.assertRaises(expected_error) as context:
            asql_compile(asql, dialect=dialect, settings=settings)
        
        if error_contains:
            self.assertIn(
                error_contains.lower(),
                str(context.exception).lower(),
                f"Error message should contain '{error_contains}':\n{context.exception}"
            )
    
    def validate_contains(
        self,
        asql: str,
        *substrings: str,
        dialect: Optional[str] = None,
        settings: Optional[CompileSettings] = None,
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
            actual_sql = asql_compile(asql, dialect=dialect, settings=settings)
        except Exception as e:
            self.fail(
                f"ASQL compilation failed:\n"
                f"  ASQL: {asql}\n"
                f"  Dialect: {dialect}\n"
                f"  Error: {type(e).__name__}: {e}"
            )
        
        check_sql = actual_sql if case_sensitive else actual_sql.lower()
        
        for substring in substrings:
            check_sub = substring if case_sensitive else substring.lower()
            self.assertIn(
                check_sub,
                check_sql,
                f"Expected substring '{substring}' not found in SQL:\n{actual_sql}"
            )
        
        return actual_sql
    
    def validate_valid_sql(
        self,
        asql: str,
        dialect: Optional[str] = None,
        settings: Optional[CompileSettings] = None,
    ) -> str:
        """Validate that ASQL compiles to valid, parseable SQL.
        
        This doesn't check the exact output, just that it's valid SQL.
        
        Args:
            asql: ASQL query to compile
            dialect: SQL dialect (defaults to target_dialect)
            settings: Compile settings (defaults to self.settings)
            
        Returns:
            The compiled SQL string
        """
        dialect = dialect or self.target_dialect
        settings = settings or self.settings
        
        try:
            actual_sql = asql_compile(asql, dialect=dialect, settings=settings)
        except Exception as e:
            self.fail(
                f"ASQL compilation failed:\n"
                f"  ASQL: {asql}\n"
                f"  Dialect: {dialect}\n"
                f"  Error: {type(e).__name__}: {e}"
            )
        
        # Try to parse the generated SQL
        try:
            parsed = sqlglot.parse_one(actual_sql, dialect=dialect)
            self.assertIsNotNone(
                parsed,
                f"SQLGlot returned None when parsing:\n{actual_sql}"
            )
        except sqlglot.errors.ParseError as e:
            self.fail(
                f"Generated SQL is not valid:\n"
                f"  ASQL: {asql}\n"
                f"  SQL: {actual_sql}\n"
                f"  Parse Error: {e}"
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
