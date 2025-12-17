# ASQL Language Configuration System

Design document for ASQL's configuration system.

---

## Philosophy: Should ASQL Even Have Config?

### The Spectrum of Configurability

| Tool | Philosophy | Config Level |
|------|------------|--------------|
| **Black** | "Uncompromising" - almost zero options | Minimal |
| **Prettier** | Opinionated - few options, strong defaults | Low |
| **Rustfmt** | Has options, but encourages defaults | Medium |
| **ESLint** | Highly configurable, rule-by-rule | High |

### Recommendation for ASQL

**ASQL should be Prettier-style: opinionated with limited, meaningful options.**

---

## Core Design Principle

```
┌─────────────────────────────────────────────────────────────┐
│  PARSING (Input)     │  ALWAYS PERMISSIVE                  │
│  compile()           │  Accept ALL valid ASQL syntaxes     │
├──────────────────────┼──────────────────────────────────────┤
│  STYLE (Output)      │  CONFIGURABLE                       │
│  reverse_compile()   │  Output in configured style         │
│  normalize()         │                                     │
├──────────────────────┼──────────────────────────────────────┤
│  COMPILE (Behavior)  │  CONFIGURABLE                       │
│  compile()           │  Settings affect generated SQL      │
└──────────────────────┴──────────────────────────────────────┘
```

**Key insight**: There are two types of configuration:

1. **Style settings** (`style:`): Affect HOW ASQL IS WRITTEN (output format)
   - Only affects `reverse_compile()` and `normalize()`
   - Example: `#` vs `count(*)`, `-col` vs `col DESC`

2. **Compile settings** (`compile:`): Affect HOW SQL IS GENERATED (behavior)
   - Affects `compile()` output
   - Example: `auto_spine` (gap-filling), `week_start`

ASQL will ALWAYS accept all valid syntaxes. Style config controls output format.
Compile config controls SQL generation behavior.

---

## Configuration File

### File Format: YAML Only

```
asql.config.yaml      # Standard location
.asqlrc.yaml          # Hidden file alternative
```

**Why just YAML?**
- One format = simpler tooling, simpler docs
- YAML is human-readable and supports comments
- Programmatic use (libraries) can pass config as dict/object directly

### Basic Structure

```yaml
# asql.config.yaml

# Preset: "default" | "sql-compat" | "concise"
preset: default

# Target SQL dialect for compile()
dialect: snowflake

# Override individual style options (optional)
# These affect OUTPUT style for reverse_compile() and normalize()
style:
  count: hash           # override specific options

# Compile settings (optional)
# These affect HOW queries are compiled to SQL
compile:
  auto_spine: false     # auto gap-fill date columns in GROUP BY
  week_start: monday    # monday | sunday
```

---

## Simplified Configuration (No Lint, Just Style)

ASQL is like Prettier:
1. Accept all valid syntax on input
2. Output in ONE configured style
3. To "lint", just run `normalize()` and diff

```bash
# "Lint" by checking if normalization changes anything
asql normalize --check query.asql
# Exit 1 if file would change, exit 0 if already normalized
```

This is exactly how `prettier --check` and `black --check` work.

---

## Presets

```yaml
preset: default      # or: sql-compat, concise
```

| Preset | Description | Key Choices |
|--------|-------------|-------------|
| `default` | Balanced ASQL style | `=`, `#`, `??`, `limit`, `-col` |
| `sql-compat` | Familiar to SQL users | `=`, `count(*)`, `coalesce()`, `limit`, `col DESC` |
| `concise` | Maximum brevity | `=`, `#`, `??`, `limit`, `-col`, `sort` keyword |

---

## Style Options

Each option controls OUTPUT style only. Input always accepts all variants.

```yaml
style:
  # Equality operator
  equality: single          # single (=) (default) | double (==)
  
  # Count notation  
  count: hash               # hash (#) (default) | function (count(*))
  
  # Null coalescing
  coalesce: operator        # operator (??) (default) | function (coalesce())
  
  # Descending order
  descending: prefix        # prefix (-col) (default) | suffix (col DESC)
  
  # Type casting
  cast: double_colon        # double_colon (::) (default) | function (CAST)
  
  # String quotes
  quotes: double            # double (") (default) | single (')
  
  # Sort keyword
  sort_keyword: order_by    # order_by (default) | sort
  
  # Week start (semantic, affects week() function)
  week_start: monday        # monday (default) | sunday
  
  # CTE handling - squash pass-through CTEs like "from table stash as name"
  squash_empty_ctes: true   # true (default) | false
  
  # Keep final empty CTE pattern (dbt style: stash as X followed by from X)
  # Only applies to empty CTEs - non-empty CTEs are never squashed
  keep_final_empty_cte: false  # false (default) | true
```

---

## Compile Settings

**Unlike style options, compile settings affect the GENERATED SQL, not just output formatting.**

```yaml
compile:
  # Auto-spine: automatically add gap-filling for date truncations in GROUP BY
  # When true, date columns will include all dates in the range (no gaps)
  auto_spine: false           # false (default) | true
  
  # Week start day: affects week() function output
  week_start: monday          # monday (default) | sunday
  
  # Relative date type: what "7 days ago" compiles to
  # timestamp -> CURRENT_TIMESTAMP - INTERVAL '7 days'
  # date -> CURRENT_DATE - INTERVAL '7 days'
  relative_date_type: timestamp   # timestamp (default) | date
```

