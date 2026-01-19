"""Auto-aliasing for function calls without explicit aliases.

This module implements Phase 1 (prefix-based) and Phase 2 (template-based)
auto-aliasing for ASQL function calls.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
import re

from jinja2 import Environment
from sqlglot import exp

from asql.config import CompileSettings


# Default prefixes for common functions
DEFAULT_PREFIXES: Dict[str, str] = {
    "count": "num",
    "row_number": "row_num",
    "running_count": "running_num",
    "distinct_count": "uniq",
}


def _get_column_name_from_expr(expr: exp.Expression) -> Optional[str]:
    """Extract column name from an expression.
    
    Returns the column name if the expression is a simple column reference,
    otherwise returns None (indicating a complex expression).
    """
    if isinstance(expr, exp.Column):
        return expr.name
    elif isinstance(expr, exp.Identifier):
        return expr.name
    elif isinstance(expr, exp.Star):
        return None  # count(*) has no column
    return None


def _get_function_prefix(
    func_name: str,
    settings: CompileSettings,
) -> str:
    """Get the prefix for a function name.
    
    Checks function-specific prefix first, then falls back to default prefix,
    then to the function name itself.
    """
    # Check configured prefix
    if func_name in settings.alias_prefixes:
        return settings.alias_prefixes[func_name]
    
    # Check default prefixes
    if func_name in DEFAULT_PREFIXES:
        return DEFAULT_PREFIXES[func_name]
    
    # Fall back to function name
    return func_name


def _extract_template_variables(
    func_call: exp.Func,
    func_name: str,
    prefix: str,
) -> Dict[str, Any]:
    """Extract template variables from a function call.
    
    Returns a dictionary with template variables:
    - func: function name
    - prefix: configured prefix
    - col: shorthand for arg1 (single-arg only)
    - arg1, arg2, ...: function arguments
    - distinct: "distinct" if DISTINCT modifier used
    - order_by: order column if ORDER BY clause used
    - partition_by: partition column if PARTITION BY used
    """
    vars_dict: Dict[str, Any] = {
        "func": func_name,
        "prefix": prefix,
    }
    
    # Extract arguments
    # Handle typed date functions (Month, Year, etc.) that use .this instead of .expressions
    args = func_call.expressions
    is_distinct = False
    
    if not args and hasattr(func_call, "this") and func_call.this is not None:
        this_val = func_call.this
        # Handle DISTINCT modifier (e.g., COUNT(DISTINCT customer_id))
        if isinstance(this_val, exp.Distinct):
            is_distinct = True
            # Get the actual column(s) from inside DISTINCT
            args = this_val.expressions if this_val.expressions else []
        else:
            # Typed date functions like Month, Year store their arg in .this
            args = [this_val]
    
    if args:
        # Handle count(*) case - Star in args
        if len(args) == 1 and isinstance(args[0], exp.Star):
            vars_dict["arg1"] = None
            vars_dict["col"] = None
        else:
            for i, arg in enumerate(args, 1):
                col_name = _get_column_name_from_expr(arg)
                vars_dict[f"arg{i}"] = col_name or ""
                if i == 1:
                    vars_dict["col"] = col_name or ""
    else:
        vars_dict["arg1"] = None
        vars_dict["col"] = None
    
    # Extract DISTINCT modifier
    if is_distinct or (hasattr(func_call, "is_distinct") and func_call.is_distinct):
        vars_dict["distinct"] = "distinct"
    else:
        vars_dict["distinct"] = ""
    
    # Extract ORDER BY (for window functions and ordered aggregates)
    order_by_col = None
    if hasattr(func_call, "expressions") and func_call.expressions:
        # Check for ORDER BY in window function
        if hasattr(func_call, "within_group") and func_call.within_group:
            order_exprs = func_call.within_group.expressions if hasattr(func_call.within_group, "expressions") else []
            if order_exprs:
                order_by_col = _get_column_name_from_expr(order_exprs[0])
        # Check for ORDER BY in OVER clause
        if hasattr(func_call, "over") and func_call.over:
            if hasattr(func_call.over, "order") and func_call.over.order:
                order_exprs = func_call.over.order.expressions if hasattr(func_call.over.order, "expressions") else []
                if order_exprs:
                    order_by_col = _get_column_name_from_expr(order_exprs[0])
    
    vars_dict["order_by"] = order_by_col or ""
    
    # Extract PARTITION BY (for window functions)
    partition_by_col = None
    if hasattr(func_call, "over") and func_call.over:
        if hasattr(func_call.over, "partition") and func_call.over.partition:
            partition_exprs = func_call.over.partition.expressions if hasattr(func_call.over.partition, "expressions") else []
            if partition_exprs:
                partition_by_col = _get_column_name_from_expr(partition_exprs[0])
    
    vars_dict["partition_by"] = partition_by_col or ""
    
    return vars_dict


def _convert_to_jinja_syntax(template: str) -> str:
    """Convert {var} and {var|filter} syntax to Jinja2 {{ var }} and {{ var|filter }} syntax."""
    # Convert {variable|filter} patterns to {{ variable|filter }}
    # But don't convert {{ which is already Jinja2 escape syntax
    result = re.sub(r'(?<!\{)\{([^{}]+)\}(?!\})', r'{{ \1 }}', template)
    return result


def _render_template(
    template: str,
    vars_dict: Dict[str, Any],
) -> str:
    """Render template using Jinja2.
    
    Accepts templates in simplified {var} syntax or Jinja2 {{ var }} syntax.
    
    Args:
        template: Template string with {var} or {{ var }} syntax
        vars_dict: Dictionary of template variables
        
    Returns:
        Rendered alias string
    """
    # Convert {var} syntax to Jinja2 {{ var }} syntax
    jinja_template_str = _convert_to_jinja_syntax(template)
    
    # Create Jinja2 environment with custom filters
    env = Environment()
    
    def lower_filter(value: Any) -> str:
        return str(value).lower() if value else ""
    
    def upper_filter(value: Any) -> str:
        return str(value).upper() if value else ""
    
    def title_filter(value: Any) -> str:
        return str(value).title() if value else ""
    
    def camel_filter(value: Any) -> str:
        """Convert to camelCase."""
        if not value:
            return ""
        parts = str(value).split("_")
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
    
    def snake_filter(value: Any) -> str:
        """Convert to snake_case."""
        if not value:
            return ""
        # Insert _ before uppercase letters
        return re.sub(r'(?<!^)(?=[A-Z])', '_', str(value)).lower()
    
    env.filters["lower"] = lower_filter
    env.filters["upper"] = upper_filter
    env.filters["title"] = title_filter
    env.filters["camel"] = camel_filter
    env.filters["snake"] = snake_filter
    
    jinja_template = env.from_string(jinja_template_str)
    result = jinja_template.render(**vars_dict)
    
    # Clean up double underscores and trailing/leading underscores
    result = re.sub(r'_+', '_', result)
    result = result.strip('_')
    
    return result


def _get_function_name(func_call: exp.Func) -> str:
    """Get the function name from a Function expression."""
    # sql_name() handles most cases
    name = func_call.sql_name()
    if name:
        return name.lower()
    
    # Fallback to this.name or this.this.name
    if hasattr(func_call, "this"):
        if isinstance(func_call.this, exp.Identifier):
            return func_call.this.name.lower()
        elif hasattr(func_call.this, "name"):
            return func_call.this.name.lower()
    
    # Last resort: use the class name
    class_name = func_call.__class__.__name__.lower()
    if class_name.endswith("function"):
        return class_name[:-8]  # Remove "Function" suffix
    
    # If we get here, sql_name() returned empty and the class doesn't follow
    # the "XxxFunction" naming convention. This is unexpected - surface it.
    raise ValueError(
        f"Cannot determine function name for {func_call.__class__.__name__}. "
        f"sql_name() returned empty and class name doesn't end with 'Function'."
    )


def _generate_alias(
    func_call: exp.Func,
    func_name: str,
    settings: CompileSettings,
) -> Optional[str]:
    """Generate an alias for a function call.
    
    Precedence:
    1. Function-specific template (highest priority)
    2. Function-specific prefix + default template
    3. Default template with function's default prefix
    4. Fallback to simple prefix-based generation
    
    Returns None if no alias can be generated (e.g., complex expressions).
    """
    prefix = _get_function_prefix(func_name, settings)
    vars_dict = _extract_template_variables(func_call, func_name, prefix)
    
    # Special case: count(*) should use prefix only if template allows it
    # Note: For Count(*), the Star is stored in .this, not .expressions
    is_count_star = (
        func_name.lower() == "count" and 
        (
            (len(func_call.expressions) == 1 and isinstance(func_call.expressions[0], exp.Star)) or
            (hasattr(func_call, "this") and isinstance(func_call.this, exp.Star))
        )
    )
    
    # Precedence 1: Function-specific template
    if func_name in settings.alias_templates:
        template = settings.alias_templates[func_name]
        alias = _render_template(template, vars_dict)
        if alias:
            return alias
    
    # Precedence 2: Function-specific prefix + default template
    if func_name in settings.alias_prefixes and settings.alias_template:
        template = settings.alias_template
        alias = _render_template(template, vars_dict)
        if alias:
            return alias
    
    # Precedence 3: Default template
    if settings.alias_template:
        template = settings.alias_template
        alias = _render_template(template, vars_dict)
        if alias:
            return alias
    
    # Fallback: Simple prefix-based generation (Phase 1)
    # Default pattern: {prefix}_{col} for single-arg, {prefix}_{arg1}_{arg2} for multi-arg
    if is_count_star:
        # count(*) -> just prefix (e.g., "num")
        return prefix
    
    if vars_dict.get("col"):
        # Single-arg function with column: prefix_col
        return f"{prefix}_{vars_dict['col']}"
    elif vars_dict.get("arg1"):
        # Multi-arg function: prefix_arg1_arg2...
        parts = [prefix]
        i = 1
        while f"arg{i}" in vars_dict and vars_dict[f"arg{i}"]:
            parts.append(str(vars_dict[f"arg{i}"]))
            i += 1
        return "_".join(parts)
    
    # No column name available (complex expression) - return None
    # User should provide explicit alias
    return None


def _should_add_alias(expr: exp.Expression) -> bool:
    """Check if an expression should get an auto-alias.
    
    Only function calls without explicit aliases should get auto-aliases.
    """
    # If it's already wrapped in an Alias, don't add another
    if isinstance(expr, exp.Alias):
        return False
    
    # Function calls should get aliases
    if isinstance(expr, exp.Func):
        return True
    
    return False


def _add_alias_to_expression(
    expr: exp.Expression,
    alias: str,
) -> exp.Alias:
    """Wrap an expression with an Alias node."""
    return exp.Alias(this=expr, alias=alias)


def apply_auto_aliasing(
    statement: exp.Expression,
    settings: CompileSettings,
) -> exp.Expression:
    """Apply auto-aliasing to function calls in a statement.
    
    Traverses the AST and adds aliases to function calls that don't have them.
    
    Args:
        statement: SQLGlot expression (typically a SELECT statement)
        settings: CompileSettings with alias configuration
        
    Returns:
        Modified statement with auto-aliases added
    """
    # Skip if no alias configuration is set
    # Note: We still apply default prefixes even without explicit config
    # This enables basic auto-aliasing out of the box
    
    def visit(node: exp.Expression) -> exp.Expression:
        """Recursively visit AST nodes and add aliases where needed."""
        # Handle SELECT expressions
        if isinstance(node, exp.Select):
            # Process SELECT expressions
            new_expressions = []
            for expr in node.expressions:
                if _should_add_alias(expr):
                    if isinstance(expr, exp.Func):
                        func_name = _get_function_name(expr)
                        alias = _generate_alias(expr, func_name, settings)
                        if alias:
                            new_expr = _add_alias_to_expression(expr, alias)
                            new_expressions.append(new_expr)
                        else:
                            new_expressions.append(expr)
                    else:
                        new_expressions.append(expr)
                elif isinstance(expr, exp.Alias):
                    # Already has explicit alias - don't change it
                    # But recursively process nested expressions for any nested functions
                    new_this = visit(expr.this)
                    new_expressions.append(exp.Alias(this=new_this, alias=expr.alias))
                else:
                    # Recursively process nested expressions
                    new_expr = visit(expr)
                    new_expressions.append(new_expr)
            node.set("expressions", new_expressions)
        
        # Recursively visit children (skip expressions for SELECT since we handled them above)
        # Also skip GROUP BY, ORDER BY, etc. where aliases are not valid
        skip_keys = {"expressions"} if isinstance(node, exp.Select) else set()
        
        # Don't add aliases in GROUP BY, ORDER BY, WHERE, HAVING, etc.
        no_alias_contexts = (exp.Group, exp.Order, exp.Where, exp.Having, exp.Join)
        in_no_alias_context = isinstance(node, no_alias_contexts)
        
        for key, value in node.args.items():
            if key in skip_keys:
                continue
                
            if key == "expressions" and isinstance(value, list):
                # For non-SELECT expressions (GROUP BY, ORDER BY, etc.), don't add aliases
                new_list = []
                for item in value:
                    if isinstance(item, exp.Expression):
                        # Don't add aliases in GROUP BY, ORDER BY, etc.
                        if in_no_alias_context:
                            new_list.append(visit(item))
                        elif _should_add_alias(item):
                            if isinstance(item, exp.Func):
                                func_name = _get_function_name(item)
                                alias = _generate_alias(item, func_name, settings)
                                if alias:
                                    new_list.append(_add_alias_to_expression(item, alias))
                                else:
                                    new_list.append(item)
                            else:
                                new_list.append(visit(item))
                        elif isinstance(item, exp.Alias):
                            # Already has explicit alias - don't change it
                            # But recursively process nested expressions
                            new_this = visit(item.this)
                            new_list.append(exp.Alias(this=new_this, alias=item.alias))
                        else:
                            new_list.append(visit(item))
                    else:
                        new_list.append(item)
                node.set(key, new_list)
            elif isinstance(value, exp.Expression):
                node.set(key, visit(value))
            elif isinstance(value, list):
                new_list = []
                for item in value:
                    if isinstance(item, exp.Expression):
                        new_list.append(visit(item))
                    else:
                        new_list.append(item)
                node.set(key, new_list)
        
        return node
    
    result = visit(statement.copy())
    
    # Note: We previously had a hack here to preserve _cohort_info attribute.
    # Now that cohort uses CohortBy AST node (stored in args), it survives .copy() automatically.
    
    return result
