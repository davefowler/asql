# Configurable Auto-Aliasing: Design & Implementation Considerations

**Status**: Research document exploring configuration options for ASQL's auto-aliasing system.

**Related**: 
- `auto-alias-mapping-table.md` - Current auto-aliasing patterns
- `underscore-notation-edge-cases.md` - Edge cases and potential issues

---

## Overview

ASQL's auto-aliasing system generates column names automatically when functions are used without explicit `as` aliases. This document explores how to make this system fully configurable, allowing users to customize naming patterns for all functions.

---

## Current State

Currently, only count-related functions have proposed configuration:

```yaml
# asql.config.yaml
compile:
  count_alias: "num"              # Default: "num"
  distinct_count_alias: "num_distinct"  # Default: "num_distinct"
```

**Limitation**: Only two settings for count functions. What about `sum()`, `avg()`, `year()`, etc.?

---

## Problem: Configuration for All Functions

### Current Pattern

Each function follows a pattern:
- `sum(amount)` → `sum_amount`
- `avg(price)` → `avg_price`
- `year(created_at)` → `year_created_at`
- `count(*)` → `num`
- `count(distinct email)` → `num_distinct_email`

### Questions

1. **Should every function have its own setting?**
   ```yaml
   compile:
     sum_alias_prefix: "sum"
     avg_alias_prefix: "avg"
     year_alias_prefix: "year"
     count_alias_prefix: "num"
     # ... 50+ more functions?
   ```
   **Problem**: Too many settings, hard to maintain

2. **Should we use templates?**
   ```yaml
   compile:
     alias_template: "{func}_{col}"
     count_alias_template: "{alias}"  # Special case
   ```
   **Problem**: How do we handle special cases?

3. **Should we use prefixes + templates?**
   ```yaml
   compile:
     alias_template: "{prefix}_{col}"
     sum_alias_prefix: "sum"
     count_alias_prefix: "num"
   ```
   **Problem**: Still need many prefix settings

---

## Approach 1: Per-Function Prefix Settings

### Configuration

```yaml
# asql.config.yaml
compile:
  # Aggregate functions
  sum_alias_prefix: "sum"
  avg_alias_prefix: "avg"
  min_alias_prefix: "min"
  max_alias_prefix: "max"
  count_alias_prefix: "num"
  distinct_count_alias_prefix: "num_distinct"  # or "uniq"
  
  # Date functions
  year_alias_prefix: "year"
  month_alias_prefix: "month"
  week_alias_prefix: "week"
  day_alias_prefix: "day"
  
  # Window functions
  running_sum_alias_prefix: "running_sum"
  running_avg_alias_prefix: "running_avg"
  running_count_alias_prefix: "running_num"
  prior_alias_prefix: "prior"
  next_alias_prefix: "next"
  
  # String functions
  upper_alias_prefix: "upper"
  lower_alias_prefix: "lower"
  length_alias_prefix: "length"
  
  # ... and so on for all functions
```

### Pros
- ✅ Explicit and clear
- ✅ Easy to understand
- ✅ Can override individual functions

### Cons
- ❌ **Too many settings** (50+ functions)
- ❌ Hard to maintain
- ❌ Verbose config file
- ❌ Easy to miss a function

---

## Approach 2: Template-Based Configuration

### Basic Template

```yaml
# asql.config.yaml
compile:
  # Default template for all functions
  alias_template: "{func}_{col}"
  
  # Special cases override template
  count_alias_template: "{prefix}"  # count(*) → "num" (no column)
  distinct_count_alias_template: "{prefix}_distinct_{col}"  # count(distinct email) → "num_distinct_email"
```

**Note**: `{prefix}` refers to the configured prefix for the function (e.g., `count_alias_prefix: "num"`), or the function name itself if no prefix is configured. Templates are **fully specified** - you provide the complete pattern, not just overrides.

### Template Variables & Filters

Templates use Jinja-style syntax with filters for transformations. This keeps the variable list small and familiar to users who know Jinja.

#### Core Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{func}` | Function name | `sum`, `avg`, `year`, `running_count` |
| `{prefix}` | Configured prefix (or function name if no prefix) | `num`, `sum`, `avg`, `year` |
| `{col}` | **Shorthand for `{arg1}`** - first column name (single-arg functions only) | `amount`, `price`, `created_at` |
| `{arg1}`, `{arg2}`, `{arg3}`, etc. | Function arguments (always available, `{arg1}` = first, `{arg2}` = second, etc.) | `order_id`, `date`, `email` |

