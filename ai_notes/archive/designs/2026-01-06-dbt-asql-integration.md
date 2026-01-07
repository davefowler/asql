# dbt-asql Integration Plan

**Date**: January 6, 2026  
**Goal**: Enable ASQL in dbt models WITHOUT requiring `{% asql %}` wrappers

---

## Background

### How dbt-prql Works

PRQL's dbt integration requires wrapping PRQL code:

```sql
-- models/my_model.sql
{% prql %}
from employees
filter start_date > @2021-01-01
group department (aggregate {avg_salary = average salary})
{% endprql %}
```

**Problems with this approach**:
1. **Wrapper friction** — Every model needs `{% prql %}` tags
2. **File extension confusion** — It's a `.sql` file with non-SQL content
3. **IDE issues** — Syntax highlighting doesn't work properly
4. **Mixed mode** — Can't easily mix ASQL and SQL in same file

---

## Proposed Approaches

### Approach 1: File Extension Detection (Recommended)

**Concept**: Use `.asql` file extension. dbt-asql automatically compiles them.

**Usage**:
```asql
-- models/my_model.asql
from employees
  where start_date > @2021-01-01
  group by department ( avg(salary) as avg_salary )
```

**How it works**:
1. dbt-asql registers as a dbt adapter hook
2. On model load, check if file ends with `.asql`
3. If so, compile ASQL → SQL before dbt processes it
4. Pass the SQL to dbt's normal compilation pipeline

**Advantages**:
- ✅ No wrapper needed
- ✅ Clean `.asql` files
- ✅ IDE can provide ASQL syntax highlighting
- ✅ Clear separation: `.asql` = ASQL, `.sql` = SQL

**Disadvantages**:
- ⚠️ Requires dbt to recognize `.asql` extension
- ⚠️ May need adapter-level integration

**Implementation**:

```python
# dbt_asql/__init__.py
from dbt.plugins import register_model_parser

class AsqlModelParser:
    @staticmethod
    def is_applicable(path: str) -> bool:
        return path.endswith('.asql')
    
    @staticmethod
    def parse(raw_code: str, context: dict) -> str:
        from asql import compile
        # First pass Jinja, then compile ASQL
        jinja_processed = context.env.from_string(raw_code).render(context)
        return compile(jinja_processed)

register_model_parser(AsqlModelParser)
```

---

### Approach 2: Comment Directive

**Concept**: Use a magic comment at the top of `.sql` files.

**Usage**:
```sql
-- @asql
from employees
  where start_date > @2021-01-01
  group by department ( avg(salary) as avg_salary )
```

**How it works**:
1. dbt-asql hooks into dbt's model loading
2. Checks for `-- @asql` or `/* asql */` at file start
3. If present, compiles the rest as ASQL

**Advantages**:
- ✅ Works with existing `.sql` extension
- ✅ No dbt core changes needed
- ✅ Easy to add/remove

**Disadvantages**:
- ⚠️ Still requires a "marker"
- ⚠️ IDE sees `.sql` but content is ASQL

---

### Approach 3: Auto-Detection (Recommended as Fallback)

**Concept**: Automatically detect ASQL vs SQL based on syntax patterns.

**Why it works**: ASQL has many distinctive patterns that never appear in SQL:

| Pattern | ASQL | SQL |
|---------|------|-----|
| Starts with `from` (no SELECT) | ✅ | Very rare |
| Uses `&` or `&?` for joins | ✅ | ❌ Never |
| Uses `#` for count | ✅ | ❌ Never |
| Uses `@` for dates | ✅ | ❌ Never |
| Uses `-col` for descending | ✅ | ❌ Never |
| Uses `??` for coalesce | ✅ | ❌ Never |
| Uses `per ... first by` | ✅ | ❌ Never |
| Uses `group by ... ()` | ✅ | ❌ Never |
| Uses `stash as` | ✅ | ❌ Never |

**Detection algorithm**:
```python
def is_asql(code: str) -> bool:
    # Strong indicators (definitely ASQL)
    strong_patterns = [
        r'\b&\?\b',           # LEFT JOIN symbol
        r'\?\&\b',            # RIGHT JOIN symbol  
        r'\bstash\s+as\b',    # stash as
        r'\bper\s+\w+\s+first\b',  # per ... first
        r'group\s+by\s+.*\(', # group by ... (
        r'\?\?',              # coalesce
        r'#\s*\w+',           # # count shorthand
        r'@\d{4}-\d{2}-\d{2}', # date literal
    ]
    
    for pattern in strong_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            return True
    
    # Medium: File starts with "from" (not preceded by SELECT)
    first_word = get_first_keyword(code)
    if first_word.lower() == 'from':
        return True
    
    return False
```

