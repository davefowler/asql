# Conditional Columns / Status-Based Column Expansion - Research & Proposal

**Date:** 2026-01-16  
**Status:** Research Complete, Proposal Draft  
**Triggered by:** [Playground Example](https://play.analyticsql.com/?d_f=snowflake&d_t=ASQL&...) from dbt_zendesk

---

## 1. What's the Pattern?

The example shows a common analytics pattern I'll call **"conditional column expansion"** or **"status-based derived columns"**. Here's the essence:

```sql
-- From the business_minutes CTE in dbt_zendesk
case when ticket_status in ('pending') then scheduled_minutes
    else 0 end as agent_wait_time_in_minutes,
case when ticket_status in ('new', 'open', 'hold') then scheduled_minutes
    else 0 end as requester_wait_time_in_minutes,
case when ticket_status in ('new', 'open', 'hold', 'pending') then scheduled_minutes
    else 0 end as solve_time_in_minutes,
case when ticket_status in ('new', 'open') then scheduled_minutes
    else 0 end as agent_work_time_in_minutes,
case when ticket_status in ('hold') then scheduled_minutes
    else 0 end as on_hold_time_in_minutes,
case when ticket_status = 'new' then scheduled_minutes
    else 0 end as new_status_duration_minutes,
case when ticket_status = 'open' then scheduled_minutes
    else 0 end as open_status_duration_minutes
```

**What this does:**
- Takes a single value column (`scheduled_minutes`)
- "Fans out" into 7 different output columns
- Each column gets the value ONLY when a specific condition matches
- Otherwise the column gets 0 (or NULL)

This is **NOT** a pivot operation (which is usually 1:1 value-to-column for each distinct value). Instead, it's a **many-to-many mapping** where:
- The same status value can contribute to multiple output columns
- Multiple status values can contribute to the same output column
- The conditions can be arbitrary expressions, not just equality

---

## 2. How Common is This Pattern?

**Extremely common** in analytics workloads. Found in:

### 2.1 Time-in-State Analysis
- Support ticket duration by status (the dbt_zendesk example)
- Order fulfillment time by stage
- Manufacturing time by process step
- User session time by activity type

### 2.2 Conditional Aggregation Prep
Creating columns that will later be summed/aggregated:
```sql
sum(case when is_returned then amount else 0 end) as returns_amount,
sum(case when is_completed then amount else 0 end) as completed_amount
```

### 2.3 Funnel/Category Breakdowns
- Marketing attribution by channel
- Revenue by product category
- Costs by department

### 2.4 Boolean Flag Expansion
```sql
case when status = 'active' then 1 else 0 end as is_active,
case when status = 'pending' then 1 else 0 end as is_pending,
...
```

### 2.5 Evidence of Prevalence
- dbt packages (zendesk, salesforce, hubspot, etc.) use this pattern extensively
- StackOverflow: Thousands of questions about "multiple CASE WHEN columns"
- Every analytics team I've seen has queries with 5-20 conditional columns

---

## 3. The Pain Points

### 3.1 Verbosity
The SQL is extremely repetitive:
- Each column repeats `case when ... then ... else ... end as`
- The base value (`scheduled_minutes`) is repeated for every column
- The default (`0`) is repeated for every column

### 3.2 Maintenance Burden
When business logic changes:
- Adding a new status requires updating multiple CASE statements
- Changing which statuses belong to which category is error-prone
- Finding all places where a status is used is difficult

### 3.3 Readability
The actual business logic (the mapping) is buried in boilerplate:
```sql
-- What you care about:
pending → agent_wait_time
(new, open, hold) → requester_wait_time
(new, open, hold, pending) → solve_time

-- What you have to write: 50+ lines of CASE WHEN
```

### 3.4 Consistency
- Easy to forget a status in one column but not another
- No validation that the same status list is used consistently
- Copy-paste errors are common

---

## 4. What Do Other Tools/Languages Do?

### 4.1 dbt + Jinja Macros
The most common solution today - template the repetition:

```jinja
{% set status_map = {
  'pending': 'agent_wait_time',
  ['new', 'open', 'hold']: 'requester_wait_time',
  ...
} %}

{% for statuses, col_name in status_map.items() %}
  sum(case when ticket_status in ({{ statuses | join(',') }}) 
      then scheduled_minutes else 0 end) as {{ col_name }},
{% endfor %}
```

**Pros:** Flexible, reduces duplication  
**Cons:** Hidden logic, harder to debug, Jinja is awkward for complex mappings

### 4.2 Pandas / Python
```python
# Using apply with a dict mapping
df['agent_wait'] = df['scheduled_minutes'].where(df['status'] == 'pending', 0)
df['requester_wait'] = df['scheduled_minutes'].where(df['status'].isin(['new', 'open', 'hold']), 0)
```

Or with pivot_table:
```python
# Only works for 1:1 mapping (status → column)
df.pivot_table(values='minutes', index='ticket_id', columns='status', aggfunc='sum')
```

**Note:** Pandas pivot_table doesn't support the many-to-many mapping pattern.

### 4.3 PRQL
PRQL has `switch` but it maps to a single output, not multiple columns:
```prql
derive tier = switch status [
  "pending" => "agent",
  "new" || "open" => "requester",
]
```

PRQL doesn't have a built-in pattern for generating multiple columns from conditions.

### 4.4 SQL Extensions

**PostgreSQL FILTER clause** (aggregation only):
```sql
sum(minutes) filter (where status = 'pending') as agent_wait
```
This is cleaner but only works in aggregate context, not row-level.

**PIVOT (SQL Server, Oracle, Snowflake):**
```sql
PIVOT (sum(minutes) FOR status IN ('pending', 'new', 'open'))
```
This is 1:1 mapping only - doesn't support the overlapping category pattern.

### 4.5 BI Tools / Semantic Layers
- LookML: Define measures with conditions
- dbt Metrics: Define metrics with filters
- Cube.js: Measures with segments

These push the problem to a different layer but don't solve it at the query level.

### 4.6 Generated/Computed Columns
Some databases support schema-level computed columns, but:
- Most require deterministic expressions
- Doesn't help when the mapping is specific to the query
- Inflexible for ad-hoc analysis

---

## 5. ASQL Opportunity

ASQL is well-positioned to address this because:
1. We already have clean `when` syntax for conditionals
2. We have a pipeline model that could incorporate this
3. Our target audience (analytics engineers) hits this pain point daily

---

## 6. Design Options

### Option A: `spread` Expression

Create multiple columns by spreading a value across conditions:

```asql
from intercepted_periods
select
  source_relation,
  ticket_id,
  ticket_status,
  spread scheduled_minutes ?? 0 as (
    agent_wait_time when ticket_status in ("pending"),
    requester_wait_time when ticket_status in ("new", "open", "hold"),
    solve_time when ticket_status in ("new", "open", "hold", "pending"),
    agent_work_time when ticket_status in ("new", "open"),
    on_hold_time when ticket_status in ("hold"),
    new_status_duration when ticket_status = "new",
    open_status_duration when ticket_status = "open"
  )
```

**Characteristics:**
- `spread <value_expr> ?? <default> as (...)` - creates multiple columns
- Each branch: `<alias> when <condition>`
- Clean grouping of related columns
- Default value is explicit

### Option B: `bucket` Syntax

More declarative, focused on the mapping:

```asql
from intercepted_periods
bucket scheduled_minutes by ticket_status into (
  agent_wait_time: "pending",
  requester_wait_time: ("new", "open", "hold"),
  solve_time: ("new", "open", "hold", "pending"),
  agent_work_time: ("new", "open"),
  on_hold_time: "hold",
  new_status_duration: "new",
  open_status_duration: "open"
) default 0
```

**Characteristics:**
- `bucket <value> by <column> into (<mapping>) default <value>`
- More concise syntax
- Values on the right side are implicitly `column in (values)`
- Doesn't support arbitrary conditions (only equality/membership)

### Option C: Inline Multiple `when` with Spread

Extension of existing `when` syntax:

```asql
from intercepted_periods
select
  source_relation,
  ticket_id,
  scheduled_minutes when ticket_status in ("pending") as agent_wait_time ?? 0,
  scheduled_minutes when ticket_status in ("new", "open", "hold") as requester_wait_time ?? 0,
  ...
```

**Characteristics:**
- Uses existing `when` pattern
- Each column is independent
- More repetition than Options A/B
- But still cleaner than SQL's `CASE WHEN ... THEN ... ELSE ... END`

### Option D: `categorize` Pipeline Operator

A dedicated pipeline step:

```asql
from intercepted_periods
categorize scheduled_minutes as time_in_status where
  agent_wait_time: ticket_status in ("pending"),
  requester_wait_time: ticket_status in ("new", "open", "hold"),
  solve_time: ticket_status in ("new", "open", "hold", "pending"),
  agent_work_time: ticket_status in ("new", "open"),
  on_hold_time: ticket_status in ("hold")
  default 0
```

**Characteristics:**
- Pipeline-level operator (like `rename`, `replace`)
- Adds multiple columns in one statement
- Could be composable with other operators

### Option E: Mapping Table Reference

For large/dynamic mappings, reference a configuration:

```asql
from intercepted_periods
spread scheduled_minutes using status_time_mapping
```

Where `status_time_mapping` is defined elsewhere (YAML, another table, etc.)

**Characteristics:**
- Maximum reusability
- Separation of mapping from query
- Requires additional infrastructure

---

## 7. Comparison Matrix

| Aspect | Option A (spread) | Option B (bucket) | Option C (inline when) | Option D (categorize) |
|--------|------------------|-------------------|----------------------|---------------------|
| Readability | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Flexibility | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Conciseness | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Arbitrary conditions | ✅ | ❌ (equality only) | ✅ | ✅ |
| Grouping of columns | ✅ | ✅ | ❌ | ✅ |
| Learning curve | Medium | Low | Low | Medium |
| Implementation complexity | Medium | Medium | Low | Medium |

---

## 8. Recommendation

### Primary Recommendation: Option A (`spread`) + Option C (inline enhancement)

**Why:**

1. **Option A (`spread`)** handles the common case elegantly:
   - Groups related conditional columns together
   - Clear syntax with explicit default
   - Supports arbitrary conditions
   - Signals intent clearly ("spread this value across conditions")

2. **Option C (inline when)** is a simpler enhancement that's useful even standalone:
   - `value when condition as alias ?? default` is intuitive
   - Low implementation cost
   - Progressive complexity (use simple form for simple cases, spread for complex)

### Example of Both Working Together

```asql
from intercepted_periods
select
  source_relation,
  ticket_id,
  ticket_status,
  
  -- For complex related columns, use spread
  spread scheduled_minutes ?? 0 as (
    agent_wait_time when ticket_status in ("pending"),
    requester_wait_time when ticket_status in ("new", "open", "hold"),
    solve_time when ticket_status in ("new", "open", "hold", "pending"),
    agent_work_time when ticket_status in ("new", "open"),
    on_hold_time when ticket_status in ("hold")
  ),
  
  -- For simple one-off conditionals, inline is cleaner
  scheduled_minutes when ticket_status = "new" as new_duration ?? 0,
  scheduled_minutes when ticket_status = "open" as open_duration ?? 0
```

---

## 9. Should We Do This?

### YES - Strong Recommendation

**Reasons:**

1. **High pain, common pattern**: This is one of the most tedious patterns in analytics SQL

2. **Clean fit for ASQL's philosophy**: 
   - "Natural language feel"
   - "Less boilerplate"
   - "Better for analytics"

3. **No good existing solution**: Even dbt macros are awkward for this

4. **Differentiation**: This would be a killer feature for ASQL vs other SQL alternatives

5. **Implementation is tractable**: Compiles straightforwardly to CASE WHEN

### Concerns to Address

1. **Complexity**: Don't want ASQL to become a kitchen-sink language
   - Mitigation: Start with Option C (inline when), graduate to spread if validated

2. **Confusion with pivot**: Need clear documentation distinguishing this from pivot
   - Spread: many-to-many mapping, same value to multiple columns
   - Pivot: one-to-one, distinct values become columns

3. **Edge cases**: What about NULL handling, type coercion, nested expressions
   - Address in detailed design phase

---

## 10. Next Steps

1. **[ ] Validate the pattern**: Search existing ASQL examples/tests for CASE WHEN patterns
2. **[ ] Prototype Option C**: Low-risk, high-value enhancement to `when`
3. **[ ] Design Option A in detail**: Grammar, parsing, edge cases
4. **[ ] Create GitHub issue**: With spec and discussion
5. **[ ] Implement and test**: Start with simple cases

---

## Appendix: SQL Comparison

**Current SQL (53 lines for 7 columns):**
```sql
case when ticket_status in ('pending') then scheduled_minutes
    else 0 end as agent_wait_time_in_minutes,
case when ticket_status in ('new', 'open', 'hold') then scheduled_minutes
    else 0 end as requester_wait_time_in_minutes,
case when ticket_status in ('new', 'open', 'hold', 'pending') then scheduled_minutes
    else 0 end as solve_time_in_minutes,
case when ticket_status in ('new', 'open') then scheduled_minutes
    else 0 end as agent_work_time_in_minutes,
case when ticket_status in ('hold') then scheduled_minutes
    else 0 end as on_hold_time_in_minutes,
case when ticket_status = 'new' then scheduled_minutes
    else 0 end as new_status_duration_minutes,
case when ticket_status = 'open' then scheduled_minutes
    else 0 end as open_status_duration_minutes
```

**ASQL with `spread` (12 lines for 7 columns):**
```asql
spread scheduled_minutes ?? 0 as (
  agent_wait_time when ticket_status in ("pending"),
  requester_wait_time when ticket_status in ("new", "open", "hold"),
  solve_time when ticket_status in ("new", "open", "hold", "pending"),
  agent_work_time when ticket_status in ("new", "open"),
  on_hold_time when ticket_status in ("hold"),
  new_status_duration when ticket_status = "new",
  open_status_duration when ticket_status = "open"
)
```

**Reduction: ~77% less code** 🎉
