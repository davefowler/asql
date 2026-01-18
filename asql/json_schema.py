"""
JSON Schema for Visual ASQL Editor

Provides conversion from JSON representation to ASQL text.
For JSON output, use the visual_asql dialect:
    sqlglot.transpile(sql, read="asql", write="visual_asql")
"""

from typing import Dict, Any, List


def json_to_asql(query_json: Dict[str, Any]) -> str:
    """
    Convert JSON representation to ASQL text.

    Args:
        query_json: Dict with 'from' and 'transforms' keys

    Returns:
        ASQL query as string
    """
    lines: List[str] = []

    # FROM clause
    from_clause = query_json.get("from", {})
    table = from_clause.get("table", "")
    if not table:
        return "from # Enter table name"

    lines.append(f"from {table}")

    # Process transforms
    for transform in query_json.get("transforms", []):
        transform_type = transform.get("type")

        # === FILTER TRANSFORMS ===
        if transform_type == "where":
            condition = transform.get("condition", {})
            condition_asql = _expression_to_asql(condition)
            if condition_asql:
                lines.append(f"  where {condition_asql}")

        elif transform_type == "having":
            condition = transform.get("condition", {})
            condition_asql = _expression_to_asql(condition)
            if condition_asql:
                lines.append(f"  having {condition_asql}")

        elif transform_type == "qualify":
            condition = transform.get("condition", {})
            condition_asql = _expression_to_asql(condition)
            if condition_asql:
                lines.append(f"  qualify {condition_asql}")

        # === JOIN TRANSFORMS ===
        elif transform_type == "join":
            join_type = transform.get("join_type", "inner")
            join_table = transform.get("table", "")
            condition = transform.get("condition")

            # Map join type to ASQL symbol
            join_symbol = {
                "inner": "&",
                "left": "&?",
                "right": "?&",
                "full": "?&?",
                "cross": "*",
            }.get(join_type, "&")

            if condition:
                condition_asql = _expression_to_asql(condition)
                lines.append(f"  {join_symbol} {join_table} on {condition_asql}")
            else:
                lines.append(f"  {join_symbol} {join_table}")

        # === SELECT TRANSFORMS ===
        elif transform_type == "select":
            columns = transform.get("columns", [])
            if columns:
                column_strs = _columns_to_asql(columns)
                lines.append(f"  select {', '.join(column_strs)}")

        elif transform_type == "except":
            columns = transform.get("columns", [])
            if columns:
                col_names = [c.get("name", c) if isinstance(c, dict) else c for c in columns]
                lines.append(f"  except {', '.join(col_names)}")

        # === AGGREGATE TRANSFORMS ===
        elif transform_type == "group_by":
            dimensions = transform.get("dimensions", [])
            aggregates = transform.get("aggregates", [])

            if dimensions:
                dims_str = ", ".join(dimensions)

                if aggregates:
                    # Use ASQL's inline aggregate syntax
                    agg_strs = []
                    for agg in aggregates:
                        func = agg.get("function", "count")
                        col = agg.get("column", "*")
                        alias = agg.get("alias", f"{func}_{col}")
                        agg_strs.append(f"{func}({col}) as {alias}")

                    aggs_str = ",\n    ".join(agg_strs)
                    lines.append(f"  group by {dims_str} (")
                    lines.append(f"    {aggs_str}")
                    lines.append("  )")
                else:
                    lines.append(f"  group by {dims_str}")

        # === SORT TRANSFORMS ===
        elif transform_type == "order_by":
            expressions = transform.get("expressions", [])
            if expressions:
                order_parts = []
                for expr in expressions:
                    col = expr.get("column", "")
                    direction = expr.get("direction", "asc")
                    # Use ASQL's - prefix for descending
                    if direction == "desc":
                        order_parts.append(f"-{col}")
                    else:
                        order_parts.append(col)

                lines.append(f"  order by {', '.join(order_parts)}")

        # === UTILITY TRANSFORMS ===
        elif transform_type == "limit":
            count = transform.get("count", 10)
            lines.append(f"  limit {count}")

        elif transform_type == "offset":
            count = transform.get("count", 0)
            lines.append(f"  offset {count}")

        elif transform_type == "distinct":
            lines.append("  distinct")

        elif transform_type == "sample":
            size = transform.get("size", 100)
            lines.append(f"  sample {size}")

        elif transform_type == "stash":
            name = transform.get("name", "cte")
            lines.append(f"  stash as {name}")

        elif transform_type == "deduplicate":
            columns = transform.get("columns", [])
            if columns:
                col_names = [c.get("name", c) if isinstance(c, dict) else c for c in columns]
                lines.append(f"  deduplicate {', '.join(col_names)}")
            else:
                lines.append("  deduplicate")

        # === COLUMN TRANSFORMS ===
        elif transform_type == "extend":
            columns = transform.get("columns", [])
            if columns:
                column_strs = _columns_to_asql(columns)
                lines.append(f"  extend {', '.join(column_strs)}")

        elif transform_type == "rename":
            mappings = transform.get("mappings", [])
            if mappings:
                rename_strs = []
                for m in mappings:
                    old_name = m.get("from", m.get("old", ""))
                    new_name = m.get("to", m.get("new", ""))
                    rename_strs.append(f"{old_name} as {new_name}")
                lines.append(f"  rename {', '.join(rename_strs)}")

        elif transform_type == "replace":
            columns = transform.get("columns", [])
            if columns:
                column_strs = _columns_to_asql(columns)
                lines.append(f"  replace {', '.join(column_strs)}")

        elif transform_type == "explode":
            column = transform.get("column", "")
            lines.append(f"  explode {column}")

        # === WINDOW TRANSFORMS ===
        elif transform_type == "per":
            columns = transform.get("columns", [])
            if columns:
                col_names = [c.get("name", c) if isinstance(c, dict) else c for c in columns]
                lines.append(f"  per {', '.join(col_names)}")

        elif transform_type == "number":
            lines.append("  number")

        elif transform_type == "rank":
            lines.append("  rank")

        elif transform_type == "dense":
            lines.append("  dense")

        # === ANALYTICS TRANSFORMS ===
        elif transform_type == "cohort":
            entity = transform.get("entity", "")
            cohort_date = transform.get("cohort_date", "")
            event_date = transform.get("event_date", "")
            lines.append(f"  cohort {entity} by {cohort_date} on {event_date}")

        elif transform_type == "recurse":
            max_depth = transform.get("max_depth")
            if max_depth:
                lines.append(f"  recurse {max_depth}")
            else:
                lines.append("  recurse")

    return "\n".join(lines)


