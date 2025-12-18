# Coming from X

If you’re coming to ASQL from another analytics tool, you shouldn’t have to “start over”.
ASQL is still SQL at heart, but many of its ergonomics were inspired by popular data tools and workflows.

In the guides below, you’ll see side-by-side translations and a quick-start style walkthrough that shows how to write ASQL the way you already think.

## What will feel familiar

Depending on where you’re coming from, you’ll likely recognize a bunch of patterns right away:

- **Pipelines / chaining**: write transformations top-to-bottom like `df.pipe(...)` / `%>%` / a dbt CTE stack.
- **Verbs and intent**: `where`, `select`, `group by`, `order by`, `limit` map closely to the mental model you already use.
- **Built-in “macro-like” helpers**: common dbt_utils-style patterns (pivot/unpivot, date spines, dedupe, surrogate keys) are first-class ASQL syntax/functions.
- **Warehouse-first execution**: like dbt/SQL, ASQL runs in your database (not in-memory like pandas), but keeps the readability of chained transforms.

Choose your background:

<div class="grid cards" markdown>

-   :fontawesome-brands-python: **[pandas](pandas.md)**

    ---

    If you're coming from pandas, ASQL will feel familiar - both use a pipeline/chaining approach.

-   :material-database: **[dbt](dbt.md)**

    ---

    ASQL integrates naturally with dbt. Think of ASQL as "what goes inside your dbt models."

-   :material-language-r: **[R / dplyr](r.md)**

    ---

    If you're coming from R's tidyverse, ASQL's pipeline approach will feel natural.

-   :material-database-search: **[SQL](sql.md)**

    ---

    If you're already comfortable with SQL, ASQL is SQL with better ergonomics.

</div>

---

## Quick Concept Mapping

| Concept | pandas | dplyr | dbt | SQL | ASQL |
|---------|--------|-------|-----|-----|------|
| Filter rows | `df[df.x > 0]` | `filter(x > 0)` | `WHERE x > 0` | `WHERE x > 0` | `where x > 0` |
| Select columns | `df[['a','b']]` | `select(a, b)` | `SELECT a, b` | `SELECT a, b` | `select a, b` |
| Add column | `df['c'] = ...` | `mutate(c = ...)` | `SELECT *, ... AS c` | `SELECT *, ... AS c` | `select *, ... as c` |
| Group & sum | `df.groupby().sum()` | `group_by() %>% summarize()` | `GROUP BY` | `GROUP BY` | `group by ... (...)` |
| Sort desc | `sort_values(ascending=False)` | `arrange(desc(x))` | `ORDER BY x DESC` | `ORDER BY x DESC` | `order by -x` |
| Null default | `fillna(0)` | `replace_na(0)` | `COALESCE(x, 0)` | `COALESCE(x, 0)` | `x ?? 0` |
| Dedupe | `drop_duplicates()` | `distinct()` | `{{ deduplicate() }}` | `ROW_NUMBER() + QUALIFY` | `per ... first by` |
| Left join | `merge(how='left')` | `left_join()` | `LEFT JOIN` | `LEFT JOIN` | `&?` |
| Pivot | `pivot_table()` | `pivot_wider()` | `{{ pivot() }}` | `PIVOT` | `pivot ... by` |
| Unpivot | `melt()` | `pivot_longer()` | `{{ unpivot() }}` | `UNPIVOT` | `unpivot ... into` |