**Note**: `{arg1}` is always set to the first column/argument. `{col}` is just a readable shorthand for `{arg1}` in single-arg functions. For multi-arg functions, use `{arg1}`, `{arg2}`, etc. explicitly.
| `{distinct}` | "distinct" if DISTINCT modifier is used | `distinct` or empty string |
| `{order_by}` | Order column if ORDER BY is used | `order_date` or empty |
| `{partition_by}` | Partition column if PARTITION BY is used | `customer_id` or empty |

#### Available Filters

Filters can be applied to any variable using `|` syntax (Jinja-style):

| Filter | Description | Example |
|--------|-------------|---------|
| `lower` | Convert to lowercase | `{func\|lower}` → `sum`, `SUM` → `sum` |
| `upper` | Convert to uppercase | `{func\|upper}` → `SUM`, `sum` → `SUM` |
| `title` | Title case (first letter uppercase) | `{func\|title}` → `Sum`, `sum` → `Sum` |
| `snake` | Convert to snake_case | `{func\|snake}` → `running_count` → `running_count` |
| `camel` | Convert to camelCase | `{func\|camel}` → `running_count` → `runningCount` |

#### Multi-Column Functions

For functions with multiple columns (e.g., `arg_max(order_id, date)`), use `{arg1}`, `{arg2}`, etc.:

```yaml
compile:
  arg_max_alias_template: "{prefix}_{arg1}_{arg2}"
  arg_max_alias_prefix: "arg_max"
# arg_max(order_id, date) → "arg_max_order_id_date"
```

#### Examples with Filters

```yaml
compile:
  # Uppercase convention
  alias_template: "{func|upper}_{col|upper}"
  # sum(amount) → "SUM_AMOUNT"
  
  # CamelCase convention
  alias_template: "{func|title}{col|title}"
  # sum(amount) → "SumAmount"
  
  # Lowercase with distinct handling
  distinct_count_alias_template: "{prefix|lower}_{distinct|lower}_{col|lower}"
  # count(distinct email) → "num_distinct_email"
```

### Examples

```yaml
compile:
  # Default: func_col
  alias_template: "{func}_{col}"
  # sum(amount) → "sum_amount"
  
  # Alternative: FUNC_COL (uppercase)
  alias_template: "{func|upper}_{col|upper}"
  # sum(amount) → "SUM_AMOUNT"
  
  # Alternative: FuncCol (camelCase)
  alias_template: "{func|title}{col|title}"
  # sum(amount) → "SumAmount"
  
  # Count special cases
  count_alias_prefix: "num"
  count_alias_template: "{prefix}"  # Fully specified - no column
  # count(*) → "num"
  
  distinct_count_alias_prefix: "uniq"
  distinct_count_alias_template: "{prefix}_{distinct}_{col}"
  # count(distinct email) → "uniq_distinct_email"
  
  # Multi-arg functions
  arg_max_alias_prefix: "arg_max"
  arg_max_alias_template: "{prefix}_{arg1}_{arg2}"
  # arg_max(order_id, date) → "arg_max_order_id_date"
  
  # Functions with ORDER BY
  first_alias_prefix: "first"
  first_alias_template: "{prefix}_{col}_by_{order_by}"
  # first(order_id order by -date) → "first_order_id_by_date"
```

### Pros
- ✅ **Flexible** - can customize patterns
- ✅ **Fewer settings** - one template + special cases
- ✅ **Powerful** - supports different naming conventions

### Cons
- ❌ **Complex** - users need to understand template syntax
- ❌ **Error-prone** - invalid templates could break
- ❌ **Hard to discover** - what variables are available?

---

## Approach 3: Prefix + Template Hybrid

### Configuration

```yaml
# asql.config.yaml
compile:
  # Default template (uses prefix)
  alias_template: "{prefix}_{col}"
  
  # Function-specific prefixes (override default)
  sum_alias_prefix: "sum"
  avg_alias_prefix: "avg"
  count_alias_prefix: "num"
  distinct_count_alias_prefix: "uniq"  # or "num_distinct"
  
  # Special templates override prefix
  count_alias_template: "{prefix}"  # count(*) → "num" (no column)
  distinct_count_alias_template: "{prefix}_{col}"  # count(distinct email) → "uniq_email"
  
  # Multi-arg functions
  arg_max_alias_template: "{prefix}_{arg1}_{arg2}"
  arg_max_alias_prefix: "arg_max"
```

### How It Works

