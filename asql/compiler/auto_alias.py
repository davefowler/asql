"""Auto-aliasing for function calls without explicit aliases.

This module implements Phase 1 (prefix-based) and Phase 2 (template-based)
auto-aliasing for ASQL function calls.
"""

from __future__ import annotations

from typing import Optional, Dict, List, Any
import re

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
    func_call: exp.Function,
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
    args = func_call.expressions
    if args:
        # Handle count(*) case - empty args list
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
    if func_call.is_distinct:
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


def _render_template_fallback(
    template: str,
    vars_dict: Dict[str, Any],
) -> str:
    """Render template using simple string replacement (fallback when Jinja2 unavailable).
    
    Supports basic {variable} substitution and simple filters:
    - {prefix|lower} -> lowercase
    - {prefix|upper} -> uppercase
    - {prefix|title} -> title case
    """
    result = template
    
    # Handle filters (simple implementation)
    def apply_filter(value: Any, filter_name: str) -> str:
        if value is None:
            return ""
        value_str = str(value)
        if filter_name == "lower":
            return value_str.lower()
        elif filter_name == "upper":
            return value_str.upper()
        elif filter_name == "title":
            return value_str.title()
        elif filter_name == "camel":
            # Simple camelCase: split on _, capitalize each part except first
            parts = value_str.split("_")
            return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
        elif filter_name == "snake":
            # Convert to snake_case
            # Insert _ before uppercase letters
            return re.sub(r'(?<!^)(?=[A-Z])', '_', value_str).lower()
        return value_str
    
    # Find all {variable|filter} patterns
    pattern = r'\{(\w+)(?:\|(\w+))?\}'
    
    def replace_match(match: re.Match) -> str:
        var_name = match.group(1)
        filter_name = match.group(2)
        
        if var_name in vars_dict:
            value = vars_dict[var_name]
            if filter_name:
                return apply_filter(value, filter_name)
            return str(value) if value is not None else ""
        return match.group(0)  # Keep original if variable not found
    
    result = re.sub(pattern, replace_match, result)
    
    # Clean up any remaining {variable} patterns
    result = re.sub(r'\{(\w+)\}', lambda m: str(vars_dict.get(m.group(1), "")), result)
    
    # Remove double underscores and trailing/leading underscores
    result = re.sub(r'_+', '_', result)
    result = result.strip('_')
    
    return result


def _render_template(
    template: str,
    vars_dict: Dict[str, Any],
) -> str:
    """Render template using Jinja2 if available, otherwise fallback.
    
    Args:
        template: Jinja2 template string
        vars_dict: Dictionary of template variables
        
    Returns:
        Rendered alias string
    """
    try:
        from jinja2 import Environment, Template
        
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
        
        jinja_template = env.from_string(template)
        result = jinja_template.render(**vars_dict)
        
        # Clean up double underscores and trailing/leading underscores
        result = re.sub(r'_+', '_', result)
        result = result.strip('_')
        
        return result
    except ImportError:
        # Jinja2 not available, use fallback
        return _render_template_fallback(template, vars_dict)


def _get_function_name(func_call: exp.Function) -> str:
    """Get the function name from a Function expression."""
    # Try sql_name() first (handles most cases)
    try:
        name = func_call.sql_name()
        if name:
            return name.lower()
    except Exception:
        pass
    
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
    
    return "unknown"


def _generate_alias(
    func_call: exp.Function,
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
    is_count_star = (
        func_name.lower() == "count" and 
        len(func_call.expressions) == 1 and 
        isinstance(func_call.expressions[0], exp.Star)
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
    if isinstance(expr, exp.Function):
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
                    if isinstance(expr, exp.Function):
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
        skip_keys = {"expressions"} if isinstance(node, exp.Select) else set()
        
        for key, value in node.args.items():
            if key in skip_keys:
                continue
                
            if key == "expressions" and isinstance(value, list):
                # Handle expressions lists (GROUP BY, etc. - SELECT already handled above)
                new_list = []
                for item in value:
                    if isinstance(item, exp.Expression):
                        if _should_add_alias(item):
                            if isinstance(item, exp.Function):
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
    
    return visit(statement.copy())
