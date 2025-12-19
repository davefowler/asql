"""Auto-spine transformation helpers.

Auto-spine automatically adds gap-filling spines for GROUP BY columns.

This module intentionally exports a number of semi-private helpers that the
test suite imports directly.

## New Unified Approach (v2)

Both date and categorical columns are handled with the same pattern:
1. Generate a "wide" spine (all possible values)
2. Copy relevant WHERE predicates to filter the spine
3. LEFT JOIN with aggregated data

For dates: generate_series(config_min, CURRENT_DATE, interval) + WHERE filter
For categoricals: SELECT DISTINCT col FROM table + WHERE filter

This approach:
- Avoids semantic parsing of WHERE bounds (>, <, >=, etc.)
- Handles edge cases (no data in first/last periods) correctly
- Provides consistent behavior for dates and categoricals
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple, Set

import sqlglot
from sqlglot import exp

from asql.config import CompileSettings
from asql.errors import ASQLCompilationError

logger = logging.getLogger(__name__)


# Default spine date bounds (can be made configurable later)
SPINE_MIN_DATE = "'1970-01-01'"
SPINE_MAX_DATE = "CURRENT_DATE"


def _generate_spine_comment(metadata: dict) -> str:
    """Generate a descriptive comment for a spine CTE.
    
    Args:
        metadata: Dict with keys: alias, is_date, trunc_unit, explicit_values,
                  source_column, source_table, needs_data_bounds
    
    Returns:
        Comment text (without /* */ markers - SQLGlot adds those)
    """
    alias = metadata.get("alias", "column")
    is_date = metadata.get("is_date", False)
    trunc_unit = metadata.get("trunc_unit")
    explicit_values = metadata.get("explicit_values")
    source_column = metadata.get("source_column")
    source_table = metadata.get("source_table", "table")
    needs_data_bounds = metadata.get("needs_data_bounds", False)
    
    if explicit_values:
        # Explicit values from guarantee()
        values_preview = explicit_values[:3]
        if len(explicit_values) > 3:
            values_str = ", ".join(f"'{v}'" for v in values_preview) + ", ..."
        else:
            values_str = ", ".join(f"'{v}'" for v in values_preview)
        return f"Guaranteed values for {alias}: [{values_str}]"
    
    if is_date and trunc_unit:
        # Date spine
        col_ref = source_column or alias
        if needs_data_bounds:
            return f"Date spine for {trunc_unit}({col_ref}) - range from data MIN to MAX"
        else:
            return f"Date spine for {trunc_unit}({col_ref}) - ensures all {trunc_unit}s in range appear"
    
    # Categorical spine (DISTINCT values)
    col_ref = source_column or alias
    return f"All distinct values of '{col_ref}' from {source_table}"


DATE_TRUNC_FUNCTIONS = {
    "year",
    "month",
    "week",
    "day",
    "hour",
    "quarter",
    "date_trunc",
}


TRUNC_TO_INTERVAL = {
    "year": "1 year",
    "month": "1 month",
    "week": "1 week",
    "day": "1 day",
    "hour": "1 hour",
    "quarter": "3 months",
}


def _detect_rollup_cube(stmt: exp.Expression) -> Tuple[bool, bool, List[str]]:
    """Detect if a statement uses ROLLUP or CUBE in GROUP BY."""
    has_rollup = False
    has_cube = False
    columns: List[str] = []

    rollup = stmt.find(exp.Rollup)
    if rollup:
        has_rollup = True
        for expr_ in rollup.expressions:
            if isinstance(expr_, exp.Column):
                columns.append(expr_.name)
            elif isinstance(expr_, exp.Alias):
                columns.append(expr_.alias)
            else:
                columns.append(expr_.sql())

    cube = stmt.find(exp.Cube)
    if cube:
        has_cube = True
        for expr_ in cube.expressions:
            if isinstance(expr_, exp.Column):
                columns.append(expr_.name)
            elif isinstance(expr_, exp.Alias):
                columns.append(expr_.alias)
            else:
                columns.append(expr_.sql())

    return has_rollup, has_cube, columns


def _is_guarantee_wrapped(expr_: exp.Expression) -> Tuple[bool, Optional[List[str]]]:
    """Check if an expression is wrapped in guarantee() for explicit spine."""
    inner = expr_.this if isinstance(expr_, exp.Alias) else expr_

    if isinstance(inner, exp.Anonymous) and inner.name and inner.name.lower() == "guarantee":
        if len(inner.expressions) > 1:
            values_expr = inner.expressions[1]
            if isinstance(values_expr, exp.Array):
                values = [str(e.this).strip("'\"") for e in values_expr.expressions]
                return True, values
            return True, None
        return True, None

    return False, None


def _unwrap_guarantee(expr_: exp.Expression) -> exp.Expression:
    """Unwrap guarantee() wrapper and return the inner expression."""
    if isinstance(expr_, exp.Alias):
        inner = expr_.this
        if isinstance(inner, exp.Anonymous) and inner.name and inner.name.lower() == "guarantee":
            if inner.expressions:
                return exp.Alias(this=inner.expressions[0], alias=expr_.alias)
        return expr_

    if isinstance(expr_, exp.Anonymous) and expr_.name and expr_.name.lower() == "guarantee":
        if expr_.expressions:
            return expr_.expressions[0]

    return expr_


def _remove_guarantee_wrappers(stmt: exp.Expression) -> exp.Expression:
    """Remove all guarantee() wrappers from a statement before SQL generation."""
    if not isinstance(stmt, exp.Select):
        return stmt

    group = stmt.find(exp.Group)
    if group:
        new_exprs = []
        for expr_ in group.expressions:
            is_guarantee, _ = _is_guarantee_wrapped(expr_)
            new_exprs.append(_unwrap_guarantee(expr_) if is_guarantee else expr_)
        group.set("expressions", new_exprs)

    if stmt.expressions:
        new_exprs = []
        for expr_ in stmt.expressions:
            is_guarantee, _ = _is_guarantee_wrapped(expr_)
            new_exprs.append(_unwrap_guarantee(expr_) if is_guarantee else expr_)
        stmt.set("expressions", new_exprs)

    return stmt


def _get_column_names_from_expr(expr_: exp.Expression) -> Set[str]:
    """Extract all column names referenced in an expression."""
    columns: Set[str] = set()
    for col in expr_.find_all(exp.Column):
        columns.add(col.name)
    return columns


def _get_source_column_from_trunc(trunc_expr: exp.Expression) -> Optional[exp.Expression]:
    """Extract the source column from a date truncation expression."""
    expr_ = trunc_expr
    if isinstance(expr_, exp.Alias):
        expr_ = expr_.this

    if isinstance(expr_, (exp.Anonymous, exp.Func)):
        # Handle date_trunc('unit', column) - column is second argument
        if hasattr(expr_, "name") and expr_.name and expr_.name.lower() == "date_trunc":
            if len(expr_.expressions) > 1:
                return expr_.expressions[1]

        # Handle functions like MONTH(column), YEAR(column) where arg is in expressions
        if expr_.expressions:
            return expr_.expressions[0]

        # Handle SQLGlot's typed date functions (Month, Year, etc.) where arg is in .this
        if hasattr(expr_, "this") and expr_.this is not None:
            return expr_.this

    return None


def _is_predicate_safe_for_spine(
    predicate: exp.Expression,
    target_column: str,
) -> bool:
    """Check if a predicate is safe to use in a spine CTE.
    
    A predicate is "safe" if:
    - It only references the target column (no other table columns)
    - Other referenced values are literals, functions, or constants
    
    Unsafe predicates reference other columns that won't exist in the spine context.
    
    Examples:
    - Safe: created_at >= '2021-01-01' (column + literal)
    - Safe: YEAR(created_at) = 2021 (function on column + literal)
    - Unsafe: created_at > updated_at (two columns)
    - Unsafe: created_at BETWEEN start_date AND end_date (columns as bounds)
    """
    columns = _get_column_names_from_expr(predicate)
    
    # If the predicate doesn't reference our target column, it's not relevant
    if target_column not in columns:
        return False
    
    # If it references ONLY our target column, it's safe
    if columns == {target_column}:
        return True
    
    # If it references other columns besides the target, it's unsafe
    # (those columns won't exist in the spine CTE)
    return False


def _extract_predicates_for_column(
    where_clause: Optional[exp.Where],
    source_column_name: str,
) -> Tuple[List[exp.Expression], List[exp.Expression]]:
    """Extract predicates from WHERE that involve a specific column.
    
    This finds any predicate (comparison, IN, BETWEEN, etc.) that references
    the given column and returns them as two lists:
    1. Safe predicates - only reference the target column (can be used in spine)
    2. Unsafe predicates - reference other columns (skipped for spine)
    
    Args:
        where_clause: The WHERE clause expression
        source_column_name: The column name to look for (e.g., 'created_at')
        
    Returns:
        Tuple of (safe_predicates, unsafe_predicates)
    """
    if not where_clause:
        return [], []
    
    safe_predicates: List[exp.Expression] = []
    unsafe_predicates: List[exp.Expression] = []
    
    def find_predicates(node: exp.Expression) -> None:
        """Recursively find predicates involving the target column."""
        # Handle AND - recurse into both sides
        if isinstance(node, exp.And):
            find_predicates(node.this)
            find_predicates(node.expression)
            return
        
        # Handle OR - if either side involves our column, check safety
        if isinstance(node, exp.Or):
            columns_in_node = _get_column_names_from_expr(node)
            if source_column_name in columns_in_node:
                # OR predicates with other columns are always unsafe
                # because we can't partially apply them
                if _is_predicate_safe_for_spine(node, source_column_name):
                    safe_predicates.append(node.copy())
                else:
                    unsafe_predicates.append(node.copy())
            return
        
        # For other predicates (comparisons, IN, BETWEEN, etc.)
        # Check if they reference our target column
        columns_in_node = _get_column_names_from_expr(node)
        if source_column_name in columns_in_node:
            if _is_predicate_safe_for_spine(node, source_column_name):
                safe_predicates.append(node.copy())
            else:
                unsafe_predicates.append(node.copy())

    find_predicates(where_clause.this)
    return safe_predicates, unsafe_predicates


def _transform_predicate_for_spine(
    predicate: exp.Expression,
    source_column_name: str,
    spine_column_name: str,
) -> exp.Expression:
    """Transform a predicate to use the spine column name instead of source column.
    
    For date spines, we transform: created_at >= '2021-01-01' -> d >= '2021-01-01'
    where 'd' is the generate_series output variable.
    
    For categorical spines, we just use the same column name.
    """
    result = predicate.copy()
    
    for col in result.find_all(exp.Column):
        if col.name == source_column_name:
            col.set("this", exp.to_identifier(spine_column_name))
            # Clear table qualifier if present
            if col.args.get("table"):
                col.set("table", None)
    
    return result


def _predicates_to_where_sql(predicates: List[exp.Expression], dialect: Optional[str] = None) -> str:
    """Convert list of predicates to a WHERE clause SQL string."""
    if not predicates:
        return ""
    
    if len(predicates) == 1:
        return f"WHERE {predicates[0].sql(dialect=dialect)}"
    
    # Combine with AND
    combined = predicates[0]
    for pred in predicates[1:]:
        combined = exp.And(this=combined, expression=pred)
    
    return f"WHERE {combined.sql(dialect=dialect)}"


def _find_select_alias_for_expr(stmt: exp.Select, expr: exp.Expression) -> Optional[str]:
    """Find alias from SELECT for a matching expression.
    
    If the SELECT has an alias for an expression matching expr, return that alias.
    This is used to leverage auto-aliasing when GROUP BY expressions don't have aliases.
    """
    expr_sql = expr.sql()
    
    for sel_expr in stmt.expressions:
        if isinstance(sel_expr, exp.Alias):
            # Compare the inner expression
            if sel_expr.this.sql() == expr_sql:
                return sel_expr.alias
    
    return None


def _get_all_group_by_columns(
    stmt: exp.Expression,
) -> List[Tuple[str, exp.Expression, bool, Optional[str], Optional[List[str]], Optional[str]]]:
    """Get all GROUP BY columns with their spine information.
    
    Returns list of tuples:
    - alias: output column alias
    - group_expr: the GROUP BY expression
    - is_date: whether this is a date truncation
    - trunc_unit: the truncation unit (month, day, etc.) if is_date
    - explicit_values: explicit values from guarantee() if any
    - source_column: the source column name (for predicate extraction)
    """
    results: List[Tuple[str, exp.Expression, bool, Optional[str], Optional[List[str]], Optional[str]]] = []

    if not isinstance(stmt, exp.Select):
        return results

    group_by = stmt.find(exp.Group)
    if not group_by:
        return results

    all_group_exprs: List[exp.Expression] = []

    for group_expr in group_by.expressions:
        if isinstance(group_expr, (exp.Rollup, exp.Cube)):
            all_group_exprs.extend(list(group_expr.expressions))
        else:
            all_group_exprs.append(group_expr)

    rollup_list = group_by.args.get("rollup", [])
    for rollup in rollup_list or []:
        if isinstance(rollup, exp.Rollup):
            all_group_exprs.extend(list(rollup.expressions))

    cube_list = group_by.args.get("cube", [])
    for cube in cube_list or []:
        if isinstance(cube, exp.Cube):
            all_group_exprs.extend(list(cube.expressions))

    for group_expr in all_group_exprs:
        alias: Optional[str] = None
        is_date = False
        trunc_unit: Optional[str] = None
        explicit_values: Optional[List[str]] = None
        source_column: Optional[str] = None

        is_guarantee, values = _is_guarantee_wrapped(group_expr)
        if is_guarantee:
            explicit_values = values

        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
            inner = group_expr.this
            if is_guarantee and isinstance(inner, exp.Anonymous):
                inner = inner.expressions[0] if inner.expressions else inner
        else:
            inner = group_expr
            if is_guarantee and isinstance(inner, exp.Anonymous):
                inner = inner.expressions[0] if inner.expressions else inner
            if isinstance(inner, exp.Column):
                alias = inner.name

        # If no alias found, check SELECT for matching auto-generated alias
        if not alias:
            alias = _find_select_alias_for_expr(stmt, group_expr)

        if not alias:
            alias = f"col_{len(results)}"

        # Determine function name and source column
        func_name = None
        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, "sql_name") else type(inner).__name__.lower()

        # Get source column for predicate extraction
        if isinstance(inner, exp.Column):
            source_column = inner.name
        else:
            source_col_expr = _get_source_column_from_trunc(group_expr)
            if source_col_expr and isinstance(source_col_expr, exp.Column):
                source_column = source_col_expr.name

        if func_name in DATE_TRUNC_FUNCTIONS:
            is_date = True
            if func_name == "date_trunc":
                if inner.expressions:
                    unit_arg = inner.expressions[0]
                    if isinstance(unit_arg, exp.Literal):
                        trunc_unit = unit_arg.this.strip("'\"").lower()
            else:
                trunc_unit = func_name

        results.append((alias, group_expr, is_date, trunc_unit, explicit_values, source_column))

    return results


def _build_spine_cte_sql(
    alias: str,
    is_date: bool,
    trunc_unit: Optional[str],
    explicit_values: Optional[List[str]],
    source_column: Optional[str],
    source_table: str,
    safe_predicates: List[exp.Expression],
    all_predicates: List[exp.Expression],
    has_unsafe_predicates: bool,
    dialect: Optional[str] = None,
    include_null: bool = False,
    use_data_bounds: bool = False,
    data_cte_name: Optional[str] = None,
) -> str:
    """Build SQL for a spine CTE - unified for both dates and categoricals.
    
    Args:
        alias: Output column alias
        is_date: Whether this is a date column
        trunc_unit: Date truncation unit (month, day, etc.) if is_date
        explicit_values: Explicit values from guarantee() if any
        source_column: Source column name for predicate transformation
        source_table: Source table name
        safe_predicates: Predicates that only reference the target column (safe for dates)
        all_predicates: All predicates involving the column (safe for categoricals)
        has_unsafe_predicates: Whether any predicates reference other columns
        dialect: SQL dialect
        include_null: Include NULL for ROLLUP/CUBE support
        use_data_bounds: For date spines, use data MIN/MAX instead of wide range
        data_cte_name: Name of the data CTE to reference for MIN/MAX bounds
    """
    dialect_lower = dialect.lower() if dialect else ""
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""
    
    # Case 1: Explicit values from guarantee()
    if explicit_values:
        return _build_explicit_values_spine_sql(alias, explicit_values, dialect, include_null)
    
    # Case 2: Date column
    if is_date and trunc_unit:
        interval = TRUNC_TO_INTERVAL.get(trunc_unit, "1 day")
        
        # If we have unsafe predicates, use data MIN/MAX fallback
        if has_unsafe_predicates and use_data_bounds and data_cte_name:
            # Emit info-level message (not a warning - this is correct behavior)
            logger.info(
                f"Date spine for '{alias}' is bounded by data MIN/MAX because WHERE clause "
                f"contains column-to-column comparisons. This correctly represents the range "
                f"where your predicate can be satisfied. Add explicit date bounds if you want "
                f"a fixed range instead."
            )
            return _build_date_spine_from_data_bounds_sql(
                alias, trunc_unit, interval, data_cte_name, dialect, include_null
            )
        
        # Transform safe predicates to use 'd' (the series variable)
        spine_predicates = []
        for pred in safe_predicates:
            if source_column:
                transformed = _transform_predicate_for_spine(pred, source_column, "d")
                spine_predicates.append(transformed)
        
        where_sql = _predicates_to_where_sql(spine_predicates, dialect)
        
        return _build_date_spine_with_filter_sql(
            alias, trunc_unit, interval, where_sql, dialect, include_null
        )
    
    # Case 3: Categorical column - SELECT DISTINCT with filter
    # For categoricals, ALL predicates are safe because we query from source table
    col_expr = source_column or alias
    
    # Use all predicates (they're all safe for categoricals)
    where_sql = _predicates_to_where_sql(all_predicates, dialect)
    
    if include_null:
        return (
            f"SELECT DISTINCT {col_expr} AS {alias} FROM {source_table} {where_sql} "
            f"UNION ALL SELECT NULL AS {alias}"
        )
    return f"SELECT DISTINCT {col_expr} AS {alias} FROM {source_table} {where_sql}"


def _build_date_spine_from_data_bounds_sql(
    alias: str,
    trunc_unit: str,
    interval: str,
    data_cte_name: str,
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a date spine using MIN/MAX from the data CTE.
    
    This is used as a fallback when WHERE predicates reference other columns
    that don't exist in the generate_series context.
    
    The spine is built by:
    1. Getting MIN/MAX of the grouped date column from the data CTE
    2. Generating dates between those bounds
    """
    dialect_lower = dialect.lower() if dialect else ""
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""
    
    # We reference the data CTE to get the date bounds
    # The data CTE already has the grouped date column aliased as 'alias'
    
    if dialect_lower in ("postgres", "postgresql", "redshift"):
        return (
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM generate_series("
            f"(SELECT MIN({alias}) FROM {data_cte_name})::date, "
            f"(SELECT MAX({alias}) FROM {data_cte_name})::date, "
            f"INTERVAL '{interval}') AS d"
        ) + null_union
    
    if dialect_lower == "duckdb":
        return (
            f"SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias} "
            f"FROM generate_series("
            f"(SELECT MIN({alias}) FROM {data_cte_name})::date, "
            f"(SELECT MAX({alias}) FROM {data_cte_name})::date, "
            f"INTERVAL '{interval}') AS t(d)"
        ) + null_union
    
    if dialect_lower == "bigquery":
        return (
            f"SELECT DATE_TRUNC(d, {trunc_unit.upper()}) AS {alias} "
            f"FROM UNNEST(GENERATE_DATE_ARRAY("
            f"(SELECT MIN({alias}) FROM {data_cte_name}), "
            f"(SELECT MAX({alias}) FROM {data_cte_name}))) AS d"
        ) + null_union
    
    if dialect_lower == "snowflake":
        return (
            f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), "
            f"(SELECT MIN({alias}) FROM {data_cte_name}))) AS {alias} "
            f"FROM TABLE(GENERATOR(ROWCOUNT => 100000)) "
            f"WHERE DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), "
            f"(SELECT MIN({alias}) FROM {data_cte_name}))) <= "
            f"(SELECT MAX({alias}) FROM {data_cte_name})"
        ) + null_union
    
    # Default: postgres-style
    return (
        f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
        f"FROM generate_series("
        f"(SELECT MIN({alias}) FROM {data_cte_name})::date, "
        f"(SELECT MAX({alias}) FROM {data_cte_name})::date, "
        f"INTERVAL '{interval}') AS d"
    ) + null_union


