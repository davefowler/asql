"""ASQL: Analytic SQL - A modern, pipeline-based query language."""

from asql.compiler import compile
from asql.dialect import ASQLDialect
from asql.reverse_compiler import reverse_compile, detect_dialect

__version__ = "0.1.0"
__all__ = ["compile", "ASQLDialect", "reverse_compile", "detect_dialect"]

