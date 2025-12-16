"""ASQL Documentation Server - Serves docs with dialect tabs."""

import re
import json
import base64
import sys
import socket
import os
from pathlib import Path
from typing import Dict, List, Optional
from flask import Flask, render_template_string, send_from_directory, jsonify, request
from asql import compile
import markdown
import requests

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Top 4 dbt dialects (most commonly used)
TOP_DIALECTS = ["postgres", "snowflake", "bigquery", "databricks"]

# All available dialects
ALL_DIALECTS = [
    "postgres", "mysql", "sqlite", "oracle", "mssql", "bigquery", 
    "snowflake", "redshift", "presto", "trino", "spark", "hive",
    "clickhouse", "duckdb", "databricks"
]

# Dialect display names
DIALECT_NAMES = {
    "postgres": "PostgreSQL",
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",
    "redshift": "Redshift",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "oracle": "Oracle",
    "mssql": "SQL Server",
    "presto": "Presto",
    "trino": "Trino",
    "spark": "Spark",
    "hive": "Hive",
    "clickhouse": "ClickHouse",
    "duckdb": "DuckDB",
    "databricks": "Databricks",
}

def get_dialect_name(dialect: str) -> str:
    """Get display name for a dialect."""
    return DIALECT_NAMES.get(dialect, dialect.title())


def precompile_asql_query(asql_query: str) -> Dict[str, str]:
    """
    Pre-compile an ASQL query to all dialects.
    
    Returns a dict mapping dialect -> SQL string.
    """
    results = {"asql": asql_query}
    
    for dialect in ALL_DIALECTS:
        try:
            sql = compile(asql_query, dialect=dialect)
            results[dialect] = sql
        except Exception as e:
            # If compilation fails, store error message
            results[dialect] = f"-- Error compiling to {dialect}: {str(e)}"
    
    return results


