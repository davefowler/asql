"""ASQL compiler public API."""

from typing import Optional, Tuple

import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect

from asql.config import CompileSettings
from asql.dialect import register_asql_dialect
from asql.errors import ASQLCompilationError, ASQLSyntaxError
from asql.preparse import preparse_asql
from asql.compiler.auto_spine import _apply_auto_spine, _remove_guarantee_wrappers
from asql.compiler.explode import process_explode_markers
from asql.compiler.inline_settings import extract_dialect_from_comment, extract_inline_settings
from asql.compiler.auto_qualify import auto_qualify_columns
from asql.compiler.auto_alias import apply_auto_aliasing


# Ensure ASQL dialect is registered
register_asql_dialect()


def compile(
    asql_query: str,
    dialect: Optional[str] = None,
    pretty: bool = False,
    settings: Optional[CompileSettings] = None,
) -> str:
    """Compile ASQL query to SQL."""
    try:
        if not asql_query.strip():
            raise ASQLSyntaxError("Empty ASQL query")

        base_settings = settings or CompileSettings()

        if not dialect:
            dialect = extract_dialect_from_comment(asql_query)

        preparsed = preparse_asql(asql_query)
        preparsed = process_explode_markers(preparsed, dialect)

        # Parse with the target dialect when possible, but fall back to generic parsing.
        # Some dialect parsers (e.g. Trino) reject otherwise-representable constructs
        # such as QUALIFY; SQLGlot can still transpile these when parsed generically.
        parse_error: Optional[Exception] = None
        try:
            statements = sqlglot.parse(preparsed, dialect=dialect)
        except sqlglot.errors.ParseError as e:
            parse_error = e
            try:
                statements = sqlglot.parse(preparsed)
            except sqlglot.errors.ParseError:
                raise ASQLSyntaxError(
                    "Failed to parse ASQL query.\n"
                    f"Original: {asql_query}\n"
                    f"Pre-parsed: {preparsed}\n"
                    f"Error: {parse_error}"
                ) from e

        inline_settings, dialect_override, query_statements = extract_inline_settings(statements)
        final_settings = base_settings.merge_with(inline_settings)

        if dialect_override and not dialect:
            dialect = dialect_override

        if not query_statements:
            raise ASQLSyntaxError("No valid queries found (only SET statements)")

        sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
        sql_parts = []

        for stmt in query_statements:
            transformed_stmt: exp.Expression = stmt

            if final_settings.auto_spine:
                try:
                    transformed_stmt = _apply_auto_spine(stmt, final_settings, dialect)
                except Exception:
                    transformed_stmt = stmt

            # Auto-qualify conflicting column names in joins
            try:
                transformed_stmt = auto_qualify_columns(transformed_stmt)
            except Exception:
                # If auto-qualification fails, continue with original statement
                pass

            # Apply auto-aliasing to function calls without explicit aliases
            try:
                transformed_stmt = apply_auto_aliasing(transformed_stmt, final_settings)
            except Exception:
                # If auto-aliasing fails, continue with original statement
                pass

            transformed_stmt = _remove_guarantee_wrappers(transformed_stmt)
            sql_parts.append(transformed_stmt.sql(dialect=sql_dialect, pretty=pretty))

        return ";\n\n".join(sql_parts)

    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e


def compile_to_ast(asql_query: str) -> exp.Expression:
    """Compile ASQL query to a SQLGlot AST (no SQL generation)."""
    try:
        if not asql_query.strip():
            raise ASQLSyntaxError("Empty ASQL query")

        sql_like = preparse_asql(asql_query)
        return sqlglot.parse_one(sql_like)

    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e


def get_preparsed(asql_query: str) -> str:
    """Get the pre-parsed (SQL-like) representation of an ASQL query."""
    return preparse_asql(asql_query)


def get_settings_from_query(
    asql_query: str,
    base_settings: Optional[CompileSettings] = None,
) -> Tuple[CompileSettings, Optional[str]]:
    """Extract inline settings from a query without compiling it."""
    base = base_settings or CompileSettings()

    try:
        preparsed = preparse_asql(asql_query)
        statements = sqlglot.parse(preparsed)
        inline_settings, dialect_override, _ = extract_inline_settings(statements)
        return base.merge_with(inline_settings), dialect_override
    except Exception:
        return base, None
