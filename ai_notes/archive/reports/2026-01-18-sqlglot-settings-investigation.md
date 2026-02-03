# ASQL Settings: Complete Integration with SQLGlot

**Date**: 2026-01-18  
**Status**: IMPLEMENTED  
**Purpose**: Document ALL ASQL settings and how they integrate with SQLGlot's dialect system.

## Implementation Summary

The ASQL settings system has been migrated to use SQLGlot's native `dialect.settings` system:

1. **ASQL Dialect** (`asql/dialect/dialect.py`):
   - Declares all settings in `SUPPORTED_SETTINGS`
   - Stores defaults in `SETTING_DEFAULTS`
   - Settings passed to constructor are stored in `self.settings`

2. **ASQLParser** (`asql/dialect/parser.py`):
   - Reads settings from `self.dialect.settings`
   - Processes inline SET statements and mutates `self.dialect.settings`
   - SET statements are removed from output (they're ASQL config, not SQL)

3. **ASQLGenerator** (`asql/dialect/generator.py`):
   - Reads style settings from `self.dialect.settings`
   - Controls output format (count: hash/function, coalesce: operator/function, etc.)

4. **Compile API** (`asql/compiler/api.py`):
   - Thin wrapper around `sqlglot.transpile()`
   - Creates ASQL dialect with settings from CompileSettings
   - Passes `comments` parameter for passthrough_comments setting

5. **Deleted Files**:
   - `asql/compiler/inline_settings.py` - replaced by parser SET handling

## Key Discovery

SQLGlot's settings system is elegantly simple:

1. **Dialect has `settings` dict** - passed via constructor, stored as `self.settings`
2. **Parser/Generator get same dialect instance** - can read AND MUTATE `self.dialect.settings`
3. **Mutations persist** - inline SET statements can override settings mid-parse

This means ALL ASQL settings can flow through SQLGlot's native system.

---

## Complete Settings Reference

ASQL has **two categories** of settings:

| Category | Direction | Used By | Purpose |
|----------|-----------|---------|---------|
| **Compile Settings** | ASQL → SQL | Parser + Transforms | Control how ASQL compiles to SQL |
| **Style Settings** | SQL → ASQL | Generator | Control ASQL output style |

---

## Compile Settings (ASQL → SQL)

These settings affect how ASQL is parsed and transformed to SQL.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `extend_dialect` | str | None | SQL dialect that ASQL extends (e.g., "snowflake") |
| `schema` | Schema | None | Schema for FK inference, column operators |
| `auto_spine` | bool | True | Gap-filling for date GROUP BY |
| `week_start` | str | "monday" | Week start: "monday" or "sunday" |
| `relative_date_type` | str | "timestamp" | Relative dates: "timestamp" or "date" |
| `alias_template` | str | None | Default auto-alias template |
| `alias_prefixes` | dict | {} | Function-to-prefix mapping |
| `alias_templates` | dict | {} | Per-function alias templates |
| `infer_join_keys` | bool | False | Use {table}_id convention for joins |
| `include_transpilation_comments` | bool | True | Add /* ASQL: ... */ comments |
| `passthrough_comments` | bool | True | Preserve source comments |

### Inline SET Syntax (Compile)

```sql
SET extend_dialect = 'snowflake';
SET auto_spine = false;
SET week_start = 'sunday';
SET relative_date_type = 'date';
SET alias_template = '{func}_{col}';
SET count_alias_prefix = 'num';
SET sum_alias_prefix = 'total';
SET infer_join_keys = true;
SET include_transpilation_comments = false;
SET passthrough_comments = false;

from orders
group by week(created_at) (count(*), sum(amount))
```

---

## Style Settings (SQL → ASQL)

These settings affect how ASQL is generated when transpiling FROM SQL.

| Setting | Type | Default | Options | Description |
|---------|------|---------|---------|-------------|
| `equality` | str | "single" | "single", "double" | `=` vs `==` |
| `count` | str | "hash" | "hash", "function" | `#` vs `count(*)` |
| `coalesce` | str | "operator" | "operator", "function" | `??` vs `coalesce()` |
| `descending` | str | "prefix" | "prefix", "suffix" | `-col` vs `col DESC` |
| `cast` | str | "double_colon" | "double_colon", "function" | `::type` vs `CAST()` |
| `quotes` | str | "double" | "double", "single" | `"string"` vs `'string'` |
| `function_shorthand` | str | "underscore" | "underscore", "space", "parens" | `sum_amount` vs `sum amount` vs `sum(amount)` |
| `squash_empty_ctes` | bool | True | | Remove pass-through CTEs |
| `keep_final_empty_cte` | bool | False | | Keep final empty CTE (dbt pattern) |
| `ignore_aliases` | bool | False | | Strip explicit aliases |
| `week_start` | str | "monday" | "monday", "sunday" | Week start for output |

### Inline SET Syntax (Style)

```sql
SET equality = 'double';
SET count = 'function';
SET coalesce = 'function';
SET descending = 'suffix';
SET cast = 'function';
SET quotes = 'single';
SET function_shorthand = 'parens';
SET squash_empty_ctes = false;
SET ignore_aliases = true;
```

---

## SQLGlot Integration

### SUPPORTED_SETTINGS Declaration

```python
class ASQL(Dialect):
    SUPPORTED_SETTINGS = {
        *Dialect.SUPPORTED_SETTINGS,  # version, normalization_strategy
        
        # === Compile Settings (ASQL → SQL) ===
        "extend_dialect",           # SQL dialect that ASQL extends
        "schema",                   # Schema object (not SET-able)
        "auto_spine",               # Gap-filling for date GROUP BY
        "week_start",               # "monday" or "sunday"
        "relative_date_type",       # "timestamp" or "date"
        "alias_template",           # Default auto-alias template
        "alias_prefixes",           # {"count": "num", "sum": "total"}
        "alias_templates",          # Per-function templates
        "infer_join_keys",          # Use {table}_id convention
        "include_transpilation_comments",
        "passthrough_comments",
        
        # === Style Settings (SQL → ASQL) ===
        "equality",                 # "single" or "double"
        "count",                    # "hash" or "function"
        "coalesce",                 # "operator" or "function"
        "descending",               # "prefix" or "suffix"
        "cast",                     # "double_colon" or "function"
        "quotes",                   # "double" or "single"
        "function_shorthand",       # "underscore", "space", "parens"
        "squash_empty_ctes",
        "keep_final_empty_cte",
        "ignore_aliases",
    }
```

### Usage Examples

```python
import sqlglot
from asql.dialect import ASQL

# === ASQL → SQL (Compile) ===

# Default settings
sqlglot.transpile(query, read="asql", write="postgres")

# Custom compile settings
asql = ASQL(
    extend_dialect="snowflake",
    auto_spine=False,
    week_start="sunday",
    alias_prefixes={"count": "num", "sum": "total"},
)
sqlglot.transpile(query, read=asql, write="snowflake")


# === SQL → ASQL (Generate) ===

# Default style
sqlglot.transpile(sql, read="postgres", write="asql")

# Custom style settings
asql = ASQL(
    equality="double",
    count="function",
    function_shorthand="parens",
)
sqlglot.transpile(sql, read="postgres", write=asql)
```

---

## Inline SET Processing

The parser mutates `self.dialect.settings` when it encounters SET statements:

```python
class ASQLParser(Parser):
    def parse(self, raw_tokens, sql=None):
        statements = super().parse(raw_tokens, sql)
        
        result = []
        for stmt in statements:
            if isinstance(stmt, exp.Set):
                # Mutate dialect settings
                self._apply_set_to_dialect(stmt)
                # Don't include SET in output
            else:
                result.append(self._apply_asql_transforms(stmt))
        
        return result
    
    def _apply_set_to_dialect(self, set_stmt):
        """Mutate self.dialect.settings based on SET statement."""
        for item in set_stmt.expressions:
            key, value = self._extract_set_key_value(item)
            
            # Handle special cases
            if key == "dialect":
                key = "extend_dialect"
            elif key.endswith("_alias_prefix"):
                func = key[:-13]
                prefixes = self.dialect.settings.get("alias_prefixes", {})
                prefixes[func] = value
                self.dialect.settings["alias_prefixes"] = prefixes
                return
            elif key.endswith("_alias_template"):
                func = key[:-15]
                templates = self.dialect.settings.get("alias_templates", {})
                templates[func] = value
                self.dialect.settings["alias_templates"] = templates
                return
            
            # Standard setting
            if key in self.dialect.SUPPORTED_SETTINGS:
                self.dialect.settings[key] = value
```

---

## Settings Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. Dialect Constructor (lowest priority)                   │
│     asql = ASQL(auto_spine=False, equality="double")        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Inline SET Statements (highest priority)                │
│     SET auto_spine = true;                                  │
│     Parser mutates self.dialect.settings                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Transforms/Generator read from dialect.settings         │
│     auto_spine = self.dialect.settings.get('auto_spine')    │
└─────────────────────────────────────────────────────────────┘
```

---

## Playground UI Wiring

The playground sends settings via JSON, which maps directly to dialect settings:

```javascript
// Frontend
fetch('/api/compile', {
    body: JSON.stringify({
        asql: query,
        dialect: 'postgres',
        settings: {
            auto_spine: false,
            week_start: 'sunday',
            function_shorthand: 'parens'
        }
    })
})
```

```python
# Backend
@app.post("/api/compile")
async def api_compile(request: CompileRequest):
    asql = ASQL(
        extend_dialect=request.dialect,
        **request.settings  # All settings flow through!
    )
    result = sqlglot.transpile(request.asql, read=asql, write=request.dialect)
    return {"sql": result[0]}


@app.post("/api/reverse-compile")
async def api_reverse_compile(request: ReverseCompileRequest):
    asql = ASQL(**request.settings)  # Style settings
    result = sqlglot.transpile(request.sql, read=request.dialect, write=asql)
    return {"asql": result[0]}
```

---

## Implementation Checklist

### Parser Settings (Currently Implemented)

| Setting | In Parser? | In SUPPORTED_SETTINGS? | SET Support? |
|---------|------------|------------------------|--------------|
| `extend_dialect` | ✅ (as asql_target_dialect) | ❌ | ✅ (as dialect) |
| `schema` | ✅ | ❌ | N/A |
| `auto_spine` | ✅ | ❌ | ✅ |
| `week_start` | ✅ | ❌ | ✅ |
| `relative_date_type` | ✅ | ❌ | ✅ |
| `alias_template` | ✅ | ❌ | ✅ |
| `alias_prefixes` | ✅ | ❌ | ✅ |
| `alias_templates` | ✅ | ❌ | ✅ |
| `infer_join_keys` | ❌ | ❌ | ❌ |
| `include_transpilation_comments` | ❌ | ❌ | ✅ |
| `passthrough_comments` | ❌ | ❌ | ✅ |

### Generator Settings (Need to Add)

| Setting | In Generator? | In SUPPORTED_SETTINGS? | SET Support? |
|---------|---------------|------------------------|--------------|
| `equality` | ❌ | ❌ | ❌ |
| `count` | ❌ | ❌ | ❌ |
| `coalesce` | ❌ | ❌ | ❌ |
| `descending` | ❌ | ❌ | ❌ |
| `cast` | ❌ | ❌ | ❌ |
| `quotes` | ❌ | ❌ | ❌ |
| `function_shorthand` | ❌ | ❌ | ❌ |
| `squash_empty_ctes` | ❌ | ❌ | ❌ |
| `keep_final_empty_cte` | ❌ | ❌ | ❌ |
| `ignore_aliases` | ❌ | ❌ | ❌ |

---

## Migration Plan

1. **Add SUPPORTED_SETTINGS** to ASQL dialect with ALL settings

2. **Update ASQLParser**
   - Read settings from `self.dialect.settings` instead of `self.asql_*`
   - Process SET statements → mutate `self.dialect.settings`
   - Add missing settings: `infer_join_keys`, `include_transpilation_comments`, `passthrough_comments`

3. **Update ASQLGenerator**
   - Read style settings from `self.dialect.settings`
   - Add all StyleConfig settings to dialect

4. **Delete legacy code**
   - Remove `asql_*` kwargs handling
   - Remove `CompileSettings` / `StyleConfig` as separate classes (or keep for convenience, but dialect.settings is source of truth)
   - Remove `asql/compiler/inline_settings.py` (parser handles it)

5. **Update playground**
   - Pass all settings to dialect constructor
   - Same API, cleaner implementation

---

## Summary

**ALL settings** (compile + style) flow through SQLGlot's `dialect.settings`:

```python
# One unified API
asql = ASQL(
    # Compile settings
    extend_dialect="snowflake",
    auto_spine=False,
    week_start="sunday",
    
    # Style settings  
    equality="double",
    function_shorthand="parens",
)

# ASQL → SQL
sqlglot.transpile(asql_query, read=asql, write="snowflake")

# SQL → ASQL
sqlglot.transpile(sql_query, read="snowflake", write=asql)
```

**Inline SET** overrides any setting:

```sql
SET auto_spine = false;
SET function_shorthand = 'parens';
from orders group by region (sum_amount)
```

**No wrapper functions.** ASQL integrates as a proper SQLGlot dialect.
