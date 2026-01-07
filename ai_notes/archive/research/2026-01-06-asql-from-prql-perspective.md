# ASQL Analysis: A PRQL Team Perspective

**Date**: January 6, 2026  
**Context**: Competitive analysis of ASQL (Analytic SQL) from PRQL's viewpoint  
**Audience**: PRQL core team

---

## TL;DR

ASQL is a pipeline SQL alternative that launched after PRQL. It shares our core insight (pipeline-first) but makes **opposite vocabulary choices** (keeps SQL keywords) and focuses on **implicit magic** rather than explicit abstractions.

**Should we be concerned?** Somewhat. ASQL targets users who find PRQL "too different"—the massive population of SQL users who want improvements but won't learn new verbs. This is a real market we're not fully serving.

**Is ASQL innovative?** Partially. Their "guaranteed groups" and convention-based inference are genuinely novel. Their syntax is mostly SQL with pipes.

**Should ASQL exist?** Probably yes, but we should consider whether PRQL can absorb some of their better ideas.

---

## 1. What Is ASQL?

ASQL (pronounced "Ask-el") is a pipeline-based query language that:
- Uses SQL vocabulary (`where`, `limit`, `order by`)
- Compiles to SQL via SQLGlot
- Emphasizes "convention over configuration"
- Targets analytics workloads

### Their Stated Values
1. Pipeline Order Over Projection-First *(same as us)*
2. Convention Over Configuration *(different from us)*
3. Familiarity Over Novelty *(opposite of us)*
4. Portable Over Proprietary *(same as us)*
5. Completeness Over Fast Queries *(unique to them)*
6. Code Comments Over Catalogues *(minor)*

---

## 2. Syntax Comparison: Where ASQL Differs

### Vocabulary

| Operation | PRQL | ASQL | Analysis |
|-----------|------|------|----------|
| Filter | `filter` | `where` | They kept SQL's confusing keyword |
| Add columns | `derive` | `select *, ...` | They don't have a dedicated verb |
| Limit | `take` | `limit` | SQL keyword |
| Sort | `sort` | `order by` | SQL keywords |
| Aggregate | `aggregate` | inline in `group by ()` | Different structure |

**Their rationale**: "Familiarity Over Novelty" — they explicitly argue that keeping SQL vocabulary reduces learning curve to "hours, not weeks."

**Our counter**: Our vocabulary is more intentional. `filter` is unambiguous (no WHERE vs HAVING confusion). `derive` clearly means "add columns." `take` is simpler than `limit`. We designed a better language; they designed a safer migration path.

### Joins

PRQL:
```prql
from employees
join departments (==department_id)
```

ASQL:
```asql
-- Both syntaxes work:
from employees & departments on department_id
from employees join departments on department_id
```

**Analysis**: They support both symbolic operators (`&`, `&?`, `?&`, `*`) and traditional SQL keywords (`join`, `left join`, etc.). The `?` marks nullable sides:
- `&` / `join` = INNER
- `&?` / `left join` = LEFT (right side nullable)
- `?&` / `right join` = RIGHT
- `?&?` / `full outer join` = FULL OUTER

The FK column shorthand (`on department_id` expanding to `ON employees.department_id = departments.id`) works with both styles.

### Aggregation

PRQL:
```prql
from orders
group customer_id (
  aggregate {
    total = sum amount,
    count = count this
  }
)
```

ASQL:
```asql
from orders
  group by customer_id (
    sum(amount) as total,
    # as count
  )
```

**Analysis**: They combine `group by` and aggregation in one clause. We separate them for orthogonality. Their `#` shorthand for `COUNT(*)` is admittedly clever.

---

## 3. Where ASQL Is Genuinely Different

### 3.1 Convention-Based FK Inference

This is novel. If a column follows `{name}_id` pattern, you can traverse it:

```asql
from orders
  select orders.user.name  -- auto-joins via user_id → users.id
```

ASQL:
1. Sees `.user.` traversal
2. Finds `user_id` column
3. Infers target `users` table (pluralized)
4. Creates LEFT JOIN automatically

**Our take**: When conventions aren't followed, this either:
1. Fails explicitly with a clear error asking for an explicit key, or
2. In the extremely rare case of a mis-named FK (e.g., `user_id` not pointing to users), produces wrong results—but a human reading the schema would make the same mistake.

For teams with good modeling standards (dbt users), this is a significant productivity win.

