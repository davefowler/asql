# Universal Auto-Aliasing for All Aggregates

## Problem

Currently, most ASQL aggregates and transformation functions require explicit `as` aliases:

```asql
from orders
  group by customer_id (
    sum(amount) as total_spent,
    first(order_id order by -order_date) as latest_order,
    # as order_count
  )
```

This is verbose and breaks declarative continuity - you can't write `sum_amount` and have it automatically create a column named `sum_amount` that you can reference later.

## Proposed Solution

Implement automatic column aliasing for all aggregates and transformation functions. When a function is used without an explicit `as` alias, generate a column name following predictable patterns.

### Behavior

```asql
-- Future: Auto-aliasing
from orders
  group by customer_id (
    sum(amount),                    -- → column: sum_amount
    first(order_id order by -order_date),  -- → column: first_order_id
    #                                -- → column: num (analytics-friendly)
    # orders                         -- → column: num_orders
  )
order by -sum_amount                -- Can reference auto-aliased column
```

### Pattern Rules

1. **Single-arg functions**: `func(col)` → `func_col`
   - `sum(amount)` → `sum_amount`
   - `avg(price)` → `avg_price`
   - `year(created_at)` → `year_created_at`

2. **Multi-arg functions**: `func(col1, col2)` → `func_col1_col2`
   - `arg_max(order_id, date)` → `arg_max_order_id_date`
   - May require explicit aliases for clarity

3. **Special cases**:
   - `count(*)` / `#` → `num` (analytics-friendly, not `count`)
   - `# orders` → `num_orders` (supports `num of orders` natural language)
   - `running_count(*)` → `running_num`
   - `row_number()` → `row_num`
   - `rank()` → `rank`

4. **Shorthand integration**: Functions that support shorthand (like `sum_amount`) already work - this extends the pattern to all functions

### Benefits

- ✅ **Declarative continuity**: Write `sum_amount` and reference `sum_amount` - no mismatch
- ✅ **Less verbosity**: Fewer `as` clauses needed
- ✅ **Consistency**: All functions follow the same pattern
- ✅ **Shorthand integration**: Auto-aliases work seamlessly with underscore shorthand syntax

### Design Considerations

1. **Backward compatibility**: Explicit `as` aliases would still work and override auto-aliases
2. **Complex expressions**: Functions with expressions (e.g., `sum(amount * quantity)`) may require explicit aliases
3. **Multi-arg functions**: May require explicit aliases for clarity
4. **Shorthand support**: Which functions can be called using their auto-alias as shorthand?

### Complete Mapping

See `ai_notes/auto-alias-mapping-table.md` for comprehensive table of all function → auto-alias mappings.

### Related Documentation

- `docs/spec_future.md` - Future features document
- `docs/concepts/shorthand.md` - Function shorthand documentation
- `ai_notes/auto-alias-mapping-table.md` - Complete mapping table

### Implementation Notes

- This would extend the existing shorthand system (which already works for `sum_amount`, `avg_price`, etc.)
- Need to determine which functions support shorthand syntax vs just auto-aliasing
- Consider edge cases: complex expressions, multiple arguments, nested functions