def _build_explicit_values_spine_sql(
    alias: str,
    values: List[str],
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a categorical spine with explicit values."""
    dialect_lower = dialect.lower() if dialect else ""

    values_sql = ", ".join([f"'{v}'" for v in values])
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""

    if dialect_lower in ("postgres", "postgresql", "redshift", "duckdb"):
        return f"SELECT unnest(ARRAY[{values_sql}]) AS {alias}{null_union}"
    if dialect_lower == "bigquery":
        return f"SELECT {alias} FROM UNNEST([{values_sql}]) AS {alias}{null_union}"
    if dialect_lower == "snowflake":
        return (
            f"SELECT value AS {alias} FROM TABLE(FLATTEN(INPUT => SPLIT('{','.join(values)}', ',')))"
            f"{null_union}"
        )

    unions = [f"SELECT '{v}' AS {alias}" for v in values]
    if include_null:
        unions.append(f"SELECT NULL AS {alias}")
    return " UNION ALL ".join(unions)


def _build_date_spine_with_filter_sql(
    alias: str,
    trunc_unit: str,
    interval: str,
    where_sql: str,
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a date spine with wide range and filter.
    
    Uses generate_series from SPINE_MIN_DATE to SPINE_MAX_DATE,
    then applies the WHERE filter to limit the range.
    """
    dialect_lower = dialect.lower() if dialect else ""
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""
    
    if dialect_lower in ("postgres", "postgresql", "redshift"):
        base = (
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM generate_series({SPINE_MIN_DATE}::date, {SPINE_MAX_DATE}::date, INTERVAL '{interval}') AS d"
        )
        if where_sql:
            return f"{base} {where_sql}{null_union}"
        return f"{base}{null_union}"
    
    if dialect_lower == "duckdb":
        base = (
            f"SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias} "
            f"FROM generate_series({SPINE_MIN_DATE}::date, {SPINE_MAX_DATE}::date, INTERVAL '{interval}') AS t(d)"
        )
        if where_sql:
            return f"{base} {where_sql}{null_union}"
        return f"{base}{null_union}"
    
    if dialect_lower == "bigquery":
        # BigQuery uses GENERATE_DATE_ARRAY
        base = (
            f"SELECT DATE_TRUNC(d, {trunc_unit.upper()}) AS {alias} "
            f"FROM UNNEST(GENERATE_DATE_ARRAY(DATE {SPINE_MIN_DATE}, CURRENT_DATE())) AS d"
        )
        if where_sql:
            return f"{base} {where_sql}{null_union}"
        return f"{base}{null_union}"
    
    if dialect_lower == "snowflake":
        # Snowflake uses GENERATOR with DATEADD
        # We generate more rows than needed and filter
        base = (
            f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), DATE {SPINE_MIN_DATE})) AS {alias} "
            f"FROM TABLE(GENERATOR(ROWCOUNT => 100000)) "
            f"WHERE DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), DATE {SPINE_MIN_DATE})) <= {SPINE_MAX_DATE}"
        )
        if where_sql:
            # Append additional filter conditions
            # Replace WHERE with AND since we already have a WHERE
            additional = where_sql.replace("WHERE ", " AND ", 1)
            return f"{base}{additional}{null_union}"
        return f"{base}{null_union}"
    
    # Default: use postgres-style
    base = (
        f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
        f"FROM generate_series({SPINE_MIN_DATE}::date, {SPINE_MAX_DATE}::date, INTERVAL '{interval}') AS d"
    )
    if where_sql:
        return f"{base} {where_sql}{null_union}"
    return f"{base}{null_union}"


