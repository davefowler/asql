"""Reusable column aliases - allow referencing earlier aliases in SELECT.

This module implements the ability to reference column aliases defined earlier
in the same SELECT clause, eliminating one of SQL's most frustrating limitations.

For DuckDB: Emits directly (native support)
For other dialects: Generates CTE chain to simulate alias reuse
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

from sqlglot import exp

from asql.errors import ASQLCompilationError


def _extract_alias_name(expr: exp.Expression) -> Optional[str]:
    """Extract alias name from a SELECT expression.
    
    Returns the alias name if the expression has one, otherwise None.
    """
    if isinstance(expr, exp.Alias):
        alias = expr.alias
        if isinstance(alias, exp.Identifier):
            return alias.name
        elif isinstance(alias, str):
            return alias
    return None


def _is_bare_column(expr: exp.Expression) -> bool:
    """Check if expression is a bare column reference (no computation).
    
    These are already included in SELECT * and should not be duplicated.
    """
    return isinstance(expr, exp.Column)


def _find_column_references(expr: exp.Expression) -> List[str]:
    """Find all column references in an expression.
    
    Returns a list of column names referenced in the expression.
    Only returns unqualified column names (no table prefix).
    """
    column_names: List[str] = []
    
    def visit(node: exp.Expression) -> None:
        """Recursively visit AST nodes to find column references."""
        if isinstance(node, exp.Column):
            # Only include unqualified columns (no table prefix)
            if not node.table:
                col_name = node.name
                if isinstance(col_name, exp.Identifier):
                    column_names.append(col_name.name)
                elif isinstance(col_name, str):
                    column_names.append(col_name)
        else:
            # Recursively visit children
            for child in node.iter_expressions():
                visit(child)
    
    visit(expr)
    return column_names


def _build_alias_dependency_graph(
    select: exp.Select,
) -> Tuple[Dict[str, Set[str]], Dict[str, exp.Expression]]:
    """Build dependency graph of aliases in SELECT expressions.
    
    Processes SELECT expressions left to right and tracks:
    1. Which aliases are defined
    2. Which earlier aliases each expression references
    
    Returns:
        Tuple of (dependencies dict, alias_to_expr dict)
        - dependencies: maps alias_name -> set of referenced alias names
        - alias_to_expr: maps alias_name -> expression that defines it
    """
    dependencies: Dict[str, Set[str]] = defaultdict(set)
    alias_to_expr: Dict[str, exp.Expression] = {}
    defined_aliases: Set[str] = set()
    
    for expr in select.expressions:
        # Extract alias name for this expression
        alias_name = _extract_alias_name(expr)
        
        if alias_name:
            # Find column references in this expression
            referenced_columns = _find_column_references(expr)
            
            # Check which referenced columns are earlier aliases
            referenced_aliases = {
                col for col in referenced_columns 
                if col in defined_aliases
            }
            
            if referenced_aliases:
                dependencies[alias_name] = referenced_aliases
            
            # Track this alias as defined
            defined_aliases.add(alias_name)
            alias_to_expr[alias_name] = expr
    
    return dependencies, alias_to_expr


def _detect_circular_dependencies(
    dependencies: Dict[str, Set[str]],
) -> Optional[List[str]]:
    """Detect circular dependencies in alias references.
    
    Returns a cycle if found, otherwise None.
    Uses DFS to detect cycles.
    """
    visited: Set[str] = set()
    rec_stack: Set[str] = set()
    path: List[str] = []
    
    def has_cycle(node: str) -> Optional[List[str]]:
        """DFS to detect cycle."""
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in dependencies.get(node, set()):
            if neighbor not in visited:
                cycle = has_cycle(neighbor)
                if cycle:
                    return cycle
            elif neighbor in rec_stack:
                # Found a cycle - return the cycle path
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]
        
        rec_stack.remove(node)
        path.pop()
        return None
    
    for alias in dependencies:
        if alias not in visited:
            cycle = has_cycle(alias)
            if cycle:
                return cycle
    
    return None


def _has_alias_dependencies(select: exp.Select) -> bool:
    """Check if SELECT has any alias dependencies (references to earlier aliases)."""
    dependencies, _ = _build_alias_dependency_graph(select)
    return len(dependencies) > 0


def _is_duckdb_dialect(dialect: Optional[str]) -> bool:
    """Check if the dialect is DuckDB."""
    if not dialect:
        return False
    dialect_lower = dialect.lower()
    return dialect_lower == "duckdb"


def _generate_cte_chain_with_prefix(
    select: exp.Select,
    dependencies: Dict[str, Set[str]],
    alias_to_expr: Dict[str, exp.Expression],
    cte_prefix: str,
) -> exp.Select:
    """Generate CTE chain for non-DuckDB dialects with unique prefix.
    
    Creates a chain of CTEs where each CTE adds expressions that can be computed
    (all their dependencies are available). The final CTE applies WHERE/ORDER BY/etc.
    
    Args:
        cte_prefix: Unique prefix for CTE names (e.g., "_alias0") to avoid conflicts
    """
    # Process expressions in order, grouping them by when they can be computed
    # Expressions can be computed when all their alias dependencies are available
    
    # Map each expression to its alias (if any) and find its dependencies
    # We need to process expressions in order to track which aliases are defined
    expr_to_alias: Dict[exp.Expression, Optional[str]] = {}
    expr_dependencies: Dict[exp.Expression, Set[str]] = {}
    
    defined_aliases: Set[str] = set()
    for expr in select.expressions:
        alias_name = _extract_alias_name(expr)
        expr_to_alias[expr] = alias_name
        
        # Find column references in this expression
        referenced_columns = _find_column_references(expr)
        # Check which referenced columns are earlier aliases
        referenced_aliases = {
            col for col in referenced_columns 
            if col in defined_aliases
        }
        expr_dependencies[expr] = referenced_aliases
        
        # Track this alias as defined (after checking dependencies)
        if alias_name:
            defined_aliases.add(alias_name)
    
    # Build expression groups: each group contains expressions that can be computed
    # at the same step (no dependencies on each other within the group)
    expression_groups: List[List[exp.Expression]] = []
    processed_aliases: Set[str] = set()
    
    remaining_expressions = list(select.expressions)
    
    while remaining_expressions:
        # Find expressions that can be computed now (all dependencies satisfied)
        ready_expressions: List[exp.Expression] = []
        remaining_after = []
        
        for expr in remaining_expressions:
            # Check if all dependencies are satisfied
            deps = expr_dependencies[expr]
            if deps.issubset(processed_aliases):
                ready_expressions.append(expr)
            else:
                remaining_after.append(expr)
        
        if not ready_expressions:
            # Should not happen if circular dependencies were caught
            raise ASQLCompilationError(
                "Cannot resolve alias dependencies - possible circular reference"
            )
        
        expression_groups.append(ready_expressions)
        
        # Mark aliases as processed
        for expr in ready_expressions:
            alias_name = expr_to_alias[expr]
            if alias_name:
                processed_aliases.add(alias_name)
        
        remaining_expressions = remaining_after
    
    # Build CTE chain with unique names
    ctes: List[exp.CTE] = []
    base_cte_name = f"{cte_prefix}_0"
    prev_cte_name = base_cte_name
    
    # First CTE: base query with first group of expressions
    # Include SELECT * to preserve all base columns, plus computed expressions (not bare columns)
    # Bare column references are already included in SELECT * and should not be duplicated
    computed_exprs_0 = [e for e in expression_groups[0] if not _is_bare_column(e)]
    base_select = select.copy()
    base_select.set("expressions", [exp.Star(), *computed_exprs_0])
    
    # Remove WHERE/ORDER BY/etc. from base - they'll go in final CTE
    base_select.set("where", None)
    base_select.set("order", None)
    base_select.set("limit", None)
    base_select.set("having", None)
    base_select.set("qualify", None)
    
    # Get FROM clause from original (use from_ which is the correct sqlglot key)
    if not base_select.args.get("from_"):
        # Need to preserve FROM from original
        if select.args.get("from_"):
            base_select.set("from_", select.args["from_"].copy())
    
    ctes.append(
        exp.CTE(
            this=base_select,
            alias=exp.TableAlias(this=exp.Identifier(this=base_cte_name, quoted=False)),
        )
    )
    
    # Subsequent CTEs: add expressions from remaining groups
    for step_num, expr_group in enumerate(expression_groups[1:], start=1):
        step_name = f"{cte_prefix}_{step_num}"
        
        # Build SELECT for this step: SELECT *, new_expressions FROM prev_step
        # Filter out bare column references (already in SELECT *)
        computed_exprs = [e for e in expr_group if not _is_bare_column(e)]
        step_select = exp.Select()
        step_select.set("expressions", [
            exp.Star(),  # SELECT * from previous step
            *computed_exprs,  # Plus the new computed expressions
        ])
        step_select.set(
            "from_",
            exp.From(
                this=exp.Table(
                    this=exp.Identifier(this=prev_cte_name, quoted=False)
                )
            )
        )
        
        ctes.append(
            exp.CTE(
                this=step_select,
                alias=exp.TableAlias(this=exp.Identifier(this=step_name, quoted=False)),
            )
        )
        
        prev_cte_name = step_name
    
    # Final SELECT: apply WHERE/ORDER BY/etc. from original query
    # Select only the columns from the original SELECT (not SELECT * which would include base columns)
    final_expressions: List[exp.Expression] = []
    for orig_expr in select.expressions:
        alias_name = _extract_alias_name(orig_expr)
        if alias_name:
            # Reference the computed alias from the CTE chain
            final_expressions.append(
                exp.Column(this=exp.Identifier(this=alias_name, quoted=False))
            )
        else:
            # For non-aliased expressions (like bare column references), copy as-is
            final_expressions.append(orig_expr.copy())
    
    final_select = exp.Select()
    final_select.set("expressions", final_expressions)
    final_select.set(
        "from_",
        exp.From(
            this=exp.Table(
                this=exp.Identifier(this=prev_cte_name, quoted=False)
            )
        )
    )
    
    # Copy clauses from original SELECT
    if select.args.get("where"):
        final_select.set("where", select.args["where"].copy())
    if select.args.get("order"):
        final_select.set("order", select.args["order"].copy())
    if select.args.get("limit"):
        final_select.set("limit", select.args["limit"].copy())
    if select.args.get("having"):
        final_select.set("having", select.args["having"].copy())
    if select.args.get("qualify"):
        final_select.set("qualify", select.args["qualify"].copy())
    
    # Wrap in WITH clause
    with_expr = exp.With(expressions=ctes)
    final_select.set("with_", with_expr)
    
    return final_select


# Global counter for unique CTE names across multiple transformations
_cte_counter: int = 0


def _get_unique_cte_prefix() -> str:
    """Get a unique prefix for CTE names to avoid conflicts."""
    global _cte_counter
    prefix = f"_alias{_cte_counter}"
    _cte_counter += 1
    return prefix


def _transform_select_alias_reuse(
    select: exp.Select,
    dialect: Optional[str],
    cte_prefix: str,
) -> exp.Select:
    """Transform a single SELECT statement for alias reuse.
    
    Returns the transformed SELECT with CTE chain if needed.
    """
    # Check if there are any alias dependencies
    if not _has_alias_dependencies(select):
        return select
    
    # Build dependency graph
    dependencies, alias_to_expr = _build_alias_dependency_graph(select)
    
    # Detect circular dependencies
    cycle = _detect_circular_dependencies(dependencies)
    if cycle:
        cycle_str = " -> ".join(cycle)
        raise ASQLCompilationError(
            f"Circular dependency detected in alias references: {cycle_str}"
        )
    
    # For DuckDB: emit as-is (native support)
    if _is_duckdb_dialect(dialect):
        return select
    
    # For other dialects: generate CTE chain with unique prefix
    return _generate_cte_chain_with_prefix(select, dependencies, alias_to_expr, cte_prefix)


def apply_alias_reuse(
    statement: exp.Expression,
    dialect: Optional[str] = None,
) -> exp.Expression:
    """Apply alias reuse transformation.
    
    For DuckDB: Emits as-is (native support)
    For other dialects: Generates CTE chain
    
    This function recursively processes CTEs to handle alias reuse
    in nested queries (e.g., stash as).
    
    Args:
        statement: SQLGlot expression (typically a SELECT statement)
        dialect: Target SQL dialect name
        
    Returns:
        Modified statement with alias reuse applied (or original if no dependencies)
    """
    if not isinstance(statement, exp.Select):
        return statement
    
    # First, recursively process any existing CTEs in the statement
    with_clause = statement.args.get("with_")
    if with_clause and hasattr(with_clause, "expressions"):
        for cte in with_clause.expressions:
            if isinstance(cte, exp.CTE) and isinstance(cte.this, exp.Select):
                cte_select = cte.this
                # Transform the CTE's SELECT if it has alias dependencies
                if _has_alias_dependencies(cte_select):
                    cte_prefix = _get_unique_cte_prefix()
                    transformed = _transform_select_alias_reuse(cte_select, dialect, cte_prefix)
                    # If transformation generated CTEs, we need to merge them
                    # For now, replace the CTE's expression
                    cte.set("this", transformed)
    
    # Now process the main SELECT
    cte_prefix = _get_unique_cte_prefix()
    return _transform_select_alias_reuse(statement, dialect, cte_prefix)
