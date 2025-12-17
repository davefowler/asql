"""ASQL Documentation Macros - Provides a mini-playground for ASQL code blocks.

This module is loaded by mkdocs-macros-plugin and provides:
1. A hook to process markdown and add a mini-playground to ASQL code blocks
2. Pre-compilation of ASQL to all supported SQL dialects
"""

import re
import os
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
    "postgres", "mysql", "sqlite", "oracle", "tsql", "bigquery",
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
    "tsql": "SQL Server",
    "presto": "Presto",
    "trino": "Trino",
    "spark": "Spark",
    "hive": "Hive",
    "clickhouse": "ClickHouse",
    "duckdb": "DuckDB",
    "databricks": "Databricks",
}

DEFAULT_DOCS_URL = "https://analyticsql.com"
DEFAULT_PLAYGROUND_URL = "https://play.analyticsql.com"


def _normalize_base_url(url: str) -> str:
    """Normalize a base URL (no trailing slash)."""
    return url.strip().rstrip("/")


def _runtime_config_script_tag() -> str:
    """Inject runtime config for docs JavaScript (per-page)."""
    docs_url = _normalize_base_url(os.environ.get("DOCS_URL", DEFAULT_DOCS_URL))
    playground_url = _normalize_base_url(os.environ.get("PLAYGROUND_URL", DEFAULT_PLAYGROUND_URL))
    return (
        "<script>"
        f"window.__ASQL_DOCS_URL__ = {json.dumps(docs_url)};"
        f"window.__ASQL_PLAYGROUND_URL__ = {json.dumps(playground_url)};"
        "</script>\n"
    )


def get_dialect_name(dialect: str) -> str:
    """Get display name for a dialect."""
    return DIALECT_NAMES.get(dialect, dialect.title())


def _split_top_level_commas(text: str) -> list[str]:
    """
    Split a string on commas that are not nested in parentheses.
    This is a small heuristic formatter for docs readability (not a parser).
    """
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)

        if ch == "," and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue

        buf.append(ch)

    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)

    return parts


def _format_paren_list_block(prefix: str, inner: str, indent: str) -> str:
    items = _split_top_level_commas(inner)
    if len(items) <= 1:
        return f"{prefix}({inner.strip()})"

    formatted_lines: list[str] = []
    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        suffix = "" if is_last else ","
        formatted_lines.append(f"{indent}{item}{suffix}")
    formatted_items = "\n".join(formatted_lines)
    return f"{prefix}(\n{formatted_items}\n)"


def format_asql_for_docs(asql_query: str) -> str:
    """
    Format ASQL for docs display (prefer short vertical lines).

    Heuristics:
    - `select (...)` → one item per line inside parens
    - `group by <keys> (...)` → keep keys, one item per line inside parens
    - leaves unknown patterns untouched
    """
    lines = asql_query.strip().splitlines()
    out: list[str] = []

    for line in lines:
        raw = line.rstrip()
        if not raw.strip():
            out.append(raw)
            continue

        leading_ws = re.match(r"^\s*", raw).group(0)
        body = raw.strip()

        # select (a, b, c)
        if body.lower().startswith("select"):
            m = re.match(r"^select\s*\((.*)\)\s*$", body, flags=re.IGNORECASE)
            if m:
                inner = m.group(1)
                out.append(leading_ws + _format_paren_list_block("select ", inner, leading_ws + "  "))
                continue

        # group by <keys> (a, b, c)
        if body.lower().startswith("group by"):
            # Require a whitespace boundary before the aggregation parens so we don't
            # accidentally treat function-call parens in the grouping keys (e.g. month(created_at))
            # as the start of the aggregation list.
            m = re.match(r"^group\s+by\s+(.+?)\s+\((.*)\)\s*$", body, flags=re.IGNORECASE)
            if m:
                keys = m.group(1).strip()
                inner = m.group(2)
                prefix = f"group by {keys} "
                out.append(leading_ws + _format_paren_list_block(prefix, inner, leading_ws + "  "))
                continue

        out.append(raw)

    # Trim trailing blank lines introduced by formatting
    return "\n".join(out).rstrip() + "\n"


