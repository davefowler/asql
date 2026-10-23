"""Compare polyglot-sql output with Python sqlglot output on the asql corpus.

Match levels: exact string
AST-equal (both parsed by sqlglot in the write dialect);
mismatch
polyglot error/panic.
"""

import collections
import json
import sys
import warnings

warnings.filterwarnings("ignore")
import sqlglot

with open(sys.argv[1]) as f:
    rows = json.load(f)
stats = collections.Counter()
by_pair = collections.defaultdict(collections.Counter)
examples = collections.defaultdict(list)


def classify(py, rs, write):
    if py is None:
        return "py_fail"
    if isinstance(rs, dict) and "Err" in rs:
        return "rs_panic" if rs["Err"] == "PANIC" else "rs_error"
    rs = rs["Ok"] if isinstance(rs, dict) else rs
    if rs == py:
        return "exact"
    try:
        a = sqlglot.parse_one(py, read=write)
        b = sqlglot.parse_one(rs, read=write)
        if a == b:
            return "ast_equal"
    except Exception:  # noqa: BLE001
        return "rs_unparseable"
    return "mismatch"


for r in rows:
    d = r["dialect"]
    c = classify(r["identity_py"], r["identity_rs"], d)
    stats[c] += 1
    by_pair[f"{d}->{d}"][c] += 1
    if c not in ("exact", "ast_equal") and len(examples[c]) < 12:
        examples[c].append(
            (
                r["id"],
                f"{d}->{d}",
                r["sql"][:300],
                r["identity_py"] and r["identity_py"][:300],
                str(r["identity_rs"])[:300],
            )
        )
    for w, (py, rs) in r["cross"].items():
        c = classify(py, rs, w)
        stats[c] += 1
        by_pair[f"{d}->{w}"][c] += 1
        if c not in ("exact", "ast_equal") and len(examples[c]) < 12:
            examples[c].append(
                (r["id"], f"{d}->{w}", r["sql"][:300], py and py[:300], str(rs)[:300])
            )

total = sum(stats.values())
print(f"total cases: {total}")
for k, v in stats.most_common():
    print(f"  {k:16s} {v:5d}  {100 * v / total:5.1f}%")
print("\nper read->write pair (exact+ast_equal / total):")
for pair, c in sorted(by_pair.items()):
    t = sum(c.values())
    ok = c["exact"] + c["ast_equal"]
    print(
        f"  {pair:22s} {ok:4d}/{t:<4d} {100 * ok / t:5.1f}%   "
        + " ".join(f"{k}={v}" for k, v in c.items() if k not in ("exact", "ast_equal"))
    )
for kind, exs in examples.items():
    print(f"\n=== examples: {kind}")
    for ex in exs[:8]:
        print(" -", ex[0], ex[1])
        print("   in :", ex[2].replace("\n", " "))
        print("   py :", (ex[3] or "").replace("\n", " "))
        print("   rs :", ex[4].replace("\n", " "))
