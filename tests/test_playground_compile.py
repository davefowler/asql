"""`/api/compile` compiles against the playground's tables and column types.

Without them, BigQuery month/year arithmetic can't tell a TIMESTAMP from a
DATE and column operators can't expand on dialects without EXCLUDE.
"""

from __future__ import annotations

import asyncio

from asql.playground.app import CompileRequest, api_compile


def compile_(query: str, dialect: str) -> dict[str, str]:
    return asyncio.run(api_compile(CompileRequest(asql=query, dialect=dialect)))


def test_bigquery_month_arithmetic_on_a_timestamp_column() -> None:
    result = compile_("from orders select created_at - 1 month as a", "bigquery")
    assert "error" not in result, result
    assert "TIMESTAMP(DATETIME(created_at) - INTERVAL '1' MONTH)" in result["sql"]


def test_column_operators_expand_without_native_exclude() -> None:
    result = compile_("from users except email", "postgres")
    assert "error" not in result, result
    assert "email" not in result["sql"]