**Philosophy**: This aligns with our "Concise Over Verbose" value—redundant explicitness isn't clarity, it's noise. When `user_id` obviously points to `users.id`, forcing you to write it adds nothing but error surface.

### 3.2 Guaranteed Groups (Auto-Spine)

This is their most interesting feature. When you GROUP BY a date truncation, ASQL ensures **all expected values appear**, even with no data:

```asql
from orders
  where order_date >= @2024-01-01 and order_date < @2025-01-01
  group by month(order_date) ( sum(amount) ?? 0 as revenue )
```

Result: All 12 months appear, even those with zero revenue.

**How it works**: ASQL generates a "spine" CTE with all expected values, then LEFT JOINs your data.

**Why it matters**: Analytics dashboards break when months are missing. This is a real pain point we don't address.

**Our take**: This is genuinely useful. It's "magic" but the magic is well-defined and documented. They claim <5% performance overhead.

**Should we adopt?** Possibly, but it conflicts with our "simple" principle. It adds implicit behavior that users might not expect.

### 3.3 Auto-Aliasing

ASQL auto-generates column names when aliases aren't provided:

```asql
from orders
  group by month(created_at) ( sum(amount) )
  -- columns: month_created_at, sum_amount (auto-generated)
```

**Our take**: We require explicit naming. Their approach reduces typing but can produce unexpected names.

### 3.4 Domain-Specific Features

ASQL has analytics-specific syntax that we don't:

| Feature | ASQL | PRQL |
|---------|------|------|
| `# users` | COUNT(DISTINCT user_id) via naming | No equivalent |
| `7 days ago` | Relative date literal | Manual calculation |
| `days_since_created_at` | Auto-generates DATEDIFF | No equivalent |
| `cohort by` | First-class cohort analysis | Manual CTEs |
| `per ... first by` | Deduplication sugar | `group ... take 1` |

**Our take**: These are conveniences, not fundamental improvements. But conveniences matter for adoption.

---

## 4. Where PRQL Is Better

### 4.1 Abstraction: `let` and `func`

We have user-defined functions and variables. They don't.

```prql
func fiscal_year date -> (date + 6m) | year

let threshold = 1000

from orders
filter amount > threshold
derive fy = fiscal_year order_date
```

ASQL has no equivalent. Their `stash as` only creates CTEs, not reusable expressions.

**This is our core advantage.** ASQL users will hit a wall when they need to reuse logic across queries. We enable composability; they enable convenience.

### 4.2 Cleaner Vocabulary

Our verbs are intentional and unambiguous:

| PRQL | Why it's better |
|------|----------------|
| `filter` | No WHERE/HAVING confusion |
| `derive` | Clear: "add columns" |
| `take` | Simpler than `limit` |
| `aggregate` | Explicit separation from `group` |

ASQL inherits SQL's historical baggage.

### 4.3 `derive` vs `select *`

Adding a column in PRQL:
```prql
from orders
derive total = amount * quantity
```

Adding a column in ASQL:
```asql
from orders
  select *, amount * quantity as total
```

Our syntax is cleaner. They require `select *, ...` to preserve existing columns.

### 4.4 Orthogonal Primitives

We designed PRQL with composability in mind. Operations are orthogonal:
- `filter` filters
- `derive` adds columns
- `select` chooses columns
- `group` groups
- `aggregate` aggregates

ASQL conflates things. Their `group by ... ()` combines grouping and aggregation. Their `select` does too many jobs.

---

## 5. Honest Assessment: Should ASQL Exist?

### Arguments FOR ASQL's existence:

1. **Different audience**: SQL users who want improvements but won't learn new vocabulary. This is a HUGE population we're not fully capturing.

2. **Convention-based inference**: If you follow naming conventions, ASQL is legitimately less typing. FK traversal and auto-aliasing are real productivity gains.

3. **Guaranteed groups**: This solves a real analytics pain point we don't address. Missing data in GROUP BY results causes dashboard bugs.

4. **Lower learning curve**: Their "hours, not weeks" claim is probably accurate. SQL users can read ASQL immediately.

### Arguments AGAINST ASQL's existence:

1. **Mostly cosmetic differences**: Remove the conveniences, and ASQL is "PRQL with SQL keywords." The core pipeline model is identical.

2. **No abstraction story**: Without `func` and `let`, ASQL users can't build reusable query logic. This limits its power for complex use cases.

3. **Magic can fail**: Convention-based FK inference relies on naming patterns. When conventions break, errors will be mysterious.

