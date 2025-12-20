"""ASQL compiler public API."""

from typing import List, Optional, Tuple

import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect

from asql.config import CompileSettings
from asql.dialect import register_asql_dialect
from asql.errors import ASQLCompilationError, ASQLSyntaxError, ASQLDialectError, ASQLDialectWarning
from asql.preparse import preparse_asql
from asql.dialect_features import (
    Feature,
    check_feature,
    has_column_operators,
    has_slice_syntax,
    get_dialect_display_name,
)
import warnings
from asql.compiler.auto_spine import _apply_auto_spine, _remove_guarantee_wrappers
from asql.compiler.explode import process_explode_markers
from asql.compiler.inline_settings import (
    extract_dialect_from_comment,
    extract_inline_settings,
    extract_comment_settings,
)
from asql.compiler.auto_qualify import auto_qualify_columns
from asql.compiler.auto_alias import apply_auto_aliasing


def _validate_dialect_features(
    original_query: str,
    preparsed_query: str,
    dialect: Optional[str],
    settings: CompileSettings,
) -> None:
    """Validate that features used in the query are supported by the target dialect.
    
    Raises ASQLDialectError for unsupported features without workarounds.
    Raises ASQLDialectWarning for features with known issues or partial support.
    
    Args:
        original_query: Original ASQL query string
        preparsed_query: Pre-parsed SQL-like query string
        dialect: Target SQL dialect
        settings: Compile settings (for schema availability check)
    """
    if not dialect:
        return  # Can't validate without a dialect
    
    # 1. Check column operators (except, rename, replace)
    if has_column_operators(preparsed_query):
        if not check_feature(Feature.COLUMN_EXCLUDE, dialect):
            dialect_name = get_dialect_display_name(dialect)
            schema_available = settings.schema is not None
            
            if schema_available:
                # Schema can enable fallback (Issue #80) - warn but allow
                warnings.warn(
                    ASQLDialectWarning(
                        f"Column operators ('except', 'rename', 'replace') are not natively supported "
                        f"for {dialect_name}.\n\n"
                        f"A schema is provided, so ASQL will attempt to expand columns automatically. "
                        f"If this fails, use explicit SELECT: 'select col1, col2 from table'.\n\n"
                        f"See: https://asql.dev/docs/dialect-limitations#column-operators"
                    )
                )
            else:
                # No schema - hard error
                raise ASQLDialectError(
                    f"Column operators ('except', 'rename', 'replace') are not supported for {dialect_name}.\n\n"
                    f"The 'except' operator requires EXCEPT/EXCLUDE syntax which {dialect_name} doesn't support.\n\n"
                    f"Options:\n"
                    f"  1. Provide a schema to enable automatic column enumeration (see docs/schema.md)\n"
                    f"  2. Use explicit SELECT: 'select id, name, email from users'\n"
                    f"  3. Use a dialect with EXCLUDE support: BigQuery, Snowflake, DuckDB\n\n"
                    f"See: https://asql.dev/docs/dialect-limitations#column-operators"
                )
    
    # 2. Check slice syntax (known bug #77)
    if has_slice_syntax(original_query):
        if not check_feature(Feature.SLICE_SYNTAX, dialect):
            dialect_name = get_dialect_display_name(dialect)
            warnings.warn(
                ASQLDialectWarning(
                    f"Slice syntax '[start:end]' has known issues for {dialect_name} (Issue #77).\n\n"
                    f"The generated SQL may be invalid. Use SUBSTRING() instead:\n"
                    f"  'select substring(name, 1, 5) as prefix'\n\n"
                    f"See: https://asql.dev/docs/dialect-limitations#slice-syntax"
                )
            )