**Recommended strategy: Both!**

1. **`.asql` files** — Always compiled as ASQL (explicit)
2. **`.sql` files** — Auto-detect using patterns above (convenient)

This gives users:
- Certainty when they want it (use `.asql`)
- Convenience when patterns are clear (`.sql` with ASQL syntax)

**Why auto-detection wasn't the ONLY approach**:
- Some edge cases exist (simple `from x where y` could be either)
- Explicit `.asql` extension is clearer for teams
- IDE tooling works better with explicit extensions
- But auto-detection is a great fallback!

**Advantages**:
- ✅ Works with existing `.sql` files
- ✅ No markers needed
- ✅ Graceful migration path

**Disadvantages**:
- ⚠️ Edge cases with very simple queries
- ⚠️ Debugging: "Why was this treated as ASQL/SQL?"

**Mitigation**: Log which detection method was used; provide explicit override.

---

## Jinja/Macro Compatibility

### The Challenge

dbt models use Jinja templating extensively:

```sql
{{ config(materialized='table') }}

SELECT * FROM {{ ref('users') }}
WHERE created_at > '{{ var("start_date") }}'
```

ASQL needs to handle these Jinja expressions.

### PRQL's Approach

PRQL's compiler passes through `{{ }}` expressions unchanged:

```prql
from {{ ref('users') }}
filter created_at > @{{ var('start_date') }}
```

The `{{ ref('users') }}` is preserved and dbt resolves it later.

### ASQL's Approach

ASQL should do the same: **pass through Jinja expressions**.

**Implementation**:
1. Detect `{{ ... }}` and `{% ... %}` patterns
2. Replace with placeholders before ASQL compilation
3. Restore after compilation

```python
def compile_with_jinja(asql_code: str) -> str:
    # Extract Jinja expressions
    placeholders = {}
    def replace_jinja(match):
        key = f"__JINJA_{len(placeholders)}__"
        placeholders[key] = match.group(0)
        return key
    
    cleaned = re.sub(r'\{\{.*?\}\}|\{%.*?%\}', replace_jinja, asql_code)
    
    # Compile ASQL
    sql = compile(cleaned)
    
    # Restore Jinja
    for key, value in placeholders.items():
        sql = sql.replace(key, value)
    
    return sql
```

### Common Patterns

| dbt Pattern | ASQL Usage | Output |
|-------------|------------|--------|
| `{{ ref('users') }}` | `from {{ ref('users') }}` | `FROM {{ ref('users') }}` |
| `{{ source('raw', 'events') }}` | `from {{ source('raw', 'events') }}` | `FROM {{ source('raw', 'events') }}` |
| `{{ var('date') }}` | `where date > @{{ var('date') }}` | `WHERE date > {{ var('date') }}` |
| `{{ config(...) }}` | At top of file, preserved | Preserved as-is |
| `{% if ... %}` | Wrap ASQL conditionally | Preserved as-is |

### Edge Cases

**Date literals with variables**:
```asql
where date > @{{ var('start_date') }}
```

This is tricky because `@` is ASQL's date prefix but the value comes from Jinja.

**Solution**: Compile `@{{ ... }}` to `CAST({{ ... }} AS DATE)` or similar:
```sql
WHERE date > CAST({{ var('start_date') }} AS DATE)
```

Or let the user handle it:
```asql
where date > {{ var('start_date') }}::DATE
```

---

## Do We Actually Need `ref()` and `var()`?

### What `ref()` Actually Does

`ref()` serves THREE purposes in dbt:

1. **Dependency Graph (DAG)** — dbt knows to run `stg_orders` before `fct_orders` because `fct_orders` uses `{{ ref('stg_orders') }}`

2. **Schema Resolution** — In dev, `ref('orders')` → `analytics_dev.orders`. In prod, → `analytics.orders`. The actual schema is injected at compile time.

3. **Cross-Project References** — `{{ ref('other_project', 'model') }}` enables referencing models from other dbt projects.

### Could We Avoid `ref()`?

**Yes!** Some tools do exactly this:

