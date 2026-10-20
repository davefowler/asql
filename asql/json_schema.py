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
    - raw: ASQL text for a whole pipeline the visual form cannot model
    - from.raw: ASQL text for a FROM source that is not a plain table

Names versus expressions:
    Fields that hold a *name* (from.table, join.table, column nodes, aliases,
    dimension strings, order-by columns, aggregate columns, except/rename
    columns) are raw, unquoted identifiers; anything that is not a plain
    identifier is backtick-quoted here. Fields that hold an *expression*
    (``expression`` keys and ``raw`` nodes) are ASQL text pasted verbatim.
"""

import re
from typing import Any

_PLAIN_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(r"-?\d+(\.\d+)?")

# A string in a name slot that contains one of these can only be expression
# text (hand-written JSON such as {"dimensions": ["month(created_at)"]}) and is
# pasted as written. Dashes, dots and spaces are left for names.
_EXPRESSION_CHARS = frozenset("()[]{}+*/<>=!'\"`,:;?|&%#@~^$")

# Binary operator precedence, highest binds tightest. Children of lower
# precedence are parenthesized so a hand-built tree keeps its shape.
_PRECEDENCE: dict[str, int] = {
    "OR": 1,
    "AND": 2,
    "=": 4,
    "==": 4,
    "!=": 4,
    "<>": 4,
    "<": 4,
    ">": 4,
    "<=": 4,
    ">=": 4,
    "||": 5,
    "+": 6,
    "-": 6,
    "*": 7,
    "/": 7,
    "%": 7,
}
# `a + (b + c)` may drop its parentheses; `a * (b / c)` and `a - (b - c)` may not.
_ASSOCIATIVE = frozenset({"AND", "OR", "+", "*", "||"})
# Structured comparison-like nodes bind like comparisons.
_COMPARISON_NODES = frozenset(
    {
        "in",
        "not_in",
        "like",
        "ilike",
        "matches",
        "between",
        "null_check",
        "contains",
        "icontains",
        "starts_with",
        "istarts_with",
        "ends_with",
        "iends_with",
    }
)


def quote_identifier(name: str) -> str:
    """Backtick-quote a single identifier unless it is plain."""
    if _PLAIN_IDENTIFIER.fullmatch(name):
        return name
    return "`" + name.replace("`", "``") + "`"


def _name_sql(name: Any) -> str:
    """ASQL for a name slot: `col`, `t.col`, `db.table`, `t.*`, or expression text."""
    text = str(name).strip()
    if not text or text == "*":
        return text
    if "`" in text:
        return text  # already quoted by the writer
    if _NUMBER.fullmatch(text) or any(c in _EXPRESSION_CHARS for c in text):
        return text  # expression text, pasted verbatim
    parts = text.split(".")
    if parts[-1] == "*":
        return ".".join(quote_identifier(p) for p in parts[:-1]) + ".*"
    return ".".join(quote_identifier(p) for p in parts)


def _table_sql(table: Any, alias: Any = None) -> str:
    text = _name_sql(table)
    if alias:
        text = f"{text} as {quote_identifier(str(alias))}"
    return text


def json_to_asql(query_json: dict[str, Any] | list[dict[str, Any]]) -> str:
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
    pipelines = [query_json] if isinstance(query_json, dict) else query_json

    if not pipelines:
        return "from # Enter table name"

    result_lines: list[str] = []

    for i, pipeline in enumerate(pipelines):
        from_clause = pipeline.get("from", {})
        from_table = (
            from_clause.get("table", "") if isinstance(from_clause, dict) else ""
        )
        name = pipeline.get("name")

        # Check if this pipeline continues from a CTE we just created
        # If so, we don't need a new FROM - just continue the pipeline
        previous = pipelines[i - 1] if i > 0 else None
        is_continuation = (
            previous is not None
            and bool(previous.get("name"))
            and from_table == previous.get("name")
            and not pipeline.get("raw")
            and not (isinstance(from_clause, dict) and from_clause.get("alias"))
        )

        if is_continuation:
            # Continue the pipeline - just add transforms (no FROM)
            transforms_lines = _transforms_to_asql_lines(pipeline.get("transforms", []))
            result_lines.extend(transforms_lines)
        else:
            # Start a new pipeline with FROM
            # Handle set operations (UNION, INTERSECT, EXCEPT) before this pipeline
            set_op = previous.get("set_operation") if previous else None
            if set_op:
                op_type = set_op.get("type", "union").upper()
                if set_op.get("all"):
                    op_type += " ALL"
                result_lines.append(op_type)
            elif previous is not None and previous.get("name"):
                # `stash as x` then a fresh `from`: the CTEs carry over
                result_lines.append("")
            elif previous is not None:
                # Independent pipelines are separate statements
                result_lines.append(";")

            pipeline_asql = _pipeline_to_asql(pipeline)
            result_lines.append(pipeline_asql)

        # Add stash for named pipelines (CTEs)
        if name:
            result_lines.append(f"  stash as {quote_identifier(str(name))}")

    return "\n".join(result_lines)


def _transforms_to_asql_lines(transforms: list[dict[str, Any]]) -> list[str]:
    """Convert transforms list to ASQL lines (without FROM clause)."""
    lines: list[str] = []

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
            join_table = _table_sql(transform.get("table", ""), transform.get("alias"))
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
                col_names = [_name_sql(_column_entry_name(c)) for c in columns]
                lines.append(f"  except {', '.join(col_names)}")

        # === AGGREGATE TRANSFORMS ===
        elif transform_type == "group_by":
            dimensions = transform.get("dimensions", [])
            aggregates = transform.get("aggregates", [])

            if dimensions:
                dims_str = ", ".join(_dimension_to_asql(d) for d in dimensions)

                if aggregates:
                    # Use ASQL's inline aggregate syntax
                    agg_strs = [_aggregate_to_asql(agg) for agg in aggregates]
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
                order_parts = [_ordered_to_asql(expr) for expr in expressions]
                lines.append(f"  order by {', '.join(order_parts)}")

        # === UTILITY TRANSFORMS ===
        elif transform_type == "limit":
            lines.append(f"  limit {_count_to_asql(transform, 10)}")

        elif transform_type == "offset":
            lines.append(f"  offset {_count_to_asql(transform, 0)}")

        elif transform_type == "distinct":
            lines.append("  distinct")

        elif transform_type == "sample":
            size = transform.get("size", 100)
            per = transform.get("per")
            if per:
                lines.append(f"  sample {size} per {_name_sql(per)}")
            else:
                lines.append(f"  sample {size}")

        elif transform_type == "pivot":
            aggregate = str(transform.get("aggregate", "")).strip()
            column = _name_sql(transform.get("column", ""))
            values = transform.get("values") or []
            line = f"  pivot {aggregate} by {column}"
            if values:
                value_strs = [_expression_to_asql(v) for v in values]
                line += f" values ({', '.join(value_strs)})"
            lines.append(line)

        elif transform_type == "unpivot":
            columns = [
                _name_sql(_column_entry_name(c)) for c in transform.get("columns", [])
            ]
            name = quote_identifier(str(transform.get("name", "name")))
            value = quote_identifier(str(transform.get("value", "value")))
            lines.append(f"  unpivot {', '.join(columns)} into {name}, {value}")

        elif transform_type == "stash":
            name = transform.get("name", "cte")
            lines.append(f"  stash as {quote_identifier(str(name))}")

        elif transform_type == "deduplicate":
            columns = transform.get("columns", [])
            if columns:
                col_names = [_name_sql(_column_entry_name(c)) for c in columns]
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
                    rename_strs.append(
                        f"{_name_sql(old_name)} as {quote_identifier(str(new_name))}"
                    )
                lines.append(f"  rename {', '.join(rename_strs)}")

        elif transform_type == "replace":
            columns = transform.get("columns", [])
            if columns:
                replace_strs = []
                for col in columns:
                    if isinstance(col, dict):
                        name = _name_sql(col.get("name", ""))
                        expression = col.get("expression") or col.get("name", "")
                        replace_strs.append(f"{name} with {expression}")
                    else:
                        replace_strs.append(str(col))
                lines.append(f"  replace {', '.join(replace_strs)}")

        elif transform_type == "explode":
            column = _name_sql(transform.get("column", ""))
            alias = transform.get("alias")
            if alias:
                lines.append(f"  explode {column} as {quote_identifier(str(alias))}")
            else:
                lines.append(f"  explode {column}")

        # === WINDOW TRANSFORMS ===
        elif transform_type == "per":
            columns = transform.get("columns", [])
            if columns:
                col_names = [_name_sql(_column_entry_name(c)) for c in columns]
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

        # === VERBATIM ===
        elif transform_type == "raw":
            text = str(transform.get("asql", "")).strip()
            if text:
                lines.append(f"  {text}")

    return lines


def _pipeline_to_asql(pipeline: dict[str, Any]) -> str:
    """Convert a single pipeline to ASQL text (including FROM clause)."""
    raw = pipeline.get("raw")
    if raw:
        return str(raw).strip()

    lines: list[str] = []

    # FROM clause
    from_clause = pipeline.get("from", {})
    if not isinstance(from_clause, dict):
        from_clause = {}
    table = from_clause.get("table", "")
    source = from_clause.get("raw")
    if source:
        lines.append(f"from {str(source).strip()}")
    elif table:
        lines.append(f"from {_table_sql(table, from_clause.get('alias'))}")
    else:
        return "from # Enter table name"

    # Add transforms
    transform_lines = _transforms_to_asql_lines(pipeline.get("transforms", []))
    lines.extend(transform_lines)

    return "\n".join(lines)


def _column_entry_name(col: Any) -> str:
    return str(col.get("name", "")) if isinstance(col, dict) else str(col)


def _columns_to_asql(columns: list[Any]) -> list[str]:
    """Convert column list (select/extend) to ASQL strings.

    {"name": n}: a column name, `t.n` with {"source": t}. {"expression": e,
    "name": n}: `e as n`, except when the expression is the column itself
    (`t.n`, `t.*`, or equal to n).
    """
    column_strs = []
    for col in columns:
        if isinstance(col, dict):
            expression = col.get("expression")
            name = col.get("name")
            source = col.get("source")
            if not expression and source and name and name != "*":
                column_strs.append(f"{_name_sql(source)}.{_name_sql(name)}")
            elif expression:
                expression = str(expression).strip()
                if (
                    not name
                    or name == expression
                    or expression.endswith("*")
                    or (
                        expression.endswith(f".{name}")
                        and _name_sql(expression) == expression
                    )
                ):
                    column_strs.append(expression)
                else:
                    column_strs.append(f"{expression} as {quote_identifier(str(name))}")
            else:
                column_strs.append(_name_sql(name or ""))
        else:
            column_strs.append(_name_sql(col))
    return column_strs


def _dimension_to_asql(dim: Any) -> str:
    """A GROUP BY key: a name string or {"expression": ..., "alias": ...}."""
    if isinstance(dim, dict):
        expression = dim.get("expression")
        text = str(expression).strip() if expression else _name_sql(dim.get("name", ""))
        alias = dim.get("alias")
        if alias:
            text = f"{text} as {quote_identifier(str(alias))}"
        return text
    return _name_sql(dim)


def _aggregate_to_asql(agg: dict[str, Any]) -> str:
    """One aggregate block entry."""
    alias = agg.get("alias")
    expression = agg.get("expression")
    if expression:
        text = str(expression).strip()
    else:
        func = agg.get("function", "count")
        col = str(agg.get("column") or "*").strip()  # Empty string -> *
        distinct = bool(agg.get("distinct"))
        if col.lower().startswith("distinct "):
            col, distinct = col[len("distinct ") :].strip(), True
        col_sql = _name_sql(col)
        text = f"{func}({'distinct ' if distinct else ''}{col_sql})"
        if not alias:
            alias = f"{func}_{col}" if col != "*" else None
    if alias:
        return f"{text} as {quote_identifier(str(alias))}"
    return text


def _ordered_to_asql(expr: dict[str, Any]) -> str:
    """One ORDER BY key with ASQL's - prefix for descending."""
    if expr.get("type") == "raw":
        return str(expr.get("asql", "")).strip()
    expression = expr.get("expression")
    key = str(expression).strip() if expression else _name_sql(expr.get("column", ""))
    direction = expr.get("direction", "asc")
    nulls = (expr.get("nulls") or "").lower()
    if direction == "desc":
        # `-key` reads back as NULLS LAST; spell out NULLS FIRST explicitly.
        if nulls == "first":
            return f"{key} DESC NULLS FIRST"
        return f"-{key}"
    if nulls == "last":
        return f"{key} NULLS LAST"
    return key


