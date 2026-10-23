"""ASQL dialect implementation using SQLGlot's TRANSFORM_PARSERS pattern.

ASQL (Analytic SQL) is a human-readable, pipeline-based query language that
transpiles to SQL. This dialect implements the core ASQL parsing using SQLGlot's
built-in infrastructure.

Key features:
- FROM-first syntax: `from users where status = 'active'`
- Pipeline operators: `from users | where x | group by y`
- Descending order shorthand: `-column` → `column DESC`
- Proper pipeline semantics: `group by X | where Y` → CTE + WHERE

Settings are passed via the ASQL dialect constructor:
    from asql.dialect import ASQL
    asql = ASQL(extend_dialect="postgres", auto_spine=False)
    sqlglot.transpile(query, read=asql, write="postgres")
"""

# mypy: disable-error-code="no-untyped-call"
# This file subclasses sqlglot.Parser and calls its private _match* methods
# throughout.  sqlglot ships py.typed but those internal methods carry no return
# annotations, so every inherited call would fire no-untyped-call.

from __future__ import annotations

import re
import typing as t

import sqlglot
from sqlglot import exp
from sqlglot.helper import seq_get
from sqlglot.parser import Parser
from sqlglot.tokens import Token, TokenType

from asql.dialect.transforms.count_entity import ENTITY_CANDIDATE
from asql.errors import ASQLCompilationError
from asql.expressions import Spine
from asql.functions import (
    ASQL_FUNCTION_REGISTRY,
    NATURAL_DATE_DIRECTIONS,
    NATURAL_DATE_UNITS,
    SAMPLE_META,
    STRING_OP_META,
    build_bucket,
    get_natural_agg,
    get_natural_date_function,
    remember_call,
)

if t.TYPE_CHECKING:
    pass


def _build_spine_expression(args: list[t.Any]) -> Spine:
    """Build a Spine expression from function arguments.

    spine(month(date)) → Spine(this=month(date))
    """
    col = seq_get(args, 0)
    if col is None:
        # Return empty Spine - will be caught as invalid
        return Spine(this=exp.Null())
    return Spine(this=col)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
# Module-level helpers following SQLGlot/PRQL patterns.
# =============================================================================


def _select_all(table: exp.Expr) -> exp.Select:
    """Create SELECT * FROM table expression.

    PRQL pattern for cleanly building initial queries from FROM clauses.
    """
    return exp.select("*").from_(table, copy=False)


# query.meta key: "block" once an aggregate block fixed the grouped projection, "bare"
# for a `group by k` still awaiting its select, "selected" after that select.
_GROUP_STAGE = "asql_group_stage"

# query.meta key set on the pass-through `SELECT * FROM name` that `stash as name`
# leaves behind, so a following top-level `from` can start a new pipeline over it.
_STASHED = "asql_stashed"

# Names the pipe parser gives the stages it closes itself.
AUTO_CTE_RE = re.compile(r"__tmp\d+")


# Each dialect spells intervals differently; a structured unit lets sqlglot
# emit INTERVAL '7' DAY (BigQuery, MySQL, Trino) or INTERVAL '7 DAY' (Postgres).
def _interval(number: str, unit: str) -> exp.Interval:
    return exp.Interval(
        this=exp.Literal.string(number), unit=exp.var(unit.upper().removesuffix("S"))
    )


# `col::PST` names a region, not a fixed offset: warehouses other than Postgres
# accept only IANA names, so each abbreviation means its region's zone.
TIMEZONE_ABBREVIATIONS: dict[str, str] = {
    "UTC": "UTC",
    "GMT": "UTC",
    **dict.fromkeys(("PT", "PST", "PDT"), "America/Los_Angeles"),
    **dict.fromkeys(("MT", "MST", "MDT"), "America/Denver"),
    **dict.fromkeys(("CT", "CST", "CDT"), "America/Chicago"),
    **dict.fromkeys(("ET", "EST", "EDT"), "America/New_York"),
}


def _build_now(args: list[exp.Expr]) -> exp.Expr:
    if args:
        raise ValueError("now() takes no arguments")
    return exp.CurrentTimestamp()


def _dcolon(parser: Parser, this: exp.Expr, to: exp.Expr) -> exp.Expr:
    if isinstance(to, exp.Literal) and to.is_string:
        return exp.ConvertTimezone(target_tz=to, timestamp=this)
    return parser.build_cast(strict=parser.STRICT_CAST, this=this, to=to)


