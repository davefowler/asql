"""Spine transformation for explicit spine() expressions.

This module processes exp.Spine nodes in GROUP BY clauses and generates
gap-filling CTEs. It replaces the auto-detection approach with explicit
spine marking.

Usage:
    from orders spine by month(created_at) (sum(amount))
    from orders group by spine(month(created_at)), region (sum(amount))

Both syntaxes create Spine() wrapped columns in GROUP BY, which this
module processes to generate gap-filling CTEs.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import sqlglot
from sqlglot import exp

from asql.config import CompileSettings
from asql.expressions import Spine

# Import helpers from spine_helpers
from asql.compiler.spine_helpers import (
    DATE_TRUNC_FUNCTIONS,
    TRUNC_TO_INTERVAL,
    _generate_spine_comment,
    _detect_rollup_cube,
    _get_source_column_from_trunc,
    _build_date_spine_sql,
    _build_date_spine_from_data_sql,
    _build_distinct_values_spine_sql,
    _extract_date_bounds_from_where,
)

logger = logging.getLogger(__name__)


def transform_spine_expressions(
    stmt: exp.Expression,
    dialect: str,
    settings: CompileSettings,
) -> exp.Expression:
    """Transform Spine() expressions into gap-filling CTEs.
    
    Finds Spine(column) expressions in GROUP BY and generates:
    1. Date spine CTE (for date truncation columns)
    2. Categorical spine CTE (for other columns)
    3. LEFT JOIN to ensure all values appear in output
    
    Args:
        stmt: SQLGlot expression (typically a SELECT)
        dialect: Target SQL dialect (for generate_series syntax)
        settings: Compile settings (for comments, etc.)
    
    Returns:
        Transformed expression with spine CTEs
    """
    if not isinstance(stmt, exp.Select):
        return stmt
    
    # Find Spine expressions in GROUP BY
    spine_columns = _find_spine_columns(stmt)
    if not spine_columns:
        return stmt
    
    # Check for ROLLUP/CUBE which we can't spine
    has_rollup, has_cube, _ = _detect_rollup_cube(stmt)
    if has_rollup or has_cube:
        logger.warning("Spine not supported with ROLLUP/CUBE - skipping")
        return _unwrap_spine_expressions(stmt)
    
    # Build spine CTEs and transform query
    return _apply_spine_transform(stmt, spine_columns, dialect, settings)


def _find_spine_columns(
    stmt: exp.Expression,
) -> List[Tuple[str, exp.Expression, Optional[str], bool]]:
    """Find Spine() expressions in GROUP BY.
    
    Returns list of tuples: (alias, inner_expr, trunc_unit, is_date)
    """
    results: List[Tuple[str, exp.Expression, Optional[str], bool]] = []
    
    group_by = stmt.find(exp.Group)
    if not group_by:
        return results
    
    for i, group_expr in enumerate(group_by.expressions):
        spine_node = None
        alias = None
        
        # Handle Spine directly or wrapped in Alias
        if isinstance(group_expr, Spine):
            spine_node = group_expr
            alias = f"spine_col_{i}"
        elif isinstance(group_expr, exp.Alias):
            if isinstance(group_expr.this, Spine):
                spine_node = group_expr.this
                alias = group_expr.alias
        
        if spine_node is None:
            continue
        
        # Extract the inner expression from Spine
        inner_expr = spine_node.this
        
        # Determine if this is a date truncation
        trunc_unit = _get_trunc_unit(inner_expr)
        is_date = trunc_unit is not None
        
        if alias is None:
            # Generate alias from inner expression
            if isinstance(inner_expr, exp.Column):
                alias = inner_expr.name
            elif isinstance(inner_expr, exp.Alias):
                alias = inner_expr.alias
            else:
                alias = f"spine_col_{i}"
        
        results.append((alias, inner_expr, trunc_unit, is_date))
    
    return results


def _get_trunc_unit(expr: exp.Expression) -> Optional[str]:
    """Get the truncation unit if expr is a date truncation function."""
    # Check for direct date type expressions
    date_type_map = {
        exp.Month: "month",
        exp.Week: "week",
        exp.Day: "day",
        exp.Year: "year",
        exp.Quarter: "quarter",
        exp.Hour: "hour",
    }
    
    for date_type, unit in date_type_map.items():
        if isinstance(expr, date_type):
            return unit
    
    # Check for Anonymous function calls
    if isinstance(expr, exp.Anonymous):
        func_name = expr.name.lower() if expr.name else ""
        if func_name in DATE_TRUNC_FUNCTIONS:
            if func_name == "date_trunc":
                # DATE_TRUNC('month', col) - get unit from first arg
                if expr.expressions:
                    first_arg = expr.expressions[0]
                    if isinstance(first_arg, exp.Literal):
                        return first_arg.this.lower()
            else:
                return func_name
    
    # Check for DateTrunc expression
    if isinstance(expr, exp.DateTrunc):
        unit = expr.args.get("unit")
        if isinstance(unit, exp.Literal):
            return unit.this.lower()
    
    return None


def _unwrap_spine_expressions(stmt: exp.Expression) -> exp.Expression:
    """Remove Spine wrappers from GROUP BY, keeping inner expressions."""
    if not isinstance(stmt, exp.Select):
        return stmt
    
    group = stmt.find(exp.Group)
    if not group:
        return stmt
    
    new_exprs = []
    for expr in group.expressions:
        if isinstance(expr, Spine):
            new_exprs.append(expr.this)
        elif isinstance(expr, exp.Alias) and isinstance(expr.this, Spine):
            # Preserve alias but unwrap Spine
            new_exprs.append(exp.Alias(this=expr.this.this, alias=expr.alias))
        else:
            new_exprs.append(expr)
    
    group.set("expressions", new_exprs)
    return stmt


def _apply_spine_transform(
    stmt: exp.Select,
    spine_columns: List[Tuple[str, exp.Expression, Optional[str], bool]],
    dialect: str,
    settings: CompileSettings,
) -> exp.Expression:
    """Apply spine transformation to the statement.
    
    This is a simplified version that handles the most common cases.
    For complex queries, we delegate to the existing auto_spine machinery.
    """
    
    # Get existing CTEs
    existing_ctes = []
    with_clause = stmt.args.get("with_")
    if with_clause:
        existing_ctes = list(with_clause.expressions)
    
    spine_ctes = []
    spine_aliases = []
    
    # Get the source table for categorical spines
    from_clause = stmt.find(exp.From)
    source_table = ""
    if from_clause and isinstance(from_clause.this, exp.Table):
        source_table = from_clause.this.name
    
    # Extract WHERE bounds for date spines
    where_clause = stmt.find(exp.Where)
    
    for alias, inner_expr, trunc_unit, is_date in spine_columns:
        spine_alias = f"{alias}_spine"
        spine_aliases.append((alias, spine_alias, inner_expr))
        
        if is_date and trunc_unit:
            # Generate date spine CTE
            source_col = _get_source_column_from_trunc(inner_expr)
            source_col_name = source_col.name if isinstance(source_col, exp.Column) else None
            
            # Get interval for this truncation unit
            interval = TRUNC_TO_INTERVAL.get(trunc_unit, "1 day")
            
            # Try to extract bounds from WHERE
            min_date, max_date = None, None
            if where_clause and source_col_name:
                # Convert string column name to exp.Column for comparison
                source_col_expr = exp.Column(this=exp.to_identifier(source_col_name))
                min_date, max_date = _extract_date_bounds_from_where(
                    stmt, source_col_expr
                )
            
            # Build date spine SQL
            # Note: signature is (alias, trunc_unit, min_date, max_date, interval, dialect)
            if min_date and max_date:
                spine_sql = _build_date_spine_sql(
                    alias, trunc_unit, min_date, max_date, interval, dialect
                )
            else:
                # Use data-based bounds
                # signature is (alias, trunc_unit, col_expr, source_table, where_sql, interval, dialect)
                col_expr = source_col_name or alias
                # where_sql should be a full WHERE clause like "WHERE x >= y"
                # Add null check for where_clause.this to handle malformed WHERE clauses
                if where_clause and where_clause.this is not None:
                    where_sql = f"WHERE {where_clause.this.sql()}"
                else:
                    where_sql = ""
                spine_sql = _build_date_spine_from_data_sql(
                    alias, trunc_unit, col_expr, source_table,
                    where_sql, interval, dialect
                )
            
            # Parse the spine SQL into an expression
            try:
                spine_select = sqlglot.parse_one(spine_sql, dialect=dialect)
                
                # Add comment if enabled
                if settings.include_transpilation_comments:
                    comment = _generate_spine_comment({
                        "alias": alias,
                        "is_date": True,
                        "trunc_unit": trunc_unit,
                        "source_column": source_col_name,
                        "source_table": source_table,
                        "needs_data_bounds": min_date is None,
                    })
                    spine_select.add_comments([comment])
                
                spine_cte = exp.CTE(
                    this=spine_select,
                    alias=exp.TableAlias(this=exp.to_identifier(spine_alias)),
                )
                spine_ctes.append(spine_cte)
            except Exception as e:
                # Log at ERROR level with context to help debugging
                logger.error(
                    f"Failed to generate date spine CTE for column '{alias}' "
                    f"(trunc_unit={trunc_unit}, table={source_table}): {e}. "
                    f"Generated SQL was: {spine_sql[:200]}..."
                )
                continue
        else:
            # Generate categorical spine CTE (SELECT DISTINCT from table)
            col_expr = inner_expr.sql() if inner_expr else alias
            # Add null check for where_clause.this
            if where_clause and where_clause.this is not None:
                where_sql = f"WHERE {where_clause.this.sql()}"
            else:
                where_sql = ""
            spine_sql = _build_distinct_values_spine_sql(
                alias, source_table, col_expr, where_sql, dialect
            )
            
            try:
                spine_select = sqlglot.parse_one(spine_sql, dialect=dialect)
                
                if settings.include_transpilation_comments:
                    comment = _generate_spine_comment({
                        "alias": alias,
                        "is_date": False,
                        "source_column": inner_expr.sql() if inner_expr else alias,
                        "source_table": source_table,
                    })
                    spine_select.add_comments([comment])
                
                spine_cte = exp.CTE(
                    this=spine_select,
                    alias=exp.TableAlias(this=exp.to_identifier(spine_alias)),
                )
                spine_ctes.append(spine_cte)
            except Exception as e:
                # Log at ERROR level with context
                logger.error(
                    f"Failed to generate categorical spine CTE for column '{alias}' "
                    f"(table={source_table}): {e}. "
                    f"Generated SQL was: {spine_sql[:200]}..."
                )
                continue
    
    if not spine_ctes:
        return _unwrap_spine_expressions(stmt)
    
    # Combine CTEs
    all_ctes = existing_ctes + spine_ctes
    
    # Create new WITH clause, preserving recursive flag from original
    recursive = with_clause.args.get("recursive") if with_clause else False
    new_with = exp.With(expressions=all_ctes, recursive=recursive)
    
    # Update the statement
    stmt.set("with_", new_with)
    
    # Unwrap Spine expressions in GROUP BY (keep inner expressions)
    stmt = _unwrap_spine_expressions(stmt)
    
    # Add JOINs to spine CTEs
    for alias, spine_alias, inner_expr in spine_aliases:
        spine_table = exp.Table(this=exp.to_identifier(spine_alias))
        
        # Build join condition: spine_alias.alias = inner_expr
        spine_col = exp.Column(
            this=exp.to_identifier(alias),
            table=exp.to_identifier(spine_alias)
        )
        
        join_condition = exp.EQ(this=spine_col, expression=inner_expr.copy())
        
        join = exp.Join(
            this=spine_table,
            on=join_condition,
            kind="LEFT",
        )
        
        # Add join to statement
        joins = stmt.args.get("joins") or []
        joins.append(join)
        stmt.set("joins", joins)
    
    return stmt
