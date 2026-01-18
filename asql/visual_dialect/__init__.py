"""Visual ASQL Dialect package.

This package provides the VisualASQL dialect for SQLGlot, enabling bidirectional
JSON <-> SQL conversion for visual query builders.

Usage:
    import sqlglot
    import asql.dialect  # Registers 'asql' dialect
    import asql.visual_dialect  # Registers 'visual_asql' dialect
    
    # SQL → JSON (with column tracking)
    json_output = sqlglot.transpile(
        "from users where id = 1", 
        read="asql", 
        write="visual_asql"
    )[0]
    
    # JSON → SQL
    sql = sqlglot.transpile(
        '{"from": {"table": "users"}, "transforms": []}',
        read="visual_asql",
        write="postgres"
    )[0]
"""

from asql.visual_dialect.dialect import VisualASQL, register_visual_asql_dialect
from asql.visual_dialect.generator import VisualASQLGenerator

__all__ = [
    "VisualASQL",
    "VisualASQLGenerator",
    "register_visual_asql_dialect",
]

# Ensure dialect is registered on package import
register_visual_asql_dialect()
