"""Regenerate parity.json: Python asql is the oracle for the Rust crate's tests.

uv run --all-extras --locked python rust/asql-core/tests/fixtures/gen_parity.py
"""

import json
import pathlib
import warnings

warnings.filterwarnings("ignore")
import asql

QUERIES = [
    "from users",
    "from users where status == 'active'",
    "from orders where amount > 100 and status == 'completed' select id, amount",
    "from orders group by region (sum(amount) as revenue, # as orders)",
    "from orders group by region, status (sum(amount), avg(amount), #)",
    "from orders where status == 'completed' group by region (sum(amount) as revenue) order by -revenue limit 10",
    "from users select name, email order by name limit 5",
    "from events where user_id = 7 order by -created_at, id",
]
TARGETS = ["postgres", "duckdb", "bigquery", "snowflake"]
rows = [
    {"asql": q, "sql": {d: asql.transpile(q, write=d)[0] for d in TARGETS}}
    for q in QUERIES
]
out = pathlib.Path(__file__).with_name("parity.json")
out.write_text(json.dumps(rows, indent=1) + "\n")
print(f"wrote {out} ({len(rows)} queries x {len(TARGETS)} dialects)")
