"""ASQL Documentation Macros - Provides dialect tabs for ASQL code blocks.

This module is loaded by mkdocs-macros-plugin and provides:
1. A hook to process markdown and add dialect tabs to ASQL code blocks
2. Pre-compilation of ASQL to all supported SQL dialects
"""

import re
import json
import base64
import html
import hashlib
import warnings
import logging
from typing import Dict

# Suppress SQLGlot warnings during compilation (they're noisy for unsupported features)
logging.getLogger('sqlglot').setLevel(logging.ERROR)


# Top 4 dialects (most commonly used, shown as tabs)
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
    import sys
    import io
    from asql import compile
    
    results = {"asql": asql_query}
    
    for dialect in ALL_DIALECTS:
        try:
            # Suppress all output during compilation (SQLGlot prints warnings to stdout/stderr)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                old_stdout, old_stderr = sys.stdout, sys.stderr
                sys.stdout = sys.stderr = io.StringIO()
                try:
                    sql = compile(asql_query, dialect=dialect)
                finally:
                    sys.stdout, sys.stderr = old_stdout, old_stderr
            results[dialect] = sql
        except Exception as e:
            # If compilation fails, store error message
            results[dialect] = f"-- Error compiling to {dialect}: {str(e)}"
    
    return results


def generate_tabs_html(compiled: Dict[str, str], block_id: str) -> str:
    """Generate HTML for dialect tabs."""
    
    # Get top dialects (excluding asql)
    top_dialects_list = [d for d in TOP_DIALECTS if d in compiled]
    
    # Get other dialects (not in top 4)
    other_dialects = [d for d in ALL_DIALECTS if d not in TOP_DIALECTS and d in compiled]
    
    # Encode compiled SQL for embedding in HTML
    compiled_json = json.dumps(compiled)
    compiled_b64 = base64.b64encode(compiled_json.encode()).decode()
    
    # Get initial code content (ASQL by default)
    initial_code = compiled.get('asql', '')
    initial_code_escaped = html.escape(initial_code)
    
    tabs_html = f'''<div class="asql-code-block" data-block-id="{block_id}" data-compiled="{compiled_b64}">
<div class="dialect-tabs">
<button class="tab-btn active" data-dialect="asql" onclick="showDialect('{block_id}', 'asql')">ASQL</button>
'''
    
    # Add top dialect tabs
    for dialect in top_dialects_list:
        dialect_name = get_dialect_name(dialect)
        tabs_html += f'<button class="tab-btn" data-dialect="{dialect}" onclick="showDialect(\'{block_id}\', \'{dialect}\')">{dialect_name}</button>\n'
    
    # Add "..." tab if there are other dialects
    if other_dialects:
        tabs_html += f'<button class="tab-btn more-tab" onclick="showMoreDialects(\'{block_id}\')">⋯</button>\n'
    
    tabs_html += f'''</div>
<div class="code-content">
<a href="#" onclick="openInPlayground('{block_id}'); return false;" class="play-button" title="Open in Playground">
<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
</a>
<pre><code class="language-asql" id="code-{block_id}">{initial_code_escaped}</code></pre>
</div>
</div>
'''
    
    return tabs_html


def process_asql_blocks(markdown_content: str) -> str:
    """
    Process markdown content, finding ASQL code blocks and replacing them
    with tabbed code blocks that include pre-compiled SQL for all dialects.
    """
    # Pattern to match ASQL code blocks: ```asql ... ```
    # We need to match standalone ```asql blocks (not in === tabs)
    asql_pattern = r'```asql\s*\n(.*?)```'
    
    def replace_asql_block(match):
        asql_query = match.group(1).strip()
        
        # Skip if empty
        if not asql_query:
            return match.group(0)
        
        # Pre-compile to all dialects
        compiled = precompile_asql_query(asql_query)
        
        # Create a unique ID for this code block
        block_id = hashlib.md5(asql_query.encode()).hexdigest()[:8]
        
        # Generate HTML for tabs
        tabs_html = generate_tabs_html(compiled, block_id)
        
        return tabs_html
    
    # Replace all ASQL blocks
    processed_content = re.sub(asql_pattern, replace_asql_block, markdown_content, flags=re.DOTALL)
    
    return processed_content


# MkDocs macros plugin hooks

def define_env(env):
    """
    Define the mkdocs-macros environment.
    This is called by mkdocs-macros-plugin on startup.
    """
    
    @env.macro
    def asql(query: str) -> str:
        """
        Macro to render an ASQL query with dialect tabs.
        
        Usage in markdown:
            {{ asql("SELECT * FROM users |> WHERE active") }}
        """
        compiled = precompile_asql_query(query.strip())
        block_id = hashlib.md5(query.encode()).hexdigest()[:8]
        return generate_tabs_html(compiled, block_id)
    
    @env.macro
    def dialect_name(dialect: str) -> str:
        """Get display name for a dialect."""
        return get_dialect_name(dialect)


def on_pre_page_macros(env) -> None:
    """
    Hook called by mkdocs-macros-plugin before macro rendering.
    This automatically converts ```asql blocks to dialect tabs.
    """
    # Access the markdown content and process it
    if hasattr(env, 'markdown') and env.markdown:
        env.markdown = process_asql_blocks(env.markdown)
