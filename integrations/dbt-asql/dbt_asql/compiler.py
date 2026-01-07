"""
ASQL to dbt-compatible SQL compiler.

This module handles:
1. Compiling ASQL → SQL
2. Expanding {{ variable }} → {{ var('variable') }}
3. Extracting SET statements → {{ config(...) }}
4. Resolving table names → {{ ref('...') }}
"""

import re
from typing import Optional

from asql import compile as asql_compile


def compile_asql_model(
    asql_code: str,
    known_models: Optional[set[str]] = None,
    dialect: str = "postgres",
) -> str:
    """
    Compile an ASQL model to dbt-compatible SQL.
    
    Args:
        asql_code: The ASQL source code
        known_models: Set of known dbt model names (for ref detection)
        dialect: SQL dialect to compile to
        
    Returns:
        SQL code with dbt Jinja expressions
    """
    # Step 1: Extract and convert SET statements to config
    config, remaining_code = _extract_config(asql_code)
    
    # Step 2: Preserve Jinja blocks before ASQL compilation
    remaining_code, jinja_placeholders = _extract_jinja(remaining_code)
    
    # Step 3: Compile ASQL to SQL
    sql = asql_compile(remaining_code, dialect=dialect)
    
    # Step 4: Restore Jinja blocks
    sql = _restore_jinja(sql, jinja_placeholders)
    
    # Step 5: Expand variable syntax {{ x }} → {{ var('x') }}
    sql = _expand_variables(sql)
    
    # Step 6: Resolve model references (table names → ref())
    if known_models:
        sql = _resolve_refs(sql, known_models)
    
    # Step 7: Add config block at top
    if config:
        config_str = _format_config(config)
        sql = f"{config_str}\n\n{sql}"
    
    return sql


def _extract_config(code: str) -> tuple[dict, str]:
    """
    Extract SET statements and return config dict + remaining code.
    
    Example:
        SET materialized = incremental;
        SET unique_key = id;
        
    Returns:
        ({'materialized': 'incremental', 'unique_key': 'id'}, remaining_code)
    """
    config = {}
    lines = []
    
    for line in code.split('\n'):
        # Match: SET key = value;
        match = re.match(
            r'^\s*SET\s+(\w+)\s*=\s*(.+?)\s*;?\s*$',
            line,
            re.IGNORECASE
        )
        if match:
            key, value = match.groups()
            # Parse the value
            config[key.lower()] = _parse_value(value)
        else:
            lines.append(line)
    
    return config, '\n'.join(lines)


def _parse_value(value: str) -> str | int | float | bool | list:
    """Parse a config value from string."""
    value = value.strip().rstrip(';')
    
    # Boolean
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    
    # Integer
    if re.match(r'^-?\d+$', value):
        return int(value)
    
    # Float
    if re.match(r'^-?\d+\.\d+$', value):
        return float(value)
    
    # List: [a, b, c]
    if value.startswith('[') and value.endswith(']'):
        items = value[1:-1].split(',')
        return [item.strip().strip('"\'') for item in items]
    
    # String (remove quotes if present)
    return value.strip('"\'')


def _format_config(config: dict) -> str:
    """Format config dict as dbt config block."""
    parts = []
    for key, value in config.items():
        if isinstance(value, bool):
            parts.append(f"{key}={str(value).lower()}")
        elif isinstance(value, (int, float)):
            parts.append(f"{key}={value}")
        elif isinstance(value, list):
            list_str = "[" + ", ".join(f"'{v}'" for v in value) + "]"
            parts.append(f"{key}={list_str}")
        else:
            parts.append(f"{key}='{value}'")
    
    return "{{ config(" + ", ".join(parts) + ") }}"


def _extract_jinja(code: str) -> tuple[str, dict]:
    """
    Extract Jinja blocks and replace with placeholders.
    
    Returns:
        (code_with_placeholders, {placeholder: original_jinja})
    """
    placeholders = {}
    counter = [0]  # Use list to allow mutation in closure
    
    def replace(match: re.Match) -> str:
        key = f"__JINJA_{counter[0]}__"
        counter[0] += 1
        placeholders[key] = match.group(0)
        return key
    
    # Match {{ ... }} and {% ... %}
    pattern = r'\{\{.*?\}\}|\{%.*?%\}'
    result = re.sub(pattern, replace, code, flags=re.DOTALL)
    
    return result, placeholders


def _restore_jinja(code: str, placeholders: dict) -> str:
    """Restore Jinja blocks from placeholders."""
    for key, value in placeholders.items():
        code = code.replace(key, value)
    return code


def _expand_variables(code: str) -> str:
    """
    Expand simplified variable syntax to dbt var() calls.
    
    {{ x }} → {{ var('x') }}
    {{ x || default }} → {{ var('x', default) }}
    {{ env.KEY }} → {{ env_var('KEY') }}
    """
    def expand(match: re.Match) -> str:
        content = match.group(1).strip()
        
        # Skip if already a function call (var, ref, source, config, this, target)
        if re.match(r'^(var|ref|source|config|this|target|is_incremental)\s*[\(\.]', content):
            return match.group(0)
        
        # Skip if it's just 'this'
        if content == 'this':
            return match.group(0)
        
        # Environment variable: env.KEY
        if content.startswith('env.'):
            env_var = content[4:]
            return f"{{{{ env_var('{env_var}') }}}}"
        
        # Variable with default: x || default
        if '||' in content:
            parts = content.split('||', 1)
            var_name = parts[0].strip()
            default = parts[1].strip()
            
            # Handle date literals in defaults
            if default.startswith('@'):
                default = f"'{default[1:]}'"
            elif not (default.startswith('"') or default.startswith("'") or 
                      re.match(r'^-?\d', default)):
                default = f"'{default}'"
            
            return f"{{{{ var('{var_name}', {default}) }}}}"
        
        # Simple variable: x
        return f"{{{{ var('{content}') }}}}"
    
    # Match {{ ... }} but not {% ... %}
    return re.sub(r'\{\{\s*([^}]+?)\s*\}\}', expand, code)


def _resolve_refs(sql: str, known_models: set[str]) -> str:
    """
    Replace table names with {{ ref('...') }} if they're known models.
    
    Uses regex to find FROM/JOIN clauses and check table names.
    """
    def replace_table(match: re.Match) -> str:
        keyword = match.group(1)  # FROM or JOIN
        table = match.group(2)     # table name
        
        # Skip if already has {{ or is qualified (schema.table)
        if '{{' in table or '.' in table:
            return match.group(0)
        
        # Check if it's a known model
        if table.lower() in {m.lower() for m in known_models}:
            return f"{keyword} {{{{ ref('{table}') }}}}"
        
        return match.group(0)
    
    # Match FROM table or JOIN table (not already using ref/source)
    pattern = r'\b(FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'
    return re.sub(pattern, replace_table, sql, flags=re.IGNORECASE)

