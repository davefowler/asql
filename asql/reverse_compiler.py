"""ASQL reverse compiler - transforms SQL to ASQL."""

import re
from typing import Optional, List
import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect

from asql.errors import ASQLCompilationError


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
    
    try:
        # Try parsing with different dialects and see which one works best
        dialects_to_try = ['bigquery', 'redshift', 'postgres', 'mysql', 'snowflake', 'spark']
        
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
            except Exception:
                continue
        
        # Also try generic parsing
        try:
            parsed = sqlglot.parse(sql_query)
            if parsed and not best_dialect:
                # If generic parsing works, return None (unknown/ansi)
                return None
        except Exception:
            pass
        
        return best_dialect
    except Exception:
        return None


def reverse_compile(
    sql_query: str,
    source_dialect: Optional[str] = None,
) -> str:
    """
    Compile SQL query to ASQL.
    
    Args:
        sql_query: SQL query string
        source_dialect: Source SQL dialect (e.g., 'bigquery', 'redshift')
                       If None, will attempt auto-detection
    
    Returns:
        ASQL query string
    
    Raises:
        ASQLCompilationError: If compilation fails
    """
    try:
        if not sql_query.strip():
            raise ASQLCompilationError("Empty SQL query")
        
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
        # Add common dialects as fallbacks
        dialects_to_try.extend(['snowflake', 'bigquery', 'postgres', 'redshift', 'mysql', 'spark'])
        
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
                asql = _select_to_asql(expr)
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