def precompile_asql_query(asql_query: str) -> Dict[str, str]:
    """
    Pre-compile an ASQL query to all dialects.
    
    Returns a dict mapping dialect -> SQL string.
    """
    import sys
    import io
    from asql import compile
    
    formatted_asql = format_asql_for_docs(asql_query)
    results = {"asql": formatted_asql}
    
    compilation_errors: list[str] = []

    for dialect in ALL_DIALECTS:
        try:
            # Suppress all output during compilation (SQLGlot prints warnings to stdout/stderr)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                old_stdout, old_stderr = sys.stdout, sys.stderr
                sys.stdout = sys.stderr = io.StringIO()
                try:
                    sql = compile(formatted_asql, dialect=dialect)
                finally:
                    sys.stdout, sys.stderr = old_stdout, old_stderr
            # Pretty-print for docs readability (adds newlines/indentation)
            try:
                import sqlglot

                parsed = sqlglot.parse_one(sql, dialect=dialect)
                results[dialect] = parsed.sql(dialect=dialect, pretty=True)
            except Exception:
                # If pretty formatting fails for any reason, fall back to raw SQL
                results[dialect] = sql
        except Exception as e:
            compilation_errors.append(f"{dialect}: {e}")
    
    if compilation_errors:
        # Fail fast: docs build should fail if any compiled example doesn't compile.
        msg = (
            "ASQL docs example failed to compile for one or more dialects.\n"
            f"Errors: {', '.join(compilation_errors)}\n"
            "ASQL:\n"
            f"{formatted_asql}"
        )
        raise RuntimeError(msg)

    return results


def generate_mini_playground_html(compiled: Dict[str, str], block_id: str) -> str:
    """Generate HTML for the ASQL mini-playground (split pane + global 'to' dialect)."""

    # Encode compiled SQL for embedding in HTML
    compiled_json = json.dumps(compiled)
    compiled_b64 = base64.b64encode(compiled_json.encode()).decode()

    # Initial content (JS will update the "to" pane based on localStorage)
    initial_asql = html.escape(compiled.get("asql", ""))
    default_to_dialect = "postgres"
    initial_to_sql = html.escape(compiled.get(default_to_dialect, ""))

    # Build dropdown options for all available dialects (excluding ASQL)
    options_html = ""
    for dialect in ALL_DIALECTS:
        if dialect not in compiled:
            continue
        dialect_name = get_dialect_name(dialect)
        selected_attr = ' selected="selected"' if dialect == default_to_dialect else ""
        options_html += f'<option value="{dialect}"{selected_attr}>{dialect_name}</option>\n'

    playground_html = f'''<div class="asql-code-block asql-mini-playground" data-block-id="{block_id}" data-compiled="{compiled_b64}">
<div class="asql-mp-grid">
  <div class="asql-mp-pane asql-mp-pane-left">
    <div class="asql-mp-pane-header">
      <span class="asql-mp-pane-title">ASQL</span>
      <a href="#" onclick="openInPlayground('{block_id}'); return false;" class="asql-mp-play-button" title="Open in Playground" aria-label="Open in Playground">
        <span class="asql-mp-play-label">Playground</span>
        <span class="asql-mp-play-icon" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
        </span>
      </a>
    </div>
    <pre><code class="language-asql" id="asql-{block_id}">{initial_asql}</code></pre>
  </div>
  <div class="asql-mp-pane asql-mp-pane-right">
    <div class="asql-mp-pane-header">
      <div class="asql-mp-to-wrap" aria-label="Choose SQL dialect">
        <select class="asql-mp-to-select" data-block-id="{block_id}">
          {options_html}
        </select>
      </div>
    </div>
    <pre><code class="language-sql" id="to-{block_id}">{initial_to_sql}</code></pre>
  </div>
</div>
</div>
'''

    return playground_html


