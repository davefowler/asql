"""ASQL Interactive Playground - Web-based query editor and executor with bidirectional translation."""

import json
import os
import re
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError
from asql.reverse_compiler import reverse_compile, detect_dialect

app = Flask(__name__)


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
    def process_if_block(match):
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
    result_lines = []
    prev_line_was_cte_end = False  # Track if previous line ended a CTE
    
    for i, line in enumerate(lines):
        original_line = line
        line_has_macro = bool(re.search(r'\{\{|%\}', line))
        
        # Skip lines that are entirely config blocks or 404 errors
        if re.search(r'^\s*\{\{\s*config\s*\(', line, re.IGNORECASE):
            continue
        if '404: Not Found' in line:
            continue
        
        # Replace {{ ref('table_name') }} or {{ ref("table_name") }} with table_name
        # Handle both single and double quotes, and nested quotes
        def replace_ref(match):
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
        
        # Replace {{ dbt.type_int() }} with INT
        line = re.sub(r'\{\{\s*dbt\.type_int\s*\(\)\s*\}\}', 'INT', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_bigint\s*\(\)\s*\}\}', 'BIGINT', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_string\s*\(\)\s*\}\}', 'VARCHAR', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_float\s*\(\)\s*\}\}', 'FLOAT', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_numeric\s*\(\)\s*\}\}', 'NUMERIC', line, flags=re.IGNORECASE)
        line = re.sub(r'\{\{\s*dbt\.type_boolean\s*\(\)\s*\}\}', 'BOOLEAN', line, flags=re.IGNORECASE)
        
        # Replace {{ dbt_utils.group_by(N) }} with empty string (GROUP BY already present)
        line = re.sub(r'\{\{\s*dbt_utils\.group_by\s*\([^)]+\)\s*\}\}', '', line, flags=re.IGNORECASE)
        
        # Replace {{ fivetran_utils.string_agg(...) }} with STRING_AGG(...)
        def replace_fivetran_string_agg(match):
            full_match = match.group(0)
            # Extract arguments from string_agg('distinct col', "', '")
            # Try to find the column and delimiter
            args_match = re.search(r'string_agg\s*\(\s*([^)]+)\s*\)', full_match, re.IGNORECASE)
            if args_match:
                args = args_match.group(1)
                # Handle 'distinct merged_lead_id', "', '"
                # Split by comma, but be careful with nested quotes
                parts = []
                current = ''
                in_quotes = False
                quote_char = None
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
        def replace_var(match):
            var_content = match.group(1)
            # Try to extract default value if present: var('name', default)
            default_match = re.search(r',\s*([^,)]+)\s*\)', var_content)
            if default_match:
                return default_match.group(1).strip("'\"")
            # No default, remove it
            return ''
        
        line = re.sub(
            r'\{\{\s*var\s*\(\s*([^)]+)\s*\)\s*\}\}',
            replace_var,
            line,
            flags=re.IGNORECASE
        )
        
        # Remove any remaining complex macros (entire lines that are just macros)
        if re.match(r'^\s*\{%\s*set\s+.*%\}\s*$', line):
            should_skip_line = True
        
        # Check if line is entirely a macro before processing
        line_before = line
        # Replace remaining {{ ... }} blocks inline (preserve the line)
        line = re.sub(r'\{\{[^}]*\}\}', '', line)
        
        # Remove any remaining {% ... %} blocks (catch-all)
        line = re.sub(r'\{%[^%]*%\}', '', line)
        
        # Check if this line ends a CTE (has closing paren and possibly comma)
        line_stripped = line.strip()
        is_cte_end = bool(re.match(r'^\s*\)\s*,?\s*$', line_stripped))
        
        # If the line was entirely a macro and is now empty/whitespace, skip it
        # BUT preserve commas if this is a CTE end
        if not line.strip() and re.search(r'\{\{|%\}', line_before):
            if should_skip_line:
                # If we're skipping a line that had a macro, check if previous line was CTE end
                # and next line starts a new CTE - we need to add a comma
                if prev_line_was_cte_end and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith('--') and not re.search(r'\{\{|%\}', next_line):
                        # Next line starts a new CTE, add comma to previous line
                        if result_lines:
                            result_lines[-1] = result_lines[-1].rstrip().rstrip(',') + ','
                continue
        
        # If we're skipping a line with a macro, but it had a comma, preserve it
        if should_skip_line:
            # Check if next non-empty line starts a new CTE
            if i + 1 < len(lines):
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line or next_line.startswith('--'):
                        continue
                    if re.search(r'\{\{|%\}', next_line):
                        break
                    # Check if it starts a new CTE (identifier followed by "as (")
                    if re.match(r'^\w+\s+as\s*\(', next_line, re.IGNORECASE):
                        # Previous CTE needs a comma
                        if result_lines and prev_line_was_cte_end:
                            result_lines[-1] = result_lines[-1].rstrip().rstrip(',') + ','
                    break
            continue
        
        # Don't remove trailing commas - they're needed for SQL syntax
        # Only clean up if the line is empty after macro removal
        
        # Only add non-empty lines
        if line.strip():
            result_lines.append(line)
            prev_line_was_cte_end = is_cte_end
        else:
            prev_line_was_cte_end = False
    
    # Post-process: Fix missing commas in SELECT statements and CTEs
    result = '\n'.join(result_lines)
    
    # Fix missing commas between SELECT columns (add comma if line ends with identifier and next line starts with identifier)
    fixed_lines = []
    lines = result.split('\n')
    in_select = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Detect SELECT statement start
        if re.match(r'^\s*select\s+', stripped, re.IGNORECASE):
            in_select = True
            fixed_lines.append(line)
            continue
        
        # Detect end of SELECT (FROM, GROUP BY, etc.)
        if in_select and re.match(r'^\s*(from|group\s+by|order\s+by|having|where)\s+', stripped, re.IGNORECASE):
            in_select = False
            fixed_lines.append(line)
            continue
        
        # If we're in a SELECT and this line has a column but no comma
        if in_select and stripped and not stripped.startswith('--'):
            # Check if this looks like a column (has identifier or function call)
            if re.match(r'^\s*[\w\.]+\s*', stripped) or re.match(r'^\s*\w+\s*\(', stripped):
                # Check if next line also looks like a column
                if i + 1 < len(lines):
                    next_stripped = lines[i + 1].strip()
                    if next_stripped and not next_stripped.startswith('--'):
                        # Check if next line is a column (not FROM, GROUP BY, etc.)
                        if not re.match(r'^\s*(from|group\s+by|order\s+by|having|where)\s+', next_stripped, re.IGNORECASE):
                            if re.match(r'^\s*[\w\.]+\s*', next_stripped) or re.match(r'^\s*\w+\s*\(', next_stripped):
                                # Current line needs a comma if it doesn't have one
                                if not stripped.rstrip().endswith(','):
                                    line = line.rstrip() + ','
        
        fixed_lines.append(line)
    
    result = '\n'.join(fixed_lines)
    
    result = '\n'.join(result_lines)
    
    # Clean up: remove multiple blank lines
    result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
    
    # Remove leading/trailing whitespace from each line
    result_lines = [line.rstrip() for line in result.split('\n')]
    result = '\n'.join(result_lines)
    
    return result.strip()

@app.route('/static/syntax/<path:filename>')
def serve_syntax(filename):
    """Serve syntax highlighter files."""
    syntax_dir = os.path.join(os.path.dirname(__file__), 'syntax')
    response = send_from_directory(syntax_dir, filename)
    # Ensure JavaScript files are served with correct content-type
    if filename.endswith('.js'):
        response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return response

