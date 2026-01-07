# Critical Comparison: ASQL vs PRQL

**Date**: January 6, 2026  
**Purpose**: Analyze whether ASQL warrants existence as a separate dialect from PRQL, evaluate syntax choices, and assess differentiation

---

## Executive Summary

ASQL and PRQL share pipeline-first syntax, but **solve different problems**:

- **PRQL** = "A better programming language for data" (orthogonal primitives, composability, abstraction)
- **ASQL** = "SQL with analytics superpowers" (built-in analytics features, familiar vocabulary)

The syntax similarity is superficial. The **real differentiation** is ASQL's analytics-specific features:

| ASQL Feature | What it solves | PRQL equivalent |
|--------------|----------------|-----------------|
| **Guaranteed groups** | Time series gap-filling for dashboards | None (DIY) |
| **Cohort analysis** | Complex retention queries in 3 lines | None (DIY) |
| **`per X first by`** | Deduplication in 1 line | `group X (sort ... \| take 1)` |
| **`7 days ago`** | Relative dates | Function calls |
| **Convention inference** | Auto-join on `user_id` | Explicit specification |
| **Cross-dialect dates** | `month(x)` works everywhere | Dialect-specific |

| Aspect | PRQL | ASQL |
|--------|------|------|
| **Core goal** | Better language primitives | Analytics-specific tooling |
| **Vocabulary** | New verbs (`filter`, `derive`) | SQL verbs (`where`, `select`) |
| **Power source** | Abstraction (`let`, `func`) | Built-in analytics features |
| **Target user** | Developers, data engineers | Analysts, analytics engineers |

**Verdict**: ASQL is **not** "PRQL with different syntax." It's a different product category—analytics tooling vs. language design.

---

## 1. Stated Design Principles

### PRQL's Principles (from their docs)

1. **Pipelined** — Linear pipeline of transformations
2. **Simple** — Small set of powerful, orthogonal primitives
3. **Open** — Open-source, compiles to SQL, database-agnostic
4. **Extensible** — Functions and language bindings for growth
5. **Analytical** — Focuses on data transformations, not transactions

### ASQL's Design Values (from `docs/concepts/index.md`)

1. **Pipeline Order Over Projection-First** — Written order = execution order
2. **Convention Over Configuration** — Infer from naming patterns
3. **Familiarity Over Novelty** — Keep SQL vocabulary
4. **Portable Over Proprietary** — Transpile to any dialect
5. **Completeness Over Fast Queries** — Guaranteed groups, gap-filling
6. **Code Comments Over Catalogues** — Documentation in queries

### Key Philosophical Differences

| Dimension | PRQL | ASQL |
|-----------|------|------|
| **Vocabulary strategy** | Invent cleaner verbs | Keep familiar SQL verbs |
| **Power source** | Orthogonal primitives + extensibility | Smart defaults + conventions |
| **Error prevention** | Type safety, composability | Gap-filling, auto-aliasing |
| **Configuration** | Explicit (you specify) | Implicit (ASQL infers) |

---

## 2. Core Similarities (The Shared Insight)

Both languages recognize SQL's fundamental flaw:

```sql
-- SQL: Written order ≠ Execution order
SELECT region, SUM(amount)     -- 5th (executed)
FROM sales                      -- 1st
WHERE year = 2024               -- 2nd
GROUP BY region                 -- 3rd
HAVING SUM(amount) > 1000       -- 4th
ORDER BY 2 DESC                 -- 6th
```

Both fix this with **pipeline-first syntax**:

### PRQL
```prql
from employees
filter start_date > @2021-01-01
derive {
  gross_salary = salary + (tax ?? 0),
  gross_cost = gross_salary + benefits_cost,
}
group department (
  aggregate {average_salary = average salary}
)
sort average_salary
```

### ASQL
```asql
from employees
  where start_date > @2021-01-01
  select *, salary + (tax ?? 0) as gross_salary
  group by department ( avg(salary) as average_salary )
  order by average_salary
```

**Shared syntax elements:**
- `from` at the top
- `@` prefix for date literals
- `??` for COALESCE
- Pipeline structure (top-to-bottom flow)
- Compile to SQL

---

## 3. Vocabulary Choices: Familiar vs Novel

| Operation | PRQL | ASQL | Difference |
|-----------|------|------|------------|
| Filter rows | `filter` | `where` | PRQL invents; ASQL keeps SQL |
| Add columns | `derive` | `select *, ... as col` | PRQL has dedicated verb |
| Limit rows | `take` | `limit` | PRQL simpler; ASQL familiar |
| Sort | `sort` | `order by` | PRQL simpler; ASQL familiar |
| Descending | `sort {-amount}` | `order by -amount` | Same |
| Aggregate | `aggregate` | `group by ... ( )` | PRQL separates; ASQL combines |

**PRQL's approach**: Invent cleaner, more intentional verbs. `filter` is unambiguous (vs SQL's `WHERE`/`HAVING` confusion). `derive` is clearer than `SELECT *, ...`.

**ASQL's approach**: Keep SQL vocabulary so knowledge transfers. Every SQL user already knows `where`, `limit`, `order by`.

