"""ASQL custom expression types.

These extend SQLGlot's expression system with ASQL-specific AST nodes.
"""

from __future__ import annotations

from sqlglot import exp


__all__ = ["Spine", "CohortBy"]


class Spine(exp.Func):
    """Mark a column for gap-filling spine treatment.
    
    Used in GROUP BY to indicate a column should have gap-filling applied:
    - spine by month(created_at) → GROUP BY Spine(month(created_at))
    - group by spine(month(created_at)), region → GROUP BY Spine(month(created_at)), region
    
    The spine transform processes these nodes to generate gap-filling CTEs.
    
    For date columns: generates date sequence (generate_series or equivalent)
    For categorical: generates DISTINCT values from data
    """
    arg_types = {"this": True}
    
    @property
    def output_name(self) -> str:
        """Return the output name for this spine column."""
        inner = self.this
        if isinstance(inner, exp.Alias):
            return inner.alias
        if hasattr(inner, 'output_name'):
            return inner.output_name
        return ""


class CohortBy(exp.Expression):
    """Cohort analysis clause.
    
    Syntax: cohort by month(users.signup_date) on user_id
    
    This replaces the _cohort_info attribute hack with a proper AST node.
    The cohort transform reads this clause and generates:
    - cohort_base CTE (user → cohort mapping)
    - cohort_sizes CTE (cohort → size)
    - JOINs to attach cohort info
    - Modified GROUP BY and SELECT
    
    Args:
        this: The cohort column expression (e.g., month(users.signup_date))
        granularity: Time granularity string ("month", "week", "day")
        join_key: Column to join on (e.g., user_id)
        segments: Optional list of segment expressions
    """
    arg_types = {
        "this": True,           # Cohort column expression
        "granularity": False,   # Granularity string literal
        "join_key": False,      # Join key column/identifier
        "segments": False,      # List of segment expressions
    }
    
    @property
    def cohort_column(self) -> exp.Expression:
        """Get the cohort column expression."""
        return self.this
    
    @property
    def granularity_value(self) -> str | None:
        """Get the granularity as a string."""
        gran = self.args.get("granularity")
        if isinstance(gran, exp.Literal):
            return gran.this
        return None
    
    @property
    def join_key_value(self) -> str | None:
        """Get the join key as a string."""
        key = self.args.get("join_key")
        if isinstance(key, exp.Identifier):
            return key.name
        if isinstance(key, exp.Column):
            return key.name
        if isinstance(key, str):
            return key
        return None
