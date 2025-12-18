"""ASQL reverse compiler - transforms SQL to ASQL."""

import re
from typing import Optional, List, TYPE_CHECKING
import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect, Dialects

from asql.errors import ASQLCompilationError

if TYPE_CHECKING:
    from asql.config import ASQLConfig, StyleConfig


def _get_dialect_names() -> List[str]:
    """Get all available dialect names from sqlglot, with common ones first.
    
    Returns dialect names sorted with common/popular dialects first for
    faster detection in typical use cases.
    """
    # Common dialects to prioritize (these are tried first)
    priority_dialects = ['snowflake', 'bigquery', 'postgres', 'redshift', 'mysql', 'spark', 'duckdb']
    
    # Get all dialect names from the Dialects enum
    all_dialects = [d.value for d in Dialects if d.value]  # Skip empty string (DIALECT)
    
    # Return priority dialects first, then the rest (avoiding duplicates)
    result = priority_dialects.copy()
    for d in all_dialects:
        if d not in result:
            result.append(d)
    
    return result


def detect_dialect(sql_query: str) -> Optional[str]:
    """
    Detect SQL dialect from a SQL query string.
    
    Args:
        sql_query: SQL query string
        
    Returns:
        Detected dialect name (e.g., 'bigquery', 'redshift', 'postgres') or None
    """
    if not sql_query.strip():
        return None
    
    # Skip detection if Jinja templates are present (they'll cause parse errors)
    if "{{" in sql_query or "{%" in sql_query:
        return None
    
    # Try parsing with different dialects and see which one works best
    dialects_to_try = _get_dialect_names()
    
    best_dialect = None
    best_score = 0
    
    for dialect_name in dialects_to_try:
        try:
            dialect = Dialect.get_or_raise(dialect_name)
            parsed = sqlglot.parse(sql_query, dialect=dialect)
            if parsed:
                # Simple heuristic: if it parses without errors, it might be this dialect
                # We could add more sophisticated detection here
                score = len(parsed)
                if score > best_score:
                    best_score = score
                    best_dialect = dialect_name
        except sqlglot.errors.ParseError:
            # This dialect can't parse the query, try the next one
            continue
    
    # Also try generic parsing
    try:
        parsed = sqlglot.parse(sql_query)
        if parsed and not best_dialect:
            # If generic parsing works, return None (unknown/ansi)
            return None
    except sqlglot.errors.ParseError:
        pass
    
    return best_dialect


