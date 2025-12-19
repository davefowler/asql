# Universal Auto-Aliasing with Configurable Templates (Phase 1 + Phase 2)

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

Additionally, SQL's default column naming is problematic:
- Generic names lose context (`count`, `sum`, `avg`)
- Inconsistent across dialects (PostgreSQL: `count`, `count_1`; MySQL: `COUNT(*)`; BigQuery: `f0_`)
- Requires quoted identifiers in many cases
- Creates conflicts with multiple similar functions

## Proposed Solution

Implement automatic column aliasing for all aggregates and transformation functions with configurable naming patterns. When a function is used without an explicit `as` alias, generate a column name following predictable, customizable patterns.

### Phase 1: Prefix-Based Configuration (Simple)

Start with prefix-based configuration for common functions:

```yaml
# asql.config.yaml
compile:
  # Common aggregates
  sum_alias_prefix: "sum"
  avg_alias_prefix: "avg"
  count_alias_prefix: "num"
  distinct_count_alias_prefix: "uniq"
  
  # Special templates for edge cases
  count_alias_template: "{prefix}"  # count(*) → "num"
```

**Behavior**:
```asql
from orders
  group by customer_id (
    sum(amount),                    -- → column: sum_amount
    count(*) as num,                -- → column: num (if count_alias_template set)
    count(distinct user_id)         -- → column: uniq_user_id (if distinct_count_alias_prefix: "uniq")
  )
order by -sum_amount                -- Can reference auto-aliased column
```

### Phase 2: Template System (Powerful)

Add Jinja2-based template system for advanced customization:

```yaml
# asql.config.yaml
compile:
  # Default template for all functions
  alias_template: "{prefix}_{col}"
  
  # Function-specific prefixes (override default)
  sum_alias_prefix: "sum"
  count_alias_prefix: "num"
  distinct_count_alias_prefix: "uniq"
  
  # Function-specific templates (override prefix + default template)
  count_alias_template: "{prefix}"  # count(*) → "num"
  distinct_count_alias_template: "{prefix}_{col}"  # count(distinct email) → "uniq_email"
  
  # Multi-arg function templates
  arg_max_alias_template: "{prefix}_{arg1}_{arg2}"
  arg_max_alias_prefix: "arg_max"
```

**Template Variables**:
- `{func}` - Actual SQL function name (`count`, `sum`, `year`)
- `{prefix}` - Configured prefix (or default if no custom prefix)
- `{col}` - Shorthand for `{arg1}` (single-arg functions only)
- `{arg1}`, `{arg2}`, etc. - Function arguments (always available)
- `{distinct}` - "distinct" if DISTINCT modifier used
- `{order_by}` - Order column if ORDER BY clause used
- `{partition_by}` - Partition column if PARTITION BY used

**Jinja Filters**: `|lower`, `|upper`, `|title`, `|camel`, `|snake`

**Examples**:
```yaml
# Uppercase convention
alias_template: "{prefix|upper}_{col|upper}"
# sum(amount) → "SUM_AMOUNT"

# CamelCase convention
alias_template: "{prefix|title}{col|title}"
# sum(amount) → "SumAmount"
```

### Pattern Rules

1. **Single-arg functions**: `func(col)` → `func_col` (or custom template)
   - `sum(amount)` → `sum_amount`
   - `avg(price)` → `avg_price`
   - `year(created_at)` → `year_created_at`

2. **Multi-arg functions**: `func(col1, col2)` → `func_col1_col2` (or custom template)
   - `arg_max(order_id, date)` → `arg_max_order_id_date`
   - Must use `{arg1}`, `{arg2}` in templates (cannot use `{col}`)

3. **Special cases**:
   - `count(*)` / `#` → `num` (analytics-friendly, not `count`)
   - `# orders` → `num_orders` (supports `num of orders` natural language)
   - `running_count(*)` → `running_num`
   - `row_number()` → `row_num`

4. **Shorthand integration**: Functions that support shorthand (like `sum_amount`) already work - this extends the pattern to all functions

### Precedence Rules

1. **Function-specific template** (e.g., `count_alias_template`) - highest priority
2. **Function-specific prefix** (e.g., `count_alias_prefix`) - uses default template with prefix
3. **Default template** - uses function's default prefix

### Benefits

- ✅ **Declarative continuity**: Write `sum_amount` and reference `sum_amount` - no mismatch
- ✅ **Less verbosity**: Fewer `as` clauses needed
- ✅ **Consistency**: All functions follow the same pattern
- ✅ **Configurable**: Prefix-based for simplicity, templates for power users
- ✅ **Shorthand integration**: Auto-aliases work seamlessly with underscore shorthand syntax
- ✅ **Prevents conflicts**: Unique names automatically (e.g., `num_email` vs `num_user_id` vs `num`)

### Design Considerations

1. **Backward compatibility**: Explicit `as` aliases still work and override auto-aliases
2. **Complex expressions**: Functions with expressions (e.g., `sum(amount * quantity)`) may require explicit aliases
3. **Multi-arg functions**: Require explicit `{arg1}`, `{arg2}` in templates
4. **Template parsing**: Use Jinja2 (familiar to dbt users, powerful, well-tested)
5. **Templates are fully specified**: No merging with defaults - complete pattern provided

### Complete Mapping

See `ai_notes/auto-alias-mapping-table.md` for comprehensive table of all function → auto-alias mappings.

See `ai_notes/configurable-auto-aliasing.md` for detailed design considerations, template system design, and implementation recommendations.

### Related Documentation

- `docs/spec_future.md` - Future features document
- `docs/concepts/shorthand.md` - Function shorthand documentation
- `ai_notes/auto-alias-mapping-table.md` - Complete mapping table
- `ai_notes/configurable-auto-aliasing.md` - Configuration system design
- `ai_notes/underscore-notation-edge-cases.md` - Edge cases and potential issues

### Implementation Notes

- Extends the existing shorthand system (which already works for `sum_amount`, `avg_price`, etc.)
- Phase 1: Prefix-based configuration (simple, covers 80% of use cases)
- Phase 2: Template system with Jinja2 (powerful, for advanced users)
- Consider edge cases: complex expressions, multiple arguments, nested functions, column name conflicts

### Testing Scenarios

- Single-arg functions with default template
- Single-arg functions with custom prefix
- Single-arg functions with custom template
- Multi-arg functions (must use `{arg1}`, `{arg2}`)
- Functions with modifiers (`DISTINCT`, `ORDER BY`, `PARTITION BY`)
- Column name conflicts (actual column vs function pattern)
- Re-aggregation scenarios
- Cascading aggregations

---

## PR / branch

- PR Title: "asql: implement universal auto-aliasing with configurable templates (#65)"
- Branch: "issue-65-auto-alias-templates"

## Close behavior

Use: Fixes #65