def process_markdown_file(md_path: Path) -> str:
    """
    Process a markdown file, finding ASQL code blocks and replacing them
    with tabbed code blocks that include pre-compiled SQL for all dialects.
    """
    content = md_path.read_text(encoding='utf-8')
    
    # First, handle === tab syntax (Material for MkDocs style)
    # Process line by line to handle tab groups properly
    lines = content.split('\n')
    result_lines = []
    i = 0
    
    while i < len(lines):
        # Check if this line starts a tab group with ASQL
        if re.match(r'^=== "ASQL"', lines[i]):
            # Collect the entire tab group
            tab_group_lines = []
            
            # Collect until we hit a non-tab line (that's not empty and not part of a tab)
            while i < len(lines):
                line = lines[i]
                
                # Check if this is a tab header
                if re.match(r'^=== "', line):
                    tab_group_lines.append(line)
                    i += 1
                    # Collect the code block (indented lines)
                    while i < len(lines):
                        next_line = lines[i]
                        # Empty line or indented line belongs to this tab
                        if next_line.strip() == '' or next_line.startswith('    '):
                            tab_group_lines.append(next_line)
                            i += 1
                        else:
                            break
                elif line.strip() == '':
                    # Empty line - check if next line is another tab
                    if i + 1 < len(lines) and re.match(r'^=== "', lines[i + 1]):
                        tab_group_lines.append(line)
                        i += 1
                    else:
                        # End of tab group
                        break
                else:
                    # Not a tab, end of group
                    break
            
            # Process the tab group
            tab_group = '\n'.join(tab_group_lines)
            
            # Extract ASQL query
            # Pattern: === "ASQL"\n    ```asql\n    code\n    ```
            asql_match = re.search(r'=== "ASQL"\s*\n\s+```\s*asql\s*\n((?:\s+.*?\n)*?)\s+```', tab_group, re.DOTALL | re.IGNORECASE)
            if asql_match:
                asql_query = asql_match.group(1)
                # Remove leading 4-space indentation from each line
                asql_lines = []
                for line in asql_query.split('\n'):
                    # Remove 4-space indentation if present
                    if line.startswith('    '):
                        asql_lines.append(line[4:])
                    elif line.startswith('\t'):
                        asql_lines.append(line[1:])
                    elif line.strip() == '':
                        # Preserve empty lines
                        asql_lines.append('')
                    else:
                        asql_lines.append(line)
                asql_query = '\n'.join(asql_lines).strip()
                
                if asql_query:
                    # Pre-compile to all dialects
                    compiled = precompile_asql_query(asql_query)
                    
                    # Create a unique ID
                    import hashlib
                    block_id = hashlib.md5(asql_query.encode()).hexdigest()[:8]
                    
                    # Generate HTML
                    tabs_html = generate_tabs_html(compiled, block_id)
                    result_lines.append(tabs_html)
                    continue
            
            # If processing failed, keep original lines
            result_lines.extend(tab_group_lines)
        else:
            result_lines.append(lines[i])
            i += 1
    
    processed_content = '\n'.join(result_lines)
    
    # Pattern to match ASQL code blocks: ```asql ... ```
    # Handle both ```asql and ``` asql (with space)
    asql_pattern = r'```\s*asql\s*\n(.*?)```'
    
    def replace_asql_block(match):
        asql_query = match.group(1).strip()
        
        # Skip if empty
        if not asql_query:
            return match.group(0)
        
        # Pre-compile to all dialects
        compiled = precompile_asql_query(asql_query)
        
        # Create a unique ID for this code block
        import hashlib
        block_id = hashlib.md5(asql_query.encode()).hexdigest()[:8]
        
        # Generate HTML for tabs
        tabs_html = generate_tabs_html(compiled, block_id)
        
        return tabs_html
    
    # Replace all ASQL blocks
    processed_content = re.sub(asql_pattern, replace_asql_block, processed_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Also handle SQL blocks that might have ASQL examples above them
    # Pattern: **ASQL:**\n```asql ... ```\n\n**SQL (PostgreSQL):**\n```sql ... ```
    sql_pattern = r'\*\*ASQL:\*\*\s*```\s*asql\s*\n(.*?)```\s*\n\s*\*\*SQL\s*\(.*?\):\*\*\s*```sql\n.*?```'
    
    def replace_asql_sql_pair(match):
        asql_query = match.group(1).strip()
        if not asql_query:
            return match.group(0)
        compiled = precompile_asql_query(asql_query)
        import hashlib
        block_id = hashlib.md5(asql_query.encode()).hexdigest()[:8]
        tabs_html = generate_tabs_html(compiled, block_id)
        return tabs_html
    
    processed_content = re.sub(sql_pattern, replace_asql_sql_pair, processed_content, flags=re.DOTALL | re.IGNORECASE)
    
    return processed_content


def generate_tabs_html(compiled: Dict[str, str], block_id: str) -> str:
    """Generate HTML for dialect tabs."""
    
    # Get top dialects (excluding asql)
    top_dialects_list = [d for d in TOP_DIALECTS if d in compiled]
    
    # Get other dialects (not in top 4)
    other_dialects = [d for d in ALL_DIALECTS if d not in TOP_DIALECTS and d in compiled]
    
    # Encode compiled SQL for embedding in HTML
    compiled_json = json.dumps(compiled)
    compiled_b64 = base64.b64encode(compiled_json.encode()).decode()
    
    tabs_html = f'''
<div class="asql-code-block" data-block-id="{block_id}" data-compiled="{compiled_b64}">
    <div class="dialect-tabs">
        <button class="tab-btn active" data-dialect="asql" onclick="showDialect('{block_id}', 'asql')">ASQL</button>
'''
    
    # Add top dialect tabs
    for dialect in top_dialects_list:
        dialect_name = get_dialect_name(dialect)
        tabs_html += f'        <button class="tab-btn" data-dialect="{dialect}" onclick="showDialect(\'{block_id}\', \'{dialect}\')">{dialect_name}</button>\n'
    
    # Add "..." tab if there are other dialects
    if other_dialects:
        tabs_html += f'        <button class="tab-btn more-tab" onclick="showMoreDialects(\'{block_id}\')">⋯</button>\n'
    
    # Get initial code content (ASQL by default)
    initial_code = compiled.get('asql', '')
    # Escape HTML entities
    import html
    initial_code_escaped = html.escape(initial_code)
    
    # Initial code is always ASQL
    lang_class = 'language-asql'
    
    # Generate play button - will use JavaScript to get current dialect
    import urllib.parse
    asql_query_encoded = urllib.parse.quote(compiled.get('asql', ''))
    base_play_url = f"https://play.analyticsql.com?d_f=ASQL&sql_f={asql_query_encoded}"
    
    tabs_html += f'''    </div>
    <div class="code-content" style="position: relative;">
        <a href="#" onclick="openInPlayground('{block_id}'); return false;" class="play-button" title="Open in Playground" data-block-id="{block_id}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
            </svg>
        </a>
        <pre><code class="{lang_class}" id="code-{block_id}">{initial_code_escaped}</code></pre>
    </div>
</div>
'''
    
    return tabs_html


# HTML template for documentation pages
DOC_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Analytic SQL</title>
    <link rel="stylesheet" href="/static/docs.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/sql.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/bash.min.js"></script>
    <script src="/static/asql-lang.js"></script>
</head>
<body>
    <div class="doc-container">
        <nav class="doc-nav">
            <h1><a href="/">Analytic SQL</a></h1>
            <ul>
                <li><a href="/docs/">Language Specification</a></li>
                <li><a href="/docs/QUICK_START">Syntax</a></li>
                <li><a href="/docs/EXAMPLES">Examples</a></li>
                <li><a href="/docs/INTEGRATING">Integrating</a></li>
                <li><a href="/docs/architecture">Architecture</a></li>
                <li><a href="https://play.analyticsql.com" target="_blank">Playground →</a></li>
            </ul>
        </nav>
        <main class="doc-content">
            {{ content | safe }}
        </main>
    </div>
    <script src="/static/docs.js"></script>
</body>
</html>
"""


@app.route('/')
def index():
    """Redirect to docs spec."""
    return render_doc('spec.md', 'Analytic SQL Language Specification')


@app.route('/docs/')
@app.route('/docs/<path:doc_path>')
def serve_doc(doc_path: str = 'spec.md'):
    """Serve a documentation page."""
    # Map URL paths to actual file names
    path_to_file = {
        '': 'spec.md',
        'index': 'spec.md',
        'spec': 'spec.md',
        'quick-start': 'quick_start.md',
        'QUICK_START': 'quick_start.md',
        'examples': 'examples.md',
        'EXAMPLES': 'examples.md',
        'integrating': 'integrating.md',
        'INTEGRATING': 'integrating.md',
        'architecture': 'architecture.md',
        'interactive-playground': 'interactive_playground.md',
        'INTERACTIVE_PLAYGROUND': 'interactive_playground.md',
    }
    
    # Normalize the path
    if doc_path.endswith('/'):
        doc_path = doc_path[:-1]
    
    # Map to actual file name if needed
    if doc_path in path_to_file:
        doc_path = path_to_file[doc_path]
    elif not doc_path.endswith('.md'):
        doc_path += '.md'
    
    docs_dir = Path(__file__).parent / 'docs'
    md_path = docs_dir / doc_path
    
    if not md_path.exists():
        return f"Documentation file not found: {doc_path}", 404
    
    # Map common paths to better titles
    title_map = {
        'index': 'Analytic SQL',
        'quick-start': 'Syntax Reference',
        'examples': 'Examples',
        'spec': 'Language Specification',
        'integrating': 'Integrating',
        'architecture': 'Architecture',
        'interactive-playground': 'Interactive Playground',
    }
    base_name = doc_path.replace('.md', '')
    title = title_map.get(base_name, base_name.replace('-', ' ').title())
    return render_doc(doc_path, title)


def render_doc(doc_path: str, title: str) -> str:
    """Render a markdown document with tabs."""
    docs_dir = Path(__file__).parent / 'docs'
    md_path = docs_dir / doc_path
    
    # Process markdown to add tabs
    processed_md = process_markdown_file(md_path)
    
    # Convert markdown to HTML (simple conversion for now)
    # In production, you'd use a proper markdown library
    html_content = markdown_to_html(processed_md)
    
    return render_template_string(DOC_TEMPLATE, title=title, content=html_content)


def markdown_to_html(md: str) -> str:
    """Convert markdown to HTML."""
    try:
        # Use markdown library with extensions
        # Note: We've already processed ASQL blocks to HTML, so we need to preserve them
        # Split by our HTML blocks, process markdown separately, then rejoin
        html_parts = []
        
        # Find all asql-code-block divs and their content (handling nested divs)
        # We'll match from opening tag to matching closing tag by counting divs
        i = 0
        while i < len(md):
            # Look for start of asql-code-block
            block_start = md.find('<div class="asql-code-block"', i)
            if block_start == -1:
                # No more blocks, process remaining markdown
                remaining = md[i:]
                if remaining.strip():
                    try:
                        html_parts.append(markdown.markdown(
                            remaining, 
                            extensions=['fenced_code', 'codehilite', 'tables', 'toc']
                        ))
                    except:
                        html_parts.append(remaining)
                break
            
            # Process markdown before this block
            if block_start > i:
                before_block = md[i:block_start]
                if before_block.strip():
                    try:
                        html_parts.append(markdown.markdown(
                            before_block, 
                            extensions=['fenced_code', 'codehilite', 'tables', 'toc']
                        ))
                    except:
                        html_parts.append(before_block)
            
            # Find the matching closing tag (count div opens/closes)
            div_count = 0
            j = block_start
            block_end = -1
            while j < len(md):
                if md[j:j+5] == '<div ':
                    div_count += 1
                    j = md.find('>', j) + 1
                elif md[j:j+6] == '</div>':
                    div_count -= 1
                    if div_count == 0:
                        block_end = j + 6
                        break
                    j += 6
                else:
                    j += 1
            
            if block_end == -1:
                # Couldn't find matching closing tag, process as markdown
                remaining = md[block_start:]
                if remaining.strip():
                    try:
                        html_parts.append(markdown.markdown(
                            remaining, 
                            extensions=['fenced_code', 'codehilite', 'tables', 'toc']
                        ))
                    except:
                        html_parts.append(remaining)
                break
            
            # Extract the HTML block and keep it as-is
            html_block = md[block_start:block_end]
            html_parts.append(html_block)
            i = block_end
        
        return ''.join(html_parts)
    except Exception as e:
        # Fallback: basic conversion
        html = md
        # Headers
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # Code blocks (already processed)
        # Paragraphs
        paragraphs = html.split('\n\n')
        result = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('<'):
                result.append(f'<p>{p}</p>')
            else:
                result.append(p)
        return '\n'.join(result)


def serve_embedded_playground():
    """Serve the playground HTML for embedding (full page, no docs wrapper)."""
    playground_path = Path(__file__).parent / 'playground.py'
    playground_content = playground_path.read_text(encoding='utf-8')
    
    # Extract the PLAYGROUND_HTML constant
    import re
    match = re.search(r'PLAYGROUND_HTML = """(.*?)"""', playground_content, re.DOTALL)
    if match:
        playground_html = match.group(1)
        # Update API URLs to go through this server (handle both single and double quotes)
        # Replace '/api/' and "/api/" patterns in fetch calls
        playground_html = playground_html.replace(
            "fetch('/api/",
            "fetch('/playground/api/"
        )
        playground_html = playground_html.replace(
            'fetch("/api/',
            'fetch("/playground/api/'
        )
        # Update static file paths - need to handle both src= and src=' patterns
        playground_html = playground_html.replace(
            'src="/static/syntax/',
            'src="/playground/static/syntax/'
        )
        playground_html = playground_html.replace(
            "src='/static/syntax/",
            "src='/playground/static/syntax/"
        )
        # Add embedded mode detection and hide the header
        playground_html = playground_html.replace(
            '<body>',
            '<body><script>window.ASQL_EMBEDDED = true;</script>'
        )
        # Hide the header with "Back to Docs" link and title
        playground_html = playground_html.replace(
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">',
            '<div style="display: none;">'
        )
        # Make container full width - update CSS (handle different whitespace)
        import re as re_module
        # Update container CSS to ensure full width
        playground_html = re_module.sub(
            r'\.container\s*\{[^}]*\}',
            '.container {\n            max-width: 100% !important;\n            width: 100% !important;\n            margin: 0 !important;\n            padding: 20px !important;\n        }',
            playground_html
        )
        # Also update the container div itself with inline style
        playground_html = playground_html.replace(
            '<div class="container">',
            '<div class="container" style="max-width: 100% !important; width: 100% !important; padding: 20px;">'
        )
        # Remove body padding/margin for full width
        playground_html = re_module.sub(
            r'body\s*\{[^}]*background:',
            'body {\n            margin: 0 !important;\n            padding: 0 !important;\n            background:',
            playground_html
        )
        return playground_html
    else:
        # Fallback: redirect to standalone playground
        return '<script>window.location.href = "http://localhost:5001";</script>', 302


@app.route('/playground')
@app.route('/playground/<path:path>', methods=['GET', 'POST'])
def playground(path=''):
    """Serve the playground page or proxy API requests."""
    # If no path, serve the playground embedded in docs layout (with sidebar)
    if not path or path == '':
        # Create a full-width iframe that takes up the entire browser width
        playground_content = '''<div style="position: fixed; top: 0; left: 250px; right: 0; bottom: 0; margin: 0; padding: 0; width: calc(100% - 250px); height: 100vh; z-index: 1;">
    <iframe src="/playground/embed" style="width: 100%; height: 100%; border: none;" frameborder="0" title="ASQL Playground"></iframe>
</div>
<style>
.doc-content {
    position: relative !important;
    padding: 0 !important;
    margin: 0 !important;
    margin-left: 250px !important;
    height: 100vh !important;
    overflow: hidden !important;
    max-width: none !important;
    width: calc(100% - 250px) !important;
}
</style>'''
        return render_template_string(DOC_TEMPLATE, title='Playground', content=playground_content)
    
    # Handle API requests (for the embedded playground)
    if path.startswith('api/'):
        # Proxy API requests to the playground server
        try:
            api_path = path.replace('api/', '')
            if request.method == 'POST':
                resp = requests.post(
                    f'http://localhost:5001/api/{api_path}',
                    json=request.get_json(),
                    headers={'Content-Type': 'application/json'}
                )
            else:
                resp = requests.get(f'http://localhost:5001/api/{api_path}')
            
            # Create response with proper headers
            from flask import Response
            response = Response(
                resp.content,
                status=resp.status_code,
                mimetype='application/json'
            )
            return response
        except requests.exceptions.ConnectionError:
            return jsonify({'error': 'Playground server not available. Please start playground.py on port 5001'}), 503
        except Exception as e:
            return jsonify({'error': f'Playground server error: {str(e)}'}), 503
    
    # Serve static files for playground (syntax highlighter, etc.)
    # Path format: static/syntax/codemirror/asql-mode.js
    if path.startswith('static/syntax/'):
        # Extract filename relative to syntax directory
        # path = "static/syntax/codemirror/asql-mode.js"
        # filename = "codemirror/asql-mode.js"
        filename = path.replace('static/syntax/', '')
        syntax_dir = Path(__file__).parent / 'syntax'
        file_path = syntax_dir / filename
        
        if file_path.exists() and file_path.is_file():
            # send_from_directory needs: (directory, relative_path_from_directory)
            return send_from_directory(str(syntax_dir), filename)
        
        return jsonify({'error': f'File not found: {path}'}), 404
    
    # If path is 'embed', serve the standalone playground HTML for embedding
    if path == 'embed':
        return serve_embedded_playground()
    
    # For any other path, return 404
    return jsonify({'error': f'Path not found: {path}'}), 404

@app.route('/api/dialect/view', methods=['POST'])
def track_dialect_view():
    """Track when a user views a dialect."""
    data = request.get_json()
    dialect = data.get('dialect')
    
    if dialect:
        # This will be handled by client-side localStorage
        return jsonify({'status': 'ok'})
    
    return jsonify({'error': 'Missing dialect'}), 400


if __name__ == '__main__':
    # Create static directory if it doesn't exist
    static_dir = Path(__file__).parent / 'static'
    static_dir.mkdir(exist_ok=True)
    
    # Get port from environment variable or use default
    # Using 73137 (approximate SELECT on phone keypad: 7=S, 3=E, 1=L, 3=E, 7=T) - if it conflicts, we'll find an alternative
    port = int(os.environ.get('DOCS_PORT', 73137))
    
    # Try to find an available port if default is in use
    def find_free_port(start_port):
        """Find a free port starting from start_port."""
        for port in range(start_port, start_port + 10):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('', port))
                    return port
                except OSError:
                    continue
        return None
    
    # Check if default port is available
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('', port))
            # Port is available, close the socket
            s.close()
        except OSError:
            # Port is in use, find alternative
            print(f"Port {port} is already in use. Looking for alternative port...")
            alt_port = find_free_port(73138)
            if alt_port:
                port = alt_port
                print(f"Using port {port} instead.")
            else:
                print(f"Error: Could not find an available port. Please free up port {port} or set DOCS_PORT environment variable.")
                sys.exit(1)
    
    print("Starting ASQL Documentation Server...")
    print(f"Open http://localhost:{port} in your browser")
    app.run(debug=True, host='0.0.0.0', port=port)