def reverse_compile(
    sql_query: str,
    source_dialect: Optional[str] = None,
    config: Optional["ASQLConfig"] = None,
) -> str:
    """
    Compile SQL query to ASQL.
    
    Args:
        sql_query: SQL query string
        source_dialect: Source SQL dialect (e.g., 'bigquery', 'redshift')
                       If None, will attempt auto-detection
        config: ASQL configuration for output style. If None, uses defaults.
    
    Returns:
        ASQL query string
    
    Raises:
        ASQLCompilationError: If compilation fails
    """
    try:
        if not sql_query.strip():
            raise ASQLCompilationError("Empty SQL query")
        
        # Get style config
        if config is None:
            from asql.config import ASQLConfig
            config = ASQLConfig()
        style = config.style
        
        # Check for dbt/Jinja templating syntax
        if "{{" in sql_query or "{%" in sql_query:
            raise ASQLCompilationError(
                "SQL contains dbt/Jinja templating syntax ({{ ... }} or {% ... %}). "
                "Please remove Jinja templates before parsing. "
                "Replace {{ ref('table') }} with the actual table name, "
                "and remove {% if %} / {% endif %} blocks."
            )
        
        # Auto-detect dialect if not provided
        if not source_dialect:
            source_dialect = detect_dialect(sql_query)
        
        # Parse SQL to AST - try multiple dialects if one fails
        expressions = None
        parse_error = None
        
        # List of dialects to try (in order of preference)
        dialects_to_try = []
        if source_dialect:
            dialects_to_try.append(source_dialect)
        # Add all known dialects as fallbacks (common ones first)
        for d in _get_dialect_names():
            if d not in dialects_to_try:
                dialects_to_try.append(d)
        
        for dialect_name in dialects_to_try:
            try:
                dialect = Dialect.get_or_raise(dialect_name)
                expressions = sqlglot.parse(sql_query, dialect=dialect)
                if expressions:
                    # Successfully parsed, use this dialect
                    break
            except Exception as e:
                # Try next dialect
                parse_error = e
                continue
        
        # If all dialects failed, try generic parsing
        if not expressions:
            try:
                expressions = sqlglot.parse(sql_query)
            except Exception as e:
                parse_error = e
        
        if not expressions:
            error_msg = "Failed to parse SQL query"
            if parse_error:
                error_msg = f"Failed to parse SQL query: {str(parse_error)}"
            raise ASQLCompilationError(error_msg)
        
        # Convert each expression to ASQL
        asql_parts = []
        for expr in expressions:
            if isinstance(expr, exp.Select):
                asql = _select_to_asql(expr, style)
                asql_parts.append(asql)
            elif isinstance(expr, exp.Create):
                # Handle CREATE TABLE, etc.
                raise ASQLCompilationError("CREATE statements are not supported in ASQL")
            else:
                # Try to convert other expression types
                asql_parts.append(str(expr))
        
        # Join ASQL parts (no dialect comment needed - dialect info is in UI)
        result = "\n".join(asql_parts)
        
        return result
        
    except sqlglot.errors.ParseError as e:
        error_msg = str(e)
        # Clean up error message - remove ANSI escape codes and file paths
        # Remove ANSI escape codes (e.g., [4m, [0m)
        error_msg = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
        # Remove file paths if present (common in error messages)
        error_msg = re.sub(r'[^\s]+\.sql\s+', '', error_msg)
        # Check if error mentions braces (likely Jinja template issue)
        if '{' in error_msg or 'L_BRACE' in error_msg:
            raise ASQLCompilationError(
                "SQL parse error: This query appears to contain dbt/Jinja templating syntax. "
                "Please remove Jinja templates ({{ ... }} or {% ... %}) before parsing. "
                f"Original error: {error_msg}"
            ) from e
        raise ASQLCompilationError(f"SQL parse error: {error_msg}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Reverse compilation error: {e}") from e


def _is_empty_cte(select_expr: exp.Select) -> bool:
    """Check if a SELECT is an empty pass-through (just SELECT * FROM table).
    
    Returns True if the SELECT is essentially just `SELECT * FROM table_name`
    with no WHERE, JOIN, GROUP BY, ORDER BY, LIMIT, or other clauses.
    """
    # Check for SELECT *
    select_exprs = select_expr.args.get("expressions", [])
    if not select_exprs:
        return False
    
    # Should be just Star
    if len(select_exprs) != 1:
        return False
    if not isinstance(select_exprs[0], exp.Star):
        return False
    
    # Should have FROM
    from_expr = select_expr.args.get("from_")
    if not from_expr:
        return False
    
    # Should NOT have any other clauses
    has_other_clauses = any([
        select_expr.args.get("where"),
        select_expr.args.get("group"),
        select_expr.args.get("having"),
        select_expr.args.get("order"),
        select_expr.args.get("limit"),
        select_expr.args.get("joins"),
        select_expr.args.get("distinct"),
        select_expr.args.get("qualify"),
        select_expr.args.get("windows"),
    ])
    
    return not has_other_clauses


def _get_cte_source_table(select_expr: exp.Select) -> Optional[str]:
    """Get the source table name from an empty CTE.
    
    For `SELECT * FROM table_name`, returns `table_name`.
    Returns None if not a simple table reference.
    """
    from_expr = select_expr.args.get("from_")
    if not from_expr:
        return None
    
    table = from_expr.this
    if isinstance(table, exp.Table):
        return table.this if isinstance(table.this, str) else str(table.this)
    elif isinstance(table, exp.Identifier):
        return table.this if isinstance(table.this, str) else str(table.this)
    
    return None


