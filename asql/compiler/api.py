"""ASQL compiler public API."""

from typing import List, Optional, Tuple

import re
import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect
from sqlglot.optimizer.optimizer import optimize as sqlglot_optimize
from sqlglot.optimizer.eliminate_ctes import eliminate_ctes
from sqlglot.optimizer.simplify import simplify
from sqlglot.errors import OptimizeError

from asql.config import CompileSettings, KNOWN_COMPILE_SETTINGS
from asql.dialect import register_asql_dialect
from asql.errors import ASQLCompilationError, ASQLSyntaxError, ASQLDialectError
from asql.dialect_features import (
    Feature,
    check_feature,
    get_dialect_display_name,
)
from asql.compiler.auto_spine import _apply_auto_spine, _remove_guarantee_wrappers
from asql.compiler.inline_settings import (
    extract_dialect_from_comment,
    extract_inline_settings,
    extract_comment_settings,
)
from asql.compiler.auto_qualify import auto_qualify_columns
from asql.compiler.auto_alias import apply_auto_aliasing
from asql.compiler.alias_reuse import apply_alias_reuse
from asql.compiler.column_operators import transform_column_operators_for_dialect
from asql.compiler.underscore_shorthands import (
    apply_implicit_function_aliases,
    apply_since_until_underscore_shorthands,
)
from asql.compiler.explode_fallback import transform_explode_for_dialect
from asql.compiler.list_comprehension import (
    check_snowflake_list_comprehensions,
    fix_duckdb_list_comprehensions,
)
from asql.compiler.pivot_fallback import transform_pivot_for_dialect
from asql.compiler.cohort_transform import transform_cohort
from asql.compiler.join_fk_shorthand import transform_fk_shorthand
from asql.compiler.sqlglot_schema_adapter import to_sqlglot_schema


# Dialect aliases - map common aliases to SQLGlot's expected names
_DIALECT_ALIASES = {
    'postgresql': 'postgres',
}


def _split_multistatement_blocks(text: str) -> list[str]:
    """Split text into blocks separated by blank lines, where the next block starts a new statement.
    
    Recognizes FROM, WITH, and SELECT as statement starts.
    Also handles comments before the statement keyword.
    """
    lines = text.split("\n")
    blocks: list[str] = []
    current_lines: list[str] = []
    
    # Keywords that start a new statement
    statement_starts = ("from ", "from", "with ", "with", "select ", "select")

    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            # Found blank line - check if a new statement follows
            j = i + 1
            # Skip additional blank lines
            while j < len(lines) and not lines[j].strip():
                j += 1

            if j < len(lines):
                # Skip comment lines to find the actual statement start
                k = j
                while k < len(lines):
                    stripped = lines[k].strip()
                    if not stripped:
                        k += 1
                    elif stripped.startswith("--") or stripped.startswith("/*"):
                        k += 1
                    else:
                        break
                
                # Check if the first non-comment, non-blank line starts a new statement
                if k < len(lines):
                    next_line = lines[k].lstrip().lower()
                    if any(next_line.startswith(kw) for kw in statement_starts):
                        block = "\n".join(current_lines).strip()
                        if block:
                            blocks.append(block)
                        current_lines = []
                        i = j  # Start from first non-blank line (may be comment)
                        continue

        current_lines.append(line)
        i += 1

    last = "\n".join(current_lines).strip()
    if last:
        blocks.append(last)

    return blocks


