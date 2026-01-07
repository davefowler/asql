# Vocabulary Analysis: Is PRQL's Vocabulary Objectively "Better"?

**Date**: January 6, 2026  
**Question**: PRQL uses `filter`, `derive`, `take`, `sort`. ASQL uses `where`, `select`, `limit`, `order by`. Is PRQL's vocabulary objectively better, or just different?

---

## Executive Summary

PRQL's vocabulary is **more intentional and consistent** from a language design perspective. However, "better" depends on what you optimize for:

| Criterion | PRQL Wins | ASQL Wins |
|-----------|-----------|-----------|
| Unambiguous meaning | ✅ | |
| Orthogonal design | ✅ | |
| Conciseness | ✅ | |
| Learning curve | | ✅ |
| SQL knowledge transfer | | ✅ |
| Team adoption friction | | ✅ |

**Verdict**: PRQL's vocabulary is cleaner from first principles. ASQL's vocabulary is more practical for adoption.

---

## 1. The Vocabulary Comparison

| Operation | PRQL | ASQL/SQL | What it does |
|-----------|------|----------|--------------|
| Filter rows | `filter` | `where` | Keep rows matching condition |
| Add columns | `derive` | `select *, ... as` | Add new columns |
| Choose columns | `select` | `select` | Pick which columns |
| Limit rows | `take` | `limit` | First N rows |
| Sort | `sort` | `order by` | Order rows |
| Aggregate | `aggregate` | inline in `group by ()` | Compute aggregates |

---

## 2. Where PRQL's Vocabulary Is Objectively Better

### 2.1 `filter` vs `where` — Unambiguous

**The problem with `where`:**

SQL uses `WHERE` for two different things:
1. Row filtering before aggregation → `WHERE`
2. Row filtering after aggregation → `HAVING`

```sql
SELECT region, SUM(amount) as revenue
FROM orders
WHERE status = 'completed'   -- filters rows
GROUP BY region
HAVING SUM(amount) > 1000    -- filters groups (different!)
```

**Why `filter` is better:**

PRQL uses `filter` for both cases. The position in the pipeline determines when it applies:

```prql
from orders
filter status == "completed"   # before group
group region (aggregate {revenue = sum amount})
filter revenue > 1000           # after group (HAVING equivalent)
```

No `HAVING` keyword. Just `filter` in the right place.

**ASQL's approach:**

ASQL uses `where` for both, which is the same resolution as PRQL but keeps the confusing SQL vocabulary:

```asql
from orders
  where status = "completed"   -- before group
  group by region (sum(amount) as revenue)
  where revenue > 1000         -- after group (like HAVING)
```

**Verdict**: PRQL's `filter` is objectively less confusing. ASQL improves the semantics but keeps the confusing word.

---

### 2.2 `derive` vs `select *, ...` — Dedicated Verb

**The problem with `select`:**

SQL's `SELECT` does multiple things:
1. Choose which columns to output
2. Add new computed columns
3. Rename columns
4. Sometimes, nothing (just pass through)

When you want to ADD a column without listing all existing ones:

```sql
-- SQL: Must use *, which has its own problems
SELECT *, amount * quantity AS total FROM orders
```

**Why `derive` is better:**

PRQL has a dedicated verb for "add columns":

```prql
from orders
derive total = amount * quantity
```

Crystal clear: "derive" means "add a new column." The original columns are preserved implicitly.

**ASQL's approach:**

ASQL uses the `select *, ...` pattern:

```asql
from orders
  select *, amount * quantity as total
```

This works but:
- Requires the `*` to preserve columns
- `select` is overloaded (choosing vs adding)

**Verdict**: PRQL's `derive` is objectively clearer. It's a dedicated tool for a specific job.

---

### 2.3 `take` vs `limit` — Simplicity

**The problem with `limit`:**

`LIMIT` is fine, but it's SQL jargon. What does "limit" mean to a non-programmer? "take 10" is more natural.

```prql
from orders
take 10
```

vs

```asql
from orders
  limit 10
```

**Verdict**: `take` is marginally better (one syllable, more natural). This is a small difference.

---

### 2.4 `sort` vs `order by` — Conciseness

**The problem with `order by`:**

Two words where one would do. "sort" is universally understood.

```prql
from orders
sort {-amount}
```

vs

```asql
from orders
  order by -amount
```

**Verdict**: `sort` is cleaner. But `order by` is familiar to every SQL user.

---

### 2.5 `aggregate` vs inline syntax — Orthogonality

**PRQL's approach:**

PRQL separates `group` (partitioning) from `aggregate` (computing):

```prql
from orders
group customer_id (
  aggregate {
    total = sum amount,
    count = count this
  }
)
```

These are orthogonal:
- `group` without `aggregate` → partition data
- `aggregate` without `group` → aggregate entire table

**ASQL's approach:**

ASQL combines them:

```asql
from orders
  group by customer_id (
    sum(amount) as total,
    # as count
  )
```

**Verdict**: PRQL's separation is more orthogonal. ASQL's is more concise for the common case but less flexible.

---

## 3. Where ASQL's Vocabulary Is Pragmatically Better

### 3.1 Zero Learning Curve

Every SQL user already knows:
- `where` → filter
- `order by` → sort
- `limit` → limit
- `select` → columns
- `group by` → aggregation

ASQL leverages this knowledge. PRQL requires learning new vocabulary.

**Real-world impact:**

- ASQL: "I can read this immediately"
- PRQL: "What's `derive`? What's `take`? Let me check the docs"

