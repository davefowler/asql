"""ASQL reverse compiler - transforms SQL to ASQL."""

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
        
        # Auto-detect dialect if not provided
        if not source_dialect:
            source_dialect = detect_dialect(sql_query)
        
        # Parse SQL to AST
        if source_dialect:
            dialect = Dialect.get_or_raise(source_dialect)
            expressions = sqlglot.parse(sql_query, dialect=dialect)
        else:
            expressions = sqlglot.parse(sql_query)
        
        if not expressions:
            raise ASQLCompilationError("Failed to parse SQL query")
        
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
        
        return "\n".join(asql_parts)
        
    except sqlglot.errors.ParseError as e:
        raise ASQLCompilationError(f"SQL parse error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Reverse compilation error: {e}") from e


def _select_to_asql(select_expr: exp.Select) -> str:
    """Convert a SQLGlot Select expression to ASQL."""
    parts = []
    
    # Handle WITH/CTE clauses
    if select_expr.args.get("with"):
        with_clause = select_expr.args["with"]
        ctes = []
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
                cte_asql = _select_to_asql(cte.this)
                ctes.append(f"set {cte_name} = {cte_asql}")
        if ctes:
            parts.extend(ctes)
            parts.append("")  # Empty line between CTEs and main query
    
    # FROM clause (required in ASQL)
    from_expr = select_expr.args.get("from")
    if not from_expr:
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
        left = _expression_to_asql(expr.left)
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
    
    elif isinstance(expr, (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)):
        return _aggregation_to_asql(expr)
    
    elif isinstance(expr, exp.Function):
        func_name = expr.sql_name()
        args = ", ".join(_expression_to_asql(arg) for arg in expr.expressions)
        return f"{func_name}({args})"
    
    else:
        # Fallback: use SQL representation
        return str(expr)


def _aggregation_to_asql(expr: exp.Expression) -> str:
    """Convert an aggregation expression to ASQL."""
    if isinstance(expr, exp.Count):
        if expr.expressions:
            arg = expr.expressions[0]
            if isinstance(arg, exp.Star):
                return "#"
            else:
                col = _expression_to_asql(arg)
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
