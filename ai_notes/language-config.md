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
│  OUTPUT (Rendering)  │  CONFIGURABLE                       │
│  reverse_compile()   │  Output in configured style         │
│  normalize()         │                                     │
└──────────────────────┴──────────────────────────────────────┘
```

**Key insight**: Config affects HOW ASQL IS WRITTEN (output), not WHAT IS VALID (input).

ASQL will ALWAYS accept all valid syntaxes. Config only controls what the output looks like when:
- Converting SQL → ASQL (`reverse_compile`)
- Normalizing ASQL → ASQL (`normalize`)

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
style:
  count: hash           # override specific options
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
from asql import compile, reverse_compile, normalize
from asql.config import ASQLConfig, StyleConfig

# Use default config
sql = compile("from users where status = 'active' limit 10")

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
| Style affects output? | Yes - only affects `reverse_compile` and `normalize` |
| Style affects input? | No - input always accepts all valid syntaxes |
| Separate lint rules? | No - use `normalize --check` instead |
| Default equality? | `=` (single) |
| `limit` keyword? | Removed - use `limit` only |
| Array syntax? | Not needed if we drop lint rules |

**Design principle**: Keep it simple. Style = output format. No lint rules. To check style, run `normalize --check`.