For team adoption, this matters. Every new vocabulary word is a training cost.

### 3.2 Code Review Friction

When reviewing ASQL:
- Reviewers understand what `where` does
- No mental translation required
- SQL knowledge applies directly

When reviewing PRQL:
- Reviewers need PRQL knowledge
- Mental translation to SQL concepts
- Different vocabulary for same operations

### 3.3 Interoperability

ASQL's SQL vocabulary makes it easier to:
- Mix ASQL and SQL in the same codebase
- Explain queries to SQL-only colleagues
- Transition gradually from SQL

---

## 4. The Real Question: What Are You Optimizing For?

### PRQL optimizes for: Language Purity

- Unambiguous: Every word has one meaning
- Orthogonal: Operations are independent
- Intentional: Vocabulary designed from scratch
- Consistent: No historical baggage

This is the "better language" perspective. If you were designing a query language from scratch with no constraints, PRQL's vocabulary is cleaner.

### ASQL optimizes for: Adoption Friction

- Familiar: SQL knowledge transfers
- Low barrier: No new vocabulary to learn
- Team-friendly: Everyone can read it
- Safe migration: Small step from SQL

This is the "better for adoption" perspective. If you want SQL users to switch, ASQL has lower friction.

---

## 5. Objective Analysis: Which Words Are "Better"?

Let me score each vocabulary choice:

| Operation | Clarity | Conciseness | Familiarity | Winner |
|-----------|---------|-------------|-------------|--------|
| `filter` vs `where` | PRQL | Tie | ASQL | **PRQL** (clarity matters more) |
| `derive` vs `select *` | PRQL | PRQL | ASQL | **PRQL** (dedicated verb) |
| `take` vs `limit` | Tie | PRQL | ASQL | **Tie** |
| `sort` vs `order by` | Tie | PRQL | ASQL | **Slight PRQL** |
| `aggregate` vs inline | PRQL | ASQL | ASQL | **Depends on use case** |

**Overall**: PRQL wins on language design criteria (3-4 out of 5). ASQL wins on adoption criteria (5 out of 5).

---

## 6. The Deeper Issue: Is "Better" Even the Right Question?

### Different Goals = Different "Better"

**PRQL's goal**: Create a better language for data transformation.
**ASQL's goal**: Create a better SQL for analytics.

These are different goals:
- PRQL is willing to sacrifice familiarity for cleaner design
- ASQL is willing to sacrifice cleaner design for faster adoption

### The Market Reality

There are ~10 million SQL users worldwide. Most of them:
- Know SQL vocabulary deeply
- Have muscle memory for SQL keywords
- Work in teams where SQL is the standard
- Don't want to learn a "new language"

PRQL asks: "Learn our better vocabulary"
ASQL asks: "Keep your SQL knowledge, add pipelines"

Both are valid strategies for different audiences.

---

## 7. What ASQL Could Learn

### 7.1 Consider `derive`

ASQL's biggest vocabulary gap is the lack of a dedicated "add columns" verb. The `select *, ... as` pattern is verbose.

Options:
- Add `derive` (like PRQL)
- Add `add` or `with` (more SQL-like)
- Keep current syntax (avoid scope creep)

### 7.2 Explain the `where`/`HAVING` Resolution

ASQL's docs should explicitly explain that `where` after `group by` is like `HAVING`. This is a feature, but it's not obvious.

### 7.3 Don't Chase PRQL's Vocabulary

ASQL's vocabulary strategy is deliberate. Chasing PRQL's cleaner words would:
- Alienate the "SQL familiarity" audience
- Reduce differentiation
- Add vocabulary learning cost

Stay the course.

---

## 8. Conclusion

### Is PRQL's Vocabulary "Better"?

**From a language design perspective**: Yes. `filter`, `derive`, `take`, `sort` are cleaner, more intentional words that avoid SQL's historical baggage.

**From an adoption perspective**: No. SQL vocabulary transfers instantly, requires no learning, and works in mixed teams.

### The Tradeoff

| Strategy | Advantage | Disadvantage |
|----------|-----------|--------------|
| PRQL (new vocabulary) | Cleaner language | Learning curve |
| ASQL (SQL vocabulary) | Instant familiarity | Inherited confusion |

### Final Verdict

PRQL's vocabulary is **objectively cleaner** but not **objectively better**. "Better" depends on what you value:

- **Value language purity?** → PRQL's vocabulary is better
- **Value adoption speed?** → ASQL's vocabulary is better
- **Value both?** → Pick your tradeoff

ASQL explicitly chose "Familiarity Over Novelty." This is a valid choice, not a compromise. The vocabulary is intentionally conservative.

---

## Appendix: Vocabulary Decision Framework

If ASQL ever considers vocabulary changes, use this framework:

| Question | If Yes | If No |
|----------|--------|-------|
| Does SQL have a confusing word for this? | Consider new word | Keep SQL word |
| Is the new word obviously clearer? | Consider new word | Keep SQL word |
| Will SQL users understand it instantly? | Keep SQL word | Consider new word |
| Does it add learning curve? | Keep SQL word | Consider new word |
| Is there a dedicated verb missing? | Consider new word | Keep current syntax |

**Current gaps:**
- `derive` / "add columns" — Missing dedicated verb
- `filter` — Would be cleaner but too late to change

**Not worth changing:**
- `where` → `filter` (too disruptive)
- `order by` → `sort` (marginal benefit)
- `limit` → `take` (marginal benefit)

