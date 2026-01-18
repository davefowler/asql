"""
VisualASQL Dialect - JSON-based dialect for visual query builders.

This dialect enables bidirectional conversion between JSON and SQL,
making it easy to build visual query builder interfaces.
"""

import json
import typing as t

from sqlglot import exp
from sqlglot.dialects.dialect import Dialect

from asql.dialect import ASQL, ASQLParser, ASQLTokenizer
from asql.json_schema import json_to_asql
from asql.visual_dialect.generator import VisualASQLGenerator


class VisualASQL(Dialect):
    """JSON-based visual ASQL dialect.
    
    Supports bidirectional conversion:
    - JSON → SQL: Parses JSON input, converts to ASQL, then to SQL AST
    - SQL → JSON: Generates JSON with column tracking at each pipeline stage
    
    Usage:
        # JSON → SQL
        sqlglot.transpile(json_str, read="visual_asql", write="postgres")
        
        # SQL → JSON  
        sqlglot.transpile(sql, read="postgres", write="visual_asql")
    """

    class Tokenizer(ASQLTokenizer):
        """Reuse ASQL tokenizer."""
        pass

    class Parser(ASQLParser):
        """Reuse ASQL parser."""
        pass

    class Generator(VisualASQLGenerator):
        """JSON generator with column tracking."""
        pass

    def parse(self, sql: str, **opts: t.Any) -> t.List[t.Optional[exp.Expression]]:
        """Intercept JSON input before tokenization.
        
        If input looks like JSON (starts with { or [), convert it to ASQL text
        first, then parse using the ASQL parser.
        """
        stripped = sql.strip()
        
        # Check if input is JSON
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                query_json = json.loads(stripped)
            except json.JSONDecodeError:
                # Not valid JSON, try parsing as regular ASQL
                return super().parse(sql, **opts)
            
            try:
                asql_text = json_to_asql(query_json)
                # Delegate to ASQL parser
                return ASQL().parse(asql_text, **opts)
            except (KeyError, TypeError, ValueError) as e:
                # JSON is valid but schema is wrong
                raise ValueError(f"Invalid visual_asql JSON structure: {e}") from e
        
        # Not JSON - parse as regular ASQL
        return super().parse(sql, **opts)


def register_visual_asql_dialect() -> None:
    """Register the VisualASQL dialect with SQLGlot."""
    if "visual_asql" not in Dialect._classes:
        Dialect._classes["visual_asql"] = VisualASQL
