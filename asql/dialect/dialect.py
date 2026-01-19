"""ASQL Dialect definition and registration.

This is the main dialect class that connects the tokenizer, parser, and generator.
"""

from sqlglot.dialects.dialect import Dialect

from asql.dialect.generator import ASQLGenerator
from asql.dialect.parser import ASQLParser
from asql.dialect.tokenizer import ASQLTokenizer


class ASQL(Dialect):
    """ASQL (Analytic SQL) dialect for SQLGlot.
    
    ASQL is a human-readable, pipeline-based query language that transpiles to SQL.
    This dialect uses SQLGlot's TRANSFORM_PARSERS pattern (like PRQL) for proper
    pipeline semantics.
    
    IMPORTANT: Two different dialect concepts:
    
    1. extend_dialect (INPUT) - What SQL syntax is allowed INSIDE ASQL queries.
       This lets users write dialect-specific SQL within their ASQL code.
       Example: extend_dialect="duckdb" allows DuckDB syntax like [x FOR x IN arr]
       
    2. write dialect (OUTPUT) - What SQL dialect to generate.
       This is passed to transpile(write=...) or compile(dialect=...)
       
    These can be DIFFERENT! You might write DuckDB-flavored ASQL but output Postgres.
    
    Usage:
        # Simple: ASQL → DuckDB (default)
        sqlglot.transpile(query, read="asql", write="duckdb")
        
        # With settings: allow DuckDB syntax in input, output to Postgres
        asql = ASQL(extend_dialect="duckdb", auto_spine=False)
        sqlglot.transpile(query, read=asql, write="postgres")
    
    Or via inline SET statements in the query:
        SET extend_dialect = 'duckdb';
        SET auto_spine = false;
        from orders group by month(date)
    
    Key features handled:
    - FROM-first syntax: `from users where status = 'active'`
    - Pipeline operators: `from users | where x | group by y`
    - Proper CTE wrapping: `group by X | where Y` → CTE + WHERE
    - Descending order shorthand: `-column` → `column DESC`
    - NULL equality: `== null` → `IS NULL`
    - Ternary operator: `x ? y : z` → `CASE WHEN x THEN y ELSE z END`
    - Relative dates: `7 days ago` → `CURRENT_TIMESTAMP - INTERVAL '7 days'`
    - Date arithmetic: `col + 7 days` → `col + INTERVAL '7 days'`
    """
    
    # All supported ASQL settings - can be passed to constructor or set via SET statements
    SUPPORTED_SETTINGS = {
        # Inherited from Dialect
        "version",
        "normalization_strategy",
        
        # === Compile Settings (ASQL → SQL) ===
        # IMPORTANT: extend_dialect is the INPUT/PARSING dialect, NOT the output dialect!
        # It determines what SQL syntax is allowed INSIDE ASQL queries.
        # Example: extend_dialect="duckdb" allows DuckDB-specific syntax in ASQL.
        # The OUTPUT dialect is separate (passed to transpile(write=...) or compile(dialect=...))
        "extend_dialect",           # SQL dialect that ASQL extends for parsing (e.g., "duckdb")
        "schema",                   # Schema object for FK inference, column operators
        "auto_spine",               # Gap-filling for date GROUP BY (default: True)
        "week_start",               # "monday" or "sunday" (default: "monday")
        "relative_date_type",       # "timestamp" or "date" (default: "timestamp")
        "alias_template",           # Default auto-alias template
        "alias_prefixes",           # {"count": "num", "sum": "total"}
        "alias_templates",          # Per-function alias templates
        "infer_join_keys",          # Use {table}_id convention (default: False)
        "include_transpilation_comments",  # Add /* ASQL: ... */ comments (default: True)
        "passthrough_comments",     # Preserve source comments (default: True)
        
        # === Style Settings (SQL → ASQL) ===
        "equality",                 # "single" or "double" (default: "single")
        "count",                    # "hash" or "function" (default: "hash")
        "coalesce",                 # "operator" or "function" (default: "operator")
        "descending",               # "prefix" or "suffix" (default: "prefix")
        "cast",                     # "double_colon" or "function" (default: "double_colon")
        "quotes",                   # "double" or "single" (default: "double")
        "function_shorthand",       # "underscore", "space", "parens" (default: "underscore")
        "squash_empty_ctes",        # Remove pass-through CTEs (default: True)
        "keep_final_empty_cte",     # Keep final empty CTE (default: False)
        "ignore_aliases",           # Strip explicit aliases (default: False)
    }
    
    # Default values for all settings
    SETTING_DEFAULTS = {
        # Compile settings
        "extend_dialect": None,
        "schema": None,
        "auto_spine": True,
        "week_start": "monday",
        "relative_date_type": "timestamp",
        "alias_template": None,
        "alias_prefixes": {},
        "alias_templates": {},
        "infer_join_keys": False,
        "include_transpilation_comments": True,
        "passthrough_comments": True,
        
        # Style settings
        "equality": "single",
        "count": "hash",
        "coalesce": "operator",
        "descending": "prefix",
        "cast": "double_colon",
        "quotes": "double",
        "function_shorthand": "underscore",
        "squash_empty_ctes": True,
        "keep_final_empty_cte": False,
        "ignore_aliases": False,
    }
    
    # Dialect configuration constants (following ClickHouse pattern)
    DPIPE_IS_STRING_CONCAT = True  # || is string concatenation, not OR
    NORMALIZE_FUNCTIONS: bool | str = False  # Preserve function name casing
    
    class Tokenizer(ASQLTokenizer):
        pass
    
    class Parser(ASQLParser):
        pass
    
    class Generator(ASQLGenerator):
        pass
    
    def __init__(self, **kwargs) -> None:
        """Initialize ASQL dialect with settings.
        
        All ASQL settings can be passed as kwargs:
            asql = ASQL(extend_dialect="postgres", auto_spine=False)
        
        Settings are stored in self.settings and accessible to parser/generator.
        """
        # Apply defaults for ASQL-specific settings
        for key, default in self.SETTING_DEFAULTS.items():
            if key not in kwargs:
                # Don't set None or empty dict defaults - let them be absent
                if default is not None and default != {}:
                    kwargs[key] = default
        
        # Call parent __init__ which validates against SUPPORTED_SETTINGS
        super().__init__(**kwargs)


# Register the dialect with SQLGlot
def register_asql_dialect() -> None:
    """Register the ASQL dialect with SQLGlot."""
    if "asql" not in Dialect._classes:
        Dialect["asql"] = ASQL


# Auto-register on import
register_asql_dialect()
