"""Visual ASQL round trips must not change a query's meaning.

Every UI built on Visual ASQL renders from
``sqlglot.transpile(asql_text, read="asql", write="visual_asql")`` and writes
back through ``asql.json_schema.json_to_asql``. Users toggle freely between
the visual and text modes, so for every ASQL query ``q`` and target dialect
``d`` the invariant is::

    asql.transpile(q, write=d)[0]  ≡  asql.transpile(json_to_asql(visual(q)), write=d)[0]

"≡" compares sqlglot ASTs after normalization (parentheses and comments are
stripped), so cosmetic differences such as ``NOT a IN (…)`` versus
``NOT (a IN (…))`` pass while any dropped clause or substituted operator
fails.
"""

from __future__ import annotations

import json

import pytest
import sqlglot
from sqlglot import exp

import asql
from asql.errors import ASQLDialectError
from asql.json_schema import json_to_asql
from asql.playground.examples import get_all_examples_flat

DIALECTS = ["duckdb", "postgres", "snowflake"]

# (id, asql query). The first block reproduces the failures from the audit
# (finding C12); the rest covers the operators the visual builder exposes.
CASES: list[tuple[str, str]] = [
    # --- audit reproductions -------------------------------------------
    ("schema_qualified_from", "from main.opportunities"),
    (
        "schema_qualified_join",
        "from main.opportunities & main.accounts on opportunities.account_id = accounts.id",
    ),
    ("quoted_column_where", "from users where `Last Name` = 'x'"),
    ("quoted_table", "from `my schema`.`my table`"),
    (
        "quoted_group_by",
        "from t group by `my col` ( sum(`the amt`) as `Total Amt` )",
    ),
    ("quoted_order_by", "from t order by -`my col`"),
    ("quoted_select", "from t select `my col`, a as `My A`"),
    ("quoted_except", "from t except `my col`"),
    ("quoted_rename", "from t rename `my col` as `your col`"),
    ("quoted_extend", "from t extend `a b` * 2 as `c d`"),
    ("quoted_join", "from t & `other t` on t.id = `other t`.id"),
    ("quoted_qualified_select", "from a & b on a.id = b.aid select a.`my col`, b.z"),
    ("dotted_name", "from t group by `a.b` ( count(*) as n ) order by `a.b`"),
    ("dotted_name_select", "from `s.t` select `a.b`, `x.y` as `p.q`"),
    ("digit_name", "from t group by `1st` ( count(*) as n ) order by -`1st`"),
    ("sql_join_using", "SELECT * FROM a JOIN b USING (id)"),
    (
        "sql_subquery_join",
        "SELECT * FROM a JOIN (SELECT id FROM b) AS s ON a.id = s.id",
    ),
    ("except", "from users except amount"),
    ("except_sql", "SELECT * EXCLUDE (amount) FROM users"),
    ("like", "from users where name like 'A%'"),
    ("ilike", "from users where name ilike 'a%'"),
    ("not_like", "from users where name not like 'A%'"),
    ("contains", "from users where name contains 'x'"),
    ("icontains", "from users where name icontains 'x'"),
    ("starts_with", "from users where name starts with 'J'"),
    ("ends_with", "from users where name ends with 'son'"),
    ("matches", "from users where name matches '^J.*'"),
    ("parens_or_and", "from t where (a = 1 or b = 2) and c = 3"),
    ("parens_and_or", "from t where a = 1 or (b = 2 and c = 3)"),
    ("parens_arith", "from t where (a + b) * 2 > c - 1"),
    ("extend", "from t extend amount * 2 as dbl"),
    ("extend_then_where", "from t extend amount * 2 as dbl where dbl > 10"),
    ("distinct", "from t select distinct a"),
    ("distinct_sql", "SELECT DISTINCT a FROM t"),
    ("distinct_star", "from t distinct"),
    # --- operators -----------------------------------------------------
    ("between", "from t where a between 1 and 5"),
    ("not_between", "from t where a not between 1 and 5"),
    ("in", "from t where a in (1, 2)"),
    ("in_strings", "from t where country in ('US', 'UK')"),
    ("not_in", "from t where a not in (1, 2)"),
    ("in_subquery", "from t where a in (from u select id)"),
    ("is_null", "from t where a is null"),
    ("is_not_null", "from t where a is not null"),
    ("eq_null", "from t where a == null and b != null"),
    ("not_expr", "from t where not a"),
    ("boolean_literals", "from t where active = true and deleted = false"),
    ("arithmetic", "from t where a + b * 2 > c - 1 and d / 2 >= 3 and e % 2 = 0"),
    ("concat", "from t select first || ' ' || last as full_name"),
    ("string_escapes", 'from t where a = "it\'s" and b = \'say "hi"\''),
    ("negative_number", "from t where a = -1 and b = -(c)"),
    ("ternary", "from orders select amount > 1000 ? 'high' : 'low' as tier"),
    (
        "when",
        "from users select when status is 'active' then 'A', is 'pending' then 'P', otherwise 'U' as lbl",
    ),
    ("coalesce_operator", "from users select name ?? 'Unknown' as display_name"),
    ("coalesce_function", "from users select coalesce(name, 'Unknown') as n"),
    ("cast", "from t select x::int as xi, cast(y as text) as yt"),
    ("date_literal", "from t where d >= @2024-01-01"),
    ("relative_date", "from t where created_at < 30 days ago"),
    ("date_arithmetic", "from t where d > created_at + 7 days"),
    ("function_nested", "from t select upper(trim(name)) as n, round(amount, 2) as r"),
    ("unaliased_function", "from t select upper(name)"),
    ("select_star_table", "from a & b on a.id = b.aid select a.*, b.z"),
    ("table_alias", "from users as u where u.x = 1"),
    ("join_aliases", "from users u & orders o on u.id = o.user_id"),
    # --- aggregation ---------------------------------------------------
    ("count_star", "from t group by a ( count(*) as n )"),
    ("count_hash", "from t group by a ( # as n )"),
    ("count_distinct", "from t group by a ( count(distinct b) as n )"),
    ("count_hash_distinct", "from t group by a ( #(distinct b) as n )"),
    ("count_table", "from orders group by status ( # users as c )"),
    ("agg_qualified", "from a & b on a.id = b.aid group by a.x, b.y ( sum(b.v) as s )"),
    (
        "agg_expression",
        "from t group by a ( sum(b * c) as s, max(d) - min(d) as spread )",
    ),
    ("month_group", "from t group by month(created_at) ( sum(amount) as total )"),
    (
        "month_group_alias",
        "from t group by month(created_at) as m ( sum(amount) as total )",
    ),
    ("week_group", "from t group by week(created_at) ( sum(amount) as total )"),
    (
        "year_group_multi",
        "from t group by year(created_at), region ( sum(amount) as total )",
    ),
    ("group_bare", "from t group by a, b"),
    ("having", "from t group by a ( sum(b) as s ) having s > 1"),
    ("having_count", "from t group by a ( # as n ) having # > 1"),
    ("group_then_where", "from t group by a ( sum(b) as s ) where s > 10"),
    (
        "group_then_where_order",
        "from t group by a ( sum(b) as s ) where s > 10 order by -s limit 5",
    ),
    ("stash_then_continue", "from t where a = 1 stash as act group by b ( # as n )"),
    ("stash_then_from", "from t where a = 1 stash as act\n\nfrom act select b"),
    (
        "stash_then_join",
        "from a where x = 1 stash as a1\n\nfrom b & a1 on b.id = a1.id",
    ),
    ("sql_cte", "WITH c AS (SELECT a FROM t WHERE a > 1) SELECT * FROM c"),
    ("sql_cte_join", "WITH c AS (SELECT a FROM t) SELECT * FROM u JOIN c ON u.a = c.a"),
    ("sql_cte_union", "WITH c AS (SELECT 1 AS a UNION SELECT 2 AS a) SELECT * FROM c"),
    ("group_sql_interleaved", "SELECT SUM(b) AS s, a FROM t GROUP BY a"),
    # --- joins ---------------------------------------------------------
    ("inner_join", "from a & b on a.id = b.a_id where b.x = 1"),
    ("left_join", "from a &? b on a.id = b.a_id"),
    ("right_join", "from a ?& b on a.id = b.a_id"),
    ("full_join", "from a ?&? b on a.id = b.a_id"),
    ("sql_joins", "SELECT * FROM a LEFT JOIN b ON a.id = b.a_id CROSS JOIN c"),
    ("join_and_condition", "from a & b on a.id = b.a_id and a.k = b.k"),
    ("explode", "from posts explode tags as tag select post_id, tag"),
    # --- ordering and paging -------------------------------------------
    ("order_limit_offset", "from t order by -a, b limit 10 offset 5"),
    ("order_sql_desc", "from t order by a DESC, b"),
    ("order_nulls", "from t order by a nulls last, b DESC NULLS FIRST"),
    ("order_expression", "from t order by -upper(name), lower(x)"),
    ("limit_only", "from t limit 10"),
    # --- misc stages ---------------------------------------------------
    ("sample_n", "from orders sample 100"),
    ("sample_pct", "from orders sample 10%"),
    ("sample_per", "from products sample 100 per category"),
    ("qualify", "from t qualify row_number() over (partition by a order by b) = 1"),
    ("per_first", "from events per user_id first by created_at"),
    (
        "window_select",
        "from t select a, sum(b) over (partition by a order by c) as running",
    ),
    ("union", "from a union from b"),
    ("union_all", "from a where x = 1 union all from b where y = 2"),
    ("replace", "from users replace name with upper(name)"),
    ("rename", "from users rename id as user_id, name as full_name"),
    (
        "column_ops_combined",
        "from customers except internal_id rename name as customer_name replace email with lower(email)",
    ),
    (
        "column_ops_reordered",
        "from users replace email with lower(email) rename name as customer_name",
    ),
    ("spine", "from orders spine by month(created_at) ( sum(amount) as s )"),
    (
        "pivot",
        'from orders pivot sum(amount) by status values ("pending", "shipped") group by customer_id',
    ),
    ("unpivot", "from quarterly_metrics unpivot q1, q2, q3, q4 into quarter, value"),
    ("multi_statement", "from a where x = 1;\nfrom b where y = 2"),
]

