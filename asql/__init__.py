"""ASQL: Analytic SQL - A modern, pipeline-based query language."""

from asql.compiler import compile
from asql.dialect import ASQLDialect

__version__ = "0.1.0"
__all__ = ["compile", "ASQLDialect"]