1. **Check for function-specific template** (e.g., `count_alias_template`)
   - If exists, use it **as-is** (fully specified, no merging)
   - Variables available: `{func}`, `{prefix}`, `{col}`, `{arg1}`, etc.
2. **Check for function-specific prefix** (e.g., `count_alias_prefix`)
   - If exists, use default template (`alias_template`) with this prefix
   - Example: `alias_template: "{prefix}_{col}"` + `count_alias_prefix: "num"` → `num_{col}`
   - In template, `{prefix}` = configured prefix (or default if no custom prefix)
3. **Use default template** with function's default prefix
   - `alias_template: "{prefix}_{col}"` → `sum_amount` for `sum(amount)` (uses `{prefix}` = "sum", the default)
   - Or `alias_template: "{func}_{col}"` → `sum_amount` (uses `{func}` = "sum")

**Key point**: Templates are **fully specified** - when you set `count_alias_template: "{prefix}"`, that's the complete template. It doesn't merge with defaults.

**Variable Resolution**:
- `{func}` = Always the SQL function name (`count`, `sum`)
- `{prefix}` = Custom prefix if configured, otherwise ASQL's default prefix (`num` for count, `sum` for sum)

### Pros
- ✅ **Best of both worlds** - simple defaults, powerful overrides
- ✅ **Backward compatible** - prefix settings work as before
- ✅ **Flexible** - templates for complex cases

### Cons
- ❌ **Two concepts** - prefixes and templates
- ❌ **Precedence rules** - need to document clearly

---

## Approach 4: Category-Based Configuration

### Configuration

```yaml
# asql.config.yaml
compile:
  # Category defaults
  aggregate_alias_template: "{func}_{col}"
  date_alias_template: "{func}_{col}"
  window_alias_template: "{func}_{col}"
  string_alias_template: "{func}_{col}"
  
  # Function overrides within categories
  aggregates:
    sum_prefix: "sum"
    avg_prefix: "avg"
    count_prefix: "num"
    distinct_count_prefix: "uniq"
  
  dates:
    year_prefix: "year"
    month_prefix: "month"
  
  # Special templates
  count_alias_template: "{prefix}"  # Overrides category template
```

### Pros
- ✅ **Organized** - groups related functions
- ✅ **Scalable** - easy to add new categories
- ✅ **Clear** - function categories are obvious

### Cons
- ❌ **More complex** - nested structure
- ❌ **Category definitions** - need to define what goes where

---

## Comparison with Other Systems

### dbt

dbt uses **macros** for custom SQL generation, but doesn't have built-in column naming configuration. Users write custom macros:

```sql
-- dbt macro
{% macro sum_alias(column_name) %}
  sum({{ column_name }}) as sum_{{ column_name }}
{% endmacro %}
```

**Takeaway**: dbt relies on user-written macros, not configuration.

### SQLAlchemy

SQLAlchemy uses **label generation** but doesn't have configurable templates:

```python
# SQLAlchemy
func.sum(Order.amount).label('sum_amount')  # Explicit label required
```

**Takeaway**: SQLAlchemy requires explicit labels, no auto-aliasing.

### pandas

pandas doesn't have configurable column naming - operations create new columns with default names:

```python
# pandas
df.groupby('region')['amount'].sum()  # Column name is 'amount' (unchanged)
df.groupby('region').agg({'amount': 'sum'})  # Column name is 'amount' (unchanged)
```

**Takeaway**: pandas doesn't auto-alias aggregations.

### PRQL

PRQL (Prelational Query Language) doesn't appear to have configurable auto-aliasing - it generates SQL with default names.

**Takeaway**: Most systems don't have configurable auto-aliasing - ASQL would be innovative here.

---

## Recommended Approach: Hybrid (Prefix + Template)

### Configuration Structure

```yaml
# asql.config.yaml
compile:
  # Default template (used when no function-specific config exists)
  alias_template: "{func}_{col}"
  
  # Function-specific prefixes (shortcut for common overrides)
  # These use the default template: {prefix}_{col}
  sum_alias_prefix: "sum"
  avg_alias_prefix: "avg"
  min_alias_prefix: "min"
  max_alias_prefix: "max"
  count_alias_prefix: "num"
  distinct_count_alias_prefix: "uniq"
  
  # Function-specific templates (override prefix + default template)
  count_alias_template: "{prefix}"  # count(*) → "num"
  distinct_count_alias_template: "{prefix}_{col}"  # count(distinct email) → "uniq_email"
  
  # Multi-arg function templates
  arg_max_alias_template: "{prefix}_{arg1}_{arg2}"
  arg_max_alias_prefix: "arg_max"
  
  # Window functions
  running_sum_alias_prefix: "running_sum"
  running_avg_alias_prefix: "running_avg"
  running_count_alias_prefix: "running_num"
  
  # Date functions (use default template, but can override prefix)
  year_alias_prefix: "year"  # Optional - defaults to function name
  month_alias_prefix: "month"
```

