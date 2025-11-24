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
    
    for line in lines:
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
        
        # Remove complex macros like {{ google_ads_persist_pass_through_columns(...) }}
        # These are typically entire lines that should be removed
        if re.search(r'\{\{\s*\w+_persist_pass_through_columns\s*\(', line, re.IGNORECASE):
            continue
        
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
            continue
        
        # Check if line is entirely a macro before processing
        line_before = line
        # Replace remaining {{ ... }} blocks inline (preserve the line)
        line = re.sub(r'\{\{[^}]*\}\}', '', line)
        
        # Remove any remaining {% ... %} blocks (catch-all)
        line = re.sub(r'\{%[^%]*%\}', '', line)
        
        # If the line was entirely a macro and is now empty/whitespace, skip it
        if not line.strip() and re.search(r'\{\{|%\}', line_before):
            continue
        
        # Clean up trailing commas that might be left after macro removal
        line = re.sub(r',\s*$', '', line)
        
        # Only add non-empty lines
        if line.strip():
            result_lines.append(line)
    
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
    return send_from_directory(syntax_dir, filename)

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
            padding: 20px;
        }
        
        h1 {
            text-align: center;
            margin-bottom: 30px;
            color: #333;
            font-weight: 400;
        }
        
        .language-selectors {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
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
            margin-top: 20px;
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
            margin-bottom: 20px;
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
            min-height: 350px;
        }
        
        
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
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
        
        .error {
            background: #fce8e6;
            color: #c5221f;
            padding: 12px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 13px;
        }
        
        .examples {
            background: white;
            border: 1px solid #dadce0;
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .examples h2 {
            margin-bottom: 15px;
            color: #333;
            font-weight: 400;
        }
        
        .example-section {
            margin-bottom: 25px;
        }
        
        .example-section h3 {
            margin-bottom: 10px;
            color: #333;
            font-size: 16px;
            font-weight: 400;
        }
        
        .example-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 10px;
        }
        
        .example-btn {
            padding: 8px 12px;
            background: white;
            border: 1px solid #dadce0;
            border-radius: 4px;
            cursor: pointer;
            text-align: left;
            font-size: 13px;
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
            min-height: 350px;
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
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h1 style="margin: 0;">🚀 ASQL Playground</h1>
            <a href="/docs/" style="color: #ea4335; text-decoration: none; font-weight: 500; padding: 8px 16px; border: 1px solid #ea4335; border-radius: 4px; display: inline-block;">← Back to Docs</a>
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
                    <option value="bigquery" selected>BigQuery</option>
                    <option value="snowflake">Snowflake</option>
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
        
        <div class="examples">
            <h2>📚 Example Queries</h2>
            <div id="examples-container"></div>
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
        
        // Wait for DOM and ensure ASQL mode is loaded
        document.addEventListener('DOMContentLoaded', function() {
            // Verify ASQL mode is available
            if (!CodeMirror.modes['asql']) {
                console.error('ASQL mode not loaded! Check that /static/syntax/codemirror/asql-mode.js is accessible.');
            }
            
            // Initialize CodeMirror editors
            inputEditor = CodeMirror(document.getElementById('input-editor'), {
                value: `from users
where status == "active"
group by country ( # as total_users )
sort -total_users
take 10`,
                mode: 'text/x-asql',
                lineNumbers: true,
                matchBrackets: true,
                autoCloseBrackets: true,
                theme: 'default',
                lineWrapping: true,
                placeholder: 'Enter your query here...'
            });
        
            outputEditor = CodeMirror(document.getElementById('output-editor'), {
                value: '',
                mode: 'text/x-sql',
                lineNumbers: true,
                matchBrackets: true,
                autoCloseBrackets: true,
                theme: 'default',
                readOnly: true,
                lineWrapping: true,
                placeholder: 'Translation will appear here...'
            });
        
        function getCurrentMode() {
            const fromDialect = document.getElementById('from-dialect').value;
            const toDialect = document.getElementById('to-dialect').value;
            
            if (fromDialect === 'asql' && toDialect !== 'asql') {
                return 'asql-to-sql';
            } else if (fromDialect !== 'asql' && toDialect === 'asql') {
                return 'sql-to-asql';
            } else if (fromDialect === 'asql' && toDialect === 'asql') {
                return 'asql-to-asql';
            } else {
                return 'sql-to-sql';
            }
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
sort -total_users`
            },
            {
                title: "TAKE/LIMIT",
                desc: "Limit results",
                query: `from users
take 10`
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
sort -revenue
take 10`
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
sort -total_spent
take 10`
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
sort -lifetime_value
take 50`
            },
            {
                title: "Sales Funnel Analysis",
                desc: "Multi-stage sales pipeline with joins",
                query: `from leads
where source == "website"
    and created_at >= "2024-01-01"
join opportunities on leads.id == opportunities.lead_id
where opportunities.stage != "lost"
join deals on opportunities.id == deals.opportunity_id
where deals.status == "closed"
group by leads.source, deals.region ( 
    sum(deals.amount) as revenue,
    # as closed_deals,
    avg(deals.amount) as avg_deal_size 
)
sort -revenue`
            },
            {
                title: "Product Performance Pipeline",
                desc: "Product analysis with multiple filters and aggregations",
                query: `from products
where category == "electronics"
    and in_stock == true
join order_items on products.id == order_items.product_id
join orders on order_items.order_id == orders.id
where orders.status == "completed"
    and orders.created_at >= "2024-01-01"
group by products.id, products.name ( 
    sum(order_items.quantity) as units_sold,
    sum(order_items.price * order_items.quantity) as revenue,
    # as order_count 
)
sort -revenue
take 20`
            },
            {
                title: "User Engagement Pipeline",
                desc: "User activity analysis with multiple CTEs",
                query: `from users
where created_at >= "2023-01-01"
join events on users.id == events.user_id
where events.event_type == "purchase"
    and events.timestamp >= "2024-01-01"
group by users.id, users.country ( 
    # as purchase_count,
    sum(events.value) as total_spent,
    max(events.timestamp) as last_purchase_date 
)
where total_spent > 100
sort -total_spent
take 100`
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
sort transaction_date desc, -monthly_revenue`
            },
            {
                title: "Cohort Analysis Pipeline",
                desc: "User cohort analysis with complex joins",
                query: `from users
where signup_date >= "2023-01-01"
join orders on users.id == orders.user_id
where orders.status == "completed"
group by 
    date_trunc(users.signup_date, "month") as cohort_month,
    users.country ( 
    # as users_in_cohort,
    sum(orders.total) as cohort_revenue,
    avg(orders.total) as avg_order_value 
)
sort cohort_month desc, -cohort_revenue`
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
where total_spent > 500
sort -total_spent
take 25`
            },
        ];
        
        const sqlExamples = [];
        
        // Update UI when dialects change (set up after DOM is ready)
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('from-dialect').addEventListener('change', () => {
                ensureFromNotPostgresWhenToEmpty();
                updateUITitles();
                translateQuery();
            });
            
            document.getElementById('to-dialect').addEventListener('change', () => {
                ensureFromNotPostgresWhenToEmpty();
                updateUITitles();
                translateQuery();
            });
        });
        
        function loadExamples() {
            const container = document.getElementById('examples-container');
            container.innerHTML = '';
            
            const currentMode = getCurrentMode();
            
            if (currentMode === 'asql-to-sql' || currentMode === 'asql-to-asql') {
                // Basic ASQL Examples section
                const section = document.createElement('div');
                section.className = 'example-section';
                section.innerHTML = '<h3>ASQL Examples</h3><p style="color: #666; margin-bottom: 15px; font-size: 13px;">Basic ASQL queries that showcase the language syntax. These examples shouldn\'t look too different from regular SQL - ASQL is designed to be familiar and intuitive.</p><div class="example-list" id="asql-examples"></div>';
                container.appendChild(section);
                
                const examplesDiv = document.getElementById('asql-examples');
                asqlExamples.forEach(example => {
                    const btn = document.createElement('button');
                    btn.className = 'example-btn';
                    btn.innerHTML = `
                        <div class="example-title">${example.title}</div>
                        <div class="example-desc">${example.desc}</div>
                    `;
                    btn.onclick = () => {
                        // Set "from" to ASQL if not already set
                        const fromDialect = document.getElementById('from-dialect').value;
                        if (fromDialect !== 'asql') {
                            document.getElementById('from-dialect').value = 'asql';
                            updateUITitles();
                        }
                        inputEditor.setValue(example.query);
                        translateQuery();
                    };
                    examplesDiv.appendChild(btn);
                });
                
                // ASQL Pipeline Examples section
                const pipelineSection = document.createElement('div');
                pipelineSection.className = 'example-section';
                pipelineSection.innerHTML = '<h3>ASQL Pipeline Examples</h3><p style="color: #666; margin-bottom: 15px; font-size: 13px;">Complex queries that showcase pipeline features and generate multiple CTEs.</p><div class="example-list" id="asql-pipeline-examples"></div>';
                container.appendChild(pipelineSection);
                
                const pipelineExamplesDiv = document.getElementById('asql-pipeline-examples');
                asqlPipelineExamples.forEach(example => {
                    const btn = document.createElement('button');
                    btn.className = 'example-btn';
                    btn.innerHTML = `
                        <div class="example-title">${example.title}</div>
                        <div class="example-desc">${example.desc}</div>
                    `;
                    btn.onclick = () => {
                        // Set "from" to ASQL if not already set
                        const fromDialect = document.getElementById('from-dialect').value;
                        if (fromDialect !== 'asql') {
                            document.getElementById('from-dialect').value = 'asql';
                            updateUITitles();
                        }
                        inputEditor.setValue(example.query);
                        translateQuery();
                    };
                    pipelineExamplesDiv.appendChild(btn);
                });
            } else {
                const section = document.createElement('div');
                section.className = 'example-section';
                section.innerHTML = '<h3>SQL Translation Examples</h3><div class="example-list" id="sql-examples"></div>';
                container.appendChild(section);
                
                const examplesDiv = document.getElementById('sql-examples');
                if (sqlExamples.length === 0) {
                    examplesDiv.innerHTML = '<p style="color: #666; padding: 20px;">SQL examples will be loaded from the server...</p>';
                    loadSQLExamples();
                } else {
                    sqlExamples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        btn.innerHTML = `
                            <div class="example-title">${example.title}</div>
                            <div class="example-desc">${example.desc}</div>
                        `;
                        btn.onclick = () => {
                            inputEditor.setValue(example.query);
                            document.getElementById('from-dialect').value = example.dialect || '';
                            updateUITitles();
                            translateQuery();
                        };
                        examplesDiv.appendChild(btn);
                    });
                }
            }
            
            // Always load Fivetran dbt examples
            loadFivetranExamples();
        }
        
        async function loadFivetranExamples() {
            const container = document.getElementById('examples-container');
            
            // Check if Fivetran section already exists
            let fivetranSection = document.getElementById('fivetran-examples-section');
            if (!fivetranSection) {
                fivetranSection = document.createElement('div');
                fivetranSection.id = 'fivetran-examples-section';
                fivetranSection.className = 'example-section';
                fivetranSection.innerHTML = '<h3>Fivetran_dbt Examples</h3><p style="color: #666; margin-bottom: 15px; font-size: 13px;">Here are some examples of some extensive queries used in the fivetran_dbt libraries.</p><div class="example-list" id="fivetran-examples"></div>';
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
                        btn.innerHTML = `
                            <div class="example-title">${example.title}</div>
                            <div class="example-desc">${example.desc}</div>
                        `;
                        btn.onclick = () => {
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
                    } else if (data.sql) {
                        outputEditor.setValue(data.sql);
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
            inputEditor.on('change', () => {
                clearTimeout(translateTimeout);
                translateTimeout = setTimeout(translateQuery, 500);
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
            updateUITitles();
            loadExamples();
            translateQuery();
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
        return jsonify({'error': f'Compilation Error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'})

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

@app.route('/api/fivetran-examples', methods=['GET'])
def api_fivetran_examples():
    """API endpoint to get Fivetran dbt examples."""
    import re
    from pathlib import Path
    
    examples = []
    real_examples_dir = Path(__file__).parent / 'examples' / 'real'
    
    # Load all SQL files from examples/real directory
    if real_examples_dir.exists():
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
                # Skip files that can't be read
                continue
    
    # Add the original hardcoded examples if we didn't find many files
    if len(examples) < 5:
        examples.extend([
            {
                "title": "Shopify: Line Items with Multiple Joins",
            "desc": "Complex query joining orders, transactions, and refunds (dbt_shopify)",
            "language": "bigquery",
            "toLanguage": "asql",
            "query": """WITH line_items AS (
    SELECT * FROM stg_shopify_gql__order_line
),
orders AS (
    SELECT * FROM stg_shopify_gql__order
),
transactions AS (
    SELECT order_id, kind, 
           STRING_AGG(CAST(transaction_id AS STRING), ', ') AS transaction_id,
           STRING_AGG(gateway, ', ') AS gateway
    FROM stg_shopify_gql__transaction
    WHERE kind = 'capture' AND status = 'success'
    GROUP BY order_id, kind
),
refund_transactions AS (
    SELECT order_id, SUM(amount_shop) AS total_order_refund_amount
    FROM stg_shopify_gql__transaction
    WHERE kind = 'refund'
    GROUP BY order_id
)
SELECT 
    li.order_id,
    li.order_line_id,
    o.created_timestamp AS created_at,
    o.currency,
    li.quantity,
    li.price_shop_amount AS unit_amount,
    (li.quantity * li.price_shop_amount) AS total_amount,
    t.transaction_id AS payment_id,
    t.gateway AS payment_method,
    rt.total_order_refund_amount AS refund_amount
FROM line_items li
LEFT JOIN orders o ON li.order_id = o.order_id
LEFT JOIN transactions t ON o.order_id = t.order_id
LEFT JOIN refund_transactions rt ON o.order_id = rt.order_id"""
        },
        {
            "title": "Stripe: Customer Overview with Aggregations",
            "desc": "Multiple CASE statements aggregating transaction types (dbt_stripe)",
            "language": "bigquery",
            "toLanguage": "asql",
            "query": """WITH transactions_grouped AS (
    SELECT
        customer_id,
        SUM(CASE WHEN balance_transaction_type IN ('charge', 'payment') 
            THEN balance_transaction_amount ELSE 0 END) AS total_sales,
        SUM(CASE WHEN balance_transaction_type IN ('payment_refund', 'refund') 
            THEN balance_transaction_amount ELSE 0 END) AS total_refunds,
        SUM(balance_transaction_amount) AS total_gross_transaction_amount,
        SUM(balance_transaction_fee) AS total_fees,
        COUNT(CASE WHEN balance_transaction_type IN ('charge', 'payment') 
            THEN 1 END) AS total_sales_count,
        MIN(CASE WHEN balance_transaction_type IN ('charge', 'payment') 
            THEN balance_transaction_created_at END) AS first_sale_date,
        MAX(CASE WHEN balance_transaction_type IN ('charge', 'payment') 
            THEN balance_transaction_created_at END) AS most_recent_sale_date
    FROM stripe__balance_transactions
    WHERE balance_transaction_type IN ('payment', 'charge', 'payment_refund', 'refund')
    GROUP BY customer_id
)
SELECT 
    c.customer_id,
    c.description AS customer_description,
    c.created_at AS customer_created_at,
    COALESCE(tg.total_sales, 0) AS total_sales,
    COALESCE(tg.total_refunds, 0) AS total_refunds,
    COALESCE(tg.total_gross_transaction_amount, 0) AS total_gross_transaction_amount,
    COALESCE(tg.total_fees, 0) AS total_fees,
    tg.first_sale_date,
    tg.most_recent_sale_date
FROM stg_stripe__customer c
LEFT JOIN transactions_grouped tg ON c.customer_id = tg.customer_id"""
        },
        {
            "title": "Zendesk: Ticket Enrichment with Multiple User Joins",
            "desc": "Complex joins to requester, submitter, assignee users (dbt_zendesk)",
            "language": "bigquery",
            "toLanguage": "asql",
            "query": """WITH ticket AS (
    SELECT * FROM int_zendesk__ticket_aggregates
),
users AS (
    SELECT * FROM int_zendesk__user_aggregates
),
requester_updates AS (
    SELECT * FROM int_zendesk__requester_updates
),
assignee_updates AS (
    SELECT * FROM int_zendesk__assignee_updates
)
SELECT 
    ticket.*,
    requester.email AS requester_email,
    requester.name AS requester_name,
    requester.is_active AS is_requester_active,
    COALESCE(requester_updates.total_updates, 0) AS requester_ticket_update_count,
    submitter.email AS submitter_email,
    submitter.name AS submitter_name,
    submitter.is_active AS is_submitter_active,
    assignee.email AS assignee_email,
    assignee.name AS assignee_name,
    assignee.is_active AS is_assignee_active,
    COALESCE(assignee_updates.total_updates, 0) AS assignee_ticket_update_count
FROM ticket
JOIN users AS requester ON requester.user_id = ticket.requester_id
JOIN users AS submitter ON submitter.user_id = ticket.submitter_id
LEFT JOIN users AS assignee ON assignee.user_id = ticket.assignee_id
LEFT JOIN requester_updates ON requester_updates.ticket_id = ticket.ticket_id 
    AND requester_updates.requester_id = ticket.requester_id
LEFT JOIN assignee_updates ON assignee_updates.ticket_id = ticket.ticket_id 
    AND assignee_updates.assignee_id = ticket.assignee_id"""
        },
        {
            "title": "Stripe: Balance Transactions with Dispute Logic",
            "desc": "Multiple CTEs for disputes, charges, refunds (dbt_stripe)",
            "language": "bigquery",
            "toLanguage": "asql",
            "query": """WITH dispute_summary AS (
    SELECT charge_id, 
           STRING_AGG(dispute_id, ',') AS dispute_ids,
           STRING_AGG(DISTINCT dispute_reason, ',') AS dispute_reasons,
           COUNT(dispute_id) AS dispute_count
    FROM stg_stripe__dispute
    GROUP BY charge_id
),
order_disputes AS (
    SELECT charge_id, dispute_id, dispute_status, dispute_amount,
           ROW_NUMBER() OVER (PARTITION BY charge_id, dispute_status 
                              ORDER BY dispute_created_at DESC) = 1 AS is_latest_status_dispute
    FROM stg_stripe__dispute
)
SELECT
    bt.balance_transaction_id,
    bt.created_at AS balance_transaction_created_at,
    bt.amount AS balance_transaction_amount,
    bt.fee AS balance_transaction_fee,
    bt.net AS balance_transaction_net,
    bt.type AS balance_transaction_type,
    COALESCE(charge.amount, refund.amount) AS customer_facing_amount,
    charge.charge_id,
    dispute_summary.dispute_ids,
    dispute_summary.dispute_count
FROM stg_stripe__balance_transaction bt
LEFT JOIN stg_stripe__charge charge 
    ON charge.balance_transaction_id = bt.balance_transaction_id
LEFT JOIN stg_stripe__refund refund 
    ON refund.balance_transaction_id = bt.balance_transaction_id
LEFT JOIN dispute_summary 
    ON charge.charge_id = dispute_summary.charge_id"""
        },
        {
            "title": "Shopify: Customer Cohorts with Window Functions",
            "desc": "Complex window functions for cohort analysis (dbt_shopify)",
            "language": "bigquery",
            "toLanguage": "asql",
            "query": """WITH customer_calendar AS (
    SELECT 
        calendar.date_day AS date_month,
        customers.customer_id,
        customers.first_order_timestamp,
        DATE_TRUNC('month', first_order_timestamp) AS cohort_month
    FROM calendar
    INNER JOIN customers 
        ON DATE_TRUNC('month', first_order_timestamp) <= calendar.date_day
),
orders_joined AS (
    SELECT 
        customer_calendar.date_month,
        customer_calendar.customer_id,
        customer_calendar.cohort_month,
        COALESCE(COUNT(DISTINCT orders.order_id), 0) AS order_count_in_month,
        COALESCE(SUM(orders.order_adjusted_total), 0) AS total_price_in_month
    FROM customer_calendar
    LEFT JOIN orders
        ON customer_calendar.customer_id = orders.customer_id
        AND customer_calendar.date_month = DATE_TRUNC('month', orders.created_timestamp)
    GROUP BY customer_calendar.date_month, customer_calendar.customer_id, customer_calendar.cohort_month
),
windows AS (
    SELECT *,
        SUM(total_price_in_month) OVER (
            PARTITION BY customer_id 
            ORDER BY date_month 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS total_price_lifetime,
        SUM(order_count_in_month) OVER (
            PARTITION BY customer_id 
            ORDER BY date_month 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS order_count_lifetime,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id 
            ORDER BY date_month ASC
        ) AS cohort_month_number
    FROM orders_joined
)
SELECT * FROM windows"""
            }
        ])
    
    return jsonify(examples)

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
