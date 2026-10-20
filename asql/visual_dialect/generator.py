"""
VisualASQLGenerator - Generates JSON representation from SQLGlot AST.

This generator outputs a structured JSON format suitable for visual query builders,
with column tracking at each pipeline stage.

Output format is always an array of pipelines:
    [
        {"name": "cte_name", "from": {...}, "transforms": [...], "set_operation": {...}},
        {"name": null, "from": {...}, "transforms": [...]}
    ]

Losslessness contract
---------------------
``asql.json_schema.json_to_asql`` turns this JSON back into ASQL, and users
toggle between the two freely, so the round trip must preserve meaning
exactly. Everything the visual form can model is emitted as structured
transforms and expression nodes; anything it cannot is emitted as an explicit
``raw`` node holding ASQL text that ``json_to_asql`` reproduces verbatim:

- ``{"type": "raw", "asql": "..."}``: an expression or an order-by key.
- ``{"from": {"table": "", "raw": "..."}}``: a FROM source that is not a table.
- ``{"raw": "...", ...}`` on a pipeline: the whole pipeline body.

Names (tables, columns, aliases) are emitted raw, without quotes;
``json_to_asql`` backtick-quotes whatever is not a plain identifier.
Expression text (``expression`` fields and ``raw`` nodes) is ASQL and is
pasted verbatim.
"""

import json
import typing as t
from typing import TypeGuard

from sqlglot import exp
from sqlglot.generator import Generator
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify_columns import qualify_columns
from sqlglot.schema import MappingSchema

from asql.dialect import ASQL
from asql.dialect.generator import ASQLGenerator
from asql.dialect.parser import AUTO_CTE_RE
from asql.expressions import Spine
from asql.functions import (
    ALIAS_FUNC_META,
    SAMPLE_META,
    STRING_OP_META,
    unit_function_arg,
)
from asql.json_schema import quote_identifier

# Spellings for the ASQL text carried in the JSON. Function style keeps every
# spelling a call the ASQL parser reads back to the same node (`COALESCE(a, b)`
# rather than `a ?? b`, `COUNT(*)` rather than `#`).
_TEXT_DIALECT = ASQL(
    coalesce="function", count="function", cast="function", equality="single"
)

# `contains 'x'` is parsed to LIKE '%x%'; the meta tag names the written
# operator and this table says how the value was wrapped into the pattern.
_STRING_OP_WRAPS: dict[str, tuple[str, str, str]] = {
    "contains": ("contains", "%", "%"),
    "icontains": ("icontains", "%", "%"),
    "starts with": ("starts_with", "", "%"),
    "istarts with": ("istarts_with", "", "%"),
    "ends with": ("ends_with", "%", ""),
    "iends with": ("iends_with", "%", ""),
}

# Select args the pipeline model understands; a SELECT with anything else set
# (named windows, laterals, hints, ...) becomes a raw pipeline.
_SUPPORTED_SELECT_ARGS = frozenset(
    {
        "with_",
        "expressions",
        "from_",
        "joins",
        "where",
        "group",
        "having",
        "qualify",
        "order",
        "limit",
        "offset",
        "distinct",
    }
)


def _name_part(name: str) -> str:
    """A name for a name slot: raw, unless json_to_asql would misread it.

    json_to_asql splits name slots on dots and quotes each part, so a part that
    itself contains a dot (or a backtick) is pre-quoted here.
    """
    if "." in name or "`" in name:
        return quote_identifier(name)
    return name


class _TextGenerator(ASQLGenerator):
    """ASQL spelling for the text the JSON carries (expressions, raw nodes).

    Expressions use ASQL spellings (`month(x)`, `week(x)`, backticked names)
    so the ASQL parser reads them back to the same nodes. Statement shapes
    (SELECT, WITH, FROM, JOIN) use plain SQL, which ASQL also accepts and
    which nests inside parentheses where the pipeline form does not.
    """

    select_sql = Generator.select_sql
    with_sql = Generator.with_sql
    from_sql = Generator.from_sql
    join_sql = Generator.join_sql
    ordered_sql = Generator.ordered_sql

    def if_sql(self, expression: exp.If) -> str:
        # IF(c, a, b) parses back to exp.If; CASE WHEN would come back as exp.Case,
        # which some dialects (Snowflake IFF) print differently.
        return self.func(
            "IF",
            expression.this,
            expression.args.get("true"),
            expression.args.get("false"),
        )

    # Spine is not a sqlglot class, so it is dispatched through TRANSFORMS.
    TRANSFORMS: t.ClassVar[dict[type[exp.Expr], t.Callable[..., str]]] = {
        **ASQLGenerator.TRANSFORMS,
        Spine: lambda self, e: f"spine({self.sql(e, 'this')})",
    }


