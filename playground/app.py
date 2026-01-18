"""ASQL Interactive Playground - FastAPI application."""

import os
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sqlglot.dialects import Dialects

import sqlglot

from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError
from asql.config import CompileSettings
from asql.json_schema import json_to_asql
import json

from .jinja_utils import strip_jinja_templates
from .examples import (
    ASQL_EXAMPLES,
    PIPELINE_EXAMPLES,
    COHORT_EXAMPLES,
    SAMPLING_EXAMPLES,
    RESHAPING_EXAMPLES,
    COLUMN_OPERATOR_EXAMPLES,
    COUNT_INFERENCE_EXAMPLES,
    SYNTAX_STYLES_EXAMPLES,
    SQL_EXAMPLES,
)


def get_dialect_options(panel: str = "from") -> list[dict]:
    """
    Get list of available dialects from SQLGlot with metadata.

    Args:
        panel: "from" for input panel, "to" for output panel

    Returns list of dicts with: value, label, editor (text/visual).
    """
    # Special entries that aren't SQLGlot dialects
    dialects = [
        {"value": "asql", "label": "ASQL", "editor": "text"},
        {"value": "visual-asql", "label": "Visual ASQL", "editor": "visual"},
    ]

    # Get SQLGlot dialects
    sqlglot_dialects = []
    for d in Dialects:
        if d.value:  # Skip empty DIALECT entry
            # Create nice display name
            label = d.value.replace("_", " ").title()
            # Special cases for better display
            label_map = {
                "bigquery": "BigQuery",
                "clickhouse": "ClickHouse",
                "databricks": "Databricks",
                "duckdb": "DuckDB",
                "mysql": "MySQL",
                "postgres": "PostgreSQL",
                "prql": "PRQL",
                "redshift": "Redshift",
                "snowflake": "Snowflake",
                "spark": "Spark",
                "spark2": "Spark 2",
                "sqlite": "SQLite",
                "tsql": "T-SQL (SQL Server)",
                "athena": "AWS Athena",
                "trino": "Trino",
                "presto": "Presto",
                "hive": "Hive",
                "oracle": "Oracle",
                "teradata": "Teradata",
                "starrocks": "StarRocks",
                "risingwave": "RisingWave",
                "materialize": "Materialize",
                "doris": "Apache Doris",
                "druid": "Apache Druid",
                "dremio": "Dremio",
                "drill": "Apache Drill",
                "dune": "Dune Analytics",
                "fabric": "Microsoft Fabric",
                "tableau": "Tableau",
                "solr": "Apache Solr",
                "exasol": "Exasol",
            }
            label = label_map.get(d.value, label)
            sqlglot_dialects.append({"value": d.value, "label": label, "editor": "text"})

    # Sort SQLGlot dialects alphabetically by label
    sqlglot_dialects.sort(key=lambda x: x["label"].lower())

    # Add SQL option - "Auto-detect" for input, "ANSI" for output
    if panel == "from":
        dialects.append({"value": "", "label": "SQL (Auto-detect)", "editor": "text"})
    else:
        dialects.append({"value": "", "label": "SQL (ANSI)", "editor": "text"})

    dialects.extend(sqlglot_dialects)

    return dialects


def generate_dialect_options_html(dialects: list[dict], selected: str = "") -> str:
    """Generate HTML <option> elements for dialect select."""
    options = []
    for d in dialects:
        selected_attr = " selected" if d["value"] == selected else ""
        # Store editor type as data attribute
        options.append(
            f'<option value="{d["value"]}" data-editor="{d["editor"]}"{selected_attr}>'
            f'{d["label"]}</option>'
        )
    return "\n                            ".join(options)


app = FastAPI(title="ASQL Playground", version="1.0.0")

# Mount static files
SYNTAX_DIR = Path(__file__).parent.parent / "syntax"
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Mount static files
if STATIC_DIR.exists():
    app.mount(
        "/static/playground", StaticFiles(directory=str(STATIC_DIR)), name="playground_static"
    )

if SYNTAX_DIR.exists():
    app.mount("/static/syntax", StaticFiles(directory=str(SYNTAX_DIR)), name="syntax")


# --- Pydantic Models ---


class CompileRequest(BaseModel):
    asql: str
    dialect: str = ""
    settings: dict = {}  # CompileSettings overrides


