# ASQL + SQLMesh: Learning from Modern Data Transformation

## Summary

This document analyzes SQLMesh, a next-generation data transformation framework from Tobiko Data (the creators of SQLGlot). SQLMesh represents the state-of-the-art in data pipeline orchestration and brings software engineering best practices to analytics. For each key concept we examine:

1. **SQLMesh** - How it works in SQLMesh
2. **Relevance to ASQL** - What we can learn or already implement
3. **Potential Enhancement** - Ideas worth considering

**Key insight:** SQLMesh and ASQL share the same DNA—both are built on SQLGlot. SQLMesh focuses on orchestration and deployment, while ASQL focuses on query authoring. Understanding SQLMesh helps us identify complementary features and potential integration opportunities.

**Why SQLMesh matters:** It's the most sophisticated open-source alternative to dbt, built by engineers who deeply understand SQL parsing and optimization. Their architectural decisions reflect years of learning what works and what doesn't in data transformation.

---

## Core Design Principles

### 1. Semantic Understanding via SQL Parsing

#### SQLMesh
SQLMesh's superpower is that it **truly understands SQL**, not just as text but as structured queries. Using SQLGlot, it parses every model to extract:

```python
# What SQLMesh automatically detects from your SQL:
- Tables referenced (dependencies)
- Columns used and produced
- Column-level lineage (input → output mappings)
- Query semantics (is this a simple projection? a join? an aggregation?)
```

This enables features impossible with text-based tools:
- **Automatic dependency detection** - No need for `{{ ref('table') }}` calls
- **Column-level lineage** - Know exactly which downstream columns are affected by a change
- **Smart invalidation** - Only rebuild what actually changed
- **Semantic validation** - Catch errors at compile time, not runtime

```sql
-- SQLMesh automatically knows this model depends on raw_orders and customers
SELECT 
    o.order_id,
    c.customer_name,
    o.amount
FROM raw_orders o
JOIN customers c ON o.customer_id = c.id
```

#### ASQL Comparison ✅ Already Uses SQLGlot
ASQL also uses SQLGlot for transpilation:

```asql
from orders o
join customers c on o.customer_id = c.id
select o.order_id, c.customer_name, o.amount
```

The compiled SQL goes through SQLGlot, so we have access to the same parsing capabilities.

#### Gap: ASQL Doesn't Expose Semantic Metadata
Currently ASQL compiles ASQL→SQL but doesn't expose:
- What tables were referenced
- What columns are produced
- Column lineage information
- Dependency graph

#### Potential Enhancement (High Value!)
Extend the compiler to emit rich metadata alongside SQL:

```python
from asql import compile

result = compile("""
    from orders
    join customers on orders.customer_id = customers.id
    select customer_name, sum(amount) as total
    group by customer_name
""", return_metadata=True)

# result.sql = "SELECT customer_name, SUM(amount) AS total FROM orders JOIN..."
# result.metadata = {
#     "tables_referenced": ["orders", "customers"],
#     "columns_produced": ["customer_name", "total"],
#     "columns_used": {
#         "orders": ["customer_id", "amount"],
#         "customers": ["id", "customer_name"]
#     },
#     "column_lineage": {
#         "customer_name": ["customers.customer_name"],
#         "total": ["orders.amount"]  # derived from
#     },
#     "query_type": "aggregate",
#     "content_hash": "abc123def..."
# }
```

This metadata enables:
- **IDE features**: Go-to-definition, find-references for columns
- **Impact analysis**: "What breaks if I rename this column?"
- **Smart caching**: Only recompile when inputs change
- **Orchestrator integration**: Any tool can understand ASQL outputs

---

### 2. Virtual Data Environments (Zero-Copy Dev)

#### SQLMesh
**This is SQLMesh's killer feature.** Traditional development requires copying production data to a dev schema—expensive and slow.

SQLMesh creates virtual environments using **views**:

```
Production Tables (actual data)
        ↓
Dev Environment (views pointing to prod)
        ↓
Changed Model (only this is rebuilt as a table)
```

**How it works:**
1. In dev, all unchanged models are views pointing to production tables
2. Only models you've modified are materialized as new tables
3. Downstream models that didn't change still use views
4. Views resolve to a mix of prod tables and your new dev tables

