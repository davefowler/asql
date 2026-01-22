"""ASQL custom expression types.

These extend SQLGlot's expression system with ASQL-specific AST nodes.
"""

from __future__ import annotations

from sqlglot import exp


__all__ = ["Spine"]


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
