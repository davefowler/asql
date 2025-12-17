"""ASQL compiler public API."""

from __future__ import annotations

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

        try:
            statements = sqlglot.parse(preparsed, dialect=dialect)
        except sqlglot.errors.ParseError as e:
            raise ASQLSyntaxError(
                "Failed to parse ASQL query.\n"
                f"Original: {asql_query}\n"
                f"Pre-parsed: {preparsed}\n"
                f"Error: {e}"
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
