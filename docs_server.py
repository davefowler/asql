"""ASQL Documentation Server - Serves docs with dialect tabs."""

import re
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional
from flask import Flask, render_template_string, send_from_directory, jsonify, request
from asql import compile
import markdown

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Top 4 dbt dialects (most commonly used)
TOP_DIALECTS = ["postgres", "snowflake", "bigquery", "redshift"]

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
    processed_content = re.sub(asql_pattern, replace_asql_block, content, flags=re.DOTALL | re.IGNORECASE)
    
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
    
    tabs_html += '''    </div>
    <div class="code-content">
        <pre><code class="language-sql" id="code-''' + block_id + '''"></code></pre>
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
    <title>{{ title }} - ASQL Documentation</title>
    <link rel="stylesheet" href="/static/docs.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/default.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/sql.min.js"></script>
</head>
<body>
    <div class="doc-container">
        <nav class="doc-nav">
            <h1><a href="/">ASQL</a></h1>
            <ul>
                <li><a href="/docs/">Index</a></li>
                <li><a href="/docs/quick-start">Quick Start</a></li>
                <li><a href="/docs/examples">Examples</a></li>
                <li><a href="/docs/getting-started">Getting Started</a></li>
                <li><a href="http://localhost:5001" target="_blank">Playground</a></li>
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
    """Redirect to docs index."""
    return render_doc('INDEX.md', 'ASQL Documentation')


@app.route('/docs/')
@app.route('/docs/<path:doc_path>')
def serve_doc(doc_path: str = 'INDEX.md'):
    """Serve a documentation page."""
    if not doc_path.endswith('.md'):
        doc_path += '.md'
    
    docs_dir = Path(__file__).parent / 'docs'
    md_path = docs_dir / doc_path
    
    if not md_path.exists():
        return f"Documentation file not found: {doc_path}", 404
    
    title = doc_path.replace('.md', '').replace('-', ' ').title()
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
        parts = re.split(r'(<div class="asql-code-block".*?</div>)', md, flags=re.DOTALL)
        
        for part in parts:
            if part.strip().startswith('<div class="asql-code-block"'):
                # This is our pre-processed HTML block, keep it as-is
                html_parts.append(part)
            else:
                # Process as markdown
                try:
                    html_part = markdown.markdown(
                        part, 
                        extensions=['fenced_code', 'codehilite', 'tables', 'toc']
                    )
                    html_parts.append(html_part)
                except:
                    html_parts.append(part)
        
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
    
    print("Starting ASQL Documentation Server...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