---

## 4. The Big Difference: Abstraction vs Convention

### PRQL: Abstraction via Variables and Functions

PRQL emphasizes **extensibility** through user-defined abstractions:

```prql
# Define a reusable function
func fiscal_year date -> (date + 6m) | year

# Use it
from orders
derive fy = fiscal_year order_date
group fy (aggregate {total = sum amount})
```

```prql
# Define a variable
let threshold = 1000

from orders
filter amount > threshold
```

**What this enables:**
- Reusable query logic
- Parameterized transformations
- Library-like composition
- DRY (Don't Repeat Yourself) queries

### ASQL: Convenience via Conventions

ASQL emphasizes **convention over configuration**:

```asql
-- FK inference: user_id → .user. traversal
from orders
  select orders.user.name  -- auto-joins via user_id

-- Auto-aliasing: no explicit names needed
from orders
  group by month(created_at) ( sum(amount) )
  -- columns: month_created_at, sum_amount

-- Guaranteed groups: all months appear
from orders
  where created_at >= @2024-01-01 and created_at < @2025-01-01
  group by month(created_at) ( sum(amount) ?? 0 as revenue )
```

**What this enables:**
- Less typing for common patterns
- Fewer errors (auto-aliasing, gap-filling)
- Works out-of-the-box if you follow naming conventions
- Focus on *what* you want, not *how* to get it

### Comparison

| Capability | PRQL Approach | ASQL Approach |
|------------|---------------|---------------|
| Reuse logic | `func` definitions | Not implemented |
| Named subexpressions | `let` variables | `stash as` CTEs |
| Join automation | Explicit `join` with `==` | FK inference via `.user.` |
| Column naming | Manual | Auto-aliasing |
| Missing data | Manual handling | Guaranteed groups |
| Date math | Functions | `+ 7 days` syntax |

---

## 5. Features Unique to Each Language

### PRQL Unique Features

| Feature | Description | ASQL Status |
|---------|-------------|-------------|
| `let` variables | Named subexpressions | Not implemented |
| `func` definitions | User-defined functions | Not implemented |
| `derive` | Dedicated column-add verb | Use `select *, ...` |
| `window` transform | Explicit window context | `per` command |
| Tuple literals `{}` | Grouping syntax | Uses parentheses |
| `loop` | Recursive CTEs | Not implemented |

### ASQL Unique Features

| Feature | Description | PRQL Status |
|---------|-------------|-------------|
| Convention-based FK inference | `.owner.name` auto-joins | Must specify joins |
| Guaranteed groups | All dimension values appear | Manual handling |
| Auto-aliasing | `sum(amount)` → `sum_amount` | No default aliasing |
| `#` count shorthand | `# users` = COUNT(DISTINCT user_id) | `count` keyword |
| `contains/starts with/ends with` | String matching operators | `contains` function |
| Date arithmetic `+ 7 days` | Natural date math | Function-based |
| `ago` / `from now` | Relative dates | Manual calculation |
| `days_since_created_at` | Magic date diff pattern | Not available |
| `cohort by` | First-class cohort analysis | Manual CTEs |
| Case-safe identifiers | `firstName` matches `first_name` | Case-sensitive |

---

## 6. Syntax "Sugar" vs Semantic Differences

### Pure Syntactic Sugar (Same semantics)

| Concept | PRQL | ASQL |
|---------|------|------|
| Descending sort | `sort {-col}` | `order by -col` |
| Null coalescing | `??` | `??` |
| Date literals | `@2024-01-01` | `@2024-01-01` |

### Semantic Enhancements in ASQL

These add capabilities, not just syntax:

| Feature | What it does | Why it's semantic |
|---------|--------------|-------------------|
| Convention-based joins | Auto-infers FK relationships | Reduces query complexity |
| Guaranteed groups | Ensures all dimension values appear | **Changes output cardinality** |
| Auto-aliasing | Names columns automatically | Eliminates naming errors |
| `cohort by` | Generates ~50 lines of SQL | Structural transformation |

### Semantic Enhancements in PRQL

| Feature | What it does | Why it's semantic |
|---------|--------------|-------------------|
| `func` definitions | Reusable, parameterized queries | Abstraction capability |
| `let` variables | Named subexpressions | Reduces duplication |
| `loop` | Recursive CTEs | Enables graph traversal |
| `derive` | Adds columns without listing existing | Different operation than SELECT |

---

## 7. Which Syntax Choices Are "Better"?

### PRQL Wins

| Choice | Why it's better |
|--------|----------------|
| `filter` over `where` | Unambiguous (vs `WHERE`/`HAVING`) |
| `derive` | Clearer than `select *, ...` |
| `take` | Simpler than `limit` |
| `{}` blocks | Consistent grouping syntax |
| `sort` | One word instead of two |

### ASQL Wins

| Choice | Why it's better |
|--------|----------------|
| `where` | Zero learning curve for SQL users |
| `group by ... ( )` | Groups and aggregates together |
| `#` for count | Extremely concise |
| Join symbols (`&?`) | Compact, visually distinct |
| `-` for descending | Both use this; good choice |

### Neither Clearly Better

| Choice | Trade-offs |
|--------|------------|
| Pipeline syntax | Both work; different styles |
| Aggregation syntax | PRQL separates `group`/`aggregate`; ASQL combines |

---

## 8. Is ASQL "Too Similar" to PRQL?

### Surface Similarity

On first glance, ASQL looks like "PRQL with SQL keywords":

```prql
# PRQL
from orders
filter amount > 100
take 10
```

```asql
# ASQL
from orders
  where amount > 100
  limit 10
```

This similarity is intentional—both solve the same core problem.

### Deep Differentiation

But the design values diverge significantly:

| Dimension | PRQL | ASQL |
|-----------|------|------|
| **Power source** | Abstraction (func, let) | Convention (inference, defaults) |
| **Vocabulary** | Invent new verbs | Keep SQL verbs |
| **Configuration** | Explicit | Implicit |
| **Unique capability** | Reusable query components | Automatic completeness |

### The "Should This Exist?" Test

A new language should exist if it serves needs that existing tools don't.

**PRQL's niche**: Developers who want clean abstractions and composability.

**ASQL's niche**: Users who want:
- Less boilerplate (FK inference, auto-aliasing)
- Automatic correctness (guaranteed groups)
- Zero vocabulary learning (SQL familiarity)

**Verdict**: There's room for both. They optimize for different things.

---

## 9. "Too Inventive" Evaluation

### ASQL's Inventive Features

| Feature | Inventiveness | Justification |
|---------|---------------|---------------|
| `#` for count | Medium | Novel but intuitive |
| `&?` join symbols | High | Unfamiliar but logical |
| `.owner.` FK traversal | Medium | Magic, but convention-based |
| Guaranteed groups | High | Semantic change; analytics-focused |
| `cohort by` | High | Domain-specific; huge productivity gain |
| `days_since_*` | Medium | Magic naming; powerful |

### Risk Assessment

**Conservative core** (easy adoption):
- Pipeline syntax
- SQL vocabulary (`where`, `order by`, `limit`)
- `??`, `@` date literals
- `contains`, `starts with` operators

**Inventive edges** (differentiation):
- Convention-based inference
- Guaranteed groups
- Cohort analysis
- Auto-aliasing

This balance is deliberate: **familiar syntax + powerful conventions**.

---

## 10. Conclusion

### PRQL's Strengths
- Clean, consistent language design
- Powerful abstraction (functions, variables)
- Orthogonal primitives
- "Programming language" aesthetics

### ASQL's Strengths
- Zero vocabulary learning curve
- Convention-based automation
- Analytics-specific features (guaranteed groups, cohorts)
- Less configuration needed

### The Real Differentiation

**PRQL focuses on**: Extensibility and composability via explicit abstractions.

**ASQL focuses on**: Convenience and correctness via implicit conventions.

These are complementary philosophies, not competing ones.

### Recommendation

ASQL should:
1. **Lean into conventions** — FK inference, auto-aliasing, guaranteed groups
2. **Keep SQL vocabulary** — this is a feature, not a limitation
3. **Not copy PRQL's abstraction features** — let PRQL own `func` and `let`
4. **Double down on analytics features** — cohorts, date handling, gap-filling
5. **Target breadth of audience** — developers AND analysts

---

## Appendix: Side-by-Side Examples

### Example 1: Monthly Revenue by Region

**SQL:**
```sql
SELECT 
    DATE_TRUNC('month', order_date) AS month,
    region,
    SUM(amount) AS revenue
FROM orders
WHERE order_date >= '2024-01-01'
GROUP BY 1, 2
ORDER BY month, revenue DESC
```

**PRQL:**
```prql
from orders
filter order_date >= @2024-01-01
group {month = order_date | date.month, region} (
  aggregate {revenue = sum amount}
)
sort {month, -revenue}
```

**ASQL:**
```asql
from orders
  where order_date >= @2024-01-01
  group by month(order_date), region ( sum(amount) as revenue )
  order by month_order_date, -revenue
```

### Example 2: Latest Order per Customer

**SQL:**
```sql
WITH ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS rn
    FROM orders
)
SELECT * FROM ranked WHERE rn = 1
```

**PRQL:**
```prql
from orders
group customer_id (
  sort {-order_date}
  take 1
)
```

**ASQL:**
```asql
from orders
  per customer_id first by -order_date
```

### Example 3: Guaranteed Complete Time Series (ASQL-specific)

**ASQL:**
```asql
from orders
  where created_at >= @2024-01-01 and created_at < @2025-01-01
  group by month(created_at) ( sum(amount) ?? 0 as revenue )
```

All 12 months appear, even those with zero revenue.

**SQL equivalent:** ~25 lines with `generate_series` and LEFT JOIN.

**PRQL:** Manual handling required.

---

## References

- [PRQL Language Documentation](https://prql-lang.org/)
- [ASQL Design Values](../docs/concepts/index.md)
- [ASQL Guaranteed Groups](../docs/concepts/guaranteed-groups.md)
- [ASQL Conventions](../docs/concepts/conventions.md)