def _validate_statement(stmt: exp.Expression, original_query: str) -> List[str]:
    """Validate a compiled statement for common structural errors.
    
    Returns a list of error messages (empty if valid).
    
    NOTE: This is NOT a complete SQL validator. It catches obvious structural
    issues that indicate the preparser mangled the query (e.g., inline comments
    eating the FROM clause). It does NOT validate:
    - Column existence (would require schema)
    - Aggregate/GROUP BY correctness (window functions complicate this)
    - Type compatibility
    
    The goal is to catch clearly broken queries before they're returned,
    not to be a full semantic validator.
    """
    errors: List[str] = []
    
    if not isinstance(stmt, exp.Select):
        return errors
    
    has_from = stmt.find(exp.From) is not None
    
    # Check for column references in SELECT
    select_cols = []
    for sel_expr in stmt.expressions:
        if isinstance(sel_expr, exp.Column):
            select_cols.append(sel_expr)
        elif isinstance(sel_expr, exp.Alias):
            inner = sel_expr.this
            if isinstance(inner, exp.Column):
                select_cols.append(inner)
    
    # Error: SELECT with table column references but no FROM clause
    # This catches the common preparser bug where inline comments eat the FROM.
    # We only flag this if there are actual column references (not just literals).
    if select_cols and not has_from:
        col_names = [c.name for c in select_cols[:3]]
        errors.append(
            f"Query references columns ({', '.join(col_names)}) but has no FROM clause. "
            f"This may indicate a parsing error - check for inline comments "
            f"that might be hiding part of the query."
        )
    
    return errors


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
        
        # Pre-scan for comment settings (these affect preparsing)
        include_transpilation, passthrough = extract_comment_settings(asql_query)
        if include_transpilation is not None:
            base_settings.include_transpilation_comments = include_transpilation
        if passthrough is not None:
            base_settings.passthrough_comments = passthrough

        if not dialect:
            dialect = extract_dialect_from_comment(asql_query)

        # Pass settings to preparser for schema-aware join inference
        preparsed = preparse_asql(asql_query, settings=base_settings)
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
        
        # Validate dialect feature support
        _validate_dialect_features(asql_query, preparsed, dialect, final_settings)
        
        sql_parts = []

        for stmt in query_statements:
            transformed_stmt: exp.Expression = stmt
            transformations_applied: list[str] = []

            # Apply auto-aliasing FIRST so auto_spine can use the generated aliases
            transformed_stmt = apply_auto_aliasing(transformed_stmt, final_settings)

            if final_settings.auto_spine:
                original_sql = transformed_stmt.sql()
                transformed_stmt = _apply_auto_spine(transformed_stmt, final_settings, dialect)
                # Check if auto-spine was actually applied by comparing SQL
                if transformed_stmt.sql() != original_sql:
                    transformations_applied.append("auto_spine")

            # Auto-qualify conflicting column names in joins
            transformed_stmt = auto_qualify_columns(transformed_stmt)

            transformed_stmt = _remove_guarantee_wrappers(transformed_stmt)
            
            # Validate the compiled statement for semantic errors
            validation_errors = _validate_statement(transformed_stmt, asql_query)
            if validation_errors:
                raise ASQLCompilationError(
                    f"Invalid query generated:\n" + 
                    "\n".join(f"  - {e}" for e in validation_errors) +
                    f"\n\nOriginal query:\n{asql_query[:500]}"
                )
            
            generated_sql = transformed_stmt.sql(dialect=sql_dialect, pretty=pretty)
            
            # Add transpilation comments if enabled
            if final_settings.include_transpilation_comments and transformations_applied:
                generated_sql = _add_transpilation_comments(
                    generated_sql, transformations_applied, pretty
                )
            
            sql_parts.append(generated_sql)

        return ";\n\n".join(sql_parts)

    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e


def _add_transpilation_comments(
    sql: str,
    transformations: list[str],
    pretty: bool,
) -> str:
    """Add explanatory comments about ASQL transformations to generated SQL.
    
    Args:
        sql: The generated SQL string
        transformations: List of transformation names that were applied
        pretty: Whether pretty printing is enabled
        
    Returns:
        SQL with explanatory comments prepended
    """
    comments: list[str] = []
    
    for transform in transformations:
        if transform == "auto_spine":
            comments.append(
                "/* ASQL auto-spine: Gap-filling CTEs were generated to ensure all "
                "expected GROUP BY values appear (even with zero/null aggregates). "
                "Disable with: SET auto_spine = false; */"
            )
        elif transform == "cohort":
            comments.append(
                "/* ASQL cohort: Cohort analysis CTEs were generated to track "
                "user cohorts over time periods. */"
            )
    
    if not comments:
        return sql
    
    separator = "\n\n" if pretty else " "
    return separator.join(comments) + separator + sql


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

    preparsed = preparse_asql(asql_query)
    statements = sqlglot.parse(preparsed)
    inline_settings, dialect_override, _ = extract_inline_settings(statements)
    return base.merge_with(inline_settings), dialect_override
