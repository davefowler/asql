# Metrics and Relationships (Semantic Layer)

ASQL can read a semantic graph: a `graph.yaml` file that declares your entities, models, relationships, and metrics once. Queries can then use metric names and `relationship.attribute` references directly, and ASQL compiles them to plain SQL for any dialect.

```asql
from transactions
where created_at >= @2026-01-01
group by buyer.country, month(created_at) ( volume, aov )
order by -volume
```

The file format is the one used by [dbt-metrics](https://github.com/fivetran/dbt-metrics). ASQL reads it on its own and does not depend on that project.

## Loading a graph

```python
import asql
from asql.schema import Schema
from asql.semantic import load_graph

schema = Schema.from_graph(load_graph("graph.yaml"))
sql = asql.transpile(
    "from transactions group by buyer.country ( volume )",
    write="snowflake",
    schema=schema,
)[0]
```

`Schema.from_graph` also feeds the graph's grains and relationships into [join inference](../syntax/joins.md) and [fanout protection](fanout.md). Joins you write yourself are protected without declaring any extra schema.

## The graph file

```yaml
config:
  dialect: duckdb          # dialect the expressions below are written in
entities:
  user:
    key:
      id: INT
  transaction:
    key:
      id: INT
models:
  user_profiles:
    grains:
      - user               # one row per user
    schema:
      user_id: INT
      country: TEXT
    relationships:
      user:
        key:
          id: user_id
        attributes:
          country: country
  transactions:
    grains:
      - transaction
    schema:
      transaction_id: INT
      buyer_id: INT
      amount: INT
      created_at: TIMESTAMP
    relationships:
      transaction:
        key:
          id: transaction_id
      buyer:
        entity: user       # defaults to the relationship name
        key:
          id: buyer_id
    metrics:
      volume: SUM(amount)
      transaction_count: COUNT(*)
      cn_volume: SUM(amount) FILTER (WHERE buyer.country = 'CN')
      aov: volume / transaction_count
```

| Key | Meaning |
|---|---|
| `entities.<name>.key` | The entity's typed key fields. |
| `models.<name>.schema` | The model's columns and types. The model name is the table name. |
| `models.<name>.grains` | The relationships whose keys make a row unique. Write a compound grain as one item, for example `user, as_of`. |
| `relationships.<name>.key` | A map from entity key fields to this model's columns, or a SQL predicate. |
| `relationships.<name>.attributes` | Dimensions this model exposes for the entity, as `name: expression` or `{expression, description}`. |
| `metrics.<name>` | An aggregate over the model's columns, or arithmetic over other metrics. |

When `config.dialect` is absent, expressions are parsed with sqlglot's base dialect. Unknown keys, dangling references, metric cycles and non-aggregate metrics are load errors.

## Using metrics

A bare metric name in a query whose `from` is a model expands to the metric's expression:

| ASQL | SQL |
|---|---|
| `group by status ( volume )` | `SUM(transactions.amount) AS volume` |
| `group by status ( aov )` | `SUM(transactions.amount) / COUNT(*) AS aov` |
| `group by status ( volume / 100 as v )` | `SUM(transactions.amount) / 100 AS v` |
| `select volume` | grand total, no `GROUP BY` |

- `order by -volume` sorts by the projected metric.
- A post-aggregation `where volume > 10` filters on it.
- A column of the `from` model always wins over a metric of the same name. A metric may not share a name with its own model's columns.
- An alias you define in the same block shadows a metric.

## Using relationship attributes

`relationship.attribute` adds a `LEFT JOIN` to the model whose grain is exactly the relationship's entity, and replaces the reference with the attribute's expression:

```asql
from transactions
group by buyer.country ( volume )
```

```sql
SELECT buyer.country AS buyer_country, SUM(transactions.amount) AS volume
FROM transactions
LEFT JOIN user_profiles AS buyer ON transactions.buyer_id = buyer.user_id
GROUP BY buyer.country
```

- The join is `LEFT`, so facts with no matching entity row still count toward totals.
- Two attributes through one relationship share one join.
- `buyer.country` and `seller.country` get one join each.
- Attributes work in `where`, in projections, and inside metric filters.
- A projected attribute is named `<relationship>_<attribute>` unless you alias it.

## Why the numbers are right

The target model's grain is exactly the joined entity, so every attribute join is many-to-one: it can never multiply rows of the `from` model. Every metric is computed in one grouped `SELECT` over those rows, so leaf aggregates are exact. Derived metrics are arithmetic over exact aggregates (parenthesized to keep precedence).

When ASQL can't prove that, it refuses instead of guessing. These raise `ASQLResolutionError`:

| Situation | Why |
|---|---|
| A relationship name is also a table alias in the query | `buyer.country` would be ambiguous. |
| An attribute isn't declared, or is declared on more than one model | No single join target. |
| A relationship that isn't part of the model's grain declares attributes (load error) | Only grain relationships describe the entity. |
| A join with no `on` matches several relationships (for example buyer and seller) | The join would be a guess. |
| An attribute lives only on a compound-grain model (for example SCD2, `user, as_of`) | The join may not be many-to-one; point-in-time joins aren't supported yet. |
| A relationship uses a predicate key | Only equality-map keys can be traversed. |
| A metric is defined on a different model than `from` | Cross-model metrics aren't supported yet; query from the metric's model. |
| A metric appears in a `where` before `group by` | It's an aggregate; filter after the block. |
| A metric is computed over a join you wrote that neither follows a declared many-to-one relationship nor gets rewritten by fanout protection (including any join without a `group by` or with fanout protection off) | The join could multiply the metric's rows. |
| An attribute is an aggregate or window, or names a column its model doesn't have (load error) | Attributes are row-level values of their model. |
| A metric declares `grain:` | Per-metric grain isn't supported yet. |