def _maybe_merge_multistatement_stash_ctes(
    original: str,
    settings: CompileSettings,
    dialect: Optional[str],
) -> tuple[Optional[str], Optional[list[exp.Expression]]]:
    """If input is a blank-line multi-statement stash pattern, merge CTEs into final statement.

    This replaces the preparser's MultiStatementMixin so we can delete it.
    """
    if ";" in original:
        return None, None

    blocks = _split_multistatement_blocks(original)
    if len(blocks) <= 1:
        return None, None

    stash_tail = re.compile(r"\bstash\s+as\s+\w+\s*$", re.IGNORECASE)
    if not any(stash_tail.search(b.strip()) for b in blocks[:-1]):
        return None, None

    collected_ctes: list[exp.CTE] = []

    # Parse each stash block and collect its WITH expressions.
    for block in blocks[:-1]:
        if not stash_tail.search(block.strip()):
            continue

        parsed_stmts = sqlglot.parse(block, dialect="asql")
        stmt = next((s for s in parsed_stmts if s is not None), None)
        if not isinstance(stmt, exp.Select):
            continue

        with_ = stmt.args.get("with_")
        if with_ and hasattr(with_, "expressions"):
            for cte in with_.expressions:
                if isinstance(cte, exp.CTE):
                    collected_ctes.append(cte.copy())

    # Parse the final statement.
    final_statements = sqlglot.parse(blocks[-1], dialect="asql")
    final_stmt = next((s for s in final_statements if s is not None), None)
    if not final_stmt:
        return None, None

    if collected_ctes:
        with_ = final_stmt.args.get("with_")
        if with_ and hasattr(with_, "expressions"):
            with_.expressions = [*collected_ctes, *with_.expressions]
        else:
            final_stmt.set("with_", exp.With(expressions=collected_ctes))

    return "; ".join(blocks), [final_stmt]


def _normalize_dialect(dialect: str) -> str:
    """Normalize dialect name to SQLGlot's expected format."""
    return _DIALECT_ALIASES.get(dialect.lower(), dialect)


