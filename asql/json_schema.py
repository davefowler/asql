"""
JSON Schema for Visual ASQL Editor

Provides conversion from JSON representation to ASQL text.
For JSON output, use the visual_asql dialect:
    sqlglot.transpile(sql, read="asql", write="visual_asql")

JSON Format:
    Always an array of pipelines:
    [
        {"name": "cte_name", "from": {...}, "transforms": [...], "set_operation": {...}},
        {"name": null, "from": {...}, "transforms": [...]}
    ]

    - name: null for output/unnamed queries, string for CTEs
    - set_operation: {"type": "union"|"intersect"|"except", "all": bool}
"""

from typing import Dict, Any, List, Union


def json_to_asql(query_json: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
    """
    Convert JSON representation to ASQL text.

    Args:
        query_json: Either:
            - List of pipeline dicts (new format)
            - Single dict with 'from' and 'transforms' keys (legacy format)

    Returns:
        ASQL query as string
    """
    # Handle legacy single-pipeline format
    if isinstance(query_json, dict):
        pipelines = [query_json]
    else:
        pipelines = query_json

    if not pipelines:
        return "from # Enter table name"

    # Track CTE names we've created so we can chain them properly
    cte_names: set = set()
    result_lines: List[str] = []

    for i, pipeline in enumerate(pipelines):
        from_clause = pipeline.get("from", {})
        from_table = from_clause.get("table", "") if isinstance(from_clause, dict) else ""
        name = pipeline.get("name")

        # Check if this pipeline continues from a CTE we just created
        # If so, we don't need a new FROM - just continue the pipeline
        is_continuation = from_table in cte_names

        if is_continuation:
            # Continue the pipeline - just add transforms (no FROM)
            transforms_lines = _transforms_to_asql_lines(pipeline.get("transforms", []))
            result_lines.extend(transforms_lines)
        else:
            # Start a new pipeline with FROM
            # Handle set operations (UNION, INTERSECT, EXCEPT) before this pipeline
            set_op = pipelines[i - 1].get("set_operation") if i > 0 else None
            if set_op:
                op_type = set_op.get("type", "union").upper()
                if set_op.get("all"):
                    op_type += " ALL"
                result_lines.append(op_type)
            elif i > 0:
                # Add semicolon to separate independent pipelines
                result_lines.append(";")

            pipeline_asql = _pipeline_to_asql(pipeline)
            result_lines.append(pipeline_asql)

        # Add stash for named pipelines (CTEs)
        if name:
            result_lines.append(f"  stash as {name}")
            cte_names.add(name)

    return "\n".join(result_lines)


def _transforms_to_asql_lines(transforms: List[Dict[str, Any]]) -> List[str]:
    """Convert transforms list to ASQL lines (without FROM clause)."""
    lines: List[str] = []

    for transform in transforms:
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
                        col = agg.get("column") or "*"  # Empty string -> *
                        alias = agg.get("alias") or f"{func}_{col}"
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

    return lines


def _pipeline_to_asql(pipeline: Dict[str, Any]) -> str:
    """Convert a single pipeline to ASQL text (including FROM clause)."""
    lines: List[str] = []

    # FROM clause
    from_clause = pipeline.get("from", {})
    table = from_clause.get("table", "") if isinstance(from_clause, dict) else ""
    if not table:
        return "from # Enter table name"

    lines.append(f"from {table}")

    # Add transforms
    transform_lines = _transforms_to_asql_lines(pipeline.get("transforms", []))
    lines.extend(transform_lines)

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


def _expression_to_asql(expr: Union[Dict[str, Any], str]) -> str:
    """Convert JSON expression to ASQL text.
    
    Args:
        expr: Either a dict with 'type' field for structured expressions,
              or a plain string that gets returned as-is.
    """
    if not expr:
        return ""
    
    # If it's already a string (plain SQL condition), return as-is
    if isinstance(expr, str):
        return expr

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

    elif expr_type == "binary" or expr_type == "binary_op":
        left = _expression_to_asql(expr.get("left", {}))
        right = _expression_to_asql(expr.get("right", {}))
        # Support both 'op' (generator format) and 'operator' (legacy format)
        operator = expr.get("op") or expr.get("operator", "=")

        # Convert SQL = to ASQL ==
        if operator == "=":
            operator = "=="

        # AND/OR don't need parentheses - ASQL handles precedence correctly
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


# ============================================================================
# Validation Functions
# ============================================================================

class PipelineValidationError(Exception):
    """Exception raised for pipeline validation errors."""
    pass


def validate_pipelines(pipelines: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[str]:
    """
    Validate pipeline JSON for common errors.

    Args:
        pipelines: Pipeline(s) to validate

    Returns:
        List of warning/error messages (empty if valid)
    """
    if isinstance(pipelines, dict):
        pipelines = [pipelines]

    if not pipelines:
        return ["No pipelines provided"]

    errors: List[str] = []

    # Track defined pipeline names for reference validation
    defined_names: List[str] = []

    for i, pipeline in enumerate(pipelines):
        pipeline_label = f"Pipeline {i + 1}"
        name = pipeline.get("name")

        # Validate pipeline name format
        if name:
            if not _is_valid_identifier(name):
                errors.append(
                    f"{pipeline_label}: Invalid pipeline name '{name}'. "
                    "Use only letters, numbers, and underscores."
                )
            if name in defined_names:
                errors.append(
                    f"{pipeline_label}: Duplicate pipeline name '{name}'. "
                    "Each CTE must have a unique name."
                )
            defined_names.append(name)

        # Validate FROM clause
        from_clause = pipeline.get("from", {})
        table = from_clause.get("table", "")

        if not table:
            errors.append(f"{pipeline_label}: Missing FROM table")

        # Check if FROM references an undefined pipeline
        if table and table in defined_names:
            # Valid reference to previous pipeline
            pass
        elif table and _looks_like_cte_reference(table, defined_names):
            # Might be referencing a pipeline defined later
            pass

        # Validate set_operation on non-last pipeline
        set_op = pipeline.get("set_operation")
        if set_op and i == len(pipelines) - 1:
            errors.append(
                f"{pipeline_label}: set_operation should not be on the last pipeline"
            )

    # Check for circular references (basic check)
    circular_errors = _check_circular_references(pipelines)
    errors.extend(circular_errors)

    return errors


def _is_valid_identifier(name: str) -> bool:
    """Check if name is a valid SQL identifier."""
    if not name:
        return False
    # Must start with letter or underscore
    if not (name[0].isalpha() or name[0] == '_'):
        return False
    # Rest must be alphanumeric or underscore
    return all(c.isalnum() or c == '_' for c in name)


def _looks_like_cte_reference(table: str, defined_names: List[str]) -> bool:
    """Check if table name looks like it could be a CTE reference."""
    # If it's a simple identifier (no dots), it could be a CTE
    return '.' not in table and _is_valid_identifier(table)


def _check_circular_references(pipelines: List[Dict[str, Any]]) -> List[str]:
    """
    Check for circular references between pipelines.

    A circular reference occurs when pipeline A references pipeline B,
    and pipeline B (directly or indirectly) references pipeline A.
    """
    errors: List[str] = []

    # Build dependency graph
    # name -> set of names it references
    dependencies: Dict[str, set] = {}
    name_to_idx: Dict[str, int] = {}

    for i, pipeline in enumerate(pipelines):
        name = pipeline.get("name")
        if not name:
            continue

        name_to_idx[name] = i
        deps: set = set()

        # Check FROM clause
        from_table = pipeline.get("from", {}).get("table", "")
        if from_table and _is_valid_identifier(from_table):
            deps.add(from_table)

        # Check JOIN transforms
        for transform in pipeline.get("transforms", []):
            if transform.get("type") == "join":
                join_table = transform.get("table", "")
                if join_table and _is_valid_identifier(join_table):
                    deps.add(join_table)

        dependencies[name] = deps

    # Check for cycles using DFS
    visited: set = set()
    rec_stack: set = set()

    def has_cycle(name: str, path: List[str]) -> bool:
        if name in rec_stack:
            cycle_start = path.index(name)
            cycle = path[cycle_start:] + [name]
            errors.append(
                f"Circular reference detected: {' -> '.join(cycle)}"
            )
            return True

        if name in visited:
            return False

        visited.add(name)
        rec_stack.add(name)
        path.append(name)

        for dep in dependencies.get(name, set()):
            if dep in dependencies:  # Only check if it's a defined pipeline
                if has_cycle(dep, path):
                    return True

        path.pop()
        rec_stack.remove(name)
        return False

    for name in dependencies:
        if name not in visited:
            has_cycle(name, [])

    return errors