def _apply_auto_spine(
    stmt: exp.Expression,
    settings: CompileSettings,
    dialect: Optional[str] = None,
) -> exp.Expression:
    """Apply auto-spine transformation to ALL GROUP BY columns.
    
    Unified approach:
    1. For each GROUP BY column, extract relevant WHERE predicates
    2. Build spine CTE with those predicates as filters
    3. LEFT JOIN aggregated data with spine
    """
    if not settings.auto_spine:
        return stmt

    if not isinstance(stmt, exp.Select):
        return stmt

    has_rollup, has_cube, rollup_cube_columns = _detect_rollup_cube(stmt)

    group_cols = _get_all_group_by_columns(stmt)
    if not group_cols:
        return stmt

    from_clause = stmt.find(exp.From)
    if not from_clause:
        return stmt
    source_table = from_clause.this.sql()

    where_clause = stmt.find(exp.Where)

    # spine_ctes: (cte_name, cte_select, metadata_dict)
    # metadata includes: is_date, trunc_unit, explicit_values, source_column for comment generation
    spine_ctes: List[Tuple[str, exp.Expression, dict]] = []
    # spine_columns: (alias, cte_name, original_expr_sql)
    spine_columns: List[Tuple[str, str, str]] = []
    rollup_column_order: List[str] = []
    # Track if any spine needs data bounds (affects CTE ordering)
    any_spine_needs_data_bounds = False

    for alias, group_expr, is_date, trunc_unit, explicit_values, source_column in group_cols:
        # Get the original expression SQL for matching SELECT expressions
        if isinstance(group_expr, exp.Alias):
            original_expr_sql = group_expr.this.sql()
        else:
            original_expr_sql = group_expr.sql()
        spine_cte_name = f"{alias}_spine"

        is_in_rollup_cube = alias in rollup_cube_columns or alias.lower() in [c.lower() for c in rollup_cube_columns]
        if is_in_rollup_cube and has_rollup:
            rollup_column_order.append(alias)

        # Extract predicates for this column from WHERE clause
        safe_predicates: List[exp.Expression] = []
        unsafe_predicates: List[exp.Expression] = []
        all_predicates: List[exp.Expression] = []
        has_unsafe_predicates = False
        
        if source_column and where_clause:
            safe_predicates, unsafe_predicates = _extract_predicates_for_column(where_clause, source_column)
            all_predicates = safe_predicates + unsafe_predicates
            has_unsafe_predicates = len(unsafe_predicates) > 0
        
        # For date spines with unsafe predicates, we need data CTE to be defined first
        # We'll use a two-pass approach: first collect info, then generate in correct order
        needs_data_bounds = is_date and has_unsafe_predicates and trunc_unit is not None
        if needs_data_bounds:
            any_spine_needs_data_bounds = True

        # Build unified spine SQL
        spine_sql = _build_spine_cte_sql(
            alias=alias,
            is_date=is_date,
            trunc_unit=trunc_unit,
            explicit_values=explicit_values,
            source_column=source_column,
            source_table=source_table,
            safe_predicates=safe_predicates,
            all_predicates=all_predicates,
            has_unsafe_predicates=has_unsafe_predicates,
            dialect=dialect,
            include_null=is_in_rollup_cube,
            use_data_bounds=needs_data_bounds,
            data_cte_name="spine_data" if needs_data_bounds else None,
        )

        try:
            spine_select = sqlglot.parse_one(spine_sql.strip(), dialect=dialect)
            # Store metadata for comment generation
            spine_metadata = {
                "alias": alias,
                "is_date": is_date,
                "trunc_unit": trunc_unit,
                "explicit_values": explicit_values,
                "source_column": source_column,
                "source_table": source_table,
                "needs_data_bounds": needs_data_bounds,
            }
            spine_ctes.append((spine_cte_name, spine_select, spine_metadata))
            spine_columns.append((alias, spine_cte_name, original_expr_sql))
        except Exception as e:
            raise ASQLCompilationError(
                f"Failed to generate spine for GROUP BY column '{alias}'. "
                f"Generated SQL: {spine_sql}\nError: {e}"
            ) from e

    if not spine_ctes:
        return stmt

    # For single GROUP BY, use the spine CTE directly instead of creating a redundant combined_spine
    use_combined_spine = len(spine_columns) > 1 or (has_rollup and len(rollup_column_order) > 1)

    if use_combined_spine:
        combined_spine_name = "combined_spine"
        selects = [f"{cte_name}.{alias}" for alias, cte_name, _ in spine_columns]
        froms = [spine_columns[0][1]]
        for _, cte_name, _ in spine_columns[1:]:
            froms.append(f"CROSS JOIN {cte_name}")
        combined_spine_sql = f"SELECT {', '.join(selects)} FROM {' '.join(froms)}"

        if has_rollup and len(rollup_column_order) > 1:
            rollup_filter_conditions: List[str] = []
            for i in range(len(rollup_column_order) - 1):
                col_curr = rollup_column_order[i]
                col_next = rollup_column_order[i + 1]
                curr_cte = next((cte for a, cte, _ in spine_columns if a == col_curr), None)
                next_cte = next((cte for a, cte, _ in spine_columns if a == col_next), None)
                if curr_cte and next_cte:
                    rollup_filter_conditions.append(
                        f"({curr_cte}.{col_curr} IS NOT NULL OR {next_cte}.{col_next} IS NULL)"
                    )

            if rollup_filter_conditions:
                combined_spine_sql += f" WHERE {' AND '.join(rollup_filter_conditions)}"
    else:
        # Single GROUP BY: use the spine CTE name directly
        combined_spine_name = spine_columns[0][1]
        combined_spine_sql = None  # Not needed

    data_cte_name = "spine_data"
    join_conditions = [f"{combined_spine_name}.{alias} = {data_cte_name}.{alias}" for alias, _, _ in spine_columns]

    select_cols: List[str] = []
    for sel_expr in stmt.expressions:
        # Handle SELECT * - just pass through without COALESCE wrapping
        if isinstance(sel_expr, exp.Star):
            select_cols.append(f"{data_cte_name}.*")
            continue

        if isinstance(sel_expr, exp.Alias):
            col_name = sel_expr.alias
            expr_sql = sel_expr.this.sql()
        elif isinstance(sel_expr, exp.Column):
            col_name = sel_expr.name
            expr_sql = sel_expr.sql()
        else:
            col_name = sel_expr.sql()
            expr_sql = col_name

        # Match against both alias and original expression SQL
        matched_alias = None
        for alias, _, orig_expr_sql in spine_columns:
            if col_name == alias or expr_sql == orig_expr_sql:
                matched_alias = alias
                break

        if matched_alias:
            select_cols.append(f"{combined_spine_name}.{matched_alias}")
        else:
            # Check if col_name is a valid SQL identifier (alphanumeric + underscore)
            # If not (e.g., function calls), we need to alias it properly
            safe_alias = col_name
            if not col_name.replace("_", "").isalnum() or col_name[0].isdigit() if col_name else False:
                # Use a sanitized alias for complex expressions
                safe_alias = f"col_{len(select_cols)}"
            select_cols.append(f"COALESCE({data_cte_name}.{col_name}, 0) AS {safe_alias}")

    if not select_cols:
        select_cols = [f"{combined_spine_name}.*"]

    final_sql = (
        f"SELECT {', '.join(select_cols)} "
        f"FROM {combined_spine_name} "
        f"LEFT JOIN {data_cte_name} ON {' AND '.join(join_conditions)}"
    )

    try:
        sqlglot.parse_one(final_sql.strip(), dialect=dialect)
    except Exception as e:
        raise ASQLCompilationError(
            f"Failed to generate spine join query. "
            f"Generated SQL: {final_sql}\nError: {e}"
        ) from e

    # Add aliases to the data CTE's SELECT expressions for GROUP BY columns
    # This ensures the join can reference them by the spine's alias
    data_stmt = stmt.copy()
    expr_to_alias = {orig_sql: alias for alias, _, orig_sql in spine_columns}

    new_expressions = []
    for sel_expr in data_stmt.expressions:
        if isinstance(sel_expr, exp.Alias):
            inner_expr = sel_expr.this
            original_alias = sel_expr.alias
        else:
            inner_expr = sel_expr
            original_alias = None

        # Check if this is a guarantee-wrapped expression
        is_guarantee, _ = _is_guarantee_wrapped(sel_expr)
        unwrapped_expr = inner_expr
        if is_guarantee:
            # Get the inner expression (unwrap guarantee)
            if isinstance(inner_expr, exp.Anonymous) and inner_expr.name and inner_expr.name.lower() == "guarantee":
                unwrapped_expr = inner_expr.expressions[0] if inner_expr.expressions else inner_expr

        unwrapped_sql = unwrapped_expr.sql()

        if unwrapped_sql in expr_to_alias:
            # Use the spine's alias for this expression
            new_expressions.append(exp.Alias(this=unwrapped_expr, alias=exp.to_identifier(expr_to_alias[unwrapped_sql])))
        elif is_guarantee:
            # guarantee expression not in spine - still unwrap and use original alias if present
            if original_alias:
                new_expressions.append(exp.Alias(this=unwrapped_expr, alias=exp.to_identifier(original_alias)))
            else:
                new_expressions.append(unwrapped_expr)
        else:
            new_expressions.append(sel_expr)

    data_stmt.set("expressions", new_expressions)

    cte_parts: List[str] = []
    # Track CTE names and their comments for adding after parsing
    # Only generate comments if include_transpilation_comments is enabled
    include_comments = settings.include_transpilation_comments if settings else False
    cte_comments: dict[str, str] = {}

    # When any spine needs data bounds, the data CTE must come FIRST
    # (because the spine references MIN/MAX from the data CTE)
    if any_spine_needs_data_bounds:
        cte_parts.append(f"{data_cte_name} AS ({data_stmt.sql(dialect=dialect)})")
        if include_comments:
            cte_comments[data_cte_name] = "Original aggregation query - data CTE defined first for MIN/MAX bounds"

    for cte_name, cte_select, metadata in spine_ctes:
        cte_parts.append(f"{cte_name} AS ({cte_select.sql(dialect=dialect)})")
        if include_comments:
            cte_comments[cte_name] = _generate_spine_comment(metadata)

    # Only add combined_spine CTE when we have multiple GROUP BY columns or rollup
    if combined_spine_sql is not None:
        cte_parts.append(f"{combined_spine_name} AS ({combined_spine_sql})")
        if include_comments:
            cte_comments[combined_spine_name] = "Cross-join of all spine dimensions to ensure every combination appears"
    
    # If data CTE wasn't added first, add it now (normal case)
    if not any_spine_needs_data_bounds:
        cte_parts.append(f"{data_cte_name} AS ({data_stmt.sql(dialect=dialect)})")
        if include_comments:
            cte_comments[data_cte_name] = "Original aggregation query"

    result_sql = "WITH " + ", ".join(cte_parts) + " " + final_sql
    try:
        result_stmt = sqlglot.parse_one(result_sql.strip(), dialect=dialect)
        
        # Add comments inside each CTE (before the SELECT) if comments are enabled
        if include_comments and cte_comments:
            for cte_node in result_stmt.find_all(exp.CTE):
                cte_name = cte_node.alias
                if cte_name in cte_comments:
                    # Add comment to the inner SELECT statement, not the CTE wrapper
                    inner_select = cte_node.this
                    if inner_select:
                        existing = inner_select.comments or []
                        inner_select.comments = [cte_comments[cte_name]] + existing
        
        # Preserve original statement's comments (passthrough)
        if stmt.comments:
            # Prepend original comments to the result statement's comments
            existing_comments = result_stmt.comments or []
            result_stmt.comments = list(stmt.comments) + existing_comments
        
        return result_stmt
    except Exception as e:
        raise ASQLCompilationError(
            f"Failed to assemble spine query. "
            f"Generated SQL: {result_sql}\nError: {e}"
        ) from e