# HTML template for the playground
PLAYGROUND_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASQL Playground</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/theme/monokai.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        html, body {
            width: 100%;
            margin: 0;
            padding: 0;
            overflow-x: hidden;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: white;
            color: #333;
        }
        
        .container {
            max-width: none;
            width: 100%;
            margin: 0;
            padding: 16px;
        }
        
        h1 {
            text-align: center;
            margin-bottom: 16px;
            color: #333;
            font-weight: 400;
        }
        
        .language-selectors {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        
        .language-selector {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        
        .language-selector label {
            font-size: 12px;
            color: #666;
            font-weight: 500;
        }
        
        .language-selector select {
            padding: 8px 32px 8px 12px;
            border: 1px solid #dadce0;
            border-radius: 4px;
            font-size: 14px;
            background: white;
            color: #ea4335;
            cursor: pointer;
            min-width: 160px;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23ea4335' d='M6 9L1 4h10z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 8px center;
        }
        
        .language-selector select:hover {
            border-color: #f28b82;
        }
        
        .language-selector select:focus {
            outline: none;
            border-color: #ea4335;
        }
        
        .swap-button {
            background: none;
            border: none;
            cursor: pointer;
            padding: 8px;
            margin-top: 24px;
            color: #666;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .swap-button:hover {
            color: #ea4335;
        }
        
        .swap-icon {
            width: 20px;
            height: 20px;
        }
        
        .playground {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
            margin-bottom: 0;
            border: 1px solid #dadce0;
            border-radius: 8px;
            overflow: hidden;
        }
        
        @media (max-width: 968px) {
            .playground {
                grid-template-columns: 1fr;
            }
        }
        
        .panel {
            background: white;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        
        .panel:first-child {
            border-right: 1px solid #dadce0;
        }
        
        .panel-header {
            background: white;
            color: #666;
            padding: 12px 16px;
            font-weight: 400;
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #dadce0;
        }
        
        .panel-content {
            padding: 0;
            flex: 1;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        
        #input-editor, #output-editor {
            flex: 1;
            min-height: 400px;
        }
        
        
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 8px;
            flex-wrap: wrap;
            justify-content: center;
        }
        
        button {
            padding: 10px 24px;
            border: 1px solid #dadce0;
            border-radius: 4px;
            font-size: 14px;
            cursor: pointer;
            background: white;
            color: #ea4335;
            font-weight: 500;
        }
        
        button:hover {
            background: #f8f9fa;
            border-color: #f28b82;
        }
        
        button:disabled {
            background: #f8f9fa;
            color: #999;
            cursor: not-allowed;
            border-color: #dadce0;
        }
        
        .translate-btn {
            background: #ea4335;
            color: white;
            border: none;
        }
        
        .translate-btn:hover {
            background: #c5221f;
            border-color: #c5221f;
        }
        
        button[onclick="openExamplesModal()"]:hover {
            background: #c5221f;
        }
        
        .error {
            background: #fce8e6;
            color: #c5221f;
            padding: 12px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 13px;
        }
        
        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            overflow-y: auto;
            padding: 20px;
            box-sizing: border-box;
        }
        
        .modal.open {
            display: flex;
            justify-content: center;
            align-items: flex-start;
        }
        
        .modal-content {
            background: white;
            border-radius: 8px;
            max-width: 900px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
            margin-top: 20px;
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid #dadce0;
            position: sticky;
            top: 0;
            background: white;
            z-index: 1;
        }
        
        .modal-header h2 {
            margin: 0;
            font-size: 18px;
            font-weight: 500;
            color: #333;
        }
        
        .modal-close {
            background: none;
            border: none;
            font-size: 28px;
            cursor: pointer;
            color: #666;
            padding: 0;
            line-height: 1;
        }
        
        .modal-close:hover {
            color: #333;
        }
        
        .modal-body {
            padding: 16px 20px;
        }
        
        .example-section {
            margin-bottom: 20px;
        }
        
        .example-section h3 {
            margin-bottom: 8px;
            color: #333;
            font-size: 15px;
            font-weight: 500;
        }
        
        .example-section p {
            margin-bottom: 10px;
        }
        
        .example-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 8px;
        }
        
        .example-btn {
            padding: 8px 10px;
            background: white;
            border: 1px solid #dadce0;
            border-radius: 4px;
            cursor: pointer;
            text-align: left;
            font-size: 12px;
            transition: all 0.2s;
        }
        
        .example-btn:hover {
            background: #f8f9fa;
            border-color: #f28b82;
        }
        
        .example-title {
            font-weight: 500;
            margin-bottom: 4px;
            color: #333;
        }
        
        .example-desc {
            color: #666;
            font-size: 12px;
        }
        
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #ea4335;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 10px;
        }
        
        /* CodeMirror styling */
        .CodeMirror {
            height: 100%;
            font-size: 14px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            border: none;
            border-radius: 0;
            padding: 12px;
        }
        
        .CodeMirror-scroll {
            min-height: 400px;
        }
        
        .CodeMirror-focused {
            outline: none;
        }
        
        .CodeMirror-readonly .CodeMirror-cursor {
            display: none;
        }
        
        /* Output editor - grey background to look less editable */
        #output-editor .CodeMirror {
            background: #f8f9fa;
        }
        
        #output-editor .CodeMirror-scroll {
            background: #f8f9fa;
        }
        
        #output-editor .CodeMirror-gutters {
            background: #f1f3f4;
            border-right: 1px solid #e8eaed;
        }
        
        /* Custom CodeMirror theme colors - red accents */
        .CodeMirror-linenumber {
            color: #999;
        }
        
        .CodeMirror-cursor {
            border-left: 2px solid #ea4335;
        }
        
        .CodeMirror-selected {
            background: #fce8e6;
        }
        
        .CodeMirror-focused .CodeMirror-selected {
            background: #fce8e6;
        }
        
        /* SQL and ASQL syntax highlighting colors */
        .CodeMirror .cm-keyword {
            color: #ea4335;
            font-weight: 600;
        }
        
        .CodeMirror .cm-string {
            color: #137333;
        }
        
        .CodeMirror .cm-number {
            color: #1967d2;
        }
        
        .CodeMirror .cm-comment {
            color: #999;
            font-style: italic;
        }
        
        .CodeMirror .cm-operator {
            color: #ea4335;
        }
        
        .CodeMirror .cm-variable {
            color: #333;
        }
        
        .CodeMirror .cm-def {
            color: #ea4335;
            font-weight: 500;
        }
        
        .CodeMirror .cm-atom {
            color: #1967d2;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .copy-btn {
            background: transparent;
            padding: 4px 8px;
            font-size: 12px;
            margin-left: 10px;
            border: 1px solid #dadce0;
            color: #666;
            border-radius: 4px;
        }
        
        .copy-btn:hover {
            background: #f8f9fa;
            border-color: #f28b82;
        }
        
        .detected-dialect {
            font-size: 11px;
            color: #999;
            font-style: italic;
            padding: 8px 16px;
            background: #f8f9fa;
            border-top: 1px solid #dadce0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h1 style="margin: 0;">🚀 ASQL Playground</h1>
            <div style="display: flex; gap: 8px; align-items: center;">
                <button onclick="openExamplesModal()" style="color: white; background: #ea4335; font-weight: 600; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">📚 Examples</button>
                <a href="/docs/" style="color: #ea4335; text-decoration: none; font-weight: 500; padding: 8px 16px; border: 1px solid #ea4335; border-radius: 4px; display: inline-block;">← Back to Docs</a>
            </div>
        </div>
        
        <div class="language-selectors">
            <div class="language-selector">
                <label>From:</label>
                <select id="from-dialect">
                    <option value="asql">ASQL</option>
                    <option value="">SQL (Auto-detect)</option>
                    <option value="postgres">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="bigquery">BigQuery</option>
                    <option value="snowflake">Snowflake</option>
                    <option value="redshift">Redshift</option>
                    <option value="spark">Spark</option>
                </select>
            </div>
            <button class="swap-button" onclick="swapLanguages()" title="Swap languages">
                <svg class="swap-icon" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6.99 11L3 15l3.99 4v-3H14v-2H6.99v-3zM21 9l-3.99-4v3H10v2h7.01v3L21 9z"/>
                </svg>
            </button>
            <div class="language-selector">
                <label>To:</label>
                <select id="to-dialect">
                    <option value="asql">ASQL</option>
                    <option value="">SQL (ANSI)</option>
                    <option value="postgres">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="bigquery">BigQuery</option>
                    <option value="snowflake" selected>Snowflake</option>
                    <option value="redshift">Redshift</option>
                    <option value="spark">Spark</option>
                </select>
            </div>
        </div>

        <div class="controls">
            <button class="translate-btn" onclick="translateQuery()">Translate</button>
        </div>

        <div class="playground">
            <div class="panel" id="input-panel">
                <div class="panel-header" id="input-header">
                    <span id="input-title">Enter text</span>
                    <button class="copy-btn" onclick="copyInput()">Copy</button>
                </div>
                <div class="panel-content">
                    <div id="input-editor"></div>
                    <span class="detected-dialect" id="detected-dialect" style="display: none;"></span>
                </div>
            </div>
            
            <div class="panel" id="output-panel">
                <div class="panel-header" id="output-header">
                    <span id="output-title">Translation</span>
                    <button class="copy-btn" onclick="copyOutput()">Copy</button>
                </div>
                <div class="panel-content">
                    <div id="output-editor"></div>
                    <div id="error" style="display: none;"></div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Examples Modal -->
    <div id="examples-modal" class="modal" onclick="closeExamplesModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h2>📚 Example Queries</h2>
                <button class="modal-close" onclick="closeExamplesModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div id="examples-container"></div>
            </div>
        </div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/sql/sql.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/addon/edit/matchbrackets.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/addon/edit/closebrackets.min.js"></script>
    <script src="/static/syntax/codemirror/asql-mode.js"></script>
    <script>
        // Detect if embedded in docs
        const isEmbedded = window.ASQL_EMBEDDED || (window.parent !== window && window.parent.location.hostname === window.location.hostname);
        
        // If embedded, adjust styling
        if (isEmbedded) {
            document.addEventListener('DOMContentLoaded', function() {
                const container = document.querySelector('.container');
                if (container) {
                    container.style.maxWidth = '100%';
                    container.style.padding = '10px';
                }
                // Hide back to docs link if embedded (it will be in parent frame)
                const backLink = document.querySelector('a[href="/docs/"]');
                if (backLink && window.parent !== window) {
                    backLink.style.display = 'none';
                }
            });
        }
    </script>
    <script>
        // Initialize CodeMirror editors (make them global so functions can access them)
        let inputEditor, outputEditor;
        
        // Define example arrays in global scope so they're accessible to loadExamples()
        const asqlExamples = [
            {
                title: "Simple FROM",
                desc: "Basic table selection",
                query: `from users`
            },
            {
                title: "WHERE Filter",
                desc: "Filter with conditions",
                query: `from users
where status == "active"`
            },
            {
                title: "GROUP BY",
                desc: "Aggregate with COUNT",
                query: `from users
group by country ( # as total_users )`
            },
            {
                title: "Multiple Aggregations",
                desc: "SUM, COUNT, AVG together",
                query: `from sales
group by region ( 
    sum(amount) as revenue, 
    # as orders, 
    avg(amount) as avg_order 
)`
            },
            {
                title: "SORT Descending",
                desc: "Order by descending",
                query: `from users
group by country ( # as total_users )
order by -total_users`
            },
            {
                title: "TAKE/LIMIT",
                desc: "Limit results",
                query: `from users
limit 10`
            },
            {
                title: "Complex Query",
                desc: "Full pipeline example",
                query: `from sales
where status == "completed" and amount > 100
group by region ( 
    sum(amount) as revenue, 
    # as orders 
)
order by -revenue
limit 10`
            },
            {
                title: "Multiple Conditions",
                desc: "AND/OR operators",
                query: `from users
where status == "active" 
    and age >= 18 
    and email is not null`
            },
            {
                title: "OR Conditions",
                desc: "Multiple OR conditions",
                query: `from users
where status == "active" 
    or status == "pending"`
            },
            {
                title: "NULL Checks",
                desc: "IS NULL / IS NOT NULL",
                query: `from users
where email is not null`
            },
            {
                title: "Comparisons",
                desc: "All comparison operators",
                query: `from users
where age >= 18 and age <= 65`
            },
        ];
        
        const asqlPipelineExamples = [
            {
                title: "Multi-Step Pipeline",
                desc: "Filter → Group → Sort → Limit (creates multiple CTEs)",
                query: `from orders
where status == "completed" 
    and created_at >= "2024-01-01"
group by customer_id ( 
    sum(total) as total_spent, 
    # as order_count,
    avg(total) as avg_order_value 
)
order by -total_spent
limit 10`
            },
            {
                title: "Customer Analytics Pipeline",
                desc: "Complex multi-step customer analysis",
                query: `from customers
where signup_date >= "2023-01-01"
    and is_active == true
join orders on customers.id == orders.customer_id
group by customers.id, customers.country ( 
    sum(orders.total) as lifetime_value,
    # as total_orders,
    max(orders.created_at) as last_order_date 
)
order by -lifetime_value
limit 50`
            },
            {
                title: "Sales Funnel Analysis",
                desc: "Multi-stage sales pipeline with joins",
                query: `from leads
join opportunities on leads.id == opportunities.lead_id
join deals on opportunities.id == deals.opportunity_id
where leads.source == "website"
    and leads.created_at >= "2024-01-01"
    and opportunities.stage != "lost"
    and deals.status == "closed"
group by leads.source, deals.region ( 
    sum(deals.amount) as revenue,
    # as closed_deals,
    avg(deals.amount) as avg_deal_size 
)
order by -revenue`
            },
            {
                title: "Product Performance Pipeline",
                desc: "Product analysis with multiple filters and aggregations",
                query: `from products
join order_items on products.id == order_items.product_id
join orders on order_items.order_id == orders.id
where products.category == "electronics"
    and products.in_stock == true
    and orders.status == "completed"
    and orders.created_at >= "2024-01-01"
group by products.id, products.name ( 
    sum(order_items.quantity) as units_sold,
    sum(order_items.price * order_items.quantity) as revenue,
    # as order_count 
)
order by -revenue
limit 20`
            },
            {
                title: "User Engagement Pipeline",
                desc: "User activity analysis with aggregation and filtering",
                query: `from users
join events on users.id == events.user_id
where users.created_at >= "2023-01-01"
    and events.event_type == "purchase"
    and events.timestamp >= "2024-01-01"
group by users.id, users.country ( 
    # as purchase_count,
    sum(events.value) as total_spent,
    max(events.timestamp) as last_purchase_date 
)
order by -total_spent
limit 100`
            },
            {
                title: "Time-Series Aggregation Pipeline",
                desc: "Date-based grouping with multiple aggregations",
                query: `from transactions
where status == "completed"
    and transaction_date >= "2024-01-01"
group by date_trunc(transaction_date, "month"), region ( 
    sum(amount) as monthly_revenue,
    # as transaction_count,
    avg(amount) as avg_transaction,
    min(amount) as min_transaction,
    max(amount) as max_transaction 
)
order by transaction_date desc, -monthly_revenue`
            },
            {
                title: "Cohort Analysis Pipeline",
                desc: "User cohort analysis with complex joins",
                query: `from users
join orders on users.id == orders.user_id
where users.signup_date >= "2023-01-01"
    and orders.status == "completed"
group by date_trunc(users.signup_date, "month"), users.country ( 
    date_trunc(users.signup_date, "month") as cohort_month,
    # as users_in_cohort,
    sum(orders.total) as cohort_revenue,
    avg(orders.total) as avg_order_value 
)
order by cohort_month desc, -cohort_revenue`
            },
            {
                title: "Multi-Table Join Pipeline",
                desc: "Complex joins across multiple tables",
                query: `from customers
join orders on customers.id == orders.customer_id
join order_items on orders.id == order_items.order_id
join products on order_items.product_id == products.id
where orders.status == "completed"
    and orders.created_at >= "2024-01-01"
group by customers.id, customers.name ( 
    sum(order_items.quantity * order_items.price) as total_spent,
    # as products_purchased,
    count(distinct products.category) as categories_bought 
)
order by -total_spent
limit 25`
            },
        ];
        
        const cohortExamples = [
            {
                title: "User Cohorts with first()",
                desc: "Assign users to cohorts by their first activity",
                query: `from events
group by user_id (
    first(event_date order by event_date) as first_activity,
    month(first(event_date order by event_date)) as cohort_month,
    # as total_events
)`
            },
            {
                title: "First Purchase Cohort",
                desc: "Customer cohorts by first order date",
                query: `from orders
group by customer_id (
    first(order_date order by order_date) as first_order_date,
    month(first(order_date order by order_date)) as cohort_month,
    first(order_id order by order_date) as first_order_id,
    sum(total) as lifetime_value
)`
            },
            {
                title: "Cohort Size by Month",
                desc: "Count users in each signup cohort",
                query: `from users
group by month(signup_date) (
    month(signup_date) as cohort_month,
    # as cohort_size,
    avg(age) as avg_age
)
order by cohort_month`
            },
            {
                title: "Revenue by Signup Cohort",
                desc: "Total revenue grouped by customer signup month",
                query: `from orders
join customers on orders.customer_id == customers.id
group by month(customers.signup_date) (
    month(customers.signup_date) as cohort_month,
    sum(orders.total) as total_revenue,
    # as order_count,
    count(distinct orders.customer_id) as customers
)
order by cohort_month`
            },
            {
                title: "Monthly Active by Cohort",
                desc: "Track active users by signup cohort and activity month",
                query: `from events
join users on events.user_id == users.id
group by month(users.signup_date), month(events.event_date) (
    month(users.signup_date) as cohort_month,
    month(events.event_date) as activity_month,
    count(distinct events.user_id) as active_users,
    # as total_events
)
order by cohort_month, activity_month`
            },
            {
                title: "First Event per User",
                desc: "Deduplicate to first activity using per...first by",
                query: `from events
per user_id first by event_date
select user_id, event_date as first_event_date, event_type`
            },
            {
                title: "Revenue by Cohort and Period",
                desc: "Track how each cohort spends over time",
                query: `from orders
join customers on orders.customer_id == customers.id
group by month(customers.first_order_date), month(orders.order_date) (
    month(customers.first_order_date) as cohort_month,
    month(orders.order_date) as order_month,
    sum(orders.total) as revenue,
    count(distinct orders.customer_id) as buyers,
    avg(orders.total) as avg_order_value
)
order by cohort_month, order_month`
            },
            {
                title: "Weekly Activity by Cohort",
                desc: "Track weekly active users by signup cohort",
                query: `from events
join users on events.user_id == users.id  
group by month(users.signup_date), week(events.event_date) (
    month(users.signup_date) as cohort_month,
    week(events.event_date) as activity_week,
    count(distinct events.user_id) as active_users,
    # as total_events
)
order by cohort_month, activity_week`
            },
            {
                title: "Cohort with Channel Segment",
                desc: "Segment cohorts by acquisition channel",
                query: `from events
join users on events.user_id == users.id
group by users.channel, month(users.signup_date) (
    users.channel,
    month(users.signup_date) as cohort_month,
    count(distinct events.user_id) as active_users,
    # as total_events
)
order by users.channel, cohort_month`
            },
            {
                title: "Feature Adoption Cohort",
                desc: "Find when each user first adopted a feature",
                query: `from events
where event_type == "feature_used"
group by user_id (
    first(event_date order by event_date) as first_feature_use,
    month(first(event_date order by event_date)) as adoption_month,
    # as times_used
)`
            },
        ];
        
        const samplingExamples = [
            {
                title: "Random Sample",
                desc: "Get 100 random rows",
                query: `from orders
sample 100`
            },
            {
                title: "Percentage Sample",
                desc: "Get ~10% of rows",
                query: `from orders
sample 10%`
            },
            {
                title: "Stratified Sample",
                desc: "100 random rows per category",
                query: `from products
sample 100 per category`
            },
            {
                title: "Sample with Filter",
                desc: "Sample from filtered data",
                query: `from orders
where status == "completed"
sample 500`
            },
        ];
        
        const dataReshapingExamples = [
            {
                title: "Pivot Rows to Columns",
                desc: "Transform status values into columns",
                query: `from orders
pivot sum(amount) by status values ('pending', 'shipped', 'delivered')
group by customer_id`
            },
            {
                title: "Unpivot Columns to Rows",
                desc: "Turn quarterly columns into rows",
                query: `from quarterly_metrics
unpivot q1, q2, q3, q4 into quarter, value`
            },
            {
                title: "Explode Array",
                desc: "Expand array column into rows",
                query: `from posts
explode tags as tag
select post_id, title, tag`
            },
            {
                title: "Explode and Aggregate",
                desc: "Count items per tag",
                query: `from posts
explode tags as tag
group by tag (
    # as post_count
)
order by -post_count`
            },
        ];
        
        const columnOperatorExamples = [
            {
                title: "Exclude Columns",
                desc: "Remove sensitive columns",
                query: `from users
except password_hash, internal_notes`
            },
            {
                title: "Rename Columns",
                desc: "Rename for clarity",
                query: `from users
rename id as user_id, name as full_name`
            },
            {
                title: "Replace Values",
                desc: "Transform column values",
                query: `from users
replace name with upper(name), email with lower(email)`
            },
            {
                title: "Combined Column Ops",
                desc: "Exclude, rename, and replace together",
                query: `from customers
except internal_id
rename name as customer_name
replace email with lower(email)`
            },
        ];
        
        const countInferenceExamples = [
            {
                title: "Count Rows",
                desc: "Basic COUNT(*)",
                query: `from orders
group by status (
    # as order_count
)`
            },
            {
                title: "Count Distinct Users",
                desc: "Infer primary key from table name",
                query: `from orders
group by status (
    # as total_orders,
    # users as unique_customers
)`
            },
            {
                title: "Multiple Entity Counts",
                desc: "Count different entities",
                query: `from order_items
group by category (
    # as line_items,
    # orders as unique_orders,
    # products as unique_products
)`
            },
            {
                title: "Explicit vs Inferred",
                desc: "Compare explicit and inferred counts",
                query: `from orders
group by region (
    # as total_rows,
    # users as unique_users,
    #(distinct product_id) as unique_products_explicit
)`
            },
        ];
        
        const sqlExamples = [];
        
        // Wait for DOM and ensure ASQL mode is loaded
        document.addEventListener('DOMContentLoaded', function() {
            // Verify ASQL mode is available (but don't block if it's not)
            // Wait a bit for the script to load if it hasn't yet
            let modeCheckAttempts = 0;
            const maxModeCheckAttempts = 20; // Max 2 seconds wait
            
            function checkASQLMode() {
                try {
                    // Check if CodeMirror is available
                    if (typeof CodeMirror === 'undefined') {
                        modeCheckAttempts++;
                        if (modeCheckAttempts < maxModeCheckAttempts) {
                            setTimeout(checkASQLMode, 100);
                            return;
                        }
                        console.warn('CodeMirror not loaded yet');
                        initializeEditors();
                        return;
                    }
                    
                    // Check if ASQL mode is registered (check both ways)
                    const modeExists = CodeMirror.modes && CodeMirror.modes['asql'];
                    const mimeExists = CodeMirror.mimeModes && CodeMirror.mimeModes['text/x-asql'];
                    
                    if (!modeExists && !mimeExists) {
                        modeCheckAttempts++;
                        if (modeCheckAttempts < maxModeCheckAttempts) {
                            // Try again after a short delay if mode isn't loaded yet
                            setTimeout(checkASQLMode, 100);
                            return;
                        } else {
                            console.warn('ASQL mode not loaded after waiting. Using SQL mode as fallback.');
                            console.log('Available modes:', Object.keys(CodeMirror.modes || {}));
                        }
                    } else {
                        console.log('ASQL mode loaded successfully');
                    }
                } catch (e) {
                    console.warn('Error checking ASQL mode:', e);
                }
                initializeEditors();
                
                // After editors are initialized, ensure modes are set correctly
                // This handles the case where editors were initialized before mode was registered
                setTimeout(function() {
                    if (typeof inputEditor !== 'undefined' && inputEditor) {
                        const fromDialect = document.getElementById('from-dialect').value;
                        if (fromDialect === 'asql' && CodeMirror.modes && CodeMirror.modes['asql']) {
                            inputEditor.setOption('mode', 'text/x-asql');
                        }
                    }
                    if (typeof outputEditor !== 'undefined' && outputEditor) {
                        const toDialect = document.getElementById('to-dialect').value;
                        if (toDialect === 'asql' && CodeMirror.modes && CodeMirror.modes['asql']) {
                            outputEditor.setOption('mode', 'text/x-asql');
                        }
                    }
                }, 100);
            }
            
            function initializeEditors() {
            // Read URL parameters
            const urlParams = new URLSearchParams(window.location.search);
            const d_f = urlParams.get('d_f') || 'asql';  // from dialect
            const d_t = urlParams.get('d_t') || '';      // to dialect
            const sql_f = urlParams.get('sql_f') || '';  // from SQL/ASQL
            const sql_t = urlParams.get('sql_t') || '';  // to SQL (optional)
            
            // Set default query if no URL params (blank by default)
            const defaultQuery = '';
            
            const initialInput = sql_f ? decodeURIComponent(sql_f) : defaultQuery;
            const initialOutput = sql_t ? decodeURIComponent(sql_t) : '';
            
            // Set dialect selects (defaults: from=asql, to=snowflake)
            if (d_f) {
                document.getElementById('from-dialect').value = d_f.toLowerCase();
            } else {
                document.getElementById('from-dialect').value = 'asql';
            }
            if (d_t) {
                document.getElementById('to-dialect').value = d_t.toLowerCase();
            } else {
                document.getElementById('to-dialect').value = 'snowflake';
            }
            
            // Initialize CodeMirror editors
            const fromDialectValue = d_f ? d_f.toLowerCase() : 'asql';
            inputEditor = CodeMirror(document.getElementById('input-editor'), {
                value: initialInput,
                mode: fromDialectValue === 'asql' ? 'text/x-asql' : 'text/x-sql',
                lineNumbers: true,
                matchBrackets: true,
                autoCloseBrackets: true,
                theme: 'default',
                lineWrapping: true,
                placeholder: 'Enter your query here...'
            });
        
            outputEditor = CodeMirror(document.getElementById('output-editor'), {
                value: initialOutput,
                mode: d_t && d_t.toLowerCase() === 'asql' ? 'text/x-asql' : 'text/x-sql',
                lineNumbers: true,
                matchBrackets: true,
                autoCloseBrackets: true,
                theme: 'default',
                readOnly: true,
                lineWrapping: true,
                placeholder: 'Translation will appear here...'
            });
        
        function getCurrentMode() {
            try {
                const fromSelect = document.getElementById('from-dialect');
                const toSelect = document.getElementById('to-dialect');
                
                if (!fromSelect || !toSelect) {
                    // Default to asql-to-sql if selects don't exist yet
                    return 'asql-to-sql';
                }
                
                const fromDialect = fromSelect.value;
                const toDialect = toSelect.value;
                
                if (fromDialect === 'asql' && toDialect !== 'asql') {
                    return 'asql-to-sql';
                } else if (fromDialect !== 'asql' && toDialect === 'asql') {
                    return 'sql-to-asql';
                } else if (fromDialect === 'asql' && toDialect === 'asql') {
                    return 'asql-to-asql';
                } else {
                    return 'sql-to-sql';
                }
            } catch (error) {
                console.error('Error getting current mode:', error);
                return 'asql-to-sql'; // Default fallback
            }
        }
        
        // Update URL with current state
        function updateURL() {
            if (!inputEditor) return;
            
            const fromDialect = document.getElementById('from-dialect').value || 'asql';
            const toDialect = document.getElementById('to-dialect').value || '';
            const inputQuery = inputEditor.getValue();
            const outputQuery = outputEditor ? outputEditor.getValue() : '';
            
            const params = new URLSearchParams();
            
            // Set from dialect (uppercase for ASQL, lowercase for others)
            if (fromDialect === 'asql') {
                params.set('d_f', 'ASQL');
            } else if (fromDialect) {
                params.set('d_f', fromDialect);
            }
            
            // Set to dialect
            if (toDialect) {
                if (toDialect === 'asql') {
                    params.set('d_t', 'ASQL');
                } else {
                    params.set('d_t', toDialect);
                }
            }
            
            // Set from SQL/ASQL query
            if (inputQuery && inputQuery.trim()) {
                params.set('sql_f', encodeURIComponent(inputQuery));
            }
            
            // Set to SQL query (optional, only if we have output)
            if (outputQuery && outputQuery.trim()) {
                params.set('sql_t', encodeURIComponent(outputQuery));
            }
            
            // Update URL without reloading page
            const newURL = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
            window.history.pushState({}, '', newURL);
        }
        
        function ensureFromNotPostgresWhenToEmpty() {
            const fromDialect = document.getElementById('from-dialect').value;
            const toDialect = document.getElementById('to-dialect').value;
            
            // If "to" is not selected and "from" is postgresql, switch "from" to something else
            if (!toDialect && (fromDialect === 'postgres' || fromDialect === 'postgresql')) {
                document.getElementById('from-dialect').value = 'asql';
            }
        }
        
        function updateUITitles() {
            ensureFromNotPostgresWhenToEmpty();
            
            const fromDialect = document.getElementById('from-dialect').value;
            const toDialect = document.getElementById('to-dialect').value;
            
            const fromLabel = fromDialect === 'asql' ? 'ASQL' : (fromDialect || 'SQL');
            const toLabel = toDialect === 'asql' ? 'ASQL' : (toDialect || 'SQL');
            
            document.getElementById('input-title').textContent = fromLabel;
            document.getElementById('output-title').textContent = toLabel;
            
            // Update CodeMirror mode based on dialect
            if (fromDialect === 'asql') {
                inputEditor.setOption('mode', 'text/x-asql');
            } else {
                inputEditor.setOption('mode', 'text/x-sql');
            }
            
            if (toDialect === 'asql') {
                outputEditor.setOption('mode', 'text/x-asql');
            } else {
                outputEditor.setOption('mode', 'text/x-sql');
            }
        }
        
        // ========== Examples Modal ==========
        
        function openExamplesModal() {
            const modal = document.getElementById('examples-modal');
            modal.classList.add('open');
            document.body.style.overflow = 'hidden';
            loadExamples();
        }
        
        function closeExamplesModal(event) {
            // If called from backdrop click, only close if clicking the modal backdrop itself
            if (event && event.target !== document.getElementById('examples-modal')) {
                return;
            }
            const modal = document.getElementById('examples-modal');
            modal.classList.remove('open');
            document.body.style.overflow = '';
        }
        
        // Close modal on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeExamplesModal();
            }
        });
        
        // ========== End Examples Modal ==========
        
        function swapLanguages() {
            const fromSelect = document.getElementById('from-dialect');
            const toSelect = document.getElementById('to-dialect');
            const fromValue = fromSelect.value;
            const toValue = toSelect.value;

            fromSelect.value = toValue;
            toSelect.value = fromValue;

            // Swap editor contents
            const temp = inputEditor.getValue();
            inputEditor.setValue(outputEditor.getValue());
            outputEditor.setValue(temp);

            updateUITitles();
            translateQuery();
        }

        // Update UI when dialects change (set up after DOM is ready)
        document.addEventListener('DOMContentLoaded', function() {
            // Load saved style config
            loadStyleConfig();
            
            document.getElementById('from-dialect').addEventListener('change', () => {
                ensureFromNotPostgresWhenToEmpty();
                updateUITitles();
                translateQuery();
                updateURL();
            });
            
            document.getElementById('to-dialect').addEventListener('change', () => {
                ensureFromNotPostgresWhenToEmpty();
                updateUITitles();
                translateQuery();
                updateURL();
            });
        });
        
        function loadExamples() {
            const container = document.getElementById('examples-container');
            if (!container) {
                console.error('Examples container not found');
                return;
            }
            
            try {
                container.innerHTML = '';
                
                let currentMode;
                try {
                    currentMode = getCurrentMode();
                } catch (modeError) {
                    console.warn('Error getting current mode, defaulting to asql-to-sql:', modeError);
                    currentMode = 'asql-to-sql'; // Default fallback
                }
                
                if (currentMode === 'asql-to-sql' || currentMode === 'asql-to-asql') {
                    // Basic ASQL Examples section
                    const section = document.createElement('div');
                    section.className = 'example-section';
                    const h3 = document.createElement('h3');
                    h3.textContent = 'ASQL Examples';
                    section.appendChild(h3);
                    const p = document.createElement('p');
                    p.style.color = '#666';
                    p.style.marginBottom = '15px';
                    p.style.fontSize = '13px';
                    p.textContent = 'Basic ASQL queries that showcase the language syntax. These examples should not look too different from regular SQL - ASQL is designed to be familiar and intuitive.';
                    section.appendChild(p);
                    const examplesDiv = document.createElement('div');
                    examplesDiv.className = 'example-list';
                    examplesDiv.id = 'asql-examples';
                    section.appendChild(examplesDiv);
                    container.appendChild(section);
                    
                    if (!asqlExamples || !Array.isArray(asqlExamples)) {
                        console.error('asqlExamples array is not defined or is not an array');
                        examplesDiv.innerHTML = '<p style="color: #c5221f; padding: 20px;">Error: Examples data not available.</p>';
                    } else {
                        asqlExamples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        const titleDiv = document.createElement('div');
                        titleDiv.className = 'example-title';
                        titleDiv.textContent = example.title;
                        const descDiv = document.createElement('div');
                        descDiv.className = 'example-desc';
                        descDiv.textContent = example.desc;
                        btn.appendChild(titleDiv);
                        btn.appendChild(descDiv);
                        btn.onclick = () => {
                            closeExamplesModal();
                            // Set "from" to ASQL if not already set
                            const fromDialect = document.getElementById('from-dialect').value;
                            if (fromDialect !== 'asql') {
                                document.getElementById('from-dialect').value = 'asql';
                                updateUITitles();
                            }
                            inputEditor.setValue(example.query);
                            translateQuery();
                            // Update URL after a short delay to allow translation to complete
                            setTimeout(() => {
                                updateURL();
                            }, 1000);
                        };
                        examplesDiv.appendChild(btn);
                        });
                    }
                    
                    // ASQL Pipeline Examples section
                    const pipelineSection = document.createElement('div');
                    pipelineSection.className = 'example-section';
                    const pipelineH3 = document.createElement('h3');
                    pipelineH3.textContent = 'ASQL Pipeline Examples';
                    pipelineSection.appendChild(pipelineH3);
                    const pipelineP = document.createElement('p');
                    pipelineP.style.color = '#666';
                    pipelineP.style.marginBottom = '15px';
                    pipelineP.style.fontSize = '13px';
                    pipelineP.textContent = 'Complex queries that showcase pipeline features and generate multiple CTEs.';
                    pipelineSection.appendChild(pipelineP);
                    const pipelineExamplesDiv = document.createElement('div');
                    pipelineExamplesDiv.className = 'example-list';
                    pipelineExamplesDiv.id = 'asql-pipeline-examples';
                    pipelineSection.appendChild(pipelineExamplesDiv);
                    container.appendChild(pipelineSection);
                    
                    if (!asqlPipelineExamples || !Array.isArray(asqlPipelineExamples)) {
                        console.error('asqlPipelineExamples array is not defined or is not an array');
                        pipelineExamplesDiv.innerHTML = '<p style="color: #c5221f; padding: 20px;">Error: Pipeline examples data not available.</p>';
                    } else {
                        asqlPipelineExamples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        const titleDiv = document.createElement('div');
                        titleDiv.className = 'example-title';
                        titleDiv.textContent = example.title;
                        const descDiv = document.createElement('div');
                        descDiv.className = 'example-desc';
                        descDiv.textContent = example.desc;
                        btn.appendChild(titleDiv);
                        btn.appendChild(descDiv);
                        btn.onclick = () => {
                            closeExamplesModal();
                            // Set "from" to ASQL if not already set
                            const fromDialect = document.getElementById('from-dialect').value;
                            if (fromDialect !== 'asql') {
                                document.getElementById('from-dialect').value = 'asql';
                                updateUITitles();
                            }
                            inputEditor.setValue(example.query);
                            translateQuery();
                            // Update URL after a short delay to allow translation to complete
                            setTimeout(() => {
                                updateURL();
                            }, 1000);
                        };
                        pipelineExamplesDiv.appendChild(btn);
                        });
                    }
                    
                    // Cohort Analysis Examples section
                    const cohortSection = document.createElement('div');
                    cohortSection.className = 'example-section';
                    const cohortH3 = document.createElement('h3');
                    cohortH3.textContent = 'Cohort Analysis Examples';
                    cohortSection.appendChild(cohortH3);
                    const cohortP = document.createElement('p');
                    cohortP.style.color = '#666';
                    cohortP.style.marginBottom = '15px';
                    cohortP.style.fontSize = '13px';
                    cohortP.textContent = 'Cohort analysis patterns using first(), running_sum(), prior(), and other window functions. These showcase how to build retention, LTV, and user segmentation queries.';
                    cohortSection.appendChild(cohortP);
                    const cohortExamplesDiv = document.createElement('div');
                    cohortExamplesDiv.className = 'example-list';
                    cohortExamplesDiv.id = 'cohort-examples';
                    cohortSection.appendChild(cohortExamplesDiv);
                    container.appendChild(cohortSection);
                    
                    if (!cohortExamples || !Array.isArray(cohortExamples)) {
                        console.error('cohortExamples array is not defined or is not an array');
                        cohortExamplesDiv.innerHTML = '<p style="color: #c5221f; padding: 20px;">Error: Cohort examples data not available.</p>';
                    } else {
                        cohortExamples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        const titleDiv = document.createElement('div');
                        titleDiv.className = 'example-title';
                        titleDiv.textContent = example.title;
                        const descDiv = document.createElement('div');
                        descDiv.className = 'example-desc';
                        descDiv.textContent = example.desc;
                        btn.appendChild(titleDiv);
                        btn.appendChild(descDiv);
                        btn.onclick = () => {
                            closeExamplesModal();
                            // Set "from" to ASQL if not already set
                            const fromDialect = document.getElementById('from-dialect').value;
                            if (fromDialect !== 'asql') {
                                document.getElementById('from-dialect').value = 'asql';
                                updateUITitles();
                            }
                            inputEditor.setValue(example.query);
                            translateQuery();
                            // Update URL after a short delay to allow translation to complete
                            setTimeout(() => {
                                updateURL();
                            }, 1000);
                        };
                        cohortExamplesDiv.appendChild(btn);
                        });
                    }
                    
                    // Sampling Examples section
                    const samplingSection = document.createElement('div');
                    samplingSection.className = 'example-section';
                    const samplingH3 = document.createElement('h3');
                    samplingH3.textContent = 'Sampling Examples';
                    samplingSection.appendChild(samplingH3);
                    const samplingP = document.createElement('p');
                    samplingP.style.color = '#666';
                    samplingP.style.marginBottom = '15px';
                    samplingP.style.fontSize = '13px';
                    samplingP.textContent = 'Random sampling for data exploration. Fixed counts, percentages, and stratified sampling per group.';
                    samplingSection.appendChild(samplingP);
                    const samplingExamplesDiv = document.createElement('div');
                    samplingExamplesDiv.className = 'example-list';
                    samplingExamplesDiv.id = 'sampling-examples';
                    samplingSection.appendChild(samplingExamplesDiv);
                    container.appendChild(samplingSection);
                    
                    if (typeof samplingExamples !== 'undefined' && Array.isArray(samplingExamples)) {
                        samplingExamples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        const titleDiv = document.createElement('div');
                        titleDiv.className = 'example-title';
                        titleDiv.textContent = example.title;
                        const descDiv = document.createElement('div');
                        descDiv.className = 'example-desc';
                        descDiv.textContent = example.desc;
                        btn.appendChild(titleDiv);
                        btn.appendChild(descDiv);
                        btn.onclick = () => {
                            closeExamplesModal();
                            const fromDialect = document.getElementById('from-dialect').value;
                            if (fromDialect !== 'asql') {
                                document.getElementById('from-dialect').value = 'asql';
                                updateUITitles();
                            }
                            inputEditor.setValue(example.query);
                            translateQuery();
                            setTimeout(() => { updateURL(); }, 1000);
                        };
                        samplingExamplesDiv.appendChild(btn);
                        });
                    }
                    
                    // Data Reshaping Examples section
                    const reshapingSection = document.createElement('div');
                    reshapingSection.className = 'example-section';
                    const reshapingH3 = document.createElement('h3');
                    reshapingH3.textContent = 'Data Reshaping Examples';
                    reshapingSection.appendChild(reshapingH3);
                    const reshapingP = document.createElement('p');
                    reshapingP.style.color = '#666';
                    reshapingP.style.marginBottom = '15px';
                    reshapingP.style.fontSize = '13px';
                    reshapingP.textContent = 'Pivot (rows to columns), unpivot (columns to rows), and explode (arrays to rows) operations for reshaping data.';
                    reshapingSection.appendChild(reshapingP);
                    const reshapingExamplesDiv = document.createElement('div');
                    reshapingExamplesDiv.className = 'example-list';
                    reshapingExamplesDiv.id = 'reshaping-examples';
                    reshapingSection.appendChild(reshapingExamplesDiv);
                    container.appendChild(reshapingSection);
                    
                    if (typeof dataReshapingExamples !== 'undefined' && Array.isArray(dataReshapingExamples)) {
                        dataReshapingExamples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        const titleDiv = document.createElement('div');
                        titleDiv.className = 'example-title';
                        titleDiv.textContent = example.title;
                        const descDiv = document.createElement('div');
                        descDiv.className = 'example-desc';
                        descDiv.textContent = example.desc;
                        btn.appendChild(titleDiv);
                        btn.appendChild(descDiv);
                        btn.onclick = () => {
                            closeExamplesModal();
                            const fromDialect = document.getElementById('from-dialect').value;
                            if (fromDialect !== 'asql') {
                                document.getElementById('from-dialect').value = 'asql';
                                updateUITitles();
                            }
                            inputEditor.setValue(example.query);
                            translateQuery();
                            setTimeout(() => { updateURL(); }, 1000);
                        };
                        reshapingExamplesDiv.appendChild(btn);
                        });
                    }
                    
                    // Column Operators Examples section
                    const columnOpsSection = document.createElement('div');
                    columnOpsSection.className = 'example-section';
                    const columnOpsH3 = document.createElement('h3');
                    columnOpsH3.textContent = 'Column Operator Examples';
                    columnOpsSection.appendChild(columnOpsH3);
                    const columnOpsP = document.createElement('p');
                    columnOpsP.style.color = '#666';
                    columnOpsP.style.marginBottom = '15px';
                    columnOpsP.style.fontSize = '13px';
                    columnOpsP.textContent = 'Except (exclude columns), rename, and replace operators for column manipulation without listing all columns.';
                    columnOpsSection.appendChild(columnOpsP);
                    const columnOpsExamplesDiv = document.createElement('div');
                    columnOpsExamplesDiv.className = 'example-list';
                    columnOpsExamplesDiv.id = 'column-ops-examples';
                    columnOpsSection.appendChild(columnOpsExamplesDiv);
                    container.appendChild(columnOpsSection);
                    
                    if (typeof columnOperatorExamples !== 'undefined' && Array.isArray(columnOperatorExamples)) {
                        columnOperatorExamples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        const titleDiv = document.createElement('div');
                        titleDiv.className = 'example-title';
                        titleDiv.textContent = example.title;
                        const descDiv = document.createElement('div');
                        descDiv.className = 'example-desc';
                        descDiv.textContent = example.desc;
                        btn.appendChild(titleDiv);
                        btn.appendChild(descDiv);
                        btn.onclick = () => {
                            closeExamplesModal();
                            const fromDialect = document.getElementById('from-dialect').value;
                            if (fromDialect !== 'asql') {
                                document.getElementById('from-dialect').value = 'asql';
                                updateUITitles();
                            }
                            inputEditor.setValue(example.query);
                            translateQuery();
                            setTimeout(() => { updateURL(); }, 1000);
                        };
                        columnOpsExamplesDiv.appendChild(btn);
                        });
                    }
                    
                    // Count Inference Examples section
                    const countSection = document.createElement('div');
                    countSection.className = 'example-section';
                    const countH3 = document.createElement('h3');
                    countH3.textContent = 'Smart Count Examples';
                    countSection.appendChild(countH3);
                    const countP = document.createElement('p');
                    countP.style.color = '#666';
                    countP.style.marginBottom = '15px';
                    countP.style.fontSize = '13px';
                    countP.textContent = 'The # shorthand with table names infers primary keys. "# users" becomes COUNT(DISTINCT user_id).';
                    countSection.appendChild(countP);
                    const countExamplesDiv = document.createElement('div');
                    countExamplesDiv.className = 'example-list';
                    countExamplesDiv.id = 'count-inference-examples';
                    countSection.appendChild(countExamplesDiv);
                    container.appendChild(countSection);
                    
                    if (typeof countInferenceExamples !== 'undefined' && Array.isArray(countInferenceExamples)) {
                        countInferenceExamples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        const titleDiv = document.createElement('div');
                        titleDiv.className = 'example-title';
                        titleDiv.textContent = example.title;
                        const descDiv = document.createElement('div');
                        descDiv.className = 'example-desc';
                        descDiv.textContent = example.desc;
                        btn.appendChild(titleDiv);
                        btn.appendChild(descDiv);
                        btn.onclick = () => {
                            closeExamplesModal();
                            const fromDialect = document.getElementById('from-dialect').value;
                            if (fromDialect !== 'asql') {
                                document.getElementById('from-dialect').value = 'asql';
                                updateUITitles();
                            }
                            inputEditor.setValue(example.query);
                            translateQuery();
                            setTimeout(() => { updateURL(); }, 1000);
                        };
                        countExamplesDiv.appendChild(btn);
                        });
                    }
                } else {
                    const section = document.createElement('div');
                    section.className = 'example-section';
                    const sqlH3 = document.createElement('h3');
                    sqlH3.textContent = 'SQL Translation Examples';
                    section.appendChild(sqlH3);
                    const sqlExamplesDiv = document.createElement('div');
                    sqlExamplesDiv.className = 'example-list';
                    sqlExamplesDiv.id = 'sql-examples';
                    section.appendChild(sqlExamplesDiv);
                    container.appendChild(section);
                    
                    const examplesDiv = document.getElementById('sql-examples');
                    if (sqlExamples.length === 0) {
                        examplesDiv.innerHTML = '<p style="color: #666; padding: 20px;">SQL examples will be loaded from the server...</p>';
                        loadSQLExamples();
                    } else {
                        sqlExamples.forEach(example => {
                            const btn = document.createElement('button');
                            btn.className = 'example-btn';
                            const titleDiv = document.createElement('div');
                            titleDiv.className = 'example-title';
                            titleDiv.textContent = example.title;
                            const descDiv = document.createElement('div');
                            descDiv.className = 'example-desc';
                            descDiv.textContent = example.desc;
                            btn.appendChild(titleDiv);
                            btn.appendChild(descDiv);
                            btn.onclick = () => {
                                closeExamplesModal();
                                inputEditor.setValue(example.query);
                                document.getElementById('from-dialect').value = example.dialect || '';
                                updateUITitles();
                                translateQuery();
                                // Update URL after a short delay to allow translation to complete
                                setTimeout(() => {
                                    updateURL();
                                }, 1000);
                            };
                            examplesDiv.appendChild(btn);
                        });
                    }
                }
                
                // Always load Fivetran dbt examples
                loadFivetranExamples();
            } catch (error) {
                console.error('Error loading examples:', error);
                container.innerHTML = '<p style="color: #c5221f; padding: 20px;">Error loading examples. Please refresh the page.</p>';
            }
        }
        
        async function loadFivetranExamples() {
            const container = document.getElementById('examples-container');
            
            // Check if Fivetran section already exists
            let fivetranSection = document.getElementById('fivetran-examples-section');
            if (!fivetranSection) {
                fivetranSection = document.createElement('div');
                fivetranSection.id = 'fivetran-examples-section';
                fivetranSection.className = 'example-section';
                const fivetranH3 = document.createElement('h3');
                fivetranH3.textContent = 'Fivetran_dbt Examples';
                fivetranSection.appendChild(fivetranH3);
                const fivetranP = document.createElement('p');
                fivetranP.style.color = '#666';
                fivetranP.style.marginBottom = '15px';
                fivetranP.style.fontSize = '13px';
                fivetranP.textContent = 'Here are some examples of some extensive queries used in the fivetran_dbt libraries.';
                fivetranSection.appendChild(fivetranP);
                const fivetranExamplesDiv = document.createElement('div');
                fivetranExamplesDiv.className = 'example-list';
                fivetranExamplesDiv.id = 'fivetran-examples';
                fivetranSection.appendChild(fivetranExamplesDiv);
                container.appendChild(fivetranSection);
            }
            
            const examplesDiv = document.getElementById('fivetran-examples');
            if (examplesDiv.children.length === 0) {
                examplesDiv.innerHTML = '<p style="color: #666; padding: 20px;">Fivetran examples will be loaded from the server...</p>';
                try {
                    const response = await fetch('/api/fivetran-examples');
                    const examples = await response.json();
                    
                    examplesDiv.innerHTML = '';
                    examples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        const titleDiv = document.createElement('div');
                        titleDiv.className = 'example-title';
                        titleDiv.textContent = example.title;
                        const descDiv = document.createElement('div');
                        descDiv.className = 'example-desc';
                        descDiv.textContent = example.desc;
                        btn.appendChild(titleDiv);
                        btn.appendChild(descDiv);
                        btn.onclick = () => {
                            closeExamplesModal();
                            inputEditor.setValue(example.query);
                            document.getElementById('from-dialect').value = example.language || '';
                            if (example.toLanguage) {
                                document.getElementById('to-dialect').value = example.toLanguage;
                            }
                            updateUITitles();
                            translateQuery();
                        };
                        examplesDiv.appendChild(btn);
                    });
                } catch (error) {
                    console.error('Failed to load Fivetran examples:', error);
                    examplesDiv.innerHTML = '<p style="color: #c5221f; padding: 20px;">Failed to load Fivetran examples.</p>';
                }
            }
        }
        
        async function loadSQLExamples() {
            try {
                const response = await fetch('/api/sql-examples');
                const examples = await response.json();
                sqlExamples.push(...examples);
                loadExamples();
            } catch (error) {
                console.error('Failed to load SQL examples:', error);
            }
        }
        
        
        async function translateQuery() {
            const input = inputEditor.getValue();
            const errorDiv = document.getElementById('error');
            const detectedDialectSpan = document.getElementById('detected-dialect');
            
            // Clear previous results
            outputEditor.setValue('');
            errorDiv.style.display = 'none';
            errorDiv.className = '';
            detectedDialectSpan.style.display = 'none';
            
            if (!input.trim()) {
                return;
            }
            
            const currentMode = getCurrentMode();
            const fromDialect = document.getElementById('from-dialect').value;
            const toDialect = document.getElementById('to-dialect').value;
            
            try {
                if (currentMode === 'asql-to-sql') {
                    // ASQL to SQL
                    const response = await fetch('/api/compile', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ asql: input, dialect: toDialect || '' })
                    });
                    
                    if (!response.ok) {
                        const errorText = await response.text();
                        errorDiv.textContent = `HTTP Error ${response.status}: ${errorText}`;
                        errorDiv.className = 'error';
                        errorDiv.style.display = 'block';
                        return;
                    }
                    
                    const data = await response.json();
                    
                    if (data.error) {
                        errorDiv.textContent = data.error;
                        errorDiv.className = 'error';
                        errorDiv.style.display = 'block';
                    } else                     if (data.sql) {
                        outputEditor.setValue(data.sql);
                        // Update URL after successful translation
                        updateURL();
                    } else {
                        errorDiv.textContent = 'Unexpected response format: ' + JSON.stringify(data);
                        errorDiv.className = 'error';
                        errorDiv.style.display = 'block';
                    }
                } else if (currentMode === 'sql-to-asql') {
                    // SQL to ASQL
                    let sourceDialect = fromDialect;
                    
                    // First, try to detect dialect if not specified
                    if (!sourceDialect) {
                        const detectResponse = await fetch('/api/detect-dialect', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ sql: input })
                        });
                        const detectData = await detectResponse.json();
                        if (detectData.dialect) {
                            sourceDialect = detectData.dialect;
                            detectedDialectSpan.textContent = `Detected: ${sourceDialect}`;
                            detectedDialectSpan.style.display = 'inline';
                        }
                    }
                    
                    const response = await fetch('/api/reverse-compile', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ 
                            sql: input, 
                            source_dialect: sourceDialect || '' 
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.error) {
                        errorDiv.textContent = data.error;
                        errorDiv.className = 'error';
                        errorDiv.style.display = 'block';
                    } else {
                        outputEditor.setValue(data.asql);
                        // Update URL after successful translation
                        updateURL();
                    }
                } else if (currentMode === 'sql-to-sql') {
                    // SQL to SQL (dialect conversion)
                    // First convert SQL to ASQL, then back to target SQL dialect
                    let sourceDialect = fromDialect;
                    
                    // Detect source dialect if not specified
                    if (!sourceDialect) {
                        const detectResponse = await fetch('/api/detect-dialect', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ sql: input })
                        });
                        const detectData = await detectResponse.json();
                        if (detectData.dialect) {
                            sourceDialect = detectData.dialect;
                            detectedDialectSpan.textContent = `Detected: ${sourceDialect}`;
                            detectedDialectSpan.style.display = 'inline';
                        }
                    }
                    
                    // Convert to ASQL first
                    const reverseResponse = await fetch('/api/reverse-compile', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ 
                            sql: input, 
                            source_dialect: sourceDialect || '' 
                        })
                    });
                    
                    const reverseData = await reverseResponse.json();
                    
                    if (reverseData.error) {
                        errorDiv.textContent = reverseData.error;
                        errorDiv.className = 'error';
                        errorDiv.style.display = 'block';
                        return;
                    }
                    
                    // Then convert ASQL to target SQL dialect
                    const compileResponse = await fetch('/api/compile', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ asql: reverseData.asql, dialect: toDialect || '' })
                    });
                    
                    const compileData = await compileResponse.json();
                    
                    if (compileData.error) {
                        errorDiv.textContent = compileData.error;
                        errorDiv.className = 'error';
                        errorDiv.style.display = 'block';
                    } else {
                        outputEditor.setValue(compileData.sql);
                        // Update URL after successful translation
                        updateURL();
                    }
                } else {
                    // asql-to-asql (no-op or copy)
                    outputEditor.setValue(input);
                }
            } catch (error) {
                errorDiv.textContent = 'Error: ' + error.message;
                errorDiv.className = 'error';
                errorDiv.style.display = 'block';
            }
        }
        
        function clearAll() {
            inputEditor.setValue('');
            outputEditor.setValue('');
            document.getElementById('error').style.display = 'none';
            document.getElementById('detected-dialect').style.display = 'none';
        }
        
        function copyInput() {
            const text = inputEditor.getValue();
            navigator.clipboard.writeText(text).then(() => {
                // Visual feedback could be added here
            });
        }
        
        function copyOutput() {
            const text = outputEditor.getValue();
            navigator.clipboard.writeText(text).then(() => {
                // Visual feedback could be added here
            });
        }
        
            // Auto-translate on change (debounced)
            let translateTimeout;
            let urlUpdateTimeout;
            inputEditor.on('change', () => {
                clearTimeout(translateTimeout);
                translateTimeout = setTimeout(translateQuery, 500);
                // Update URL on input change (debounced)
                clearTimeout(urlUpdateTimeout);
                urlUpdateTimeout = setTimeout(updateURL, 1000);
            });
            
            // Auto-detect dialect when SQL is pasted
            inputEditor.on('paste', () => {
                setTimeout(() => {
                    const fromDialect = document.getElementById('from-dialect').value;
                    if (fromDialect !== 'asql' && !fromDialect) {
                        translateQuery();
                    }
                }, 100);
            });
            
            // Initial load (after editors are initialized)
            try {
                updateUITitles();
                loadExamples();
                // Auto-translate if we have input query (always translate on load)
                // If sql_t is provided, output is already set, so we can skip translation
                if (sql_f && !sql_t) {
                    // We have input but no output - translate it
                    translateQuery();
                } else if (sql_f && sql_t) {
                    // Both provided - output is already set, no need to translate
                    // But ensure UI titles are correct
                } else {
                    // Default behavior - translate the default query
                    translateQuery();
                }
            } catch (e) {
                console.error('Error during initial load:', e);
                // Try to load examples anyway
                try {
                    loadExamples();
                } catch (e2) {
                    console.error('Failed to load examples:', e2);
                }
            }
            } // end initializeEditors
            
            // Start checking for ASQL mode and initialize editors when ready
            checkASQLMode();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Render the playground interface."""
    return render_template_string(PLAYGROUND_HTML)

@app.route('/api/compile', methods=['POST'])
def api_compile():
    """API endpoint to compile ASQL to SQL."""
    try:
        data = request.get_json()
        asql_query = data.get('asql', '')
        dialect = data.get('dialect', '')
        
        if not asql_query.strip():
            return jsonify({'error': 'Empty ASQL query'})
        
        sql = compile(asql_query, dialect=dialect if dialect else None, pretty=True)
        return jsonify({'sql': sql})
        
    except ASQLSyntaxError as e:
        return jsonify({'error': f'Syntax Error: {str(e)}'})
    except ASQLCompilationError as e:
        return jsonify({'error': f'Compilation Error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'})

@app.route('/api/reverse-compile', methods=['POST'])
def api_reverse_compile():
    """API endpoint to compile SQL to ASQL."""
    try:
        data = request.get_json()
        sql_query = data.get('sql', '')
        source_dialect = data.get('source_dialect', '')
        
        if not sql_query.strip():
            return jsonify({'error': 'Empty SQL query'})
        
        asql = reverse_compile(sql_query, source_dialect=source_dialect if source_dialect else None)
        return jsonify({'asql': asql})
        
    except ASQLCompilationError as e:
        error_msg = str(e)
        # Clean up error messages - remove ANSI escape codes
        error_msg = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
        # Truncate very long error messages
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        return jsonify({'error': f'Compilation Error: {error_msg}'})
    except Exception as e:
        error_msg = str(e)
        # Clean up error messages - remove ANSI escape codes
        error_msg = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
        # Truncate very long error messages
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        return jsonify({'error': f'Error: {error_msg}'})

@app.route('/api/detect-dialect', methods=['POST'])
def api_detect_dialect():
    """API endpoint to detect SQL dialect."""
    try:
        data = request.get_json()
        sql_query = data.get('sql', '')

        if not sql_query.strip():
            return jsonify({'dialect': None})

        dialect = detect_dialect(sql_query)
        return jsonify({'dialect': dialect})

    except Exception as e:
        return jsonify({'dialect': None, 'error': str(e)})

@app.route('/api/normalize', methods=['POST'])
def api_normalize():
    """Normalize ASQL to configured style."""
    try:
        data = request.get_json()
        asql_query = data.get('asql', '')
        style_config = data.get('style', {})
        
        if not asql_query.strip():
            return jsonify({'error': 'Empty ASQL query'})
        
        # Build config from style options
        from asql.config import ASQLConfig, StyleConfig
        
        style = StyleConfig(
            equality=style_config.get('equality', 'single'),
            count=style_config.get('count', 'hash'),
            coalesce=style_config.get('coalesce', 'operator'),
            descending=style_config.get('descending', 'prefix'),
            cast=style_config.get('cast', 'double_colon'),
            quotes=style_config.get('quotes', 'double'),
            week_start=style_config.get('week_start', 'monday'),
            sort_keyword=style_config.get('sort_keyword', 'order_by'),
            squash_empty_ctes=style_config.get('squash_empty_ctes', True),
            keep_final_empty_cte=style_config.get('keep_final_empty_cte', False),
        )
        
        config = ASQLConfig(style=style)
        
        # Normalize: ASQL → SQL → ASQL (with config)
        sql = compile(asql_query, dialect='snowflake')
        normalized = reverse_compile(sql, config=config)
        
        return jsonify({'asql': normalized})
        
    except ASQLSyntaxError as e:
        return jsonify({'error': f'Syntax Error: {str(e)}'})
    except ASQLCompilationError as e:
        return jsonify({'error': f'Compilation Error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'})

@app.route('/api/debug/examples-path', methods=['GET'])
def api_debug_examples_path():
    """Debug endpoint to check examples directory access."""
    import os
    from pathlib import Path
    
    debug_info = {
        'current_working_directory': os.getcwd(),
        'playground_file': __file__,
        'playground_dir': str(Path(__file__).parent),
        'possible_paths': [],
        'found_path': None,
        'examples_count': 0
    }
    
    possible_paths = [
        Path(__file__).parent / 'examples' / 'real',
        Path('examples') / 'real',
        Path(os.getcwd()) / 'examples' / 'real',
        Path(__file__).parent.parent / 'examples' / 'real',
    ]
    
    for path in possible_paths:
        path_str = str(path)
        exists = path.exists()
        is_dir = path.is_dir() if exists else False
        file_count = len(list(path.glob('*.sql'))) if exists and is_dir else 0
        
        debug_info['possible_paths'].append({
            'path': path_str,
            'exists': exists,
            'is_dir': is_dir,
            'file_count': file_count
        })
        
        if exists and is_dir and not debug_info['found_path']:
            debug_info['found_path'] = path_str
            debug_info['examples_count'] = file_count
    
    return jsonify(debug_info)

@app.route('/api/fivetran-examples', methods=['GET'])
def api_fivetran_examples():
    """API endpoint to get Fivetran dbt examples."""
    import re
    import os
    from pathlib import Path
    
    examples = []
    
    # Try multiple possible paths for the examples directory
    # Railway might have different working directory or path resolution
    possible_paths = [
        Path(__file__).parent / 'examples' / 'real',  # Relative to playground.py
        Path('examples') / 'real',  # Relative to current working directory
        Path(os.getcwd()) / 'examples' / 'real',  # Absolute from cwd
        Path(__file__).parent.parent / 'examples' / 'real',  # One level up
    ]
    
    real_examples_dir = None
    for path in possible_paths:
        if path.exists() and path.is_dir():
            real_examples_dir = path
            break
    
    # Load all SQL files from examples/real directory
    if real_examples_dir and real_examples_dir.exists():
        sql_files = sorted(real_examples_dir.glob('dbt_*.sql'))
        
        for sql_file in sql_files:
            try:
                content = sql_file.read_text()
                
                # Skip files that are too small or contain "404: Not Found"
                if len(content) < 100 or "404: Not Found" in content:
                    continue
                
                # Parse metadata from header comments
                source = None
                model = None
                dialect = "snowflake"  # Default
                
                for line in content.split('\n')[:10]:
                    if line.startswith('-- Source:'):
                        source = line.replace('-- Source:', '').strip()
                    elif line.startswith('-- Model:'):
                        model = line.replace('-- Model:', '').strip()
                    elif line.startswith('-- Dialect:'):
                        dialect = line.replace('-- Dialect:', '').strip().lower()
                
                # Generate title and description from filename
                filename = sql_file.stem
                # Remove dbt_ prefix and dialect suffix (e.g., _snowflake, _bigquery)
                # Extract dialect from filename first
                filename_dialect = None
                for d in ['snowflake', 'bigquery', 'postgres', 'redshift', 'mysql']:
                    if filename.endswith('_' + d):
                        filename_dialect = d
                        break
                
                # Remove dbt_ prefix and dialect suffix
                name_base = filename.replace('dbt_', '')
                if filename_dialect:
                    name_base = name_base.replace('_' + filename_dialect, '')
                name_parts = name_base.split('_')
                
                # Extract repo name (first part)
                repo = name_parts[0] if name_parts else 'unknown'
                repo_display = repo.replace('_', ' ').title()
                
                # Generate model name (rest of parts)
                model_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else name_parts[0] if name_parts else 'model'
                model_name = model_name.replace('__', ' ').replace('_', ' ').title()
                
                # Create title
                title = f"{repo_display}: {model_name}"
                
                # Create description
                desc = f"Real query from {repo_display} dbt package"
                if model:
                    desc += f" ({model})"
                
                # Use dialect from filename if available, otherwise from header
                final_dialect = filename_dialect or dialect
                
                # Map dialect names
                dialect_map = {
                    'snowflake': 'snowflake',
                    'bigquery': 'bigquery',
                    'postgres': 'postgres',
                    'redshift': 'redshift'
                }
                sql_dialect = dialect_map.get(final_dialect.lower(), 'snowflake')
                
                # Strip Jinja templates to make it regular SQL
                cleaned_content = strip_jinja_templates(content)
                
                examples.append({
                    "title": title,
                    "desc": desc,
                    "language": sql_dialect,
                    "toLanguage": "asql",
                    "query": cleaned_content
                })
            except Exception as e:
                # Skip files that can't be read - log for debugging
                import sys
                print(f"Warning: Could not load example {sql_file}: {e}", file=sys.stderr)
                continue
    
    return jsonify(examples)

# // TODO - why an endpoint?  just put this in the html...
@app.route('/api/sql-examples', methods=['GET'])
def api_sql_examples():
    """API endpoint to get SQL translation examples."""
    examples = [
        {
            "title": "BigQuery CTE with Joins",
            "desc": "Complex query with CTEs and aggregations",
            "dialect": "bigquery",
            "query": """WITH active_users AS (
  SELECT user_id, country, signup_date
  FROM users
  WHERE status = 'active' AND signup_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),
