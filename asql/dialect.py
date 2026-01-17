"""ASQL dialect implementation using SQLGlot's TRANSFORM_PARSERS pattern.

ASQL (Analytic SQL) is a human-readable, pipeline-based query language that
transpiles to SQL. This dialect implements the core ASQL parsing using SQLGlot's
built-in infrastructure.

Key features:
- FROM-first syntax: `from users where status = 'active'`
- Pipeline operators: `from users | where x | group by y`
- Descending order shorthand: `-column` → `column DESC`
- Proper pipeline semantics: `group by X | where Y` → CTE + WHERE
"""

from __future__ import annotations

import typing as t

import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import Dialect
from sqlglot.generator import Generator
from sqlglot.helper import seq_get
from sqlglot.parser import Parser
from sqlglot.tokens import Token, Tokenizer, TokenType

from asql.functions import (
    ASQL_FUNCTION_REGISTRY,
    NATURAL_DATE_UNITS,
    NATURAL_DATE_DIRECTIONS,
    get_natural_date_function,
    get_natural_agg,
    _build_bucket,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
# Module-level helpers following SQLGlot/PRQL patterns.
# =============================================================================

def _select_all(table: exp.Expression) -> t.Optional[exp.Select]:
    """Create SELECT * FROM table expression.
    
    PRQL pattern for cleanly building initial queries from FROM clauses.
    """
    return exp.select("*").from_(table, copy=False) if table else None


class ASQLTokenizer(Tokenizer):
    """Tokenizer for ASQL syntax.
    
    Key mappings:
    - `|` → PIPE_GT to reuse SQLGlot's pipe syntax infrastructure
    - `#` → HASH for COUNT() shorthand
    - `&` → AMP for INNER JOIN
    - `&?` → QMARK_AMP for LEFT JOIN
    - `?&` → QMARK_AMP for RIGHT JOIN (differentiated by text)
    - `?&?` → uses PLACEHOLDER token (differentiated by text)
    - `*` → STAR for CROSS JOIN (context-dependent)
    
    String handling:
    - Single quotes (') are string literals (SQL standard)
    - Double quotes (") are string literals (ASQL accepts both)
    - Backticks (`) are identifiers (for column/table names with special chars)
    """
    
    IDENTIFIERS = ["`"]  # Only backticks for identifiers
    QUOTES = ["'", '"']  # Both ' and " for strings
    
    SINGLE_TOKENS = {
        **Tokenizer.SINGLE_TOKENS,
        "|": TokenType.PIPE_GT,  # Map | to |> to reuse BigQuery's pipe infrastructure
        "#": TokenType.HASH,     # For COUNT(*) shorthand
    }
    
    KEYWORDS = {
        **Tokenizer.KEYWORDS,
        # ASQL-specific keywords
        "STASH": TokenType.VAR,
        "PER": TokenType.VAR,
        "EXTEND": TokenType.VAR,
        "RECURSE": TokenType.VAR,  # For recursive CTEs
        
        # Natural language alternatives
        "OTHERWISE": TokenType.ELSE,  # Alias for ELSE in when expressions
        
        # Join operators (multi-char tokens)
        "?&?": TokenType.PLACEHOLDER,  # FULL OUTER JOIN
        "&?": TokenType.QMARK_AMP,     # LEFT JOIN
        "?&": TokenType.QMARK_AMP,     # RIGHT JOIN
    }


class ASQLParser(Parser):
    # Transform keywords that should not be treated as table aliases
    _TRANSFORM_KEYWORDS = frozenset({
        "PER", "STASH", "EXTEND", "EXPLODE", "SAMPLE",
        "RENAME", "REPLACE", "DEDUPLICATE", "NUMBER", "RANK", "DENSE", "COHORT",
        "RECURSE",
    })
    
    # Token types that are join operators (should not be parsed as table aliases)
    _JOIN_OPERATOR_TOKENS = frozenset({
        TokenType.AMP,        # &
        TokenType.QMARK_AMP,  # &? or ?&
        TokenType.PLACEHOLDER,  # ?&? (when text is ?&?)
        TokenType.STAR,       # * for CROSS JOIN
    })
    
    def _parse_table_alias(
        self, alias_tokens: t.Optional[t.Collection[TokenType]] = None
    ) -> t.Optional[exp.TableAlias]:
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
    
    def _match_text_seq(
        self,
        *texts: str,
        advance: bool = True,
    ) -> bool:
        """Override to prevent * from being consumed as Postgres wildcard suffix.
        
        SQLGlot's base _parse_table has: self._match_text_seq("*")
        which consumes * after table names (Postgres feature).
        
        In ASQL, * is a CROSS JOIN operator, so we need to prevent this consumption.
        """
        # If we're trying to match just "*", check if it's followed by a table name
        # which would indicate it's a CROSS JOIN operator, not Postgres wildcard
        if texts == ("*",) and self._curr and self._curr.token_type == TokenType.STAR:
            # Check if next token is a table name (VAR)
            next_tok = self._next
            if next_tok and next_tok.token_type == TokenType.VAR:
                # This is likely a CROSS JOIN, don't consume
                return False
        
        return super()._match_text_seq(*texts, advance=advance)
    
    def _parse_alias(
        self, this: t.Optional[exp.Expression], explicit: bool = False
    ) -> t.Optional[exp.Expression]:
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
    def _apply_star_column_override(select_expressions: t.List[exp.Expression]) -> None:
        """
        Apply ASQL's "star override" behavior:

            select *, upper(name) as name

        becomes an AST equivalent of:

            select * EXCEPT(name), upper(name) as name

        so explicit aliases replace columns from the star expansion instead of duplicating them.
        """
        if not select_expressions:
            return

        star_expr: t.Optional[exp.Star] = None
        for select_expression in select_expressions:
            if isinstance(select_expression, exp.Star):
                star_expr = select_expression
                break

        if not star_expr:
            return

        except_names: t.List[str] = []
        for select_expression in select_expressions:
            alias = select_expression.alias
            if alias:
                except_names.append(alias)

        if not except_names:
            return

        star_expr.set(
            "except_",
            [exp.Column(this=exp.to_identifier(name)) for name in except_names],
        )

    def parse_set_operation(
        self, this: t.Optional[exp.Expression], consume_pipe: bool = False
    ) -> t.Optional[exp.Expression]:
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

        token_type = self._prev.token_type

        if token_type == TokenType.UNION:
            operation: t.Type[exp.SetOperation] = exp.Union
        elif token_type == TokenType.EXCEPT:
            operation = exp.Except
        else:
            operation = exp.Intersect

        comments = self._prev.comments

        if self._match(TokenType.DISTINCT):
            distinct: t.Optional[bool] = True
        elif self._match(TokenType.ALL):
            distinct = False
        else:
            distinct = self.dialect.SET_OP_DISTINCT_BY_DEFAULT[operation]
            if distinct is None:
                self.raise_error(f"Expected DISTINCT or ALL for {operation.__name__}")

        by_name = self._match_text_seq("BY", "NAME") or self._match_text_seq("STRICT", "CORRESPONDING")
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
            operation,
            comments=comments,
            this=this,
            distinct=distinct,
            by_name=by_name,
            expression=expression,
            side=side,
            kind=kind,
            on=on_column_list,
        )
    """Parser for ASQL pipeline syntax using TRANSFORM_PARSERS pattern.
    
    This follows PRQL's pattern:
    1. Start with FROM clause
    2. Build initial SELECT * FROM table
    3. Apply transforms (WHERE, GROUP BY, etc.) in sequence
    4. Use _build_pipe_cte() when transforms require CTE wrapping
    """
    
    # Time unit keywords for date expressions
    TIME_UNITS = frozenset({
        'day', 'days', 'week', 'weeks', 'month', 'months', 
        'year', 'years', 'hour', 'hours', 'minute', 'minutes', 
        'second', 'seconds'
    })
    
    # Use && for AND (like PRQL)
    CONJUNCTION = {
        **Parser.CONJUNCTION,
        TokenType.DAMP: exp.And,
    }
    
    # ASQL uses || for string concatenation (not OR)
    # DPIPE_IS_STRING_CONCAT handles this at dialect level
    
    # Pop PLACEHOLDER from COLUMN_OPERATORS to enable ternary ? : parsing
    # (Following ClickHouse's canonical copy-and-pop pattern)
    COLUMN_OPERATORS = Parser.COLUMN_OPERATORS.copy()
    COLUMN_OPERATORS.pop(TokenType.PLACEHOLDER)
    
    # Handle @ as date literal prefix (following DuckDB's PLACEHOLDER_PARSERS pattern)
    # @2024-01-15 → DATE '2024-01-15'
    # @2024-01-15T10:30:00 → TIMESTAMP '2024-01-15 10:30:00'
    PLACEHOLDER_PARSERS = Parser.PLACEHOLDER_PARSERS.copy()
    PLACEHOLDER_PARSERS[TokenType.PARAMETER] = lambda self: self._parse_date_literal()

    # Custom function parsers (bypass sqlglot's validate_expression arg count checks)
    # Needed for BUCKET(..., start=..., end=..., width=...) which has 4 args but returns a CASE.
    FUNCTION_PARSERS = Parser.FUNCTION_PARSERS.copy()
    FUNCTION_PARSERS.update(
        {
            "BUCKET": lambda self: self._parse_bucket(),
            "KEY": lambda self: self._parse_key(),
            "SLUGIFY": lambda self: self._parse_slugify(),
            # Window-ish helpers (ported out of preparser window transforms)
            "LAST": lambda self: self._parse_last_ordered(),
            "ARG_MAX": lambda self: self._parse_arg_max_min(is_max=True),
            "ARG_MIN": lambda self: self._parse_arg_max_min(is_max=False),
        }
    )
    
    # NO_PAREN_FUNCTION_PARSERS: Keywords that start expressions without parentheses
    # Note: WHEN handling is done in _parse_field override to avoid conflicts
    # with SQL CASE WHEN syntax
    NO_PAREN_FUNCTION_PARSERS = Parser.NO_PAREN_FUNCTION_PARSERS.copy()
    
    # PRIMARY_PARSERS: Handlers for tokens that start primary expressions
    # Used for # count shorthand
    PRIMARY_PARSERS = Parser.PRIMARY_PARSERS.copy()
    PRIMARY_PARSERS[TokenType.HASH] = lambda self, token: self._parse_count_shorthand_from_primary()
    
    # Override PIPE_SYNTAX_TRANSFORM_PARSERS to add GROUP BY support
    # This extends SQLGlot's BigQuery-style pipe syntax
    PIPE_SYNTAX_TRANSFORM_PARSERS = Parser.PIPE_SYNTAX_TRANSFORM_PARSERS.copy()
    PIPE_SYNTAX_TRANSFORM_PARSERS.update(
        {
            "GROUP BY": lambda self, query: self._parse_asql_pipe_group_by(query),
            "HAVING": lambda self, query: query.having(self._parse_assignment(), copy=False),
            "QUALIFY": lambda self, query: query.qualify(self._parse_assignment(), copy=False),
        }
    )
    
    # Transform parsers for FROM-first pipeline operations
    # These handle the transformation keywords that come after FROM (not using |>)
    TRANSFORM_PARSERS = {
        # Filtering (WHERE aliases)
        **dict.fromkeys(
            ("WHERE", "FILTER", "IF"),
            lambda self, query: self._parse_asql_where(query)
        ),
        # Selection
        "SELECT": lambda self, query: self._parse_asql_select(query),
        # Core transforms
        "LIMIT": lambda self, query: query.limit(self._parse_limit(skip_limit_token=True), copy=False),
        "ORDER BY": lambda self, query: self._parse_asql_order_by(query),
        "GROUP BY": lambda self, query: self._parse_asql_group_by(query),
        "HAVING": lambda self, query: query.having(self._parse_assignment(), copy=False),
        "QUALIFY": lambda self, query: query.qualify(self._parse_assignment(), copy=False),
        "EXTEND": lambda self, query: self._parse_asql_extend(query),
        "EXPLODE": lambda self, query: self._parse_asql_explode(query),
        "STASH": lambda self, query: self._parse_asql_stash(query),
        # Standard SQL joins
        "JOIN": lambda self, query: self._parse_asql_join(query, kind="INNER"),
        "LEFT": lambda self, query: self._parse_join_kind(query, "LEFT", ("JOIN", "OUTER JOIN")),
        "RIGHT": lambda self, query: self._parse_join_kind(query, "RIGHT", ("JOIN", "OUTER JOIN")),
        "FULL": lambda self, query: self._parse_join_kind(query, "FULL OUTER", ("OUTER", "JOIN")),
        "CROSS": lambda self, query: self._parse_join_kind(query, "CROSS", ("JOIN",)),
        # ASQL symbolic join operators (& &? ?& ?&? *)
        "ASQL_INNER_JOIN": lambda self, query: self._parse_asql_join(query, kind="INNER"),
        "ASQL_QMARK_JOIN": lambda self, query: self._parse_asql_qmark_join(query),
        "ASQL_FULL_JOIN": lambda self, query: self._parse_asql_join(query, kind="FULL OUTER"),
        "ASQL_CROSS_JOIN": lambda self, query: self._parse_asql_join(query, kind="CROSS"),
        # Column operations
        "DISTINCT": lambda self, query: self._parse_asql_distinct(query),
        "EXCEPT": lambda self, query: self._parse_asql_except(query),
        "RENAME": lambda self, query: self._parse_asql_rename(query),
        "REPLACE": lambda self, query: self._parse_asql_replace(query),
        "SAMPLE": lambda self, query: self._parse_asql_sample(query),
        # Window/ranking operations
        "PER": lambda self, query: self._parse_asql_per(query),
        "NUMBER": lambda self, query: self._parse_asql_standalone_rank(query, exp.RowNumber, "row_num"),
        "RANK": lambda self, query: self._parse_asql_standalone_rank(query, exp.Rank, "rank"),
        "DENSE": lambda self, query: self._parse_asql_dense_rank_standalone(query),
        "DEDUPLICATE": lambda self, query: self._parse_asql_deduplicate(query),
        # Advanced transforms
        "COHORT": lambda self, query: self._parse_asql_cohort(query),
        "RECURSE": lambda self, query: self._parse_asql_recurse(query),
    }
    
    # Single-word transforms for efficient _match_texts lookup
    # (Multi-word transforms like "GROUP BY" are tokenized as single tokens)
    _SINGLE_WORD_TRANSFORMS = frozenset(k for k in TRANSFORM_PARSERS if " " not in k)

    # Token-type based transform starters (these are tokenized as keywords, not VAR).
    _TOKEN_TRANSFORMS: dict[TokenType, str] = {
        TokenType.WHERE: "WHERE",
        TokenType.SELECT: "SELECT",
        TokenType.LIMIT: "LIMIT",
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
        TokenType.AMP: "ASQL_INNER_JOIN",      # & → INNER JOIN
        TokenType.QMARK_AMP: "ASQL_QMARK_JOIN", # &? or ?& → LEFT/RIGHT JOIN
        TokenType.PLACEHOLDER: "ASQL_FULL_JOIN", # ?&? → FULL OUTER JOIN (checked in _match_transform)
        TokenType.STAR: "ASQL_CROSS_JOIN",     # * → CROSS JOIN
    }

    # Function aliases for natural language
    FUNCTIONS = {
        **Parser.FUNCTIONS,
        # Include all functions from the shared registry
        **ASQL_FUNCTION_REGISTRY,
        # Additional aliases
        "TOTAL": exp.Sum.from_arg_list,
        "AVERAGE": exp.Avg.from_arg_list,
        "PRIOR": lambda args: exp.Lag(this=seq_get(args, 0), offset=seq_get(args, 1) or exp.Literal.number(1)),
        "NEXT": lambda args: exp.Lead(this=seq_get(args, 0), offset=seq_get(args, 1) or exp.Literal.number(1)),
    }

    def _parse_pivot(self) -> t.Optional[exp.Pivot]:
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
    
    def _parse_asql_pivot_syntax(self) -> t.Optional[exp.Pivot]:
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
        
        # Check for optional 'values' clause
        values: t.List[exp.Expression] = []
        if self._match_text_seq("VALUES"):
            self._match_l_paren()
            values = self._parse_csv(self._parse_primary)
            self._match_r_paren()
        
        # Ensure agg_expr is wrapped in an aggregate function if it's just a column
        if isinstance(agg_expr, exp.Column):
            agg_expr = exp.Sum(this=agg_expr)
        
        # Build the Pivot expression matching SQLGlot's structure
        return self.expression(
            exp.Pivot,
            expressions=[agg_expr],
            fields=[exp.In(this=pivot_col, expressions=values)] if values else [pivot_col],
            unpivot=False,
        )
    
    def _parse_asql_unpivot_syntax(self) -> t.Optional[exp.Pivot]:
        """Parse ASQL's simplified unpivot syntax: unpivot col1, col2, ... into name, value"""
        # Parse column list until we hit 'into'
        columns: t.List[exp.Expression] = []
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
            exp.Pivot,
            expressions=[value_col],  # Value column
            fields=[exp.In(this=name_col, expressions=columns)],  # FOR name IN (columns)
            unpivot=True,
        )

    def _parse_bucket(self) -> exp.Expression:
        """Parse bucket(...) and return a CASE expression.

        Implemented via FUNCTION_PARSERS to avoid sqlglot validate_expression() arg-count checks,
        since BUCKET can accept keyword args (start/end/width) and returns an exp.Case.
        """
        args = self._parse_function_args(alias=True)
        return _build_bucket(args)

    def _parse_key(self) -> exp.Expression:
        """Parse key(col1, col2, ...) into a stable surrogate key hash.

        Implemented via FUNCTION_PARSERS because key() is variadic but compiles to MD5(CONCAT(...)),
        which would otherwise fail sqlglot's validate_expression() (arg count mismatch).
        """
        args = self._parse_function_args(alias=True)
        if not args:
            return exp.Anonymous(this="key", expressions=args)

        coalesced: list[exp.Expression] = []
        for arg in args:
            cast = exp.Cast(this=arg, to=exp.DataType.build("VARCHAR", dialect=self.dialect))
            coalesced.append(exp.Coalesce(this=cast, expressions=[exp.Literal.string("")]))

        concat_parts: list[exp.Expression] = []
        for i, arg in enumerate(coalesced):
            if i:
                concat_parts.append(exp.Literal.string("||"))
            concat_parts.append(arg)

        concat = exp.Concat(expressions=concat_parts)
        return exp.MD5(this=concat)

    def _parse_slugify(self) -> exp.Expression:
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
        return exp.Trim(this=replaced, expression=exp.Literal.string("-"), position="BOTH")

    def _parse_field(
        self,
        any_token: bool = False,
        tokens: t.Optional[t.Collection[TokenType]] = None,
        anonymous_func: bool = False,
    ) -> t.Optional[exp.Expression]:
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
            and (self._prev is None or self._prev.token_type != TokenType.CASE)
        ):
            self._advance()  # consume WHEN
            return self._parse_when()
        
        # Handle # count shorthand
        if self._curr and self._curr.token_type == TokenType.HASH:
            return self._parse_count_shorthand()

        # FIRST(<expr> ORDER BY ...) should compile to FIRST_VALUE(...) OVER (ORDER BY ...)
        if self._curr and self._curr.token_type == TokenType.FIRST:
            index = self._index
            self._advance()  # consume FIRST
            if self._match(TokenType.L_PAREN):
                return self._parse_first_ordered()
            self._retreat(index)
        
        # Fall back to default field parsing
        return super()._parse_field(any_token=any_token, tokens=tokens, anonymous_func=anonymous_func)

    def _parse_first_ordered(self) -> exp.Expression:
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

    def _parse_count_shorthand_from_primary(self) -> exp.Expression:
        """Parse ASQL # count shorthand (called after # is consumed).
        
        Syntax:
            # → COUNT(*)
            #* or # * → COUNT(*)
            #(col) → COUNT(col)
            #(distinct col) → COUNT(DISTINCT col)
            # users → COUNT(DISTINCT user_id)
            # of users → COUNT(DISTINCT user_id)
        """
        # #* → COUNT(*)
        if self._match(TokenType.STAR):
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
        
        # # of <table> → COUNT(DISTINCT <table>_id)
        if self._curr and self._curr.token_type == TokenType.VAR and self._curr.text.upper() == "OF":
            self._advance()  # consume 'of'
            if self._curr and self._curr.token_type == TokenType.VAR:
                table_name = self._curr.text
                self._advance()
                pk_col = self._infer_primary_key_column(table_name)
                return exp.Count(
                    this=exp.Distinct(expressions=[exp.Column(this=exp.to_identifier(pk_col))])
                )
        
        # # <table> → COUNT(DISTINCT <table>_id)
        if self._curr and self._curr.token_type == TokenType.VAR:
            # Check if this is a SQL keyword that should trigger standalone # → COUNT(*)
            sql_keywords = {
                'as', 'from', 'where', 'group', 'by', 'order', 'limit', 'having',
                'select', 'join', 'on', 'and', 'or', 'not', 'in', 'is', 'null',
                'true', 'false', 'union', 'except', 'intersect', 'with', 'stash'
            }
            if self._curr.text.lower() not in sql_keywords:
                table_name = self._curr.text
                self._advance()
                pk_col = self._infer_primary_key_column(table_name)
                return exp.Count(
                    this=exp.Distinct(expressions=[exp.Column(this=exp.to_identifier(pk_col))])
                )
        
        # Standalone # → COUNT(*)
        return exp.Count(this=exp.Star())
    
    def _parse_count_shorthand(self) -> exp.Expression:
        """Parse ASQL # count shorthand (called from _parse_field).
        
        This consumes the # token first, then delegates to the main implementation.
        """
        if self._curr and self._curr.token_type == TokenType.HASH:
            self._advance()  # consume #
        return self._parse_count_shorthand_from_primary()

    def _infer_primary_key_column(self, table_name: str) -> str:
        """Infer PK column name from table name: users → user_id."""
        table_lower = table_name.lower()
        if table_lower.endswith('s') and len(table_lower) > 1:
            singular = table_lower[:-1]
        else:
            singular = table_lower
        return f"{singular}_id"

    def _parse_last_ordered(self) -> exp.Expression:
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

        flipped: list[exp.Ordered] = []
        for ordered in order_expressions:
            if isinstance(ordered, exp.Ordered):
                # Flip the sort direction: ASC <-> DESC
                ordered.set("desc", not bool(ordered.args.get("desc")))
            flipped.append(ordered)

        order = exp.Order(expressions=flipped)
        return exp.Window(this=exp.FirstValue(this=value), order=order)

    def _parse_arg_max_min(self, is_max: bool) -> exp.Expression:
        """Parse arg_max(value, key) / arg_min(value, key) into FIRST_VALUE(value) OVER (ORDER BY key ...)."""
        args = self._parse_function_args(alias=True)
        value = seq_get(args, 0)
        key = seq_get(args, 1)
        if not value or not key:
            return exp.Anonymous(this="arg_max" if is_max else "arg_min", expressions=args)

        ordered = exp.Ordered(this=key, desc=is_max)
        order = exp.Order(expressions=[ordered])
        return exp.Window(this=exp.FirstValue(this=value), order=order)

    def _parse_when(self) -> exp.Expression:
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
        default: t.Optional[exp.Expression] = None
        base_expr: t.Optional[exp.Expression] = None

        # Parse first branch to detect simple vs searched case
        # Simple case pattern: `when <column> is/</>/in <value> then <result>`
        # Searched case pattern: `when <full_condition> then <result>`
        
        # We need to parse carefully to distinguish:
        # - `when status is "active" then 1` (simple case, base_expr = status)
        # - `when age < 18 then "Minor"` (could be simple OR searched)
        # - `when age < 18 and x then "y"` (searched case)
        
        # Strategy: Parse a column/id, then check what follows
        if self._match_set(self.ID_VAR_TOKENS):
            # Got a potential base expression (identifier)
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
            elif self._match_set({TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE, TokenType.EQ, TokenType.NEQ}):
                # Comparison operator - could be simple case OR searched case with AND/OR
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

    def _parse_when_result(self) -> t.Optional[exp.Expression]:
        """Parse the result part of a when branch, stopping at comma/else/otherwise."""
        # Parse expression but stop at COMMA or ELSE (otherwise is tokenized as ELSE)
        return self._parse_unary()

    def _parse_when_branch(self, base_expr: t.Optional[exp.Expression]) -> t.Optional[exp.If]:
        """Parse a single when branch: <condition> then <result>."""
        condition: t.Optional[exp.Expression] = None

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
            elif self._match_set({TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE, TokenType.EQ, TokenType.NEQ}):
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

    def _build_comparison(
        self, left: exp.Expression, op_token: TokenType, right: exp.Expression
    ) -> exp.Expression:
        """Build a comparison expression from operator token using dialect schema."""
        from asql.dialect_schema import OPERATORS

        # Build lookup dict from OPERATORS schema (comparison + equality)
        operator_map = {}
        for cls in [OPERATORS.COMPARISON, OPERATORS.EQUALITY]:
            for attr_name in dir(cls):
                if not attr_name.startswith('_'):
                    op = getattr(cls, attr_name)
                    if hasattr(op, 'token') and hasattr(op, 'expr_class'):
                        operator_map[op.token] = op.expr_class

        # Look up operator, default to EQ if not found
        expr_class = operator_map.get(op_token, exp.EQ)
        return expr_class(this=left, expression=right)

    def _parse_bracket(self, this: t.Optional[exp.Expression] = None) -> t.Optional[exp.Expression]:
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
                except Exception:
                    start_num = None
            elif isinstance(start, exp.Neg) and isinstance(start.this, exp.Literal) and start.this.is_number:
                try:
                    start_num = -int(start.this.to_py())
                except Exception:
                    start_num = None

            if start_num is not None and start_num < 0:
                return exp.Right(this=base, expression=exp.Literal.number(str(-start_num)))
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
                    return exp.Substring(this=base, start=start, length=exp.Literal.number(str(length_num)))
                except Exception:
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
                if tok.token_type == TokenType.FOR or (tok.token_type == TokenType.VAR and tok.text.upper() == "FOR"):
                    found_for = True
                elif found_for and (tok.token_type == TokenType.IN or (tok.token_type == TokenType.VAR and tok.text.upper() == "IN")):
                    found_in = True
                    break
            
            i += 1
        
        return found_for and found_in

    def _parse_list_comprehension(self) -> exp.Expression:
        """Parse Python-style list comprehension: [expr for var in arr [if condition]]
        
        Converts to: ARRAY(SELECT expr FROM UNNEST(arr) AS var [WHERE condition])
        """
        self._advance()  # consume [
        
        # Parse everything up to 'for'
        expr_tokens: list[Token] = []
        bracket_depth = 1
        
        while self._curr:
            if self._curr.token_type == TokenType.L_BRACKET:
                bracket_depth += 1
                expr_tokens.append(self._curr)
                self._advance()
            elif self._curr.token_type == TokenType.R_BRACKET:
                bracket_depth -= 1
                if bracket_depth == 0:
                    break
                expr_tokens.append(self._curr)
                self._advance()
            elif bracket_depth == 1 and (self._curr.token_type == TokenType.FOR or (self._curr.token_type == TokenType.VAR and self._curr.text.upper() == "FOR")):
                break
            else:
                expr_tokens.append(self._curr)
                self._advance()
        
        # Build expression string for parsing
        expr_str = " ".join(t.text for t in expr_tokens).strip()
        
        # Expect 'for'
        if not (self._curr and (self._curr.token_type == TokenType.FOR or (self._curr.token_type == TokenType.VAR and self._curr.text.upper() == "FOR"))):
            self.raise_error("Expected 'for' in list comprehension")
            return exp.Array(expressions=[])
        self._advance()  # consume 'for'
        
        # Parse variable name
        var_name = self._parse_id_var()
        if not var_name:
            self.raise_error("Expected variable name in list comprehension")
            return exp.Array(expressions=[])
        
        # Expect 'in'
        if not (self._curr and (self._curr.token_type == TokenType.IN or (self._curr.token_type == TokenType.VAR and self._curr.text.upper() == "IN"))):
            self.raise_error("Expected 'in' in list comprehension")
            return exp.Array(expressions=[])
        self._advance()  # consume 'in'
        
        # Parse array expression (column name or more complex expression)
        array_expr = self._parse_column()
        if not array_expr:
            self.raise_error("Expected array expression in list comprehension")
            return exp.Array(expressions=[])
        
        # Check for optional 'if' condition
        condition_expr: t.Optional[exp.Expression] = None
        if self._curr and self._curr.token_type == TokenType.VAR and self._curr.text.upper() == "IF":
            self._advance()  # consume 'if'
            # Parse condition up to ]
            cond_tokens: list[Token] = []
            while self._curr and self._curr.token_type != TokenType.R_BRACKET:
                cond_tokens.append(self._curr)
                self._advance()
            if cond_tokens:
                cond_str = " ".join(t.text for t in cond_tokens).strip()
                try:
                    condition_expr = sqlglot.parse_one(cond_str, dialect="asql")
                except Exception:
                    try:
                        condition_expr = sqlglot.parse_one(cond_str)
                    except Exception:
                        pass
        
        # Expect ]
        if not self._match(TokenType.R_BRACKET):
            self.raise_error("Expected ']' at end of list comprehension")
        
        # Parse the expression string
        try:
            select_expr = sqlglot.parse_one(expr_str, dialect="asql")
        except Exception:
            try:
                select_expr = sqlglot.parse_one(expr_str)
            except Exception:
                select_expr = exp.Column(this=exp.Identifier(this=expr_str))
        
        # Build ARRAY(SELECT expr FROM UNNEST(arr) AS var [WHERE condition])
        unnest = exp.Unnest(
            expressions=[array_expr],
            alias=exp.TableAlias(this=exp.to_identifier(var_name.name if hasattr(var_name, 'name') else str(var_name)))
        )
        
        select = exp.Select(
            expressions=[select_expr],
            from_=exp.From(this=unnest),
        )
        
        if condition_expr:
            select.set("where", exp.Where(this=condition_expr))
        
        return exp.Array(expressions=[select])

    def _match_transform(self) -> t.Optional[str]:
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
            return self._prev.text.upper()
        
        return None

    def _parse_statement(self) -> t.Optional[exp.Expression]:
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

    def _find_trailing_stash_index(self) -> t.Optional[int]:
        """Find a top-level trailing-transform token index for SELECT-first queries.
        
        These keywords can appear after SELECT-first queries (converted from FROM-first
        by the preparser) and need special handling.
        """
        depth = 0
        i = self._index
        # Keywords that can appear as trailing transforms after SELECT-first queries
        trailing_keywords = {"STASH", "COHORT", "EXCEPT", "RENAME", "REPLACE"}
        
        while i < len(self._tokens):
            tok = self._tokens[i]

            if tok.token_type in (TokenType.L_PAREN, TokenType.L_BRACKET, TokenType.L_BRACE):
                depth += 1
            elif tok.token_type in (TokenType.R_PAREN, TokenType.R_BRACKET, TokenType.R_BRACE):
                depth = max(depth - 1, 0)

            if depth == 0 and tok.text.upper() in trailing_keywords:
                # Avoid treating set-operation EXCEPT as a trailing transform:
                #   SELECT ... EXCEPT SELECT ...
                if tok.token_type == TokenType.EXCEPT:
                    next_tok = self._tokens[i + 1] if i + 1 < len(self._tokens) else None
                    if next_tok and next_tok.token_type == TokenType.SELECT:
                        i += 1
                        continue
                return i

            i += 1

        return None

    def _parse_asql_trailing_transforms(self, query: exp.Query) -> exp.Query:
        """Parse ASQL pipeline transforms that appear after an already-parsed query."""
        seen_group_by = bool(query.args.get("group"))

        while True:
            self._match(TokenType.PIPE_GT)

            transform_name = self._match_transform()
            if not transform_name:
                break

            if seen_group_by and transform_name in ("WHERE", "FILTER", "IF"):
                query = self._build_pipe_cte(query, [exp.Star()])

            query = self.TRANSFORM_PARSERS[transform_name](self, query)

            if transform_name == "GROUP BY":
                seen_group_by = True

        return query

    def _parse_query(
        self, 
        nested: bool = False,
        parse_subquery_alias: bool = True,
        parse_set_operation: bool = True,
    ) -> t.Optional[exp.Query]:
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
        query = _select_all(from_.this)
        
        # Transfer comments from FROM clause to SELECT (preserves leading comments)
        if from_.comments:
            query.comments = from_.comments
        
        if with_:
            query.set("with_", with_)
        
        # Track if we've seen a GROUP BY (for CTE wrapping logic)
        seen_group_by = False
        
        # Apply transforms in sequence
        while True:
            # Skip pipe operators
            self._match(TokenType.PIPE_GT)
            
            # Check for transform keywords
            transform_name = self._match_transform()
            if not transform_name:
                break
            
            # Determine if we need CTE wrapping
            # GROUP BY followed by WHERE/HAVING needs CTE
            if seen_group_by and transform_name in ("WHERE", "FILTER", "IF"):
                query = self._build_pipe_cte(query, [exp.Star()])
            
            # Apply the transform
            query = self.TRANSFORM_PARSERS[transform_name](self, query)
            
            # Track GROUP BY
            if transform_name == "GROUP BY":
                seen_group_by = True
        
        # Handle set operations (UNION, INTERSECT, EXCEPT)
        if parse_set_operation:
            query = self._parse_set_operations(query)
        
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
        order = self.expression(exp.Order, expressions=expressions)
        return query.order_by(order, copy=False)

    def _parse_ordered(
        self, parse_method: t.Optional[t.Callable] = None
    ) -> t.Optional[exp.Ordered]:
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

    def _parse_asql_ordered(self) -> t.Optional[exp.Ordered]:
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

        self._apply_star_column_override(expressions)

        return query.select(*expressions, append=False, copy=False)

    def _is_transform_boundary_token(self, token_type: TokenType, text: str) -> bool:
        """Return True if a token can start a new pipeline transform."""
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
        return text.upper() in self.TRANSFORM_PARSERS

    def _find_transform_boundary_index(self) -> int:
        """Find token index where a transform payload should stop."""
        depth = 0
        i = self._index
        while i < len(self._tokens):
            tok = self._tokens[i]

            if tok.token_type in (TokenType.L_PAREN, TokenType.L_BRACKET, TokenType.L_BRACE):
                depth += 1
            elif tok.token_type in (TokenType.R_PAREN, TokenType.R_BRACKET, TokenType.R_BRACE):
                depth = max(depth - 1, 0)

            if depth == 0 and i != self._index and self._is_transform_boundary_token(tok.token_type, tok.text):
                return i

            i += 1

        return len(self._tokens)

    def _consume_tokens_until_index(self, end_index: int) -> None:
        """Advance tokens until self._index == end_index."""
        while self._curr and self._index < end_index:
            self._advance()

    def _parse_asql_expression_until_transform_boundary(self) -> t.Optional[exp.Expression]:
        """Parse an expression until the next transform keyword (PRQL-style chaining).

        This enables indentation/newline pipelines without requiring explicit `|`.
        """
        if not self._curr:
            return None

        end_index = self._find_transform_boundary_index()
        if self._index >= end_index:
            return None

        condition = self._parse_assignment()
        self._consume_tokens_until_index(end_index)
        return condition

    def _parse_asql_select_expressions_until_transform_boundary(self) -> list[exp.Expression]:
        """Parse SELECT projections until the next transform keyword."""
        if not self._curr:
            return []

        end_index = self._find_transform_boundary_index()
        expressions: list[exp.Expression] = []

        while self._curr and self._index < end_index:
            expression = self._parse_expression()
            if not expression:
                break
            expressions.append(expression)

            if not self._match(TokenType.COMMA):
                break

        self._consume_tokens_until_index(end_index)
        return expressions

    def _parse_asql_group_by(self, query: exp.Query) -> exp.Query:
        """Parse GROUP BY with optional aggregate block: group by X (agg1, agg2).
        
        Note: GROUP BY is tokenized as a single token, so BY is already consumed.
        
        Syntax options:
        1. group by col1, col2              - standard GROUP BY
        2. group by col1 (agg1, agg2)       - GROUP BY with aggregate block
        3. group by col1, col2 (agg1, agg2) - multiple cols with aggregates
        
        The tricky part: `group by region (sum(amount))` - the ( starts an aggregate
        block, not a function call. We use _parse_group_by_term() which handles this.
        """
        expressions = []
        
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
        
        # Check for aggregate block: group by X (agg1, agg2)
        if self._match(TokenType.L_PAREN):
            aggregates = self._parse_csv(self._parse_expression)
            if not self._match(TokenType.R_PAREN):
                self.raise_error("Expected ) to close aggregate block")
            
            # Replace SELECT * with grouping cols + aggregates
            select_exprs = list(expressions) + list(aggregates)
            query.select(*select_exprs, append=False, copy=False)
        
        return query
    
    def _parse_group_by_term(self) -> t.Optional[exp.Expression]:
        """Parse a single GROUP BY term, handling the aggregate block ambiguity.
        
        This handles:
        - Simple columns: region, category
        - Qualified columns: customers.id, orders.total
        - Function calls: month(date), year(created_at), slugify(name)
        - But stops at standalone ( that starts an aggregate block
        
        The key insight: aggregate blocks always contain aliased expressions.
        So we parse a "simple term" (column or function) and stop before any
        standalone ( that looks like an aggregate block.
        """
        if not self._curr:
            return None
        
        if self._curr.token_type == TokenType.VAR:
            name = self._curr.text
            next_tok = self._next
            
            # Check for qualified column: table.column
            if next_tok and next_tok.token_type == TokenType.DOT:
                # This is table.column - parse the full qualified name
                self._advance()  # consume table name
                self._advance()  # consume .
                
                if self._curr and self._curr.token_type == TokenType.VAR:
                    col_name = self._curr.text
                    self._advance()  # consume column name
                    return exp.Column(
                        this=exp.to_identifier(col_name),
                        table=exp.to_identifier(name)
                    )
                else:
                    # Malformed, just return the table as column
                    return exp.Column(this=exp.to_identifier(name))
            
            if next_tok and next_tok.token_type == TokenType.L_PAREN:
                # Check if this looks like an aggregate block
                if self._looks_like_aggregate_block_at(self._index + 1):
                    # This is: identifier (aggregate_block)
                    self._advance()  # consume identifier
                    return exp.Column(this=exp.to_identifier(name))
                
                # Otherwise, this is a function call like month(date) or slugify(name)
                # Check if it's a custom function with special parsing (like SLUGIFY)
                upper_name = name.upper()
                if upper_name in self.FUNCTION_PARSERS:
                    # Use the custom function parser
                    self._advance()  # consume function name
                    return self.FUNCTION_PARSERS[upper_name](self)
                
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
                    if callable(func_class):
                        expr = func_class(args)
                    else:
                        expr = func_class(this=args[0] if args else None)
                else:
                    expr = exp.Anonymous(this=name, expressions=args)
                
                return expr
            else:
                # Simple column
                self._advance()
                return exp.Column(this=exp.to_identifier(name))
        
        # For other cases (literals, etc.), use standard parsing
        return self._parse_primary()
    
    def _looks_like_aggregate_block_at(self, paren_idx: int) -> bool:
        """Check if ( at given index starts an aggregate block vs a function call.
        
        Aggregate blocks contain aggregate functions with aliases:
        - (sum(amount) as revenue)   - explicit alias
        - (count(*) num)             - implicit alias (func followed by VAR)
        
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
                if tok.token_type == TokenType.VAR:
                    # Check if this is a function call
                    next_idx = peek_idx + 1
                    if next_idx < len(self._tokens):
                        next_tok = self._tokens[next_idx]
                        if next_tok.token_type == TokenType.L_PAREN:
                            found_inner_func = True
            
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
            expressions=[exp.Star()]
        )

    def _parse_asql_explode(self, query: exp.Query) -> exp.Query:
        """Parse EXPLODE clause: explode array_expr as alias.

        We parse into a CROSS JOIN UNNEST(...) AS alias. Dialect-specific differences
        (e.g. Snowflake FLATTEN) are handled in the compiler stage.
        """
        array_expr = self._parse_unary()
        if not array_expr:
            self.raise_error("Expected expression after 'explode'")

        if not self._match(TokenType.ALIAS):  # AS
            self.raise_error("Expected 'as' after explode expression")

        alias = self._parse_id_var()
        if not alias:
            self.raise_error("Expected alias name after 'explode ... as'")

        unnest = exp.Unnest(
            expressions=[array_expr],
            alias=exp.TableAlias(this=exp.to_identifier(alias)),
        )

        return query.join(unnest, join_type="CROSS", copy=False)

    def _parse_table(
        self,
        schema: bool = False,
        joins: bool = False,
        alias_tokens: t.Optional[t.Collection[TokenType]] = None,
        parse_bracket: bool = False,
        is_db_reference: bool = False,
        parse_partition: bool = False,
        consume_pipe: bool = False,
    ) -> t.Optional[exp.Expression]:
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

            if not self._match(TokenType.ALIAS):  # AS
                self.raise_error("Expected 'as' after explode expression")

            alias = self._parse_id_var()
            if not alias:
                self.raise_error("Expected alias name after 'explode ... as'")

            unnest = exp.Unnest(
                expressions=[array_expr],
                alias=exp.TableAlias(this=exp.to_identifier(alias)),
            )
            join = exp.Join(this=unnest, kind="CROSS")
            table_expr.append("joins", join)

        return table_expr

    def _parse_asql_stash(self, query: exp.Query) -> exp.Query:
        """Parse STASH AS clause for CTEs."""
        if not self._match(TokenType.ALIAS):  # AS
            self.raise_error("Expected 'as' after 'stash'")
        
        alias = self._parse_id_var()
        if not alias:
            self.raise_error("Expected CTE name after 'stash as'")
        
        # Create CTE and continue with SELECT * FROM cte
        table_alias = exp.to_identifier(alias)
        return self._build_pipe_cte(query, [exp.Star()], exp.TableAlias(this=table_alias))

    def _parse_asql_join(self, query: exp.Query, kind: str = "INNER") -> exp.Query:
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
        
        # Build the join
        join = exp.Join(this=this, on=on_condition, kind=kind)
        query.join(join, copy=False)
        return query
    
    def _parse_on_condition_until_join_op(self) -> t.Optional[exp.Expression]:
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
                    TokenType.WHERE, TokenType.GROUP_BY, TokenType.ORDER_BY,
                    TokenType.LIMIT, TokenType.HAVING, TokenType.QUALIFY
                ):
                    return False
                
                # Check for join operators
                if tok.token_type in (TokenType.AMP, TokenType.QMARK_AMP):
                    return True
                if tok.token_type == TokenType.PLACEHOLDER and tok.text == "?&?":
                    return True
                if tok.token_type == TokenType.STAR:
                    if idx + 1 < len(self._tokens) and self._tokens[idx + 1].token_type == TokenType.VAR:
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
            if idx + 1 < len(self._tokens) and self._tokens[idx + 1].token_type == TokenType.VAR:
                return True
        return False
    
    def _parse_on_expr_with_join_stop(self) -> t.Optional[exp.Expression]:
        """Parse ON expression, stopping at join operators.
        
        We scan ahead to find the extent of the expression, then parse it.
        """
        # Find extent of ON condition (stop at join operators, other clauses, or end)
        start_idx = self._index
        
        while self._curr and not self._is_at_join_op_or_end():
            # Also stop at clause keywords
            if self._curr.token_type in (
                TokenType.WHERE, TokenType.GROUP_BY, TokenType.ORDER_BY, 
                TokenType.LIMIT, TokenType.HAVING, TokenType.QUALIFY
            ):
                break
            self._advance()
        
        # Parse what we've accumulated
        end_idx = self._index
        
        if end_idx == start_idx:
            return None
        
        # Reset to start and parse as expression
        self._index = start_idx
        self._curr = self._tokens[start_idx]
        
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
    
    def _parse_term_for_join(self) -> t.Optional[exp.Expression]:
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
                        this=exp.to_identifier(col_name),
                        table=exp.to_identifier(name)
                    )
            
            return exp.Column(this=exp.to_identifier(name))
        
        # Handle literals
        if self._curr.token_type in (TokenType.STRING, TokenType.NUMBER):
            val = self._curr.text
            self._advance()
            return exp.Literal.string(val) if self._prev.token_type == TokenType.STRING else exp.Literal.number(val)
        
        # Handle TRUE/FALSE
        if self._curr.token_type in (TokenType.TRUE, TokenType.FALSE):
            val = self._curr.token_type == TokenType.TRUE
            self._advance()
            return exp.Boolean(this=val)
        
        return None

    def _parse_join_kind(self, query: exp.Query, kind: str, skip_keywords: tuple = ()) -> exp.Query:
        """Parse join with specified kind after consuming optional keywords."""
        for kw in skip_keywords:
            self._match_text_seq(*kw.split())
        return self._parse_asql_join(query, kind=kind)

    def _parse_asql_qmark_join(self, query: exp.Query) -> exp.Query:
        """Parse &? (LEFT) or ?& (RIGHT) join based on previous token."""
        prev = self._tokens[self._index - 1].text if self._index > 0 else ""
        return self._parse_asql_join(query, kind="LEFT" if prev == "&?" else "RIGHT")

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
        partition_cols: t.List[exp.Expression] = []
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
        order_desc = False
        alias = None
        
        if self._match(TokenType.FIRST) or self._match_text_seq("FIRST"):
            # per X first by Y → QUALIFY ROW_NUMBER() OVER (PARTITION BY X ORDER BY Y) = 1
            if not self._match_text_seq("BY"):
                self.raise_error("Expected BY after FIRST")
                return query
            order_expr, order_desc = self._parse_order_col_with_direction()
            return self._add_qualify_row_number(query, partition_cols, order_expr, order_desc)
            
        elif self._match_text_seq("LAST"):
            # per X last by Y → QUALIFY ROW_NUMBER() OVER (PARTITION BY X ORDER BY Y DESC) = 1
            # Note: LAST is not a token type, so we use _match_text_seq
            if not self._match_text_seq("BY"):
                self.raise_error("Expected BY after LAST")
                return query
            order_expr, order_desc = self._parse_order_col_with_direction()
            # Reverse the order for "last"
            order_desc = not order_desc
            return self._add_qualify_row_number(query, partition_cols, order_expr, order_desc)
            
        elif self._match_text_seq("DENSE", "RANK") or self._match_text_seq("DENSE_RANK"):
            # per X dense rank by Y [as alias]
            if not self._match_text_seq("BY"):
                self.raise_error("Expected BY after DENSE RANK")
                return query
            order_expr, order_desc = self._parse_order_col_with_direction()
            alias = self._parse_alias_after_as()
            return self._add_window_to_select(query, exp.DenseRank, partition_cols, order_expr, order_desc, alias or "dense_rank")
            
        elif self._match_text_seq("NUMBER"):
            # per X number by Y [as alias]
            if not self._match_text_seq("BY"):
                self.raise_error("Expected BY after NUMBER")
                return query
            order_expr, order_desc = self._parse_order_col_with_direction()
            alias = self._parse_alias_after_as()
            return self._add_window_to_select(query, exp.RowNumber, partition_cols, order_expr, order_desc, alias or "row_num")
            
        elif self._match_text_seq("RANK"):
            # per X rank by Y [as alias]
            if not self._match_text_seq("BY"):
                self.raise_error("Expected BY after RANK")
                return query
            order_expr, order_desc = self._parse_order_col_with_direction()
            alias = self._parse_alias_after_as()
            return self._add_window_to_select(query, exp.Rank, partition_cols, order_expr, order_desc, alias or "rank")
        
        else:
            self.raise_error("Expected FIRST, LAST, NUMBER, RANK, or DENSE RANK after partition columns")
            return query
    
    def _parse_order_col_with_direction(self) -> t.Tuple[exp.Expression, bool]:
        """Parse order column with optional - prefix for DESC."""
        order_desc = False
        if self._match(TokenType.DASH):
            order_desc = True
        order_expr = self._parse_column()
        return order_expr, order_desc
    
    def _parse_alias_after_as(self) -> t.Optional[str]:
        """Parse optional AS alias."""
        if self._match(TokenType.ALIAS):
            alias_expr = self._parse_id_var()
            return alias_expr.this if alias_expr else None
        return None
    
    def _add_qualify_row_number(
        self, 
        query: exp.Query, 
        partition_cols: t.List[exp.Expression],
        order_expr: exp.Expression,
        order_desc: bool
    ) -> exp.Query:
        """Add QUALIFY ROW_NUMBER() OVER (...) = 1 to query."""
        # Build window: ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)
        order = exp.Ordered(this=order_expr, desc=order_desc)
        row_num = exp.Window(
            this=exp.RowNumber(),
            partition_by=partition_cols,
            order=exp.Order(expressions=[order])
        )
        
        # QUALIFY ROW_NUMBER() = 1
        qualify = exp.EQ(this=row_num, expression=exp.Literal.number(1))
        
        return query.qualify(qualify, copy=False)
    
    def _add_window_to_select(
        self,
        query: exp.Query,
        window_func: t.Type[exp.Func],
        partition_cols: t.List[exp.Expression],
        order_expr: exp.Expression,
        order_desc: bool,
        alias: str
    ) -> exp.Query:
        """Add a window function to the SELECT list."""
        # Build window: func() OVER (PARTITION BY ... ORDER BY ...)
        order = exp.Ordered(this=order_expr, desc=order_desc)
        window = exp.Window(
            this=window_func(),
            partition_by=partition_cols,
            order=exp.Order(expressions=[order])
        )
        
        # Add as aliased column to SELECT
        aliased = exp.Alias(this=window, alias=exp.to_identifier(alias))
        
        return query.select(aliased, append=True, copy=False)
    
    def _parse_asql_standalone_rank(
        self,
        query: exp.Query,
        window_func: t.Type[exp.Func],
        default_alias: str
    ) -> exp.Query:
        """Parse standalone ranking: number by <col> [as alias] or rank by <col> [as alias].
        
        Only triggers if followed by BY. Otherwise returns None to fall through
        to standard function parsing (e.g., rank() over (...)).
        """
        if not self._match_text_seq("BY"):
            # Not "rank by", let it fall through to standard parsing
            return None
        
        order_expr, order_desc = self._parse_order_col_with_direction()
        alias = self._parse_alias_after_as()
        
        # Build window: func() OVER (ORDER BY ...)
        order = exp.Ordered(this=order_expr, desc=order_desc)
        window = exp.Window(
            this=window_func(),
            order=exp.Order(expressions=[order])
        )
        
        # Add as aliased column to SELECT
        aliased = exp.Alias(this=window, alias=exp.to_identifier(alias or default_alias))
        
        return query.select(aliased, append=True, copy=False)
    
    def _parse_asql_dense_rank_standalone(self, query: exp.Query) -> exp.Query:
        """Parse dense rank by <col> [as alias] (handles the space in 'dense rank')."""
        if not self._match_text_seq("RANK"):
            self.raise_error("Expected RANK after DENSE")
            return query
        return self._parse_asql_standalone_rank(query, exp.DenseRank, "dense_rank")
    
    def _parse_asql_deduplicate(self, query: exp.Query) -> exp.Query:
        """Parse deduplicate by <cols> order by <col>.
        
        This is syntactic sugar for: per <cols> first by <col>
        """
        if not self._match_text_seq("BY"):
            self.raise_error("Expected BY after DEDUPLICATE")
            return query
        
        # Parse partition columns
        partition_cols: t.List[exp.Expression] = []
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
        if not self._match(TokenType.ORDER_BY) and not self._match_text_seq("ORDER", "BY"):
            self.raise_error("DEDUPLICATE BY requires ORDER BY clause")
            return query
        
        # Parse order expression with optional - prefix
        order_expr, order_desc = self._parse_order_col_with_direction()
        
        # Same as: per <cols> first by <order_col>
        return self._add_qualify_row_number(query, partition_cols, order_expr, order_desc)

    def _parse_asql_cohort(self, query: exp.Query) -> exp.Query:
        """Parse cohort by [segments,] <granularity>(<table.column>) [on <join_key>].
        
        Syntax:
            cohort by month(users.signup_date)
            cohort by month(users.signup_date) on user_id
            cohort by users.channel, month(users.signup_date) on user_id
            cohort by week(customers.first_order_date) on customer_id
        
        This stores cohort info on the query for later AST transformation in the compiler.
        The compiler will generate:
        - CTEs: cohort_base, cohort_sizes
        - JOINs to those CTEs
        - Modified SELECT with cohort_month, period, cohort_size
        - Modified GROUP BY and ORDER BY
        """
        if not self._match_text_seq("BY"):
            self.raise_error("Expected BY after COHORT")
            return query
        
        # Parse optional segment columns before the granularity function
        # Syntax: cohort by segment1, segment2, month(...)
        segments: t.List[exp.Expression] = []
        
        while True:
            # Check if this is the granularity function (month/week/day)
            if self._curr and self._curr.token_type == TokenType.VAR:
                curr_text = self._curr.text.upper()
                if curr_text in ("MONTH", "WEEK", "DAY"):
                    # Check if followed by ( - that means it's the granularity function
                    next_tok = self._next
                    if next_tok and next_tok.token_type == TokenType.L_PAREN:
                        break  # Found granularity function
            
            # Try parsing a column as segment
            col = self._parse_column()
            if col:
                segments.append(col)
                if not self._match(TokenType.COMMA):
                    break
            else:
                break
        
        # Parse granularity function: month/week/day
        granularity = None
        if self._match_text_seq("MONTH"):
            granularity = "month"
        elif self._match_text_seq("WEEK"):
            granularity = "week"
        elif self._match_text_seq("DAY"):
            granularity = "day"
        else:
            self.raise_error("Expected MONTH, WEEK, or DAY for cohort granularity")
            return query
        
        # Parse (table.column)
        if not self._match(TokenType.L_PAREN):
            self.raise_error(f"Expected ( after {granularity.upper()}")
            return query
        
        # Parse column reference (may be table.column or just column)
        cohort_col = self._parse_column()
        if not cohort_col:
            self.raise_error("Expected column reference in cohort function")
            return query
        
        if not self._match(TokenType.R_PAREN):
            self.raise_error("Expected ) after cohort column")
            return query
        
        # Parse optional ON join_key
        join_key = None
        if self._match(TokenType.ON):
            join_key_col = self._parse_column()
            if join_key_col:
                join_key = join_key_col.name if hasattr(join_key_col, 'name') else str(join_key_col.this)
        
        # Store cohort info on the query for compiler to process
        # We use a custom annotation that the compiler will look for
        cohort_info = {
            "granularity": granularity,
            "cohort_col": cohort_col,
            "join_key": join_key,
            "segments": segments,
        }
        
        # Store as a comment/annotation that survives AST manipulation
        # The compiler will look for this and apply the cohort transform
        if not hasattr(query, "_cohort_info"):
            query._cohort_info = cohort_info
        else:
            query._cohort_info = cohort_info
        
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
        expressions: list[exp.Expression] = list(query.expressions)
        star = next((e for e in expressions if isinstance(e, exp.Star)), None)
        if not star:
            star = exp.Star()
            expressions.insert(0, star)

        existing = (star.args.get("except_") or star.args.get("except") or [])
        existing_names = {c.name for c in existing if isinstance(c, exp.Column) and c.name}
        new_names = {c.name for c in columns if isinstance(c, exp.Column) and c.name}
        merged_names = sorted(existing_names.union(new_names))
        star.set("except_", [exp.Column(this=exp.to_identifier(n)) for n in merged_names])

        query.set("expressions", expressions)
        return query

    def _parse_asql_rename(self, query: exp.Query) -> exp.Query:
        """Parse RENAME column operator."""
        # Syntax:
        #   rename old as new
        #   rename old as new, old2 as new2
        rename_pairs: list[tuple[exp.Column, exp.Identifier]] = []

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

        expressions: list[exp.Expression] = list(query.expressions)
        star = next((e for e in expressions if isinstance(e, exp.Star)), None)
        if not star:
            star = exp.Star()
            expressions.insert(0, star)

        existing = (star.args.get("except_") or star.args.get("except") or [])
        existing_names = {c.name for c in existing if isinstance(c, exp.Column) and c.name}

        # Renames must exclude the original columns to avoid duplicates
        rename_old_names = {old.name for old, _ in rename_pairs}
        merged_names = sorted(existing_names.union(rename_old_names))
        star.set("except_", [exp.Column(this=exp.to_identifier(n)) for n in merged_names])

        expressions.extend(
            exp.Alias(this=exp.Column(this=old.this), alias=new) for old, new in rename_pairs
        )
        query.set("expressions", expressions)
        return query

    def _parse_asql_replace(self, query: exp.Query) -> exp.Query:
        """Parse REPLACE column operator."""
        # Syntax:
        #   replace col with expr
        #   replace col with expr, col2 with expr2
        replace_pairs: list[tuple[str, exp.Expression]] = []

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

        expressions: list[exp.Expression] = list(query.expressions)
        star = next((e for e in expressions if isinstance(e, exp.Star)), None)
        if not star:
            star = exp.Star()
            expressions.insert(0, star)

        existing = (star.args.get("except_") or star.args.get("except") or [])
        existing_names = {c.name for c in existing if isinstance(c, exp.Column) and c.name}

        exclude_names = {col for col, _ in replace_pairs}
        merged_names = sorted(existing_names.union(exclude_names))
        star.set("except_", [exp.Column(this=exp.to_identifier(n)) for n in merged_names])

        expressions.extend(
            exp.Alias(this=expr, alias=exp.to_identifier(col)) for col, expr in replace_pairs
        )
        query.set("expressions", expressions)
        return query
    
    # Note: PIVOT/UNPIVOT parsing is handled by _parse_pivot() (table expression level)
    # Note: EXPLODE is still handled by preparser markers (complex dialect-specific output)

    def _parse_asql_sample(self, query: exp.Query) -> exp.Query:
        """Parse SAMPLE clause."""
        # Supported:
        # - sample N         -> ORDER BY RANDOM() LIMIT N
        # - sample N%        -> TABLESAMPLE BERNOULLI(N)
        # - sample N per col -> QUALIFY ROW_NUMBER() OVER (PARTITION BY col ORDER BY RANDOM()) <= N
        if not self._match(TokenType.NUMBER):
            self.raise_error("Expected number after SAMPLE")

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

            rand = exp.Rand()
            window = exp.Window(
                this=exp.RowNumber(),
                partition_by=exp.Partition(expressions=[partition_col]),
                order=exp.Order(expressions=[exp.Ordered(this=rand)]),
            )
            condition = exp.LTE(this=window, expression=n)
            return self._build_pipe_cte(query=query.qualify(condition, copy=False), expressions=[exp.Star()])

        # sample N
        rand = exp.Rand()
        sampled_query = query.order_by(exp.Order(expressions=[exp.Ordered(this=rand)]), copy=False).limit(n, copy=False)
        return self._build_pipe_cte(query=sampled_query, expressions=[exp.Star()])

    def _parse_equality(self) -> t.Optional[exp.Expression]:
        """Parse equality with NULL handling.
        
        Like PRQL: `== null` becomes `IS NULL`
        """
        eq = self._parse_tokens(self._parse_comparison, self.EQUALITY)
        if not isinstance(eq, (exp.EQ, exp.NEQ)):
            return eq

        # NULL handling: == null → IS NULL
        if isinstance(eq.expression, exp.Null):
            is_exp = exp.Is(this=eq.this, expression=eq.expression)
            return is_exp if isinstance(eq, exp.EQ) else exp.Not(this=is_exp)
        if isinstance(eq.this, exp.Null):
            is_exp = exp.Is(this=eq.expression, expression=eq.this)
            return is_exp if isinstance(eq, exp.EQ) else exp.Not(this=is_exp)
        
        return eq

    def _parse_comparison(self) -> t.Optional[exp.Expression]:
        """Parse comparison expressions with ASQL string-matching operators.

        Supports:
        - contains / icontains
        - starts with / istarts with
        - ends with / iends with
        - matches
        """
        index = self._index
        left = self._parse_range()

        if left and self._curr and self._curr.token_type == TokenType.VAR:
            def build_like(
                right: exp.Expression,
                *,
                wrap_left: str,
                wrap_right: str,
                case_insensitive: bool,
            ) -> exp.Expression:
                if isinstance(right, exp.Literal) and right.is_string:
                    pattern = exp.Literal.string(f"{wrap_left}{right.this}{wrap_right}")
                else:
                    parts: list[exp.Expression] = []
                    if wrap_left:
                        parts.append(exp.Literal.string(wrap_left))
                    parts.append(right)
                    if wrap_right:
                        parts.append(exp.Literal.string(wrap_right))
                    pattern = exp.Concat(expressions=parts) if len(parts) > 1 else right

                like_cls: t.Type[exp.Expression] = exp.ILike if case_insensitive else exp.Like
                return like_cls(this=left, expression=pattern)

            # Try to match string operators from dialect schema
            from asql.dialect_schema import OPERATORS

            matched_operator = None
            for attr_name in dir(OPERATORS.STRING):
                if not attr_name.startswith('_'):
                    string_op = getattr(OPERATORS.STRING, attr_name)
                    if hasattr(string_op, 'tokens'):
                        if self._match_text_seq(*string_op.tokens):
                            matched_operator = string_op
                            break

            if not matched_operator:
                self._retreat(index)
                return super()._parse_comparison()

            # Use matched operator's configuration
            case_insensitive = not matched_operator.case_sensitive
            wrap_left, wrap_right = matched_operator.wrap_pattern

            right = self._parse_range()
            if not right:
                self.raise_error("Expected string literal or expression after string operator")
            return build_like(
                right,
                wrap_left=wrap_left,
                wrap_right=wrap_right,
                case_insensitive=case_insensitive,
            )

        self._retreat(index)
        return super()._parse_comparison()

    def _parse_assignment(self) -> t.Optional[exp.Expression]:
        """Parse assignment expressions with ternary operator support.
        
        Ternary: `condition ? true_value : false_value` → `CASE WHEN condition THEN true_value ELSE false_value END`
        
        Following ClickHouse's elegant pattern - check for ? AFTER parsing expression,
        then recursively parse true/false values. Handles nested ternaries automatically.
        """
        this = super()._parse_assignment()
        
        if self._match(TokenType.PLACEHOLDER):  # Found ?
            return self.expression(
                exp.If,
                this=this,
                true=self._parse_assignment(),
                false=self._match(TokenType.COLON) and self._parse_assignment(),
            )
        
        return this

    def _parse_unary(self) -> t.Optional[exp.Expression]:
        """Parse unary expressions with ASQL extensions.
        
        Extensions:
        - COUNT shorthand: `#` → `COUNT(*)`
        - COUNT shorthand: `#(col)` → `COUNT(col)` 
        - Relative dates: `7 days ago` → `CURRENT_TIMESTAMP - INTERVAL '7 days'`
        - Relative dates: `3 months from now` → `CURRENT_TIMESTAMP + INTERVAL '3 months'`
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

        parsed_count = self._parse_asql_count_unary(start_index)
        if parsed_count is not None:
            return parsed_count

        parsed_relative_date = self._parse_asql_relative_date_unary(start_index)
        if parsed_relative_date is not None:
            return parsed_relative_date

        parsed_space_date = self._parse_asql_space_notation_date_function_unary(start_index)
        if parsed_space_date is not None:
            return parsed_space_date

        parsed_natural_agg = self._parse_asql_natural_agg_unary(start_index)
        if parsed_natural_agg is not None:
            return parsed_natural_agg

        return super()._parse_unary()

    def _parse_asql_multiword_unary(self, start_index: int) -> t.Optional[exp.Expression]:
        """Parse ASQL multi-word unary sugar like `day of week col` and `row number()`."""
        if self._match_text_seq("DAY", "OF", "WEEK"):
            argument = self._parse_column()
            if not argument:
                self.raise_error("Expected expression after 'day of week'")
            return exp.DayOfWeek(this=argument)

        row_number_index = self._index
        if self._match_text_seq("ROW", "NUMBER") and self._match(TokenType.L_PAREN):
            if not self._match(TokenType.R_PAREN):
                self.raise_error("Expected ) after row number(")
            return self._parse_window(exp.RowNumber())
        self._retreat(row_number_index)

        self._retreat(start_index)
        return None

    def _parse_asql_count_unary(self, start_index: int) -> t.Optional[exp.Expression]:
        """Parse COUNT shorthand at expression start (`#`, `#(col)`, `#*`)."""
        if self._match(TokenType.HASH):
            return self._parse_count_shorthand_from_primary()

        self._retreat(start_index)
        return None

    def _parse_asql_relative_date_unary(self, start_index: int) -> t.Optional[exp.Expression]:
        """Parse relative date literals like `7 days ago` / `3 months from now`."""
        if not self._match(TokenType.NUMBER, advance=False):
            self._retreat(start_index)
            return None

        number_text = self._curr.text
        self._advance()

        if not (self._curr and self._curr.text.lower() in self.TIME_UNITS):
            self._retreat(start_index)
            return None

        unit_text = self._curr.text.lower()
        self._advance()

        if self._match_text_seq("AGO"):
            interval = exp.Interval(this=exp.Literal.string(f"{number_text} {unit_text}"))
            return exp.Sub(this=exp.CurrentTimestamp(), expression=interval)

        if self._match_text_seq("FROM", "NOW"):
            interval = exp.Interval(this=exp.Literal.string(f"{number_text} {unit_text}"))
            return exp.Add(this=exp.CurrentTimestamp(), expression=interval)

        self._retreat(start_index)
        return None

    def _parse_asql_space_notation_date_function_unary(
        self,
        start_index: int,
    ) -> t.Optional[exp.Expression]:
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

    def _parse_asql_natural_agg_unary(self, start_index: int) -> t.Optional[exp.Expression]:
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
    
    def _parse_factor(self) -> t.Optional[exp.Expression]:
        """Parse factor expressions with ASQL date arithmetic.
        
        Extensions:
        - Date arithmetic: `created_at + 7 days` → `created_at + INTERVAL '7 days'`
        - Date arithmetic: `due_date - 1 month` → `due_date - INTERVAL '1 month'`
        
        Uses idiomatic SQLGlot save/retreat pattern for lookahead.
        """
        this = super()._parse_factor()
        
        # Check for date arithmetic: expr +/- NUMBER TIME_UNIT
        while self._curr:
            op_class = None
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
                    if self._curr and self._curr.text.lower() in ('ago', 'from'):
                        # Retreat to before operator - let _parse_unary handle it
                        self._retreat(index - 1)
                        break
                    
                    # Build: left +/- INTERVAL 'N unit'
                    interval = exp.Interval(this=exp.Literal.string(f"{number} {unit}"))
                    this = op_class(this=this, expression=interval)
                    continue
            
            # Not a date arithmetic pattern, retreat and let normal parsing handle it
            self._retreat(index - 1)  # Back to before operator
            break
        
        return this

    def _parse_date_literal(self) -> t.Optional[exp.Expression]:
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
            if var_text.startswith('T') and var_text[1:].isdigit():
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
                                return exp.Timestamp(this=exp.Literal.string(f"{date_str} {time_str}"))
        
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
        anchor_condition = where_clause.this.copy() if where_clause else exp.EQ(this=exp.Literal.number(1), expression=exp.Literal.number(1))
        
        cte_name = f"_recurse_{table_name}"
        table_alias = table_name[0].lower()
        
        # Build anchor query using AST: SELECT *, 1 AS _level FROM table WHERE ...
        anchor_query = (
            exp.select(exp.Star(), exp.Alias(this=exp.Literal.number(1), alias="_level"))
            .from_(table_name, copy=False)
            .where(anchor_condition, copy=False)
        )
        
        # Build recursive query using AST
        recursive_query = (
            exp.select(
                exp.Column(this=exp.Star(), table=table_alias),
                exp.Add(
                    this=exp.Column(this=exp.to_identifier("_level"), table=cte_name),
                    expression=exp.Literal.number(1)
                )
            )
            .from_(exp.Table(this=exp.to_identifier(table_name), alias=exp.TableAlias(this=exp.to_identifier(table_alias))), copy=False)
            .join(cte_name, on=exp.EQ(
                this=exp.Column(this=exp.to_identifier(fk_col_name), table=table_alias),
                expression=exp.Column(this=exp.to_identifier("id"), table=cte_name)
            ), copy=False)
            .where(exp.LT(
                this=exp.Column(this=exp.to_identifier("_level"), table=cte_name),
                expression=exp.Literal.number(max_depth)
            ), copy=False)
        )
        
        # Combine with UNION ALL
        cte_body = exp.Union(this=anchor_query, expression=recursive_query, distinct=False)
        cte_expr = exp.CTE(this=cte_body, alias=exp.TableAlias(this=exp.to_identifier(cte_name)))
        
        # Final query: SELECT * FROM cte_name
        new_query = exp.select("*").from_(cte_name, copy=False)
        new_query.set("with_", exp.With(expressions=[cte_expr], recursive=True))
        
        return new_query