# The 42 playground examples (the audit found 19 changed meaning and 5 failed).
CASES += [
    (f"playground:{category}:{title}", query)
    for category, title, query in get_all_examples_flat()
]


def _cosmetic(node: exp.Expr) -> exp.Expr:
    if isinstance(node, exp.Paren):
        return node.this
    if (
        isinstance(node, exp.Not)
        and isinstance(node.this, exp.Is)
        and isinstance(node.this.expression, exp.Null)
    ):
        # NOT a IS NULL  ≡  a IS NOT NULL
        inner = node.this
        return exp.Is(this=inner.this, expression=exp.Null(), negate=True)
    if (
        isinstance(node, exp.Join)
        and not node.args.get("kind")
        and not (node.args.get("side"))
    ):
        node.set("kind", "INNER")  # JOIN  ≡  INNER JOIN
    return node


def _normalize(sql: str, dialect: str) -> exp.Expr:
    """Parse SQL and drop everything that carries no meaning."""
    tree = sqlglot.parse_one(sql, read=dialect)
    tree = tree.transform(_cosmetic)
    for node in tree.walk():
        node.comments = None
    return tree


def _visual(query: str) -> list[list[dict]]:
    return [
        json.loads(js)
        for js in sqlglot.transpile(query, read="asql", write="visual_asql")
    ]


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize(("name", "query"), CASES, ids=[c[0] for c in CASES])
def test_round_trip_preserves_meaning(name: str, query: str, dialect: str) -> None:
    pipelines_per_statement = _visual(query)

    try:
        expected = asql.transpile(query, write=dialect)
    except ASQLDialectError:
        # e.g. column operators without a schema on dialects lacking EXCLUDE:
        # the round trip must fail the same way, not silently succeed.
        assert len(pipelines_per_statement) == 1
        back = json_to_asql(pipelines_per_statement[0])
        with pytest.raises(ASQLDialectError):
            asql.transpile(back, write=dialect)
        return

    assert len(pipelines_per_statement) == len(expected)
    for pipelines, expected_sql in zip(pipelines_per_statement, expected, strict=True):
        if not pipelines:
            # an empty statement (a `;` followed only by comments)
            assert sqlglot.parse(expected_sql, read=dialect) in ([], [None])
            continue
        back = json_to_asql(pipelines)
        actual_sql = asql.transpile(back, write=dialect)[0]
        want = _normalize(expected_sql, dialect)
        got = _normalize(actual_sql, dialect)
        assert got == want, (
            f"\n--- original ASQL ---\n{query}"
            f"\n--- regenerated ASQL ---\n{back}"
            f"\n--- expected {dialect} ---\n{want.sql(dialect)}"
            f"\n--- got {dialect} ---\n{got.sql(dialect)}"
        )


@pytest.mark.parametrize(("name", "query"), CASES, ids=[c[0] for c in CASES])
def test_unsupported_nodes_are_explicit(name: str, query: str) -> None:
    """Anything the visual form can't model is a `raw` node holding ASQL text."""

    def walk(node: object) -> None:
        if isinstance(node, dict):
            assert node.get("type") != "unknown", node
            if node.get("type") == "raw":
                assert isinstance(node.get("asql"), str) and node["asql"].strip()
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for pipelines in _visual(query):
        walk(pipelines)
        for pipeline in pipelines:
            assert pipeline["from"].get("table") or pipeline["from"].get("raw"), (
                pipeline
            )
            assert "error" not in pipeline["from"], pipeline