user_orders AS (
  SELECT au.user_id, au.country,
    COUNT(o.order_id) AS order_count,
    SUM(o.amount) AS total_spent
  FROM active_users au
  LEFT JOIN orders o ON au.user_id = o.user_id
  GROUP BY au.user_id, au.country
)
SELECT country,
  COUNT(*) AS user_count,
  AVG(order_count) AS avg_orders,
  SUM(total_spent) AS total_revenue
FROM user_orders
GROUP BY country
ORDER BY total_revenue DESC
LIMIT 10"""
        },
        {
            "title": "Redshift Window Functions",
            "desc": "Running totals with window functions",
            "dialect": "redshift",
            "query": """SELECT product_id, category, sale_date, amount,
  SUM(amount) OVER (
    PARTITION BY category 
    ORDER BY sale_date 
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_total
FROM sales
WHERE sale_date >= '2024-01-01'
ORDER BY category, sale_date"""
        },
        {
            "title": "PostgreSQL Complex Join",
            "desc": "Multiple joins with HAVING clause",
            "dialect": "postgres",
            "query": """SELECT u.user_id, u.email,
  COUNT(DISTINCT o.order_id) AS order_count,
  SUM(o.amount) AS total_spent,
  AVG(o.amount) AS avg_order_value
FROM users u
INNER JOIN orders o ON u.user_id = o.user_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
WHERE u.created_at >= '2024-01-01' AND o.status = 'completed'
GROUP BY u.user_id, u.email
HAVING COUNT(DISTINCT o.order_id) > 5
ORDER BY total_spent DESC
LIMIT 20"""
        },
        {
            "title": "BigQuery Nested CTEs",
            "desc": "Multiple CTEs with window functions",
            "dialect": "bigquery",
            "query": """WITH monthly_sales AS (
  SELECT DATE_TRUNC(order_date, MONTH) AS month, region,
    SUM(amount) AS revenue, COUNT(*) AS order_count
  FROM orders
  WHERE order_date >= '2023-01-01'
  GROUP BY month, region
),
region_rankings AS (
  SELECT month, region, revenue, order_count,
    RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS revenue_rank
  FROM monthly_sales
)
SELECT month, region, revenue, order_count
FROM region_rankings
WHERE revenue_rank <= 3
ORDER BY month DESC, revenue DESC"""
        },
        {
            "title": "Redshift Date Aggregation",
            "desc": "Weekly aggregations with HAVING",
            "dialect": "redshift",
            "query": """SELECT DATE_TRUNC('week', event_timestamp) AS week, event_type,
  COUNT(*) AS event_count,
  COUNT(DISTINCT user_id) AS unique_users
FROM events
WHERE event_timestamp >= '2024-01-01'
  AND event_type IN ('click', 'view', 'purchase')
GROUP BY week, event_type
HAVING COUNT(*) > 100
ORDER BY week DESC, event_count DESC"""
        },
        {
            "title": "BigQuery Multiple CTEs",
            "desc": "Complex multi-CTE query",
            "dialect": "bigquery",
            "query": """WITH customers AS (
  SELECT DISTINCT user_id, country, signup_date
  FROM users WHERE status = 'active'
),
orders_summary AS (
  SELECT user_id, COUNT(*) AS order_count, SUM(amount) AS total_amount
  FROM orders WHERE status = 'completed'
  GROUP BY user_id
),
customer_metrics AS (
  SELECT c.user_id, c.country,
    COALESCE(o.order_count, 0) AS order_count,
    COALESCE(o.total_amount, 0) AS total_amount
  FROM customers c
  LEFT JOIN orders_summary o ON c.user_id = o.user_id
)
SELECT country, COUNT(*) AS customer_count,
  AVG(order_count) AS avg_orders,
  SUM(total_amount) AS total_revenue
FROM customer_metrics
GROUP BY country
ORDER BY total_revenue DESC"""
        },
        {
            "title": "PostgreSQL Subquery",
            "desc": "Correlated subquery example",
            "dialect": "postgres",
            "query": """SELECT p.product_id, p.name, p.price,
  (SELECT AVG(price) FROM products WHERE category = p.category) AS avg_category_price
FROM products p
WHERE p.price > (SELECT AVG(price) FROM products WHERE category = p.category)
ORDER BY p.price DESC"""
        },
        {
            "title": "BigQuery Time Series",
            "desc": "Time series analysis with CTEs",
            "dialect": "bigquery",
            "query": """WITH daily_metrics AS (
  SELECT DATE(timestamp) AS date, event_type,
    COUNT(*) AS event_count,
    COUNT(DISTINCT user_id) AS unique_users
  FROM events
  WHERE timestamp >= TIMESTAMP('2024-01-01')
    AND timestamp < TIMESTAMP('2024-02-01')
  GROUP BY date, event_type
),
daily_totals AS (
  SELECT date, SUM(event_count) AS total_events, SUM(unique_users) AS total_users
  FROM daily_metrics
  GROUP BY date
)
SELECT dt.date, dt.total_events, dt.total_users, dm.event_type, dm.event_count
FROM daily_totals dt
LEFT JOIN daily_metrics dm ON dt.date = dm.date
ORDER BY dt.date DESC, dm.event_count DESC"""
        },
        {
            "title": "Redshift CASE Statement",
            "desc": "CASE with aggregations",
            "dialect": "redshift",
            "query": """SELECT user_id, amount,
  CASE 
    WHEN amount < 50 THEN 'low'
    WHEN amount < 200 THEN 'medium'
    ELSE 'high'
  END AS order_tier,
  COUNT(*) AS order_count
FROM orders
WHERE order_date >= '2024-01-01'
GROUP BY user_id, amount, order_tier
ORDER BY amount DESC
LIMIT 50"""
        },
        {
            "title": "BigQuery Array Operations",
            "desc": "Array aggregations",
            "dialect": "bigquery",
            "query": """SELECT category, COUNT(*) AS product_count,
  ARRAY_AGG(DISTINCT brand IGNORE NULLS) AS brands,
  AVG(price) AS avg_price
FROM products
WHERE in_stock = TRUE
GROUP BY category
ORDER BY product_count DESC"""
        },
        {
            "title": "PostgreSQL JSON Operations",
            "desc": "JSON field extraction",
            "dialect": "postgres",
            "query": """SELECT user_id, metadata->>'source' AS source, COUNT(*) AS event_count
FROM events
WHERE metadata ? 'source' AND event_timestamp >= '2024-01-01'
GROUP BY user_id, metadata->>'source'
ORDER BY event_count DESC
LIMIT 100"""
        },
        {
            "title": "Simple SELECT with WHERE",
            "desc": "Basic filtering example",
            "dialect": "",
            "query": """SELECT user_id, email, status
FROM users
WHERE status = 'active' AND created_at >= '2024-01-01'
ORDER BY created_at DESC
LIMIT 100"""
        }
    ]
    return jsonify(examples)

if __name__ == '__main__':
    # Get port from environment variable (Railway provides PORT)
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    print("Starting ASQL Playground...")
    print(f"Open http://localhost:{port} in your browser")
    app.run(debug=debug, host='0.0.0.0', port=port)