# Legacy function exports for backwards compatibility with tests
def _find_non_date_group_by_columns(stmt: exp.Expression) -> List[Tuple[str, exp.Expression]]:
    """Find non-date columns in GROUP BY that need cross-join with distinct values."""
    results: List[Tuple[str, exp.Expression]] = []

    if not isinstance(stmt, exp.Select):
        return results

    group_by = stmt.find(exp.Group)
    if not group_by:
        return results

    for group_expr in group_by.expressions:
        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
            inner = group_expr.this
        else:
            inner = group_expr
            alias = inner.name if isinstance(inner, exp.Column) else None

        is_guarantee, _ = _is_guarantee_wrapped(group_expr)
        if is_guarantee:
            continue

        func_name = None
        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, "sql_name") else type(inner).__name__.lower()

        if func_name not in DATE_TRUNC_FUNCTIONS and alias:
            results.append((alias, group_expr))

    return results


def _find_date_trunc_in_group_by(
    stmt: exp.Expression,
) -> List[Tuple[str, str, exp.Expression, Optional[List[str]]]]:
    """Find date truncation expressions in GROUP BY clause."""
    results: List[Tuple[str, str, exp.Expression, Optional[List[str]]]] = []

    if not isinstance(stmt, exp.Select):
        return results

    group_by = stmt.find(exp.Group)
    if not group_by:
        return results

    for group_expr in group_by.expressions:
        func_name = None
        trunc_unit = None
        alias = None
        explicit_values = None

        is_guarantee, values = _is_guarantee_wrapped(group_expr)
        if is_guarantee:
            explicit_values = values

        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
            inner = group_expr.this
            if is_guarantee and isinstance(inner, exp.Anonymous):
                inner = inner.expressions[0] if inner.expressions else inner
        else:
            inner = group_expr
            if is_guarantee and isinstance(inner, exp.Anonymous):
                inner = inner.expressions[0] if inner.expressions else inner
            if isinstance(inner, exp.Column):
                alias = inner.name
            elif hasattr(inner, "alias") and inner.alias:
                alias = inner.alias

        if isinstance(inner, exp.Anonymous):
            func_name = inner.name.lower() if inner.name else None
        elif isinstance(inner, exp.Func):
            func_name = inner.sql_name().lower() if hasattr(inner, "sql_name") else type(inner).__name__.lower()

        if func_name in DATE_TRUNC_FUNCTIONS:
            if func_name == "date_trunc":
                if inner.expressions:
                    unit_arg = inner.expressions[0]
                    if isinstance(unit_arg, exp.Literal):
                        trunc_unit = unit_arg.this.strip("'\"").lower()
            else:
                trunc_unit = func_name

            if trunc_unit and alias:
                results.append((alias, trunc_unit, group_expr, explicit_values))

    return results


