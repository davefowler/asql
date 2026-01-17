"""ASQL Generator.

Converts SQLGlot AST back to ASQL syntax.
"""

import typing as t

from sqlglot import exp
from sqlglot.generator import Generator


class ASQLGenerator(Generator):
    """Generator for ASQL. Converts SQLGlot AST back to ASQL syntax.
    
    Handles ASQL-specific output formatting:
    - CAST(x AS TYPE) → x::TYPE
    - WITH cte AS (...) → from ... stash as cte
    - SELECT * FROM → from
    - Joins with symbols: INNER JOIN → &
    """
    
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
    
    def cast_sql(self, expression: exp.Cast, safe_prefix: t.Optional[str] = None) -> str:
        """Generate ASQL :: cast syntax instead of CAST(... AS ...).
        
        Note: safe_prefix (for TRY_CAST) is intentionally ignored - ASQL uses
        the same :: syntax for both CAST and TRY_CAST, leaving error handling
        to the target dialect during compilation.
        """
        expr_sql = self.sql(expression, "this")
        type_sql = self.sql(expression, "to")
        return f"{expr_sql}::{type_sql}"
    
    def with_sql(self, expression: exp.With) -> str:
        """Convert CTEs to stash statements for ASQL output.
        
        WITH cte AS (SELECT ...) SELECT ... FROM cte
        →
        from ... stash as cte
        
        from cte
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
        
        return "\n\n".join(cte_parts)
    
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
            limit_val = self.sql(limit.this)
            parts.append(f"limit {limit_val}")
        
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