def _select_to_asql(select_expr: exp.Select) -> str:
    """Convert a SQLGlot Select expression to ASQL."""
    parts = []
    
    # Handle WITH/CTE clauses (sqlglot 28+ uses "with_")
    with_clause = select_expr.args.get("with_")
    if with_clause:
        ctes = []
        # Handle case where expressions might not be available
        try:
            # Try to get expressions from the with clause
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
                        try:
                            cte_asql = _select_to_asql(cte.this)
                            ctes.append(f"{cte_asql}\nstash as {cte_name}")
                        except ASQLCompilationError as cte_error:
                            # If a CTE can't be converted (e.g., no FROM clause), 
                            # include it as a comment and continue
                            cte_sql = str(cte.this)
                            ctes.append(f"-- CTE '{cte_name}' could not be converted: {cte_error}\n-- Original: {cte_sql[:100]}...")
        except (AttributeError, TypeError) as e:
            # If we can't parse CTEs, skip them and continue with the main query
            # This allows the query to still be converted even if CTE parsing fails
            pass
        
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
            expr_strs = [_expression_to_asql(e) for e in select_exprs]
            return f"-- No FROM clause, cannot convert to ASQL: SELECT {', '.join(expr_strs)}"
        raise ASQLCompilationError("ASQL requires a FROM clause")
    
    table = from_expr.this
    if isinstance(table, exp.Table):
        table_name = table.this if isinstance(table.this, str) else str(table.this)
        parts.append(f"from {table_name}")
    elif isinstance(table, exp.Identifier):
        parts.append(f"from {table.this}")
    else:
        parts.append(f"from {str(table)}")
    
    # JOIN clauses
    joins = select_expr.args.get("joins", [])
    for join in joins:
        join_type = join.kind or "inner"
        join_table = join.this
        table_name = join_table.this if isinstance(join_table, exp.Table) else str(join_table)
        
        on_condition = join.args.get("on")
        if on_condition:
            condition_str = _expression_to_asql(on_condition)
            parts.append(f"join {table_name} on {condition_str}")
        else:
            parts.append(f"join {table_name}")
    
    # WHERE clause
    where_expr = select_expr.args.get("where")
    if where_expr:
        condition = _expression_to_asql(where_expr.this)
        parts.append(f"where {condition}")
    
    # GROUP BY clause
    group_expr = select_expr.args.get("group")
    select_exprs = select_expr.args.get("expressions", [])
    
    if group_expr:
        group_cols = []
        for col in group_expr.expressions:
            group_cols.append(_expression_to_asql(col))
        
        # Get aggregations from SELECT expressions
        aggregations = []
        grouping_col_set = set()
        for col in group_expr.expressions:
            col_str = _expression_to_asql(col)
            grouping_col_set.add(col_str.lower())
        
        for expr in select_exprs:
            # Check if it's an aggregation
            if isinstance(expr, (exp.AggFunc, exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
                agg_str = _aggregation_to_asql(expr)
                aggregations.append(agg_str)
            # Check if it's an aliased aggregation
            elif isinstance(expr, exp.Alias) and isinstance(expr.this, (exp.AggFunc, exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
                agg_str = _aggregation_to_asql(expr)
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
                    select_str = _expression_to_asql(expr)
                    select_parts.append(select_str)
            if select_parts:
                parts.append(f"select {', '.join(select_parts)}")
    
    # ORDER BY clause
    order_expr = select_expr.args.get("order")
    if order_expr:
        order_parts = []
        for order in order_expr.expressions:
            expr_str = _expression_to_asql(order.this)
            desc = order.args.get("desc", False)
            if desc:
                order_parts.append(f"-{expr_str}")
            else:
                order_parts.append(expr_str)
        parts.append(f"sort {', '.join(order_parts)}")
    
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
                limit_value = _expression_to_asql(limit_value_expr)
        elif limit_expr.expressions:
            # Fallback: try expressions list
            limit_value_expr = limit_expr.expressions[0]
            if isinstance(limit_value_expr, exp.Literal):
                limit_value = str(limit_value_expr.this)
            else:
                limit_value = _expression_to_asql(limit_value_expr)
        else:
            # Last fallback
            limit_value = str(limit_expr.this) if limit_expr.this else "10"
        parts.append(f"take {limit_value}")
    
    return "\n".join(parts)


def _expression_to_asql(expr: exp.Expression) -> str:
    """Convert a SQLGlot expression to ASQL string representation."""
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
            return f'"{expr.this}"'
        return str(expr.this)
    
    elif isinstance(expr, exp.EQ):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} == {right}"
    
    elif isinstance(expr, exp.NEQ):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} != {right}"
    
    elif isinstance(expr, exp.GT):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} > {right}"
    
    elif isinstance(expr, exp.GTE):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} >= {right}"
    
    elif isinstance(expr, exp.LT):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} < {right}"
    
    elif isinstance(expr, exp.LTE):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} <= {right}"
    
    elif isinstance(expr, exp.And):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} and {right}"
    
    elif isinstance(expr, exp.Or):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"({left} or {right})"
    
    elif isinstance(expr, exp.Is):
        left = _expression_to_asql(expr.left)
        if expr.args.get("not"):
            return f"{left} is not null" if expr.right is None else f"{left} is not {_expression_to_asql(expr.right)}"
        else:
            return f"{left} is null" if expr.right is None else f"{left} is {_expression_to_asql(expr.right)}"
    
    elif isinstance(expr, exp.In):
        # In expressions use 'this' for the left side, not 'left'
        left = _expression_to_asql(expr.this) if expr.this else ""
        expressions = expr.expressions
        values = ", ".join(_expression_to_asql(e) for e in expressions)
        if expr.args.get("not"):
            return f"{left} not in ({values})"
        return f"{left} in ({values})"
    
    elif isinstance(expr, exp.Add):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} + {right}"
    
    elif isinstance(expr, exp.Sub):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} - {right}"
    
    elif isinstance(expr, exp.Mul):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} * {right}"
    
    elif isinstance(expr, exp.Div):
        left = _expression_to_asql(expr.left)
        right = _expression_to_asql(expr.right)
        return f"{left} / {right}"
    
    elif isinstance(expr, exp.Alias):
        expr_str = _expression_to_asql(expr.this)
        alias = expr.alias.this if isinstance(expr.alias, exp.Identifier) else str(expr.alias)
        return f"{expr_str} as {alias}"
    
    elif isinstance(expr, exp.Cast):
        # Convert CAST(... AS ...) to PostgreSQL-style :: syntax
        expr_str = _expression_to_asql(expr.this)
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
            return f"{expr_str}::{type_name}"
        # Fallback if type not found
        return f"{expr_str}::UNKNOWN"
    
    elif isinstance(expr, (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
        return _aggregation_to_asql(expr)
    
    elif isinstance(expr, exp.Coalesce):
        # Convert COALESCE to ?? operator (ASQL nullish coalescing)
        # COALESCE(a, b, c) becomes a ?? b ?? c
        args = [expr.this] + (expr.expressions if expr.expressions else [])
        arg_strs = [_expression_to_asql(arg) for arg in args]
        return " ?? ".join(arg_strs)
    
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
            expr_str = _expression_to_asql(expr.this)
            parts.append(expr_str)
            
            # Process WHEN clauses (stored in ifs list as If expressions)
            for if_expr in ifs:
                if isinstance(if_expr, exp.If):
                    when_value = _expression_to_asql(if_expr.this) if if_expr.this else ""
                    then_value = _expression_to_asql(if_expr.args.get("true")) if if_expr.args.get("true") else ""
                    parts.append(f"  when {when_value} then {then_value}")
        else:
            # Searched CASE: CASE WHEN condition THEN result
            # Process WHEN clauses (stored in ifs list as If expressions)
            for if_expr in ifs:
                if isinstance(if_expr, exp.If):
                    when_condition = _expression_to_asql(if_expr.this) if if_expr.this else ""
                    then_value = _expression_to_asql(if_expr.args.get("true")) if if_expr.args.get("true") else ""
                    parts.append(f"  when {when_condition} then {then_value}")
        
        # Add ELSE clause if present
        default = expr.args.get("default")
        if default:
            default_str = _expression_to_asql(default)
            parts.append(f"  else {default_str}")
        
        parts.append("end")
        return "\n".join(parts)
    
    elif isinstance(expr, exp.Anonymous):
        # Generic function call (e.g., STRING_AGG, DATE_TRUNC, CAST, COALESCE, etc.)
        func_name = expr.this if isinstance(expr.this, str) else str(expr.this)
        func_name_upper = func_name.upper()
        
        # Check if it's COALESCE function call
        if func_name_upper == "COALESCE":
            # Convert COALESCE(a, b, c) to a ?? b ?? c (ASQL nullish coalescing)
            # Anonymous COALESCE might have first arg in expr.this or expr.expressions
            args = []
            if hasattr(expr, 'this') and expr.this:
                args.append(expr.this)
            if expr.expressions:
                args.extend(expr.expressions)
            # If no args found, try expressions only
            if not args and expr.expressions:
                args = expr.expressions
            arg_strs = [_expression_to_asql(arg) for arg in args]
            return " ?? ".join(arg_strs) if arg_strs else "COALESCE()"
        
        # Check if it's CAST function call (CAST(expr AS type))
        # Note: SQLGlot usually parses CAST as exp.Cast, but some dialects might parse as Anonymous
        if func_name_upper == "CAST":
            # CAST expressions: CAST(expr AS type)
            # SQLGlot might structure this differently when parsed as Anonymous
            # Try to extract the expression and type
            if expr.expressions and len(expr.expressions) >= 1:
                cast_expr = expr.expressions[0]
                cast_expr_str = _expression_to_asql(cast_expr)
                type_name = "UNKNOWN"
                
                # Look for type in expressions (might be after AS keyword)
                # SQLGlot might have: expressions = [expr, "AS", type] or [expr, type]
                for i, e in enumerate(expr.expressions[1:], 1):
                    # Skip "AS" keyword if present
                    if isinstance(e, str) and e.upper() == "AS":
                        continue
                    # Found type
                    if isinstance(e, (exp.Identifier, exp.DataType)):
                        type_name = _expression_to_asql(e)
                        break
                    elif isinstance(e, exp.Expression):
                        # Might be a type expression
                        type_name = _expression_to_asql(e)
                        break
                
                # Also check if there's a 'to' argument (like exp.Cast has)
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
                
                return f"{cast_expr_str}::{type_name}"
        
        # For other functions, just pass through
        args = ", ".join(_expression_to_asql(arg) for arg in expr.expressions) if expr.expressions else ""
        return f"{func_name}({args})"
    
    elif hasattr(expr, 'sql_name') and hasattr(expr, 'expressions'):
        # Try to handle as function if it has sql_name and expressions
        try:
            func_name = expr.sql_name()
            args = ", ".join(_expression_to_asql(arg) for arg in expr.expressions) if expr.expressions else ""
            return f"{func_name}({args})"
        except Exception:
            pass
    
    else:
        # Fallback: use SQL representation
        return str(expr)


def _aggregation_to_asql(expr: exp.Expression) -> str:
    """Convert an aggregation expression to ASQL."""
    if isinstance(expr, exp.Count):
        # Check for DISTINCT keyword
        distinct = getattr(expr, 'distinct', False) or expr.args.get('distinct', False)
        if expr.expressions:
            arg = expr.expressions[0]
            if isinstance(arg, exp.Star):
                return "#"
            else:
                col = _expression_to_asql(arg)
                if distinct:
                    return f"count(distinct {col})"
                return f"count({col})"
        return "#"
    
    elif isinstance(expr, exp.Sum):
        if expr.expressions:
            col = _expression_to_asql(expr.expressions[0])
            return f"sum({col})"
        return "sum()"
    
    elif isinstance(expr, exp.Avg):
        if expr.expressions:
            col = _expression_to_asql(expr.expressions[0])
            return f"avg({col})"
        return "avg()"
    
    elif isinstance(expr, exp.Min):
        if expr.expressions:
            col = _expression_to_asql(expr.expressions[0])
            return f"min({col})"
        return "min()"
    
    elif isinstance(expr, exp.Max):
        if expr.expressions:
            col = _expression_to_asql(expr.expressions[0])
            return f"max({col})"
        return "max()"
    
    elif isinstance(expr, exp.Alias):
        # Handle aliased aggregations
        agg_str = _aggregation_to_asql(expr.this)
        alias = expr.alias.this if isinstance(expr.alias, exp.Identifier) else str(expr.alias)
        return f"{agg_str} as {alias}"
    
    else:
        return str(expr)