def _find_guarantee_in_group_by(
    stmt: exp.Expression,
) -> List[Tuple[str, exp.Expression, Optional[List[str]]]]:
    """Find guarantee() expressions in GROUP BY clause for categorical columns."""
    results: List[Tuple[str, exp.Expression, Optional[List[str]]]] = []

    if not isinstance(stmt, exp.Select):
        return results

    group_by = stmt.find(exp.Group)
    if not group_by:
        return results

    for group_expr in group_by.expressions:
        is_guarantee, explicit_values = _is_guarantee_wrapped(group_expr)
        if not is_guarantee:
            continue

        alias = None
        if isinstance(group_expr, exp.Alias):
            alias = group_expr.alias
        else:
            inner = group_expr
            if isinstance(inner, exp.Anonymous) and inner.expressions:
                first_arg = inner.expressions[0]
                if isinstance(first_arg, exp.Column):
                    alias = first_arg.name

        if alias:
            results.append((alias, group_expr, explicit_values))

    return results


# Legacy exports - keep for backwards compatibility
def _build_categorical_spine_sql(
    alias: str,
    values: List[str],
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a categorical spine with explicit values."""
    return _build_explicit_values_spine_sql(alias, values, dialect, include_null)


def _build_date_spine_sql(
    alias: str,
    trunc_unit: str,
    min_date: str,
    max_date: str,
    interval: str,
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a date spine with explicit bounds (legacy)."""
    # This is kept for backwards compatibility but the new approach
    # uses _build_date_spine_with_filter_sql instead
    dialect_lower = dialect.lower() if dialect else ""
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""

    if dialect_lower in ("postgres", "postgresql", "redshift"):
        return (
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d"
        ) + null_union
    if dialect_lower == "bigquery":
        return (
            f"SELECT DATE_TRUNC(d, {trunc_unit.upper()}) AS {alias} "
            f"FROM UNNEST(GENERATE_DATE_ARRAY({min_date}, {max_date})) AS d"
        ) + null_union
    if dialect_lower == "snowflake":
        return (
            f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), {min_date})) AS {alias} "
            f"FROM TABLE(GENERATOR(ROWCOUNT => 10000)) "
            f"WHERE DATE_TRUNC('{trunc_unit}', DATEADD({trunc_unit}, SEQ4(), {min_date})) <= {max_date}"
        ) + null_union
    if dialect_lower == "duckdb":
        return (
            f"SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias} "
            f"FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS t(d)"
        ) + null_union

    return (
        f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
        f"FROM generate_series({min_date}::date, {max_date}::date, INTERVAL '{interval}') AS d"
    ) + null_union