def process_asql_blocks(markdown_content: str) -> str:
    """
    Process markdown content, finding ASQL code blocks and replacing them
    with tabbed code blocks that include pre-compiled SQL for all dialects.
    """
    # Pattern to match ASQL code blocks: ```asql ... ```
    # We need to match standalone ```asql blocks (not in === tabs)
    asql_pattern = r'```asql\s*\n(.*?)```'
    
    def should_compile_asql_block(asql_query: str) -> bool:
        """
        Only compile full ASQL queries into the mini-playground.

        Many docs pages include small ASQL *snippets* (e.g. `sum amount`, `# users`)
        that are intended as syntax examples, not standalone queries. We leave those
        as normal fenced code blocks (still syntax-highlighted), and only compile
        blocks that look like real queries.
        """
        non_comment_lines: list[str] = []
        for line in asql_query.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("--"):
                continue
            non_comment_lines.append(stripped)

        if not non_comment_lines:
            return False

        # Only compile blocks that appear to contain a *single* query.
        # If there are multiple independent examples in one fenced block (e.g. multiple `from ...`),
        # leave it as a normal code block.
        query_starters = 0
        for line in non_comment_lines:
            lowered = line.lower()
            if lowered.startswith("from ") or lowered.startswith("with "):
                query_starters += 1
        if query_starters != 1:
            return False

        # Multi-line SELECT blocks ("select" on its own line + indented columns)
        # are not reliably supported by the current compiler. Leave them as plain
        # fenced code blocks for now.
        select_lines = 0
        for line in non_comment_lines:
            lowered = line.lower()
            if lowered == "select":
                return False
            if lowered.startswith("select "):
                select_lines += 1
        # Multiple SELECT statements inside one fenced block are usually documentation snippets.
        if select_lines > 1:
            return False

        # Spec/WIP conditional syntax isn't implemented yet.
        for line in non_comment_lines:
            if line.lower().startswith("if "):
                return False

        # Spec-only pseudo syntax (pipeline/object literal examples) should not be compiled.
        for line in non_comment_lines:
            if line.startswith("|"):
                return False
            if "{" in line or "}" in line:
                return False
            lowered = line.lower()
            # Raw SQL window syntax snippets (OVER ...) are documentation-only.
            if " over " in lowered or "over(" in lowered:
                return False
            # Ellipsis placeholders are documentation-only.
            if "..." in line:
                return False

        first = non_comment_lines[0].lower()
        return first.startswith("from ") or first.startswith("with ")

    def replace_asql_block(match):
        asql_query = match.group(1).strip()
        
        # Skip if empty
        if not asql_query:
            return match.group(0)

        # Skip snippet blocks (leave as fenced code, no compilation)
        if not should_compile_asql_block(asql_query):
            return match.group(0)
        
        # Pre-compile to all dialects
        compiled = precompile_asql_query(asql_query)
        
        # Create a unique ID for this code block
        block_id = hashlib.md5(asql_query.encode()).hexdigest()[:8]
        
        # Generate HTML for mini playground
        tabs_html = generate_mini_playground_html(compiled, block_id)
        
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
        return generate_mini_playground_html(compiled, block_id)
    
    @env.macro
    def dialect_name(dialect: str) -> str:
        """Get display name for a dialect."""
        return get_dialect_name(dialect)

    @env.macro
    def playground_url() -> str:
        """Get the configured playground base URL."""
        return _normalize_base_url(os.environ.get("PLAYGROUND_URL", DEFAULT_PLAYGROUND_URL))

    @env.macro
    def docs_url() -> str:
        """Get the configured docs base URL."""
        return _normalize_base_url(os.environ.get("DOCS_URL", DEFAULT_DOCS_URL))


def on_pre_page_macros(env) -> None:
    """
    Hook called by mkdocs-macros-plugin before macro rendering.
    This automatically converts ```asql blocks to dialect tabs.
    """
    # Access the markdown content and process it
    if hasattr(env, 'markdown') and env.markdown:
        playground_url = _normalize_base_url(os.environ.get("PLAYGROUND_URL", DEFAULT_PLAYGROUND_URL))

        # Make markdown links environment-aware (so mkdocs serve can point at localhost).
        env.markdown = env.markdown.replace(DEFAULT_PLAYGROUND_URL, playground_url)

        # Provide runtime config for docs/static/docs.js
        env.markdown = _runtime_config_script_tag() + env.markdown

        try:
            env.markdown = process_asql_blocks(env.markdown)
        except Exception as e:
            page = getattr(env, "page", None)
            page_file = getattr(page, "file", None) if page is not None else None
            src_path = getattr(page_file, "src_path", None) if page_file is not None else None
            page_hint = f" (page: {src_path})" if src_path else ""
            raise RuntimeError(f"{e}{page_hint}") from e
