"""
VisualASQLGenerator - Generates JSON representation from SQLGlot AST.

This generator outputs a structured JSON format suitable for visual query builders,
with column tracking at each pipeline stage.

Output format is always an array of pipelines:
    [
        {"name": "cte_name", "from": {...}, "transforms": [...], "set_operation": {...}},
        {"name": null, "from": {...}, "transforms": [...]}
    ]
"""

import json
import typing as t

from sqlglot import exp
from sqlglot.generator import Generator
from sqlglot.schema import MappingSchema
from sqlglot.optimizer.qualify_columns import qualify_columns
from sqlglot.optimizer.annotate_types import annotate_types

class VisualASQLGenerator(Generator):
    """Generator that outputs JSON array of pipelines with column tracking."""

    # Declarative mappings per .cursorrules - use dicts instead of elif chains
    _SIDE_JOIN_MAP: t.ClassVar[t.Dict[str, str]] = {
        "LEFT": "left",
        "RIGHT": "right",
        "FULL": "full",
    }

    _KIND_JOIN_MAP: t.ClassVar[t.Dict[str, str]] = {
        "CROSS": "cross",
        "INNER": "inner",
        "LEFT": "left",
        "RIGHT": "right",
        "FULL": "full",
    }

    _BINARY_OP_MAP: t.ClassVar[t.Dict[t.Type[exp.Expression], str]] = {
        exp.EQ: "=",
        exp.NEQ: "!=",
        exp.LT: "<",
        exp.GT: ">",
        exp.LTE: "<=",
        exp.GTE: ">=",
    }

    _SET_OP_MAP: t.ClassVar[t.Dict[t.Type[exp.Expression], str]] = {
        exp.Union: "union",
        exp.Intersect: "intersect",
        exp.Except: "except",
    }

    def __init__(self, schema: t.Optional[MappingSchema] = None, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._schema = schema

    def generate(
        self, expression: exp.Expression, copy: bool = True
    ) -> str:
        """Generate JSON string from AST - always outputs array format."""
        if copy:
            expression = expression.copy()

        # Build JSON structure (always an array)
        result = self._build_pipelines(expression)

        return json.dumps(result, indent=2)

    def _build_pipelines(self, expression: exp.Expression) -> t.List[t.Dict[str, t.Any]]:
        """Build array of pipeline representations."""
        pipelines: t.List[t.Dict[str, t.Any]] = []

        # Handle CTEs (WITH clause) - note: SQLGlot uses 'with_' not 'with'
        if isinstance(expression, exp.Select) and expression.args.get("with_"):
            with_clause = expression.args["with_"]
            for cte in with_clause.expressions:
                cte_name = cte.alias
                cte_query = cte.this
                if isinstance(cte_query, exp.Select):
                    pipeline = self._build_single_pipeline(cte_query)
                    pipeline["name"] = cte_name
                    pipelines.append(pipeline)

        # Handle set operations (UNION, INTERSECT, EXCEPT)
        if isinstance(expression, (exp.Union, exp.Intersect, exp.Except)):
            self._build_set_operation_pipelines(expression, pipelines)
        elif isinstance(expression, exp.Select):
            # Pre-qualify columns if schema provided
            if self._schema:
                try:
                    expression = qualify_columns(
                        expression,
                        schema=self._schema,
                        expand_stars=True
                    )
                    expression = annotate_types(expression, schema=self._schema)
                except (ValueError, KeyError, AttributeError):
                    # Schema lookup/qualification can fail for various reasons
                    # (missing tables, SELECT *, complex expressions, etc.)
                    pass
                except Exception:
                    # Catch other sqlglot optimizer errors (e.g., OptimizeError)
                    pass

            pipeline = self._build_single_pipeline(expression)
            pipeline["name"] = None  # Final output pipeline
            pipelines.append(pipeline)
        else:
            # Unsupported expression type
            pipelines.append({
                "name": None,
                "from": {"table": "", "error": f"Unsupported: {type(expression).__name__}"},
                "transforms": []
            })

        return pipelines

    def _build_set_operation_pipelines(
        self,
        expression: exp.Expression,
        pipelines: t.List[t.Dict[str, t.Any]]
    ) -> None:
        """Recursively build pipelines for set operations."""
        if isinstance(expression, (exp.Union, exp.Intersect, exp.Except)):
            # Process left side
            left = expression.this
            if isinstance(left, (exp.Union, exp.Intersect, exp.Except)):
                self._build_set_operation_pipelines(left, pipelines)
            elif isinstance(left, exp.Select):
                pipeline = self._build_single_pipeline(left)
                pipeline["name"] = None

                # Add set operation info
                op_type = self._SET_OP_MAP.get(type(expression), "union")
                is_all = expression.args.get("distinct") is False
                pipeline["set_operation"] = {"type": op_type, "all": is_all}

                pipelines.append(pipeline)

            # Process right side
            right = expression.expression
            if isinstance(right, (exp.Union, exp.Intersect, exp.Except)):
                self._build_set_operation_pipelines(right, pipelines)
            elif isinstance(right, exp.Select):
                pipeline = self._build_single_pipeline(right)
                pipeline["name"] = None
                pipelines.append(pipeline)

    def _build_single_pipeline(self, expression: exp.Select) -> t.Dict[str, t.Any]:
        """Build JSON representation of a single SELECT query."""
        if not isinstance(expression, exp.Select):
            return {"from": {"table": "", "error": f"Expected Select, got {type(expression).__name__}"}, "transforms": []}

        result: t.Dict[str, t.Any] = {"name": None, "from": None, "transforms": []}
        current_columns: t.List[t.Dict[str, t.Any]] = []
        transform_id = 0

        # Pre-extract column references from the query for fallback when no schema
        inferred_columns_by_table = self._extract_columns_from_query(expression)

        # Extract top-level comments from the SELECT statement
        pipeline_comments = self._get_comments(expression)
        if pipeline_comments:
            result["comments"] = pipeline_comments

        # FROM clause (uses 'from_' because 'from' is a Python keyword)
        if from_clause := expression.args.get("from_"):
            table_expr = from_clause.this
            if table_expr:
                table_name = self._get_table_name(table_expr)
                table_alias = self._get_alias(table_expr)
                table_cols = self._get_table_columns(table_name)
                
                # If no schema columns, use inferred columns from query
                if not table_cols:
                    # Get columns for this table (try both name and alias)
                    table_cols = inferred_columns_by_table.get(table_name, [])
                    if table_alias and table_alias != table_name:
                        table_cols = table_cols + inferred_columns_by_table.get(table_alias, [])
                    # Deduplicate by name
                    seen = set()
                    unique_cols = []
                    for col in table_cols:
                        if col["name"] not in seen:
                            seen.add(col["name"])
                            unique_cols.append(col)
                    table_cols = unique_cols
                
                current_columns = table_cols.copy()

                from_comments = self._get_comments(from_clause) or self._get_comments(table_expr)
                result["from"] = {
                    "table": table_name,
                    "alias": table_alias if table_alias != table_name else None,
                    "output_columns": table_cols,
                }
                if from_comments:
                    result["from"]["comments"] = from_comments

        # JOINs - accumulate columns
        for join in expression.args.get("joins") or []:
            join_table_expr = join.this
            join_table = self._get_table_name(join_table_expr)
            join_alias = self._get_alias(join_table_expr)
            join_cols = self._get_table_columns(join_table)
            
            # If no schema columns, use inferred columns from query
            if not join_cols:
                join_cols = inferred_columns_by_table.get(join_table, [])
                if join_alias and join_alias != join_table:
                    join_cols = join_cols + inferred_columns_by_table.get(join_alias, [])
                # Deduplicate by name
                seen = set()
                unique_cols = []
                for col in join_cols:
                    if col["name"] not in seen:
                        seen.add(col["name"])
                        unique_cols.append(col)
                join_cols = unique_cols
            
            current_columns.extend(join_cols)

            join_type = self._get_join_type(join)
            condition = None
            if on_clause := join.args.get("on"):
                condition = self._expression_to_json(on_clause)

            transform: t.Dict[str, t.Any] = {
                "id": f"t{transform_id}",
                "type": "join",
                "join_type": join_type,
                "table": join_table,
                "alias": join_alias if join_alias != join_table else None,
                "condition": condition,
                "output_columns": current_columns.copy(),
            }
            if comments := self._get_comments(join):
                transform["comments"] = comments
            result["transforms"].append(transform)
            transform_id += 1

        # WHERE - columns unchanged
        if where := expression.args.get("where"):
            transform = {
                "id": f"t{transform_id}",
                "type": "where",
                "condition": self._expression_to_json(where.this),
                "output_columns": current_columns.copy(),
            }
            # Collect all comments from the WHERE clause and its condition tree
            if comments := self._collect_all_comments(where):
                transform["comments"] = comments
            result["transforms"].append(transform)
            transform_id += 1

        # GROUP BY - columns change to dimensions + aggregates
        if group := expression.args.get("group"):
            dims, aggs = self._extract_group_by_columns(expression, group)
            current_columns = dims + aggs

            transform = {
                "id": f"t{transform_id}",
                "type": "group_by",
                "dimensions": [d["name"] for d in dims],
                "aggregates": [
                    {
                        "function": a.get("function", ""),
                        "column": a.get("source_column", ""),
                        "alias": a["name"],
                    }
                    for a in aggs
                ],
                "output_columns": current_columns.copy(),
            }
            if comments := self._get_comments(group):
                transform["comments"] = comments
            result["transforms"].append(transform)
            transform_id += 1

        # SELECT - explicit columns (only if not SELECT *)
        elif exprs := expression.args.get("expressions"):
            if not self._is_select_star(exprs):
                select_cols = self._extract_select_columns(exprs)
                current_columns = select_cols

                # Collect comments from individual select expressions
                select_comments: t.List[str] = []
                for expr in exprs:
                    if expr_comments := self._get_comments(expr):
                        select_comments.extend(expr_comments)

                transform = {
                    "id": f"t{transform_id}",
                    "type": "select",
                    "columns": [
                        {"name": c["name"], "expression": c.get("expression")}
                        for c in select_cols
                    ],
                    "output_columns": current_columns.copy(),
                }
                if select_comments:
                    transform["comments"] = select_comments
                result["transforms"].append(transform)
                transform_id += 1

        # HAVING - columns unchanged
        if having := expression.args.get("having"):
            transform = {
                "id": f"t{transform_id}",
                "type": "having",
                "condition": self._expression_to_json(having.this),
                "output_columns": current_columns.copy(),
            }
            if comments := self._get_comments(having):
                transform["comments"] = comments
            result["transforms"].append(transform)
            transform_id += 1

        # ORDER BY - columns unchanged
        if order := expression.args.get("order"):
            transform = {
                "id": f"t{transform_id}",
                "type": "order_by",
                "expressions": self._extract_order_columns(order),
                "output_columns": current_columns.copy(),
            }
            if comments := self._get_comments(order):
                transform["comments"] = comments
            result["transforms"].append(transform)
            transform_id += 1

        # LIMIT - columns unchanged (only if count was successfully parsed)
        if limit := expression.args.get("limit"):
            count = self._extract_limit_value(limit)
            if count is not None:
                transform = {
                    "id": f"t{transform_id}",
                    "type": "limit",
                    "count": count,
                    "output_columns": current_columns.copy(),
                }
                if comments := self._get_comments(limit):
                    transform["comments"] = comments
                result["transforms"].append(transform)
                transform_id += 1

        # OFFSET - columns unchanged
        if offset := expression.args.get("offset"):
            offset_val = self._extract_offset_value(offset)
            transform = {
                "id": f"t{transform_id}",
                "type": "offset",
                "count": offset_val,
                "output_columns": current_columns.copy(),
            }
            if comments := self._get_comments(offset):
                transform["comments"] = comments
            result["transforms"].append(transform)
            transform_id += 1

        return result

    def _get_table_name(self, table_expr: exp.Expression) -> str:
        """Extract table name from expression."""
        if isinstance(table_expr, exp.Table):
            return table_expr.name
        if hasattr(table_expr, "name"):
            return str(table_expr.name)
        return str(table_expr)

    def _get_alias(self, table_expr: exp.Expression) -> t.Optional[str]:
        """Extract alias from table expression."""
        if isinstance(table_expr, exp.Table) and table_expr.alias:
            return table_expr.alias
        return None

    def _get_comments(self, expr: exp.Expression) -> t.Optional[t.List[str]]:
        """Extract comments from an expression node."""
        if hasattr(expr, "comments") and expr.comments:
            # Clean up comments (strip whitespace, remove empty ones)
            cleaned = [c.strip() for c in expr.comments if c and c.strip()]
            return cleaned if cleaned else None
        return None

    def _collect_all_comments(self, expr: exp.Expression) -> t.List[str]:
        """Recursively collect all comments from an expression tree."""
        comments: t.List[str] = []
        
        def collect(node: exp.Expression) -> None:
            if hasattr(node, "comments") and node.comments:
                for c in node.comments:
                    if c and c.strip():
                        comments.append(c.strip())
            for child in node.iter_expressions():
                collect(child)
        
        collect(expr)
        return comments

    def _get_table_columns(self, table_name: str) -> t.List[t.Dict[str, t.Any]]:
        """Get columns for a table from schema."""
        if not self._schema:
            return []

        try:
            table_expr = exp.to_table(table_name)
            cols = self._schema.column_names(table_expr)
            result = []
            for col in cols:
                col_type = self._schema.get_column_type(
                    table_expr, 
                    exp.column(col)
                )
                type_str = str(col_type) if col_type else "UNKNOWN"
                result.append({
                    "name": col,
                    "type": type_str,
                    "source": table_name,
                })
            return result
        except (KeyError, AttributeError, TypeError, ValueError):
            # Schema lookup can fail for missing tables, invalid column refs, etc.
            return []

    def _extract_columns_from_query(
        self, expression: exp.Select
    ) -> t.Dict[str, t.List[t.Dict[str, t.Any]]]:
        """Extract all column references from a query, grouped by table.
        
        This provides a fallback for column info when no schema is available.
        We scan SELECT, GROUP BY, ORDER BY, WHERE, and JOIN ON clauses
        to find all referenced columns.
        """
        columns_by_table: t.Dict[str, t.List[t.Dict[str, t.Any]]] = {}
        
        # Get the FROM table name to use as default for unqualified columns
        from_table_name: t.Optional[str] = None
        if from_clause := expression.args.get("from_"):
            if table_expr := from_clause.this:
                from_table_name = self._get_table_name(table_expr)
        
        # Also collect all table names/aliases for reference
        all_tables: t.Set[str] = set()
        if from_table_name:
            all_tables.add(from_table_name)
        for join in expression.args.get("joins") or []:
            if join.this:
                join_table = self._get_table_name(join.this)
                all_tables.add(join_table)
                if alias := self._get_alias(join.this):
                    all_tables.add(alias)
        
        def add_column(table: t.Optional[str], name: str) -> None:
            """Add a column reference to the appropriate table."""
            if not name:
                return
            # If no table specified and we have a single FROM table, use it
            # Otherwise use "_unqualified_" bucket
            if table:
                source = table
            elif from_table_name and len(all_tables) == 1:
                # Single table query - unqualified columns belong to FROM table
                source = from_table_name
            else:
                # Multi-table query - keep unqualified separate
                source = "_unqualified_"
            
            if source not in columns_by_table:
                columns_by_table[source] = []
            # Check if already exists
            for existing in columns_by_table[source]:
                if existing["name"] == name:
                    return
            columns_by_table[source].append({
                "name": name,
                "source": source if source != "_unqualified_" else None,
            })
        
        def extract_from_expression(expr: t.Optional[exp.Expression]) -> None:
            """Recursively extract column references from an expression."""
            if expr is None:
                return
            if isinstance(expr, exp.Column):
                add_column(expr.table, expr.name)
            # Recurse into child expressions
            for child in expr.iter_expressions():
                extract_from_expression(child)
        
        # Extract from SELECT expressions
        for select_expr in expression.args.get("expressions") or []:
            extract_from_expression(select_expr)
        
        # Extract from WHERE clause
        if where := expression.args.get("where"):
            extract_from_expression(where)
        
        # Extract from GROUP BY clause
        if group := expression.args.get("group"):
            for group_expr in group.expressions:
                extract_from_expression(group_expr)
        
        # Extract from ORDER BY clause
        if order := expression.args.get("order"):
            for order_expr in order.expressions:
                extract_from_expression(order_expr)
        
        # Extract from HAVING clause
        if having := expression.args.get("having"):
            extract_from_expression(having)
        
        # Extract from JOIN ON conditions
        for join in expression.args.get("joins") or []:
            if on_clause := join.args.get("on"):
                extract_from_expression(on_clause)
        
        # For multi-table queries, distribute unqualified columns to all tables
        # (since we can't know which table they belong to without schema)
        if "_unqualified_" in columns_by_table and len(all_tables) > 1:
            unqualified = columns_by_table.pop("_unqualified_")
            for table in all_tables:
                if table not in columns_by_table:
                    columns_by_table[table] = []
                for col in unqualified:
                    # Add to each table if not already present
                    col_names = {c["name"] for c in columns_by_table[table]}
                    if col["name"] not in col_names:
                        columns_by_table[table].append({
                            "name": col["name"],
                            "source": table,
                        })
        
        return columns_by_table

    def _get_join_type(self, join: exp.Join) -> str:
        """Extract join type from Join expression using declarative dict lookup."""
        kind = join.args.get("kind", "")
        side = join.args.get("side", "")

        if side:
            if join_type := self._SIDE_JOIN_MAP.get(side.upper()):
                return join_type

        if kind:
            if join_type := self._KIND_JOIN_MAP.get(kind.upper()):
                return join_type

        return "inner"

    def _expression_to_json(self, expr: exp.Expression) -> t.Dict[str, t.Any]:
        """Convert SQLGlot expression to JSON representation."""
        if isinstance(expr, exp.Column):
            result: t.Dict[str, t.Any] = {
                "type": "column",
                "name": expr.name,
            }
            if expr.table:
                result["table"] = expr.table
            if hasattr(expr, "type") and expr.type:
                result["data_type"] = str(expr.type)
            return result

        elif isinstance(expr, exp.Literal):
            value = expr.this
            if expr.is_number:
                data_type = "number"
                try:
                    typed_value: t.Any = int(value) if "." not in str(value) else float(value)
                except (ValueError, TypeError):
                    typed_value = value
            else:
                data_type = "string"
                typed_value = value

            return {"type": "literal", "value": typed_value, "data_type": data_type}

        elif isinstance(expr, exp.Boolean):
            return {"type": "literal", "value": expr.this, "data_type": "boolean"}

        elif isinstance(expr, exp.Null):
            return {"type": "literal", "value": None, "data_type": "null"}

        # Binary comparison operators (uses class-level _BINARY_OP_MAP)
        elif isinstance(expr, (exp.EQ, exp.NEQ, exp.LT, exp.GT, exp.LTE, exp.GTE)):
            return {
                "type": "binary",
                "op": self._BINARY_OP_MAP.get(type(expr), "="),
                "left": self._expression_to_json(expr.this),
                "right": self._expression_to_json(expr.expression),
            }

        # Logical operators
        elif isinstance(expr, exp.And):
            return {
                "type": "binary",
                "op": "AND",
                "left": self._expression_to_json(expr.this),
                "right": self._expression_to_json(expr.expression),
            }

        elif isinstance(expr, exp.Or):
            return {
                "type": "binary",
                "op": "OR",
                "left": self._expression_to_json(expr.this),
                "right": self._expression_to_json(expr.expression),
            }

        elif isinstance(expr, exp.Not):
            return {
                "type": "unary_op",
                "operator": "not",
                "operand": self._expression_to_json(expr.this),
            }

        # IS NULL / IS NOT NULL
        elif isinstance(expr, exp.Is):
            if isinstance(expr.expression, exp.Null):
                return {
                    "type": "null_check",
                    "operator": "is null",
                    "operand": self._expression_to_json(expr.this),
                }
            return {"type": "unknown", "value": str(expr)}

        # IN operator
        elif isinstance(expr, exp.In):
            values = []
            if expr.expressions:
                values = [self._expression_to_json(e) for e in expr.expressions]
            return {
                "type": "in",
                "operand": self._expression_to_json(expr.this),
                "values": values,
            }

        # LIKE operator
        elif isinstance(expr, exp.Like):
            return {
                "type": "like",
                "operand": self._expression_to_json(expr.this),
                "pattern": self._expression_to_json(expr.expression),
            }

        # BETWEEN operator
        elif isinstance(expr, exp.Between):
            return {
                "type": "between",
                "operand": self._expression_to_json(expr.this),
                "low": self._expression_to_json(expr.args.get("low")),
                "high": self._expression_to_json(expr.args.get("high")),
            }

        # Function calls
        elif isinstance(expr, exp.Func):
            args = []
            for arg in expr.args.values():
                if arg is not None:
                    if isinstance(arg, list):
                        args.extend(self._expression_to_json(a) for a in arg if a)
                    elif isinstance(arg, exp.Expression):
                        args.append(self._expression_to_json(arg))
            
            return {
                "type": "function",
                "name": expr.sql_name(),
                "args": args,
            }

        # Parenthesized expression
        elif isinstance(expr, exp.Paren):
            return self._expression_to_json(expr.this)

        # Fallback for unsupported expressions
        else:
            return {"type": "unknown", "value": str(expr)}

    def _is_select_star(self, exprs: t.List[exp.Expression]) -> bool:
        """Check if expressions represent SELECT *."""
        return len(exprs) == 1 and isinstance(exprs[0], exp.Star)

    def _extract_select_columns(
        self, exprs: t.List[exp.Expression]
    ) -> t.List[t.Dict[str, t.Any]]:
        """Extract column info from SELECT expressions."""
        columns = []
        for expr in exprs:
            if isinstance(expr, exp.Alias):
                col_info: t.Dict[str, t.Any] = {
                    "name": expr.alias,
                    "expression": expr.this.sql() if expr.this else None,
                }
                if hasattr(expr, "type") and expr.type:
                    col_info["type"] = str(expr.type)
                columns.append(col_info)
            elif isinstance(expr, exp.Column):
                col_info = {"name": expr.name}
                if expr.table:
                    col_info["source"] = expr.table
                if hasattr(expr, "type") and expr.type:
                    col_info["type"] = str(expr.type)
                columns.append(col_info)
            else:
                columns.append({
                    "name": expr.sql(),
                    "expression": expr.sql(),
                })
        return columns

    def _extract_group_by_columns(
        self, select: exp.Select, group: exp.Group
    ) -> t.Tuple[t.List[t.Dict[str, t.Any]], t.List[t.Dict[str, t.Any]]]:
        """Extract dimensions and aggregates from GROUP BY context."""
        dims: t.List[t.Dict[str, t.Any]] = []
        aggs: t.List[t.Dict[str, t.Any]] = []

        # Get dimension columns from GROUP BY
        for expr in group.expressions:
            if isinstance(expr, exp.Column):
                dim_info: t.Dict[str, t.Any] = {"name": expr.name}
                if expr.table:
                    dim_info["source"] = expr.table
                if hasattr(expr, "type") and expr.type:
                    dim_info["type"] = str(expr.type)
                dims.append(dim_info)
            else:
                dims.append({"name": expr.sql()})

        # Get aggregates from SELECT clause
        for expr in select.args.get("expressions") or []:
            if isinstance(expr, exp.Alias) and isinstance(expr.this, exp.AggFunc):
                agg_func = expr.this
                func_name = agg_func.__class__.__name__.lower()
                
                # Get the column being aggregated
                source_col = ""
                if agg_func.this:
                    if isinstance(agg_func.this, exp.Column):
                        source_col = agg_func.this.name
                    elif isinstance(agg_func.this, exp.Star):
                        source_col = "*"
                    else:
                        source_col = agg_func.this.sql()

                agg_info: t.Dict[str, t.Any] = {
                    "name": expr.alias,
                    "function": func_name,
                    "source_column": source_col,
                }
                if hasattr(expr, "type") and expr.type:
                    agg_info["type"] = str(expr.type)
                aggs.append(agg_info)

        return dims, aggs

    def _extract_order_columns(self, order: exp.Order) -> t.List[t.Dict[str, t.Any]]:
        """Extract order by expressions."""
        expressions = []
        for ordered in order.expressions:
            column = ordered.this
            column_name = column.name if hasattr(column, "name") else str(column)
            direction = "desc" if ordered.args.get("desc") else "asc"

            expressions.append({"column": column_name, "direction": direction})

        return expressions

    def _extract_limit_value(self, limit: exp.Limit) -> t.Optional[int]:
        """Extract limit count value. Returns None if parsing fails."""
        limit_expr = limit.expression if hasattr(limit, "expression") else limit.this
        if limit_expr:
            try:
                if hasattr(limit_expr, "this"):
                    return int(limit_expr.this)
                return int(limit_expr)
            except (ValueError, AttributeError, TypeError):
                pass
        return None

    def _extract_offset_value(self, offset: exp.Offset) -> int:
        """Extract offset count value."""
        offset_expr = offset.expression if hasattr(offset, "expression") else offset.this
        if offset_expr:
            try:
                if hasattr(offset_expr, "this"):
                    return int(offset_expr.this)
                return int(offset_expr)
            except (ValueError, AttributeError, TypeError):
                pass
        return 0  # Default offset is 0
