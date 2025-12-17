"""ASQL Interactive Playground - FastAPI application."""

import os
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError
from asql.reverse_compiler import reverse_compile, detect_dialect
from asql.config import ASQLConfig, StyleConfig

from .jinja_utils import strip_jinja_templates
from .examples import (
    ASQL_EXAMPLES,
    PIPELINE_EXAMPLES,
    COHORT_EXAMPLES,
    SAMPLING_EXAMPLES,
    RESHAPING_EXAMPLES,
    COLUMN_OPERATOR_EXAMPLES,
    COUNT_INFERENCE_EXAMPLES,
    SQL_EXAMPLES,
    get_all_examples,
)


app = FastAPI(title="ASQL Playground", version="1.0.0")

# Mount static files
STATIC_DIR = Path(__file__).parent.parent / "static"
SYNTAX_DIR = Path(__file__).parent.parent / "syntax"
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Mount syntax files first (more specific path)
if SYNTAX_DIR.exists():
    app.mount("/static/syntax", StaticFiles(directory=str(SYNTAX_DIR)), name="syntax")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- Pydantic Models ---

class CompileRequest(BaseModel):
    asql: str
    dialect: str = ""


class ReverseCompileRequest(BaseModel):
    sql: str
    source_dialect: str = ""


class DetectDialectRequest(BaseModel):
    sql: str


class NormalizeRequest(BaseModel):
    asql: str
    style: dict = {}


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Render the playground interface."""
    template_path = TEMPLATES_DIR / "index.html"
    if template_path.exists():
        content = template_path.read_text()
        
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
            "sql": SQL_EXAMPLES,
        }
        examples_json = json.dumps(examples_data)
        
        # Escape </script> to prevent breaking HTML parser
        # Use \u003c instead of < in the closing script tag
        examples_json = examples_json.replace("</script>", r"<\/script>")
        examples_json = examples_json.replace("</Script>", r"<\/Script>")
        examples_json = examples_json.replace("</SCRIPT>", r"<\/SCRIPT>")
        
        # Replace the placeholder with actual data
        content = content.replace(
            '/* EXAMPLES_DATA_PLACEHOLDER */ {}',
            examples_json
        )
        
        return HTMLResponse(content=content)
    return HTMLResponse(content="<h1>Template not found</h1>", status_code=500)


@app.post("/api/compile")
async def api_compile(request: CompileRequest) -> dict:
    """API endpoint to compile ASQL to SQL."""
    try:
        if not request.asql.strip():
            return {"error": "Empty ASQL query"}
        
        sql = compile(
            request.asql,
            dialect=request.dialect if request.dialect else None,
            pretty=True
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
    """API endpoint to compile SQL to ASQL."""
    try:
        if not request.sql.strip():
            return {"error": "Empty SQL query"}
        
        asql = reverse_compile(
            request.sql,
            source_dialect=request.source_dialect if request.source_dialect else None
        )
        return {"asql": asql}
        
    except ASQLCompilationError as e:
        error_msg = str(e)
        # Clean up error messages - remove ANSI escape codes
        error_msg = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        return {"error": f"Compilation Error: {error_msg}"}
    except Exception as e:
        error_msg = str(e)
        error_msg = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        return {"error": f"Error: {error_msg}"}


@app.post("/api/detect-dialect")
async def api_detect_dialect(request: DetectDialectRequest) -> dict:
    """API endpoint to detect SQL dialect."""
    try:
        if not request.sql.strip():
            return {"dialect": None}
        
        dialect = detect_dialect(request.sql)
        return {"dialect": dialect}
    except Exception as e:
        return {"dialect": None, "error": str(e)}


@app.post("/api/normalize")
async def api_normalize(request: NormalizeRequest) -> dict:
    """Normalize ASQL to configured style."""
    try:
        if not request.asql.strip():
            return {"error": "Empty ASQL query"}
        
        style_config = request.style
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
        )
        config = ASQLConfig(style=style)
        
        # Compile to SQL then reverse compile to normalized ASQL
        sql = compile(request.asql, pretty=True)
        normalized = reverse_compile(sql, config=config)
        
        return {"normalized": normalized}
        
    except ASQLSyntaxError as e:
        return {"error": f"Syntax Error: {str(e)}"}
    except ASQLCompilationError as e:
        return {"error": f"Compilation Error: {str(e)}"}
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


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
        Path(__file__).parent.parent / 'examples' / 'real',
        Path('examples') / 'real',
        Path(os.getcwd()) / 'examples' / 'real',
    ]
    
    real_examples_dir = None
    for path in possible_paths:
        if path.exists() and path.is_dir():
            real_examples_dir = path
            break
    
    if not real_examples_dir or not real_examples_dir.exists():
        return examples
    
    sql_files = sorted(real_examples_dir.glob('dbt_*.sql'))
    
    for sql_file in sql_files:
        try:
            content = sql_file.read_text()
            
            # Skip files that are too small or contain errors
            if len(content) < 100 or "404: Not Found" in content:
                continue
            
            # Parse metadata from header comments
            source = None
            model = None
            dialect = "snowflake"
            
            for line in content.split('\n')[:10]:
                if line.startswith('-- Source:'):
                    source = line.replace('-- Source:', '').strip()
                elif line.startswith('-- Model:'):
                    model = line.replace('-- Model:', '').strip()
                elif line.startswith('-- Dialect:'):
                    dialect = line.replace('-- Dialect:', '').strip().lower()
            
            # Generate title from filename
            filename = sql_file.stem
            filename_dialect = None
            for d in ['snowflake', 'bigquery', 'postgres', 'redshift', 'mysql']:
                if filename.endswith('_' + d):
                    filename_dialect = d
                    break
            
            name_base = filename.replace('dbt_', '')
            if filename_dialect:
                name_base = name_base.replace('_' + filename_dialect, '')
            name_parts = name_base.split('_')
            
            repo = name_parts[0] if name_parts else 'unknown'
            repo_display = repo.replace('_', ' ').title()
            model_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else name_parts[0] if name_parts else 'model'
            model_name = model_name.replace('__', ' ').replace('_', ' ').title()
            
            title = f"{repo_display}: {model_name}"
            desc = f"Real query from {repo_display} dbt package"
            if model:
                desc += f" ({model})"
            
            final_dialect = filename_dialect or dialect
            dialect_map = {
                'snowflake': 'snowflake',
                'bigquery': 'bigquery',
                'postgres': 'postgres',
                'redshift': 'redshift'
            }
            sql_dialect = dialect_map.get(final_dialect.lower(), 'snowflake')
            
            cleaned_content = strip_jinja_templates(content)
            
            examples.append({
                "title": title,
                "desc": desc,
                "language": sql_dialect,
                "toLanguage": "asql",
                "query": cleaned_content
            })
        except Exception as e:
            import sys
            print(f"Warning: Could not load example {sql_file}: {e}", file=sys.stderr)
            continue
    
    return examples


@app.get("/api/debug/examples-path")
async def api_debug_examples_path() -> dict:
    """Debug endpoint to check examples directory access."""
    debug_info = {
        'current_working_directory': os.getcwd(),
        'playground_file': __file__,
        'playground_dir': str(Path(__file__).parent),
        'possible_paths': [],
        'found_path': None,
        'examples_count': 0
    }
    
    possible_paths = [
        Path(__file__).parent.parent / 'examples' / 'real',
        Path('examples') / 'real',
        Path(os.getcwd()) / 'examples' / 'real',
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
    
    return debug_info