**Benefits:**
- 💰 **Cost**: No data duplication for unchanged models
- ⚡ **Speed**: Instant environment creation (just create views)
- 🔄 **Iteration**: Quick feedback loop for changes
- 🔙 **Rollback**: Just drop the dev views

```bash
# Create a dev environment in seconds
sqlmesh plan dev

# SQLMesh shows exactly what will be rebuilt:
# - model_a: NEW (you changed it)
# - model_b: INDIRECT (depends on model_a, will be rebuilt)
# - model_c: UNCHANGED (view pointing to prod)
```

#### ASQL Consideration
This is an **orchestration feature**, not a query language feature. ASQL compiles queries; it doesn't manage environments.

However, ASQL can support environment-aware compilation:

#### Potential Enhancement (Medium Value)
Allow schema resolution based on environment:

```python
# ASQL compiler option
compile(query, environment="dev", schema_mapping={
    "orders": "dev_schema.orders_v2",  # Use dev version
    "customers": "prod_schema.customers"  # Use prod version
})
```

Or in ASQL syntax:
```asql
config:
  schema_prefix: ${ASQL_SCHEMA:-prod}

from orders  -- Resolves to prod.orders or dev.orders based on config
```

**Value:** Medium. Enables ASQL to work seamlessly with SQLMesh or custom virtual environments.

---

### 3. Plan/Apply Workflow (Terraform for Data)

#### SQLMesh
Before any changes are applied, SQLMesh shows you exactly what will happen:

```bash
$ sqlmesh plan

Models:
├── Added:
│   └── staging.new_model
├── Directly Modified:
│   └── marts.customer_summary (breaking change)
└── Indirectly Modified:
    └── marts.revenue_report (downstream of customer_summary)

Backfill required: 2024-01-01 to 2024-12-31

Apply plan? [y/n]
```

**Key concepts:**

| Change Type | Description | Impact |
|-------------|-------------|--------|
| **Added** | New model | No downstream impact |
| **Directly Modified** | You changed this model | May affect downstream |
| **Indirectly Modified** | Depends on something you changed | Will be rebuilt |
| **Breaking** | Schema changed (columns added/removed) | Forces rebuild of downstream |
| **Non-breaking** | Logic changed but schema same | May reuse downstream data |

SQLMesh is **smart about breaking vs. non-breaking changes**:
- Add a column? Non-breaking—downstream doesn't use it
- Remove a column? Breaking if used downstream
- Change aggregation logic? Non-breaking if output schema is same

#### ASQL Consideration
Again, this is orchestration. But ASQL can provide the metadata needed for smart change detection.

#### Potential Enhancement (High Value)
Emit content hashes and schema fingerprints:

```python
result = compile(query, return_metadata=True)

# result.metadata includes:
{
    "content_hash": "abc123",  # Hash of the ASQL source
    "sql_hash": "def456",      # Hash of compiled SQL
    "schema_fingerprint": "ghi789",  # Hash of output columns
    "output_schema": [
        {"name": "customer_id", "type": "INTEGER"},
        {"name": "total_orders", "type": "INTEGER"},
        {"name": "total_revenue", "type": "DECIMAL(10,2)"}
    ]
}
```

With this metadata, any orchestrator can implement smart change detection:
- `content_hash` changed but `sql_hash` same? Formatting only, skip rebuild
- `sql_hash` changed but `schema_fingerprint` same? Non-breaking, may reuse downstream
- `schema_fingerprint` changed? Breaking, must rebuild downstream

---

### 4. Incremental Processing with Smart Semantics

#### SQLMesh
SQLMesh has sophisticated incremental processing with multiple strategies:

```sql
MODEL (
    name db.events,
    kind INCREMENTAL_BY_TIME_RANGE (
        time_column event_time,
        batch_size 1,       -- Process 1 day at a time
        lookback 3          -- Re-process last 3 days for late data
    )
);

SELECT * FROM raw_events
WHERE event_time BETWEEN @start_date AND @end_date
```

**Incremental model kinds:**

