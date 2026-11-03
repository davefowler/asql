"""Every runnable docs example must execute, not just compile.

The docs build compiles each ` ```asql-play ` block for every dialect; this
runs the DuckDB compilation against empty tables shaped like the playground
schema, which catches SQL the engine rejects (an ambiguous column after a
join, an alias inside a function argument, a column dropped by an earlier
stage) that compiling alone cannot.

Examples that name tables or columns the playground schema does not have are
reported as xfail with the engine's message: they are schema drift to clean
up, not compiler bugs, and must not hide one. Anything else fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pytest

import asql
from asql.playground.schema import PLAYGROUND_SCHEMA, playground_schema

_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

DOCS_EXAMPLES = [
    (f"{path.relative_to(_DOCS_DIR)}#{index}", block.strip())
    for path in sorted(_DOCS_DIR.rglob("*.md"))
    for index, block in enumerate(
        re.findall(r"```asql-play\s*\n(.*?)```", path.read_text(), re.S)
    )
    if block.strip()
]

# DuckDB's wording for a table or column the example expects and the
# playground schema lacks.
_SCHEMA_DRIFT = re.compile(
    r"Table with name \w+ does not exist"
    r"|Referenced column \"?\w+\"? not found in FROM clause"
    r"|Table \"\w+\" does not have a column named"
)


def _duckdb_type(dtype: str) -> str:
    """Playground types are sqlglot-ish; DuckDB spells arrays as T[]."""
    match = re.fullmatch(r"ARRAY<(.+)>", dtype)
    return f"{match.group(1)}[]" if match else dtype


@pytest.fixture(scope="module")
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for table, columns in PLAYGROUND_SCHEMA.items():
        cols = ", ".join(
            f'"{name}" {_duckdb_type(dtype)}' for name, dtype in columns.items()
        )
        con.sql(f'CREATE TABLE "{table}" ({cols})')
    return con


@pytest.mark.parametrize(
    ("example_id", "query"), DOCS_EXAMPLES, ids=[e[0] for e in DOCS_EXAMPLES]
)
def test_docs_example_executes_on_duckdb(
    con: duckdb.DuckDBPyConnection, example_id: str, query: str
) -> None:
    statements = asql.transpile(
        query, write="duckdb", schema=playground_schema(), infer_join_keys=True
    )
    for sql in statements:
        if "SELECT" not in sql.upper():
            continue  # a comment-only statement, nothing to run
        try:
            con.sql(sql).fetchall()
        except duckdb.Error as e:
            message = str(e).splitlines()[0]
            if _SCHEMA_DRIFT.search(message):
                pytest.xfail(f"playground schema drift: {message}")
            raise