4. **SQL baggage**: Keeping `where`, `order by`, etc. inherits SQL's historical warts.

### Verdict

**ASQL probably should exist**, but for a different reason than they claim.

ASQL's value isn't the syntax—it's the **analytics-specific features**:
- **Guaranteed groups** — Automatic gap-filling for time series (huge for dashboards)
- **Cohort analysis** — Built-in syntax for a notoriously complex pattern
- **Date conveniences** — `7 days ago`, `+ 14 days`, cross-dialect normalization
- **Convention-based inference** — `user_id` auto-joins, `created_at` auto-sorts
- **Window shortcuts** — `per customer first by -date` for deduplication

These address real pain points in analytics workflows that we don't prioritize. We focus on "better programming language for data"; they focus on "better analytics language."

> **Key insight**: ASQL isn't trying to be a better PRQL. It's trying to be **SQL with analytics superpowers**. The pipeline syntax is just a vehicle for the analytics features.

---

## 6. What Should PRQL Learn From ASQL?

### Consider Adopting

1. **Guaranteed groups / auto-spine**: This is genuinely useful for analytics. We could add a `fill` or `complete` transform.

2. **Date arithmetic syntax**: `+ 7 days` is nicer than our function-based approach.

3. **Relative dates**: `7 days ago` is more readable than manual calculation.

### Don't Adopt

1. **SQL vocabulary**: Our vocabulary is intentionally better. Don't regress.

2. **Convention-based FK inference**: Too magical, conflicts with our explicit philosophy.

3. **Auto-aliasing**: We prefer explicit naming.

4. **`#` count shorthand**: Cute but not essential.

---

## 7. Competitive Positioning

### Where PRQL Wins

- Complex queries requiring abstraction (`func`, `let`)
- Teams who value explicit, orthogonal design
- Developers with programming language backgrounds
- Use cases beyond analytics (ETL, data engineering)

### Where ASQL Wins

- SQL users who want minimal learning curve
- Analytics-heavy workflows (dashboards, time series)
- Teams with strong naming conventions
- Quick ad-hoc queries

### Market Implications

ASQL will capture users who:
- Tried PRQL and found vocabulary changes off-putting
- Want pipeline syntax but not a "new language"
- Prioritize analytics-specific features

We should consider whether PRQL needs a "SQL compatibility mode" or if we're comfortable ceding this audience.

---

## 8. Recommendations for PRQL

1. **Don't panic**: ASQL solves a different problem. Our abstraction story (`func`, `let`) is a moat they can't easily cross.

2. **Consider guaranteed groups**: This is a good idea we should evaluate.

3. **Improve date handling**: Their `+ 7 days` and `ago` syntax is better than ours.

4. **Stay the course on vocabulary**: Our intentional verbs are a feature, not a bug.

5. **Target different messaging**: We're for "developers who want a better language." They're for "SQL users who want fewer keystrokes."

---

## Appendix: Code Comparison

### Simple Query

PRQL:
```prql
from orders
filter status == "completed"
sort {-created_at}
take 10
```

ASQL:
```asql
from orders
  where status = "completed"
  order by -created_at
  limit 10
```

**Verdict**: Nearly identical. ASQL uses SQL keywords; we use cleaner verbs.

### Aggregation

PRQL:
```prql
from orders
group customer_id (
  aggregate {
    total = sum amount,
    orders = count this
  }
)
sort {-total}
```

ASQL:
```asql
from orders
  group by customer_id (
    sum(amount) as total,
    # as orders
  )
  order by -total
```

**Verdict**: Similar structure. We separate `group`/`aggregate`; they combine them.

### Complex Analytics (ASQL's strength)

ASQL:
```asql
from orders
  where created_at >= @2024-01-01 and created_at < @2025-01-01
  group by month(created_at) ( sum(amount) ?? 0 as revenue )
  -- All 12 months guaranteed to appear
```

PRQL (equivalent):
```prql
# Would require manual date spine CTE
# No built-in gap-filling
```

**Verdict**: ASQL wins here. Guaranteed groups is a real feature we lack.

### Abstraction (PRQL's strength)

PRQL:
```prql
func revenue_metrics -> (
  aggregate {
    total = sum amount,
    avg = average amount,
    orders = count this
  }
)

from orders
group region (revenue_metrics)
```

ASQL (equivalent):
```asql
# No user-defined functions
# Must repeat aggregation logic everywhere
```

**Verdict**: PRQL wins here. Our abstraction capabilities are unmatched.

