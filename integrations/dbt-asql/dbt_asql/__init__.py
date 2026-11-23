"""
dbt-asql: Write dbt models in ASQL

ASQL is SQL for analysts: a superset of SQL that compiles to standard SQL.
This package integrates ASQL with dbt, allowing you to write
.asql model files that are automatically compiled.
"""

__version__ = "0.1.0"

from dbt_asql.compiler import compile_asql_model

__all__ = [
    "compile_asql_model",
    "__version__",
]