**SQLMesh** (open source, by Tobiko Data) parses SQL to infer dependencies automatically — no `ref()` needed. It inspects `FROM table_name` clauses to build the DAG.

> **Note**: We wouldn't depend on SQLMesh. SQLMesh just proves the concept works. ASQL already uses **SQLGlot** (the parser that SQLMesh also uses) — we'd reuse that for dependency detection.

**For dbt-asql, we'd use SQLGlot** (which ASQL already uses):
1. **Parse the compiled SQL** with SQLGlot to extract table names
2. **Match them to known models** (from the dbt manifest)
3. **Replace with `{{ ref() }}`** before dbt processes

```python
from sqlglot import parse, exp

def find_table_references(sql: str) -> set[str]:
    """Use SQLGlot to find all table references."""
    tables = set()
    for statement in parse(sql):
        for table in statement.find_all(exp.Table):
            tables.add(table.name)
    return tables

def resolve_model_refs(sql: str, dbt_manifest: dict) -> str:
    """Replace table names with {{ ref() }} if they're known models."""
    known_models = {m['name'] for m in dbt_manifest['nodes'].values()}
    tables = find_table_references(sql)
    
    for table in tables:
        if table in known_models:
            # Replace bare table name with ref()
            sql = re.sub(
                rf'\bFROM\s+{table}\b', 
                f"FROM {{{{ ref('{table}') }}}}", 
                sql, 
                flags=re.IGNORECASE
            )
    return sql
```

**No new dependencies** — SQLGlot is already in ASQL's stack.

**Advantages**:
- ✅ No `ref()` needed at all
- ✅ Just write `from orders` instead of `from {{ ref('orders') }}`
- ✅ Cleaner syntax

**Disadvantages**:
- ⚠️ Ambiguity: Is `orders` a model or a raw table?
- ⚠️ Cross-project refs need explicit syntax
- ⚠️ Schema resolution still needs a mechanism

### Proposed Hybrid: Smart Defaults with Optional Explicit

```asql
-- Option A: Implicit model reference (auto-detected)
from orders          -- dbt-asql checks: is "orders" a known model? If yes, treat as ref

-- Option B: Explicit model reference (when needed)
from @orders         -- @ means "this is definitely a model ref"

-- Option C: Explicit raw table (escape hatch)
from raw.orders      -- Qualified name = raw table, not a model
```

**Resolution order**:
1. If qualified (`schema.table`), use as-is (raw table)
2. If starts with `@`, it's definitely a model ref
3. If unqualified and matches a known model name, treat as ref
4. Otherwise, use as-is (raw table)

### What `var()` Actually Does

`var()` is simpler — it's just **external configuration injection**:

1. Values defined in `dbt_project.yml`
2. Values passed via CLI: `dbt run --vars '{"start_date": "2024-01-01"}'`
3. Default values if not specified

**We can't avoid needing variables** — external values must come from somewhere.

**But we can massively simplify the syntax**:

| dbt Jinja | dbt-asql | Savings |
|-----------|----------|---------|
| `{{ var('start_date') }}` | `{{ start_date }}` | Drop `var('...')` wrapper |
| `{{ var('limit', 1000) }}` | `{{ limit \|\| 1000 }}` | With default using `\|\|` |
| `{{ env_var('API_KEY') }}` | `{{ env.API_KEY }}` | Dot notation for env vars |

**Why `{{ start_date }}` instead of `$start_date`?**

1. **Familiar to dbt users** — They already know `{{ }}` means "inject something"
2. **Clear visual marker** — Easy to spot variables in queries
3. **Consistent** — Works the same way refs/sources used to
4. **Less learning** — Just drop `var('...')`, keep everything else

**Example**:
```asql
-- dbt + SQL (verbose)
SELECT * FROM {{ ref('orders') }}
WHERE created_at > '{{ var("start_date") }}'
LIMIT {{ var("row_limit", 100) }}

-- dbt-asql (clean)
from orders
  where created_at > {{ start_date }}
  limit {{ row_limit || 100 }}
```

**How it works under the hood**:

dbt-asql compiles `{{ start_date }}` → `{{ var('start_date') }}` before passing to dbt:

