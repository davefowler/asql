"""Dialect-specific expansion for explode markers."""

from __future__ import annotations

import re
from typing import Optional


def process_explode_markers(preparsed: str, dialect: Optional[str]) -> str:
    """Replace __ASQL_EXPLODE__ markers with dialect-specific SQL."""
    result = preparsed
    dialect_lower = (dialect or "").lower()

    pattern = r"__ASQL_EXPLODE_START__(.+?)__ASQL_EXPLODE_SEP__(.+?)__ASQL_EXPLODE_END__"

    def replace_explode(match: re.Match) -> str:
        array_expr = match.group(1)
        alias = match.group(2)

        if dialect_lower == "snowflake":
            return (
                " CROSS JOIN (SELECT value AS "
                f"{alias} FROM TABLE(FLATTEN(INPUT => {array_expr}))) AS _{alias}_exploded"
            )
        if dialect_lower == "bigquery":
            return f", UNNEST({array_expr}) AS {alias}"
        if dialect_lower in ("postgres", "postgresql", "redshift", "duckdb"):
            return f", UNNEST({array_expr}) AS {alias}"

        return f", UNNEST({array_expr}) AS {alias}"

    return re.sub(pattern, replace_explode, result)
