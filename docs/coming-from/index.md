# Coming from X

This guide helps users coming from pandas, dbt, R/dplyr, or SQL translate their familiar patterns into ASQL.

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