```python
def expand_variables(asql_code: str) -> str:
    """Convert simplified variable syntax to dbt var() calls."""
    
    def expand_var(match):
        content = match.group(1).strip()
        
        # Check for default value (using ||)
        if '||' in content:
            var_name, default = content.split('||', 1)
            return f"{{{{ var('{var_name.strip()}', {default.strip()}) }}}}"
        
        # Check for env var (env.VAR_NAME)
        if content.startswith('env.'):
            env_var = content[4:]
            return f"{{{{ env_var('{env_var}') }}}}"
        
        # Simple variable
        return f"{{{{ var('{content}') }}}}"
    
    return re.sub(r'\{\{\s*([^}]+)\s*\}\}', expand_var, asql_code)
```

**Complete variable syntax**:

| Pattern | Expands to | Use case |
|---------|------------|----------|
| `{{ x }}` | `{{ var('x') }}` | Simple variable |
| `{{ x \|\| default }}` | `{{ var('x', default) }}` | With default |
| `{{ env.API_KEY }}` | `{{ env_var('API_KEY') }}` | Environment variable |
| `{{ target.name }}` | `{{ target.name }}` | Target info (unchanged) |
| `{{ this }}` | `{{ this }}` | Self-reference (unchanged) |

### What `source()` Actually Does

`source()` references raw data sources (not dbt models):

1. Defined in `sources.yml`
2. Enables data freshness checks
3. Clear distinction from transformed models

**This is valuable** — raw sources ARE different from models.

**Proposed syntax**:
```asql
from source(raw, orders)   -- Keep explicit, it's semantically different
-- or
from @source:raw.orders    -- Prefixed syntax
```

### Summary: Recommended Approach

| Concept | dbt Jinja | dbt-asql | Improvement |
|---------|-----------|----------|-------------|
| Model ref | `{{ ref('orders') }}` | Just `orders` | Auto-detect from manifest |
| Source ref | `{{ source('raw', 'x') }}` | `source(raw, x)` | Drop quotes |
| Variable | `{{ var('start_date') }}` | `{{ start_date }}` | Drop `var('...')` |
| Variable w/ default | `{{ var('x', 100) }}` | `{{ x \|\| 100 }}` | Familiar `\|\|` syntax |
| Env variable | `{{ env_var('KEY') }}` | `{{ env.KEY }}` | Dot notation |
| Self-ref | `{{ this }}` | `{{ this }}` | Unchanged |
| Config | `{{ config(...) }}` | `SET key = val;` | Native syntax |

**Bottom line**: 
- `ref()` disappears entirely — just use table names
- `var()` becomes `{{ variable_name }}` — familiar but cleaner
- `source()` stays explicit but drops quotes
- Config becomes native `SET` statements

---

## Package Structure

```
dbt-asql/
├── dbt_asql/
│   ├── __init__.py       # Plugin registration
│   ├── parser.py         # ASQL model parser
│   ├── jinja_compat.py   # Jinja passthrough handling
│   └── macros/
│       └── asql.sql      # Optional macros
├── setup.py
├── pyproject.toml
└── README.md
```

---

## Installation & Setup

### User Installation

```bash
pip install dbt-asql
```

### dbt_project.yml

No changes needed if using Approach 1 (file extension).

For Approach 2/3, might need:
```yaml
# dbt_project.yml
plugins:
  - dbt-asql
```

---

## Feature Comparison

| Feature | dbt-prql | dbt-asql (proposed) |
|---------|----------|---------------------|
| File extension | `.sql` | `.asql` (preferred) or `.sql` |
| Wrapper required | `{% prql %}...{% endprql %}` | None |
| Jinja passthrough | ✅ `{{ }}` preserved | ✅ `{{ }}` preserved |
| `ref()` support | ✅ | ✅ |
| `source()` support | ✅ | ✅ |
| `var()` support | ✅ | ✅ |
| `config()` support | ✅ | ✅ |
| Mixed SQL/ASQL | Manual blocks | Auto-detect (Approach 3) |
| IDE support | Limited | Better with `.asql` extension |

---

## Implementation Phases

### Phase 1: Basic Integration
- [ ] Create dbt-asql package
- [ ] Implement `.asql` file extension detection
- [ ] Basic Jinja passthrough (`{{ }}` preservation)
- [ ] Test with simple models

### Phase 2: Full Jinja Support
- [ ] Handle `{% if %}` blocks
- [ ] Handle `{% for %}` loops
- [ ] Handle `{{ config() }}`
- [ ] Handle date literal + Jinja combinations

### Phase 3: Developer Experience
- [ ] VS Code extension updates for `.asql` in dbt projects
- [ ] Error messages showing ASQL line numbers
- [ ] dbt docs generation from ASQL models