class ASQLParser(Parser):
    """ASQL Parser that reads settings from dialect.settings.

    Settings are passed via the ASQL dialect constructor:
        asql = ASQL(extend_dialect="postgres", auto_spine=False)
        sqlglot.transpile(query, read=asql, write="postgres")

    Or via inline SET statements in the query:
        SET extend_dialect = 'postgres';
        SET auto_spine = false;
        from orders group by month(date)
    """

    # Transform keywords that should not be treated as table aliases
    _TRANSFORM_KEYWORDS = frozenset(
        {
            "PER",
            "STASH",
            "EXTEND",
            "EXPLODE",
            "SAMPLE",
            "RENAME",
            "REPLACE",
            "DEDUPLICATE",
            "NUMBER",
            "RANK",
            "DENSE",
            "COHORT",
            "RECURSE",
            "SPINE",
        }
    )

    def _get_setting(self, name: str, default: t.Any = None) -> t.Any:
        """Get a setting from dialect.settings with fallback to default."""
        if (
            hasattr(self, "dialect")
            and self.dialect
            and hasattr(self.dialect, "settings")
        ):
            return self.dialect.settings.get(name, default)
        return default

    def _set_setting(self, name: str, value: t.Any) -> None:
        """Set a setting in dialect.settings (mutates dialect)."""
        if (
            hasattr(self, "dialect")
            and self.dialect
            and hasattr(self.dialect, "settings")
        ):
            self.dialect.settings[name] = value

    def parse(self, raw_tokens: list[Token], sql: str) -> list[exp.Expr | None]:
        """Parse tokens and apply ASQL transforms.

        This overrides the base parse() to:
        1. Process SET statements → mutate dialect.settings
        2. Apply ASQL-specific transforms
        3. Remove SET statements from output (they're ASQL config, not SQL)
        """
        # Call parent parse
        statements = super().parse(raw_tokens, sql)

        # Process statements: extract SETs, apply transforms
        result: list[exp.Expr | None] = []
        for stmt in statements:
            if stmt is None:
                result.append(stmt)
            elif isinstance(stmt, exp.Set):
                # Process SET statement - mutate dialect settings
                self._apply_set_to_dialect(stmt)
                # Don't include SET in output (it's ASQL config, not real SQL)
            else:
                # Apply ASQL transforms
                transformed = self._apply_asql_transforms(stmt)
                result.append(transformed)

        return result

    # Valid values for settings that have constrained options
    _VALID_WEEK_START = frozenset({"monday", "sunday"})
    _VALID_RELATIVE_DATE_TYPE = frozenset({"timestamp", "date"})
    _VALID_EQUALITY = frozenset({"single", "double"})
    _VALID_COUNT = frozenset({"hash", "function"})
    _VALID_COALESCE = frozenset({"operator", "function"})
    _VALID_DESCENDING = frozenset({"prefix", "suffix"})
    _VALID_CAST = frozenset({"double_colon", "function"})
    _VALID_QUOTES = frozenset({"double", "single"})
    _VALID_FUNCTION_SHORTHAND = frozenset({"underscore", "space", "parens"})

    # PER clause: qualify operations (FIRST/LAST) - maps to (reverse_order,)
    # FIRST: keep order as-is, LAST: reverse the order
    _PER_QUALIFY_OPS: dict[tuple[str, ...], bool] = {
        ("FIRST",): False,  # Don't reverse order
        ("LAST",): True,  # Reverse order for "last"
    }

    # PER clause: window function operations - maps to (expr_class, default_alias)
    _PER_WINDOW_OPS: dict[tuple[str, ...], tuple[type[exp.Func], str]] = {
        ("NUMBER",): (exp.RowNumber, "row_num"),
        ("RANK",): (exp.Rank, "rank"),
        ("DENSE", "RANK"): (exp.DenseRank, "dense_rank"),
        ("DENSE_RANK",): (exp.DenseRank, "dense_rank"),
    }

    def _apply_set_to_dialect(self, set_stmt: exp.Set) -> None:
        """Mutate self.dialect.settings based on SET statement.

        Handles:
            SET extend_dialect = 'postgres'
            SET auto_spine = false
            SET count_alias_prefix = 'num'  → alias_prefixes['count'] = 'num'
            SET count_alias_template = '...' → alias_templates['count'] = '...'

        Validates setting values where applicable.
        """
        for item in set_stmt.expressions:
            if not hasattr(item, "this") or not isinstance(item.this, exp.EQ):
                continue

            eq = item.this
            key = eq.this.sql().lower().strip("\"'`")
            value_expr = eq.expression

            # Extract value
            if isinstance(value_expr, exp.Boolean):
                value = value_expr.this
            elif isinstance(value_expr, exp.Literal):
                value = value_expr.this.strip("\"'")
                if isinstance(value, str):
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
            elif isinstance(value_expr, exp.Var):
                value = value_expr.this
            else:
                value = value_expr.sql().strip("\"'")

            # Handle special key patterns
            if key == "dialect":
                # "dialect" is an alias for "extend_dialect"
                key = "extend_dialect"

            value = self.normalize_setting(key, value)

            if key.endswith("_alias_prefix"):
                # e.g., count_alias_prefix = 'num' → alias_prefixes['count'] = 'num'
                func_name = key[:-13]  # Remove "_alias_prefix"
                # DEFENSIVE: .copy() prevents mutating SETTING_DEFAULTS shared dict
                prefixes = self._get_setting("alias_prefixes", {}).copy()
                prefixes[func_name] = str(value)
                self._set_setting("alias_prefixes", prefixes)
            elif key.endswith("_alias_template"):
                # e.g., count_alias_template = '...' → alias_templates['count'] = '...'
                func_name = key[:-15]  # Remove "_alias_template"
                # DEFENSIVE: .copy() prevents mutating SETTING_DEFAULTS shared dict
                templates = self._get_setting("alias_templates", {}).copy()
                templates[func_name] = str(value)
                self._set_setting("alias_templates", templates)
            else:
                # Standard setting
                self._set_setting(key, value)

    @classmethod
    def normalize_setting(cls, key: str, value: t.Any) -> t.Any:
        """Validate a setting value and lowercase constrained choices.

        Raises ValueError for invalid values.
        """
        validators = {
            "week_start": (cls._VALID_WEEK_START, "must be 'monday' or 'sunday'"),
            "relative_date_type": (
                cls._VALID_RELATIVE_DATE_TYPE,
                "must be 'timestamp' or 'date'",
            ),
            "equality": (cls._VALID_EQUALITY, "must be 'single' or 'double'"),
            "count": (cls._VALID_COUNT, "must be 'hash' or 'function'"),
            "coalesce": (cls._VALID_COALESCE, "must be 'operator' or 'function'"),
            "descending": (cls._VALID_DESCENDING, "must be 'prefix' or 'suffix'"),
            "cast": (cls._VALID_CAST, "must be 'double_colon' or 'function'"),
            "quotes": (cls._VALID_QUOTES, "must be 'double' or 'single'"),
            "function_shorthand": (
                cls._VALID_FUNCTION_SHORTHAND,
                "must be 'underscore', 'space', or 'parens'",
            ),
        }

        if key in validators:
            valid_values, error_msg = validators[key]
            str_value = str(value).lower() if value is not None else ""
            if str_value not in valid_values:
                raise ValueError(f"Invalid value for {key}: '{value}' - {error_msg}")
            return str_value

        # Validate boolean settings
        boolean_settings = {
            "auto_spine",
            "infer_join_keys",
            "fanout_protection",
            "include_transpilation_comments",
            "passthrough_comments",
            "squash_empty_ctes",
            "keep_final_empty_cte",
            "ignore_aliases",
        }
        if key in boolean_settings and not isinstance(value, bool):
            raise ValueError(
                f"Invalid value for {key}: '{value}' - must be true or false"
            )
        return value

    def _apply_asql_transforms(self, stmt: exp.Expr) -> exp.Expr:
        """Apply ASQL-specific AST transforms after parsing.

        Reads all settings from self.dialect.settings.

        Transform order (Phase 1 - no output dialect needed):
        1. Underscore shorthands (days_since_created_at → DATEDIFF)
        2. Implicit function aliases (SUM(amount) → SUM(amount) AS sum_amount)
        3. Auto-aliasing (function calls without explicit aliases)
        4. FK shorthand (ON user_id → ON orders.user_id = users.id) - needs schema
        5. Auto-qualify columns (resolve ambiguous columns in JOINs)

        Transform order (Phase 2 - generate universal SQL):
        7. Alias reuse → CTE chains (works on all dialects including DuckDB)
        8. List comprehension → ARRAY(SELECT...) (works on all dialects)
        9. Auto-spine → gap-filling CTEs (SQLGlot converts generate_series)
        10. Remove guarantee wrappers (cleanup)
        """
        # Read settings from dialect
        schema = self._get_setting("schema")
        week_start = self._get_setting("week_start", "monday")
        relative_date_type = self._get_setting("relative_date_type", "timestamp")
        alias_template = self._get_setting("alias_template")
        alias_prefixes = self._get_setting("alias_prefixes", {})
        alias_templates = self._get_setting("alias_templates", {})
        infer_join_keys = self._get_setting("infer_join_keys", False)
        fanout_protection = self._get_setting("fanout_protection", True)

        # Build CompileSettings object for transform functions
        from asql.config import CompileSettings

        settings = CompileSettings(
            week_start=week_start,
            schema=schema,
            alias_template=alias_template,
            alias_prefixes=alias_prefixes,
            alias_templates=alias_templates,
            relative_date_type=relative_date_type,
            infer_join_keys=infer_join_keys,
            fanout_protection=fanout_protection,
            include_transpilation_comments=self._get_setting(
                "include_transpilation_comments", True
            ),
        )

        # Import parser-stage transforms (from asql/dialect/transforms/)
        from asql.dialect.transforms.auto_alias import apply_auto_aliasing
        from asql.dialect.transforms.auto_qualify import auto_qualify_columns
        from asql.dialect.transforms.count_entity import resolve_count_entities
        from asql.dialect.transforms.date_units import (
            fill_default_week_start,
            reject_numeric_comparisons,
        )
        from asql.dialect.transforms.join_fk_shorthand import transform_fk_shorthand
        from asql.dialect.transforms.pivot_group_by import apply_pivot_group_by
        from asql.dialect.transforms.underscore_shorthands import (
            apply_implicit_function_aliases,
            apply_since_until_underscore_shorthands,
        )

        # === Phase 1: Basic transforms (no dialect/schema required) ===
        stmt = apply_pivot_group_by(stmt)
        stmt = reject_numeric_comparisons(stmt)
        stmt = fill_default_week_start(stmt, week_start)
        stmt = apply_since_until_underscore_shorthands(stmt, settings)
        stmt = resolve_count_entities(stmt, settings)
        stmt = apply_implicit_function_aliases(stmt, settings)
        stmt = apply_auto_aliasing(stmt, settings)

        # === Phase 2: Join inference (uses the schema when there is one) ===
        stmt = transform_fk_shorthand(stmt, settings)

        # Auto-qualify columns in joins (expands SELECT * to table.* for each table)
        stmt = auto_qualify_columns(stmt)

        # List comprehension: Convert to ARRAY(SELECT...) which works everywhere
        # This is done in parser because it doesn't need output dialect knowledge -
        # the ARRAY(SELECT...) form works on all dialects. DuckDB post-processing
        # in list_comprehension.py converts it back to native syntax.
        stmt = self._transform_list_comprehensions_universal(stmt)

        # === Dialect-aware transforms moved to asql.transpile() ===
        # The following transforms need the OUTPUT dialect and run in asql.transpile():
        # - spine_transform (exp.Spine → gap-filling CTEs)
        # - alias_reuse (same-row refs → CTEs for non-DuckDB)
        # - column_operators (* EXCEPT → explicit columns)

        return stmt

    def _transform_list_comprehensions_universal(self, stmt: exp.Expr) -> exp.Expr:
        """Convert list comprehensions to ARRAY(SELECT...) which works on all dialects.

        Transforms: [x * 2 FOR x IN arr] → ARRAY(SELECT x * 2 FROM UNNEST(arr) AS x)
        """
        for node in stmt.walk():
            if isinstance(node, exp.Array):
                exprs = node.expressions
                if exprs and isinstance(exprs[0], exp.Comprehension):
                    comp = exprs[0]
                    converted = self._comprehension_to_array_select(comp)
                    node.set("expressions", converted.expressions)
        return stmt

    # Token types that are join operators (should not be parsed as table aliases)
    _JOIN_OPERATOR_TOKENS = frozenset(
        {
            TokenType.AMP,  # &
            TokenType.QMARK_AMP,  # &? or ?&
            TokenType.PLACEHOLDER,  # ?&? (when text is ?&?)
            TokenType.STAR,  # * for CROSS JOIN
        }
    )

    def _parse_table_alias(
        self, alias_tokens: t.Collection[TokenType] | None = None
    ) -> exp.TableAlias | None:
        """Override to prevent ASQL transform keywords and join operators from being treated as table aliases.

        Examples that must work:
            from orders per customer_id first by created_at
            from customers & orders on customers.id = orders.customer_id

        Without this, 'per' is parsed as table alias: FROM orders AS per
        And join operators would be consumed incorrectly.
        """
        # Check if current token is a join operator
        if self._curr and self._curr.token_type in self._JOIN_OPERATOR_TOKENS:
            # Special check for PLACEHOLDER - only skip if it's ?&?
            if self._curr.token_type == TokenType.PLACEHOLDER:
                if self._curr.text == "?&?":
                    return None
            else:
                return None

        # Check if current token is a transform keyword
        if self._curr and self._curr.text.upper() in self._TRANSFORM_KEYWORDS:
            return None
        return super()._parse_table_alias(alias_tokens)

    def _match(
        self,
        token_type: TokenType,
        advance: bool = True,
        expression: exp.Expr | None = None,
    ) -> bool:
        """`<table> * <table>` is ASQL's CROSS JOIN operator.

        SQLGlot's ``_parse_table`` consumes a ``*`` right after a table name as
        Postgres's no-op wildcard suffix. Refusing a star that a bare name
        follows leaves it for the join parser; no other sqlglot ``_match(STAR)``
        site (``SELECT *`` and ``a * b`` go through ``_match_set``) can see
        that token pair. ASQL's own ``#*`` shorthand steps past its star with
        ``_advance_past_count_star`` so an implicit alias after it is not
        mistaken for a joined table.
        """
        if (
            token_type == TokenType.STAR
            and self._curr.token_type == TokenType.STAR
            and self._next.token_type == TokenType.VAR
        ):
            return False
        return super()._match(token_type, advance, expression)

    def _advance_past_count_star(self) -> bool:
        """Consume the ``*`` of ``#*``/``##*`` without the cross-join hook."""
        if self._curr.token_type != TokenType.STAR:
            return False
        self._advance()
        return True

    def _parse_alias(
        self, this: exp.Expr | None, explicit: bool = False
    ) -> exp.Expr | None:
        """Prevent ASQL transform keywords from being treated as implicit aliases.

        Example that must work:
            from t select x stash as tmp

        Without this, `stash` can be parsed as an implicit alias for `x`, leaving
        `as tmp` as an unexpected token.
        """
        if (
            not explicit
            and this is not None
            and self._curr
            and self._curr.token_type == TokenType.VAR
            and self._curr.text.upper() in self.TRANSFORM_PARSERS
        ):
            return this
        return super()._parse_alias(this, explicit=explicit)

    @staticmethod
    def _apply_star_column_override(
        select_expressions: list[exp.Expr],
        source_columns: set[str] | None = None,
    ) -> None:
        """
        Apply ASQL's "star override" behavior:

            select *, upper(name) as name

        becomes an AST equivalent of:

            select * EXCEPT(name), upper(name) as name

        so explicit aliases replace columns from the star expansion instead of duplicating them.
        When ``source_columns`` is known, only aliases that name one of them are excluded
        (engines reject excluding a column that does not exist).
        """
        if not select_expressions:
            return

        star_expr: exp.Star | None = None
        for select_expression in select_expressions:
            if isinstance(select_expression, exp.Star):
                star_expr = select_expression
                break

        if not star_expr:
            return

        except_names: list[str] = []
        for select_expression in select_expressions:
            alias = select_expression.alias
            if alias and (source_columns is None or alias in source_columns):
                except_names.append(alias)

        if not except_names:
            return

        star_expr.set(
            "except_",
            [exp.Column(this=exp.to_identifier(name)) for name in except_names],
        )

    def parse_set_operation(
        self, this: exp.Expr | None, consume_pipe: bool = False
    ) -> exp.Expr | None:
        """Override to support ASQL FROM-first queries on the RHS of set operations.

        SQLGlot's default implementation parses the RHS via `_parse_select`, which requires
        SELECT-first SQL. ASQL also allows:

            from a select x
            union all
            from b select x

        so we fall back to parsing the RHS via our FROM-first `_parse_query`.
        """
        start = self._index
        _, side_token, kind_token = self._parse_join_parts()

        side = side_token.text if side_token else None
        kind = kind_token.text if kind_token else None

        if not self._match_set(self.SET_OPERATIONS):
            self._retreat(start)
            return None

        assert self._prev is not None  # _match_set advanced past the matched token
        token_type = self._prev.token_type

        if token_type == TokenType.UNION:
            operation: type[exp.SetOperation] = exp.Union
        elif token_type == TokenType.EXCEPT:
            operation = exp.Except
        else:
            operation = exp.Intersect

        comments = self._prev.comments

        if self._match(TokenType.DISTINCT):
            distinct: bool | None = True
        elif self._match(TokenType.ALL):
            distinct = False
        else:
            distinct = self.dialect.SET_OP_DISTINCT_BY_DEFAULT[operation]
            if distinct is None:
                self.raise_error(f"Expected DISTINCT or ALL for {operation.__name__}")

        by_name = self._match_text_seq("BY", "NAME") or self._match_text_seq(
            "STRICT", "CORRESPONDING"
        )
        if self._match_text_seq("CORRESPONDING"):
            by_name = True
            if not side and not kind:
                kind = "INNER"

        on_column_list = None
        if by_name and self._match_texts(("ON", "BY")):
            on_column_list = self._parse_wrapped_csv(self._parse_column)

        rhs_index = self._index
        expression = self._try_parse(
            lambda: Parser._parse_select(
                self, nested=True, parse_set_operation=False, consume_pipe=consume_pipe
            )
        )
        if not expression:
            self._retreat(rhs_index)
            expression = self._parse_query(nested=True, parse_set_operation=False)
        if not expression:
            self.raise_error(f"Expected a query after {operation.__name__.upper()}")

        return self.expression(
            operation(
                this=this,
                distinct=distinct,
                by_name=by_name,
                expression=expression,
                side=side,
                kind=kind,
                on=on_column_list,
            ),
            comments=comments,
        )

    """Parser for ASQL pipe syntax using TRANSFORM_PARSERS pattern.

    This follows PRQL's pattern:
    1. Start with FROM clause
    2. Build initial SELECT * FROM table
    3. Apply transforms (WHERE, GROUP BY, etc.) in sequence
    4. Use _build_pipe_cte() when transforms require CTE wrapping
    """

    # Time unit keywords for date expressions
    TIME_UNITS = frozenset(
        {
            "day",
            "days",
            "week",
            "weeks",
            "month",
            "months",
            "year",
            "years",
            "hour",
            "hours",
            "minute",
            "minutes",
            "second",
            "seconds",
        }
    )

    # `month of year col` extracts an integer part; `month(col)` truncates.
    _EXTRACT_PARTS: t.ClassVar[dict[tuple[str, str, str], str]] = {
        ("DAY", "OF", "MONTH"): "DAY",
        ("DAY", "OF", "YEAR"): "DOY",
        ("WEEK", "OF", "YEAR"): "WEEK",
        ("MONTH", "OF", "YEAR"): "MONTH",
        ("QUARTER", "OF", "YEAR"): "QUARTER",
    }

    # Use && for AND (like PRQL)
    CONJUNCTION = {
        **Parser.CONJUNCTION,
        TokenType.DAMP: exp.And,
    }

    # Hive-only ordering modifiers: every non-Hive generator silently drops
    # them, so a `sort by` typo would vanish without a trace. Error instead.
    QUERY_MODIFIER_PARSERS: t.ClassVar[
        dict[TokenType, t.Callable[[ASQLParser], t.Any]]
    ] = {
        **Parser.QUERY_MODIFIER_PARSERS,
        TokenType.SORT_BY: lambda self: self._reject_hive_only_modifier("sort by"),
        TokenType.CLUSTER_BY: lambda self: self._reject_hive_only_modifier(
            "cluster by"
        ),
        TokenType.DISTRIBUTE_BY: lambda self: self._reject_hive_only_modifier(
            "distribute by"
        ),
    }

    def _reject_hive_only_modifier(self, keyword: str) -> None:
        self.raise_error(
            f"`{keyword}` is not ASQL — use `order by` (`order by -col` for descending)"
        )

    # ASQL uses || for string concatenation (not OR)
    # DPIPE_IS_STRING_CONCAT handles this at dialect level

    # Pop PLACEHOLDER from COLUMN_OPERATORS to enable ternary ? : parsing
    # (Following ClickHouse's canonical copy-and-pop pattern)
    COLUMN_OPERATORS = Parser.COLUMN_OPERATORS.copy()
    COLUMN_OPERATORS.pop(TokenType.PLACEHOLDER)
    COLUMN_OPERATORS[TokenType.DCOLON] = _dcolon

    def _parse_dcolon(self) -> exp.Expr | None:
        """`col::"Europe/London"` and `col::PST` are timezones; anything else is a type."""
        if self._match(TokenType.STRING):
            return exp.Literal.string(self._prev.text)
        zone = self._curr and TIMEZONE_ABBREVIATIONS.get(self._curr.text.upper())
        if zone and not (self._next and self._next.token_type == TokenType.L_PAREN):
            self._advance()
            return exp.Literal.string(zone)
        return super()._parse_dcolon()

    # Handle @ as date literal prefix (following DuckDB's PLACEHOLDER_PARSERS pattern)
    # @2024-01-15 → DATE '2024-01-15'
    # @2024-01-15T10:30:00 → TIMESTAMP '2024-01-15 10:30:00'
    PLACEHOLDER_PARSERS: t.ClassVar[
        dict[TokenType, t.Callable[[ASQLParser], exp.Expr | None]]
    ] = Parser.PLACEHOLDER_PARSERS.copy()
    PLACEHOLDER_PARSERS[TokenType.PARAMETER] = lambda self: self._parse_date_literal()

    # Custom function parsers (bypass sqlglot's validate_expression arg count checks)
    # Needed for BUCKET(..., start=..., end=..., width=...) which has 4 args but returns a CASE.
    FUNCTION_PARSERS: t.ClassVar[
        dict[str, t.Callable[[ASQLParser], exp.Expr | None]]
    ] = {
        **Parser.FUNCTION_PARSERS,
        "BUCKET": lambda self: self._parse_bucket(),
        "KEY": lambda self: self._parse_key(),
        "SLUGIFY": lambda self: self._parse_slugify(),
        # Window-ish helpers (ported out of preparser window transforms)
        "LAST": lambda self: self._parse_last_ordered(),
        "ARG_MAX": lambda self: self._parse_arg_max_min(is_max=True),
        "ARG_MIN": lambda self: self._parse_arg_max_min(is_max=False),
    }

    # NO_PAREN_FUNCTION_PARSERS: Keywords that start expressions without parentheses
    # Note: WHEN handling is done in _parse_field override to avoid conflicts
    # with SQL CASE WHEN syntax
    NO_PAREN_FUNCTION_PARSERS = Parser.NO_PAREN_FUNCTION_PARSERS.copy()

    # PRIMARY_PARSERS: Handlers for tokens that start primary expressions
    # Used for # count shorthand
    PRIMARY_PARSERS: t.ClassVar[
        dict[TokenType, t.Callable[[ASQLParser, Token], exp.Expr | None]]
    ] = Parser.PRIMARY_PARSERS.copy()
    PRIMARY_PARSERS[TokenType.HASH] = lambda self, token: (
        self._parse_count_shorthand_from_primary()
    )

    # Override PIPE_SYNTAX_TRANSFORM_PARSERS to add GROUP BY support
    # This extends SQLGlot's BigQuery-style pipe syntax
    # Handler signature: (parser, pipeline query) -> transformed query, or None to
    # fall through. The query is a Select at runtime but typed exp.Query throughout
    # this module, so the second parameter stays untyped to bridge the two.
    PIPE_SYNTAX_TRANSFORM_PARSERS: t.ClassVar[
        dict[str, t.Callable[[ASQLParser, t.Any], exp.Query | None]]
    ] = {
        **Parser.PIPE_SYNTAX_TRANSFORM_PARSERS,
        "GROUP BY": lambda self, query: self._parse_asql_pipe_group_by(query),
        "HAVING": lambda self, query: query.having(
            self._parse_assignment(), copy=False
        ),
        "QUALIFY": lambda self, query: query.qualify(
            self._parse_assignment(), copy=False
        ),
    }

    # Transform parsers for FROM-first pipeline operations
    # These handle the transformation keywords that come after FROM (not using |>).
    # Same handler signature as PIPE_SYNTAX_TRANSFORM_PARSERS above.
    TRANSFORM_PARSERS: dict[str, t.Callable[[ASQLParser, t.Any], exp.Query | None]] = {
        # Filtering
        "WHERE": lambda self, query: self._parse_asql_where(query),
        # Selection
        "SELECT": lambda self, query: self._parse_asql_select(query),
        # Core transforms
        "LIMIT": lambda self, query: query.limit(
            self._parse_limit(skip_limit_token=True), copy=False
        ),
        "OFFSET": lambda self, query: query.offset(self._parse_number(), copy=False),
        "ORDER BY": lambda self, query: self._parse_asql_order_by(query),
        "GROUP BY": lambda self, query: self._parse_asql_group_by(query),
        "HAVING": lambda self, query: query.having(
            self._parse_assignment(), copy=False
        ),
        "QUALIFY": lambda self, query: query.qualify(
            self._parse_assignment(), copy=False
        ),
        "EXTEND": lambda self, query: self._parse_asql_extend(query),
        "EXPLODE": lambda self, query: self._parse_asql_explode(query),
        "STASH": lambda self, query: self._parse_asql_stash(query),
        # Standard SQL joins
        "JOIN": lambda self, query: self._parse_asql_join(query, kind="INNER"),
        "LEFT": lambda self, query: self._parse_join_kind(
            query, "LEFT", ("JOIN", "OUTER JOIN")
        ),
        "RIGHT": lambda self, query: self._parse_join_kind(
            query, "RIGHT", ("JOIN", "OUTER JOIN")
        ),
        "FULL": lambda self, query: self._parse_join_kind(
            query, "FULL OUTER", ("OUTER", "JOIN")
        ),
        "CROSS": lambda self, query: self._parse_join_kind(query, "CROSS", ("JOIN",)),
        # ASQL symbolic join operators (& &? ?& ?&? *)
        "ASQL_INNER_JOIN": lambda self, query: self._parse_asql_join(
            query, kind="INNER"
        ),
        "ASQL_QMARK_JOIN": lambda self, query: self._parse_asql_qmark_join(query),
        "ASQL_FULL_JOIN": lambda self, query: self._parse_asql_join(
            query, kind="FULL OUTER"
        ),
        "ASQL_CROSS_JOIN": lambda self, query: self._parse_asql_join(
            query, kind="CROSS"
        ),
        # Column operations
        "DISTINCT": lambda self, query: self._parse_asql_distinct(query),
        "EXCEPT": lambda self, query: self._parse_asql_except(query),
        "RENAME": lambda self, query: self._parse_asql_rename(query),
        "REPLACE": lambda self, query: self._parse_asql_replace(query),
        "SAMPLE": lambda self, query: self._parse_asql_sample(query),
        # Window/ranking operations
        "PER": lambda self, query: self._parse_asql_per(query),
        "NUMBER": lambda self, query: self._parse_asql_standalone_rank(
            query, exp.RowNumber, "row_num"
        ),
        "RANK": lambda self, query: self._parse_asql_standalone_rank(
            query, exp.Rank, "rank"
        ),
        "DENSE": lambda self, query: self._parse_asql_dense_rank_standalone(query),
        "DEDUPLICATE": lambda self, query: self._parse_asql_deduplicate(query),
        # Advanced transforms
        "RECURSE": lambda self, query: self._parse_asql_recurse(query),
        # Spine - explicit gap-filling: spine by month(date) (aggs)
        "SPINE": lambda self, query: self._parse_asql_spine_by(query),
    }

    # Steps that read a grouped query's output as a table (see _apply_pipeline_transform).
    _STEPS_ON_GROUPED_OUTPUT = frozenset(
        {
            "WHERE",
            "SELECT",
            "EXTEND",
            "EXPLODE",
            "JOIN",
            "LEFT",
            "RIGHT",
            "FULL",
            "CROSS",
            "ASQL_INNER_JOIN",
            "ASQL_QMARK_JOIN",
            "ASQL_FULL_JOIN",
            "ASQL_CROSS_JOIN",
            "EXCEPT",
            "RENAME",
            "REPLACE",
            "PER",
            "NUMBER",
            "RANK",
            "DENSE",
            "DEDUPLICATE",
            "GROUP BY",
            "SPINE",
        }
    )

    # Single-word transforms for efficient _match_texts lookup
    # (Multi-word transforms like "GROUP BY" are tokenized as single tokens)
    _SINGLE_WORD_TRANSFORMS = frozenset(k for k in TRANSFORM_PARSERS if " " not in k)

    # Token-type based transform starters (these are tokenized as keywords, not VAR).
    _TOKEN_TRANSFORMS: dict[TokenType, str] = {
        TokenType.WHERE: "WHERE",
        TokenType.SELECT: "SELECT",
        TokenType.LIMIT: "LIMIT",
        TokenType.OFFSET: "OFFSET",
        TokenType.HAVING: "HAVING",
        TokenType.JOIN: "JOIN",
        TokenType.LEFT: "LEFT",
        TokenType.RIGHT: "RIGHT",
        TokenType.FULL: "FULL",
        TokenType.CROSS: "CROSS",
        TokenType.DISTINCT: "DISTINCT",
        TokenType.EXCEPT: "EXCEPT",
        TokenType.QUALIFY: "QUALIFY",
        # ASQL join operators
        TokenType.AMP: "ASQL_INNER_JOIN",  # & → INNER JOIN
        TokenType.QMARK_AMP: "ASQL_QMARK_JOIN",  # &? or ?& → LEFT/RIGHT JOIN
        TokenType.PLACEHOLDER: "ASQL_FULL_JOIN",  # ?&? → FULL OUTER JOIN (checked in _match_transform)
        TokenType.STAR: "ASQL_CROSS_JOIN",  # * → CROSS JOIN
    }

    # Function aliases for natural language
    FUNCTIONS: t.ClassVar[dict[str, t.Callable[[list[exp.Expr]], exp.Expr]]] = {
        **Parser.FUNCTIONS,
        # Include all functions from the shared registry
        **ASQL_FUNCTION_REGISTRY,
        # Additional aliases
        "TOTAL": exp.Sum.from_arg_list,
        "NOW": _build_now,
        "AVERAGE": exp.Avg.from_arg_list,
        "PRIOR": lambda args: exp.Lag(
            this=seq_get(args, 0), offset=seq_get(args, 1) or exp.Literal.number(1)
        ),
        "NEXT": lambda args: exp.Lead(
            this=seq_get(args, 0), offset=seq_get(args, 1) or exp.Literal.number(1)
        ),
        # Spine function for explicit gap-filling: group by spine(month(date)), region
        "SPINE": lambda args: _build_spine_expression(args),
        # uniq(col) → COUNT(DISTINCT col)
        "UNIQ": lambda args: exp.Count(this=exp.Distinct(expressions=args)),
    }

    def _parse_pivot(self) -> exp.Pivot | None:
        """Parse PIVOT/UNPIVOT expressions.

        Handles both standard SQL syntax and ASQL's simplified syntax:

        PIVOT:
          SQL:  PIVOT (AGG FOR col IN (values))
          ASQL: pivot agg by col values (values)
          ASQL: pivot agg by col  (dynamic pivot)

        UNPIVOT:
          SQL:  UNPIVOT (value_col FOR name_col IN (col1, col2, ...))
          ASQL: unpivot col1, col2, ... into name_col, value_col
        """
        # Try standard SQL PIVOT first (starts with PIVOT keyword followed by paren)
        if self._match(TokenType.PIVOT):
            if self._curr and self._curr.token_type == TokenType.L_PAREN:
                # Standard SQL PIVOT syntax
                self._retreat(self._index - 1)  # Go back to before PIVOT
                return super()._parse_pivot()

            # ASQL syntax: pivot agg by col [values (...)]
            return self._parse_asql_pivot_syntax()

        elif self._match(TokenType.UNPIVOT):
            if self._curr and self._curr.token_type == TokenType.L_PAREN:
                # Standard SQL UNPIVOT syntax
                self._retreat(self._index - 1)  # Go back to before UNPIVOT
                return super()._parse_pivot()

            # ASQL syntax: unpivot col1, col2, ... into name_col, value_col
            return self._parse_asql_unpivot_syntax()

        elif self._match_text_seq("PIVOT"):
            return self._parse_asql_pivot_syntax()
        elif self._match_text_seq("UNPIVOT"):
            return self._parse_asql_unpivot_syntax()
        else:
            return None

    def _parse_asql_pivot_syntax(self) -> exp.Pivot | None:
        """Parse ASQL's simplified pivot syntax: pivot agg by col [values (...)]"""
        index = self._index

        # Parse aggregate expression (e.g., sum(amount) or just amount)
        agg_expr = self._parse_unary()

        # Expect 'by' keyword
        if not self._match_text_seq("BY"):
            # Not ASQL syntax, retreat and try standard parsing
            self._retreat(index)
            return None

        # Parse the pivot column
        pivot_col = self._parse_column()
        if pivot_col is None:
            self.raise_error("Expected a column after 'by'")
            return None

        # Check for optional 'values' clause
        values: list[exp.Expr] = []
        if self._match_text_seq("VALUES"):
            self._match_l_paren()
            values = self._parse_csv(self._parse_primary)
            self._match_r_paren()

        # Ensure agg_expr is wrapped in an aggregate function if it's just a column
        if isinstance(agg_expr, exp.Column):
            agg_expr = exp.Sum(this=agg_expr)

        # Build the Pivot expression matching SQLGlot's structure
        fields: list[exp.Expr] = (
            [exp.In(this=pivot_col, expressions=values)] if values else [pivot_col]
        )
        return self.expression(
            exp.Pivot(expressions=[agg_expr], fields=fields, unpivot=False)
        )

    def _parse_asql_unpivot_syntax(self) -> exp.Pivot | None:
        """Parse ASQL's simplified unpivot syntax: unpivot col1, col2, ... into name, value"""
        # Parse column list until we hit 'into'
        columns: list[exp.Expr] = []
        while True:
            col = self._parse_column()
            if col:
                columns.append(col)
            if not self._match(TokenType.COMMA):
                break

        # Expect 'into' keyword
        if not self._match_text_seq("INTO"):
            self.raise_error("Expected 'into' after unpivot columns")

        # Parse name and value column identifiers
        name_col = self._parse_id_var()
        if not self._match(TokenType.COMMA):
            self.raise_error("Expected comma between name and value columns")
        value_col = self._parse_id_var()

        # Build SQLGlot UNPIVOT expression
        # Standard SQL: UNPIVOT (value FOR name IN (col1, col2, ...))
        return self.expression(
            exp.Pivot(
                expressions=[value_col],  # Value column
                fields=[
                    exp.In(this=name_col, expressions=columns)
                ],  # FOR name IN (columns)
                unpivot=True,
            )
        )

    def _parse_bucket(self) -> exp.Expr:
        """Parse bucket(...) and return a CASE expression.

        Implemented via FUNCTION_PARSERS to avoid sqlglot validate_expression() arg-count checks,
        since BUCKET can accept keyword args (start/end/width) and returns an exp.Case.
        """
        args = self._parse_function_args(alias=True)
        return build_bucket(args)

    def _parse_key(self) -> exp.Expr:
        """Parse key(col1, col2, ...) into a stable surrogate key hash.

        Implemented via FUNCTION_PARSERS because key() is variadic but compiles to MD5(CONCAT(...)),
        which would otherwise fail sqlglot's validate_expression() (arg count mismatch).
        """
        args = self._parse_function_args(alias=True)
        if not args:
            return exp.Anonymous(this="key", expressions=args)

        coalesced: list[exp.Expr] = []
        for arg in args:
            cast = exp.Cast(
                this=arg, to=exp.DataType.build("VARCHAR", dialect=self.dialect)
            )
            coalesced.append(
                exp.Coalesce(this=cast, expressions=[exp.Literal.string("")])
            )

        concat_parts: list[exp.Expr] = []
        for i, arg in enumerate(coalesced):
            if i:
                concat_parts.append(exp.Literal.string("||"))
            concat_parts.append(arg)

        concat = exp.Concat(expressions=concat_parts)
        return exp.MD5(this=concat)

    def _parse_slugify(self) -> exp.Expr:
        """Parse slugify(expr) into TRIM(REGEXP_REPLACE(LOWER(expr), ...))."""
        args = self._parse_function_args(alias=True)
        if len(args) != 1:
            return exp.Anonymous(this="slugify", expressions=args)

        lowered = exp.Lower(this=args[0])
        replaced = exp.RegexpReplace(
            this=lowered,
            expression=exp.Literal.string("[^a-z0-9]+"),
            replacement=exp.Literal.string("-"),
        )
        return remember_call(
            "slugify",
            args,
            exp.Trim(
                this=replaced, expression=exp.Literal.string("-"), position="BOTH"
            ),
        )

    def _parse_field(
        self,
        any_token: bool = False,
        tokens: t.Collection[TokenType] | None = None,
        anonymous_func: bool = False,
    ) -> exp.Expr | None:
        """Override to handle ASQL-specific expression starters.

        Handles:
        - `when` conditional expressions
        - `#` count shorthand
        - FIRST(<expr> ORDER BY ...)
        """
        # Check for ASQL's `when` conditional expression
        # Only intercept if we're NOT inside a CASE expression
        # (i.e., previous token was not CASE)
        if (
            self._curr
            and self._curr.token_type == TokenType.WHEN
            and self._prev.token_type != TokenType.CASE
        ):
            self._advance()  # consume WHEN
            return self._parse_when()

        # FIRST(<expr> ORDER BY ...) should compile to FIRST_VALUE(...) OVER (ORDER BY ...)
        if self._curr and self._curr.token_type == TokenType.FIRST:
            index = self._index
            self._advance()  # consume FIRST
            if self._match(TokenType.L_PAREN):
                return self._parse_first_ordered()
            self._retreat(index)

        # Fall back to default field parsing
        return super()._parse_field(
            any_token=any_token, tokens=tokens, anonymous_func=anonymous_func
        )

    def _parse_first_ordered(self) -> exp.Expr:
        """Parse FIRST(<value> ORDER BY <order>) into FIRST_VALUE(<value>) OVER (ORDER BY ...)."""
        value = self._parse_expression()
        if not value:
            self.raise_error("Expected expression after FIRST(")

        if not self._match(TokenType.ORDER_BY):
            self.raise_error("Expected ORDER BY inside FIRST(...)")

        order_expressions = self._parse_csv(self._parse_ordered)
        if not self._match(TokenType.R_PAREN):
            self.raise_error("Expected ) to close FIRST(...)")

        order = exp.Order(expressions=order_expressions)
        return exp.Window(this=exp.FirstValue(this=value), order=order)

    def _parse_count_shorthand_from_primary(self) -> exp.Expr:
        """Parse ASQL # count shorthand (called after # is consumed).

        Syntax:
            # → COUNT(*)
            #* or # * → COUNT(*)
            #col or # col → COUNT(col), or COUNT(DISTINCT key) when col names an
                entity table (resolved in transforms/count_entity.py)
            #(col) → COUNT(col)
            #(distinct col) → COUNT(DISTINCT col)
            ##col or ## col → COUNT(DISTINCT col)
        """
        # ## → COUNT(DISTINCT col) - double hash means distinct
        if self._match(TokenType.HASH):
            # We now have ## - parse the column for distinct count
            if self._advance_past_count_star():
                return exp.Count(this=exp.Distinct(expressions=[exp.Star()]))
            if self._curr and self._curr.token_type == TokenType.VAR:
                col_name = self._curr.text
                self._advance()
                return exp.Count(
                    this=exp.Distinct(
                        expressions=[exp.Column(this=exp.to_identifier(col_name))]
                    )
                )
            # ## with nothing after → COUNT(DISTINCT *)
            return exp.Count(this=exp.Distinct(expressions=[exp.Star()]))

        # #* → COUNT(*)
        if self._advance_past_count_star():
            return exp.Count(this=exp.Star())

        # #(col) → COUNT(col), #(distinct col) → COUNT(DISTINCT col)
        if self._match(TokenType.L_PAREN):
            # Check for DISTINCT
            if self._match(TokenType.DISTINCT):
                col = self._parse_expression()
                self._match(TokenType.R_PAREN)
                return exp.Count(this=exp.Distinct(expressions=[col] if col else []))
            else:
                col = self._parse_expression()
                self._match(TokenType.R_PAREN)
                return exp.Count(this=col)

        # #col or # col → COUNT(col) - single hash followed by identifier
        if self._curr and self._curr.token_type == TokenType.VAR:
            # Check if this is a SQL keyword that should trigger standalone # → COUNT(*)
            sql_keywords = {
                "as",
                "from",
                "where",
                "group",
                "by",
                "order",
                "limit",
                "having",
                "select",
                "join",
                "on",
                "and",
                "or",
                "not",
                "in",
                "is",
                "null",
                "true",
                "false",
                "union",
                "except",
                "intersect",
                "with",
                "stash",
            }
            if self._curr.text.lower() not in sql_keywords:
                col_name = self._curr.text
                self._advance()
                count = exp.Count(this=exp.Column(this=exp.to_identifier(col_name)))
                count.set(ENTITY_CANDIDATE, True)
                return count

        # Standalone # → COUNT(*)
        return exp.Count(this=exp.Star())

    def _parse_last_ordered(self) -> exp.Expr:
        """Parse last(value ORDER BY x) into FIRST_VALUE(value) OVER (ORDER BY x DESC/ASC flipped)."""
        value = self._parse_expression()
        if not value:
            self.raise_error("Expected expression after last(")

        if not self._match(TokenType.ORDER_BY):
            # Fallback to a normal function call if no ORDER BY form is used
            args = self._parse_csv(self._parse_expression)
            return exp.Anonymous(this="last", expressions=[value, *args])

        order_expressions = self._parse_csv(self._parse_ordered)
        if not self._curr or self._curr.token_type != TokenType.R_PAREN:
            self.raise_error("Expected ) to close last(...)")

        flipped: list[exp.Expr] = []
        for ordered in order_expressions:
            # Flip the sort direction: ASC <-> DESC
            ordered.set("desc", not bool(ordered.args.get("desc")))
            flipped.append(ordered)

        order = exp.Order(expressions=flipped)
        return exp.Window(this=exp.FirstValue(this=value), order=order)

    def _parse_arg_max_min(self, is_max: bool) -> exp.Expr:
        """Parse arg_max(value, key) / arg_min(value, key) into FIRST_VALUE(value) OVER (ORDER BY key ...)."""
        args = self._parse_function_args(alias=True)
        value = seq_get(args, 0)
        key = seq_get(args, 1)
        if not value or not key:
            return exp.Anonymous(
                this="arg_max" if is_max else "arg_min", expressions=args
            )

        ordered = exp.Ordered(this=key, desc=is_max)
        order = exp.Order(expressions=[ordered])
        return exp.Window(this=exp.FirstValue(this=value), order=order)

    def _parse_when(self) -> exp.Expr:
        """Parse ASQL `when` conditional expression into SQL CASE.

        Syntax (comma-separated branches):
            when <base_expr>
              is <value> then <result>,
              is <value2> then <result2>,
              otherwise <default>

            when <condition> then <result>, <condition2> then <result2>, otherwise <default>

        Examples:
            when status is "active" then 1, otherwise 0
            when age < 18 then "Minor", otherwise "Adult"
            when status is "active" then 1, is "pending" then 0, otherwise -1
        """
        ifs: list[exp.If] = []
        default: exp.Expr | None = None
        base_expr: exp.Expr | None = None

        # Parse first branch to detect simple vs searched case
        # Simple case pattern: `when <column> is/</>/in <value> then <result>`
        # Searched case pattern: `when <full_condition> then <result>`

        # We need to parse carefully to distinguish:
        # - `when status is "active" then 1` (simple case, base_expr = status)
        # - `when age < 18 then "Minor"` (could be simple OR searched)
        # - `when age < 18 and x then "y"` (searched case)

        # Strategy: Parse a column/id, then check what follows
        condition: exp.Expr | None = None
        if self._match_set(self.ID_VAR_TOKENS):
            # Got a potential base expression (identifier)
            assert self._prev is not None  # _match_set advanced past the matched token
            maybe_base = exp.column(self._prev.text)

            if self._match(TokenType.IS):
                # `is` or `is not` pattern - definitely simple case
                base_expr = maybe_base
                if self._match(TokenType.NOT):
                    value = self._parse_unary()
                    condition = exp.NEQ(this=base_expr.copy(), expression=value)
                else:
                    value = self._parse_unary()
                    condition = exp.EQ(this=base_expr.copy(), expression=value)
                self._match(TokenType.THEN)
                result = self._parse_when_result()
                ifs.append(exp.If(this=condition, true=result))
            elif self._match(TokenType.IN):
                # `in (values)` pattern - simple case
                base_expr = maybe_base
                values = self._parse_wrapped_csv(self._parse_unary)
                condition = exp.In(this=base_expr.copy(), expressions=values)
                self._match(TokenType.THEN)
                result = self._parse_when_result()
                ifs.append(exp.If(this=condition, true=result))
            elif self._match_set(
                {
                    TokenType.LT,
                    TokenType.GT,
                    TokenType.LTE,
                    TokenType.GTE,
                    TokenType.EQ,
                    TokenType.NEQ,
                }
            ):
                # Comparison operator - could be simple case OR searched case with AND/OR
                assert (
                    self._prev is not None
                )  # _match_set advanced past the matched token
                op_token = self._prev.token_type
                value = self._parse_unary()
                condition = self._build_comparison(maybe_base.copy(), op_token, value)

                # Check if there's AND/OR after - if so, this is searched case
                if self._match(TokenType.AND):
                    # Searched case with compound condition
                    right = self._parse_conjunction()
                    condition = exp.And(this=condition, expression=right)
                    base_expr = None
                elif self._match(TokenType.OR):
                    right = self._parse_disjunction()
                    condition = exp.Or(this=condition, expression=right)
                    base_expr = None
                else:
                    # Simple case with comparison
                    base_expr = maybe_base

                self._match(TokenType.THEN)
                result = self._parse_when_result()
                ifs.append(exp.If(this=condition, true=result))
            elif self._match(TokenType.THEN):
                # Just `<column> then <result>` - column itself is the condition (truthy check)
                condition = maybe_base
                result = self._parse_when_result()
                ifs.append(exp.If(this=condition, true=result))
                base_expr = None  # Searched case
            else:
                # More complex: retreat and parse full condition
                self._retreat(self._index - 1)
                condition = self._parse_conjunction()
                self._match(TokenType.THEN)
                result = self._parse_when_result()
                ifs.append(exp.If(this=condition, true=result))
                base_expr = None  # Searched case
        else:
            # Not an identifier - parse as full condition (searched case)
            condition = self._parse_conjunction()
            self._match(TokenType.THEN)
            result = self._parse_when_result()
            ifs.append(exp.If(this=condition, true=result))
            base_expr = None

        # Parse remaining branches (comma-separated)
        while self._match(TokenType.COMMA):
            # Check for otherwise/else (ELSE token - tokenizer maps otherwise→ELSE)
            if self._match(TokenType.ELSE):
                default = self._parse_when_result()
                break

            # Parse next branch
            branch_if = self._parse_when_branch(base_expr)
            if branch_if:
                ifs.append(branch_if)

        # Check for otherwise/else without preceding comma (optional trailing comma)
        if default is None and self._match(TokenType.ELSE):
            default = self._parse_when_result()

        return exp.Case(ifs=ifs, default=default)

    def _parse_when_result(self) -> exp.Expr | None:
        """Parse the result part of a when branch, stopping at comma/else/otherwise."""
        # Parse expression but stop at COMMA or ELSE (otherwise is tokenized as ELSE)
        return self._parse_unary()

    def _parse_when_branch(self, base_expr: exp.Expr | None) -> exp.If | None:
        """Parse a single when branch: <condition> then <result>."""
        condition: exp.Expr | None = None

        if base_expr is not None:
            # Simple case: branch starts with operator or value
            if self._match(TokenType.IS):
                if self._match(TokenType.NOT):
                    value = self._parse_unary()
                    condition = exp.NEQ(this=base_expr.copy(), expression=value)
                else:
                    value = self._parse_unary()
                    condition = exp.EQ(this=base_expr.copy(), expression=value)
            elif self._match(TokenType.IN):
                values = self._parse_wrapped_csv(self._parse_unary)
                condition = exp.In(this=base_expr.copy(), expressions=values)
            elif self._match_set(
                {
                    TokenType.LT,
                    TokenType.GT,
                    TokenType.LTE,
                    TokenType.GTE,
                    TokenType.EQ,
                    TokenType.NEQ,
                }
            ):
                assert (
                    self._prev is not None
                )  # _match_set advanced past the matched token
                op_token = self._prev.token_type
                value = self._parse_unary()
                condition = self._build_comparison(base_expr.copy(), op_token, value)
            else:
                # Implied equality: just a value
                value = self._parse_unary()
                if value:
                    condition = exp.EQ(this=base_expr.copy(), expression=value)
        else:
            # Searched case: full condition
            condition = self._parse_conjunction()

        if condition is None:
            return None

        self._match(TokenType.THEN)
        result = self._parse_when_result()
        return exp.If(this=condition, true=result)

    # Comparison operator token -> expression class mapping
    COMPARISON_OPS = {
        TokenType.GT: exp.GT,
        TokenType.GTE: exp.GTE,
        TokenType.LT: exp.LT,
        TokenType.LTE: exp.LTE,
        TokenType.EQ: exp.EQ,
        TokenType.NEQ: exp.NEQ,
        TokenType.NULLSAFE_EQ: exp.NullSafeEQ,
    }

    def _build_comparison(
        self, left: exp.Expr, op_token: TokenType, right: exp.Expr | None
    ) -> exp.Expr:
        """Build a comparison expression from operator token."""
        expr_class = self.COMPARISON_OPS.get(op_token, exp.EQ)
        return expr_class(this=left, expression=right)

    def _parse_bracket(self, this: exp.Expr | None = None) -> exp.Expr | None:
        """Override to handle:
        1. Python-style list comprehensions: [expr for var in arr]
        2. ASQL slice syntax: expr[start:end]

        List comprehensions are converted to ARRAY(SELECT expr FROM UNNEST(arr) AS var).

        ASQL supports python-style slices for strings:
          - expr[start:end] → SUBSTRING(expr, start, end - start + 1)
          - expr[start:]    → SUBSTRING(expr, start)
          - expr[:end]      → LEFT(expr, end)
          - expr[-n:]       → RIGHT(expr, n)

        SQLGlot natively parses slices as exp.Slice inside exp.Bracket; we translate that AST
        into portable string functions here (parser-level, not regex).
        """
        # Check for list comprehension: [expr for var in arr [if condition]]
        # Only when not indexing (this is None) and we see L_BRACKET
        if this is None and self._match(TokenType.L_BRACKET, advance=False):
            # Check if this is a list comprehension by looking for 'for ... in' pattern
            if self._is_list_comprehension():
                return self._parse_list_comprehension()

        parsed = super()._parse_bracket(this)
        if not isinstance(parsed, exp.Bracket):
            return parsed

        # Only handle single slice, e.g. email[1:5]
        if len(parsed.expressions) != 1:
            return parsed

        slice_expr = parsed.expressions[0]
        if not isinstance(slice_expr, exp.Slice):
            return parsed

        base = parsed.this
        start = slice_expr.this
        end = slice_expr.expression

        if start is None and end is None:
            return base

        if start is None and end is not None:
            return exp.Left(this=base, expression=end)

        if start is not None and end is None:
            start_num: int | None = None
            if isinstance(start, exp.Literal) and start.is_number:
                try:
                    start_num = int(start.to_py())
                except (ValueError, TypeError):
                    start_num = None
            elif (
                isinstance(start, exp.Neg)
                and isinstance(start.this, exp.Literal)
                and start.this.is_number
            ):
                try:
                    start_num = -int(start.this.to_py())
                except (ValueError, TypeError):
                    start_num = None

            if start_num is not None and start_num < 0:
                return exp.Right(
                    this=base, expression=exp.Literal.number(str(-start_num))
                )
            return exp.Substring(this=base, start=start)

        # start and end are present
        if start is not None and end is not None:
            if (
                isinstance(start, exp.Literal)
                and start.is_number
                and isinstance(end, exp.Literal)
                and end.is_number
            ):
                try:
                    start_num = int(start.to_py())
                    end_num = int(end.to_py())
                    length_num = end_num - start_num + 1
                    return exp.Substring(
                        this=base,
                        start=start,
                        length=exp.Literal.number(str(length_num)),
                    )
                except (ValueError, TypeError):
                    pass

            length = exp.Add(
                this=exp.Sub(this=end.copy(), expression=start.copy()),
                expression=exp.Literal.number(1),
            )
            return exp.Substring(this=base, start=start, length=length)

        return parsed

    def _is_list_comprehension(self) -> bool:
        """Check if we're at the start of a list comprehension.

        Looks ahead for pattern: [expr for var in arr [if condition]]
        """
        if not self._match(TokenType.L_BRACKET, advance=False):
            return False

        # Scan ahead to determine if this is list comprehension syntax
        bracket_depth = 0
        found_for = False
        found_in = False

        i = self._index
        while i < len(self._tokens):
            tok = self._tokens[i]

            if tok.token_type == TokenType.L_BRACKET:
                bracket_depth += 1
            elif tok.token_type == TokenType.R_BRACKET:
                bracket_depth -= 1
                if bracket_depth == 0:
                    break
            elif bracket_depth == 1:  # Only at top level within the brackets
                if tok.token_type == TokenType.FOR or (
                    tok.token_type == TokenType.VAR and tok.text.upper() == "FOR"
                ):
                    found_for = True
                elif found_for and (
                    tok.token_type == TokenType.IN
                    or (tok.token_type == TokenType.VAR and tok.text.upper() == "IN")
                ):
                    found_in = True
                    break

            i += 1

        return found_for and found_in

    def _parse_list_comprehension(self) -> exp.Expr:
        """Parse Python-style list comprehension: [expr for var in arr [if condition]]

        For DuckDB: keeps as exp.Array(Comprehension) for native [x FOR x IN arr] syntax
        For others: converts to ARRAY(SELECT expr FROM UNNEST(arr) AS var [WHERE condition])

        Uses SQLGlot's built-in _parse_comprehension which returns exp.Comprehension.
        """
        self._advance()  # consume [

        # SQLGlot's _parse_assignment() handles "expr FOR var IN arr [IF cond]"
        # and returns exp.Comprehension
        parsed = self._parse_assignment()

        # Expect ]
        if not self._match(TokenType.R_BRACKET):
            self.raise_error("Expected ']' at end of list comprehension")

        # Keep as Comprehension AST - dialect-specific conversion happens in compile()
        # DuckDB: native [x FOR x IN arr] syntax
        # Others: ARRAY(SELECT ... FROM UNNEST(...))
        if isinstance(parsed, exp.Comprehension):
            return exp.Array(expressions=[parsed])

        # Not a comprehension - return as array literal
        return exp.Array(expressions=[parsed] if parsed else [])

    def _comprehension_to_array_select(self, comp: exp.Comprehension) -> exp.Expr:
        """Convert exp.Comprehension to ARRAY(SELECT expr FROM UNNEST(arr) AS var [WHERE cond]).

        This generates portable SQL that works on Postgres, BigQuery, etc.
        (DuckDB native syntax is handled by post-processing in list_comprehension.py)
        """
        # Extract parts from Comprehension
        select_expr = comp.this  # The expression to evaluate
        var_expr = comp.expression  # The loop variable
        iterator = comp.args.get("iterator")  # The array to iterate
        condition = comp.args.get("condition")  # Optional IF condition

        # Get variable name
        var_name = var_expr.name if hasattr(var_expr, "name") else str(var_expr)

        # Build UNNEST with alias
        unnest = exp.Unnest(
            expressions=[iterator],
            alias=exp.TableAlias(this=exp.to_identifier(var_name)),
        )

        # Build SELECT
        select = exp.Select(
            expressions=[select_expr],
            from_=exp.From(this=unnest),
        )

        if condition:
            select.set("where", exp.Where(this=condition))

        return exp.Array(expressions=[select])

    def _match_transform(self) -> str | None:
        """Match a transform keyword and return its name.

        Uses efficient token matching:
        1. Check multi-word keywords (GROUP BY, ORDER BY) as single tokens
        2. Use _match_texts for single-word keywords (PRQL pattern)
        """
        # Tokenized-as-keyword transforms (PRQL doesn't need this because its tokenizer leaves these as VARs).
        if self._curr and self._curr.token_type in self._TOKEN_TRANSFORMS:
            # Special handling for PLACEHOLDER - only treat as ASQL_FULL_JOIN if text is ?&?
            if self._curr.token_type == TokenType.PLACEHOLDER:
                if self._curr.text == "?&?":
                    self._advance()
                    return "ASQL_FULL_JOIN"
                # Other placeholders are not transforms
                return None

            # Special handling for STAR - only treat as CROSS JOIN if followed by table name
            if self._curr.token_type == TokenType.STAR:
                # Check if next token is a table name (VAR) - this indicates CROSS JOIN
                next_tok = self._next
                if next_tok and next_tok.token_type == TokenType.VAR:
                    self._advance()
                    return "ASQL_CROSS_JOIN"
                # Otherwise it's SELECT * or multiplication
                return None

            transform = self._TOKEN_TRANSFORMS[self._curr.token_type]
            self._advance()
            return transform

        # Check for multi-word keywords (tokenized as single tokens)
        if self._match(TokenType.GROUP_BY):
            return "GROUP BY"
        if self._match(TokenType.ORDER_BY):
            return "ORDER BY"

        # Use efficient set-based matching for single-word transforms (PRQL pattern)
        if self._match_texts(self._SINGLE_WORD_TRANSFORMS):
            assert (
                self._prev is not None
            )  # _match_texts advanced past the matched token
            return self._prev.text.upper()

        return None

    def _parse_statement(self) -> exp.Expr | None:
        statement = self._parse_statement_unvalidated()
        if statement is not None:
            self._reject_aggregates_in_group_by(statement)
        return statement

    def _reject_aggregates_in_group_by(self, statement: exp.Expr) -> None:
        """Reject aggregate functions inside GROUP BY expressions.

        No SQL dialect allows aggregates in GROUP BY, so this only fires on the
        SELECT-first misparse of an ASQL aggregate block: `select * from orders
        group by region ( sum(amount) as rev )` parses as the function call
        REGION(SUM(amount) AS rev) and would silently emit wrong SQL.
        """
        for group in statement.find_all(exp.Group):
            for group_expr in group.expressions:
                # Prune at subquery roots: a scalar subquery in GROUP BY may
                # legitimately contain an aggregate — only the group key's own
                # expression is checked.
                key_expr: exp.Expr = group_expr
                for node in key_expr.walk(prune=lambda n: isinstance(n, exp.Select)):
                    if isinstance(node, exp.AggFunc):
                        self.raise_error(
                            "aggregates are not allowed inside GROUP BY — this "
                            "looks like an ASQL aggregate block after a SELECT "
                            "query. Either start the query with `from` to use "
                            "pipe syntax (from orders group by region ( "
                            "sum(amount) as rev )), or write standard SQL with "
                            "aggregates in the SELECT list and plain keys in "
                            "GROUP BY"
                        )

    def _parse_statement_unvalidated(self) -> exp.Expr | None:
        """Parse a single statement.

        PRQL-style: try parsing an expression first, otherwise parse ASQL FROM-first pipelines.
        This is required because SQLGlot's base statement parser starts from SELECT, and its
        FROM-first fallback doesn't understand ASQL's transform chaining order.
        """
        index = self._index

        # SELECT-first queries with trailing ASQL transforms (e.g. "... GROUP BY ... stash as x")
        # aren't valid SQL, so parsing as a normal SQL expression will fail. This can occur today
        # because the preparser may reorder FROM-first pipelines into SELECT-first queries.
        if self._curr and self._curr.token_type == TokenType.SELECT:
            stash_index = self._find_trailing_stash_index()
            if stash_index is not None:
                stash_token = self._tokens[stash_index]
                start = self._curr.start
                end = stash_token.start
                fragment = self.sql[start:end].strip().rstrip(",")
                if fragment:
                    parsed = sqlglot.parse_one(fragment, dialect="asql")
                    if isinstance(parsed, exp.Query):
                        self._consume_tokens_until_index(stash_index)
                        return self._parse_asql_trailing_transforms(parsed)

        # FROM-first ASQL pipelines should be parsed by our pipeline parser first.
        # If we let the base parser handle `FROM ... ORDER BY ...` it can "successfully" parse a
        # partial statement and then choke on the next transform keyword (like SELECT).
        if self._curr and self._curr.token_type == TokenType.FROM:
            query = self._parse_query()
            if query:
                return query
            self._retreat(index)

        # Try parsing a normal SQL statement first, but don't consume on failure.
        # NOTE: `_parse_expression` does not parse full SELECT statements, so using it here
        # breaks internal helper parses like `sqlglot.parse_one("SELECT ...")` within ASQL's
        # pipeline helpers.
        statement = self._try_parse(lambda: Parser._parse_statement(self))
        if statement:
            return statement

        # Ensure we're fully back at the starting position before trying ASQL FROM-first.
        self._retreat(index)

        query = self._parse_query()
        if query:
            return query

        # Fall back to standard SQL statement parsing (SELECT/INSERT/...) from the original position.
        self._retreat(index)
        return super()._parse_statement()

    def _find_trailing_stash_index(self) -> int | None:
        """Find a top-level trailing-transform token index for SELECT-first queries.

        These keywords can appear after SELECT-first queries (converted from FROM-first
        by the preparser) and need special handling.
        """
        depth = 0
        i = self._index
        # Keywords that can appear as trailing transforms after SELECT-first queries
        trailing_keywords = {"STASH", "COHORT", "EXCEPT", "RENAME", "REPLACE"}
        seen_group_by = False
        seen_set_op = False

        while i < len(self._tokens):
            tok = self._tokens[i]

            if tok.token_type in (
                TokenType.L_PAREN,
                TokenType.L_BRACKET,
                TokenType.L_BRACE,
            ):
                depth += 1
            elif tok.token_type in (
                TokenType.R_PAREN,
                TokenType.R_BRACKET,
                TokenType.R_BRACE,
            ):
                depth = max(depth - 1, 0)

            if depth == 0:
                if tok.token_type == TokenType.GROUP_BY:
                    seen_group_by = True
                elif tok.token_type in (
                    TokenType.UNION,
                    TokenType.INTERSECT,
                ):
                    # Once a set operation appears, GROUP BY / WHERE belong to a
                    # branch Select, not the outer node — the trailing-WHERE
                    # CTE-wrap (which reads `group` off the outer query) can't
                    # apply. Disable it for the rest of the scan.
                    seen_group_by = False
                    seen_set_op = True
                elif tok.token_type == TokenType.SELECT:
                    # A new SELECT starts a fresh branch whose WHERE is ordinary
                    # SQL again.
                    seen_group_by = False
                elif (
                    tok.token_type == TokenType.WHERE
                    and seen_group_by
                    and not seen_set_op
                ):
                    # WHERE after GROUP BY is invalid standard SQL, so the only
                    # sensible reading is the pipeline post-aggregation filter.
                    return i

            if (
                depth == 0
                and tok.token_type != TokenType.IDENTIFIER
                and tok.text.upper() in trailing_keywords
            ):
                # Avoid treating set-operation EXCEPT as a trailing transform:
                #   SELECT ... EXCEPT SELECT ...
                if tok.token_type == TokenType.EXCEPT:
                    next_tok = (
                        self._tokens[i + 1] if i + 1 < len(self._tokens) else None
                    )
                    if next_tok and next_tok.token_type == TokenType.SELECT:
                        i += 1
                        continue
                return i

            i += 1

        return None

    def _parse_asql_trailing_transforms(self, query: exp.Query) -> exp.Query:
        """Parse ASQL pipeline transforms that appear after an already-parsed query."""
        while True:
            self._match(TokenType.PIPE_GT)

            transform_name = self._match_transform()
            if not transform_name:
                break

            result = self._apply_pipeline_transform(query, transform_name)
            if result is None:
                break
            query = result

        return query

    def _apply_pipeline_transform(
        self, query: exp.Query, transform_name: str
    ) -> exp.Query | None:
        """Run one pipeline step; None means fall-through (e.g. rank() without BY).

        An aggregate block fixes the grouped SELECT's projection, so steps that read
        its output as a table (WHERE, SELECT, EXTEND, joins, windows, ...) first close
        it into a CTE. Steps that act on the grouped SELECT itself (ORDER BY, LIMIT,
        HAVING, ...) stay flat. After a bare `group by k` the next `select` is that
        grouped SELECT's projection; any other reading step has nothing to read yet
        and raises.
        """
        if query.args.get("group") and transform_name in self._STEPS_ON_GROUPED_OUTPUT:
            stage = query.meta.get(_GROUP_STAGE)
            if stage == "bare" and transform_name == "SELECT":
                query.meta[_GROUP_STAGE] = "selected"
            elif stage == "bare":
                raise ASQLCompilationError(
                    f"`{transform_name.lower()}` after a bare `group by` has nothing "
                    "to read: add an aggregate block or a select before it"
                )
            else:
                query = self._build_pipe_cte(query, [exp.Star()])
        elif transform_name == "GROUP BY" and [type(e) for e in query.expressions] != [
            exp.Star
        ]:
            # An earlier select is its own stage; group over its output.
            query = self._build_pipe_cte(query, [exp.Star()])
        return self.TRANSFORM_PARSERS[transform_name](self, query)

    def _parse_wrapped_select(self, table: bool = False) -> exp.Expr | None:
        if self._curr and self._curr.token_type == TokenType.FROM:
            return self._parse_query(nested=True)
        return super()._parse_wrapped_select(table=table)

    def _parse_select_query(
        self,
        nested: bool = False,
        table: bool = False,
        parse_subquery_alias: bool = True,
        parse_set_operation: bool = True,
    ) -> exp.Expr | None:
        # sqlglot reads a parenthesized `FROM` as DuckDB's `FROM x SELECT ...`,
        # which rejects ASQL steps (`where`, `order by`, ...) before `select`.
        if (
            self._prev
            and self._prev.token_type == TokenType.L_PAREN
            and self._curr
            and self._curr.token_type == TokenType.FROM
        ):
            return self._parse_query(
                nested=True, parse_set_operation=parse_set_operation
            )
        return super()._parse_select_query(
            nested=nested,
            table=table,
            parse_subquery_alias=parse_subquery_alias,
            parse_set_operation=parse_set_operation,
        )

    def _parse_query(
        self,
        nested: bool = False,
        parse_set_operation: bool = True,
    ) -> exp.Query | None:
        """Parse ASQL query starting with FROM.

        Pattern from PRQL:
        1. Parse FROM clause
        2. Build SELECT * FROM table
        3. Apply transforms in sequence
        """
        start_index = self._index

        # Check for WITH first (CTEs from stash as)
        with_ = self._parse_with()

        # Parse FROM clause
        from_ = self._parse_from()
        if not from_:
            # Not a FROM-first ASQL query; let the base parser handle it via _parse_statement fallback.
            self._retreat(start_index)
            return None

        # Build initial SELECT * FROM table
        query: exp.Query = _select_all(from_.this)

        # Transfer comments from FROM clause to SELECT (preserves leading comments)
        if from_.comments:
            query.comments = from_.comments

        if with_:
            query.set("with_", with_)

        # Apply transforms in sequence
        while True:
            # Skip pipe operators
            self._match(TokenType.PIPE_GT)

            # Check for transform keywords
            transform_name = self._match_transform()
            if not transform_name:
                break

            result = self._apply_pipeline_transform(query, transform_name)
            if result is None:
                return None
            query = result

        # `stash as x` followed by a fresh `from` (spec §11.2) starts a new
        # pipeline that can read x: carry the CTEs over to that pipeline.
        if (
            query.meta.get(_STASHED)
            and self._curr
            and self._curr.token_type == TokenType.FROM
            and self._passthrough_cte_name(query) is not None
        ):
            ctes = list(query.args["with_"].expressions)
            next_query = self._parse_query(
                nested=nested, parse_set_operation=parse_set_operation
            )
            if next_query is None:
                self.raise_error("Expected a pipeline after `stash as`")
                return None
            next_with = next_query.args.get("with_")
            if next_with:
                ctes.extend(next_with.expressions)
            next_query.set("with_", exp.With(expressions=ctes))
            return next_query

        # Handle set operations (UNION, INTERSECT, EXCEPT)
        if parse_set_operation:
            query = t.cast(exp.Query, self._parse_set_operations(query))

        return query

    def _parse_asql_where(self, query: exp.Query) -> exp.Query:
        """Parse WHERE clause."""
        condition = self._parse_asql_expression_until_transform_boundary()
        if not condition:
            self.raise_error("Missing WHERE condition")
        return query.where(condition, copy=False)

    def _parse_asql_order_by(self, query: exp.Query) -> exp.Query:
        """Parse ORDER BY with ASQL's -column DESC shorthand.

        Note: ORDER BY is tokenized as a single token, so BY is already consumed.
        """
        expressions = self._parse_csv(self._parse_asql_ordered)
        order = self.expression(exp.Order(expressions=expressions))
        return query.order_by(order, copy=False)

    def _parse_ordered(
        self, parse_method: t.Callable[..., t.Any] | None = None
    ) -> exp.Ordered | None:
        """Override to handle -column for DESC (like PRQL).

        Examples:
            order by -created_at  → ORDER BY created_at DESC
            order by name         → ORDER BY name ASC (default)
        """
        desc = self._match(TokenType.DASH)

        # Call parent implementation
        ordered = super()._parse_ordered(parse_method=parse_method)

        if ordered and desc:
            ordered.set("desc", True)
            ordered.set("nulls_first", False)

        return ordered

    def _parse_asql_ordered(self) -> exp.Ordered | None:
        """Parse ordered expression with -column for DESC (for FROM-first syntax)."""
        return self._parse_ordered()

    def _parse_asql_select(self, query: exp.Query) -> exp.Query:
        """Parse SELECT clause."""
        # Support `select distinct ...` inside ASQL SELECT stage
        if self._match(TokenType.DISTINCT):
            query = self._parse_asql_distinct(query)
        expressions = self._parse_asql_select_expressions_until_transform_boundary()
        if not expressions:
            return query

        self._apply_star_column_override(
            expressions, self._pipe_cte_output_columns(query)
        )

        return query.select(*expressions, append=False, copy=False)

    @staticmethod
    def _pipe_cte_output_columns(query: exp.Query) -> set[str] | None:
        """Output column names when ``query`` selects from a pipeline CTE whose
        every projection is an alias or plain column; None when any is unknown
        (unaliased aggregates are named later, ``tbl.*``, set-operation bodies)."""
        from_ = query.args.get("from_")
        with_ = query.args.get("with_")
        if from_ is None or with_ is None or not isinstance(from_.this, exp.Table):
            return None
        for cte in with_.expressions:
            if cte.alias != from_.this.name:
                continue
            if not isinstance(cte.this, exp.Select):
                return None
            names: set[str] = set()
            for projection in cte.this.expressions:
                named_column = isinstance(projection, exp.Column) and not isinstance(
                    projection.this, exp.Star
                )
                if not (isinstance(projection, exp.Alias) or named_column):
                    return None
                names.add(projection.alias_or_name)
            return names
        return None

    def _is_transform_boundary_token(self, token_type: TokenType, text: str) -> bool:
        """Return True if a token can start a new pipeline transform."""
        if token_type == TokenType.IDENTIFIER:
            return False  # a backticked name is never a keyword (`limit`)
        if token_type == TokenType.PIPE_GT:
            return True
        if token_type == TokenType.SEMICOLON:
            return True
        # In SELECT fragments parsed via helper statements (e.g. `SELECT <fragment> FROM _t`),
        # `FROM` must end the projection list. Treat it as a hard boundary at top level.
        if token_type == TokenType.FROM:
            return True
        if token_type in (TokenType.GROUP_BY, TokenType.ORDER_BY):
            return True
        if token_type in (TokenType.UNION, TokenType.INTERSECT):
            return True
        return text.upper() in self.TRANSFORM_PARSERS

    def _starts_join_step(self, i: int) -> bool:
        """Return True if tokens at ``i`` open a join step (`& table ...`).

        `&` and `*` are also expression operators, so an operator only starts a
        join when a table reference follows and that reference is itself followed
        by something a join can be followed by (`on`, `as`, another join
        operator, a transform keyword, or the end of the query). `*` additionally
        has to start a line: `price * qty` is far more common in a filter than a
        cross join, and every documented pipeline puts the step on its own line.
        """
        tokens = self._tokens
        tok = tokens[i]
        if tok.token_type == TokenType.STAR:
            if i == 0 or tok.line == tokens[i - 1].line:
                return False
        elif not (
            tok.token_type in (TokenType.AMP, TokenType.QMARK_AMP)
            or (tok.token_type == TokenType.PLACEHOLDER and tok.text == "?&?")
        ):
            return False

        j = i + 1
        if j >= len(tokens) or tokens[j].token_type != TokenType.VAR:
            return False
        j += 1
        while (
            j + 1 < len(tokens)
            and tokens[j].token_type == TokenType.DOT
            and tokens[j + 1].token_type == TokenType.VAR
        ):
            j += 2
        if j >= len(tokens):
            return True
        after = tokens[j]
        return (
            after.token_type in (TokenType.ON, TokenType.ALIAS)
            or self._starts_join_step(j)
            or self._is_transform_boundary_token(after.token_type, after.text)
        )

    def _find_transform_boundary_index(self, stop_at_join: bool = False) -> int:
        """Find token index where a transform payload should stop.

        With ``stop_at_join``, a join operator that opens a join step also ends
        the payload (a `where` followed by `& table on ...`).
        """
        depth = 0
        i = self._index
        while i < len(self._tokens):
            tok = self._tokens[i]

            if tok.token_type in (
                TokenType.L_PAREN,
                TokenType.L_BRACKET,
                TokenType.L_BRACE,
            ):
                depth += 1
            elif tok.token_type in (
                TokenType.R_PAREN,
                TokenType.R_BRACKET,
                TokenType.R_BRACE,
            ):
                if depth == 0:
                    # Closes the parenthesized pipeline this payload sits in.
                    return i
                depth -= 1

            if (
                depth == 0
                and i != self._index
                and (
                    self._is_transform_boundary_token(tok.token_type, tok.text)
                    or (stop_at_join and self._starts_join_step(i))
                )
            ):
                return i

            i += 1

        return len(self._tokens)

    def _consume_tokens_until_index(self, end_index: int) -> None:
        """Advance tokens until self._index == end_index."""
        while self._curr and self._index < end_index:
            self._advance()

    def _parse_asql_expression_until_transform_boundary(self) -> exp.Expr | None:
        """Parse an expression until the next transform keyword (PRQL-style chaining).

        This enables indentation/newline pipelines without requiring explicit `|`.
        """
        if not self._curr:
            return None

        end_index = self._find_transform_boundary_index(stop_at_join=True)
        if self._index >= end_index:
            return None

        # `&`/`*` would be swallowed as binary operators, so hide the join
        # operator behind a statement terminator while the condition is parsed.
        join_token = self._tokens[end_index] if end_index < len(self._tokens) else None
        if join_token is not None and not self._is_transform_boundary_token(
            join_token.token_type, join_token.text
        ):
            original_type = join_token.token_type
            join_token.token_type = TokenType.SEMICOLON
            try:
                condition = self._parse_assignment()
            finally:
                join_token.token_type = original_type
        else:
            condition = self._parse_assignment()
        self._consume_tokens_until_index(end_index)
        return condition

    def _parse_asql_select_expressions_until_transform_boundary(
        self,
    ) -> list[exp.Expr]:
        """Parse SELECT projections until the next transform keyword."""
        if not self._curr:
            return []

        end_index = self._find_transform_boundary_index()
        expressions: list[exp.Expr] = []

        while self._curr and self._index < end_index:
            expression = self._parse_expression()
            if not expression:
                break
            expressions.append(expression)

            if not self._match(TokenType.COMMA):
                break

        self._consume_tokens_until_index(end_index)
        return expressions

    def _parse_asql_group_by(self, query: exp.Select) -> exp.Select:
        """Parse GROUP BY with optional aggregate block: group by X (agg1, agg2).

        Note: GROUP BY is tokenized as a single token, so BY is already consumed.

        Syntax options:
        1. group by col1, col2              - standard GROUP BY
        2. group by col1 (agg1, agg2)       - GROUP BY with aggregate block
        3. group by col1, col2 (agg1, agg2) - multiple cols with aggregates

        The tricky part: `group by region (sum(amount))` - the ( starts an aggregate
        block, not a function call. We use _parse_group_by_term() which handles this.
        """
        expressions: list[exp.Expr] = []

        while True:
            # Check if this is start of aggregate block
            if self._curr and self._curr.token_type == TokenType.L_PAREN:
                break

            # Parse group-by term: can be column or function like month(date)
            expr = self._parse_group_by_term()
            if not expr:
                break

            # Check if expression looks like it consumed the aggregate block
            if isinstance(expr, exp.Anonymous) and expr.expressions:
                has_alias = any(isinstance(arg, exp.Alias) for arg in expr.expressions)
                if has_alias:
                    group_col = exp.Column(this=exp.to_identifier(expr.name))
                    expressions.append(group_col)
                    query.group_by(*expressions, copy=False)
                    query.meta[_GROUP_STAGE] = "block"
                    select_exprs = list(expressions) + list(expr.expressions)
                    query.select(*select_exprs, append=False, copy=False)
                    return query

            expressions.append(expr)

            # After parsing expression, check for aggregate block
            if self._curr and self._curr.token_type == TokenType.L_PAREN:
                break

            if not self._match(TokenType.COMMA):
                break

        if not expressions:
            return query

        query.group_by(*expressions, copy=False)
        query.meta[_GROUP_STAGE] = "bare"

        # Check for aggregate block: group by X (agg1, agg2)
        if self._match(TokenType.L_PAREN):
            query.meta[_GROUP_STAGE] = "block"
            aggregates = self._parse_csv(self._parse_expression)
            if not self._match(TokenType.R_PAREN):
                self.raise_error("Expected ) to close aggregate block")

            # Replace SELECT * with grouping cols + aggregates. spine(x) marks the
            # GROUP BY key only; the projection selects x itself.
            # Copies: a key shared by GROUP BY and the projection would only be
            # resolved (week start, ...) in one of them by node.replace().
            select_exprs = [
                t.cast(exp.Expr, e.this if isinstance(e, Spine) else e).copy()
                for e in expressions
            ] + list(aggregates)
            query.select(*select_exprs, append=False, copy=False)

        return query

    def _parse_group_by_term(self) -> exp.Expr | None:
        """Parse a single GROUP BY term, handling the aggregate block ambiguity.

        This handles:
        - Simple columns: region, category
        - Qualified columns: customers.id, orders.total
        - Function calls: month(date), year(created_at), slugify(name)
        - Aliased expressions: month(date) as cohort, region as reg
        - But stops at standalone ( that starts an aggregate block

        The key insight: aggregate blocks always contain aliased expressions.
        So we parse a "simple term" (column or function) and stop before any
        standalone ( that looks like an aggregate block.
        """
        if not self._curr:
            return None

        expr: exp.Expr | None = None

        if self._curr.token_type in (TokenType.VAR, TokenType.IDENTIFIER):
            name = self._curr.text
            name_ident = self._identifier_from_token(self._curr)
            is_quoted = self._curr.token_type == TokenType.IDENTIFIER
            next_tok = self._next

            # Check for qualified column: table.column
            if next_tok and next_tok.token_type == TokenType.DOT:
                # This is table.column - parse the full qualified name
                self._advance()  # consume table name
                self._advance()  # consume .

                if self._curr and self._curr.token_type in (
                    TokenType.VAR,
                    TokenType.IDENTIFIER,
                ):
                    col_ident = self._identifier_from_token(self._curr)
                    self._advance()  # consume column name
                    expr = exp.Column(this=col_ident, table=name_ident)
                else:
                    # Malformed, just return the table as column
                    expr = exp.Column(this=name_ident)

            elif next_tok and next_tok.token_type == TokenType.L_PAREN and is_quoted:
                # A backticked name is never a function call, so the ( after
                # `my col` can only open the aggregate block.
                self._advance()  # consume identifier
                expr = exp.Column(this=name_ident)

            elif next_tok and next_tok.token_type == TokenType.L_PAREN:
                # Check if this looks like an aggregate block. Unaliased block
                # contents only count when the identifier is not a known
                # function — `coalesce(sum_amount)` stays a function call,
                # `region (sum_amount)` is a key + block.
                upper_name = name.upper()
                known_function = (
                    upper_name in self.FUNCTION_PARSERS or upper_name in self.FUNCTIONS
                )
                if self._looks_like_aggregate_block_at(
                    self._index + 1, allow_unaliased=not known_function
                ):
                    # This is: identifier (aggregate_block)
                    self._advance()  # consume identifier
                    expr = exp.Column(this=exp.to_identifier(name))
                else:
                    # Otherwise, this is a function call like month(date) or slugify(name)
                    # Check if it's a custom function with special parsing (like SLUGIFY)
                    if upper_name in self.FUNCTION_PARSERS:
                        # Use the custom function parser
                        self._advance()  # consume function name
                        expr = self.FUNCTION_PARSERS[upper_name](self)
                    else:
                        # Otherwise, parse as a standard function
                        self._advance()  # consume identifier
                        self._advance()  # consume (

                        # Parse function arguments
                        args = self._parse_csv(self._parse_expression)

                        if not self._match(TokenType.R_PAREN):
                            self.raise_error("Expected ) after function arguments")

                        # Build function expression using FUNCTIONS registry if available
                        func_class = self.FUNCTIONS.get(upper_name)
                        if func_class:
                            expr = func_class(args)
                        else:
                            expr = exp.Anonymous(this=name, expressions=args)
            else:
                # Simple column
                self._advance()
                expr = exp.Column(this=name_ident)
        else:
            # For other cases (literals, etc.), use standard parsing
            expr = self._parse_primary()

        # Check for optional alias: "AS alias" or just "alias"
        # But don't consume ( which starts aggregate block
        if expr and self._curr:
            if self._match(TokenType.ALIAS):
                # Explicit AS keyword
                if self._curr and self._curr.token_type in (
                    TokenType.VAR,
                    TokenType.IDENTIFIER,
                ):
                    alias_ident = self._identifier_from_token(self._curr)
                    self._advance()
                    expr = exp.Alias(this=expr, alias=alias_ident)

        return expr

    @staticmethod
    def _identifier_from_token(token: Token) -> exp.Identifier:
        """Identifier for a name token; backticked (IDENTIFIER) tokens stay quoted."""
        if token.token_type == TokenType.IDENTIFIER:
            return exp.Identifier(this=token.text, quoted=True)
        return exp.to_identifier(token.text)

    # True aggregate names for unaliased aggregate-block detection. Subset of
    # NATURAL_AGG_FUNCS: date parts like MONTH are group keys, not aggregates.
    _AGG_BLOCK_FUNCS = frozenset(
        {
            "SUM",
            "TOTAL",
            "AVG",
            "AVERAGE",
            "COUNT",
            "UNIQ",
            "MIN",
            "MINIMUM",
            "MAX",
            "MAXIMUM",
        }
    )

    def _metric_names(self) -> t.Collection[str]:
        from asql.schema import Schema

        schema = self._get_setting("schema")
        if isinstance(schema, Schema) and schema.graph is not None:
            return schema.graph.metrics.keys()
        return ()

    def _looks_like_aggregate_block_at(
        self, paren_idx: int, allow_unaliased: bool = False
    ) -> bool:
        """Check if ( at given index starts an aggregate block vs a function call.

        Aggregate blocks contain aggregate functions with aliases:
        - (sum(amount) as revenue)   - explicit alias
        - (count(*) num)             - implicit alias (func followed by VAR)

        With allow_unaliased (the identifier before the paren is not a known
        function, so a function-call reading would be garbage), unaliased
        aggregate contents also count:
        - (sum(amount))              - parens form, auto-aliased later
        - (sum_amount, avg_price)    - underscore shorthand
        - (sum amount)               - space shorthand
        - (#)                        - count shorthand
        - (volume)                   - a metric declared in the schema's graph

        Regular function calls don't have this structure:
        - month(event_date)
        """
        peek_idx = paren_idx + 1  # Start after the (

        if peek_idx >= len(self._tokens):
            return False

        # Look for pattern: func(...) VAR  or  func(...) AS VAR
        depth = 1
        found_inner_func = False

        while peek_idx < len(self._tokens) and depth > 0:
            tok = self._tokens[peek_idx]

            if tok.token_type == TokenType.L_PAREN:
                depth += 1
            elif tok.token_type == TokenType.R_PAREN:
                depth -= 1
                if depth == 1 and found_inner_func:
                    # Just closed an inner function, check what follows
                    next_idx = peek_idx + 1
                    if next_idx < len(self._tokens):
                        next_tok = self._tokens[next_idx]
                        # Check for explicit alias: ) AS
                        if next_tok.token_type == TokenType.ALIAS:
                            return True
                        # Check for implicit alias: ) VAR (not followed by ()
                        if next_tok.token_type == TokenType.VAR:
                            # Make sure it's not another function call
                            after_var_idx = next_idx + 1
                            if after_var_idx >= len(self._tokens):
                                return True  # VAR at end
                            after_var = self._tokens[after_var_idx]
                            if after_var.token_type != TokenType.L_PAREN:
                                return True  # VAR not followed by (
            elif depth == 1:
                # At top level of the block
                if tok.token_type == TokenType.ALIAS:
                    return True  # Found AS at top level
                if allow_unaliased and tok.token_type == TokenType.HASH:
                    return True  # Count shorthand: (#)
                if tok.token_type == TokenType.VAR:
                    upper = tok.text.upper()
                    # Check if this is a function call
                    next_idx = peek_idx + 1
                    following = (
                        self._tokens[next_idx] if next_idx < len(self._tokens) else None
                    )
                    if following and following.token_type == TokenType.L_PAREN:
                        found_inner_func = True
                        if allow_unaliased and upper in self._AGG_BLOCK_FUNCS:
                            return True  # Parens form: (sum(amount))
                    elif allow_unaliased:
                        if tok.text.lower() in self._metric_names():
                            return True  # Semantic-graph metric: (volume)
                        if (
                            upper in self._AGG_BLOCK_FUNCS
                            and following
                            and following.token_type == TokenType.VAR
                        ):
                            return True  # Space shorthand: (sum amount)
                        if any(
                            upper.startswith(f"{agg}_") for agg in self._AGG_BLOCK_FUNCS
                        ):
                            return True  # Underscore shorthand: (sum_amount)

            peek_idx += 1

        return False

    def _parse_asql_pipe_group_by(self, query: exp.Query) -> exp.Query:
        """Parse GROUP BY in pipe syntax: |> GROUP BY col.

        This is called by PIPE_SYNTAX_TRANSFORM_PARSERS and handles proper
        CTE wrapping for pipeline semantics.

        After a GROUP BY, subsequent WHERE clauses should filter on aggregated
        results, which requires CTE wrapping.
        """
        # Parse the group by clause
        group_by = self._parse_group()
        if group_by:
            query.set("group", group_by)

        # Wrap in CTE so subsequent WHERE operates on grouped results
        return self._build_pipe_cte(query=query, expressions=[exp.Star()])

    def _parse_asql_extend(self, query: exp.Query) -> exp.Query:
        """Parse EXTEND clause: extend expr as alias."""
        expressions = self._parse_csv(self._parse_expression)
        if not expressions:
            return query

        # EXTEND adds columns: SELECT *, new_col
        all_exprs = [exp.Star()] + list(expressions)
        return self._build_pipe_cte(
            query=query.select(*all_exprs, append=False, copy=False),
            expressions=[exp.Star()],
        )

    def _parse_asql_explode(self, query: exp.Select) -> exp.Select:
        """Parse EXPLODE clause: explode array_expr as alias.

        We parse into a CROSS JOIN UNNEST(...) AS alias. Dialect-specific differences
        (e.g. Snowflake FLATTEN) are handled in the compiler stage.
        """
        array_expr = self._parse_unary()
        if not array_expr:
            self.raise_error("Expected expression after 'explode'")
            return query

        if not self._match(TokenType.ALIAS):  # AS
            self.raise_error("Expected 'as' after explode expression")

        alias = self._parse_id_var()
        if alias is None:
            self.raise_error("Expected alias name after 'explode ... as'")
            return query

        unnest = exp.Unnest(
            expressions=[array_expr],
            alias=exp.TableAlias(this=exp.to_identifier(alias.name)),
        )

        return query.join(unnest, join_type="CROSS", copy=False)

    def _parse_table(
        self,
        schema: bool = False,
        joins: bool = False,
        alias_tokens: t.Collection[TokenType] | None = None,
        parse_bracket: bool = False,
        is_db_reference: bool = False,
        parse_partition: bool = False,
        consume_pipe: bool = False,
    ) -> exp.Expr | None:
        """Override to support `FROM <table> explode <expr> as <alias>` in SELECT-first queries.

        The preparser can reorder FROM-first pipelines into SELECT-first queries, so `explode`
        must be understood at the table-expression level (like PIVOT/UNPIVOT).
        """
        table_expr = super()._parse_table(
            schema=schema,
            joins=joins,
            alias_tokens=alias_tokens,
            parse_bracket=parse_bracket,
            is_db_reference=is_db_reference,
            parse_partition=parse_partition,
            consume_pipe=consume_pipe,
        )
        if not table_expr:
            return table_expr

        # Handle: FROM posts explode tags as tag
        if self._match_text_seq("EXPLODE"):
            array_expr = self._parse_unary()
            if not array_expr:
                self.raise_error("Expected expression after 'explode'")
                return table_expr

            if not self._match(TokenType.ALIAS):  # AS
                self.raise_error("Expected 'as' after explode expression")

            alias = self._parse_id_var()
            if alias is None:
                self.raise_error("Expected alias name after 'explode ... as'")
                return table_expr

            unnest = exp.Unnest(
                expressions=[array_expr],
                alias=exp.TableAlias(this=exp.to_identifier(alias.name)),
            )
            join = exp.Join(this=unnest, kind="CROSS")
            table_expr.append("joins", join)

        return table_expr

    def _parse_asql_stash(self, query: exp.Query) -> exp.Query:
        """Parse STASH AS clause for CTEs."""
        if not self._match(TokenType.ALIAS):  # AS
            self.raise_error("Expected 'as' after 'stash'")

        alias = self._parse_id_var()
        if alias is None:
            self.raise_error("Expected CTE name after 'stash as'")
            return query

        # Create CTE and continue with SELECT * FROM cte
        # Pass the alias name as a string, not TableAlias, so that _build_pipe_cte
        # creates a proper Table node in FROM (not TableAlias). This is needed for
        # eliminate_ctes to correctly handle the CTE reference.
        alias_name = alias.name
        passthrough = self._passthrough_cte_name(query)
        if passthrough is not None and AUTO_CTE_RE.fullmatch(passthrough):
            # `extend x as y stash as foo`: the extend already closed its stage
            # into __tmpN, so name that CTE instead of chaining `foo AS (SELECT *
            # FROM __tmpN)` behind it.
            with_ = query.args["with_"]
            with_.expressions[-1].set(
                "alias", exp.TableAlias(this=exp.to_identifier(alias_name))
            )
            query.args["from_"].this.set("this", exp.to_identifier(alias_name))
            stashed: exp.Query = query
        else:
            stashed = self._build_pipe_cte(query, [exp.Star()], alias_name)  # type: ignore[arg-type]
        stashed.meta[_STASHED] = True
        return stashed

    @staticmethod
    def _passthrough_cte_name(query: exp.Query) -> str | None:
        """Name of the CTE that `query` merely re-selects (`SELECT * FROM cte`), else None."""
        if not isinstance(query, exp.Select):
            return None
        if [type(e) for e in query.expressions] != [exp.Star]:
            return None
        clause_keys = (
            "joins",
            "where",
            "group",
            "having",
            "qualify",
            "order",
            "limit",
            "offset",
            "distinct",
            "laterals",
            "windows",
            "sample",
        )
        if any(query.args.get(key) for key in clause_keys):
            return None
        from_ = query.args.get("from_")
        with_ = query.args.get("with_")
        table = from_.this if from_ else None
        if (
            not isinstance(table, exp.Table)
            or table.alias
            or table.db
            or table.args.get("pivots")
            or table.args.get("sample")
            or not with_
            or not with_.expressions
        ):
            return None
        last_cte = with_.expressions[-1]
        if not isinstance(last_cte, exp.CTE) or last_cte.alias != table.name:
            return None
        return table.name

    def _parse_asql_join(self, query: exp.Select, kind: str = "INNER") -> exp.Select:
        """Parse JOIN clause with ASQL join operators.

        We need to custom parse because SQLGlot's _parse_join uses _parse_assignment
        for ON conditions, which doesn't stop at ASQL join operators (&, &?, ?&, ?&?).
        """
        # Parse table name and optional alias
        this = self._parse_table()
        if not this:
            return query

        # Check for ON condition
        on_condition = None
        if self._match(TokenType.ON):
            # Parse ON condition, stopping at ASQL join operators
            on_condition = self._parse_on_condition_until_join_op()

        if kind in ("RIGHT", "FULL OUTER") and query.args.get("where"):
            if query.args.get("joins"):
                raise ASQLCompilationError(
                    f"A {kind.lower()} join after a `where` that follows earlier "
                    "joins is ambiguous: the filter would apply after the earlier "
                    "joins, but a right/full join needs the filtered result first. "
                    "Name the filtered result in its own stage with `stash as`, "
                    "then join to it."
                )
            # A preceding `where` filters the left side before this join; leaving
            # it in the outer WHERE would also drop the null-extended rows.
            source = query.args["from_"].this
            filtered = exp.select("*").from_(source).where(query.args["where"].this)
            query.set("where", None)
            query.set(
                "from_",
                exp.From(
                    this=exp.Subquery(
                        this=filtered,
                        alias=exp.TableAlias(
                            this=exp.to_identifier(source.alias_or_name)
                        ),
                    )
                ),
            )

        # Build the join
        join = exp.Join(this=this, on=on_condition, kind=kind)
        query.join(join, copy=False)
        return query

    def _parse_on_condition_until_join_op(self) -> exp.Expr | None:
        """Parse ON condition, stopping at ASQL join operators.

        This is needed because the standard _parse_assignment will consume
        ASQL join operators (&, &?, ?&, ?&?) as part of the expression.

        We handle three cases:
        1. FK shorthand: ON user_id → just a column name (next token is join op)
        2. Simple/complex expression without join ops: use standard parser
        3. Complex with chained joins: stop at join operators
        """
        # Check if the next token after the current one is a join operator
        # If so, this is FK shorthand - just return the column
        if self._is_at_join_op_or_end(offset=1):
            return self._parse_column()

        # Scan ahead to see if there are any join operators in the condition
        has_join_op = self._scan_for_join_op_in_condition()

        if not has_join_op:
            # No join operators - use standard parser
            return self._parse_assignment()

        # Otherwise, parse the full expression but stop at join operators
        return self._parse_on_expr_with_join_stop()

    def _scan_for_join_op_in_condition(self) -> bool:
        """Scan ahead to check if there's a join operator before the next clause."""
        idx = self._index
        paren_depth = 0

        while idx < len(self._tokens):
            tok = self._tokens[idx]

            # Track parentheses
            if tok.token_type == TokenType.L_PAREN:
                paren_depth += 1
            elif tok.token_type == TokenType.R_PAREN:
                paren_depth -= 1

            # Only check for join ops outside parentheses
            if paren_depth == 0:
                # Stop at clause keywords
                if tok.token_type in (
                    TokenType.WHERE,
                    TokenType.GROUP_BY,
                    TokenType.ORDER_BY,
                    TokenType.LIMIT,
                    TokenType.HAVING,
                    TokenType.QUALIFY,
                ):
                    return False

                # Check for join operators
                if tok.token_type in (TokenType.AMP, TokenType.QMARK_AMP):
                    return True
                if tok.token_type == TokenType.PLACEHOLDER and tok.text == "?&?":
                    return True
                if tok.token_type == TokenType.STAR:
                    if (
                        idx + 1 < len(self._tokens)
                        and self._tokens[idx + 1].token_type == TokenType.VAR
                    ):
                        return True

            idx += 1

        return False

    def _is_at_join_op_or_end(self, offset: int = 0) -> bool:
        """Check if token at current + offset is a join operator or end."""
        idx = self._index + offset
        if idx >= len(self._tokens):
            return True

        tok = self._tokens[idx]
        if tok.token_type in (TokenType.AMP, TokenType.QMARK_AMP):
            return True
        if tok.token_type == TokenType.PLACEHOLDER and tok.text == "?&?":
            return True
        if tok.token_type == TokenType.STAR:
            # Check if followed by table name
            if (
                idx + 1 < len(self._tokens)
                and self._tokens[idx + 1].token_type == TokenType.VAR
            ):
                return True
        return False

    def _parse_on_expr_with_join_stop(self) -> exp.Expr | None:
        """Parse ON expression, stopping at join operators.

        We scan ahead to find the extent of the expression, then parse it.
        """
        # Find extent of ON condition (stop at join operators, other clauses, or end)
        start_idx = self._index

        while self._curr and not self._is_at_join_op_or_end():
            # Also stop at clause keywords
            if self._curr.token_type in (
                TokenType.WHERE,
                TokenType.GROUP_BY,
                TokenType.ORDER_BY,
                TokenType.LIMIT,
                TokenType.HAVING,
                TokenType.QUALIFY,
            ):
                break
            self._advance()

        # Parse what we've accumulated
        end_idx = self._index

        if end_idx == start_idx:
            return None

        # Reset to start and parse as expression
        self._retreat(start_idx)

        # Use a simpler parsing strategy - parse terms and operators manually
        left = self._parse_term_for_join()
        if not left:
            return None

        # Handle comparison operators
        while self._curr and self._index < end_idx:
            if self._match(TokenType.EQ):
                right = self._parse_term_for_join()
                left = exp.EQ(this=left, expression=right)
            elif self._match(TokenType.AND) or self._match(TokenType.DAMP):
                right = self._parse_term_for_join()
                if self._curr and self._index < end_idx and self._match(TokenType.EQ):
                    right2 = self._parse_term_for_join()
                    right = exp.EQ(this=right, expression=right2)
                left = exp.And(this=left, expression=right)
            elif self._match(TokenType.OR):
                right = self._parse_term_for_join()
                if self._curr and self._index < end_idx and self._match(TokenType.EQ):
                    right2 = self._parse_term_for_join()
                    right = exp.EQ(this=right, expression=right2)
                left = exp.Or(this=left, expression=right)
            else:
                break

        return left

    def _parse_term_for_join(self) -> exp.Expr | None:
        """Parse a term for join condition (column, literal, or qualified name)."""
        if not self._curr:
            return None

        # Handle qualified names: table.column
        if self._curr.token_type == TokenType.VAR:
            name = self._curr.text
            self._advance()

            if self._match(TokenType.DOT):
                if self._curr and self._curr.token_type == TokenType.VAR:
                    col_name = self._curr.text
                    self._advance()
                    return exp.Column(
                        this=exp.to_identifier(col_name), table=exp.to_identifier(name)
                    )

            return exp.Column(this=exp.to_identifier(name))

        # Handle literals
        if self._curr.token_type in (TokenType.STRING, TokenType.NUMBER):
            val = self._curr.text
            self._advance()
            assert self._prev is not None  # _advance guarantees _prev is set
            return (
                exp.Literal.string(val)
                if self._prev.token_type == TokenType.STRING
                else exp.Literal.number(val)
            )

        # Handle TRUE/FALSE
        if self._curr.token_type in (TokenType.TRUE, TokenType.FALSE):
            flag = self._curr.token_type == TokenType.TRUE
            self._advance()
            return exp.Boolean(this=flag)

        return None

    def _parse_join_kind(
        self, query: exp.Query, kind: str, skip_keywords: tuple[str, ...] = ()
    ) -> exp.Query:
        """Parse join with specified kind after consuming optional keywords."""
        for kw in skip_keywords:
            self._match_text_seq(*kw.split())
        return self._parse_asql_join(t.cast(exp.Select, query), kind=kind)

    def _parse_asql_qmark_join(self, query: exp.Query) -> exp.Query:
        """Parse &? (LEFT) or ?& (RIGHT) join based on previous token."""
        prev = self._tokens[self._index - 1].text if self._index > 0 else ""
        return self._parse_asql_join(
            t.cast(exp.Select, query), kind="LEFT" if prev == "&?" else "RIGHT"
        )

    def _parse_asql_per(self, query: exp.Query) -> exp.Query:
        """Parse PER command for window operations.

        Syntax:
        - per <partition_cols> first by <order_expr>  → QUALIFY ROW_NUMBER()=1
        - per <partition_cols> last by <order_expr>   → QUALIFY ROW_NUMBER()=1 (reversed order)
        - per <partition_cols> number by <order_expr> [as alias] → add ROW_NUMBER() to SELECT
        - per <partition_cols> rank by <order_expr> [as alias]   → add RANK() to SELECT
        - per <partition_cols> dense rank by <order_expr> [as alias] → add DENSE_RANK() to SELECT
        """
        # Parse partition columns (comma-separated)
        partition_cols: list[exp.Expr] = []
        while True:
            col = self._parse_column()
            if col:
                partition_cols.append(col)
            if not self._match(TokenType.COMMA):
                break

        if not partition_cols:
            self.raise_error("Expected partition columns after PER")
            return query

        # Check for operation type: first/last/number/rank/dense rank
        # Use dict lookups instead of elif chains (SQLGlot idiomatic pattern)

        # Check FIRST token type first (it has a dedicated TokenType)
        if self._match(TokenType.FIRST):
            return self._handle_per_qualify_op(
                t.cast(exp.Select, query), partition_cols, reverse_order=False
            )

        # Check qualify operations (FIRST, LAST)
        for tokens, reverse_order in self._PER_QUALIFY_OPS.items():
            if self._match_text_seq(*tokens):
                return self._handle_per_qualify_op(
                    t.cast(exp.Select, query), partition_cols, reverse_order
                )

        # Check window operations (NUMBER, RANK, DENSE RANK)
        for tokens, (expr_class, default_alias) in self._PER_WINDOW_OPS.items():
            if self._match_text_seq(*tokens):
                return self._handle_per_window_op(
                    query, partition_cols, expr_class, default_alias
                )

        self.raise_error(
            "Expected FIRST, LAST, NUMBER, RANK, or DENSE RANK after partition columns"
        )
        return query

    def _handle_per_qualify_op(
        self,
        query: exp.Select,
        partition_cols: list[exp.Expr],
        reverse_order: bool,
    ) -> exp.Query:
        """Handle PER ... FIRST/LAST BY ... → QUALIFY ROW_NUMBER() = 1."""
        if not self._match_text_seq("BY"):
            self.raise_error("Expected BY after FIRST/LAST")
            return query
        order_expr, order_desc = self._parse_order_col_with_direction()
        if reverse_order:
            order_desc = not order_desc
        return self._add_qualify_row_number(
            query, partition_cols, order_expr, order_desc
        )

    def _handle_per_window_op(
        self,
        query: exp.Query,
        partition_cols: list[exp.Expr],
        expr_class: type[exp.Func],
        default_alias: str,
    ) -> exp.Query:
        """Handle PER ... NUMBER/RANK/DENSE RANK BY ... → add window function to SELECT."""
        if not self._match_text_seq("BY"):
            self.raise_error(f"Expected BY after {default_alias.upper()}")
            return query
        order_expr, order_desc = self._parse_order_col_with_direction()
        alias = self._parse_alias_after_as()
        return self._add_window_to_select(
            query,
            expr_class,
            partition_cols,
            order_expr,
            order_desc,
            alias or default_alias,
        )

    def _parse_order_col_with_direction(self) -> tuple[exp.Expr, bool]:
        """Parse order column with optional - prefix for DESC."""
        order_desc = False
        if self._match(TokenType.DASH):
            order_desc = True
        order_expr = self._parse_column() or exp.Null()
        return order_expr, order_desc

    def _parse_alias_after_as(self) -> str | None:
        """Parse optional AS alias."""
        if self._match(TokenType.ALIAS):
            alias_expr = self._parse_id_var()
            return alias_expr.this if alias_expr else None
        return None

    def _add_qualify_row_number(
        self,
        query: exp.Query,
        partition_cols: list[exp.Expr],
        order_expr: exp.Expr,
        order_desc: bool,
    ) -> exp.Query:
        """Add QUALIFY ROW_NUMBER() OVER (...) = 1 to query."""
        # Build window: ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)
        order = exp.Ordered(this=order_expr, desc=order_desc)
        row_num = exp.Window(
            this=exp.RowNumber(),
            partition_by=partition_cols,
            order=exp.Order(expressions=[order]),
        )

        # QUALIFY ROW_NUMBER() = 1
        qualify_cond = exp.EQ(this=row_num, expression=exp.Literal.number(1))

        assert isinstance(query, exp.Select)
        return query.qualify(qualify_cond, copy=False)

    def _add_window_to_select(
        self,
        query: exp.Query,
        window_func: type[exp.Func],
        partition_cols: list[exp.Expr],
        order_expr: exp.Expr,
        order_desc: bool,
        alias: str,
    ) -> exp.Query:
        """Add a window function to the SELECT list."""
        # Build window: func() OVER (PARTITION BY ... ORDER BY ...)
        order = exp.Ordered(this=order_expr, desc=order_desc)
        window = exp.Window(
            this=window_func(),
            partition_by=partition_cols,
            order=exp.Order(expressions=[order]),
        )

        # Add as aliased column to SELECT
        aliased = exp.Alias(this=window, alias=exp.to_identifier(alias))

        return query.select(aliased, append=True, copy=False)

    def _parse_asql_standalone_rank(
        self, query: exp.Query, window_func: type[exp.Func], default_alias: str
    ) -> exp.Query | None:
        """Parse standalone ranking: number by <col> [as alias] or rank by <col> [as alias].

        Only triggers if followed by BY. Otherwise returns None to fall through
        to standard function parsing (e.g., rank() over (...)).
        """
        if not self._match_text_seq("BY"):
            return None

        order_expr, order_desc = self._parse_order_col_with_direction()
        alias = self._parse_alias_after_as()

        # Build window: func() OVER (ORDER BY ...)
        order = exp.Ordered(this=order_expr, desc=order_desc)
        window = exp.Window(this=window_func(), order=exp.Order(expressions=[order]))

        # Add as aliased column to SELECT
        aliased = exp.Alias(
            this=window, alias=exp.to_identifier(alias or default_alias)
        )

        return query.select(aliased, append=True, copy=False)

    def _parse_asql_dense_rank_standalone(self, query: exp.Query) -> exp.Query:
        """Parse dense rank by <col> [as alias] (handles the space in 'dense rank')."""
        if not self._match_text_seq("RANK"):
            self.raise_error("Expected RANK after DENSE")
            return query
        result = self._parse_asql_standalone_rank(query, exp.DenseRank, "dense_rank")
        return result if result is not None else query

    def _parse_asql_deduplicate(self, query: exp.Query) -> exp.Query:
        """Parse deduplicate by <cols> order by <col>.

        This is syntactic sugar for: per <cols> first by <col>
        """
        if not self._match_text_seq("BY"):
            self.raise_error("Expected BY after DEDUPLICATE")
            return query

        # Parse partition columns
        partition_cols: list[exp.Expr] = []
        while True:
            col = self._parse_column()
            if col:
                partition_cols.append(col)
            if not self._match(TokenType.COMMA):
                break

        if not partition_cols:
            self.raise_error("Expected columns after DEDUPLICATE BY")
            return query

        # Expect ORDER BY
        if not self._match(TokenType.ORDER_BY) and not self._match_text_seq(
            "ORDER", "BY"
        ):
            self.raise_error("DEDUPLICATE BY requires ORDER BY clause")
            return query

        # Parse order expression with optional - prefix
        order_expr, order_desc = self._parse_order_col_with_direction()

        # Same as: per <cols> first by <order_col>
        return self._add_qualify_row_number(
            query, partition_cols, order_expr, order_desc
        )

    def _parse_asql_spine_by(self, query: exp.Query) -> exp.Query:
        """Parse spine by <columns> (aggregations).

        Syntax:
            spine by month(created_at) (sum(amount))
            spine by month(date), year(date) (sum(amount), count(*))

        This is like GROUP BY but wraps each column in Spine() to mark it
        for gap-filling transformation.

        Returns a query with GROUP BY containing Spine-wrapped columns.
        """
        if not self._match_text_seq("BY"):
            self.raise_error("Expected BY after SPINE")
            return query

        # Parse comma-separated columns (each will be wrapped in Spine)
        # Use same logic as _parse_asql_group_by but wrap in Spine
        columns: list[exp.Expr] = []

        while True:
            # Check if this is start of aggregate block
            if self._curr and self._curr.token_type == TokenType.L_PAREN:
                break

            # Parse spine term (like group-by term)
            expr = self._parse_group_by_term()
            if not expr:
                break

            # Wrap in Spine
            columns.append(Spine(this=expr))

            # After parsing expression, check for aggregate block
            if self._curr and self._curr.token_type == TokenType.L_PAREN:
                break

            # Check for comma vs end
            if not self._match(TokenType.COMMA):
                break

        if not columns:
            self.raise_error("Expected column expression after SPINE BY")
            return query

        # Set GROUP BY with Spine-wrapped columns
        query.set("group", exp.Group(expressions=columns))
        query.meta[_GROUP_STAGE] = "bare"

        # Parse optional aggregations in parens: (sum(amount), count(*))
        if self._match(TokenType.L_PAREN):
            query.meta[_GROUP_STAGE] = "block"
            aggs = self._parse_csv(self._parse_expression)
            if not self._match(TokenType.R_PAREN):
                self.raise_error("Expected ) to close aggregate block")

            # Replace SELECT * with spine columns + aggs
            new_select = []
            for spine_col in columns:
                # Extract inner expression from Spine for SELECT
                inner = spine_col.this
                new_select.append(inner.copy())
            new_select.extend(aggs)
            query.select(*new_select, append=False, copy=False)

        return query

    def _parse_asql_distinct(self, query: exp.Query) -> exp.Query:
        """Parse DISTINCT / DISTINCT ON (...) for ASQL pipelines."""
        if self._match(TokenType.ON):
            on_columns = self._parse_wrapped_csv(self._parse_column)
            if not on_columns:
                self.raise_error("Expected column list after DISTINCT ON")
            query.set("distinct", exp.Distinct(on=exp.Tuple(expressions=on_columns)))
            return query

        query.set("distinct", exp.Distinct())
        return query

    def _parse_asql_except(self, query: exp.Query) -> exp.Query:
        """Parse EXCEPT column operator."""
        # EXCEPT col1, col2 - exclude columns
        columns = self._parse_csv(self._parse_column)
        if not columns:
            return query

        # In maintainer-style dialects, prefer mutating the query projection in-place
        # rather than wrapping in synthetic CTEs unless semantics require it.
        expressions: list[exp.Expr] = list(query.expressions)
        star = next((e for e in expressions if isinstance(e, exp.Star)), None)
        if not star:
            star = exp.Star()
            expressions.insert(0, star)

        existing = star.args.get("except_") or star.args.get("except") or []
        existing_names = {
            c.name for c in existing if isinstance(c, exp.Column) and c.name
        }
        new_names = {c.name for c in columns if isinstance(c, exp.Column) and c.name}
        merged_names = sorted(existing_names.union(new_names))
        star.set(
            "except_", [exp.Column(this=exp.to_identifier(n)) for n in merged_names]
        )

        query.set("expressions", expressions)
        return query

    def _parse_asql_rename(self, query: exp.Query) -> exp.Query:
        """Parse RENAME column operator."""
        # Syntax:
        #   rename old as new
        #   rename old as new, old2 as new2
        rename_pairs: list[tuple[exp.Column, exp.Expr]] = []

        while True:
            old = self._parse_column()
            if not old or not isinstance(old, exp.Column):
                self.raise_error("Expected column name after RENAME")
                return query

            if not self._match(TokenType.ALIAS) and not self._match_text_seq("AS"):
                self.raise_error("Expected AS in RENAME mapping")
                return query

            new = self._parse_id_var()
            if not new:
                self.raise_error("Expected new column name after AS in RENAME mapping")
                return query

            rename_pairs.append((old, new))

            if not self._match(TokenType.COMMA):
                break

        expressions: list[exp.Expr] = list(query.expressions)
        star = next((e for e in expressions if isinstance(e, exp.Star)), None)
        if not star:
            star = exp.Star()
            expressions.insert(0, star)

        existing = star.args.get("except_") or star.args.get("except") or []
        existing_names = {
            c.name for c in existing if isinstance(c, exp.Column) and c.name
        }

        # Renames must exclude the original columns to avoid duplicates
        rename_old_names = {old.name for old, _ in rename_pairs}
        merged_names = sorted(existing_names.union(rename_old_names))
        star.set(
            "except_", [exp.Column(this=exp.to_identifier(n)) for n in merged_names]
        )

        expressions.extend(
            exp.Alias(this=exp.Column(this=old.this), alias=new)
            for old, new in rename_pairs
        )
        query.set("expressions", expressions)
        return query

    def _parse_asql_replace(self, query: exp.Query) -> exp.Query:
        """Parse REPLACE column operator."""
        # Syntax:
        #   replace col with expr
        #   replace col with expr, col2 with expr2
        replace_pairs: list[tuple[str, exp.Expr]] = []

        while True:
            col = self._parse_column()
            if not col or not isinstance(col, exp.Column):
                self.raise_error("Expected column name after REPLACE")
                return query

            if not self._match_text_seq("WITH"):
                self.raise_error("Expected WITH in REPLACE clause")
                return query

            expr = self._parse_assignment()
            if not expr:
                self.raise_error("Expected expression after WITH in REPLACE clause")
                return query

            replace_pairs.append((col.name, expr))

            if not self._match(TokenType.COMMA):
                break

        expressions: list[exp.Expr] = list(query.expressions)
        star = next((e for e in expressions if isinstance(e, exp.Star)), None)
        if not star:
            star = exp.Star()
            expressions.insert(0, star)

        existing = star.args.get("except_") or star.args.get("except") or []
        existing_names = {
            c.name for c in existing if isinstance(c, exp.Column) and c.name
        }

        exclude_names = {col for col, _ in replace_pairs}
        merged_names = sorted(existing_names.union(exclude_names))
        star.set(
            "except_", [exp.Column(this=exp.to_identifier(n)) for n in merged_names]
        )

        expressions.extend(
            exp.Alias(this=expr, alias=exp.to_identifier(col))
            for col, expr in replace_pairs
        )
        query.set("expressions", expressions)
        return query

    # Note: PIVOT/UNPIVOT parsing is handled by _parse_pivot() (table expression level)
    # Note: EXPLODE is still handled by preparser markers (complex dialect-specific output)

    def _parse_asql_sample(self, query: exp.Select) -> exp.Query:
        """Parse SAMPLE clause."""
        # Supported:
        # - sample N         -> ORDER BY RANDOM() LIMIT N
        # - sample N%        -> TABLESAMPLE BERNOULLI(N)
        # - sample N per col -> QUALIFY ROW_NUMBER() OVER (PARTITION BY col ORDER BY RANDOM()) <= N
        if not self._match(TokenType.NUMBER):
            self.raise_error("Expected number after SAMPLE")

        assert self._prev is not None  # _match(NUMBER) returned True: token consumed
        n = exp.Literal.number(self._prev.text)

        # sample N%
        if self._match(TokenType.MOD):  # %
            from_ = query.args.get("from_") or query.args.get("from")
            if not from_:
                return query

            # Attach TABLESAMPLE to the FROM target
            sampled = exp.TableSample(method="BERNOULLI", percent=n)
            table = from_.this
            if table:
                table.set("sample", sampled)
            return query

        # sample N per col (stratified)
        if self._match_text_seq("PER"):
            partition_col = self._parse_column()
            if not partition_col:
                self.raise_error("Expected column after SAMPLE <n> PER")
                return query

            rand = exp.Rand()
            window = exp.Window(
                this=exp.RowNumber(),
                partition_by=exp.Partition(expressions=[partition_col]),
                order=exp.Order(expressions=[exp.Ordered(this=rand)]),
            )
            condition = exp.LTE(this=window, expression=n)
            sampled_query = query.qualify(condition, copy=False)
            sampled_query.meta[SAMPLE_META] = {
                "size": n.this,
                "per": partition_col.copy(),
            }
            return self._build_pipe_cte(query=sampled_query, expressions=[exp.Star()])

        # sample N
        rand = exp.Rand()
        sampled_query = query.order_by(
            exp.Order(expressions=[exp.Ordered(this=rand)]), copy=False
        ).limit(n, copy=False)
        sampled_query.meta[SAMPLE_META] = {"size": n.this, "per": None}
        return self._build_pipe_cte(query=sampled_query, expressions=[exp.Star()])

    def _build_pipe_cte(
        self,
        query: exp.Query,
        expressions: list[exp.Expr],
        alias_cte: exp.TableAlias | None = None,
    ) -> exp.Select:
        """Never reuse an auto CTE name a `stash as __tmpN` already took."""
        if alias_cte is None:
            with_ = query.args.get("with_")
            taken = {cte.alias for cte in with_.expressions} if with_ else set()
            while f"__tmp{self._pipe_cte_counter + 1}" in taken:
                self._pipe_cte_counter += 1
        return super()._build_pipe_cte(query, expressions, alias_cte)

    def _parse_equality(self, parse_is: bool = True) -> exp.Expr | None:
        """Parse equality with NULL handling.

        Like PRQL: `== null` becomes `IS NULL`
        """
        eq = super()._parse_equality(parse_is=parse_is)
        if not isinstance(eq, (exp.EQ, exp.NEQ)):
            return eq

        # NULL handling: == null → IS NULL, != null → IS NOT NULL
        if isinstance(eq.expression, exp.Null):
            this, null = eq.this, eq.expression
        elif isinstance(eq.this, exp.Null):
            this, null = eq.expression, eq.this
        else:
            return eq
        return exp.Is(this=this, expression=null, negate=isinstance(eq, exp.NEQ))

    def _parse_comparison(self, this: exp.Expr | None = None) -> exp.Expr | None:
        """Parse comparison expressions with ASQL string-matching operators.

        Supports:
        - contains / icontains
        - starts with / istarts with
        - ends with / iends with
        - matches
        """
        index = self._index
        left = this or self._parse_range()

        if left and self._curr and self._curr.token_type == TokenType.VAR:

            def build_like(
                right: exp.Expr,
                *,
                wrap_left: str,
                wrap_right: str,
                case_insensitive: bool,
                written: str,
            ) -> exp.Expr:
                pattern: exp.Expr
                if isinstance(right, exp.Literal) and right.is_string:
                    pattern = exp.Literal.string(f"{wrap_left}{right.this}{wrap_right}")
                else:
                    parts: list[exp.Expr] = []
                    if wrap_left:
                        parts.append(exp.Literal.string(wrap_left))
                    parts.append(right)
                    if wrap_right:
                        parts.append(exp.Literal.string(wrap_right))
                    pattern = exp.Concat(expressions=parts) if len(parts) > 1 else right

                like_cls: type[exp.Expr] = exp.ILike if case_insensitive else exp.Like
                like = like_cls(this=left, expression=pattern)
                like.meta[STRING_OP_META] = written
                return like

            # String operators: tokens to match -> (wrap_left, wrap_right, case_insensitive)
            string_ops = {
                ("CONTAINS",): ("%", "%", False),
                ("ICONTAINS",): ("%", "%", True),
                ("STARTS", "WITH"): ("", "%", False),
                ("ISTARTS", "WITH"): ("", "%", True),
                ("ENDS", "WITH"): ("%", "", False),
                ("IENDS", "WITH"): ("%", "", True),
                ("MATCHES",): ("", "", False),  # Regex - handled specially
            }

            matched = None
            written = ""
            for tokens, config in string_ops.items():
                if self._match_text_seq(*tokens):
                    matched = config
                    written = " ".join(tokens).lower()
                    break

            if not matched:
                self._retreat(index)
                return super()._parse_comparison(this)

            wrap_left, wrap_right, case_insensitive = matched

            # Handle MATCHES specially - it's regex, not LIKE
            if wrap_left == "" and wrap_right == "" and not case_insensitive:
                # This was MATCHES - use REGEXP
                right = self._parse_range()
                if not right:
                    self.raise_error("Expected pattern after MATCHES")
                return exp.RegexpLike(this=left, expression=right)

            right = self._parse_range()
            if right is None:
                self.raise_error(
                    "Expected string literal or expression after string operator"
                )
                return super()._parse_comparison(this)
            return build_like(
                right,
                wrap_left=wrap_left,
                wrap_right=wrap_right,
                case_insensitive=case_insensitive,
                written=written,
            )

        self._retreat(index)
        return super()._parse_comparison(this)

    def _parse_assignment(self) -> exp.Expr | None:
        """Parse assignment expressions with ternary operator support.

        Ternary: `condition ? true_value : false_value` → `CASE WHEN condition THEN true_value ELSE false_value END`

        Following ClickHouse's elegant pattern - check for ? AFTER parsing expression,
        then recursively parse true/false values. Handles nested ternaries automatically.
        """
        this = super()._parse_assignment()

        if self._match(TokenType.PLACEHOLDER):  # Found ?
            return self.expression(
                exp.If(
                    this=this,
                    true=self._parse_assignment(),
                    false=self._match(TokenType.COLON) and self._parse_assignment(),
                )
            )

        return this

    def _parse_unary(self) -> exp.Expr | None:
        """Parse unary expressions with ASQL extensions.

        Extensions:
        - COUNT shorthand: `#` → `COUNT(*)`
        - COUNT shorthand: `#(col)` → `COUNT(col)`
        - Relative dates: `7 days ago` → `CURRENT_TIMESTAMP - INTERVAL '7' DAY`
        - Relative dates: `3 months from now` → `CURRENT_TIMESTAMP + INTERVAL '3' MONTH`
        - Space notation: `days since col` → `days_since(col)`
        - Space notation: `months until col` → `months_until(col)`

        Uses idiomatic SQLGlot save/retreat pattern for lookahead.

        Note: `# users` → `COUNT(DISTINCT user_id)` still handled by preparser
        because it requires table name singularization.
        """
        start_index = self._index

        parsed_multiword = self._parse_asql_multiword_unary(start_index)
        if parsed_multiword is not None:
            return parsed_multiword

        parsed_relative_date = self._parse_asql_relative_date_unary(start_index)
        if parsed_relative_date is not None:
            return parsed_relative_date

        parsed_space_date = self._parse_asql_space_notation_date_function_unary(
            start_index
        )
        if parsed_space_date is not None:
            return parsed_space_date

        parsed_natural_agg = self._parse_asql_natural_agg_unary(start_index)
        if parsed_natural_agg is not None:
            return parsed_natural_agg

        return super()._parse_unary()

    def _parse_asql_multiword_unary(self, start_index: int) -> exp.Expr | None:
        """Parse ASQL multi-word unary sugar like `day of week col` and `row number()`."""
        if self._match_text_seq("DAY", "OF", "WEEK"):
            argument = self._parse_column()
            if not argument:
                self.raise_error("Expected expression after 'day of week'")
            return exp.DayOfWeek(this=argument)

        for words, part in self._EXTRACT_PARTS.items():
            if self._match_text_seq(*words):
                argument = self._parse_column()
                if not argument:
                    self.raise_error(
                        f"Expected expression after '{' '.join(words).lower()}'"
                    )
                return exp.Extract(this=exp.var(part), expression=argument)

        row_number_index = self._index
        if self._match_text_seq("ROW", "NUMBER") and self._match(TokenType.L_PAREN):
            if not self._match(TokenType.R_PAREN):
                self.raise_error("Expected ) after row number(")
            return self._parse_window(exp.RowNumber())
        self._retreat(row_number_index)

        self._retreat(start_index)
        return None

    def _parse_asql_relative_date_unary(self, start_index: int) -> exp.Expr | None:
        """Parse relative date literals like `7 days ago` / `3 months from now`."""
        if not self._match(TokenType.NUMBER, advance=False):
            self._retreat(start_index)
            return None

        assert (
            self._curr is not None
        )  # _match(advance=False) matched: _curr is the token
        number_text = self._curr.text
        self._advance()

        if not (self._curr and self._curr.text.lower() in self.TIME_UNITS):
            self._retreat(start_index)
            return None

        unit_text = self._curr.text.lower()
        self._advance()

        now: exp.Expr = (
            exp.CurrentDate()
            if self._get_setting("relative_date_type", "timestamp") == "date"
            else exp.CurrentTimestamp()
        )
        if self._match_text_seq("AGO"):
            return exp.Sub(this=now, expression=_interval(number_text, unit_text))

        if self._match_text_seq("FROM", "NOW"):
            return exp.Add(this=now, expression=_interval(number_text, unit_text))

        self._retreat(start_index)
        return None

    def _parse_asql_space_notation_date_function_unary(
        self,
        start_index: int,
    ) -> exp.Expr | None:
        """Parse `days since col` / `months until col` → date-diff functions."""
        if not (self._curr and self._curr.token_type == TokenType.VAR):
            self._retreat(start_index)
            return None

        unit_text = self._curr.text.lower()
        if unit_text not in NATURAL_DATE_UNITS:
            self._retreat(start_index)
            return None

        self._advance()

        if not (self._curr and self._curr.token_type == TokenType.VAR):
            self._retreat(start_index)
            return None

        direction_text = self._curr.text.lower()
        if direction_text not in NATURAL_DATE_DIRECTIONS:
            self._retreat(start_index)
            return None

        self._advance()

        column_expr = self._parse_column()
        if not column_expr:
            self._retreat(start_index)
            return None

        func_name = get_natural_date_function(unit_text, direction_text)
        if not func_name:
            self._retreat(start_index)
            return None

        func_builder = ASQL_FUNCTION_REGISTRY.get(func_name)
        if not func_builder:
            self._retreat(start_index)
            return None

        return func_builder([column_expr])

    def _parse_asql_natural_agg_unary(self, start_index: int) -> exp.Expr | None:
        """Parse natural aggregates like `sum amount` / `sum of amount`."""
        if not (self._curr and self._curr.token_type == TokenType.VAR):
            self._retreat(start_index)
            return None

        func_text = self._curr.text.upper()
        func_builder = get_natural_agg(func_text)
        if not func_builder:
            self._retreat(start_index)
            return None

        self._advance()

        if self._curr and self._curr.text.lower() == "of":
            self._advance()

        if not (self._curr and self._curr.token_type == TokenType.VAR):
            self._retreat(start_index)
            return None

        next_text = self._curr.text.lower()
        sql_keywords = {
            "and",
            "as",
            "by",
            "false",
            "from",
            "group",
            "in",
            "is",
            "join",
            "limit",
            "not",
            "null",
            "on",
            "or",
            "order",
            "true",
            "where",
        }
        if next_text in sql_keywords:
            self._retreat(start_index)
            return None

        column_expr = self._parse_column()
        if not column_expr:
            self._retreat(start_index)
            return None

        return func_builder([column_expr])

    def _parse_factor(self, parse_mod: bool = True) -> exp.Expr | None:
        """Parse factor expressions with ASQL date arithmetic.

        Extensions:
        - Date arithmetic: `created_at + 7 days` → `created_at + INTERVAL '7' DAY`
        - Date arithmetic: `due_date - 1 month` → `due_date - INTERVAL '1' MONTH`

        Uses idiomatic SQLGlot save/retreat pattern for lookahead.
        """
        this = super()._parse_factor(parse_mod=parse_mod)

        # Check for date arithmetic: expr +/- NUMBER TIME_UNIT
        while self._curr:
            op_class: type[exp.Add | exp.Sub] | None = None
            if self._match(TokenType.PLUS):
                op_class = exp.Add
            elif self._match(TokenType.DASH):
                op_class = exp.Sub
            else:
                break

            # Save position after operator
            index = self._index

            # Check for NUMBER TIME_UNIT pattern
            if self._match(TokenType.NUMBER, advance=False):
                number = self._curr.text
                self._advance()

                if self._curr and self._curr.text.lower() in self.TIME_UNITS:
                    unit = self._curr.text.lower()

                    # Check next token - make sure it's not "ago" or "from now"
                    # (those are standalone relative date patterns, not date arithmetic)
                    self._advance()  # Move to check what comes after TIME_UNIT
                    if self._curr and self._curr.text.lower() in ("ago", "from"):
                        # Retreat to before operator - let _parse_unary handle it
                        self._retreat(index - 1)
                        break

                    interval = _interval(number, unit)
                    assert op_class is not None
                    this = op_class(this=this, expression=interval)
                    continue

            # Not a date arithmetic pattern, retreat and let normal parsing handle it
            self._retreat(index - 1)  # Back to before operator
            break

        return this

    def _parse_date_literal(self) -> exp.Expr | None:
        """Parse @ date literal.

        @2024-01-15 → exp.Date(this='2024-01-15')
        @2024-01-15T10:30:00 → exp.Timestamp(this='2024-01-15 10:30:00')

        Following DuckDB's PLACEHOLDER_PARSERS pattern.
        """
        # Check if we have a date pattern: NUMBER - NUMBER - NUMBER
        if not self._match(TokenType.NUMBER, advance=False):
            return None

        index = self._index

        # Parse year
        if not self._curr or not self._curr.text.isdigit():
            return None
        year = self._curr.text
        if len(year) != 4:
            return None  # Not a 4-digit year
        self._advance()

        # Parse first dash
        if not self._match(TokenType.DASH):
            self._retreat(index)
            return None

        # Parse month
        if not self._match(TokenType.NUMBER, advance=False):
            self._retreat(index)
            return None
        month = self._curr.text
        self._advance()

        # Parse second dash
        if not self._match(TokenType.DASH):
            self._retreat(index)
            return None

        # Parse day
        if not self._match(TokenType.NUMBER, advance=False):
            self._retreat(index)
            return None
        day = self._curr.text
        self._advance()

        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        # Check for timestamp: T followed by time
        # Tokenizer combines T with the hour: "T10" becomes VAR 'T10'
        if self._curr and self._curr.token_type == TokenType.VAR:
            var_text = self._curr.text.upper()
            if var_text.startswith("T") and var_text[1:].isdigit():
                hour = var_text[1:]  # Extract hour from T10 → 10
                self._advance()  # Consume T10

                # Parse :MM:SS
                if self._match(TokenType.COLON):
                    if self._match(TokenType.NUMBER, advance=False):
                        minute = self._curr.text
                        self._advance()

                        if self._match(TokenType.COLON):
                            if self._match(TokenType.NUMBER, advance=False):
                                second = self._curr.text
                                self._advance()

                                time_str = f"{hour.zfill(2)}:{minute.zfill(2)}:{second.zfill(2)}"
                                return exp.Timestamp(
                                    this=exp.Literal.string(f"{date_str} {time_str}")
                                )

        # Just a date
        return exp.Date(this=exp.Literal.string(date_str))

    def _parse_asql_recurse(self, query: exp.Query) -> exp.Query:
        """Parse recurse(fk_column [, max_depth]) for recursive CTEs.

        Syntax:
            from employees where id = 1 recurse(manager_id)
            from employees where id = 1 recurse(manager_id, 5)

        Generates a WITH RECURSIVE CTE for hierarchical traversal.
        """
        # Expect ( after RECURSE
        if not self._match(TokenType.L_PAREN):
            self.raise_error("Expected ( after RECURSE")
            return query

        # Parse FK column
        fk_column = self._parse_column()
        if not fk_column:
            self.raise_error("Expected FK column name in RECURSE")
            return query

        fk_col_name = fk_column.name

        # Optional max depth
        max_depth = 100  # Default
        if self._match(TokenType.COMMA):
            if self._match(TokenType.NUMBER, advance=False):
                assert (
                    self._curr is not None
                )  # _match(advance=False) matched: _curr is the token
                max_depth = int(self._curr.text)
                self._advance()

        if not self._match(TokenType.R_PAREN):
            self.raise_error("Expected ) after RECURSE arguments")
            return query

        # Extract table name and WHERE condition from the query
        from_clause = query.find(exp.From)
        if not from_clause:
            self.raise_error("RECURSE requires a FROM clause")
            return query

        table_expr = from_clause.this
        if isinstance(table_expr, exp.Table):
            table_name = table_expr.name
        else:
            self.raise_error("RECURSE requires a simple table name")
            return query

        # Get the WHERE condition (anchor) - use AST directly
        where_clause = query.find(exp.Where)
        anchor_condition = (
            where_clause.this.copy()
            if where_clause
            else exp.EQ(this=exp.Literal.number(1), expression=exp.Literal.number(1))
        )

        cte_name = f"_recurse_{table_name}"
        table_alias = table_name[0].lower()

        # Build anchor query using AST: SELECT *, 1 AS _level FROM table WHERE ...
        anchor_query = (
            exp.select(
                exp.Star(), exp.Alias(this=exp.Literal.number(1), alias="_level")
            )
            .from_(table_name, copy=False)
            .where(anchor_condition, copy=False)
        )

        # Build recursive query using AST
        recursive_query = (
            exp.select(
                exp.Column(this=exp.Star(), table=table_alias),
                exp.Add(
                    this=exp.Column(this=exp.to_identifier("_level"), table=cte_name),
                    expression=exp.Literal.number(1),
                ),
            )
            .from_(
                exp.Table(
                    this=exp.to_identifier(table_name),
                    alias=exp.TableAlias(this=exp.to_identifier(table_alias)),
                ),
                copy=False,
            )
            .join(
                cte_name,
                on=exp.EQ(
                    this=exp.Column(
                        this=exp.to_identifier(fk_col_name), table=table_alias
                    ),
                    expression=exp.Column(this=exp.to_identifier("id"), table=cte_name),
                ),
                copy=False,
            )
            .where(
                exp.LT(
                    this=exp.Column(this=exp.to_identifier("_level"), table=cte_name),
                    expression=exp.Literal.number(max_depth),
                ),
                copy=False,
            )
        )

        # Combine with UNION ALL
        cte_body = exp.Union(
            this=anchor_query, expression=recursive_query, distinct=False
        )
        cte_expr = exp.CTE(
            this=cte_body, alias=exp.TableAlias(this=exp.to_identifier(cte_name))
        )

        # Final query: SELECT * FROM cte_name
        new_query = exp.select("*").from_(cte_name, copy=False)
        new_query.set("with_", exp.With(expressions=[cte_expr], recursive=True))

        return new_query
