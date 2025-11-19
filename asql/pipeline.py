"""Pipeline step tracking and CTE generation for ASQL."""

from typing import List, Optional
from sqlglot import exp


class PipelineStep:
    """Represents a single pipeline transformation step."""
    
    def __init__(self) -> None:
        self.from_clause: Optional[exp.From] = None
        self.where_clauses: List[exp.Where] = []
        self.joins: List[exp.Join] = []
        self.group_by: Optional[exp.Group] = None
        self.aggregations: List[exp.Expression] = []
        self.select: Optional[List[exp.Expression]] = None
        self.sort: Optional[exp.Order] = None
        self.limit: Optional[exp.Limit] = None
        self.store_name: Optional[str] = None  # Name for stored CTE
    
    def has_content(self) -> bool:
        """Check if step has any content."""
        return any([
            self.from_clause,
            self.where_clauses,
            self.joins,
            self.group_by,
            self.select,
            self.sort,
            self.limit
        ])
    
    def add_where(self, where_expr: exp.Where) -> None:
        """Add a WHERE clause to this step."""
        self.where_clauses.append(where_expr)
    
    def add_join(self, join_expr: exp.Join) -> None:
        """Add a JOIN to this step."""
        self.joins.append(join_expr)


def generate_step_name(step_number: int, step: PipelineStep) -> str:
    """
    Generate a descriptive CTE name based on the step's primary operation.
    
    Examples:
        - Step with WHERE: "1_where_status" or "1_where"
        - Step with GROUP BY: "2_group_by_country" or "2_group_by"
        - Step with JOIN: "3_join_orders" or "3_join"
    
    The name includes:
        1. Step number (for ordering)
        2. Operation type (where, group_by, join, etc.)
        3. Optional: Key column/table name (if available and not too verbose)
    """
    parts = [str(step_number)]
    
    # Determine primary operation
    if step.group_by:
        parts.append("group_by")
        # Optionally include grouping column name
        if step.group_by.expressions:
            col_name = extract_column_name(step.group_by.expressions[0])
            if col_name:
                parts.append(col_name)
    elif step.joins:
        parts.append("join")
        # Optionally include joined table name
        if step.joins[0].this:
            table_name = extract_table_name(step.joins[0].this)
            if table_name:
                parts.append(table_name)
    elif step.where_clauses:
        parts.append("where")
        # Optionally include filter column name
        if step.where_clauses[0].this:
            col_name = extract_column_name(step.where_clauses[0].this)
            if col_name:
                parts.append(col_name)
    elif step.sort:
        parts.append("sort")
    elif step.limit:
        parts.append("limit")
    elif step.select:
        parts.append("select")
    else:
        # Fallback for FROM-only step
        parts.append("from")
    
    return "_".join(parts)


def extract_column_name(expr: exp.Expression) -> Optional[str]:
    """Extract column name from expression if it's a simple identifier."""
    if isinstance(expr, exp.Column):
        if isinstance(expr.this, exp.Identifier):
            return expr.this.name
        return None
    elif isinstance(expr, exp.Identifier):
        return expr.name
    # For complex expressions, return None to keep name simple
    return None


def extract_table_name(expr: exp.Expression) -> Optional[str]:
    """Extract table name from expression if it's a simple table reference."""
    if isinstance(expr, exp.Table):
        if isinstance(expr.this, exp.Identifier):
            return expr.this.name
        return None
    elif isinstance(expr, exp.Identifier):
        return expr.name
    return None


def combine_where_clauses(where_clauses: List[exp.Where]) -> exp.Where:
    """Combine multiple WHERE clauses with AND."""
    if not where_clauses:
        raise ValueError("Cannot combine empty WHERE clauses list")
    
    if len(where_clauses) == 1:
        return where_clauses[0]
    
    # Combine with AND
    combined = where_clauses[0].this
    for where_clause in where_clauses[1:]:
        combined = exp.And(this=combined, expression=where_clause.this)
    
    return exp.Where(this=combined)


def build_select_for_step(
    step: PipelineStep, 
    previous_step_name: Optional[str]
) -> exp.Select:
    """Build a SELECT statement for a pipeline step."""
    select = exp.Select()
    
    # FROM clause: either base table or previous CTE
    # If step has its own from_clause, use it (first step)
    # Otherwise, reference previous step
    if step.from_clause:
        from_expr = step.from_clause
    elif previous_step_name:
        from_expr = exp.From(
            this=exp.Table(this=exp.Identifier(this=previous_step_name))
        )
    else:
        # This shouldn't happen, but handle gracefully
        raise ValueError("Step has no FROM clause and no previous step to reference")
    
    if from_expr:
        select.set("from_", from_expr)  # SQLGlot uses 'from_' not 'from'
    
    # Add WHERE clauses
    if step.where_clauses:
        # Combine multiple WHEREs with AND
        combined_where = combine_where_clauses(step.where_clauses)
        select.set("where", combined_where)
    
    # Add JOINs
    if step.joins:
        select.set("joins", step.joins)
    
    # Add GROUP BY
    if step.group_by:
        select.set("group", step.group_by)
        # Set SELECT expressions to grouping columns + aggregations
        expressions = []
        # Add grouping columns
        if step.group_by.expressions:
            expressions.extend(step.group_by.expressions)
        # Add aggregations
        expressions.extend(step.aggregations)
        select.set("expressions", expressions)
    
    # Add SELECT columns (if specified)
    if step.select:
        select.set("expressions", step.select)
    elif not step.group_by:
        # Default to SELECT * if no GROUP BY and no explicit SELECT
        select.set("expressions", [exp.Star()])
    
    # Add SORT (ORDER BY)
    if step.sort:
        select.set("order", step.sort)
    
    # Add LIMIT
    if step.limit:
        select.set("limit", step.limit)
    
    return select


def build_cte_pipeline(steps: List[PipelineStep]) -> exp.Select:
    """
    Build a CTE-based pipeline from a list of pipeline steps.
    
    Args:
        steps: List of PipelineStep objects representing the pipeline
    
    Returns:
        SQLGlot Select expression with WITH clause containing CTEs
    """
    if not steps:
        raise ValueError("Cannot build pipeline from empty steps list")
    
    # Build CTEs for each step
    ctes = []
    previous_step_name = None
    
    for i, step in enumerate(steps):
        # Use store_name if provided, otherwise generate descriptive CTE name
        if step.store_name:
            step_name = step.store_name
        else:
            step_name = generate_step_name(i + 1, step)
        
        # Create SELECT for this step
        step_select = build_select_for_step(step, previous_step_name)
        
        # Create CTE
        cte = exp.CTE(
            this=step_select,
            alias=exp.TableAlias(this=exp.Identifier(this=step_name))
        )
        ctes.append(cte)
        previous_step_name = step_name
    
    # Create final SELECT that uses the last CTE
    final_select = exp.Select()
    final_select.set("expressions", [exp.Star()])  # Or specific columns
    final_select.set("from_", exp.From(
        this=exp.Table(this=exp.Identifier(this=previous_step_name))
    ))
    
    # Attach WITH clause with all CTEs (SQLGlot uses 'with_' not 'with' because 'with' is a Python keyword)
    final_select.set("with_", exp.With(expressions=ctes))
    
    return final_select