class ReverseCompileRequest(BaseModel):
    sql: str
    source_dialect: str = ""
    settings: dict = {}  # StyleConfig overrides


class DetectDialectRequest(BaseModel):
    sql: str


class NormalizeRequest(BaseModel):
    asql: str
    style: dict = {}


# --- Routes ---


def _normalize_base_url(url: str) -> str:
    """Normalize a base URL (no trailing slash)."""
    return url.strip().rstrip("/")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Render the playground interface."""
    template_path = TEMPLATES_DIR / "index.html"
    if template_path.exists():
        content = template_path.read_text()

        docs_url = _normalize_base_url(os.environ.get("DOCS_URL", "https://analyticsql.com"))
        playground_url = _normalize_base_url(
            os.environ.get("PLAYGROUND_URL", "https://play.analyticsql.com")
        )
        content = content.replace("__DOCS_URL__", docs_url)
        content = content.replace("__PLAYGROUND_URL__", playground_url)

        # Inject examples data directly into the template
        import json

        examples_data = {
            "asql": ASQL_EXAMPLES,
            "pipeline": PIPELINE_EXAMPLES,
            "cohort": COHORT_EXAMPLES,
            "sampling": SAMPLING_EXAMPLES,
            "reshaping": RESHAPING_EXAMPLES,
            "column_operators": COLUMN_OPERATOR_EXAMPLES,
            "count_inference": COUNT_INFERENCE_EXAMPLES,
            "syntax_styles": SYNTAX_STYLES_EXAMPLES,
            "sql": SQL_EXAMPLES,
        }
        examples_json = json.dumps(examples_data)

        # Escape </script> to prevent breaking HTML parser
        # Use \u003c instead of < in the closing script tag
        examples_json = examples_json.replace("</script>", r"<\/script>")
        examples_json = examples_json.replace("</Script>", r"<\/Script>")
        examples_json = examples_json.replace("</SCRIPT>", r"<\/SCRIPT>")

        # Replace the placeholder with actual data
        content = content.replace("/* EXAMPLES_DATA_PLACEHOLDER */ {}", examples_json)

        # Inject dialect options (dynamically from SQLGlot)
        from_dialects = get_dialect_options(panel="from")
        to_dialects = get_dialect_options(panel="to")
        from_options = generate_dialect_options_html(from_dialects, selected="asql")
        to_options = generate_dialect_options_html(to_dialects, selected="snowflake")
        content = content.replace("<!-- FROM_DIALECT_OPTIONS -->", from_options)
        content = content.replace("<!-- TO_DIALECT_OPTIONS -->", to_options)

        return HTMLResponse(content=content)
    return HTMLResponse(content="<h1>Template not found</h1>", status_code=500)


@app.post("/api/compile")
async def api_compile(request: CompileRequest) -> dict:
    """API endpoint to compile ASQL to SQL."""
    try:
        if not request.asql.strip():
            return {"error": "Empty ASQL query"}

        # Build compile settings from request
        compile_settings = None
        if request.settings:
            compile_settings = CompileSettings.from_dict(request.settings)

        sql = compile(
            request.asql,
            dialect=request.dialect if request.dialect else None,
            pretty=True,
            settings=compile_settings,
        )
        return {"sql": sql}

    except ASQLSyntaxError as e:
        return {"error": f"Syntax Error: {str(e)}"}
    except ASQLCompilationError as e:
        return {"error": f"Compilation Error: {str(e)}"}
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


@app.post("/api/reverse-compile")
async def api_reverse_compile(request: ReverseCompileRequest) -> dict:
    """API endpoint to compile SQL to ASQL using sqlglot.transpile()."""
    try:
        if not request.sql.strip():
            return {"error": "Empty SQL query"}

        # Use sqlglot.transpile to convert SQL to ASQL
        source_dialect = request.source_dialect if request.source_dialect else None
        results = sqlglot.transpile(
            request.sql,
            read=source_dialect,
            write="asql",
        )
        
        if not results or not results[0]:
            return {"error": "Failed to convert SQL to ASQL"}
        
        asql = results[0]
        return {"asql": asql}

    except sqlglot.errors.ParseError as e:
        error_msg = str(e)
        error_msg = re.sub(r"\x1b\[[0-9;]*m", "", error_msg)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        return {"error": f"Parse Error: {error_msg}"}
    except Exception as e:
        error_msg = str(e)
        error_msg = re.sub(r"\x1b\[[0-9;]*m", "", error_msg)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        return {"error": f"Error: {error_msg}"}


@app.post("/api/detect-dialect")
async def api_detect_dialect(request: DetectDialectRequest) -> dict:
    """API endpoint to detect SQL dialect.
    
    Note: Dialect detection is heuristic-based. Returns None if unable to
    determine a specific dialect (the SQL is generic enough to work in multiple).
    """
    try:
        if not request.sql.strip():
            return {"dialect": None}

        # Try parsing with common dialects and see which one works best
        # For now, return None since dialect detection is complex and
        # sqlglot.transpile works without specifying a source dialect
        return {"dialect": None}
    except Exception as e:
        return {"dialect": None, "error": str(e)}


@app.post("/api/normalize")
async def api_normalize(request: NormalizeRequest) -> dict:
    """Normalize ASQL to configured style using sqlglot.transpile().
    
    Note: Style configuration is currently limited - use transpile's built-in
    normalization. Full style options will be added to the ASQL generator.
    """
    try:
        if not request.asql.strip():
            return {"error": "Empty ASQL query"}

        # Use sqlglot.transpile for ASQL → ASQL normalization
        # This applies the ASQL generator's standard formatting
        results = sqlglot.transpile(request.asql, read="asql", write="asql")
        
        if not results or not results[0]:
            return {"error": "Failed to normalize ASQL"}
        
        normalized = results[0]
        return {"normalized": normalized}

    except ASQLSyntaxError as e:
        return {"error": f"Syntax Error: {str(e)}"}
    except sqlglot.errors.ParseError as e:
        return {"error": f"Parse Error: {str(e)}"}
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


@app.get("/api/settings-schema")
async def api_settings_schema() -> dict:
    """Get the settings schema for the playground settings modal."""
    return {
        "compile": {
            "title": "Compile Settings",
            "description": "Settings that affect how ASQL is compiled to SQL",
            "fields": [
                {
                    "name": "auto_spine",
                    "label": "Auto Spine",
                    "type": "boolean",
                    "default": True,
                    "description": "Automatically add gap-filling for date truncations in GROUP BY",
                },
                {
                    "name": "week_start",
                    "label": "Week Start",
                    "type": "select",
                    "options": ["monday", "sunday"],
                    "default": "monday",
                    "description": "Which day the week() function starts on",
                },
                {
                    "name": "relative_date_type",
                    "label": "Relative Date Type",
                    "type": "select",
                    "options": ["timestamp", "date"],
                    "default": "timestamp",
                    "description": "What type '7 days ago' compiles to",
                },
                {
                    "name": "infer_join_keys",
                    "label": "Infer Join Keys",
                    "type": "boolean",
                    "default": False,
                    "description": "Infer join keys using {table}_id convention when no schema is available",
                },
                {
                    "name": "passthrough_comments",
                    "label": "Passthrough Comments",
                    "type": "boolean",
                    "default": True,
                    "description": "Preserve ASQL source comments in the generated SQL output",
                },
                {
                    "name": "include_transpilation_comments",
                    "label": "Transpilation Comments",
                    "type": "boolean",
                    "default": True,
                    "description": "Add explanatory comments about ASQL transformations (auto-spine, cohort, etc.)",
                },
            ],
        },
        "style": {
            "title": "Style Settings",
            "description": "Settings that affect ASQL output style (for SQL → ASQL)",
            "fields": [
                {
                    "name": "equality",
                    "label": "Equality Operator",
                    "type": "select",
                    "options": [
                        {"value": "single", "label": "= (SQL style)"},
                        {"value": "double", "label": "== (Python style)"},
                    ],
                    "default": "single",
                    "description": "Which equality operator to use",
                },
                {
                    "name": "count",
                    "label": "Count Notation",
                    "type": "select",
                    "options": [
                        {"value": "hash", "label": "# (shorthand)"},
                        {"value": "function", "label": "count(*) (function)"},
                    ],
                    "default": "hash",
                    "description": "How to write count expressions",
                },
                {
                    "name": "coalesce",
                    "label": "Null Coalescing",
                    "type": "select",
                    "options": [
                        {"value": "operator", "label": "?? (operator)"},
                        {"value": "function", "label": "coalesce() (function)"},
                    ],
                    "default": "operator",
                    "description": "How to write null coalescing",
                },
                {
                    "name": "descending",
                    "label": "Descending Order",
                    "type": "select",
                    "options": [
                        {"value": "prefix", "label": "-col (prefix)"},
                        {"value": "suffix", "label": "col DESC (suffix)"},
                    ],
                    "default": "prefix",
                    "description": "How to write descending order",
                },
                {
                    "name": "cast",
                    "label": "Type Casting",
                    "type": "select",
                    "options": [
                        {"value": "double_colon", "label": ":: (PostgreSQL)"},
                        {"value": "function", "label": "CAST() (SQL standard)"},
                    ],
                    "default": "double_colon",
                    "description": "How to write type casts",
                },
                {
                    "name": "quotes",
                    "label": "String Quotes",
                    "type": "select",
                    "options": [
                        {"value": "double", "label": '"double"'},
                        {"value": "single", "label": "'single'"},
                    ],
                    "default": "double",
                    "description": "Which quote style to use for strings",
                },
                {
                    "name": "function_shorthand",
                    "label": "Function Shorthand",
                    "type": "select",
                    "options": [
                        {"value": "underscore", "label": "sum_amount (underscore)"},
                        {"value": "space", "label": "sum amount (space)"},
                        {"value": "parens", "label": "sum(amount) (parens)"},
                    ],
                    "default": "underscore",
                    "description": "How to write function shorthands",
                },
                {
                    "name": "ignore_aliases",
                    "label": "Ignore Aliases",
                    "type": "boolean",
                    "default": True,
                    "description": "Strip column aliases from output (lets ASQL's auto-naming generate clean output)",
                },
            ],
        },
    }


@app.get("/api/examples")
async def api_examples() -> dict:
    """Get all ASQL examples organized by category."""
    return {
        "asql": ASQL_EXAMPLES,
        "pipeline": PIPELINE_EXAMPLES,
        "cohort": COHORT_EXAMPLES,
        "sampling": SAMPLING_EXAMPLES,
        "reshaping": RESHAPING_EXAMPLES,
        "column_operators": COLUMN_OPERATOR_EXAMPLES,
        "count_inference": COUNT_INFERENCE_EXAMPLES,
        "syntax_styles": SYNTAX_STYLES_EXAMPLES,
    }


@app.get("/api/sql-examples")
async def api_sql_examples() -> list:
    """API endpoint to get SQL translation examples."""
    return SQL_EXAMPLES


@app.get("/api/fivetran-examples")
async def api_fivetran_examples() -> list:
    """API endpoint to get Fivetran dbt examples."""
    examples = []

    # Try multiple possible paths for the examples directory
    possible_paths = [
        Path(__file__).parent.parent / "examples" / "real",
        Path("examples") / "real",
        Path(os.getcwd()) / "examples" / "real",
    ]

    real_examples_dir = None
    for path in possible_paths:
        if path.exists() and path.is_dir():
            real_examples_dir = path
            break

    if not real_examples_dir or not real_examples_dir.exists():
        return examples

    sql_files = sorted(real_examples_dir.glob("dbt_*.sql"))

    for sql_file in sql_files:
        try:
            content = sql_file.read_text()

            # Skip files that are too small or contain errors
            if len(content) < 100 or "404: Not Found" in content:
                continue

            # Parse metadata from header comments
            model = None
            dialect = "snowflake"

            for line in content.split("\n")[:10]:
                if line.startswith("-- Model:"):
                    model = line.replace("-- Model:", "").strip()
                elif line.startswith("-- Dialect:"):
                    dialect = line.replace("-- Dialect:", "").strip().lower()

            # Generate title from filename
            filename = sql_file.stem
            filename_dialect = None
            for d in ["snowflake", "bigquery", "postgres", "redshift", "mysql"]:
                if filename.endswith("_" + d):
                    filename_dialect = d
                    break

            name_base = filename.replace("dbt_", "")
            if filename_dialect:
                name_base = name_base.replace("_" + filename_dialect, "")
            name_parts = name_base.split("_")

            repo = name_parts[0] if name_parts else "unknown"
            repo_display = repo.replace("_", " ").title()
            model_name = (
                " ".join(name_parts[1:])
                if len(name_parts) > 1
                else name_parts[0] if name_parts else "model"
            )
            model_name = model_name.replace("__", " ").replace("_", " ").title()

            title = f"{repo_display}: {model_name}"
            desc = f"Real query from {repo_display} dbt package"
            if model:
                desc += f" ({model})"

            final_dialect = filename_dialect or dialect
            dialect_map = {
                "snowflake": "snowflake",
                "bigquery": "bigquery",
                "postgres": "postgres",
                "redshift": "redshift",
            }
            sql_dialect = dialect_map.get(final_dialect.lower(), "snowflake")

            cleaned_content = strip_jinja_templates(content)

            examples.append(
                {
                    "title": title,
                    "desc": desc,
                    "language": sql_dialect,
                    "toLanguage": "asql",
                    "query": cleaned_content,
                }
            )
        except Exception as e:
            import sys

            print(f"Warning: Could not load example {sql_file}: {e}", file=sys.stderr)
            continue

    return examples


@app.get("/api/debug/examples-path")
async def api_debug_examples_path() -> dict:
    """Debug endpoint to check examples directory access."""
    debug_info = {
        "current_working_directory": os.getcwd(),
        "playground_file": __file__,
        "playground_dir": str(Path(__file__).parent),
        "possible_paths": [],
        "found_path": None,
        "examples_count": 0,
    }

    possible_paths = [
        Path(__file__).parent.parent / "examples" / "real",
        Path("examples") / "real",
        Path(os.getcwd()) / "examples" / "real",
    ]

    for path in possible_paths:
        path_str = str(path)
        exists = path.exists()
        is_dir = path.is_dir() if exists else False
        file_count = len(list(path.glob("*.sql"))) if exists and is_dir else 0

        debug_info["possible_paths"].append(
            {"path": path_str, "exists": exists, "is_dir": is_dir, "file_count": file_count}
        )

        if exists and is_dir and not debug_info["found_path"]:
            debug_info["found_path"] = path_str
            debug_info["examples_count"] = file_count

    return debug_info


# --- Visual Editor API Endpoints ---


@app.post("/api/visual/parse")
async def parse_to_visual(request: Request):
    """
    Convert ASQL text to JSON representation for visual editor.

    Request body:
        {"asql": "from users where status == \"active\""}

    Response:
        {"success": true, "query": {...}} or {"success": false, "error": "..."}
    """
    try:
        data = await request.json()
        asql_text = data.get("asql", "").strip()

        if not asql_text:
            return {"success": False, "error": "No ASQL query provided"}

        # Convert ASQL to JSON using visual_asql dialect
        # Now supports CTEs, set operations, and multiple queries
        json_str = sqlglot.transpile(asql_text, read="asql", write="visual_asql")[0]
        query_json = json.loads(json_str)

        return {"success": True, "query": query_json}
    except ASQLSyntaxError as e:
        return {"success": False, "error": f"Syntax error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Parse error: {str(e)}"}


@app.post("/api/visual/compile")
async def compile_from_visual(request: Request):
    """
    Convert JSON representation from visual editor to ASQL text.

    Request body:
        {"query": {"from": {"table": "users"}, "transforms": [...]}}

    Response:
        {"success": true, "asql": "from users\\n  where ..."} or {"success": false, "error": "..."}
    """
    try:
        data = await request.json()
        query_json = data.get("query", {})

        if not query_json:
            return {"success": False, "error": "No query provided"}

        # Convert JSON to ASQL
        asql_text = json_to_asql(query_json)

        return {"success": True, "asql": asql_text}
    except Exception as e:
        return {"success": False, "error": f"Compilation error: {str(e)}"}


@app.get("/api/visual/operations")
async def list_visual_operations():
    """
    List available operations for the visual editor.
    Dynamically generated from ui_schema.
    """
    from asql.ui_schema import list_all_operations

    return {"operations": list_all_operations()}


@app.get("/api/visual/operations/{operation_type}/schema")
async def get_operation_schema(operation_type: str):
    """
    Get UI schema for a specific operation type.

    Returns the schema needed to render the operation's form,
    including parameter definitions, widgets, and validation.
    """
    from asql.ui_schema import get_operation_schema

    schema = get_operation_schema(operation_type)

    if not schema:
        return {"error": f"Unknown operation type: {operation_type}"}

    return schema