def _columns_match(expr1: exp.Expression, expr2: exp.Expression) -> bool:
    """Check if two expressions refer to the same column (legacy)."""
    if isinstance(expr1, exp.Column) and isinstance(expr2, exp.Column):
        return expr1.name == expr2.name
    return expr1.sql() == expr2.sql()


def _extract_date_bounds_from_where(
    stmt: exp.Expression,
    column_expr: exp.Expression,
) -> Tuple[Optional[str], Optional[str]]:
    """Extract date bounds from WHERE clause for a given column expression (legacy).
    
    Note: The new unified approach doesn't use this function - it copies
    predicates directly instead of extracting bounds. This is kept for
    backwards compatibility.
    """
    where = stmt.find(exp.Where)
    if not where:
        return None, None

    min_date: Optional[str] = None
    max_date: Optional[str] = None

    def check_condition(node: exp.Expression) -> None:
        nonlocal min_date, max_date

        if isinstance(node, (exp.GTE, exp.GT)):
            if _columns_match(node.this, column_expr) and isinstance(node.expression, (exp.Literal, exp.Cast)):
                min_date = node.expression.sql()
        elif isinstance(node, (exp.LTE, exp.LT)):
            if _columns_match(node.this, column_expr) and isinstance(node.expression, (exp.Literal, exp.Cast)):
                max_date = node.expression.sql()
        elif isinstance(node, exp.Between):
            if _columns_match(node.this, column_expr):
                low = node.args.get("low")
                high = node.args.get("high")
                if isinstance(low, (exp.Literal, exp.Cast)):
                    min_date = low.sql()
                if isinstance(high, (exp.Literal, exp.Cast)):
                    max_date = high.sql()
        elif isinstance(node, exp.And):
            check_condition(node.this)
            check_condition(node.expression)

    check_condition(where.this)
    return min_date, max_date