def _count_to_asql(transform: dict[str, Any], default: int) -> str:
    expression = transform.get("expression")
    if expression:
        return str(expression).strip()
    count = transform.get("count")
    return str(default if count is None else count)


def _string_literal(value: Any) -> str:
    """An ASQL string literal; double quotes unless the value contains one."""
    text = str(value)
    if '"' not in text:
        return f'"{text}"'
    return "'" + text.replace("'", "''") + "'"


def _binary_operand(parent_op: str, operand: dict[str, Any] | str, right: bool) -> str:
    """Render a binary operator's child, parenthesized if it binds looser."""
    text = _expression_to_asql(operand)
    if not isinstance(operand, dict):
        return text
    parent_prec = _PRECEDENCE.get(parent_op.upper(), 4)
    child_type = operand.get("type")
    if child_type in ("binary", "binary_op"):
        child_op = str(operand.get("op") or operand.get("operator", "=")).upper()
        child_prec = _PRECEDENCE.get(child_op, 4)
        same_associative_op = child_op == parent_op.upper() and child_op in _ASSOCIATIVE
        if child_prec < parent_prec or (
            child_prec == parent_prec
            and (right or parent_prec == 4)
            and not same_associative_op
        ):
            return f"({text})"
    elif child_type in _COMPARISON_NODES and parent_prec >= 4:
        return f"({text})"
    return text


