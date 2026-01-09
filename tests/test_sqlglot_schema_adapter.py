from __future__ import annotations

from asql.compiler.sqlglot_schema_adapter import to_sqlglot_schema
from asql.schema import Schema


def test_sqlglot_schema_adapter_converts_tables_and_columns() -> None:
    asql_schema = Schema.from_dict(
        {
            "tables": {
                "orders": {"columns": ["id", "user_id"]},
                "users": {"columns": ["id"]},
            },
            "relationships": [
                {
                    "from_table": "orders",
                    "from_column": "user_id",
                    "to_table": "users",
                    "to_column": "id",
                    "source": "explicit",
                }
            ],
        }
    )

    sqlglot_schema = to_sqlglot_schema(asql_schema, dialect="postgres")
    assert sqlglot_schema is not None
    assert sqlglot_schema.has_column("orders", "id")
    assert sqlglot_schema.has_column("orders", "user_id")
    assert sqlglot_schema.has_column("users", "id")