### Phase 4: Advanced Features
- [ ] ASQL macros (reusable ASQL snippets)
- [ ] dbt test generation from ASQL schemas
- [ ] Performance: incremental compilation

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| dbt doesn't support custom file extensions | Use Approach 2 (comment directive) as fallback |
| Jinja edge cases break compilation | Comprehensive test suite; graceful error handling |
| IDE confusion with `.asql` files | Provide VS Code extension; document setup |
| Performance overhead | Cache compiled SQL; only recompile on change |

---

## Example: Full dbt Model

### Before: dbt + SQL

```sql
-- models/revenue_by_region.sql (traditional dbt)
{{ config(materialized='incremental', unique_key='region') }}

WITH orders_filtered AS (
  SELECT *
  FROM {{ ref('stg_orders') }}
  WHERE status = 'completed'
    AND created_at > '{{ var("start_date", "2024-01-01") }}'
    {% if is_incremental() %}
      AND created_at > (SELECT MAX(created_at) FROM {{ this }})
    {% endif %}
)
SELECT
  region,
  DATE_TRUNC('month', created_at) AS month,
  SUM(amount) AS revenue,
  COUNT(*) AS order_count
FROM orders_filtered
GROUP BY region, DATE_TRUNC('month', created_at)
ORDER BY revenue DESC
LIMIT {{ var("row_limit", 1000) }}
```

**Line count**: 21 lines  
**Jinja symbols**: 7 `{{` + 1 `{%`

---

### After: dbt-asql (Proposed)

```asql
-- models/revenue_by_region.asql
SET materialized = incremental;
SET unique_key = region;

from stg_orders
  where status = 'completed'
  where created_at > {{ start_date || @2024-01-01 }}
  {% if is_incremental() %}
    where created_at > (select max(created_at) from {{ this }})
  {% endif %}
  group by region, month(created_at) (
    sum(amount) as revenue,
    # as order_count
  )
  order by -revenue
  limit {{ row_limit || 1000 }}
```

**Line count**: 15 lines (29% reduction)  
**Jinja symbols**: 3 `{{` + 1 `{%` (50% reduction)  
**No `ref()` needed**: `stg_orders` auto-detected from manifest  
**No `var()` needed**: `{{ start_date }}` expands automatically

---

### Compiled SQL (what dbt sees)

```sql
{{ config(materialized='incremental', unique_key='region') }}

WITH _asql_cte_1 AS (
  SELECT * FROM {{ ref('stg_orders') }}
  WHERE status = 'completed'
    AND created_at > {{ var('start_date', '2024-01-01') }}
    {% if is_incremental() %}
      AND created_at > (SELECT MAX(created_at) FROM {{ this }})
    {% endif %}
)
SELECT 
  region,
  DATE_TRUNC('month', created_at) AS month_created_at,
  SUM(amount) AS revenue,
  COUNT(*) AS order_count
FROM _asql_cte_1
GROUP BY region, DATE_TRUNC('month', created_at)
ORDER BY revenue DESC
LIMIT {{ var('row_limit', 1000) }}
```

dbt-asql expands:
- `stg_orders` → `{{ ref('stg_orders') }}` (auto-detected model)
- `{{ start_date || @2024-01-01 }}` → `{{ var('start_date', '2024-01-01') }}`
- `{{ row_limit || 1000 }}` → `{{ var('row_limit', 1000) }}`
- `SET materialized = ...` → `{{ config(materialized='...') }}`

---

## Conclusion

**Recommended approach**: File extension detection (`.asql` files).

This provides the cleanest user experience:
- No wrappers needed
- Clear file distinction
- Better IDE support
- Straightforward implementation

The key implementation challenge is Jinja passthrough, which PRQL has already solved. We can follow their pattern.

---

## Brainstorm: Native Syntax for dbt Configs

> **Note**: This is exploratory. `SET` statements work fine, but here's how configs might feel more "ASQL-native."

### All dbt Config Options