def _expression_to_asql(expr: dict[str, Any] | str) -> str:
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
        name = str(expr.get("name", ""))
        name_sql = "*" if name == "*" else quote_identifier(name)
        if table:
            return f"{_name_sql(table)}.{name_sql}"
        return name_sql

    elif expr_type == "star":
        return "*"

    elif expr_type == "literal":
        value = expr.get("value", "")
        data_type = expr.get("data_type", "string")

        if value is None:
            return "null"
        if data_type == "string":
            return _string_literal(value)
        elif data_type == "number":
            return str(value)
        elif data_type == "boolean":
            return str(value).lower()
        elif data_type == "null":
            return "null"
        else:
            # Fallback: treat as string
            return _string_literal(value)

    elif expr_type == "paren":
        return f"({_expression_to_asql(expr.get('expression', {}))})"

    elif expr_type == "binary" or expr_type == "binary_op":
        # Support both 'op' (generator format) and 'operator' (legacy format)
        operator = str(expr.get("op") or expr.get("operator", "="))
        left = _binary_operand(operator, expr.get("left", {}), right=False)
        right = _binary_operand(operator, expr.get("right", {}), right=True)

        # Convert SQL = to ASQL ==
        if operator == "=":
            operator = "=="

        return f"{left} {operator} {right}"

    elif expr_type == "unary_op":
        operand_json = expr.get("operand", {})
        operand = _expression_to_asql(operand_json)
        operator = expr.get("operator", "")
        if operator == "not":
            return f"not ({operand})"
        child_type = (
            operand_json.get("type") if isinstance(operand_json, dict) else None
        )
        if child_type in ("binary", "binary_op") or child_type in _COMPARISON_NODES:
            operand = f"({operand})"
        return f"-{operand}" if operator == "-" else f"{operator} {operand}"

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

    # LIKE / ILIKE operators (SQL patterns, kept as LIKE)
    elif expr_type in ("like", "ilike"):
        operand = _expression_to_asql(expr.get("operand", {}))
        pattern = _expression_to_asql(expr.get("pattern", {}))
        negate = "not " if expr.get("negate") else ""
        return f"{operand} {negate}{expr_type} {pattern}"

    # MATCHES operator (regex)
    elif expr_type == "matches":
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
        distinct = "distinct " if expr.get("distinct") else ""
        return f"{name}({distinct}{', '.join(arg_strs)})"

    # Verbatim ASQL text for anything the visual form cannot model
    elif expr_type == "raw":
        return str(expr.get("asql", "")).strip()

    elif expr_type == "unknown":
        # Legacy spelling of `raw`
        return str(expr.get("value", "")).strip()

    else:
        return ""