| Kind | Use Case | Description |
|------|----------|-------------|
| `FULL` | Dimension tables | Rebuild entire table each run |
| `VIEW` | Light transforms | Materialize as view, not table |
| `INCREMENTAL_BY_TIME_RANGE` | Time-series data | Process date ranges incrementally |
| `INCREMENTAL_BY_UNIQUE_KEY` | CDC/upserts | Merge new/updated rows by key |
| `INCREMENTAL_BY_PARTITION` | Partitioned tables | Replace entire partitions |
| `SEED` | Static data | CSV files loaded as tables |
| `SCD_TYPE_2` | Slowly-changing dimensions | Track historical changes |

**Magic variables** available in models:
- `@start_date`, `@end_date` - Time range being processed
- `@execution_date` - When the run started
- `@this` - Reference to current table (for self-joins)

#### ASQL Comparison
ASQL has a planned `incremental` operator:

```asql
from source raw_events
  incremental by event_time
  select *
```

#### Gap: ASQL Missing Advanced Incremental Patterns

| SQLMesh Feature | ASQL Status | Notes |
|-----------------|-------------|-------|
| Time-range incremental | ⏳ Planned | `incremental by` |
| Lookback periods | ❌ Not planned | Late-arriving data |
| Unique-key incremental | ❌ Not planned | CDC/upsert patterns |
| SCD Type 2 | ❌ Not planned | Historical tracking |
| Batch sizing | ❌ Not planned | Control partition size |

#### Potential Enhancement (Medium Value)
Extended incremental syntax:

```asql
-- Time-range with lookback
from source raw_events
  incremental by event_time lookback 3 days
  select *

-- Unique-key incremental (upsert)
from source raw_orders
  incremental by order_id
  upsert on order_id
  select *

-- SCD Type 2
from source customers
  slowly_changing on customer_id
  track name, email, address
  select *
```

**Value:** Medium. Power users would love these, but they add complexity. Consider as future features.

---

### 5. Automatic Dependency Detection

#### SQLMesh
No `{{ ref() }}` needed! SQLMesh parses your SQL and automatically detects dependencies:

```sql
-- model: staging/orders.sql
-- SQLMesh automatically knows this depends on raw.orders
SELECT * FROM raw.orders WHERE is_valid = 1

-- model: marts/customer_orders.sql
-- SQLMesh automatically knows this depends on staging.orders and staging.customers
SELECT 
    c.customer_name,
    COUNT(*) as order_count
FROM staging.orders o
JOIN staging.customers c ON o.customer_id = c.id
GROUP BY c.customer_name
```

**Contrast with dbt:**
```sql
-- dbt requires explicit refs
SELECT 
    c.customer_name,
    COUNT(*) as order_count
FROM {{ ref('staging', 'orders') }} o
JOIN {{ ref('staging', 'customers') }} c ON o.customer_id = c.id
GROUP BY c.customer_name
```

