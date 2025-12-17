"""Utilities for stripping Jinja/dbt templates from SQL."""

import re


def strip_jinja_templates(sql_content: str) -> str:
    """
    Strip dbt/Jinja templating from SQL and replace with regular SQL.
    
    Handles:
    - {{ config(...) }} - removes entire lines
    - {{ ref('table') }} - replaces with table name
    - {{ dbt.type_*() }} - replaces with SQL type
    - {{ fivetran_utils.*() }} - replaces with SQL function
    - {{ dbt_utils.*() }} - replaces with SQL (e.g., group_by)
    - {{ var(...) }} - removes or replaces with default
    - {{ macro_name(...) }} - removes complex macros
    - {% if ... %} / {% endif %} - removes conditionals, keeps True branch
    - {% else %} - removes
    
    Args:
        sql_content: SQL string with Jinja templates
        
    Returns:
        SQL string with Jinja templates removed/replaced
    """
    # First, handle multi-line {% if %} blocks by removing them entirely
    # We'll keep the True branch content (before {% else %} if present)
    
    # Remove {% if ... %} ... {% else %} ... {% endif %} blocks, keeping the True branch
    def process_if_block(match: re.Match[str]) -> str:
        block_content = match.group(0)
        # Find {% else %} if present
        else_match = re.search(r'\{%\s*else\s*%\}', block_content)
        if else_match:
            # Keep only the part before {% else %}
            return block_content[:else_match.start()]
        # If no else, keep everything between {% if %} and {% endif %}
        if_match = re.search(r'\{%\s*if\s+.*?\s*%\}', block_content)
        endif_match = re.search(r'\{%\s*endif\s*%\}', block_content)
        if if_match and endif_match:
            return block_content[if_match.end():endif_match.start()]
        return ''
    
    # Process {% if %} blocks (including multi-line)
    sql_content = re.sub(
        r'\{%\s*if\s+[^%]*%\}.*?\{%\s*endif\s*%\}',
        process_if_block,
        sql_content,
        flags=re.DOTALL
    )
    
    # Remove standalone {% else %} lines
    sql_content = re.sub(r'^\s*\{%\s*else\s*%\}\s*$', '', sql_content, flags=re.MULTILINE)
    
    lines = sql_content.split('\n')
    result_lines: list[str] = []
    prev_line_was_cte_end = False  # Track if previous line ended a CTE
    
    for i, line in enumerate(lines):
        original_line = line
        
        # Skip lines that are entirely config blocks or 404 errors
        if re.search(r'^\s*\{\{\s*config\s*\(', line, re.IGNORECASE):
            continue
        if '404: Not Found' in line:
            continue
        
        # Replace {{ ref('table_name') }} or {{ ref("table_name") }} with table_name
        def replace_ref(match: re.Match[str]) -> str:
            ref_content = match.group(1)
            # Extract table name from ref('table') or ref("table")
            table_match = re.search(r'[\'"]?([^\'"]+)[\'"]?', ref_content)
            if table_match:
                return table_match.group(1)
            return ref_content.strip()
        
        line = re.sub(
            r'\{\{\s*ref\s*\(\s*([^)]+)\s*\)\s*\}\}',
            replace_ref,
            line,
            flags=re.IGNORECASE
        )
        
        # Replace {{ dbt.type_*() }} with SQL types
        line = re.sub(r'\{\{\s*dbt\.type_int\s*\(\)\s*\}\}', 'INT', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_bigint\s*\(\)\s*\}\}', 'BIGINT', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_string\s*\(\)\s*\}\}', 'VARCHAR', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_float\s*\(\)\s*\}\}', 'FLOAT', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_numeric\s*\(\)\s*\}\}', 'NUMERIC', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_boolean\s*\(\)\s*\}\}', 'BOOLEAN', line, flags=re.IGNORECASE)
        
        # Replace {{ dbt_utils.group_by(N) }} with empty string
        line = re.sub(r'\{\{\s*dbt_utils\.group_by\s*\([^)]+\)\s*\}\}', '', line, flags=re.IGNORECASE)
        
        # Replace {{ fivetran_utils.string_agg(...) }} with STRING_AGG(...)
        def replace_fivetran_string_agg(match: re.Match[str]) -> str:
            full_match = match.group(0)
            args_match = re.search(r'string_agg\s*\(\s*([^)]+)\s*\)', full_match, re.IGNORECASE)
            if args_match:
                args = args_match.group(1)
                parts: list[str] = []
                current = ''
                in_quotes = False
                quote_char: str | None = None
                for char in args:
                    if char in ("'", '"') and not in_quotes:
                        in_quotes = True
                        quote_char = char
                        current += char
                    elif char == quote_char and in_quotes:
                        in_quotes = False
                        quote_char = None
                        current += char
                    elif char == ',' and not in_quotes:
                        parts.append(current.strip())
                        current = ''
                    else:
                        current += char
                if current:
                    parts.append(current.strip())
                
                if len(parts) >= 1:
                    col_expr = parts[0].strip("'\"")
                    delimiter = parts[1].strip("'\"") if len(parts) > 1 else "', '"
                    if 'distinct' in col_expr.lower():
                        col = col_expr.replace('distinct', '').strip()
                        return f"STRING_AGG(DISTINCT {col}, '{delimiter}')"
                    return f"STRING_AGG({col_expr}, '{delimiter}')"
            return 'STRING_AGG(...)'
        
        line = re.sub(
            r'\{\{\s*fivetran_utils\.string_agg\s*\([^)]+\)\s*\}\}',
            replace_fivetran_string_agg,
            line,
            flags=re.IGNORECASE
        )
        
        # Check if this line contains a macro that should be removed entirely
        should_skip_line = False
        if re.search(r'\{\{\s*\w+_persist_pass_through_columns\s*\(', line, re.IGNORECASE):
            should_skip_line = True
        
        # Replace {{ var('name', default) }} with default value or remove
        def replace_var(match: re.Match[str]) -> str:
            var_content = match.group(1)
            default_match = re.search(r',\s*([^,)]+)\s*\)', var_content)
            if default_match:
                return default_match.group(1).strip("'\"")
            return ''
        
        line = re.sub(
            r'\{\{\s*var\s*\(\s*([^)]+)\s*\)\s*\}\}',
            replace_var,
            line,
            flags=re.IGNORECASE
        )
        
        # Remove any remaining complex macros
        if re.match(r'^\s*\{%\s*set\s+.*%\}\s*$', line):
            should_skip_line = True
        
        # Replace remaining {{ ... }} blocks inline
        line_before = line
        line = re.sub(r'\{\{[^}]*\}\}', '', line)
        
        # Remove any remaining {% ... %} blocks
        line = re.sub(r'\{%[^%]*%\}', '', line)
        
        # Check if this line ends a CTE
        line_stripped = line.strip()
        is_cte_end = bool(re.match(r'^\s*\)\s*,?\s*$', line_stripped))
        
        # If the line was entirely a macro and is now empty, skip it
        if not line.strip() and re.search(r'\{\{|%\}', line_before):
            if should_skip_line:
                if prev_line_was_cte_end and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith('--') and not re.search(r'\{\{|%\}', next_line):
                        if result_lines:
                            result_lines[-1] = result_lines[-1].rstrip().rstrip(',') + ','
                continue
        
        if should_skip_line:
            if i + 1 < len(lines):
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line or next_line.startswith('--'):
                        continue
                    if re.search(r'\{\{|%\}', next_line):
                        break
                    if re.match(r'^\w+\s+as\s*\(', next_line, re.IGNORECASE):
                        if result_lines and prev_line_was_cte_end:
                            result_lines[-1] = result_lines[-1].rstrip().rstrip(',') + ','
                    break
            continue
        
        # Only add non-empty lines
        if line.strip():
            result_lines.append(line)
            prev_line_was_cte_end = is_cte_end
        else:
            prev_line_was_cte_end = False
    
    result = '\n'.join(result_lines)
    
    # Clean up: remove multiple blank lines
    result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
    
    # Remove trailing whitespace from each line
    result_lines = [line.rstrip() for line in result.split('\n')]
    result = '\n'.join(result_lines)
    
    return result.strip()