# ============================================================================
# Validation Functions
# ============================================================================


def validate_pipelines(pipelines: dict[str, Any] | list[dict[str, Any]]) -> list[str]:
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

    errors: list[str] = []

    # Track defined pipeline names for reference validation
    defined_names: list[str] = []

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
        table = from_clause.get("table", "") or from_clause.get("raw", "")

        if not table and not pipeline.get("raw"):
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
    if not (name[0].isalpha() or name[0] == "_"):
        return False
    # Rest must be alphanumeric or underscore
    return all(c.isalnum() or c == "_" for c in name)


def _looks_like_cte_reference(table: str, defined_names: list[str]) -> bool:
    """Check if table name looks like it could be a CTE reference."""
    # If it's a simple identifier (no dots), it could be a CTE
    return "." not in table and _is_valid_identifier(table)


def _check_circular_references(pipelines: list[dict[str, Any]]) -> list[str]:
    """
    Check for circular references between pipelines.

    A circular reference occurs when pipeline A references pipeline B,
    and pipeline B (directly or indirectly) references pipeline A.
    """
    errors: list[str] = []

    # Build dependency graph
    # name -> set of names it references
    dependencies: dict[str, set[str]] = {}
    name_to_idx: dict[str, int] = {}

    for i, pipeline in enumerate(pipelines):
        name = pipeline.get("name")
        if not name:
            continue

        name_to_idx[name] = i
        deps: set[str] = set()

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
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def has_cycle(name: str, path: list[str]) -> bool:
        if name in rec_stack:
            cycle_start = path.index(name)
            cycle = path[cycle_start:] + [name]
            errors.append(f"Circular reference detected: {' -> '.join(cycle)}")
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