### Inline SET Statements

Compile settings can also be set inline within a query using SQL `SET` statements:

```asql
SET auto_spine = true;
SET week_start = 'sunday';
SET dialect = 'postgres';

from orders
group by week(created_at) as w (sum(amount) as revenue)
```

**Priority order** (highest to lowest):
1. Inline `SET` statements in query
2. Settings passed to `compile()` function
3. Settings from config file
4. Default values

---

## Full Preset Definitions

### `default`
```yaml
style:
  equality: single          # status = "active"
  count: hash               # #
  coalesce: operator        # name ?? "Unknown"
  descending: prefix        # order by -amount
  cast: double_colon        # value::INT
  quotes: double            # "active"
  sort_keyword: order_by    # order by
  week_start: monday
  squash_empty_ctes: true        # remove "from x stash as x" pass-throughs
  keep_final_empty_cte: false    # squash all empty CTEs, including final
```

### `sql-compat`
```yaml
style:
  equality: single          # status = 'active'
  count: function           # count(*)
  coalesce: function        # coalesce(name, 'Unknown')
  descending: suffix        # order by amount DESC
  cast: function            # CAST(value AS INT)
  quotes: single            # 'active'
  sort_keyword: order_by    # order by
  week_start: monday
  squash_empty_ctes: true        # remove pass-throughs
  keep_final_empty_cte: false    # squash all empty CTEs
```

### `concise`
```yaml
style:
  equality: single          # status = "active"
  count: hash               # #
  coalesce: operator        # ??
  descending: prefix        # -amount
  cast: double_colon        # ::
  quotes: double            # "active"
  sort_keyword: sort        # sort (instead of order by)
  week_start: monday
  squash_empty_ctes: true        # remove pass-throughs
  keep_final_empty_cte: false    # squash all empty CTEs
```

---

## Implementation

See `asql/config.py` for the actual implementation.

### Using Config

```python
from asql import compile, reverse_compile, normalize, CompileSettings
from asql.config import ASQLConfig, StyleConfig

# Use default config
sql = compile("from users where status = 'active' limit 10")

# Compile with custom settings
settings = CompileSettings(auto_spine=True, week_start="sunday")
sql = compile("from orders group by week(date) (...)", settings=settings)

# Extract settings from a query
from asql import get_settings_from_query
settings, dialect = get_settings_from_query('''
    SET auto_spine = true;
    from orders ...
''')

# Reverse compile with config
config = ASQLConfig.from_preset("sql-compat")
asql = reverse_compile(sql, config=config)

# Normalize ASQL to a style
normalized = normalize(some_asql, config=config)
```

---

## CLI (Future)

```bash
# Compile ASQL to SQL (uses config if present)
asql compile query.asql

# Normalize ASQL to configured style
asql normalize query.asql

# Check if already normalized (for CI)
asql normalize --check query.asql

# Use specific preset
asql normalize --preset sql-compat query.asql

# Override dialect
asql compile --dialect bigquery query.asql
```

---

## Current Code Status

| Feature | Input (preparser) | Output (reverse_compiler) |
|---------|-------------------|---------------------------|
| Equality | Accepts `=` and `==`, converts `==` → `=` | Outputs `=` (configurable) |
| Count | Accepts `#` and `count(*)` | Outputs `#` (configurable) |
| Limit | Accepts `limit` only | Outputs `limit` |
| Coalesce | Accepts `??` and `coalesce()` | Outputs `??` (configurable) |
| Descending | Accepts `-col` and `col DESC` | Outputs `-col` (configurable) |
| Cast | Accepts `::` and `CAST()` | Outputs `::` (configurable) |
| Empty CTEs | N/A | Squashed by default (configurable) |

### CTE Squashing

When converting SQL with CTEs like:
```sql
WITH stats AS (SELECT * FROM stats),
     accounts AS (SELECT * FROM accounts WHERE active = true)
SELECT * FROM stats JOIN accounts ...
```

The `stats` CTE is "empty" - it's just `SELECT * FROM stats` with no transforms.
By default (`squash_empty_ctes: true`), this becomes:

```asql
from accounts
where active = true
stash as accounts

from stats
join accounts ...
```

The empty `stats` CTE is removed and references are inlined.

---

## Summary

| Question | Answer |
|----------|--------|
| Config file format? | YAML only (`asql.config.yaml`) |
| Config sections? | `style:` (output format), `compile:` (SQL generation behavior) |
| Style affects output? | Yes - only affects `reverse_compile` and `normalize` |
| Style affects input? | No - input always accepts all valid syntaxes |
| Compile affects SQL? | Yes - affects generated SQL (e.g., gap-filling, week start) |
| Inline config? | Yes - use `SET setting = value;` at top of query |
| Separate lint rules? | No - use `normalize --check` instead |
| Default equality? | `=` (single) |

**Design principle**: Keep it simple. 
- `style:` = output format for reverse_compile/normalize
- `compile:` = SQL generation behavior
- No lint rules. To check style, run `normalize --check`.
