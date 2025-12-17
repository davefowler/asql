# Playground Settings

How ASQL style configuration is exposed in the playground.

---

## Overview

The playground lets users set their ASQL style preferences. When users click examples or paste SQL, the output ASQL is normalized to their preferred style.

**Flow:**
```
User clicks example (written in default style)
    ↓
normalize(example, user_config)
    ↓
Display in user's preferred style
```

This means examples are maintained in ONE canonical style, but displayed in whatever style the user prefers.

---

## Style Options Exposed

From `language-config.md`, these are the style options:

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `equality` | `single` / `double` | `single` | `=` vs `==` |
| `count` | `hash` / `function` | `hash` | `#` vs `count(*)` |
| `coalesce` | `operator` / `function` | `operator` | `??` vs `coalesce()` |
| `descending` | `prefix` / `suffix` | `prefix` | `-col` vs `col DESC` |
| `cast` | `double_colon` / `function` | `double_colon` | `::INT` vs `CAST(x AS INT)` |
| `quotes` | `double` / `single` | `double` | `"text"` vs `'text'` |
| `sort_keyword` | `order_by` / `sort` | `order_by` | `order by` vs `sort` |
| `week_start` | `monday` / `sunday` | `monday` | ISO vs US week start |
| `squash_empty_ctes` | `true` / `false` | `true` | Remove pass-through CTEs |
| `keep_final_empty_cte` | `true` / `false` | `false` | Keep final empty CTE (dbt style) |

**Notes**:
- The `limit` keyword is always `limit` (no `take` alternative)
- `squash_empty_ctes` removes CTEs that are just `SELECT * FROM table` with no transforms
- `keep_final_empty_cte` is useful for dbt users who like the `stash as X / from X` pattern at the end
- Non-empty CTEs (with WHERE, JOIN, etc.) are never squashed - only empty pass-throughs

---

## Implementation Status

✅ **IMPLEMENTED** in `playground.py`:

### Settings Panel UI

A collapsible settings panel is added above the editors with:

1. **Preset Buttons**: Quick presets (Default, SQL Compatible, Concise)
2. **Individual Options**: Dropdowns for each style option
3. **localStorage Persistence**: Settings are saved between sessions

### API Endpoint

`POST /api/normalize` - Normalizes ASQL to the configured style:

```python
@app.route('/api/normalize', methods=['POST'])
def api_normalize():
    data = request.get_json()
    asql_query = data.get('asql', '')
    style_config = data.get('style', {})
    
    # Build config and normalize
    style = StyleConfig(**style_config)
    config = ASQLConfig(style=style)
    
    sql = compile(asql_query, dialect='snowflake')
    normalized = reverse_compile(sql, config=config)
    
    return jsonify({'asql': normalized})
```

### JavaScript Functions

- `toggleSettings()` - Expand/collapse settings panel
- `applyPreset(presetName)` - Apply a preset
- `updateStyleConfig()` - Read values from UI and save to localStorage
- `normalizeASQL(asqlInput)` - Call API to normalize ASQL

---

## Presets

### Default
```javascript
{
    equality: 'single',      // =
    count: 'hash',           // #
    coalesce: 'operator',    // ??
    descending: 'prefix',    // -col
    cast: 'double_colon',    // ::
    quotes: 'double',        // "text"
    sort_keyword: 'order_by',// order by
    week_start: 'monday',
    squash_empty_ctes: true,      // remove pass-through CTEs
    keep_final_empty_cte: false,  // squash all empty CTEs
}
```

### SQL Compatible
```javascript
{
    equality: 'single',      // =
    count: 'function',       // count(*)
    coalesce: 'function',    // coalesce()
    descending: 'suffix',    // col DESC
    cast: 'function',        // CAST()
    quotes: 'single',        // 'text'
    sort_keyword: 'order_by',// order by
    week_start: 'monday',
    squash_empty_ctes: true,      // remove pass-through CTEs
    keep_final_empty_cte: false,  // squash all empty CTEs
}
```

### Concise
```javascript
{
    equality: 'single',      // =
    count: 'hash',           // #
    coalesce: 'operator',    // ??
    descending: 'prefix',    // -col
    cast: 'double_colon',    // ::
    quotes: 'double',        // "text"
    sort_keyword: 'sort',    // sort (shorter)
    week_start: 'monday',
    squash_empty_ctes: true,      // remove pass-through CTEs
    keep_final_empty_cte: false,  // squash all empty CTEs
}
```

---

## Example Workflow

1. User opens playground
2. Saved settings loaded from localStorage (or defaults)
3. User clicks "Top Sellers" example:
   ```asql
   from sales
   where status = "completed"
   group by region ( sum(amount) as revenue )
   order by -revenue
   limit 10
   ```
4. If user has SQL-compat preset, it's normalized:
   ```asql
   from sales
   where status = 'completed'
   group by region ( count(*) as orders )
   order by revenue desc
   limit 10
   ```
5. User can then modify and translate to SQL

---

## Files Modified

- `asql/config.py` - Config classes (ASQLConfig, StyleConfig)
- `asql/reverse_compiler.py` - Accept config, style-aware output
- `asql/__init__.py` - Export normalize(), ASQLConfig, StyleConfig
- `playground.py` - Settings panel UI, /api/normalize endpoint