def _normalize_leading_set_statements(text: str) -> str:
    """Normalize leading SET statements to always be separated by semicolons.

    ASQL allows:
        SET auto_spine = false
        SET dialect = 'postgres'
        from users

    SQLGlot requires statement separators, so we rewrite the leading SET statements to:
        SET auto_spine = false; SET dialect = 'postgres'; from users

    We only rewrite known compile settings (plus legacy *_alias_prefix/_alias_template keys).
    """
    result = text.strip()
    preserved_sets: list[str] = []

    pattern = r"^\s*set\s+(\w+)\s*=\s*([^;]+?)(?:;|(?=\s*(?:set|from|select)\s)|\s*$)"

    while True:
        match = re.match(pattern, result, re.IGNORECASE)
        if not match:
            break

        name = match.group(1).lower()
        value = match.group(2).strip()

        if (
            name in KNOWN_COMPILE_SETTINGS
            or name.endswith("_alias_prefix")
            or name.endswith("_alias_template")
        ):
            preserved_sets.append(f"SET {name} = {value}")
            result = result[match.end() :].strip()
        else:
            break

    if preserved_sets:
        if result:
            return "; ".join(preserved_sets) + "; " + result
        return "; ".join(preserved_sets) + ";"

    return text


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
    #
    # Column operators are now parsed by the ASQL dialect. For dialects without native support,
    # we rely on schema-aware expansion in `transform_column_operators_for_dialect`.
    #
    # We should error early if:
    # - Dialect doesn't support COLUMN_EXCLUDE
    # - No schema is provided
    # - The original query uses column operators
    uses_column_ops = bool(
        re.search(r"\bexcept\s+(?!select\b)", original_query, re.IGNORECASE)
        or re.search(r"\brename\s+[a-zA-Z_]", original_query, re.IGNORECASE)
        or re.search(r"\breplace\s+[a-zA-Z_]", original_query, re.IGNORECASE)
    )
    if uses_column_ops and not check_feature(Feature.COLUMN_EXCLUDE, dialect) and not settings.schema:
        dialect_name = get_dialect_display_name(dialect)
        raise ASQLDialectError(
            f"Column operators ('except', 'rename', 'replace') are not supported for {dialect_name} without a schema.\n\n"
            f"Options:\n"
            f"  1. Provide a schema to enable automatic column enumeration (see docs/schema.md)\n"
            f"  2. Use explicit SELECT: 'select id, name, email from users'\n"
            f"  3. Use a dialect with EXCLUDE support: BigQuery, Snowflake, DuckDB\n\n"
            f"See: https://asql.dev/docs/dialect-limitations#column-operators"
        )
    
    # 2. Slice syntax - no longer needs validation (Issue #77 fixed)
    # The preparser now converts slice syntax to SUBSTRING/LEFT/RIGHT,
    # which SQLGlot correctly transpiles to all dialects.


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

        asql_query = _normalize_leading_set_statements(asql_query)
        base_settings = settings or CompileSettings()
        
        # Pre-scan for comment settings (these affect preparsing)
        include_transpilation, passthrough = extract_comment_settings(asql_query)
        if include_transpilation is not None:
            base_settings.include_transpilation_comments = include_transpilation
        if passthrough is not None:
            base_settings.passthrough_comments = passthrough

        if not dialect:
            dialect = extract_dialect_from_comment(asql_query)
        
        # Normalize dialect aliases (e.g., 'postgresql' -> 'postgres')
        if dialect:
            dialect = _normalize_dialect(dialect)

        # Handle stash-based CTEs across blank-line-separated statements
        merged_preparsed, merged_statements = _maybe_merge_multistatement_stash_ctes(
            asql_query, base_settings, dialect
        )

        if merged_preparsed is not None and merged_statements is not None:
            statements = merged_statements
        else:
            # Split on blank lines followed by FROM (multi-statement support)
            # Then parse each statement directly with SQLGlot - no preparser needed!
            blocks = _split_multistatement_blocks(asql_query)
            statements = []
            for block in blocks:
                if not block.strip():
                    continue
                try:
                    parsed = sqlglot.parse(block, dialect="asql")
                    statements.extend([s for s in parsed if s is not None])
                except sqlglot.errors.ParseError as e:
                    raise ASQLSyntaxError(
                        f"Failed to parse ASQL query.\n"
                        f"Query: {block}\n"
                        f"Error: {e}"
                    ) from e

        inline_settings, dialect_override, query_statements = extract_inline_settings(statements)
        final_settings = base_settings.merge_with(inline_settings)

        if dialect_override and not dialect:
            dialect = dialect_override

        # Filter to only actual query statements (not Semicolon nodes from trailing comments)
        query_statements = [
            s for s in query_statements
            if isinstance(s, (exp.Select, exp.Union, exp.Query, exp.Subquery, exp.CTE))
        ]

        if not query_statements:
            raise ASQLSyntaxError("No valid queries found (only SET statements)")

        sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
        
        # Validate dialect feature support
        _validate_dialect_features(asql_query, asql_query, dialect, final_settings)
        
        sql_parts = []

        for stmt in query_statements:
            transformed_stmt: exp.Expression = stmt
            transformations_applied: list[str] = []

            sqlglot_schema = to_sqlglot_schema(final_settings.schema, dialect=dialect)

            transformed_stmt = apply_since_until_underscore_shorthands(transformed_stmt, final_settings)
            transformed_stmt = apply_implicit_function_aliases(transformed_stmt, final_settings)
            transformed_stmt = transform_column_operators_for_dialect(transformed_stmt, dialect, final_settings)

            # Apply auto-aliasing FIRST so auto_spine can use the generated aliases
            transformed_stmt = apply_auto_aliasing(transformed_stmt, final_settings)

            # Expand FK shorthand in JOIN conditions (e.g., ON user_id → ON orders.user_id = users.id)
            transformed_stmt = transform_fk_shorthand(transformed_stmt, final_settings)
            
            # Transform cohort analysis queries (generates CTEs and JOINs)
            transformed_stmt = transform_cohort(transformed_stmt, final_settings)

            # Transform PIVOT to CASE/WHEN for non-native dialects BEFORE auto_spine
            # (auto_spine generates CTEs that should have PIVOT already resolved)
            transformed_stmt = transform_pivot_for_dialect(transformed_stmt, dialect, final_settings)

            # Rewrite EXPLODE joins for dialect-specific SQL (e.g. Snowflake FLATTEN)
            transformed_stmt = transform_explode_for_dialect(transformed_stmt, dialect)

            if final_settings.auto_spine:
                original_sql = transformed_stmt.sql()
                transformed_stmt = _apply_auto_spine(transformed_stmt, final_settings, dialect)
                # Check if auto-spine was actually applied by comparing SQL
                if transformed_stmt.sql() != original_sql:
                    transformations_applied.append("auto_spine")

            # Auto-qualify conflicting column names in joins
            transformed_stmt = auto_qualify_columns(transformed_stmt)

            # Apply alias reuse (allow referencing earlier aliases in SELECT)
            transformed_stmt = apply_alias_reuse(transformed_stmt, dialect)

            transformed_stmt = _remove_guarantee_wrappers(transformed_stmt)

            # Use SQLGlot's optimizer framework for conservative cleanup.
            #
            # NOTE: We intentionally do not run the full default rule set yet.
            # Some rules are schema- and dialect-sensitive and can be surprising in ASQL output.
            #
            # We also avoid `merge_subqueries` for now: it can raise `OptimizeError` on certain
            # dialect-specific table-function shapes (e.g., Snowflake EXPLODE/FLATTEN patterns).
            try:
                transformed_stmt = sqlglot_optimize(
                    transformed_stmt,
                    schema=sqlglot_schema,
                    dialect=dialect,
                    rules=(eliminate_ctes, simplify),
                )
            except OptimizeError:
                # Best-effort optimization only; compilation must remain robust.
                pass
            
            # Validate the compiled statement for semantic errors
            validation_errors = _validate_statement(transformed_stmt, asql_query)
            if validation_errors:
                raise ASQLCompilationError(
                    "Invalid query generated:\n" + 
                    "\n".join(f"  - {e}" for e in validation_errors) +
                    f"\n\nOriginal query:\n{asql_query[:500]}"
                )
            
            generated_sql = transformed_stmt.sql(
                dialect=sql_dialect,
                pretty=pretty,
                comments=final_settings.passthrough_comments,
            )

            # Fix DuckDB list comprehensions (use native syntax)
            generated_sql = fix_duckdb_list_comprehensions(generated_sql, dialect)

            # Check for Snowflake list comprehension issues
            check_snowflake_list_comprehensions(generated_sql, dialect)

            # Add transpilation comments if enabled
            if final_settings.include_transpilation_comments and transformations_applied:
                generated_sql = _add_transpilation_comments(
                    generated_sql, transformations_applied, pretty
                )
            
            # Strip trailing semicolons to avoid double semicolons when joining
            generated_sql = generated_sql.rstrip().rstrip(';').rstrip()
            sql_parts.append(generated_sql)

        return ";\n\n".join(sql_parts)

    except ASQLSyntaxError:
        raise
    except ASQLDialectError:
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

        asql_query = _normalize_leading_set_statements(asql_query)
        return sqlglot.parse_one(asql_query, dialect="asql")

    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e


def get_preparsed(asql_query: str) -> str:
    """Get the SQL representation of an ASQL query (for debugging).
    
    Note: This now parses with SQLGlot and re-generates.
    There is no separate preparser.
    """
    asql_query = _normalize_leading_set_statements(asql_query)
    ast = sqlglot.parse_one(asql_query, dialect="asql")
    return ast.sql()


def get_settings_from_query(
    asql_query: str,
    base_settings: Optional[CompileSettings] = None,
) -> Tuple[CompileSettings, Optional[str]]:
    """Extract inline settings from a query without compiling it."""
    base = base_settings or CompileSettings()

    asql_query = _normalize_leading_set_statements(asql_query)
    statements = sqlglot.parse(asql_query, dialect="asql")
    inline_settings, dialect_override, _ = extract_inline_settings(statements)
    return base.merge_with(inline_settings), dialect_override