class VisualASQLGenerator(Generator):
    """Generator that outputs JSON array of pipelines with column tracking."""

    # Declarative mappings per .cursorrules - use dicts instead of elif chains
    _SIDE_JOIN_MAP: t.ClassVar[dict[str, str]] = {
        "LEFT": "left",
        "RIGHT": "right",
        "FULL": "full",
    }

    _KIND_JOIN_MAP: t.ClassVar[dict[str, str]] = {
        "CROSS": "cross",
        "INNER": "inner",
        "LEFT": "left",
        "RIGHT": "right",
        "FULL": "full",
    }

    _BINARY_OP_MAP: t.ClassVar[dict[type[exp.Expr], str]] = {
        exp.EQ: "=",
        exp.NEQ: "!=",
        exp.LT: "<",
        exp.GT: ">",
        exp.LTE: "<=",
        exp.GTE: ">=",
        exp.And: "AND",
        exp.Or: "OR",
        exp.Add: "+",
        exp.Sub: "-",
        exp.Mul: "*",
        exp.Div: "/",
        exp.Mod: "%",
        exp.DPipe: "||",
    }

    _SET_OP_MAP: t.ClassVar[dict[type[exp.Expr], str]] = {
        exp.Union: "union",
        exp.Intersect: "intersect",
        exp.Except: "except",
    }

    def __init__(self, schema: MappingSchema | None = None, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._schema = schema
        self._text_generator = _TextGenerator(dialect=_TEXT_DIALECT, comments=False)

    def generate(self, expression: exp.Expr, copy: bool = True) -> str:
        """Generate JSON string from AST - always outputs array format."""
        if copy:
            expression = expression.copy()

        # Build JSON structure (always an array)
        result = self._build_pipelines(expression)

        return json.dumps(result, indent=2)

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def _text(self, expr: exp.Expr) -> str:
        """ASQL text for a node, as pasted verbatim by json_to_asql."""
        return self._text_generator.generate(expr, copy=False).strip()

    def _raw(self, expr: exp.Expr) -> dict[str, t.Any]:
        return {"type": "raw", "asql": self._text(expr)}

    @staticmethod
    def _is_plain_column(expr: exp.Expr) -> TypeGuard[exp.Column]:
        """A column reference json_to_asql can emit from its name alone."""
        return (
            isinstance(expr, exp.Column)
            and isinstance(expr.this, exp.Identifier)
            and not expr.args.get("db")
            and not expr.args.get("catalog")
        )

    @staticmethod
    def _column_name(column: exp.Column) -> str:
        """Raw (unquoted) dotted name of a plain column: `col` or `t.col`."""
        name = _name_part(column.name)
        return f"{_name_part(column.table)}.{name}" if column.table else name

    def _name_or_text(self, expr: exp.Expr) -> str:
        """Raw name for a plain column, ASQL text for anything else."""
        if self._is_plain_column(expr):
            return self._column_name(expr)
        return self._text(expr)

    # ------------------------------------------------------------------
    # Pipelines
    # ------------------------------------------------------------------

    def _build_pipelines(self, expression: exp.Expr) -> list[dict[str, t.Any]]:
        """Build array of pipeline representations."""
        pipelines: list[dict[str, t.Any]] = []
        if isinstance(expression, exp.Semicolon):
            return pipelines  # an empty statement (`;` with only comments)

        # Handle CTEs (WITH clause) - note: SQLGlot uses 'with_' not 'with'
        with_clause = (
            expression.args.get("with_")
            if isinstance(expression, (exp.Select, exp.SetOperation))
            else None
        )
        if with_clause and with_clause.args.get("recursive"):
            # `recurse` / WITH RECURSIVE has no pipeline form.
            return [self._raw_pipeline(expression)]
        if with_clause:
            for cte in with_clause.expressions:
                cte_name = cte.alias
                cte_query = cte.this
                if isinstance(cte_query, exp.Select):
                    pipeline = self._build_single_pipeline(cte_query, cte_name)
                else:
                    pipeline = self._raw_pipeline(cte_query)
                pipeline["name"] = cte_name
                pipelines.append(pipeline)

        # Handle set operations (UNION, INTERSECT, EXCEPT)
        if isinstance(expression, exp.SetOperation):
            self._build_set_operation_pipelines(expression, pipelines)
        elif isinstance(expression, exp.Select):
            # Pre-qualify columns if schema provided
            if self._schema:
                # sqlglot qualification is best-effort: schema lookup can fail
                # for missing tables, SELECT *, complex expressions, etc.
                try:
                    qualified = qualify_columns(
                        expression, schema=self._schema, expand_stars=True
                    )
                    expression = annotate_types(qualified, schema=self._schema)
                except Exception:  # noqa: BLE001, S110 - sqlglot errors non-fatal
                    pass

            pipeline = self._build_single_pipeline(expression)
            pipeline["name"] = None  # Final output pipeline
            pipelines.append(pipeline)
        else:
            pipelines.append(self._raw_pipeline(expression))

        return pipelines

    def _raw_pipeline(self, expression: exp.Expr) -> dict[str, t.Any]:
        """A pipeline the visual form cannot model: its body is ASQL text."""
        body = expression
        if isinstance(expression, (exp.Select, exp.SetOperation)) and (
            expression.args.get("with_")
        ):
            # The CTEs were already emitted as their own pipelines.
            body = expression.copy()
            body.set("with_", None)
        text = self._text(body)
        return {
            "name": None,
            "from": {"table": "", "raw": text, "output_columns": []},
            "transforms": [],
            "raw": text,
        }

    def _build_set_operation_pipelines(
        self, expression: exp.Expr, pipelines: list[dict[str, t.Any]]
    ) -> None:
        """Recursively build pipelines for set operations."""
        if isinstance(expression, exp.SetOperation):
            # Process left side
            left = expression.this
            if isinstance(left, exp.SetOperation):
                self._build_set_operation_pipelines(left, pipelines)
            else:
                pipeline = (
                    self._build_single_pipeline(left)
                    if isinstance(left, exp.Select)
                    else self._raw_pipeline(left)
                )
                pipeline["name"] = None

                # Add set operation info
                op_type = self._SET_OP_MAP.get(type(expression), "union")
                is_all = expression.args.get("distinct") is False
                pipeline["set_operation"] = {"type": op_type, "all": is_all}

                pipelines.append(pipeline)

            # Process right side
            right = expression.expression
            if isinstance(right, exp.SetOperation):
                self._build_set_operation_pipelines(right, pipelines)
            else:
                pipeline = (
                    self._build_single_pipeline(right)
                    if isinstance(right, exp.Select)
                    else self._raw_pipeline(right)
                )
                pipeline["name"] = None
                pipelines.append(pipeline)

    def _build_single_pipeline(
        self, expression: exp.Select, cte_name: str | None = None
    ) -> dict[str, t.Any]:
        """Build JSON representation of a single SELECT query.

        ``cte_name`` is the CTE this SELECT is the body of, if any; a parser
        generated name (`__tmpN`) marks a stage the pipeline closed itself.
        """
        unsupported_args = [
            key
            for key, value in expression.args.items()
            if value and key not in _SUPPORTED_SELECT_ARGS
        ]
        distinct = expression.args.get("distinct")
        if unsupported_args or (distinct and distinct.args.get("on")):
            return self._raw_pipeline(expression)

        result: dict[str, t.Any] = {"name": None, "from": None, "transforms": []}
        current_columns: list[dict[str, t.Any]] = []
        transforms: list[dict[str, t.Any]] = result["transforms"]

        # Pre-extract column references from the query for fallback when no schema
        inferred_columns_by_table = self._extract_columns_from_query(expression)

        # Extract top-level comments from the SELECT statement
        pipeline_comments = self._get_comments(expression)
        if pipeline_comments:
            result["comments"] = pipeline_comments

        # Check if this is a multi-table query (has JOINs)
        has_joins = bool(expression.args.get("joins"))

        # FROM clause (uses 'from_' because 'from' is a Python keyword)
        from_clause = expression.args.get("from_")
        if from_clause is None:
            # SELECT without FROM (`SELECT 1 AS a`): nothing to pipeline from.
            return self._raw_pipeline(expression)

        table_expr = from_clause.this
        sample_transform: dict[str, t.Any] | None = None
        pivot_transforms: list[dict[str, t.Any]] = []
        pivoted = self._unfold_pivot(table_expr)
        if pivoted is not None:
            table_expr, pivot_transforms = pivoted
        if self._is_plain_table(table_expr):
            table_name = self._get_table_name(table_expr)
            table_alias = self._get_alias(table_expr)
            # Only qualify column names if there are joins (to avoid ambiguity)
            table_cols = self._get_table_columns(table_name, qualify=has_joins)

            # If no schema columns, use inferred columns from query
            if not table_cols:
                table_cols = self._inferred_columns(
                    inferred_columns_by_table, table_name, table_alias
                )

            current_columns = table_cols.copy()

            from_comments = self._get_comments(from_clause) or self._get_comments(
                table_expr
            )
            result["from"] = {
                "table": table_name,
                "alias": table_alias if table_alias != table_name else None,
                "output_columns": table_cols,
            }
            if from_comments:
                result["from"]["comments"] = from_comments
            sample_transform = self._sample_transform(table_expr)
        else:
            # Subquery, pivot, table function, ...: keep the source verbatim.
            result["from"] = {
                "table": "",
                "raw": self._text(table_expr),
                "alias": None,
                "output_columns": [],
            }

        if sample_transform:
            sample_transform["output_columns"] = current_columns.copy()
            transforms.append(sample_transform)
        for transform in pivot_transforms:
            transform["output_columns"] = current_columns.copy()
            transforms.append(transform)

        # `sample N` / `sample N per col` desugar into ORDER BY RANDOM() LIMIT N
        # or a QUALIFY; the parser left the written form behind.
        sample_stage = self._sample_stage(expression)

        # JOINs - accumulate columns
        for join in expression.args.get("joins") or []:
            join_transform = self._join_transform(join, inferred_columns_by_table)
            if join_transform is None:
                return self._raw_pipeline(expression)
            transform = join_transform
            if transform["type"] == "join":
                current_columns.extend(transform.pop("_columns"))
            transform["output_columns"] = current_columns.copy()
            transforms.append(transform)

        # WHERE - columns unchanged
        if where := expression.args.get("where"):
            transform = {
                "type": "where",
                "condition": self._expression_to_json(where.this),
                "output_columns": current_columns.copy(),
            }
            # Collect all comments from the WHERE clause and its condition tree
            if where_comments := self._collect_all_comments(where):
                transform["comments"] = where_comments
            transforms.append(transform)

        # GROUP BY - columns change to dimensions + aggregates
        if group := expression.args.get("group"):
            group_transforms = self._group_by_transforms(expression, group)
            if group_transforms is None:
                return self._raw_pipeline(expression)
            for transform in group_transforms:
                current_columns = transform.pop("_columns")
                transform["output_columns"] = current_columns.copy()
                transforms.append(transform)

        # SELECT - explicit columns (only if not SELECT *)
        else:
            select_transforms = self._select_transforms(expression, cte_name)
            if select_transforms is None:
                return self._raw_pipeline(expression)
            for transform in select_transforms:
                if "_columns" in transform:
                    current_columns = transform.pop("_columns")
                transform["output_columns"] = current_columns.copy()
                transforms.append(transform)

        if distinct:
            transforms.append(
                {"type": "distinct", "output_columns": current_columns.copy()}
            )

        # HAVING / QUALIFY - columns unchanged
        for key in ("having", "qualify"):
            if key == "qualify" and sample_stage and sample_stage.get("per"):
                continue
            if clause := expression.args.get(key):
                transform = {
                    "type": key,
                    "condition": self._expression_to_json(clause.this),
                    "output_columns": current_columns.copy(),
                }
                if comments := self._get_comments(clause):
                    transform["comments"] = comments
                transforms.append(transform)

        if sample_stage and not sample_stage.get("per"):
            # ORDER BY RANDOM() LIMIT N belong to the sample stage
            transforms.append(
                {
                    "type": "sample",
                    "size": sample_stage["size"],
                    "output_columns": current_columns.copy(),
                }
            )

        # ORDER BY - columns unchanged
        if (order := expression.args.get("order")) and not (
            sample_stage and not sample_stage.get("per")
        ):
            transform = {
                "type": "order_by",
                "expressions": self._extract_order_columns(order),
                "output_columns": current_columns.copy(),
            }
            if comments := self._get_comments(order):
                transform["comments"] = comments
            transforms.append(transform)

        # LIMIT / OFFSET - columns unchanged
        for key in ("limit", "offset"):
            if key == "limit" and sample_stage and not sample_stage.get("per"):
                continue
            if clause := expression.args.get(key):
                transform = self._count_transform(key, clause)
                transform["output_columns"] = current_columns.copy()
                if comments := self._get_comments(clause):
                    transform["comments"] = comments
                transforms.append(transform)

        if sample_stage and sample_stage.get("per"):
            transforms.append(
                {
                    "type": "sample",
                    "size": sample_stage["size"],
                    "per": sample_stage["per"],
                    "output_columns": current_columns.copy(),
                }
            )

        for index, transform in enumerate(transforms):
            transform["id"] = f"t{index}"
            # id first keeps the JSON readable
            transforms[index] = {"id": transform.pop("id"), **transform}

        return result

    # ------------------------------------------------------------------
    # FROM / JOIN
    # ------------------------------------------------------------------

    def _sample_stage(self, select: exp.Select) -> dict[str, t.Any] | None:
        """The `sample` the parser desugared this SELECT from, if its shape held."""
        meta = select.meta.get(SAMPLE_META)
        if not meta:
            return None
        size = str(meta.get("size"))
        per = meta.get("per")
        if per is not None:
            qualify = select.args.get("qualify")
            condition = qualify.this if qualify else None
            if not (
                isinstance(condition, exp.LTE)
                and isinstance(condition.this, exp.Window)
                and isinstance(condition.this.this, exp.RowNumber)
                and condition.expression == exp.Literal.number(size)
            ):
                return None
            return {"size": size, "per": self._name_or_text(per)}
        order = select.args.get("order")
        limit = select.args.get("limit")
        if not (
            order
            and [type(o.this) for o in order.expressions] == [exp.Rand]
            and limit
            and limit.expression == exp.Literal.number(size)
        ):
            return None
        return {"size": size, "per": None}

    def _unfold_pivot(
        self, table_expr: exp.Expr
    ) -> tuple[exp.Expr, list[dict[str, t.Any]]] | None:
        """`pivot`/`unpivot` stages back out of a pivoted FROM source.

        `pivot agg by col values (...) group by k` is parsed as
        `(SELECT k, <pivot columns> FROM t) PIVOT(...)`; `unpivot` and a
        pivot without keys sit directly on the table.
        """
        if not isinstance(table_expr, (exp.Table, exp.Subquery)):
            return None
        pivots = table_expr.args.get("pivots") or []
        if len(pivots) != 1:
            return None
        pivot = pivots[0]
        transform = self._pivot_transform(pivot)
        if transform is None:
            return None

        if isinstance(table_expr, exp.Table):
            source = table_expr.copy()
            source.set("pivots", None)
            return source, [transform]

        inner = table_expr.this
        if (
            table_expr.alias
            or not isinstance(inner, exp.Select)
            or set(inner.args) - {"expressions", "from_"}
            or not inner.args.get("from_")
            or not isinstance(inner.args["from_"].this, exp.Table)
            or not all(self._is_plain_column(c) for c in inner.expressions)
        ):
            return None
        pivot_columns = {
            c.name
            for node in [*pivot.expressions, *pivot.args.get("fields", [])]
            for c in node.find_all(exp.Column)
        }
        keys = [c.name for c in inner.expressions if c.name not in pivot_columns]
        if not keys:
            return None
        return inner.args["from_"].this, [
            transform,
            {"type": "group_by", "dimensions": keys, "aggregates": []},
        ]

    def _pivot_transform(self, pivot: exp.Pivot) -> dict[str, t.Any] | None:
        extras = {
            key
            for key, value in pivot.args.items()
            if value and key not in ("expressions", "fields", "unpivot")
        }
        fields = pivot.args.get("fields") or []
        if extras or len(pivot.expressions) != 1 or len(fields) != 1:
            return None
        field = fields[0]
        if pivot.args.get("unpivot"):
            # UNPIVOT(value FOR name IN (c1, c2))
            value = pivot.expressions[0]
            if not (
                isinstance(value, exp.Identifier)
                and isinstance(field, exp.In)
                and isinstance(field.this, exp.Identifier)
                and all(self._is_plain_column(c) for c in field.expressions)
            ):
                return None
            return {
                "type": "unpivot",
                "columns": [self._column_name(c) for c in field.expressions],
                "name": field.this.name,
                "value": value.name,
            }
        aggregate = pivot.expressions[0]
        if isinstance(aggregate, exp.Alias):
            aggregate = aggregate.this  # the parser's auto alias
        if isinstance(field, exp.In):
            column, values = field.this, list(field.expressions)
            if set(field.args) - {"this", "expressions"}:
                return None
        else:
            column, values = field, []
        if not self._is_plain_column(column):
            return None
        return {
            "type": "pivot",
            "aggregate": self._text(aggregate),
            "column": self._column_name(column),
            "values": [self._expression_to_json(v) for v in values],
        }

    @staticmethod
    def _is_plain_table(table_expr: exp.Expr) -> bool:
        """A table reference `from.table` + `alias` can carry."""
        if not isinstance(table_expr, exp.Table):
            return False
        if not isinstance(table_expr.this, exp.Identifier):
            return False
        extras = {
            key
            for key, value in table_expr.args.items()
            if value and key not in ("this", "db", "catalog", "alias", "sample")
        }
        if extras:
            return False
        alias = table_expr.args.get("alias")
        if alias and alias.args.get("columns"):
            return False
        sample = table_expr.args.get("sample")
        return sample is None or VisualASQLGenerator._percent_sample(sample) is not None

    @staticmethod
    def _percent_sample(sample: exp.TableSample) -> str | None:
        """`sample 10%` is the only table sample the pipeline form spells."""
        extras = {
            key
            for key, value in sample.args.items()
            if value and key not in ("percent", "method")
        }
        percent = sample.args.get("percent")
        method = sample.args.get("method")
        if extras or not isinstance(percent, exp.Literal) or not percent.is_number:
            return None
        if method and str(method).upper() != "BERNOULLI":
            return None
        return f"{percent.this}%"

    def _sample_transform(self, table_expr: exp.Table) -> dict[str, t.Any] | None:
        sample = table_expr.args.get("sample")
        if sample is None:
            return None
        return {"type": "sample", "size": self._percent_sample(sample)}

    def _get_table_name(self, table_expr: exp.Expr) -> str:
        """Fully qualified table name (`catalog.schema.table`), unquoted."""
        if isinstance(table_expr, exp.Table):
            parts = [
                part.name
                for part in (
                    table_expr.args.get("catalog"),
                    table_expr.args.get("db"),
                    table_expr.this,
                )
                if part is not None
            ]
            return ".".join(_name_part(part) for part in parts)
        if hasattr(table_expr, "name"):
            return str(table_expr.name)
        return str(table_expr)

    def _get_alias(self, table_expr: exp.Expr) -> str | None:
        """Extract alias from table expression."""
        if isinstance(table_expr, exp.Table) and table_expr.alias:
            return table_expr.alias
        return None

    def _inferred_columns(
        self,
        inferred_columns_by_table: dict[str, list[dict[str, t.Any]]],
        table_name: str,
        table_alias: str | None,
    ) -> list[dict[str, t.Any]]:
        """Columns referenced in the query for a table (by name or alias)."""
        cols = list(inferred_columns_by_table.get(table_name, []))
        if table_alias and table_alias != table_name:
            cols = cols + inferred_columns_by_table.get(table_alias, [])
        seen: set[str] = set()
        unique_cols = []
        for col in cols:
            if col["name"] not in seen:
                seen.add(col["name"])
                unique_cols.append(col)
        return unique_cols

    def _join_transform(
        self,
        join: exp.Join,
        inferred_columns_by_table: dict[str, list[dict[str, t.Any]]],
    ) -> dict[str, t.Any] | None:
        """join / explode transform, or None when the join has no pipeline form."""
        join_table_expr = join.this
        comments = self._get_comments(join)

        extras = {
            key
            for key, value in join.args.items()
            if value and key not in ("this", "on", "kind", "side")
        }
        kind = (join.args.get("kind") or "").upper()
        side = (join.args.get("side") or "").upper()
        known_join = (not kind or kind in self._KIND_JOIN_MAP) and (
            not side or side in self._SIDE_JOIN_MAP
        )

        transform: dict[str, t.Any]
        if (
            isinstance(join_table_expr, exp.Unnest)
            and kind == "CROSS"
            and not side
            and not extras
            and join.args.get("on") is None
            and len(join_table_expr.expressions) == 1
            and join_table_expr.alias
            and not join_table_expr.args.get("offset")
            and not (join_table_expr.args.get("alias") or exp.TableAlias()).args.get(
                "columns"
            )
        ):
            # `explode tags as tag`
            transform = {
                "type": "explode",
                "column": self._name_or_text(join_table_expr.expressions[0]),
                "alias": join_table_expr.alias,
            }
        elif (
            self._is_plain_table(join_table_expr)
            and not join_table_expr.args.get("sample")
            and known_join
            and not extras
        ):
            join_table = self._get_table_name(join_table_expr)
            join_alias = self._get_alias(join_table_expr)
            join_cols = self._get_table_columns(join_table)
            if not join_cols:
                join_cols = self._inferred_columns(
                    inferred_columns_by_table, join_table, join_alias
                )
            condition = None
            if on_clause := join.args.get("on"):
                condition = self._expression_to_json(on_clause)
            transform = {
                "type": "join",
                "join_type": self._get_join_type(join),
                "table": join_table,
                "alias": join_alias if join_alias != join_table else None,
                "condition": condition,
                "_columns": join_cols,
            }
        else:
            # Subquery joins, USING, lateral, semi/anti joins, ...: the pipeline
            # parser has no spelling for them, so the whole SELECT goes raw.
            return None
        if comments:
            transform["comments"] = comments
        return transform

    def _get_comments(self, expr: exp.Expr) -> list[str] | None:
        """Extract comments from an expression node."""
        if hasattr(expr, "comments") and expr.comments:
            # Clean up comments (strip whitespace, remove empty ones)
            cleaned = [c.strip() for c in expr.comments if c and c.strip()]
            return cleaned if cleaned else None
        return None

    def _collect_all_comments(self, expr: exp.Expr) -> list[str]:
        """Recursively collect all comments from an expression tree."""
        comments: list[str] = []

        def collect(node: exp.Expr) -> None:
            if hasattr(node, "comments") and node.comments:
                for c in node.comments:
                    if c and c.strip():
                        comments.append(c.strip())
            for child in node.iter_expressions():
                collect(child)

        collect(expr)
        return comments

    def _get_table_columns(
        self, table_name: str, qualify: bool = True
    ) -> list[dict[str, t.Any]]:
        """Get columns for a table from schema.

        Args:
            table_name: The table name to look up
            qualify: If True, include qualified name (table.column) for disambiguation
        """
        if not self._schema:
            return []

        try:
            table_expr = exp.to_table(table_name)
            cols = self._schema.column_names(table_expr)
            result = []
            for col in cols:
                col_type = self._schema.get_column_type(table_expr, exp.column(col))
                type_str = str(col_type)
                # Use qualified name (table.column) for clarity after JOINs
                qualified_name = f"{table_name}.{col}" if qualify else col
                result.append(
                    {
                        "name": qualified_name,
                        "type": type_str,
                        "source": table_name,
                    }
                )
            return result
        except (KeyError, AttributeError, TypeError, ValueError):
            # Schema lookup can fail for missing tables, invalid column refs, etc.
            return []

    def _extract_columns_from_query(
        self, expression: exp.Select
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Extract all column references from a query, grouped by table.

        Uses SQLGlot's find_all() to locate all Column nodes in the AST.
        Provides fallback column info when no schema is available.
        """
        columns_by_table: dict[str, list[dict[str, t.Any]]] = {}
        seen: set[str] = set()

        # Get FROM table name for unqualified columns in single-table queries
        from_table_name: str | None = None
        if from_clause := expression.args.get("from_"):
            if table_expr := from_clause.this:
                from_table_name = self._get_table_name(table_expr)

        # Count tables to determine if single or multi-table query
        table_count = 1 if from_table_name else 0
        table_count += len(expression.args.get("joins") or [])

        # Use SQLGlot's find_all to get all Column nodes
        for col in expression.find_all(exp.Column):
            table = col.table
            name = col.name
            if not name or name == "*":
                continue

            # For single-table queries, unqualified columns belong to FROM table
            if not table and table_count == 1 and from_table_name:
                table = from_table_name

            # Build qualified key for deduplication
            qualified_key = f"{table}.{name}" if table else name
            if qualified_key in seen:
                continue
            seen.add(qualified_key)

            # Group by table (or "_unqualified_" if no table)
            source = table or "_unqualified_"
            if source not in columns_by_table:
                columns_by_table[source] = []
            columns_by_table[source].append(
                {
                    "name": name,  # Use just the column name, not qualified
                    "source": table,
                }
            )

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

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _expression_to_json(self, expr: exp.Expr | None) -> dict[str, t.Any]:
        """Convert SQLGlot expression to JSON representation."""
        if expr is None:
            return {"type": "null"}
        written = expr.meta.get(ALIAS_FUNC_META)
        if written:
            return {
                "type": "function",
                "name": written,
                "args": [self._expression_to_json(unit_function_arg(expr))],
            }
        if isinstance(expr, exp.Column):
            if not self._is_plain_column(expr):
                return self._raw(expr)
            result: dict[str, t.Any] = {
                "type": "column",
                "name": expr.name,
            }
            if expr.table:
                result["table"] = expr.table
            if hasattr(expr, "type") and expr.type:
                result["data_type"] = str(expr.type)
            return result

        if isinstance(expr, exp.Literal):
            value = expr.this
            if expr.is_number:
                data_type = "number"
                try:
                    typed_value: t.Any = (
                        int(value) if "." not in str(value) else float(value)
                    )
                except (ValueError, TypeError):
                    typed_value = value
                if str(typed_value) != str(value):
                    # 1e5, 007, ...: keep the written form rather than a value
                    # whose spelling would change the SQL.
                    return self._raw(expr)
            else:
                data_type = "string"
                typed_value = value

            return {"type": "literal", "value": typed_value, "data_type": data_type}

        if isinstance(expr, exp.Boolean):
            return {"type": "literal", "value": expr.this, "data_type": "boolean"}

        if isinstance(expr, exp.Null):
            return {"type": "literal", "value": None, "data_type": "null"}

        if isinstance(expr, exp.Star) and not expr.args.get("except_"):
            return {"type": "star"}

        if isinstance(expr, exp.Paren):
            return {"type": "paren", "expression": self._expression_to_json(expr.this)}

        if isinstance(expr, exp.Neg):
            return {
                "type": "unary_op",
                "operator": "-",
                "operand": self._expression_to_json(expr.this),
            }

        # Comparison, logical and arithmetic operators
        op = self._BINARY_OP_MAP.get(type(expr))
        if op is not None and type(expr) in self._BINARY_OP_MAP:
            return {
                "type": "binary",
                "op": op,
                "left": self._expression_to_json(expr.this),
                "right": self._expression_to_json(expr.expression),
            }

        if isinstance(expr, exp.Not):
            inner = expr.this
            if isinstance(inner, exp.In) and self._in_values(inner) is not None:
                return {
                    "type": "not_in",
                    "operand": self._expression_to_json(inner.this),
                    "values": self._in_values(inner),
                }
            if isinstance(inner, exp.Is) and isinstance(inner.expression, exp.Null):
                return self._null_check(inner, negate=not inner.args.get("negate"))
            return {
                "type": "unary_op",
                "operator": "not",
                "operand": self._expression_to_json(inner),
            }

        # IS NULL / IS NOT NULL
        if isinstance(expr, exp.Is):
            if isinstance(expr.expression, exp.Null):
                return self._null_check(expr, negate=bool(expr.args.get("negate")))
            return self._raw(expr)

        # IN operator
        if isinstance(expr, exp.In):
            values = self._in_values(expr)
            if values is None:
                return self._raw(expr)
            return {
                "type": "in",
                "operand": self._expression_to_json(expr.this),
                "values": values,
            }

        # LIKE family: `contains`, `starts with`, ... keep their own node types
        if isinstance(expr, (exp.Like, exp.ILike)):
            return self._like_json(expr)

        if isinstance(expr, exp.RegexpLike):
            return {
                "type": "matches",
                "operand": self._expression_to_json(expr.this),
                "pattern": self._expression_to_json(expr.expression),
            }

        # BETWEEN operator
        if isinstance(expr, exp.Between) and not expr.args.get("symmetric"):
            return {
                "type": "between",
                "operand": self._expression_to_json(expr.this),
                "low": self._expression_to_json(expr.args.get("low")),
                "high": self._expression_to_json(expr.args.get("high")),
            }

        # Function calls
        if isinstance(expr, exp.Func):
            function_json = self._function_json(expr)
            if function_json is not None:
                return function_json

        # Fallback: ASQL text, reproduced verbatim by json_to_asql
        return self._raw(expr)

    def _null_check(self, expr: exp.Is, negate: bool) -> dict[str, t.Any]:
        return {
            "type": "null_check",
            "operator": "is not null" if negate else "is null",
            "operand": self._expression_to_json(expr.this),
        }

    def _in_values(self, expr: exp.In) -> list[dict[str, t.Any]] | None:
        """Values of a plain `x in (a, b)`; None for subqueries and the like."""
        extras = {
            key
            for key, value in expr.args.items()
            if value and key not in ("this", "expressions")
        }
        if extras or not expr.expressions:
            return None
        return [self._expression_to_json(e) for e in expr.expressions]

    def _like_json(self, expr: exp.Like | exp.ILike) -> dict[str, t.Any]:
        written = expr.meta.get(STRING_OP_META)
        spec = _STRING_OP_WRAPS.get(written or "")
        if spec and not expr.args.get("negate"):
            node_type, wrap_left, wrap_right = spec
            value = self._unwrap_pattern(expr.expression, wrap_left, wrap_right)
            if value is not None:
                return {
                    "type": node_type,
                    "operand": self._expression_to_json(expr.this),
                    "value": self._expression_to_json(value),
                }
        result: dict[str, t.Any] = {
            "type": "ilike" if isinstance(expr, exp.ILike) else "like",
            "operand": self._expression_to_json(expr.this),
            "pattern": self._expression_to_json(expr.expression),
        }
        if expr.args.get("negate"):
            result["negate"] = True
        return result

    @staticmethod
    def _unwrap_pattern(
        pattern: exp.Expr, wrap_left: str, wrap_right: str
    ) -> exp.Expr | None:
        """Recover the written value from the LIKE pattern the parser built."""
        if isinstance(pattern, exp.Literal) and pattern.is_string:
            text = pattern.this
            end = len(text) - len(wrap_right)
            if (
                text.startswith(wrap_left)
                and text.endswith(wrap_right)
                and end >= len(wrap_left)
            ):
                return exp.Literal.string(text[len(wrap_left) : end])
            return None
        if isinstance(pattern, exp.Concat):
            parts = list(pattern.expressions)
            if wrap_left:
                if not parts or parts[0] != exp.Literal.string(wrap_left):
                    return None
                parts = parts[1:]
            if wrap_right:
                if not parts or parts[-1] != exp.Literal.string(wrap_right):
                    return None
                parts = parts[:-1]
            if len(parts) == 1:
                return parts[0]
        return None

    def _function_json(self, expr: exp.Func) -> dict[str, t.Any] | None:
        """Structured call for functions that spell as NAME(arg, ...), else None.

        The candidate spelling is checked against the ASQL text of the node so
        that functions with their own syntax (CAST ... AS, EXTRACT ... FROM,
        DATE_TRUNC unit order, windows) fall through to a raw node instead of
        being re-read with different arguments.
        """
        if isinstance(expr, exp.Count):
            this = expr.this
            if this is None or isinstance(this, exp.Star):
                if not expr.expressions and not expr.args.get("big_int"):
                    return {
                        "type": "function",
                        "name": "count",
                        "args": [{"type": "star"}],
                    }
                return None
            if (
                isinstance(this, exp.Distinct)
                and len(this.expressions) == 1
                and not this.args.get("on")
                and not expr.expressions
            ):
                return {
                    "type": "function",
                    "name": "count",
                    "args": [self._expression_to_json(this.expressions[0])],
                    "distinct": True,
                }

        args: list[exp.Expr] = []
        for value in expr.args.values():
            if value is None or value is False or value == []:
                continue
            if isinstance(value, list):
                if not all(isinstance(item, exp.Expr) for item in value):
                    return None
                args.extend(value)
            elif isinstance(value, exp.Expr):
                args.append(value)
            else:
                return None

        name = expr.name if isinstance(expr, exp.Anonymous) else expr.sql_name()
        if not name:
            return None
        candidate = f"{name}({', '.join(self._text(arg) for arg in args)})"
        if candidate != self._text(expr):
            return None
        return {
            "type": "function",
            "name": name,
            "args": [self._expression_to_json(arg) for arg in args],
        }

    # ------------------------------------------------------------------
    # SELECT / column operators / EXTEND
    # ------------------------------------------------------------------

    def _select_transforms(
        self, select: exp.Select, cte_name: str | None
    ) -> list[dict[str, t.Any]] | None:
        """Transforms for the projection of a SELECT without GROUP BY.

        Returns None when the projection has no pipeline spelling.
        """
        exprs = list(select.expressions)
        if not exprs:
            return []
        star = exprs[0] if isinstance(exprs[0], exp.Star) else None
        if star is not None:
            if any(isinstance(e, exp.Star) for e in exprs[1:]):
                return None
            others = exprs[1:]
            if star.args.get("replace") or star.args.get("rename"):
                return None
            if not all(isinstance(e, exp.Alias) for e in others):
                return None
            aliases = t.cast(list[exp.Alias], others)
            except_cols = star.args.get("except_") or []
            if not except_cols:
                if not aliases:
                    return []  # plain SELECT *
                if cte_name and AUTO_CTE_RE.fullmatch(cte_name):
                    return [self._extend_transform(aliases)]  # `extend` stage
                # `select *, expr as alias` in place
                star_columns: list[dict[str, t.Any]] = [{"name": "*"}] + [
                    {"name": alias.alias, "expression": self._text(alias.this)}
                    for alias in aliases
                ]
                return [
                    {
                        "type": "select",
                        "columns": star_columns,
                        "_columns": star_columns,
                    }
                ]
            if not all(self._is_plain_column(c) and not c.table for c in except_cols):
                return None
            return self._column_op_transforms([c.name for c in except_cols], aliases)

        columns = self._select_columns(exprs)
        if columns is None:
            return None
        select_comments: list[str] = []
        for expr in exprs:
            if expr_comments := self._get_comments(expr):
                select_comments.extend(expr_comments)
        transform: dict[str, t.Any] = {
            "type": "select",
            "columns": [
                {
                    key: value
                    for key, value in c.items()
                    if key in ("name", "expression", "source")
                }
                for c in columns
            ],
            "_columns": columns,
        }
        if select_comments:
            transform["comments"] = select_comments
        return [transform]

    def _extend_transform(self, aliases: list[exp.Alias]) -> dict[str, t.Any]:
        columns = [
            {"name": alias.alias, "expression": self._text(alias.this)}
            for alias in aliases
        ]
        return {"type": "extend", "columns": columns}

    def _column_op_transforms(
        self, except_names: list[str], aliases: list[exp.Alias]
    ) -> list[dict[str, t.Any]] | None:
        """Decompose `* EXCLUDE (...), a AS b, f(c) AS c` into except/rename/replace.

        The parser merges those stages into one projection (excluded names
        sorted, aliases in stage order), so emitting them in alias order
        rebuilds the same projection.
        """
        consumed: set[str] = set()
        ops: list[tuple[str, dict[str, t.Any]]] = []
        for alias in aliases:
            source = alias.this
            new_name = alias.alias
            if (
                self._is_plain_column(source)
                and not source.table
                and source.name in except_names
                and source.name not in consumed
                and source.name != new_name
            ):
                ops.append(("rename", {"from": source.name, "to": new_name}))
                consumed.add(source.name)
            elif new_name in except_names and new_name not in consumed:
                ops.append(
                    ("replace", {"name": new_name, "expression": self._text(source)})
                )
                consumed.add(new_name)
            else:
                return None

        transforms: list[dict[str, t.Any]] = []
        leftover = [name for name in except_names if name not in consumed]
        if leftover:
            transforms.append({"type": "except", "columns": leftover})
        for kind, entry in ops:
            if transforms and transforms[-1]["type"] == kind:
                key = "mappings" if kind == "rename" else "columns"
                transforms[-1][key].append(entry)
            elif kind == "rename":
                transforms.append({"type": "rename", "mappings": [entry]})
            else:
                transforms.append({"type": "replace", "columns": [entry]})
        return transforms

    def _select_columns(self, exprs: list[exp.Expr]) -> list[dict[str, t.Any]] | None:
        """Column entries for an explicit projection (no bare *)."""
        columns = []
        for expr in exprs:
            if isinstance(expr, exp.Star):
                return None
            if isinstance(expr, exp.Alias):
                col_info: dict[str, t.Any] = {
                    "name": expr.alias,
                    "expression": self._text(expr.this),
                }
                if hasattr(expr, "type") and expr.type:
                    col_info["type"] = str(expr.type)
                columns.append(col_info)
            elif isinstance(expr, exp.Column) and (
                isinstance(expr.this, exp.Star) or expr.name == "*"
            ):
                # orders.* keeps its table; json_to_asql pastes the expression.
                columns.append({"name": "*", "expression": self._text(expr)})
            elif self._is_plain_column(expr):
                col_info = {"name": _name_part(expr.name)}
                if expr.table:
                    col_info["source"] = expr.table  # json_to_asql writes t.col
                if hasattr(expr, "type") and expr.type:
                    col_info["type"] = str(expr.type)
                columns.append(col_info)
            else:
                text = self._text(expr)
                columns.append({"name": text, "expression": text})
        return columns

    # ------------------------------------------------------------------
    # GROUP BY
    # ------------------------------------------------------------------

    def _group_by_transforms(
        self, select: exp.Select, group: exp.Group
    ) -> list[dict[str, t.Any]] | None:
        """group_by transform (+ a select transform when the projection is not
        `dimensions, aggregates`), or None when GROUP BY has no pipeline form."""
        extras = {
            key for key, value in group.args.items() if value and key != "expressions"
        }
        if extras:
            return None

        dims: list[t.Any] = []
        dim_columns: list[dict[str, t.Any]] = []
        for expr in group.expressions:
            if self._is_plain_column(expr):
                dims.append(self._column_name(expr))
                dim_info: dict[str, t.Any] = {"name": expr.name}
                if expr.table:
                    dim_info["source"] = expr.table
                if hasattr(expr, "type") and expr.type:
                    dim_info["type"] = str(expr.type)
                dim_columns.append(dim_info)
            elif isinstance(expr, exp.Alias):
                dims.append({"expression": self._text(expr.this), "alias": expr.alias})
                dim_columns.append({"name": expr.alias})
            else:
                dims.append({"expression": self._text(expr), "alias": None})
                dim_columns.append({"name": self._projected_name(select, expr)})

        select_exprs = list(select.expressions)
        if [type(e) for e in select_exprs] == [exp.Star]:
            # bare `group by k`: the projection is still *
            return [
                {
                    "type": "group_by",
                    "dimensions": dims,
                    "aggregates": [],
                    "_columns": dim_columns,
                }
            ]

        n_dims = len(group.expressions)
        leading = select_exprs[:n_dims]
        rest = select_exprs[n_dims:]
        if len(leading) == n_dims and all(
            self._matches_dim(e, g)
            for e, g in zip(leading, group.expressions, strict=True)
        ):
            aggregates = []
            agg_columns = []
            for expr in rest:
                aggregates.append(self._aggregate_json(expr))
                agg_columns.append(
                    {
                        "name": aggregates[-1].get("alias")
                        or aggregates[-1]["expression"]
                    }
                )
            if aggregates:
                return [
                    {
                        "type": "group_by",
                        "dimensions": dims,
                        "aggregates": aggregates,
                        "_columns": dim_columns + agg_columns,
                    }
                ]

        # Projection that is not `dims, aggs`: `group by k` then an explicit select
        columns = self._select_columns(select_exprs)
        if columns is None:
            return None
        return [
            {
                "type": "group_by",
                "dimensions": dims,
                "aggregates": [],
                "_columns": dim_columns,
            },
            {
                "type": "select",
                "columns": [
                    {
                        key: value
                        for key, value in c.items()
                        if key in ("name", "expression", "source")
                    }
                    for c in columns
                ],
                "_columns": columns,
            },
        ]

    def _projected_name(self, select: exp.Select, dim: exp.Expr) -> str:
        """Output name of a computed dimension (its alias in the projection)."""
        for expr in select.expressions:
            if isinstance(expr, exp.Alias) and self._matches_dim(expr, dim):
                return expr.alias
        return self._text(dim)

    def _matches_dim(self, select_expr: exp.Expr, dim: exp.Expr) -> bool:
        """Does a projection entry re-select this GROUP BY key?"""
        if isinstance(dim, exp.Alias):
            return select_expr == dim or (
                isinstance(select_expr, exp.Alias)
                and select_expr.alias == dim.alias
                and self._matches_dim(select_expr.this, dim.this)
            )
        dim_core = dim.this if isinstance(dim, Spine) else dim
        core = select_expr.this if isinstance(select_expr, exp.Alias) else select_expr
        if core in (dim, dim_core):
            return True
        # `week(x)`: the key carries an unresolved WeekStart, the projection the
        # resolved one; both spell the same.
        return self._text(core) == self._text(dim_core)

    def _aggregate_json(self, expr: exp.Expr) -> dict[str, t.Any]:
        """Aggregate entry: structured for `agg(column)`, expression text otherwise."""
        alias = expr.alias if isinstance(expr, exp.Alias) else None
        core = expr.this if isinstance(expr, exp.Alias) else expr
        if isinstance(core, exp.AggFunc):
            this = core.this
            distinct = False
            if (
                isinstance(core, exp.Count)
                and isinstance(this, exp.Distinct)
                and len(this.expressions) == 1
            ):
                this, distinct = this.expressions[0], True
            if this is None or isinstance(this, exp.Star):
                column: str | None = "*"
            elif self._is_plain_column(this):
                column = self._column_name(this)
            else:
                column = None
            if column is not None:
                function = core.sql_name().lower()
                spelled = (
                    f"{core.sql_name()}({'DISTINCT ' if distinct else ''}"
                    f"{self._text(this) if column != '*' else '*'})"
                )
                if spelled == self._text(core):
                    entry: dict[str, t.Any] = {
                        "function": function,
                        "column": column,
                        "alias": alias,
                    }
                    if distinct:
                        entry["distinct"] = True
                    return entry
        return {"expression": self._text(core), "alias": alias}

    # ------------------------------------------------------------------
    # ORDER BY / LIMIT / OFFSET
    # ------------------------------------------------------------------

    def _extract_order_columns(self, order: exp.Order) -> list[dict[str, t.Any]]:
        """Extract order by expressions."""
        expressions = []
        for ordered in order.expressions:
            if not isinstance(ordered, exp.Ordered):
                expressions.append(self._raw(ordered))
                continue
            key = ordered.this
            desc = bool(ordered.args.get("desc"))
            entry: dict[str, t.Any]
            if self._is_plain_column(key):
                entry = {"column": self._column_name(key)}
            else:
                entry = {"expression": self._text(key)}
            entry["direction"] = "desc" if desc else "asc"
            # `-col` reads back as nulls last and plain `col` as nulls first;
            # only spell out the other combinations.
            nulls_first = ordered.args.get("nulls_first")
            if desc and nulls_first is True:
                entry["nulls"] = "first"
            elif not desc and nulls_first is False:
                entry["nulls"] = "last"
            if ordered.args.get("explicit") or ordered.args.get("with_fill"):
                entry = self._raw(ordered)
            expressions.append(entry)

        return expressions

    def _count_transform(
        self, key: str, clause: exp.Limit | exp.Offset
    ) -> dict[str, t.Any]:
        """limit/offset transform; a non-integer count keeps its expression."""
        extras = {
            k for k, v in clause.args.items() if v and k not in ("expression", "this")
        }
        value = clause.expression
        if not extras and isinstance(value, exp.Literal) and value.is_number:
            try:
                return {"type": key, "count": int(value.this)}
            except ValueError:
                pass
        return {"type": key, "count": None, "expression": self._text(clause.expression)}