| Config | Purpose | Common Values |
|--------|---------|---------------|
| `materialized` | How to store | `table`, `view`, `incremental`, `ephemeral` |
| `unique_key` | Dedup key for incremental | Column name(s) |
| `schema` | Target schema | `staging`, `marts` |
| `alias` | Override table name | Any string |
| `database` | Target database | Database name |
| `tags` | Metadata labels | `['daily', 'core']` |
| `enabled` | Enable/disable model | `true`, `false` |
| `pre_hook` | SQL before model | SQL string |
| `post_hook` | SQL after model | SQL string |
| `cluster_by` | Clustering (Snowflake/BQ) | Column list |
| `partition_by` | Partitioning (BQ) | Column or expression |
| `on_schema_change` | Schema drift handling | `ignore`, `fail`, `sync` |
| `incremental_strategy` | How to merge | `merge`, `delete+insert`, `append` |
| `grants` | Permissions | User/role grants |

### Option A: `SET` Statements (Current Proposal)

```asql
SET materialized = incremental;
SET unique_key = id;
SET schema = marts;
SET tags = [daily, core];

from orders ...
```

**Pros**: Familiar SQL-ish  
**Cons**: Feels like database commands, verbose

---

### Option B: Shebang-Style Header

```asql
#! materialized=incremental unique_key=id schema=marts

from orders ...
```

**Pros**: Compact, clearly metadata  
**Cons**: Unfamiliar syntax, cramped

---

### Option C: YAML-like Header Block

```asql
---
materialized: incremental
unique_key: id
schema: marts
tags: [daily, core]
---

from orders ...
```

**Pros**: Clean separation, readable  
**Cons**: Mixes paradigms (YAML + ASQL)

---

### Option D: Native Keywords Woven Into Syntax

What if some configs became **natural parts of ASQL**?

```asql
-- Materialization as output keyword
from orders
  where status = 'completed'
  group by region ( sum(amount) as revenue )
  save as table marts.revenue_by_region  -- "save as table/view/incremental"

-- Or at the start
create incremental table marts.revenue (unique key = id) as
from orders ...

-- Or as a trailing clause
from orders
  ...
  materialize as incremental table revenue
    unique key = id
    partition by created_at
```

**Interesting options**:

| Concept | Native ASQL Syntax Idea |
|---------|------------------------|
| `materialized = table` | `save as table` or `create table ... as` |
| `materialized = view` | `save as view` or `create view ... as` |
| `materialized = incremental` | `save as incremental` + `unique key = ...` |
| `schema = marts` | Just use qualified name: `marts.revenue` |
| `alias = orders_v2` | `save as orders_v2` |
| `partition_by` | `partition by created_at` clause |
| `cluster_by` | `cluster by region, date` clause |

---

### Option E: Trailing Config Block

```asql
from orders
  where status = 'completed'
  group by region ( sum(amount) as revenue )

config
  materialized: incremental
  unique_key: id
  partition_by: created_at
```

**Pros**: Clearly separate from query logic  
**Cons**: Feels like an afterthought

---

### Option F: Inline Annotations

```asql
from orders @incremental(unique_key=id)
  where status = 'completed'
  group by region ( sum(amount) as revenue )
  @partition(created_at)
  @cluster(region)
```

**Pros**: Attached to relevant parts  
**Cons**: Noisy, scattered

---

### Recommendation

**Keep `SET` for now** but consider **Option D** (native keywords) for the most common configs:

```asql
-- Phase 1: SET statements (works today)
SET materialized = incremental;
SET unique_key = id;

from orders ...

-- Phase 2 (future): Native syntax for common cases
from orders
  ...
  save as incremental table revenue
    unique key = id
```

The query itself naturally expresses:
- **What data** (from, where, group)
- **What output** (save as table/view/incremental)
- **Where** (schema.table_name)
- **How** (unique key, partition by, cluster by)

This keeps metadata close to the query instead of in a separate header.

---

## Related Documents

- **[Native dbt Syntax Investigation](2026-01-06-dbt-native-syntax.md)** — Explores how to replace Jinja `{{ }}` and `{% %}` with native ASQL syntax for configs, refs, sources, variables, and conditionals.

---

## Next Steps

1. Review this proposal
2. Decide on approach (file extension vs comment directive vs auto-detection)
3. Prototype basic integration with file extension detection
4. Add auto-detection as fallback for `.sql` files
5. Implement syntax expansions:
   - Model names → `{{ ref('name') }}` (from manifest)
   - `{{ var_name }}` → `{{ var('var_name') }}`
   - `{{ var || default }}` → `{{ var('var', default) }}`
   - `{{ env.NAME }}` → `{{ env_var('NAME') }}`
   - `SET key = val;` → `{{ config(key='val') }}`
6. Test with real dbt projects
7. Publish to PyPI

