# ASQL: Future Features & Considerations

This document contains features that are planned for future implementation, under consideration, or marked as "maybe" for v1.0.

**Note**: Features in this document are NOT implemented. See `docs/spec.md` for the current specification of implemented features.

---

---


## Ternary-Style Conditionals (Future Consideration)

ASQL may add support for concise ternary expressions in the future:

**Tracking**: [#28](https://github.com/davefowler/asql/issues/28)

```asql
-- Potential future syntax (not yet decided)
amount == 0 ? null : amount           -- JS-style
null if amount == 0 else amount       -- Python-style
```

**Current**: Use ASQL `when` (or SQL `CASE WHEN ... THEN ... ELSE ... END`):
```asql
CASE WHEN amount == 0 THEN NULL ELSE amount END
```

**Priority**: Low - `when` syntax is already clear and readable. Ternary expressions are syntactic sugar.

---


## Shorthand Natural Language (50/50 on implementation)

For very simple exploratory queries, you can omit the `from` clause and infer it from the aggregation:

**Tracking**: [#40](https://github.com/davefowler/asql/issues/40)

```asql
# of Users by country
Sum of revenue by region
Avg Users.age by country
```

**Note**: This shorthand is nice for a big percentage of exploratory queries, but it's different from other queries that start with `from`. In these examples, the `from` table is inferred from its use in `# of Users`. It's really nice shorthand, but also potentially confusing.

**Status**: Marked as 50/50 on implementation - may or may not make it into v1.0.

**Pros**:
- Very concise for exploratory queries
- Natural language feel

**Cons**:
- Different syntax from other queries
- Potentially confusing
- Requires inference logic

---


## Future Considerations

These are broader ideas that may or may not be implemented:

- **Visual SQL Editor**: ASQL's structure could enable a great visual query builder whose base could also be a text editor/IDE. Get the best of visual and text-based exploration.
- **dbt Integration**: Building ASQL into dbt out of the gate would make it immediately useful for the dbt community
- **Common Schema Format**: A shared schema/statistics library for cross-database compatibility
- **Query Optimization**: ASQL-specific optimizations before SQL generation
- **IDE Integration**: Full-featured editor with autocomplete, error checking, SQL preview
- **Testing Framework**: Query testing and validation tools

---

## Safe casting (`::type?`) (Future Consideration)

ASQL may add “safe cast” syntax that returns `NULL` on cast failure.

### Why it exists
- Dialects differ (`TRY_CAST`, `SAFE_CAST`, etc.)
- Real data often contains non-castable values (`\"N/A\"`, empty strings, mixed types)

### Proposed syntax

```asql
select value::integer? as value_int
select value::integer? ?? 0 as value_int
```

### Current
Use strict casts (`value::integer`) and/or dialect-specific SQL (`TRY_CAST`, `SAFE_CAST`) directly.

---

## Safe divide (`/?`) (Future Consideration)

ASQL may add a safe divide operator where divide-by-zero yields `NULL` (i.e., the result is “not required”).

### Proposed syntax

```asql
4 /? 3     -- normal division
4 /? 0     -- NULL (safe-divide)
```

### Current
Use SQL `CASE` / `NULLIF` patterns directly, e.g. `a / NULLIF(b, 0)` (dialect dependent).

---

## Table sources: `series(...)` / `date_spine(...)` (Future Consideration)

ASQL may add table-producing functions that can be used directly in `from`:

```asql
from series(1, 100)
from date_spine(start = @2024-01-01, end = @2024-12-31, grain = day)
```

**Why it exists**: Sometimes you want to generate rows without an existing source table (numbers/date dimension).

**Current**: Prefer compiler `auto_spine` (gap-filling for grouped date dimensions) where applicable, or use warehouse-native generators in raw SQL.

---

## Union relations: `from union(t1, t2, ...)` (Future Consideration)

ASQL may add a convenience table source for unioning a list of relations:

```asql-play
from union(users_2022, users_2023, users_2024)
```

Open design questions:
- schema alignment vs “union all as-is”
- `fill_missing = null` behavior
- dialect differences

---

## `slugify(expr)` (Future Consideration)

ASQL may add a helper to convert strings to URL-friendly slugs:

**Tracking**: [#64](https://github.com/davefowler/asql/issues/64)

```asql
select slugify(name) as slug
```

Open design questions:
- dialect portability (regex replace differences)
- unicode normalization behavior

---

## Universal Auto-Aliasing for All Aggregates (Future Consideration)

ASQL may implement automatic column aliasing for all aggregate and transformation functions, enabling declarative continuity where the function call syntax matches the output column name.

**Tracking**: [#65](https://github.com/davefowler/asql/issues/65)

### Proposed Behavior

When any aggregate or transformation function is used without an explicit `as` alias, ASQL would automatically generate a column name following predictable patterns:

```asql
-- Current (requires explicit aliases)
from orders
  group by customer_id (
    sum(amount) as total_spent,
    first(order_id order by -order_date) as latest_order,
    # as order_count
  )

-- Future (auto-aliases)
from orders
  group by customer_id (
    sum(amount),                    -- → column: sum_amount
    first(order_id order by -order_date),  -- → column: first_order_id
    #                                -- → column: num (analytics-friendly)
    # orders                         -- → column: num_orders
  )
order by -sum_amount                -- Can reference auto-aliased column
```

### Benefits

- **Declarative continuity**: Write `sum_amount` and reference `sum_amount` - no mismatch
- **Less verbosity**: Fewer `as` clauses needed
- **Consistency**: All functions follow the same pattern
- **Shorthand integration**: Auto-aliases work seamlessly with underscore shorthand syntax

### Design Considerations

1. **Pattern**: `func(col)` → `func_col` for single-arg functions
2. **Multi-arg functions**: May require explicit aliases (e.g., `concat(col1, col2)`)
3. **Complex expressions**: Functions with expressions (e.g., `sum(amount * quantity)`) may require explicit aliases
4. **Backward compatibility**: Explicit `as` aliases would still work and override auto-aliases
5. **Shorthand support**: Functions that support shorthand (like `sum_amount`) already work - this extends the pattern

### Complete Mapping Table

See [Auto-Alias Mapping Table](../../ai_notes/auto-alias-mapping-table.md) for a comprehensive table of all function → auto-alias mappings and which functions support shorthand syntax.

### Current

Most aggregates require explicit `as` aliases. Shorthand forms like `sum_amount` already work and create columns with matching names.

---

## Date Aggregate Convention: Dropping `_at` Suffix (Future Consideration)

ASQL may add a convention where date aggregates on columns ending in `_at` can optionally drop the `_at` suffix for brevity.

### Proposed syntax

```asql
-- Current (always works)
month_created_at  -- → month(created_at)
year_updated_at   -- → year(updated_at)

-- Future (optional shorthand)
month_created     -- → month(created_at) (infers _at suffix)
year_updated      -- → year(updated_at) (infers _at suffix)
```

### Rationale

- **Convention-based**: Columns ending in `_at` are almost always timestamps
- **Brevity**: Shorter syntax for common patterns
- **Readability**: `month_created` reads naturally

### Open design questions

- Should this only work for columns ending in `_at`, or also `_date`, `_time`?
- What if both `created_at` and `created` exist? (prefer explicit)
- Should this be opt-in via config, or always available?
- Does this apply to all date functions (`year`, `month`, `day`, `date`, `date_trunc`, etc.)?

### Current

Use explicit column names: `month_created_at`, `year_updated_at`, etc.

---

## Function Naming Consistency: `running_num` vs `running_count` (Future Consideration)

ASQL may rename `running_count()` to `running_num()` for consistency with the `num` naming convention used for count auto-aliases.

**Current**: `running_count(*)` → column: `running_count` (or `running_num` if auto-aliased)

**Proposed**: `running_num(*)` → column: `running_num`

### Rationale

- **Consistency**: If `#` → `num` and `count(*)` → `num`, then `running_count(*)` should be `running_num(*)`
- **Analytics-friendly**: `num` is more analytics-friendly than `count` (see [Auto-Alias Mapping Table](../../ai_notes/auto-alias-mapping-table.md))
- **Declarative continuity**: `running_num` matches the auto-alias pattern `running_num`

### Current Behavior

```asql
-- Current syntax
from orders
  select running_count(*) as row_num
```

### Proposed Behavior

```asql
-- Future syntax
from orders
  select running_num(*) as row_num
  -- Or with auto-aliasing:
  select running_num(*)  -- → column: running_num
```

### Migration Considerations

- **Backward compatibility**: `running_count()` could remain as an alias for `running_num()`
- **Deprecation path**: Support both, document `running_count` as deprecated
- **Auto-aliasing**: If auto-aliasing is implemented, `running_count(*)` would auto-alias to `running_num` anyway

### Related Functions

This could also apply to:
- `running_count(*)` → `running_num(*)`
- Consider if `count()` function itself should have a `num()` alias (probably not, as `count()` is standard SQL)

**Status**: Under consideration - would improve consistency but requires breaking change or careful migration path.

---

## Preset Alias Templates (Future Consideration)

ASQL may provide preset alias templates as shortcuts for common naming conventions, allowing users to quickly apply standard styles without writing custom templates.

**Proposed syntax**:

```yaml
# asql.config.yaml
compile:
  alias_preset: "snake_case"  # or "camelCase", "UPPER_SNAKE", "PascalCase"
```

**Available presets** (proposed):

| Preset | Template | Example Output |
|--------|----------|----------------|
| `snake_case` | `{prefix}_{col}` | `sum_amount`, `num_orders` |
| `camelCase` | `{prefix|title}{col|title}` | `SumAmount`, `NumOrders` |
| `UPPER_SNAKE` | `{prefix|upper}_{col|upper}` | `SUM_AMOUNT`, `NUM_ORDERS` |
| `PascalCase` | `{prefix|title}{col|title}` | `SumAmount`, `NumOrders` |
| `lower_snake` | `{prefix|lower}_{col|lower}` | `sum_amount`, `num_orders` |

**Benefits**:
- Quick setup for common conventions
- Shareable styles across projects
- Less configuration needed for standard cases
- Can still override individual functions if needed

**Implementation**:
- Preset sets `alias_template` automatically
- Can be overridden by explicit `alias_template` setting
- Function-specific templates still take precedence

**Status**: Future consideration - nice-to-have convenience feature, not critical for initial implementation.

---

**See Also**:
- `docs/spec.md` - Current specification of implemented features
- GitHub issues - Work tracked as issues when prioritized
- `ai_notes/COHORT_ANALYSIS.md` - Detailed cohort analysis design
- `ai_notes/auto-alias-mapping-table.md` - Auto-aliasing patterns and rationale