def _build_date_spine_from_data_sql(
    alias: str,
    trunc_unit: str,
    col_expr: str,
    source_table: str,
    where_sql: str,
    interval: str,
    dialect: Optional[str] = None,
    include_null: bool = False,
) -> str:
    """Build SQL for a date spine derived from data MIN/MAX (legacy)."""
    # This is kept for backwards compatibility
    dialect_lower = dialect.lower() if dialect else ""
    null_union = f" UNION ALL SELECT NULL AS {alias}" if include_null else ""

    if dialect_lower in ("postgres", "postgresql", "redshift"):
        return (
            f"WITH bounds AS (SELECT MIN({col_expr}) as min_d, MAX({col_expr}) as max_d FROM {source_table} {where_sql}) "
            f"SELECT DATE_TRUNC('{trunc_unit}', d::date) AS {alias} "
            f"FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS d"
        ) + null_union
    if dialect_lower == "duckdb":
        return (
            f"WITH bounds AS (SELECT MIN({col_expr}) as min_d, MAX({col_expr}) as max_d FROM {source_table} {where_sql}) "
            f"SELECT DATE_TRUNC('{trunc_unit}', d) AS {alias} "
            f"FROM bounds, generate_series(min_d::date, max_d::date, INTERVAL '{interval}') AS t(d)"
        ) + null_union

    return (
        f"SELECT DISTINCT DATE_TRUNC('{trunc_unit}', {col_expr}) AS {alias} FROM {source_table} {where_sql}"
    ) + null_union
