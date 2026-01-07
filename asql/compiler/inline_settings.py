"""Inline SET statement extraction utilities."""

from __future__ import annotations

from typing import List, Optional, Tuple

from sqlglot import exp

from asql.config import CompileSettings


def extract_inline_settings(
    statements: List[exp.Expression],
) -> Tuple[CompileSettings, Optional[str], List[exp.Expression]]:
    """Extract leading SET statements into CompileSettings.

    SET statements at the beginning of a query can configure compilation behavior.

    Example:
        SET auto_spine = false;
        SET dialect = 'postgres';
        SELECT * FROM orders

    Args:
        statements: Parsed SQLGlot expressions.

    Returns:
        (settings, dialect_override, remaining_statements)
    """
    settings = CompileSettings()
    dialect_override: Optional[str] = None
    queries: List[exp.Expression] = []

    for stmt in statements:
        if isinstance(stmt, exp.Set):
            for item in stmt.expressions:
                if hasattr(item, "this") and isinstance(item.this, exp.EQ):
                    eq = item.this
                    key = eq.this.sql().lower().strip('"\'`')
                    value_expr = eq.expression

                    if isinstance(value_expr, exp.Boolean):
                        value = value_expr.this
                    elif isinstance(value_expr, exp.Literal):
                        value = value_expr.this.strip('"\'')
                        if isinstance(value, str):
                            if value.lower() == "true":
                                value = True
                            elif value.lower() == "false":
                                value = False
                    elif isinstance(value_expr, exp.Var):
                        value = value_expr.this
                    else:
                        value = value_expr.sql().strip('"\'')

                    if key == "dialect":
                        dialect_override = str(value).lower()
                    elif key == "auto_spine":
                        settings.auto_spine = bool(value)
                    elif key == "week_start":
                        if value in ("monday", "sunday"):
                            settings.week_start = value
                    elif key == "relative_date_type":
                        if value in ("timestamp", "date"):
                            settings.relative_date_type = value
                    elif key == "alias_template":
                        settings.alias_template = str(value)
                    elif key == "include_transpilation_comments":
                        settings.include_transpilation_comments = bool(value)
                    elif key == "passthrough_comments":
                        settings.passthrough_comments = bool(value)
                    elif key.endswith("_alias_prefix"):
                        func_name = key[:-13]  # Remove "_alias_prefix" suffix
                        settings.alias_prefixes[func_name] = str(value)
                    elif key.endswith("_alias_template"):
                        func_name = key[:-15]  # Remove "_alias_template" suffix
                        settings.alias_templates[func_name] = str(value)
        else:
            queries.append(stmt)

    return settings, dialect_override, queries


def extract_dialect_from_comment(asql_query: str) -> Optional[str]:
    """Extract a dialect override from a comment directive.

    Looks for patterns like:
    - -- dialect: snowflake
    - # dialect: snowflake

    Can appear anywhere in the query.
    """
    import re

    patterns = [
        r"--\s*dialect\s*:\s*(\w+)",
        r"#\s*dialect\s*:\s*(\w+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, asql_query, re.IGNORECASE)
        if match:
            return match.group(1).lower()

    return None


def extract_comment_settings(asql_query: str) -> Tuple[Optional[bool], Optional[bool]]:
    """Pre-scan for comment-related settings before preparsing.
    
    These settings need to be known before preparsing because they affect
    whether comments are preserved during the preparse phase.
    
    Returns:
        (include_transpilation_comments, passthrough_comments) - None if not set
    """
    import re
    
    include_transpilation: Optional[bool] = None
    passthrough: Optional[bool] = None
    
    # Match SET statements for comment settings
    # SET include_transpilation_comments = true/false
    # SET passthrough_comments = true/false
    patterns = [
        (r"SET\s+include_transpilation_comments\s*=\s*(true|false)", "include"),
        (r"SET\s+passthrough_comments\s*=\s*(true|false)", "passthrough"),
    ]
    
    for pattern, setting_type in patterns:
        match = re.search(pattern, asql_query, re.IGNORECASE)
        if match:
            value = match.group(1).lower() == "true"
            if setting_type == "include":
                include_transpilation = value
            else:
                passthrough = value
    
    return include_transpilation, passthrough