def _select_to_asql(select_expr: exp.Select, style: "StyleConfig" = None) -> str:
    """Convert a SQLGlot Select expression to ASQL."""
    if style is None:
        from asql.config import StyleConfig
        style = StyleConfig()
    
    parts = []
    
    # Track CTE name -> source table for empty CTEs (used for inlining)
    empty_cte_map = {}
    
    # Handle WITH/CTE clauses (sqlglot 28+ uses "with_")
    with_clause = select_expr.args.get("with_")
    if with_clause:
        ctes = []
        cte_list = []  # Keep track of (cte_name, cte_asql, is_empty) tuples
        
        # Process CTE expressions
        if hasattr(with_clause, 'expressions') and with_clause.expressions:
            for cte in with_clause.expressions:
                # Handle CTE alias - could be Identifier or string
                if cte.alias:
                    if isinstance(cte.alias, exp.Identifier):
                        cte_name = cte.alias.this
                    elif isinstance(cte.alias, str):
                        cte_name = cte.alias
                    else:
                        cte_name = str(cte.alias)
                else:
                    cte_name = None
                
                if cte_name and isinstance(cte.this, exp.Select):
                    is_empty = _is_empty_cte(cte.this)
                    source_table = _get_cte_source_table(cte.this) if is_empty else None
                    
                    # Track empty CTEs for potential inlining
                    if is_empty and source_table:
                        empty_cte_map[cte_name] = source_table
                    
                    try:
                        cte_asql = _select_to_asql(cte.this, style)
                        cte_list.append((cte_name, cte_asql, is_empty))
                    except ASQLCompilationError as cte_error:
                        # If a CTE can't be converted, include as comment
                        cte_sql = str(cte.this)
                        cte_list.append((cte_name, f"-- CTE '{cte_name}' could not be converted: {cte_error}\n-- Original: {cte_sql[:100]}...", False))
            
            # Apply squash_empty_ctes logic
            total_ctes = len(cte_list)
            for idx, (cte_name, cte_asql, is_empty) in enumerate(cte_list):
                is_last = (idx == total_ctes - 1)
                
                # Determine if we should include this CTE
                should_include = True
                if style.squash_empty_ctes and is_empty:
                    # Squash empty CTEs by default
                    if is_last and style.keep_final_empty_cte:
                        # But keep the final empty one if keep_final_empty_cte is True
                        should_include = True
                    else:
                        should_include = False
                
                if should_include:
                    ctes.append(f"{cte_asql}\nstash as {cte_name}")
        
        if ctes:
            parts.extend(ctes)
            parts.append("")  # Empty line between CTEs and main query
    
    # FROM clause (required in ASQL) - sqlglot 28+ uses "from_"
    from_expr = select_expr.args.get("from_")
    if not from_expr:
        # Check if this is a SELECT without FROM (e.g., SELECT 1, SELECT CURRENT_DATE)
        # These are valid SQL but can't be converted to ASQL
        select_exprs = select_expr.args.get("expressions", [])
        if select_exprs:
            # Return as a pass-through expression (e.g., for scalar queries)
            expr_strs = [_expression_to_asql(e, style) for e in select_exprs]
            return f"-- No FROM clause, cannot convert to ASQL: SELECT {', '.join(expr_strs)}"
        raise ASQLCompilationError("ASQL requires a FROM clause")
    
    table = from_expr.this
    if isinstance(table, exp.Table):
        table_name = table.this if isinstance(table.this, str) else str(table.this)
    elif isinstance(table, exp.Identifier):
        table_name = table.this if isinstance(table.this, str) else str(table.this)
    else:
        table_name = str(table)
    
    # If referencing a squashed empty CTE, inline the source table
    if style.squash_empty_ctes and table_name in empty_cte_map:
        table_name = empty_cte_map[table_name]
    
    parts.append(f"from {table_name}")
    
    # JOIN clauses
    joins = select_expr.args.get("joins", [])
    for join in joins:
        join_type = join.kind or "inner"
        join_table = join.this
        join_table_name = join_table.this if isinstance(join_table, exp.Table) else str(join_table)
        
        # If referencing a squashed empty CTE, inline the source table
        if style.squash_empty_ctes and join_table_name in empty_cte_map:
            join_table_name = empty_cte_map[join_table_name]
        
        on_condition = join.args.get("on")
        if on_condition:
            condition_str = _expression_to_asql(on_condition, style)
            parts.append(f"join {join_table_name} on {condition_str}")
        else:
            parts.append(f"join {join_table_name}")
    
    # WHERE clause
    where_expr = select_expr.args.get("where")
    if where_expr:
        condition = _expression_to_asql(where_expr.this, style)
        parts.append(f"where {condition}")
    
    # GROUP BY clause
    group_expr = select_expr.args.get("group")
    select_exprs = select_expr.args.get("expressions", [])
    
    if group_expr:
        group_cols = []
        for col in group_expr.expressions:
            group_cols.append(_expression_to_asql(col, style))
        
        # Get aggregations from SELECT expressions
        aggregations = []
        grouping_col_set = set()
        for col in group_expr.expressions:
            col_str = _expression_to_asql(col, style)
            grouping_col_set.add(col_str.lower())
        
        for expr in select_exprs:
            # Check if it's an aggregation
            if isinstance(expr, (exp.AggFunc, exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
                agg_str = _aggregation_to_asql(expr, style)
                aggregations.append(agg_str)
            # Check if it's an aliased aggregation
            elif isinstance(expr, exp.Alias) and isinstance(expr.this, (exp.AggFunc, exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
                agg_str = _aggregation_to_asql(expr, style)
                aggregations.append(agg_str)
        
        if aggregations:
            parts.append(f"group by {', '.join(group_cols)} ( {', '.join(aggregations)} )")
        else:
            parts.append(f"group by {', '.join(group_cols)}")
    
    # SELECT expressions (if not already handled by GROUP BY)
    # Only include non-aggregation, non-grouping columns
    if not group_expr:
        if select_exprs:
            select_parts = []
            for expr in select_exprs:
                if isinstance(expr, exp.Star):
                    # ASQL doesn't have explicit SELECT *, it's implicit
                    continue
                else:
                    select_str = _expression_to_asql(expr, style)
                    select_parts.append(select_str)
            if select_parts:
                parts.append(f"select {', '.join(select_parts)}")
    
    # ORDER BY clause
    order_expr = select_expr.args.get("order")
    if order_expr:
        order_parts = []
        for order in order_expr.expressions:
            expr_str = _expression_to_asql(order.this, style)
            desc = order.args.get("desc", False)
            if desc:
                if style.descending == "prefix":
                    order_parts.append(f"-{expr_str}")
                else:
                    order_parts.append(f"{expr_str} desc")
            else:
                order_parts.append(expr_str)
        
        parts.append(f"order by {', '.join(order_parts)}")
    
    # LIMIT clause
    limit_expr = select_expr.args.get("limit")
    if limit_expr:
        # SQLGlot stores limit value in 'expression' attribute
        limit_value_expr = limit_expr.args.get("expression")
        if limit_value_expr:
            # Could be a literal number or identifier
            if isinstance(limit_value_expr, exp.Literal):
                limit_value = str(limit_value_expr.this)
            elif isinstance(limit_value_expr, (int, float)):
                limit_value = str(int(limit_value_expr))
            else:
                limit_value = _expression_to_asql(limit_value_expr, style)
        elif limit_expr.expressions:
            # Try expressions list
            limit_value_expr = limit_expr.expressions[0]
            if isinstance(limit_value_expr, exp.Literal):
                limit_value = str(limit_value_expr.this)
            else:
                limit_value = _expression_to_asql(limit_value_expr, style)
        elif limit_expr.this:
            # Try the 'this' attribute directly
            limit_value = str(limit_expr.this)
        else:
            raise ASQLCompilationError(f"Cannot determine LIMIT value from expression: {limit_expr}")
        parts.append(f"limit {limit_value}")
    
    return "\n".join(parts)


def _expression_to_asql(expr: exp.Expression, style: "StyleConfig" = None) -> str:
    """Convert a SQLGlot expression to ASQL string representation."""
    if style is None:
        from asql.config import StyleConfig
        style = StyleConfig()
    
    if isinstance(expr, exp.Column):
        parts = []
        if expr.table:
            parts.append(expr.table)
        parts.append(expr.this if isinstance(expr.this, str) else str(expr.this))
        return ".".join(parts)
    
    elif isinstance(expr, exp.Identifier):
        return expr.this if isinstance(expr.this, str) else str(expr.this)
    
    elif isinstance(expr, exp.Literal):
        if isinstance(expr.this, str):
            quote = '"' if style.quotes == "double" else "'"
            return f'{quote}{expr.this}{quote}'
        return str(expr.this)
    
    elif isinstance(expr, exp.EQ):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        eq_op = "==" if style.equality == "double" else "="
        return f"{left} {eq_op} {right}"
    
    elif isinstance(expr, exp.NEQ):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} != {right}"
    
    elif isinstance(expr, exp.GT):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} > {right}"
    
    elif isinstance(expr, exp.GTE):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} >= {right}"
    
    elif isinstance(expr, exp.LT):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} < {right}"
    
    elif isinstance(expr, exp.LTE):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} <= {right}"
    
    elif isinstance(expr, exp.And):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} and {right}"
    
    elif isinstance(expr, exp.Or):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"({left} or {right})"
    
    elif isinstance(expr, exp.Is):
        left = _expression_to_asql(expr.left, style)
        if expr.args.get("not"):
            return f"{left} is not null" if expr.right is None else f"{left} is not {_expression_to_asql(expr.right, style)}"
        else:
            return f"{left} is null" if expr.right is None else f"{left} is {_expression_to_asql(expr.right, style)}"
    
    elif isinstance(expr, exp.In):
        # In expressions use 'this' for the left side, not 'left'
        left = _expression_to_asql(expr.this, style) if expr.this else ""
        expressions = expr.expressions
        values = ", ".join(_expression_to_asql(e, style) for e in expressions)
        if expr.args.get("not"):
            return f"{left} not in ({values})"
        return f"{left} in ({values})"
    
    elif isinstance(expr, exp.Add):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} + {right}"
    
    elif isinstance(expr, exp.Sub):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} - {right}"
    
    elif isinstance(expr, exp.Mul):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} * {right}"
    
    elif isinstance(expr, exp.Div):
        left = _expression_to_asql(expr.left, style)
        right = _expression_to_asql(expr.right, style)
        return f"{left} / {right}"
    
    elif isinstance(expr, exp.Alias):
        expr_str = _expression_to_asql(expr.this, style)
        alias = expr.alias.this if isinstance(expr.alias, exp.Identifier) else str(expr.alias)
        return f"{expr_str} as {alias}"
    
    elif isinstance(expr, exp.Cast):
        expr_str = _expression_to_asql(expr.this, style)
        # Extract type name from 'to' field
        to_type = expr.args.get("to")
        if to_type:
            if isinstance(to_type, exp.DataType):
                # DataType.this is a Type enum, use .name to get the string
                if hasattr(to_type.this, 'name'):
                    type_name = to_type.this.name
                elif isinstance(to_type.this, str):
                    type_name = to_type.this
                else:
                    type_name = str(to_type.this)
            elif isinstance(to_type, exp.Identifier):
                type_name = to_type.this if isinstance(to_type.this, str) else str(to_type.this)
            else:
                type_name = str(to_type)
            
            # Use style to determine cast syntax
            if style.cast == "double_colon":
                return f"{expr_str}::{type_name}"
            else:
                return f"cast({expr_str} as {type_name})"
        # Cast without a target type is malformed
        raise ASQLCompilationError(f"Cast expression missing target type: {expr}")
    
    elif isinstance(expr, (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
        return _aggregation_to_asql(expr, style)
    
    elif isinstance(expr, exp.Coalesce):
        # Convert COALESCE based on style
        args = [expr.this] + (expr.expressions if expr.expressions else [])
        arg_strs = [_expression_to_asql(arg, style) for arg in args]
        if style.coalesce == "operator":
            return " ?? ".join(arg_strs)
        else:
            return f"coalesce({', '.join(arg_strs)})"
    
    elif isinstance(expr, exp.Case):
        # Convert CASE statement to DuckDB/Spark-style syntax
        # CASE expr WHEN value THEN result ... ELSE default END
        # or CASE WHEN condition THEN result ... ELSE default END
        
        parts = ["case"]
        
        # Get WHEN clauses from args['ifs'] (list of If expressions)
        ifs = expr.args.get("ifs", [])
        
        # Check if this is a simple CASE (CASE expr WHEN ...) or searched CASE (CASE WHEN ...)
        if expr.this:
            # Simple CASE: CASE expr WHEN value THEN result
            expr_str = _expression_to_asql(expr.this, style)
            parts.append(expr_str)
            
            # Process WHEN clauses (stored in ifs list as If expressions)
            for if_expr in ifs:
                if isinstance(if_expr, exp.If):
                    when_value = _expression_to_asql(if_expr.this, style) if if_expr.this else ""
                    then_value = _expression_to_asql(if_expr.args.get("true"), style) if if_expr.args.get("true") else ""
                    parts.append(f"  when {when_value} then {then_value}")
        else:
            # Searched CASE: CASE WHEN condition THEN result
            # Process WHEN clauses (stored in ifs list as If expressions)
            for if_expr in ifs:
                if isinstance(if_expr, exp.If):
                    when_condition = _expression_to_asql(if_expr.this, style) if if_expr.this else ""
                    then_value = _expression_to_asql(if_expr.args.get("true"), style) if if_expr.args.get("true") else ""
                    parts.append(f"  when {when_condition} then {then_value}")
        
        # Add ELSE clause if present
        default = expr.args.get("default")
        if default:
            default_str = _expression_to_asql(default, style)
            parts.append(f"  else {default_str}")
        
        parts.append("end")
        return "\n".join(parts)
    
    elif isinstance(expr, exp.Anonymous):
        # Generic function call (e.g., STRING_AGG, DATE_TRUNC, CAST, COALESCE, etc.)
        func_name = expr.this if isinstance(expr.this, str) else str(expr.this)
        func_name_upper = func_name.upper()
        
        # Check if it's COALESCE function call
        if func_name_upper == "COALESCE":
            # Convert COALESCE based on style
            args = []
            if hasattr(expr, 'this') and expr.this:
                args.append(expr.this)
            if expr.expressions:
                args.extend(expr.expressions)
            if not args and expr.expressions:
                args = expr.expressions
            arg_strs = [_expression_to_asql(arg, style) for arg in args]
            if style.coalesce == "operator":
                return " ?? ".join(arg_strs) if arg_strs else "COALESCE()"
            else:
                return f"coalesce({', '.join(arg_strs)})" if arg_strs else "coalesce()"
        
        # Check if it's CAST function call (CAST(expr AS type))
        if func_name_upper == "CAST":
            if expr.expressions and len(expr.expressions) >= 1:
                cast_expr = expr.expressions[0]
                cast_expr_str = _expression_to_asql(cast_expr, style)
                type_name = "UNKNOWN"
                
                for i, e in enumerate(expr.expressions[1:], 1):
                    if isinstance(e, str) and e.upper() == "AS":
                        continue
                    if isinstance(e, (exp.Identifier, exp.DataType)):
                        type_name = _expression_to_asql(e, style)
                        break
                    elif isinstance(e, exp.Expression):
                        type_name = _expression_to_asql(e, style)
                        break
                
                if type_name == "UNKNOWN" and hasattr(expr, 'args') and 'to' in expr.args:
                    to_type = expr.args['to']
                    if isinstance(to_type, exp.DataType):
                        if hasattr(to_type.this, 'name'):
                            type_name = to_type.this.name
                        else:
                            type_name = str(to_type.this)
                    elif isinstance(to_type, exp.Identifier):
                        type_name = to_type.this if isinstance(to_type.this, str) else str(to_type.this)
                    else:
                        type_name = str(to_type)
                
                if type_name == "UNKNOWN":
                    raise ASQLCompilationError(f"CAST function missing target type: {expr}")
                
                if style.cast == "double_colon":
                    return f"{cast_expr_str}::{type_name}"
                else:
                    return f"cast({cast_expr_str} as {type_name})"
        
        # For other functions, just pass through
        args = ", ".join(_expression_to_asql(arg, style) for arg in expr.expressions) if expr.expressions else ""
        return f"{func_name}({args})"
    
    elif hasattr(expr, 'sql_name') and hasattr(expr, 'expressions'):
        # Handle as function if it has sql_name and expressions
        func_name = expr.sql_name()
        args = ", ".join(_expression_to_asql(arg, style) for arg in expr.expressions) if expr.expressions else ""
        return f"{func_name}({args})"
    
    # Fallback: use SQL representation
    return str(expr)


def _format_function_shorthand(func_name: str, col: str, style: "StyleConfig") -> str:
    """Format a function call according to the function_shorthand style setting.
    
    Args:
        func_name: Function name (e.g., "sum", "avg")
        col: Column name or expression
        style: StyleConfig instance
    
    Returns:
        Formatted function call string:
        - "parens" → sum(amount)
        - "underscore" → sum_amount
        - "space" → sum amount
    """
    shorthand = style.function_shorthand
    
    if shorthand == "parens":
        return f"{func_name}({col})"
    elif shorthand == "underscore":
        return f"{func_name}_{col}"
    elif shorthand == "space":
        return f"{func_name} {col}"
    else:
        # Fallback to parens if unknown
        return f"{func_name}({col})"


def _aggregation_to_asql(expr: exp.Expression, style: "StyleConfig" = None) -> str:
    """Convert an aggregation expression to ASQL."""
    if style is None:
        from asql.config import StyleConfig
        style = StyleConfig()
    
    if isinstance(expr, exp.Count):
        # Check for DISTINCT keyword
        distinct = getattr(expr, 'distinct', False) or expr.args.get('distinct', False)
        if expr.expressions:
            arg = expr.expressions[0]
            if isinstance(arg, exp.Star):
                # Use style for count notation
                return "#" if style.count == "hash" else "count(*)"
            else:
                col = _expression_to_asql(arg, style)
                if distinct:
                    return f"count(distinct {col})"
                return f"count({col})"
        # COUNT() with no args = COUNT(*)
        return "#" if style.count == "hash" else "count(*)"
    
    elif isinstance(expr, exp.Sum):
        # SQLGlot stores the argument in expr.this, not expr.expressions
        if expr.this:
            col = _expression_to_asql(expr.this, style)
            return _format_function_shorthand("sum", col, style)
        elif expr.expressions:
            col = _expression_to_asql(expr.expressions[0], style)
            return _format_function_shorthand("sum", col, style)
        return "sum()"
    
    elif isinstance(expr, exp.Avg):
        # SQLGlot stores the argument in expr.this, not expr.expressions
        if expr.this:
            col = _expression_to_asql(expr.this, style)
            return _format_function_shorthand("avg", col, style)
        elif expr.expressions:
            col = _expression_to_asql(expr.expressions[0], style)
            return _format_function_shorthand("avg", col, style)
        return "avg()"
    
    elif isinstance(expr, exp.Min):
        # SQLGlot stores the argument in expr.this, not expr.expressions
        if expr.this:
            col = _expression_to_asql(expr.this, style)
            return _format_function_shorthand("min", col, style)
        elif expr.expressions:
            col = _expression_to_asql(expr.expressions[0], style)
            return _format_function_shorthand("min", col, style)
        return "min()"
    
    elif isinstance(expr, exp.Max):
        # SQLGlot stores the argument in expr.this, not expr.expressions
        if expr.this:
            col = _expression_to_asql(expr.this, style)
            return _format_function_shorthand("max", col, style)
        elif expr.expressions:
            col = _expression_to_asql(expr.expressions[0], style)
            return _format_function_shorthand("max", col, style)
        return "max()"
    
    elif isinstance(expr, exp.Alias):
        # Handle aliased aggregations
        agg_str = _aggregation_to_asql(expr.this, style)
        alias = expr.alias.this if isinstance(expr.alias, exp.Identifier) else str(expr.alias)
        return f"{agg_str} as {alias}"
    
    else:
        return str(expr)