class ASQLGenerator(Generator):
    """Generator for outputting SQL from ASQL AST.
    
    Note: We typically use target dialect generators (postgres, bigquery, etc.)
    for final output. This is mainly for debugging/introspection.
    """
    pass  # Inherits all from Generator - add TRANSFORMS overrides as needed


class ASQL(Dialect):
    """ASQL (Analytic SQL) dialect for SQLGlot.
    
    ASQL is a human-readable, pipeline-based query language that transpiles to SQL.
    This dialect uses SQLGlot's TRANSFORM_PARSERS pattern (like PRQL) for proper
    pipeline semantics.
    
    Key features handled:
    - FROM-first syntax: `from users where status = 'active'`
    - Pipeline operators: `from users | where x | group by y`
    - Proper CTE wrapping: `group by X | where Y` → CTE + WHERE
    - Descending order shorthand: `-column` → `column DESC`
    - NULL equality: `== null` → `IS NULL`
    - Ternary operator: `x ? y : z` → `CASE WHEN x THEN y ELSE z END`
    - Relative dates: `7 days ago` → `CURRENT_TIMESTAMP - INTERVAL '7 days'`
    - Date arithmetic: `col + 7 days` → `col + INTERVAL '7 days'`
    
    Features still handled by preparser (syntactic sugar):
    - `#` → COUNT(*)
    - `@date` → DATE literal
    - Natural aggregates: `sum amount` → `sum(amount)`
    - Join operators (`&`, `<&`, `&>`)
    - etc.
    """
    
    # Dialect configuration constants (following ClickHouse pattern)
    DPIPE_IS_STRING_CONCAT = True  # || is string concatenation, not OR
    NORMALIZE_FUNCTIONS: bool | str = False  # Preserve function name casing
    
    class Tokenizer(ASQLTokenizer):
        pass
    
    class Parser(ASQLParser):
        pass
    
    class Generator(ASQLGenerator):
        pass


# Register the dialect with SQLGlot
def register_asql_dialect() -> None:
    """Register the ASQL dialect with SQLGlot."""
    if "asql" not in Dialect._classes:
        Dialect["asql"] = ASQL


# Auto-register on import
register_asql_dialect()


# Backwards compatibility alias
ASQLDialect = ASQL
