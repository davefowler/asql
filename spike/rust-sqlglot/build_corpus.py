"""Build a corpus of SQL that asql emits, per target dialect, plus sqlglot's cross-dialect transpile.

Output: corpus.json = [{"id", "asql", "dialect", "sql", "cross": {write_dialect: sql_or_null}}]
"""
import json, sys, warnings
warnings.filterwarnings("ignore")
import sqlglot
import asql
from asql.playground.examples import get_all_examples_flat

COMMENTS = "--comments" in sys.argv
TARGETS = ["postgres", "bigquery", "snowflake", "duckdb", "redshift", "mysql"]
rows = []
fails = 0
for cat, title, query in get_all_examples_flat():
    for d in TARGETS:
        try:
            sql = asql.transpile(query, write=d, passthrough_comments=COMMENTS)[0]
        except Exception as e:  # noqa: BLE001
            fails += 1
            continue
        cross = {}
        for w in TARGETS:
            if w == d:
                continue
            try:
                cross[w] = sqlglot.transpile(sql, read=d, write=w)[0]
            except Exception:  # noqa: BLE001
                cross[w] = None
        # identity: parse in d, regenerate in d (what sqlglot itself does)
        try:
            ident = sqlglot.transpile(sql, read=d, write=d)[0]
        except Exception:  # noqa: BLE001
            ident = None
        rows.append({"id": f"{cat}/{title}", "asql": query, "dialect": d, "sql": sql, "identity": ident, "cross": cross})
json.dump(rows, open(sys.argv[1], "w"), indent=1)
print(f"{len(rows)} rows, {fails} asql failures", file=sys.stderr)
