"""ASQL Generator.

Converts SQLGlot AST back to ASQL syntax.
"""

import typing as t

from sqlglot import exp
from sqlglot.generator import Generator


class ASQLGenerator(Generator):
    """Generator for ASQL. Converts SQLGlot AST back to ASQL syntax.
    
    Settings are read from self.dialect.settings:
        asql = ASQL(cast="function", equality="double")
        sqlglot.transpile(sql, read="postgres", write=asql)
    
    Style settings:
        - equality: "single" (=) or "double" (==)
        - count: "hash" (#) or "function" (count(*))
        - coalesce: "operator" (??) or "function" (coalesce())
        - descending: "prefix" (-col) or "suffix" (col DESC)
        - cast: "double_colon" (::) or "function" (CAST())
        - quotes: "double" (") or "single" (')
        - function_shorthand: "underscore", "space", or "parens"
    
    Handles ASQL-specific output formatting:
    - CAST(x AS TYPE) → x::TYPE (if cast="double_colon")
    - WITH cte AS (...) → from ... stash as cte
    - SELECT * FROM → from
    - Joins with symbols: INNER JOIN → &
    """
    
    def _get_setting(self, name: str, default: t.Any = None) -> t.Any:
        """Get a style setting from dialect.settings with fallback to default."""
        if hasattr(self, 'dialect') and self.dialect and hasattr(self.dialect, 'settings'):
            return self.dialect.settings.get(name, default)
        return default
    
    # Join symbols for ASQL output
    # Maps (side, kind) combinations to ASQL syntax
    JOIN_SYMBOLS: t.Dict[str, str] = {
        "INNER": "&",
        "LEFT": "&?",
        "LEFT OUTER": "&?",
        "RIGHT": "?&",
        "RIGHT OUTER": "?&",
        "FULL": "?&?",
        "FULL OUTER": "?&?",
        "CROSS": "cross join",
    }
    
    def count_sql(self, expression: exp.Count) -> str:
        """Generate count syntax based on settings.
        
        If count="hash" (default): #
        If count="function": COUNT(*)
        """
        count_style = self._get_setting("count", "hash")
        
        # Check if it's COUNT(*)
        this = expression.this
        is_star = isinstance(this, exp.Star) or this is None
        
        if count_style == "hash" and is_star:
            return "#"
        else:
            # Standard count function
            if is_star:
                return "COUNT(*)"
            else:
                return f"COUNT({self.sql(this)})"
    
    def coalesce_sql(self, expression: exp.Coalesce) -> str:
        """Generate coalesce syntax based on settings.
        
        If coalesce="operator" (default): a ?? b
        If coalesce="function": COALESCE(a, b)
        """
        coalesce_style = self._get_setting("coalesce", "operator")
        
        # Coalesce has 'this' (first arg) and 'expressions' (remaining args)
        first = expression.this
        rest = expression.expressions or []
        
        all_args = [first] + list(rest) if first else list(rest)
        args = [self.sql(e) for e in all_args]
        
        if coalesce_style == "operator" and len(args) == 2:
            return f"{args[0]} ?? {args[1]}"
        else:
            return f"COALESCE({', '.join(args)})"
    
    def eq_sql(self, expression: exp.EQ) -> str:
        """Generate equality syntax based on settings.
        
        If equality="single" (default): a = b
        If equality="double": a == b
        """
        equality_style = self._get_setting("equality", "single")
        left = self.sql(expression, "this")
        right = self.sql(expression, "expression")
        
        if equality_style == "double":
            return f"{left} == {right}"
        else:
            return f"{left} = {right}"
    
    def ordered_sql(self, expression: exp.Ordered) -> str:
        """Generate ORDER BY column syntax based on settings.
        
        If descending="prefix" (default): -col
        If descending="suffix": col DESC
        """
        descending_style = self._get_setting("descending", "prefix")
        col = self.sql(expression, "this")
        desc = expression.args.get("desc")
        
        if desc:
            if descending_style == "prefix":
                return f"-{col}"
            else:
                return f"{col} DESC"
        else:
            return col
    
    def cast_sql(self, expression: exp.Cast, safe_prefix: t.Optional[str] = None) -> str:
        """Generate ASQL cast syntax based on settings.
        
        If cast="double_colon" (default): x::TYPE
        If cast="function": CAST(x AS TYPE)
        
        Note: safe_prefix (for TRY_CAST) is intentionally ignored - ASQL uses
        the same syntax for both CAST and TRY_CAST, leaving error handling
        to the target dialect during compilation.
        """
        cast_style = self._get_setting("cast", "double_colon")
        expr_sql = self.sql(expression, "this")
        type_sql = self.sql(expression, "to")
        
        if cast_style == "function":
            return f"CAST({expr_sql} AS {type_sql})"
        else:
            return f"{expr_sql}::{type_sql}"
    
    def with_sql(self, expression: exp.With) -> str:
        """Convert CTEs to stash statements for ASQL output.
        
        WITH cte AS (SELECT ...) SELECT ... FROM cte
        →
        from ... stash as cte
        
        from cte
        
        Comments on the WITH clause are preserved at the start of output.
        """
        cte_parts: t.List[str] = []
        
        for cte in expression.expressions:
            if isinstance(cte, exp.CTE):
                cte_alias = cte.alias
                cte_query = cte.this
                
                # Generate the inner query
                inner_sql = self.sql(cte_query)
                
                # Format as: inner_query stash as cte_name
                cte_name = self.sql(cte_alias) if cte_alias else ""
                cte_parts.append(f"{inner_sql} stash as {cte_name}")
        
        result = "\n\n".join(cte_parts)
        
        # Preserve comments from the WITH clause (e.g., header comments before CTEs)
        return self.maybe_comment(result, expression, separated=True)
    
    def from_sql(self, expression: exp.From) -> str:
        """Generate ASQL-style FROM clause (lowercase 'from')."""
        table_sql = self.sql(expression, "this")
        return f"from {table_sql}"
    
    def select_sql(self, expression: exp.Select) -> str:
        """Generate ASQL-style SELECT with FROM first.
        
        For SELECT * FROM table → from table
        For SELECT cols FROM table → from table select cols
        For SELECT DISTINCT cols → from table select distinct cols
        """
        # Get components - note SQLGlot uses from_ (underscore) due to Python reserved word
        from_ = expression.args.get("from_")
        where = expression.args.get("where")
        group = expression.args.get("group")
        order = expression.args.get("order")
        limit = expression.args.get("limit")
        having = expression.args.get("having")
        with_ = expression.args.get("with_")
        distinct = expression.args.get("distinct")
        
        # Build FROM clause first
        parts: t.List[str] = []
        
        # Handle CTEs first if present
        if with_:
            cte_sql = self.with_sql(with_)
            parts.append(cte_sql)
        
        # FROM clause - output "from table"
        if from_:
            table_sql = self.sql(from_.this)  # Get just the table expression
            parts.append(f"from {table_sql}")
        
        # Handle joins
        joins = expression.args.get("joins")
        if joins:
            for join in joins:
                join_sql = self.join_sql(join)
                parts.append(join_sql)
        
        # SELECT columns (only if not SELECT *)
        select_expressions = expression.expressions
        is_select_star = (
            len(select_expressions) == 1 
            and isinstance(select_expressions[0], exp.Star)
            and not select_expressions[0].args.get("except_")  # Star with EXCEPT needs select
        )
        
        # Handle DISTINCT - check if it's a simple DISTINCT (not DISTINCT ON)
        # Note: DISTINCT ON (col1, col2) is PostgreSQL-specific and falls back to
        # standard SQL generation. ASQL only uses "distinct" for simple DISTINCT.
        distinct_keyword = ""
        if distinct and not distinct.args.get("on"):
            distinct_keyword = "distinct "
        
        if not is_select_star and select_expressions:
            cols = ", ".join(self.sql(e) for e in select_expressions)
            parts.append(f"select {distinct_keyword}{cols}")
        elif distinct_keyword and is_select_star:
            # SELECT DISTINCT * → select distinct *
            parts.append(f"select {distinct_keyword}*")
        
        # WHERE clause
        if where:
            where_cond = self.sql(where.this)
            parts.append(f"where {where_cond}")
        
        # GROUP BY clause
        if group:
            group_cols = ", ".join(self.sql(e) for e in group.expressions)
            parts.append(f"group by {group_cols}")
        
        # HAVING clause
        if having:
            having_cond = self.sql(having.this)
            parts.append(f"having {having_cond}")
        
        # ORDER BY clause
        if order:
            order_cols = ", ".join(self.sql(e) for e in order.expressions)
            parts.append(f"order by {order_cols}")
        
        # LIMIT clause
        if limit:
            limit_val = self.sql(limit.expression)
            parts.append(f"limit {limit_val}")
        
        # OFFSET clause
        offset = expression.args.get("offset")
        if offset:
            offset_val = self.sql(offset.expression)
            parts.append(f"offset {offset_val}")
        
        return " ".join(parts)
    
    def join_sql(self, expression: exp.Join) -> str:
        """Generate ASQL join syntax with symbols.
        
        Converts SQL joins to ASQL notation:
        - INNER JOIN → &
        - LEFT [OUTER] JOIN → &?
        - RIGHT [OUTER] JOIN → ?&
        - FULL [OUTER] JOIN → ?&?
        - CROSS JOIN → cross join
        - Other (NATURAL, SEMI, ANTI) → fall back to SQL syntax
        """
        kind = (expression.args.get("kind") or "").upper()
        side = (expression.args.get("side") or "").upper()
        
        # Build the key for lookup: "LEFT OUTER", "RIGHT", "INNER", etc.
        if side and kind:
            lookup_key = f"{side} {kind}"
        elif side:
            lookup_key = side
        elif kind:
            lookup_key = kind
        else:
            lookup_key = "INNER"  # Default to INNER JOIN
        
        # Look up ASQL symbol, fall back to standard SQL syntax for unsupported types
        join_word = self.JOIN_SYMBOLS.get(lookup_key)
        if join_word is None:
            # Unsupported join type - use SQL syntax (NATURAL JOIN, SEMI JOIN, etc.)
            join_word = f"{lookup_key} join".strip().lower()
        
        # Get the join table
        table_sql = self.sql(expression.this)
        
        # Get the ON condition
        on = expression.args.get("on")
        on_sql = f" on {self.sql(on)}" if on else ""
        
        return f"{join_word} {table_sql}{on_sql}"