SQLMesh's approach is:
- ✅ Less boilerplate
- ✅ Impossible to forget a ref
- ✅ Works with existing SQL (no templating)
- ✅ IDE-friendly (it's just SQL)

#### ASQL Comparison ✅ Already Natural
ASQL queries don't have `ref()` either—you just reference tables:

```asql
from orders o
join customers c on o.customer_id = c.id
select c.customer_name, count(*) as order_count
group by c.customer_name
```

#### Potential Enhancement
If ASQL emits dependency metadata (see Section 1), any orchestrator can build the DAG:

```python
result = compile(query, return_metadata=True)
# result.metadata.tables_referenced = ["orders", "customers"]
```

This makes ASQL a natural fit for SQLMesh or any orchestrator that uses automatic dependency detection.

---

### 6. Column-Level Lineage

#### SQLMesh
SQLMesh tracks which input columns flow to which output columns:

```sql
SELECT 
    customer_id,
    first_name || ' ' || last_name AS full_name,
    CASE WHEN total_orders > 100 THEN 'VIP' ELSE 'Regular' END AS tier
FROM customers
```

**Lineage:**
```
customer_id  ← customers.customer_id (direct)
full_name    ← customers.first_name + customers.last_name (derived)
tier         ← customers.total_orders (derived via logic)
```

**Why this matters:**
- **Impact analysis**: Change `first_name` → know `full_name` is affected downstream
- **Data governance**: Track sensitive columns through transformations
- **Debugging**: Trace where a value came from

```bash
# CLI to show column lineage
sqlmesh column lineage marts.customers.tier

# Shows:
# marts.customers.tier
#   └── staging.customers.total_orders
#       └── raw.orders.order_count
```

#### ASQL Gap
ASQL doesn't currently expose column lineage.

#### Potential Enhancement (High Value)
Since ASQL uses SQLGlot, we can tap into SQLGlot's lineage capabilities:

```python
from sqlglot.lineage import lineage
from asql import compile

asql_query = """
from customers
select 
  customer_id,
  first_name || ' ' || last_name as full_name,
  when total_orders > 100 then 'VIP' otherwise 'Regular' as tier
"""

sql = compile(asql_query)
lineage_graph = lineage(sql, dialect="duckdb")

# lineage_graph shows column-to-column mappings
```

**Implementation:** Medium effort. SQLGlot already has this capability; we just need to expose it through the ASQL compiler.

---

### 7. Testing Built Into the Workflow

#### SQLMesh
Testing is a first-class citizen, not an afterthought:

**Unit Tests (against sample data):**
```yaml
# tests/test_customer_orders.yaml
test_customer_summary:
  model: marts.customer_summary
  inputs:
    raw.customers:
      rows:
        - {id: 1, name: "Alice"}
        - {id: 2, name: "Bob"}
    raw.orders:
      rows:
        - {customer_id: 1, amount: 100}
        - {customer_id: 1, amount: 200}
  expected:
    rows:
      - {customer_name: "Alice", total: 300}
      # Bob has no orders, shouldn't appear
```

**Audits (against real data):**
```sql
-- audits/unique_customers.sql
AUDIT (
    name check_unique_customer_id,
    blocking true  -- Fail deployment if violated
);

SELECT customer_id, COUNT(*) as cnt
FROM @this
GROUP BY customer_id
HAVING COUNT(*) > 1
```

**Built-in audits:**
- `unique` - Column(s) must be unique
- `not_null` - Column(s) must not contain nulls
- `accepted_values` - Column must contain only specified values
- `relationship` - Foreign key must exist in parent table

#### ASQL Comparison ✅ Already Has Inline Assertions
ASQL supports inline assertions:

```asql
from orders
  assert id is not null
  assert amount >= 0
  select *
```

This is **better than SQLMesh** for simple checks because:
- Assertions are inline with the query
- No separate files to maintain
- Clear cause-and-effect

#### Gap: ASQL Missing Unit Tests
ASQL doesn't have a way to test queries against sample data.

#### Potential Enhancement (Medium Value)
Support for test mode with mock data:

```python
from asql import compile, test

# Define test inputs
test_inputs = {
    "customers": [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"}
    ],
    "orders": [
        {"customer_id": 1, "amount": 100},
        {"customer_id": 1, "amount": 200}
    ]
}

# Expected output
expected = [
    {"customer_name": "Alice", "total": 300}
]

query = """
from orders
join customers on orders.customer_id = customers.id
group by customers.name as customer_name (
  sum(orders.amount) as total
)
"""

# Run test
result = test(query, inputs=test_inputs, expected=expected)
assert result.passed
```

**Value:** Medium. Useful for library development but might be over-engineering for query authoring.

---

### 8. Python-Based Macros (Not Jinja)

#### SQLMesh
SQLMesh rejected Jinja in favor of Python macros:

```python
# macros/common.py
from sqlmesh import macro

@macro()
def add_audit_columns():
    return """
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    """

@macro()
def safe_divide(numerator, denominator):
    return f"CASE WHEN {denominator} = 0 THEN NULL ELSE {numerator} / {denominator} END"
```

**Usage in models:**
```sql
SELECT 
    revenue,
    costs,
    @safe_divide(revenue, costs) AS margin_ratio
FROM financials
```

**Why Python beats Jinja:**
- ✅ **Type safety**: Python catches errors; Jinja silently produces bad SQL
- ✅ **IDE support**: Autocomplete, type hints, refactoring tools
- ✅ **Testability**: Unit test macros with pytest
- ✅ **Debuggability**: Set breakpoints, inspect variables
- ✅ **No string soup**: Python generates structured output

**Contrast with dbt Jinja:**
```jinja
{% macro safe_divide(numerator, denominator) %}
  CASE WHEN {{ denominator }} = 0 THEN NULL ELSE {{ numerator }} / {{ denominator }} END
{% endmacro %}

-- Is this right? Who knows until you run it!
```

#### ASQL Comparison ✅ Already Better!
ASQL doesn't need most macros because common patterns are built-in operators:

| Pattern | dbt Jinja Macro | SQLMesh Macro | ASQL |
|---------|-----------------|---------------|------|
| Deduplication | ~15 lines | ~10 lines | `deduplicate by id keeping -date` |
| Pivot | ~30 lines | ~20 lines | `pivot col by category` |
| Window rank | ~10 lines | ~8 lines | `per group number by -col as rank` |
| Safe divide | macro | macro | Built into `??` or `when` |

#### Potential Enhancement (Low Value for Now)
If ASQL ever needs user-defined extensions, follow SQLMesh's lead:

```python
from asql import extension

@extension
def my_dedupe(table, key_cols):
    return f"""
        from {table}
        deduplicate by {', '.join(key_cols)} keeping -updated_at
    """
```

**Value:** Low for now. ASQL's operator approach is cleaner than macros.

---

### 9. Model Versioning and Instant Rollback

#### SQLMesh
Every model deployment creates a versioned table:

```
customers_v1  (version 1)
customers_v2  (version 2 - current)
customers     (view pointing to v2)
```

**Benefits:**
- **Instant rollback**: Just repoint the view to v1
- **A/B testing**: Compare v1 vs v2 outputs
- **Audit trail**: Keep historical versions
- **Zero-downtime deploys**: Swap views atomically

```bash
# Rollback to previous version
sqlmesh rollback --to-version 1

# Instantly swaps view to point to v1
# No data recomputation needed!
```

#### ASQL Consideration
This is deployment/orchestration. ASQL compiles queries; it doesn't manage table versions.

#### Potential Enhancement (Low Value)
ASQL could support version-aware table references:

```asql
-- Hypothetical: pin to specific version
from orders@v2
select *

-- Compare versions
from orders@v1 as old
join orders@v2 as new on old.id = new.id
where old.amount != new.amount
```

**Value:** Low. Version management belongs in orchestration, not query syntax.

---

### 10. Time-Travel-Aware Queries

#### SQLMesh
SQLMesh natively understands data versioning over time:

```sql
MODEL (
    name marts.daily_snapshot,
    kind SCD_TYPE_2 (
        unique_key [customer_id],
        valid_from_name valid_from,
        valid_to_name valid_to
    )
);

-- Automatically generates:
-- customer_id, ..., valid_from, valid_to, is_current
```

And supports querying at specific points in time:

```sql
-- What was the state on 2024-06-15?
SELECT * FROM marts.daily_snapshot
WHERE '2024-06-15' BETWEEN valid_from AND COALESCE(valid_to, '9999-12-31')
```

#### ASQL Consideration
SCD Type 2 is a common pattern in analytics.

#### Potential Enhancement (Medium Value)
Built-in SCD Type 2 support:

```asql
-- Create SCD Type 2 model
from source raw_customers
  slowly_changing by customer_id
  track name, email, tier
  select *

-- Compiles to:
-- Creates valid_from, valid_to, is_current columns
-- MERGE logic for updates

-- Query at point in time
from customers
  as_of @2024-06-15
  select *
```

**Value:** Medium. Common pattern but adds complexity. Consider for future.

---

## Summary: What ASQL Can Learn from SQLMesh

### ✅ Already Great in ASQL

| SQLMesh Feature | ASQL Equivalent |
|-----------------|-----------------|
| No `ref()` needed | Natural table references |
| Readable queries | Pipeline-first syntax |
| Inline testing | `assert` operator |
| Built-in patterns | `deduplicate`, `pivot`, `per` |
| Dialect support | SQLGlot transpilation |

### 🔶 High-Value Enhancements

| Concept | Potential Enhancement | Priority |
|---------|----------------------|----------|
| **Semantic metadata** | Emit tables_referenced, column_lineage with compiled SQL | **P1** |
| **Content hashing** | Hash ASQL source and compiled SQL for change detection | **P1** |
| **Schema fingerprints** | Hash output column names/types for breaking change detection | **P1** |
| **Column lineage** | Expose SQLGlot's lineage capabilities | **P2** |

### 🔷 Medium-Value Ideas

| Concept | Potential Enhancement | Priority |
|---------|----------------------|----------|
| Environment-aware compilation | Schema prefix/mapping based on environment | **P2** |
| Extended incremental modes | Lookback periods, unique-key upserts | **P3** |
| Unit test framework | Test queries against mock data | **P3** |
| SCD Type 2 support | `slowly_changing by key` operator | **P3** |

### ❌ Not Recommended for ASQL

| SQLMesh Feature | Why Skip |
|-----------------|----------|
| Virtual environments | Orchestration concern, not query language |
| Model versioning | Deployment concern, not query language |
| Scheduling | Orchestration concern |
| Python macros | ASQL operators already replace most macros |
| Plan/apply workflow | Belongs in orchestrator |

---

## The Big Picture: ASQL + SQLMesh = ❤️

ASQL and SQLMesh are **complementary**, not competitive:

```
┌─────────────────────────────────────────────────────────────┐
│                     Development Flow                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────┐      ┌─────────────┐      ┌─────────────┐     │
│   │  ASQL   │ ──→  │  SQLMesh    │ ──→  │  Warehouse  │     │
│   │ (Write) │      │(Orchestrate)│      │  (Execute)  │     │
│   └─────────┘      └─────────────┘      └─────────────┘     │
│        │                  ▲                                  │
│        │                  │                                  │
│        └──────────────────┘                                  │
│         Rich metadata enables                                │
│         smart orchestration                                  │
└─────────────────────────────────────────────────────────────┘
```

**ASQL's job:** Make queries easy to write and understand
**SQLMesh's job:** Make pipelines reliable and efficient

By emitting rich metadata, ASQL becomes an ideal **input language** for SQLMesh:

```python
# Hypothetical: SQLMesh with ASQL models
# models/customer_summary.asql

MODEL (
    name marts.customer_summary,
    kind INCREMENTAL_BY_TIME_RANGE (time_column order_date)
);

from orders o
join customers c on o.customer_id = c.id
where o.order_date between @start_date and @end_date
group by c.customer_name (
    sum(o.amount) as total_revenue,
    count(*) as order_count
)
```

SQLMesh would:
1. Parse the ASQL
2. Compile to SQL (via ASQL compiler)
3. Extract dependencies automatically
4. Apply virtual environments
5. Execute with smart incremental logic

**Best of both worlds:**
- ✅ ASQL's readable, concise syntax
- ✅ SQLMesh's smart orchestration
- ✅ No Jinja anywhere
- ✅ Fully type-safe pipeline

---

## Implementation Priority

Based on value and complexity:

| Priority | Feature | Effort | Value |
|----------|---------|--------|-------|
| **P1** | Emit `tables_referenced` in metadata | Low | High |
| **P1** | Emit `content_hash` and `sql_hash` | Low | High |
| **P1** | Emit `output_schema` fingerprint | Medium | High |
| **P2** | Column-level lineage via SQLGlot | Medium | High |
| **P2** | Environment-aware schema resolution | Medium | Medium |
| **P3** | Extended incremental modes | High | Medium |
| **P3** | Unit test framework | High | Medium |
| **Future** | SCD Type 2 support | High | Medium |

---

## Key Takeaway

**SQLMesh proves that SQL can be a first-class programming language** when you have deep semantic understanding. ASQL has the same foundation (SQLGlot) and can provide the same benefits.

The winning combination is:
1. **ASQL** for writing readable, maintainable queries
2. **Rich metadata** for integration with any orchestrator
3. **SQLMesh** (or dbt, or custom) for deployment and execution

Focus ASQL on being the **best query authoring experience**. Let orchestration tools handle everything else—but give them the metadata they need to be smart about it.

---

## References

- [SQLMesh Documentation](https://sqlmesh.readthedocs.io/)
- [SQLMesh GitHub](https://github.com/TobikoData/sqlmesh)
- [SQLGlot GitHub](https://github.com/tobymao/sqlglot)
- [SQLGlot Lineage](https://github.com/tobymao/sqlglot/blob/main/sqlglot/lineage.py)
- [Tobiko Data Blog](https://tobikodata.com/blog)
- [SQLMesh vs dbt Comparison](https://sqlmesh.readthedocs.io/en/stable/comparisons/dbt/)
- [ASQL Architecture](../../docs/architecture.md)
- [Previous ASQL SQLMesh Comparison](./SQLMESH_COMPARISON.md)

