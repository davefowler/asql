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
        self.qualify: Optional[exp.Expression] = None  # QUALIFY clause for window function filtering
        self.distinct_on: Optional[List[exp.Expression]] = None  # DISTINCT ON columns
        # Window operations: per <partition> <op> by <order> [as <alias>]
        # Or standalone: <op> by <order> [as <alias>]
        # Operations: first, last (filter), number, rank, dense_rank (add column)
        # Structure: {"op": str, "order": List[exp], "partition": List[exp], "alias": Optional[str]}
        self.window_op: Optional[dict] = None
    
    def has_content(self) -> bool:
        """Check if step has any content."""
        return any([
            self.from_clause,
            self.where_clauses,
            self.joins,
            self.group_by,
            self.select,
            self.sort,
            self.limit,
            self.qualify,
            self.distinct_on,
            self.window_op
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


def merge_steps(step1: PipelineStep, step2: PipelineStep) -> PipelineStep:
    """
    Merge two pipeline steps into one.
    
    Args:
        step1: First step (will be modified)
        step2: Second step (will be merged into step1)
    
    Returns:
        Merged step (step1 with step2's content added)
    """
    # Merge WHERE clauses
    step1.where_clauses.extend(step2.where_clauses)
    
    # Merge JOINs
    step1.joins.extend(step2.joins)
    
    # GROUP BY: step2's GROUP BY replaces step1's (shouldn't happen in practice)
    if step2.group_by:
        step1.group_by = step2.group_by
        step1.aggregations = step2.aggregations
    
    # SELECT: step2's SELECT replaces step1's (last SELECT wins)
    if step2.select:
        step1.select = step2.select
    
    # SORT: step2's SORT replaces step1's (last SORT wins)
    if step2.sort:
        step1.sort = step2.sort
    
    # LIMIT: step2's LIMIT replaces step1's (last LIMIT wins)
    if step2.limit:
        step1.limit = step2.limit
    
    # STASH AS: step2's store_name replaces step1's (last STASH AS wins)
    if step2.store_name:
        step1.store_name = step2.store_name
    
    # QUALIFY: step2's qualify replaces step1's (last QUALIFY wins)
    if step2.qualify:
        step1.qualify = step2.qualify
    
    # DISTINCT ON: step2's distinct_on replaces step1's
    if step2.distinct_on:
        step1.distinct_on = step2.distinct_on
    
    # WINDOW OP: step2's window_op replaces step1's
    if step2.window_op:
        step1.window_op = step2.window_op
    
    return step1


def step_requires_separate_cte(step: PipelineStep) -> bool:
    """
    Determine if a step requires its own CTE.
    
    A step needs a separate CTE if:
    - It has GROUP BY (aggregation changes the shape)
    - It has STASH AS (explicit CTE name)
    - It has QUALIFY (window filter needs subquery)
    - It has DISTINCT ON (needs subquery for non-postgres dialects)
    - It has WINDOW OP (window operation needs subquery)
    
    Returns:
        True if step needs separate CTE, False otherwise
    """
    return (
        step.group_by is not None or 
        step.store_name is not None or
        step.qualify is not None or
        step.distinct_on is not None or
        step.window_op is not None
    )


def is_simple_from_step(step: PipelineStep) -> bool:
    """
    Check if a step is just a simple FROM with no other operations.
    
    A simple FROM step can be inlined directly instead of creating a CTE.
    
    Returns:
        True if step is just FROM (no WHERE, JOIN, GROUP BY, SORT, LIMIT, SELECT, etc.)
    """
    return (
        step.from_clause is not None and
        not step.where_clauses and
        not step.joins and
        not step.group_by and
        not step.sort and
        not step.limit and
        not step.select and
        not step.store_name and
        not step.qualify and
        not step.distinct_on and
        not step.window_op
    )


def build_select_for_step(
    step: PipelineStep, 
    previous_step_name: Optional[str] = None,
    previous_step: Optional[PipelineStep] = None
) -> exp.Select:
    """
    Build a SELECT statement for a pipeline step.
    
    Args:
        step: The step to build SELECT for
        previous_step_name: Name of previous CTE (if previous step has a CTE)
        previous_step: Previous step object (if we want to inline it instead of using CTE)
    """
    select = exp.Select()
    
    # FROM clause: either base table, previous CTE, or inline previous step
    if step.from_clause:
        from_expr = step.from_clause
    elif previous_step and is_simple_from_step(previous_step):
        # Inline the simple FROM step directly instead of using CTE
        from_expr = previous_step.from_clause
    elif previous_step_name:
        from_expr = exp.From(
            this=exp.Table(this=exp.Identifier(this=previous_step_name))
        )
    else:
        # This shouldn't happen, but handle gracefully
        raise ValueError("Step has no FROM clause and no previous step to reference")
    
    if from_expr:
        # SQLGlot 28+ uses 'from_' as the key (Python keyword escaping)
        select.set("from_", from_expr)
    
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
    
    # Handle QUALIFY clause
    # QUALIFY is a post-window filter that runs after window functions
    # Some dialects (BigQuery, Snowflake, DuckDB) support it natively
    # For others, we wrap in a subquery and filter on the window result
    if step.qualify:
        select.set("qualify", exp.Qualify(this=step.qualify))
    
    # Handle DISTINCT ON
    # PostgreSQL supports DISTINCT ON natively
    # For other dialects, we use ROW_NUMBER() and filter
    if step.distinct_on:
        select.set("distinct", exp.Distinct(on=exp.Tuple(expressions=step.distinct_on)))
    
    # Handle WINDOW OP (per ... <op> by ... or standalone <op> by ...)
    # Operations: first/last (filter), number/rank/dense_rank (add column)
    if step.window_op:
        op = step.window_op.get("op", "first")
        order_cols = step.window_op.get("order", [])
        partition_cols = step.window_op.get("partition", [])
        alias = step.window_op.get("alias")
        
        # Determine the window function based on operation
        if op == "number":
            window_func = exp.RowNumber()
            default_alias = alias or "row_num"
        elif op == "rank":
            window_func = exp.Rank()
            default_alias = alias or "rank"
        elif op == "dense_rank":
            window_func = exp.DenseRank()
            default_alias = alias or "dense_rank"
        elif op in ("first", "last"):
            window_func = exp.RowNumber()
            default_alias = "_rn"  # Internal, used for filtering
        else:
            # Unknown op, default to row_number
            window_func = exp.RowNumber()
            default_alias = alias or "row_num"
        
        # Build window expression
        window = exp.Window(this=window_func)
        
        if partition_cols:
            window.set("partition_by", partition_cols)
        
        if order_cols:
            # For "last", reverse the order direction
            if op == "last":
                reversed_order = []
                for col in order_cols:
                    if isinstance(col, exp.Ordered):
                        reversed_order.append(exp.Ordered(this=col.this, desc=not col.args.get("desc", False)))
                    else:
                        reversed_order.append(exp.Ordered(this=col, desc=True))
                window.set("order", exp.Order(expressions=reversed_order))
            else:
                window.set("order", exp.Order(expressions=order_cols))
        
        # Add the window function as a select column
        window_alias = exp.Alias(this=window, alias=exp.Identifier(this=default_alias))
        current_expressions = select.args.get("expressions", [])
        select.set("expressions", current_expressions + [window_alias])
        
        # For first/last, add QUALIFY to filter to first row
        if op in ("first", "last"):
            qualify_condition = exp.EQ(
                this=exp.Column(this=exp.Identifier(this=default_alias)),
                expression=exp.Literal.number(1)
            )
            select.set("qualify", exp.Qualify(this=qualify_condition))
    
    return select


def build_cte_pipeline(steps: List[PipelineStep]) -> exp.Select:
    """
    Build a CTE-based pipeline from a list of pipeline steps.
    
    Optimizes by merging consecutive steps that don't require separate CTEs.
    A step requires a separate CTE if it has GROUP BY or STASH AS.
    
    Args:
        steps: List of PipelineStep objects representing the pipeline
    
    Returns:
        SQLGlot Select expression with WITH clause containing CTEs (or without CTEs if single simple step)
    """
    if not steps:
        raise ValueError("Cannot build pipeline from empty steps list")
    
    # Merge consecutive steps that don't require separate CTEs
    merged_steps: List[PipelineStep] = []
    i = 0
    
    while i < len(steps):
        current_step = steps[i]
        
        # Try to merge with following steps until we hit one that requires a separate CTE
        j = i + 1
        while j < len(steps):
            next_step = steps[j]
            
            # If next step requires separate CTE, stop merging
            if step_requires_separate_cte(next_step):
                break
            
            # If current step requires separate CTE, stop merging
            if step_requires_separate_cte(current_step):
                break
            
            # Merge next_step into current_step
            current_step = merge_steps(current_step, next_step)
            j += 1
        
        merged_steps.append(current_step)
        i = j
    
    # Optimization: If there's only one merged step and it doesn't require a CTE,
    # skip CTE creation and return the SELECT directly
    if len(merged_steps) == 1:
        single_step = merged_steps[0]
        # If it doesn't require a separate CTE (no GROUP BY, no STORE AS), return directly
        if not step_requires_separate_cte(single_step):
            return build_select_for_step(single_step, None)
    
    # Build CTEs for each merged step
    # Only create CTEs for steps that actually need them
    # Simple FROM steps can be inlined directly into the next step
    ctes = []
    previous_step_name: Optional[str] = None
    previous_step: Optional[PipelineStep] = None
    
    for i, step in enumerate(merged_steps):
        # Check if this step needs a CTE
        needs_cte = step_requires_separate_cte(step)
        
        # Determine what to use as the "previous" reference
        # If previous step is a simple FROM that wasn't CTE'd, we can inline it
        prev_step_for_inline = None
        if previous_step and is_simple_from_step(previous_step) and not previous_step_name:
            prev_step_for_inline = previous_step
        
        # Create SELECT for this step
        step_select = build_select_for_step(
            step, 
            previous_step_name=previous_step_name,
            previous_step=prev_step_for_inline
        )
        
        # Decide if we need to create a CTE for this step
        # We need a CTE if:
        # 1. Step has STASH AS (explicit CTE name)
        # 2. Next step will reference this one AND this isn't a simple FROM (can be inlined)
        # Note: GROUP BY doesn't automatically require a CTE - only if it will be referenced
        is_simple_from = is_simple_from_step(step)
        will_be_referenced = i < len(merged_steps) - 1  # Not the last step
        is_last_step = i == len(merged_steps) - 1
        
        # STASH AS always requires a CTE
        if step.store_name:
            step_name = step.store_name
            cte = exp.CTE(
                this=step_select,
                alias=exp.TableAlias(this=exp.Identifier(this=step_name))
            )
            ctes.append(cte)
            previous_step_name = step_name
            previous_step = None
            
            # If this is the last step with stash as, create final SELECT
            if is_last_step:
                final_select = exp.Select()
                final_select.set("expressions", [exp.Star()])
                final_select.set("from_", exp.From(
                    this=exp.Table(this=exp.Identifier(this=step_name))
                ))
                final_select.set("with_", exp.With(expressions=ctes))
                return final_select
        elif will_be_referenced and not is_simple_from:
            # Next step will reference this one, and it's not a simple FROM (can't be inlined)
            # Create CTE for this step
            step_name = generate_step_name(len(ctes) + 1, step)
            cte = exp.CTE(
                this=step_select,
                alias=exp.TableAlias(this=exp.Identifier(this=step_name))
            )
            ctes.append(cte)
            previous_step_name = step_name
            previous_step = None
        elif is_last_step:
            # This is the last step - return it directly without CTE wrapper
            # (unless we have existing CTEs that need to be referenced)
            if ctes:
                # We have previous CTEs - need to wrap this in a CTE and select from it
                step_name = generate_step_name(len(ctes) + 1, step)
                cte = exp.CTE(
                    this=step_select,
                    alias=exp.TableAlias(this=exp.Identifier(this=step_name))
                )
                ctes.append(cte)
                # Create final SELECT that references the last CTE
                final_select = exp.Select()
                final_select.set("expressions", [exp.Star()])
                final_select.set("from_", exp.From(
                    this=exp.Table(this=exp.Identifier(this=step_name))
                ))
                final_select.set("with_", exp.With(expressions=ctes))
                return final_select
            else:
                # No CTEs, last step - return it directly
                return step_select
        else:
            # No CTE needed - this step will be inlined into the next one
            previous_step = step
            # Keep previous_step_name as is (might be None if this is first step)
    
    # If we get here, we didn't return early (shouldn't happen, but handle gracefully)
    # Return the last step's SELECT
    last_step = merged_steps[-1]
    return build_select_for_step(last_step, previous_step_name, previous_step)