### Precedence Rules

1. **Function-specific template** (e.g., `count_alias_template`) - highest priority
2. **Function-specific prefix** (e.g., `count_alias_prefix`) - uses default template with prefix
3. **Default template** - uses function name as prefix

### Template Variable Reference

#### Core Variables

| Variable | Available In | Description | Example |
|----------|--------------|-------------|---------|
| `{func}` | All templates | Function name | `sum`, `avg`, `year`, `running_count` |
| `{prefix}` | All templates | Configured prefix (or function name if no prefix) | `sum`, `num`, `year` |
| `{col}` | Single-arg templates | **Shorthand for `{arg1}`** - first column name | `amount`, `price`, `created_at` |
| `{arg1}`, `{arg2}`, `{arg3}`, etc. | All templates | Function arguments (positional, `{arg1}` = first, `{arg2}` = second, etc.) | `order_id`, `date`, `email` |

**Multi-column handling**: 
- `{arg1}` is **always available** and equals the first column/argument
- `{col}` is **shorthand for `{arg1}`** - works for single-arg functions as convenient shorthand
- For single-arg functions: Both `{col}` and `{arg1}` work (they're the same)
- For multi-arg functions: **Must use `{arg1}`, `{arg2}`, etc. explicitly** (cannot use `{col}`)
- Example: `sum(amount)` → `{col}` or `{arg1}` both work (same value)
- Example: `arg_max(order_id, date)` → **must** use `{arg1}` and `{arg2}`, `{col}` is not valid
| `{distinct}` | Count/aggregate templates | "distinct" if DISTINCT modifier used | `distinct` or empty string |
| `{order_by}` | Ordered aggregate templates | Order column if ORDER BY clause used | `order_date` or empty (for `first()`, `last()`) |
| `{partition_by}` | Window function templates | Partition column if PARTITION BY used | `customer_id` or empty |

#### Available Filters (Jinja-style)

Filters can be applied to any variable using `|` syntax:

| Filter | Description | Example |
|--------|-------------|---------|
| `lower` | Convert to lowercase | `{func\|lower}` → `sum` |
| `upper` | Convert to uppercase | `{func\|upper}` → `SUM` |
| `title` | Title case (first letter uppercase) | `{func\|title}` → `Sum` |
| `snake` | Convert to snake_case (if needed) | `{func\|snake}` → `running_count` |
| `camel` | Convert to camelCase | `{func\|camel}` → `runningCount` |

**Note**: Using filters keeps the variable list small (5 core variables + filters) rather than having 15+ separate variables like `{func_upper}`, `{func_lower}`, `{col_upper}`, etc.

### Examples

```yaml
# Example 1: Default behavior
compile:
  alias_template: "{func}_{col}"
# sum(amount) → "sum_amount"
# avg(price) → "avg_price"

# Example 2: Custom prefix for counts (fully specified template)
compile:
  alias_template: "{func}_{col}"  # Default for most functions
  count_alias_prefix: "num"
  count_alias_template: "{prefix}"  # Fully specified - no column for count(*)
# count(*) → "num"
# count(email) → "num_email"  # Uses default template with prefix


# Example 3: Uppercase convention (using filters)
compile:
  alias_template: "{func|upper}_{col|upper}"
# sum(amount) → "SUM_AMOUNT"

# Example 4: CamelCase convention (using filters)
compile:
  alias_template: "{func|title}{col|title}"
# sum(amount) → "SumAmount"

# Example 5: Custom distinct count pattern
compile:
  distinct_count_alias_prefix: "uniq"
  distinct_count_alias_template: "{prefix}_{distinct}_{col}"
# count(distinct email) → "uniq_distinct_email"

# Example 6: Multi-arg function
compile:
  arg_max_alias_prefix: "arg_max"
  arg_max_alias_template: "{prefix}_{arg1}_{arg2}"
# arg_max(order_id, date) → "arg_max_order_id_date"

# Example 7: Function with ORDER BY
compile:
  first_alias_prefix: "first"
  first_alias_template: "{prefix}_{col}_by_{order_by}"
# first(order_id order by -date) → "first_order_id_by_date"

# Example 8: Custom separator style
compile:
  alias_template: "{prefix}__{col}"  # Double underscore separator
  count_alias_prefix: "num"
# count(email) → "num__email" (uses custom prefix with double underscore)
# sum(amount) → "sum__amount" (uses default prefix with double underscore)
```

---

## Implementation Considerations

### Template Parsing

- **Use Jinja2** for template rendering (familiar, powerful, well-tested)
- **Templates are fully specified** - you provide the complete pattern, not partial overrides
- Validate templates at config load time
- Error on unknown variables or filters
- Support escaping (e.g., `{{` for literal `{`)
- Filter syntax: `{variable|filter}` (standard Jinja)

**Important**: When you set a function-specific template (e.g., `count_alias_template: "{prefix}"`), you're providing the **complete** template. It doesn't merge with the default template - it replaces it entirely.

**Implementation note**: Jinja2 is a common dependency in Python data tools (dbt uses it), so it's a natural choice. It provides:
- Familiar syntax for users who know dbt/Jinja
- Powerful filtering and transformation
- Good error messages
- Well-documented

### Default Values

- If no config file: use hardcoded defaults
- If config file exists but setting missing: use default template
- Function-specific settings override category/default

### Validation

```python
# Pseudo-code
def validate_template(template: str, function: str) -> bool:
    """Validate template has required variables for function."""
    required_vars = get_required_variables(function)
    for var in required_vars:
        if var not in template:
            raise ValueError(f"Template missing required variable: {var}")
    return True
```

### Performance

- Parse templates once at config load time
- Cache compiled templates
- Fast lookup for function-specific configs

---

## Modifiers & Special Keywords

Beyond `DISTINCT`, ASQL functions can have other modifiers that affect column naming:

### ORDER BY (for `first()`, `last()`)

```asql
first(order_id order by -date)  -- Has ORDER BY clause
```

**Template variable**: `{order_by}` contains the column being ordered by (e.g., `date`)

**Example template**:
```yaml
first_alias_template: "{prefix}_{col}_by_{order_by}"
# first(order_id order by -date) → "first_order_id_by_date"
```

### PARTITION BY (for window functions)

```asql
row_number() over (partition by customer_id order by -date)
```

**Template variable**: `{partition_by}` contains the partition column (e.g., `customer_id`)

**Example template**:
```yaml
row_number_alias_template: "{prefix}_per_{partition_by}"
# row_number() over (partition by customer_id ...) → "row_num_per_customer_id"
```

### Other Modifiers?

Currently identified:
- ✅ `DISTINCT` → `{distinct}` variable (e.g., `count(distinct email)`)
- ✅ `ORDER BY` → `{order_by}` variable (e.g., `first(order_id order by -date)`)
- ✅ `PARTITION BY` → `{partition_by}` variable (e.g., window functions)

**Potential future modifiers** (not currently in ASQL):
- `FILTER (WHERE ...)` - SQL standard aggregate filter (e.g., `sum(amount) FILTER (WHERE status = 'active')`)
- `WITHIN GROUP (ORDER BY ...)` - For ordered-set aggregates (e.g., `percentile_cont(0.5) WITHIN GROUP (ORDER BY amount)`)
- `IGNORE NULLS` / `RESPECT NULLS` - For window functions

**Recommendation**: Start with the three identified modifiers (`distinct`, `order_by`, `partition_by`). Add others as ASQL adds support for those SQL features.

---

## Open Questions

1. **Column name transformations**: Jinja filters already handle this
   ```yaml
   compile:
     alias_template: "{prefix|title}{col|title}"  # camelCase: SumAmount
     alias_template: "{prefix|upper}_{col|upper}"  # UPPER_SNAKE: SUM_AMOUNT
   ```
   Filters like `|camel`, `|snake`, `|title`, `|upper`, `|lower` provide all needed transformations. No need for separate transform settings.

2. **Conditionals in templates**: Jinja supports conditionals, but keep it simple
   ```yaml
   compile:
     alias_template: "{prefix}_{col if col else ''}"  # Jinja conditional
   ```
   **Recommendation**: Use separate templates for special cases (like `count(*)`) rather than complex conditionals. Simpler and clearer.

3. **Per-dialect templates**: Not needed
   - Users can set per-project via config files
   - Dialect-specific naming conventions are rare
   - Keep it simple - one template per project

4. **How do we handle function name conflicts?**
   - If `sum_alias_prefix` and `sum_alias_template` both exist, **template wins** (highest precedence)
   - Document precedence clearly: Template > Prefix > Default

5. **Preset templates**: Future consideration
   - Could provide shortcuts like `alias_preset: "snake_case"` or `"camelCase"`
   - Would set `alias_template` automatically
   - Allows sharing common styles across projects
   - See `docs/spec_future.md` for future feature tracking

6. **Multi-column handling**: What's the best approach?

   **Functions with multiple columns**:
   - `arg_max(order_id, date)` - two columns
   - `arg_min(order_id, date)` - two columns  
   - `concat(first_name, last_name)` - two+ columns
   - `coalesce(primary_email, secondary_email)` - two+ columns
   - `string_agg(name, ', ')` - column + separator (arg2 is separator, not column)
   - `replace(text, "old", "new")` - column + two string literals
   
   **Options**:
   - **Option A**: `{col}` = first column only, require `{arg1}`, `{arg2}` for multi-arg
     - Pro: Explicit and clear
     - Pro: No ambiguity about which column `{col}` refers to
     - Con: More verbose for multi-arg functions
   
   - **Option B**: `{col}` works for single-arg, `{arg1}`, `{arg2}` required for multi-arg
     - Pro: Natural shorthand for common case (single-arg)
     - Pro: Forces explicit naming for complex cases
     - Con: Need to detect function arity
   
   **Recommendation**: **Option B** - `{arg1}` is always available and equals the first column/argument. `{col}` is shorthand for `{arg1}` in single-arg functions. For multi-arg functions, require explicit `{arg1}`, `{arg2}`, etc. This is clearer and prevents ambiguity.
   
   **Implementation**: 
   - `{arg1}` is always set to the first argument/column (works for all functions)
   - `{col}` = `{arg1}` (they're the same variable, `{col}` is just more readable shorthand)
   - For single-arg: Both `{col}` and `{arg1}` work identically
   - For multi-arg: Only `{arg1}`, `{arg2}`, etc. are valid (no `{col}`)
   
   **Examples**:
   ```yaml
   # Single-arg: Both {col} and {arg1} work (they're the same)
   alias_template: "{prefix}_{col}"
   # sum(amount) → "sum_amount" ✅
   # Equivalent to: alias_template: "{prefix}_{arg1}" → "sum_amount" ✅
   
   # Single-arg: Can use {arg1} explicitly if preferred
   alias_template: "{prefix}_{arg1}"
   # sum(amount) → "sum_amount" ✅ (same as {col})
   
   # Multi-arg: Must use {arg1}, {arg2} explicitly
   arg_max_alias_template: "{prefix}_{arg1}_{arg2}"
   # arg_max(order_id, date) → "arg_max_order_id_date" ✅
   
   # Cannot use {col} in multi-arg templates - error if attempted
   # concat_alias_template: "{prefix}_{col}"  # ❌ Error: {col} not valid for multi-arg functions
   concat_alias_template: "{prefix}_{arg1}_{arg2}"  # ✅ Correct
   ```


---

## Recommendations

### Phase 1: Prefix-Based (Simple)

Start with prefix-based configuration for common functions:

```yaml
compile:
  # Common aggregates
  sum_alias_prefix: "sum"
  avg_alias_prefix: "avg"
  count_alias_prefix: "num"
  distinct_count_alias_prefix: "uniq"
  
  # Special templates for edge cases
  count_alias_template: "{prefix}"  # count(*) → "num"
```

**Rationale**: Simple, easy to understand, covers 80% of use cases.

### Phase 2: Add Template Support

Add template system for power users:

```yaml
compile:
  alias_template: "{func}_{col}"  # Default
  # Function-specific overrides as needed
```

**Rationale**: Provides flexibility without overwhelming simple users.

### Phase 3: Add Presets

Add preset shortcuts:

```yaml
compile:
  alias_preset: "snake_case"  # Sets template automatically
  # Can still override individual functions
```

**Rationale**: Makes common patterns even easier.

---

## Conclusion

The **hybrid approach (prefix + template)** provides the best balance:
- **Simple defaults** for most users (just set prefixes)
- **Powerful templates** for advanced users
- **Backward compatible** with current prefix-based design
- **Extensible** for future needs

Key principles:
1. **Defaults should work well** - most users never need to configure
2. **Prefixes are shortcuts** - common case, easy to understand
3. **Templates are power features** - for advanced customization
4. **Precedence is clear** - template > prefix > default