def _columns_to_asql(columns: List[Any]) -> List[str]:
    """Convert column list to ASQL strings."""
    column_strs = []
    for col in columns:
        if isinstance(col, dict):
            if "expression" in col and col.get("expression"):
                column_strs.append(f"{col['expression']} as {col['name']}")
            else:
                column_strs.append(col.get("name", ""))
        else:
            column_strs.append(str(col))
    return column_strs


def _expression_to_asql(expr: Dict[str, Any]) -> str:
    """Convert JSON expression to ASQL text."""
    if not expr:
        return ""

    expr_type = expr.get("type")

    if expr_type == "column":
        table = expr.get("table", "")
        name = expr.get("name", "")
        if table:
            return f"{table}.{name}"
        return str(name)

    elif expr_type == "literal":
        value = expr.get("value", "")
        data_type = expr.get("data_type", "string")

        if value is None:
            return "null"
        if data_type == "string":
            # Escape double quotes to prevent injection, then wrap in double quotes
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        elif data_type == "number":
            return str(value)
        elif data_type == "boolean":
            return str(value).lower()
        elif data_type == "null":
            return "null"
        else:
            # Fallback: treat as string and escape properly
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'

    elif expr_type == "binary_op":
        left = _expression_to_asql(expr.get("left", {}))
        right = _expression_to_asql(expr.get("right", {}))
        operator = expr.get("operator", "=")

        # Convert SQL = to ASQL ==
        if operator == "=":
            operator = "=="

        # Handle AND/OR with parentheses
        if operator in ("and", "or"):
            return f"({left} {operator} {right})"

        return f"{left} {operator} {right}"

    elif expr_type == "unary_op":
        operand = _expression_to_asql(expr.get("operand", {}))
        operator = expr.get("operator", "")
        if operator == "not":
            return f"not ({operand})"
        return f"{operator} {operand}"

    # Null checks
    elif expr_type == "null_check":
        operand = _expression_to_asql(expr.get("operand", {}))
        operator = expr.get("operator", "is null")
        if operator == "is null":
            return f"{operand} == null"
        elif operator == "is not null":
            return f"{operand} != null"
        return f"{operand} {operator}"

    # IN operator
    elif expr_type == "in":
        operand = _expression_to_asql(expr.get("operand", {}))
        values = expr.get("values", [])
        value_strs = [_expression_to_asql(v) for v in values]
        return f"{operand} in ({', '.join(value_strs)})"

    # NOT IN operator
    elif expr_type == "not_in":
        operand = _expression_to_asql(expr.get("operand", {}))
        values = expr.get("values", [])
        value_strs = [_expression_to_asql(v) for v in values]
        return f"{operand} not in ({', '.join(value_strs)})"

    # LIKE operator
    elif expr_type == "like":
        operand = _expression_to_asql(expr.get("operand", {}))
        pattern = _expression_to_asql(expr.get("pattern", {}))
        return f"{operand} matches {pattern}"

    # BETWEEN operator
    elif expr_type == "between":
        operand = _expression_to_asql(expr.get("operand", {}))
        low = _expression_to_asql(expr.get("low", {}))
        high = _expression_to_asql(expr.get("high", {}))
        return f"{operand} between {low} and {high}"

    # String operators (ASQL-specific)
    elif expr_type == "contains":
        operand = _expression_to_asql(expr.get("operand", {}))
        value = _expression_to_asql(expr.get("value", {}))
        return f"{operand} contains {value}"

    elif expr_type == "icontains":
        operand = _expression_to_asql(expr.get("operand", {}))
        value = _expression_to_asql(expr.get("value", {}))
        return f"{operand} icontains {value}"

    elif expr_type == "starts_with":
        operand = _expression_to_asql(expr.get("operand", {}))
        value = _expression_to_asql(expr.get("value", {}))
        return f"{operand} starts with {value}"

    elif expr_type == "istarts_with":
        operand = _expression_to_asql(expr.get("operand", {}))
        value = _expression_to_asql(expr.get("value", {}))
        return f"{operand} istarts with {value}"

    elif expr_type == "ends_with":
        operand = _expression_to_asql(expr.get("operand", {}))
        value = _expression_to_asql(expr.get("value", {}))
        return f"{operand} ends with {value}"

    elif expr_type == "iends_with":
        operand = _expression_to_asql(expr.get("operand", {}))
        value = _expression_to_asql(expr.get("value", {}))
        return f"{operand} iends with {value}"

    # Function call
    elif expr_type == "function":
        name = expr.get("name", "")
        args = expr.get("args", [])
        arg_strs = [_expression_to_asql(a) for a in args]
        return f"{name}({', '.join(arg_strs)})"

    elif expr_type == "unknown":
        return str(expr.get("value", ""))

    else:
        return ""
