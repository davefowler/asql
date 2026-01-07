"""
dbt-asql: Write dbt models in ASQL

ASQL is a modern, readable query language that compiles to SQL.
This package integrates ASQL with dbt, allowing you to write
.asql model files that are automatically compiled.
"""

__version__ = "0.1.0"

from dbt_asql.compiler import compile_asql_model
from dbt_asql.plugin import Plugin

__all__ = [
    "compile_asql_model",
    "Plugin",
    "__version__",
]

