# Set Theory Ancestors: Pre-SQL Database Languages

**Last Updated**: December 2025

This document explores early database query languages that were grounded in set theory and relational algebra—before SQL won the standards war. Many of these languages had elegant approaches that SQL abandoned in favor of "English-like" syntax. ASQL can learn from both their successes and their market failures.

---

## The Historical Context

In the early 1970s, Edgar F. Codd published his landmark papers on the relational model. This sparked a wave of implementations, each taking different approaches to query language design:

| Year | Language | Origin | Basis |
|------|----------|--------|-------|
| 1970 | MICRO | U of Michigan | Set theory, natural language |
| 1971 | Alpha | IBM (Codd) | Relational calculus (never implemented) |
| 1974 | SQUARE | IBM (Boyce/Chamberlin) | Relational algebra |
| 1974 | SEQUEL | IBM | SQUARE simplified → became SQL |
| 1976 | QUEL | UC Berkeley (Ingres) | Tuple relational calculus |
| 1977 | QBE | IBM (Zloof) | Visual/tabular queries |
| 1969-79 | SETL | NYU | Pure set theory |
| 1977+ | Datalog | Various | Logic programming |

SQL (then SEQUEL) won primarily due to IBM's market power and aggressive standardization, not because it was technically superior. In fact, QUEL was widely considered more elegant and closer to Codd's original vision.

---

## The Key Languages

### 1. QUEL (Query Language) — Berkeley/Ingres

QUEL was the query language for Ingres, developed at UC Berkeley. It was based on tuple relational calculus and had several advantages over SQL.

**QUEL Example:**
```quel
range of e is employee
retrieve (e.name, e.salary)
where e.dept = "sales" and e.salary > 50000
```

**Equivalent SQL:**
```sql
SELECT name, salary
FROM employee e
WHERE dept = 'sales' AND salary > 50000
```

**QUEL Advantages:**
- **Explicit range variables**: `range of e is employee` made the scope crystal clear
- **Consistent syntax**: `retrieve`, `append`, `replace`, `delete` all followed the same pattern
- **No SELECT/FROM ordering confusion**: The data source is declared first, then the projection
- **Aggregate handling was cleaner**:

```quel
-- QUEL aggregation
range of e is employee  
retrieve (e.dept, avg_sal = avg(e.salary by e.dept))

-- vs SQL's GROUP BY weirdness
SELECT dept, AVG(salary) as avg_sal
FROM employee
GROUP BY dept
```

**What ASQL Already Learned**: ASQL's pipeline model with `from` first is essentially the QUEL ordering! We already adopted their best idea.

### 2. Alpha — Codd's Original Vision

Alpha was Codd's own proposed language, never implemented but hugely influential. It was a pure relational calculus language.

**Alpha Example:**
```alpha
GET W (EMPLOYEE.NAME, EMPLOYEE.SALARY) : EMPLOYEE.DEPT = 'SALES'
```

**Key Insight**: Alpha treated queries as mathematical set definitions—"get me the set W where these conditions hold." This is closer to how analysts actually think.

### 3. SETL — Pure Set Theory

SETL (SET Language) from NYU was a general-purpose language built entirely on set theory. Its data structures were sets, tuples, and maps.

**SETL Example:**
```setl
-- All employees in sales making over 50k
{[name, salary] : [name, dept, salary] in employees | dept = "sales" and salary > 50000}
```

**This is essentially set-builder notation from mathematics!**

Compare to Python's list comprehension (which SETL influenced):
```python
[(name, salary) for name, dept, salary in employees if dept == "sales" and salary > 50000]
```

**Key Insight**: Set comprehensions are incredibly expressive. Python, Haskell, and other modern languages adopted this pattern.

### 4. Datalog — Logic Programming

Datalog emerged from Prolog and treats queries as logical rules and facts.

**Datalog Example:**
```datalog
-- Define a rule
high_earner(Name, Salary) :- employee(Name, Dept, Salary), Dept = "sales", Salary > 50000.

-- Query
?- high_earner(X, Y).
```

**Datalog Advantages:**
- **Recursion is native**: Graph traversals, hierarchies, transitive closures are trivial
- **Rules are reusable**: Define a rule once, use it everywhere
- **Composable**: Rules can reference other rules

**Key Insight**: SQL's lack of easy recursion (CTEs are verbose) is a major pain point. Datalog handles this elegantly.

### 5. QBE (Query By Example) — Visual Queries

QBE took a radically different approach: queries were expressed by filling in example tables.

```
| employee | name   | dept    | salary |
|----------|--------|---------|--------|
|          | P._n   | "sales" | P._s   |
|          |        |         | >50000 |
```

**Key Insight**: Visual representation of queries. This influenced early Access, early Excel, and modern BI tools. The tabular thinking is powerful.

---

## Where SQL Went Wrong (From a Set Theory Perspective)

### 1. **Bags vs Sets**

SQL operates on "bags" (multisets with duplicates) not true sets. This was a pragmatic choice for performance but breaks mathematical consistency.

```sql
-- SQL allows duplicates by default
SELECT dept FROM employees;  -- May return duplicates

-- Must explicitly request set semantics
SELECT DISTINCT dept FROM employees;
```

**The Problem**: In relational algebra, a relation IS a set—duplicates are impossible by definition. SQL's bag semantics mean:
- `UNION` vs `UNION ALL` confusion
- Need for `DISTINCT` everywhere
- Harder query optimization (can't use set identities freely)

### 2. **NULL and Three-Valued Logic**

SQL's NULL creates a three-valued logic (TRUE, FALSE, UNKNOWN) that violates basic laws of logic.

```sql
-- In SQL, this is FALSE not TRUE:
NULL = NULL  -- Returns NULL (unknown), not TRUE

-- The law of excluded middle is violated:
WHERE x = 1 OR x != 1 OR x IS NULL  -- Need all three conditions!
```

**Codd and Date have written extensively** about how NULL poisons SQL's mathematical foundations.

### 3. **Missing Relational Operations**

SQL lacks direct support for several fundamental relational algebra operations:

| Operation | Relational Algebra | SQL Equivalent |
|-----------|-------------------|----------------|
| **Division** | A ÷ B | Complex double-NOT EXISTS pattern |
| **Semijoin** | A ⋉ B | SELECT * FROM A WHERE EXISTS (...) |
| **Antijoin** | A ▷ B | SELECT * FROM A WHERE NOT EXISTS (...) |
| **Natural Join** | A ⨝ B | NATURAL JOIN (rarely used, dangerous) |

**Relational Division Example** — "Find employees who work on ALL projects":

```sql
-- SQL: This is insane
SELECT DISTINCT e.name
FROM employees e
WHERE NOT EXISTS (
    SELECT p.id FROM projects p
    WHERE NOT EXISTS (
        SELECT * FROM assignments a
        WHERE a.emp_id = e.id AND a.proj_id = p.id
    )
);

-- Relational Algebra: Simple division
employees ÷ projects
```

### 4. **SELECT Before FROM is Backwards**

SQL's `SELECT ... FROM ... WHERE` ordering is the opposite of logical data flow:
1. You start with a table (FROM)
2. Filter it (WHERE)  
3. Then project columns (SELECT)

But SQL makes you write the projection first!

```sql
-- SQL: Projection first (backwards)
SELECT name, salary FROM employees WHERE dept = 'sales';

-- QUEL: Source first (natural)
range of e is employee
retrieve (e.name, e.salary) where e.dept = 'sales'
```

**ASQL already fixed this!** Pipeline syntax puts `from` first.

### 5. **GROUP BY Repetition**

SQL forces you to repeat columns:

```sql
SELECT 
    dept,
    location,
    COUNT(*) as num_employees
FROM employees
GROUP BY dept, location;  -- Why repeat dept, location?
```

**The grouping columns are already implied by the SELECT!**

---

## Lessons for ASQL

### ✅ Already Adopted

ASQL has already learned from these ancestors:

| Feature | Source | ASQL Status |
|---------|--------|-------------|
| `from` first | QUEL | ✅ Implemented |
| Pipeline semantics | QUEL, PRQL | ✅ Implemented |
| Implicit grouping | Set theory | ✅ Implemented (`group by x (sum y)`) |
| Natural language feel | MICRO | ✅ Design goal |

### 🔶 Potential Additions

Features ASQL could adopt:

#### 1. **Set Comprehension Syntax** (from SETL)

```asql
-- Current ASQL
from employees
  where dept == "sales" and salary > 50000
  select name, salary

-- Potential comprehension syntax for simple queries?
{name, salary : employees | dept == "sales", salary > 50000}
```

**Verdict**: Interesting but may confuse users. Keep as exploration.

#### 2. **Explicit Set Operations as First-Class Citizens**

Make UNION, INTERSECT, EXCEPT more natural:

```asql
-- Current (SQL-like)
from sales_2023
union
from sales_2024

-- More set-theoretic
sales_2023 ∪ sales_2024
sales_2023 ∩ sales_2024  
sales_2023 − sales_2024

-- Or named operators
sales_2023 union sales_2024
sales_2023 intersect sales_2024
sales_2023 minus sales_2024
```

**Where is this useful in analytics?**

Honestly, **UNION is already common** and works fine in SQL. The other two are rarer but have real use cases:

**INTERSECT** — Finding overlap between sets:
```sql
-- Customers who bought BOTH product A and product B (cross-sell candidates)
SELECT customer_id FROM orders WHERE product = 'A'
INTERSECT
SELECT customer_id FROM orders WHERE product = 'B'

-- What people do instead: JOIN or EXISTS
SELECT DISTINCT a.customer_id 
FROM orders a
JOIN orders b ON a.customer_id = b.customer_id
WHERE a.product = 'A' AND b.product = 'B'
```

**EXCEPT/MINUS** — Finding what's in one set but not another:
```sql
-- Customers who bought last year but NOT this year (churned)
SELECT customer_id FROM orders WHERE year = 2023
EXCEPT
SELECT customer_id FROM orders WHERE year = 2024

-- What people do instead: LEFT JOIN + IS NULL
SELECT DISTINCT a.customer_id 
FROM orders a
LEFT JOIN orders b ON a.customer_id = b.customer_id AND b.year = 2024
WHERE a.year = 2023 AND b.customer_id IS NULL

-- Or NOT EXISTS
SELECT DISTINCT customer_id FROM orders a
WHERE year = 2023
AND NOT EXISTS (SELECT 1 FROM orders b WHERE b.customer_id = a.customer_id AND b.year = 2024)
```

**Reality check**: INTERSECT and EXCEPT are rarely used because:
1. Most analysts don't know they exist
2. The JOIN patterns are so ingrained
3. INTERSECT/EXCEPT require matching column counts/types

**Verdict**: The named operators (`union`, `intersect`, `minus`) could be cleaner than SQL's approach, but this is **low priority** — the current SQL versions work fine and analysts already know the JOIN patterns.

**Decision**: Low priority. Not a big pain point.

#### 3. **Relational Division** 

Add a `divide by` or `forall` operator:

```asql
-- "Employees who work on ALL projects"
-- Option 1: Explicit division
from assignments
  divide by projects on project_id
  select employee_id

-- Option 2: Universal quantification  
from employees e
  where forall project in projects:
    exists assignment in assignments
      where assignment.emp_id == e.id 
        and assignment.proj_id == project.id
```

**Verdict**: `divide by` would be powerful but niche. Universal quantification (`forall`) aligns with ASQL's natural language goals.

decision: no

#### 4. **Semijoin and Antijoin Operators**

```asql
-- Current: verbose EXISTS pattern
from employees
  where exists (from orders where orders.emp_id == employees.id)

-- Potential: explicit semijoin
from employees
  semijoin orders on emp_id == orders.emp_id

-- Or simpler keywords
from employees
  where has orders (on emp_id)  -- semijoin

from employees  
  where has no orders (on emp_id)  -- antijoin
```

**How does this differ from JOIN + WHERE?**

Great question! The key differences:

| Approach | Columns Returned | Row Multiplication | Performance |
|----------|------------------|-------------------|-------------|
| **JOIN** | Both tables | Yes (1 customer × 5 orders = 5 rows) | May be slower |
| **Semijoin (EXISTS)** | Only left table | No (1 row per customer) | Often faster |

**Example showing the difference:**
```sql
-- Customer has 3 orders. What do we get?

-- JOIN: Returns 3 rows (one per order)
SELECT c.name, c.email
FROM customers c
JOIN orders o ON c.id = o.customer_id;
-- Result: Alice, Alice, Alice

-- Semijoin: Returns 1 row
SELECT c.name, c.email
FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
-- Result: Alice

-- If you JOIN, you need DISTINCT to fix it:
SELECT DISTINCT c.name, c.email
FROM customers c
JOIN orders o ON c.id = o.customer_id;
```

**When semijoin matters:**
1. **"Show me customers who have ANY orders"** — You want 1 row per customer, not 1 row per order
2. **Counting** — `COUNT(*)` after a JOIN gives wrong numbers without careful handling
3. **Performance** — EXISTS can stop at first match; JOIN must find all matches

**What people do now:**
- Many analysts use JOIN + DISTINCT (wasteful, but works)
- Experienced analysts use EXISTS/NOT EXISTS (correct but verbose)
- Some use IN/NOT IN (but NULL handling is dangerous)

**The `has`/`has no` syntax would make this trivial:**
```asql
-- "Customers who have placed orders" - crystal clear intent
from customers
  where has orders (on customer_id)
```

**Verdict**: `has` / `has no` reads naturally and is very ASQL. This is a **real pain point** — the JOIN vs EXISTS distinction trips up analysts constantly, and EXISTS syntax is ugly. This could be a great addition.

**Decision**: High priority. Common need, ugly current syntax.

#### 5. **Recursive Queries Made Easy** (from Datalog)

```asql
-- Current SQL recursive CTE (verbose)
WITH RECURSIVE subordinates AS (
    SELECT id, name, manager_id FROM employees WHERE id = 1
    UNION ALL
    SELECT e.id, e.name, e.manager_id 
    FROM employees e
    JOIN subordinates s ON e.manager_id = s.id
)
SELECT * FROM subordinates;

-- Potential ASQL
from employees
  where id == 1
  recurse through manager_id -> id  -- follow the hierarchy
  
-- Or with explicit rule definition (Datalog-style)
define subordinate_of(emp, boss):
  employees.manager_id == boss
  or subordinate_of(employees.manager_id, boss)

from employees
  where subordinate_of(id, 1)
```

**Can't you just do this with a JOIN or WHERE manager_id = 1?**

**No!** That only gets you ONE level:
- `WHERE manager_id = 1` gets **direct reports** (children)
- But what about their reports? And their reports' reports?

```
CEO (id=1)
├── VP Sales (id=2, manager_id=1)      ← WHERE manager_id=1 finds this
│   ├── Sales Dir (id=5, manager_id=2)  ← NOT found! manager_id=2, not 1
│   │   └── Sales Rep (id=8, manager_id=5)  ← NOT found!
│   └── Sales Dir (id=6, manager_id=2)
└── VP Eng (id=3, manager_id=1)        ← WHERE manager_id=1 finds this
    └── Eng Dir (id=7, manager_id=3)    ← NOT found!
```

**To get all descendants with JOINs, you'd need:**
```sql
-- Level 1 (direct reports)
SELECT * FROM employees WHERE manager_id = 1
UNION
-- Level 2 (reports of reports)
SELECT e2.* FROM employees e1
JOIN employees e2 ON e2.manager_id = e1.id
WHERE e1.manager_id = 1
UNION
-- Level 3...
-- Level 4...
-- How deep does your org go? 🤷
```

You literally can't write this query without knowing the max depth ahead of time!

**How Graph DBs Handle It (Cypher/Neo4j):**
```cypher
-- Get all subordinates at any depth
MATCH (boss:Employee {id: 1})-[:MANAGES*]->(subordinate)
RETURN subordinate

-- The * means "follow this edge any number of times"
-- Can also limit: [:MANAGES*1..3] for 1-3 levels deep
```

**How SQL Does It (Recursive CTE):**
```sql
WITH RECURSIVE org_chart AS (
    -- Base case: start with the CEO
    SELECT id, name, manager_id, 1 as level
    FROM employees WHERE id = 1
    
    UNION ALL
    
    -- Recursive case: add each person's reports
    SELECT e.id, e.name, e.manager_id, o.level + 1
    FROM employees e
    JOIN org_chart o ON e.manager_id = o.id
)
SELECT * FROM org_chart;
```

This works but is **verbose and confusing** for most analysts.

**Common real-world uses:**
- Org charts (who reports to whom)
- Bill of materials (parts containing parts)
- Category trees (electronics > phones > smartphones > iPhones)
- Network graphs (who follows whom, friend-of-friend)
- File systems (folders containing folders)

**Verdict**: Recursion simplification would be huge. The `recurse through` syntax is worth exploring.

**Decision**: Medium priority. Real need, but niche (not every query needs recursion). The syntax is tricky to get right.

#### 6. **Rule Definitions** (from Datalog)

Allow reusable query fragments:

```asql
-- Define reusable rules
define active_user:
  status == "active" and last_login > 30 days ago

define high_value_customer:
  lifetime_value > 10000 or tier == "enterprise"

-- Use in queries
from users
  where active_user and high_value_customer
```

**What does ASQL already have for CTEs?**

ASQL uses **`stash as`** for CTEs (temporary named result sets):

```asql
-- ASQL's `stash as` = SQL's WITH ... AS (CTE)
from users
  where is_active
  stash as active_users

from active_users
  group by country (# as total)
```

This compiles to:
```sql
WITH active_users AS (SELECT * FROM users WHERE is_active)
SELECT country, COUNT(*) as total FROM active_users GROUP BY country
```

**The difference between `stash as` and proposed `define`:**
- **`stash as`** = Named **data** (a result set / temp table)
- **`define`** = Named **logic** (a reusable boolean condition or expression)

```asql
-- `stash as` creates data (a temp table)
from users
  where is_active
  stash as active_users

-- `define` would create reusable logic (a predicate)
define active_user:
  status == "active" and last_login > 30 days ago

-- Used differently:
from active_users               -- `stash as` is a table
from users where active_user    -- `define` is a condition
```

**Should we add `define` for reusable predicates?**

It would be separate from `stash as`:
- `stash as` for **data** (CTEs) — already implemented
- `define` for **rules/predicates** — this would be new

**Better terminology options for rules:**

| Keyword | Pros | Cons |
|---------|------|------|
| `define` | Clear, programming-like | May feel too "code-y" |
| `rule` | Datalog heritage, clear | Unfamiliar |
| `let` | Familiar from JS/Python | Usually for values, not predicates |
| `macro` | Accurate | Scary word |
| `is` pattern | `active_user is: status == "active"` | Natural but novel |

**Potential syntax:**
```asql
-- Option 1: define keyword
define active_user:
  status == "active" and last_login > 30 days ago

-- Option 2: natural "is" pattern  
active_user is:
  status == "active" and last_login > 30 days ago

-- Option 3: arrow syntax
active_user => status == "active" and last_login > 30 days ago
```

**Verdict**: `stash as` handles data/CTEs well. Consider `define` or another keyword for reusable logic/predicates — this would be a new concept.

**Decision**: Low-medium priority. Nice to have, but `stash as` handles most use cases. The distinction between "named data" vs "named logic" may confuse users.

---

## Why SQL Won (Despite Technical Inferiority)

Understanding why SQL won helps ASQL avoid similar traps:

1. **IBM's market power**: IBM standardized SQL; Ingres was academic
2. **"English-like" marketing**: SQL's verbose syntax felt accessible to business users
3. **Standards committee**: SQL became ANSI/ISO standard in 1986
4. **Network effects**: Once SQL won, everyone optimized for it
5. **Good enough**: For most queries, SQL's awkwardness doesn't matter

**Lesson for ASQL**: 
- Don't be too clever or mathematical—accessibility matters
- SQL compatibility (transpilation) is essential for adoption
- Pick battles carefully—improve the 20% of syntax that causes 80% of pain

---

## Feature Prioritization for ASQL

Based on this analysis and the discussion above, here's a revised prioritized list:

### High Priority ⭐

| Feature | Inspiration | Why It's High Priority |
|---------|-------------|------------------------|
| `has` / `has no` semijoins | Relational algebra | **Common need**, ugly EXISTS syntax, JOIN vs EXISTS trips up analysts constantly |

### Medium Priority 🔶

| Feature | Inspiration | Notes |
|---------|-------------|-------|
| Better recursive syntax | Datalog | Real need but niche. Org charts, category trees. Syntax is tricky. |
| Rule definitions (`define`) | Datalog | Nice for reusable logic; different from `stash as` CTEs |

### Low Priority ⬇️

| Feature | Inspiration | Notes |
|---------|-------------|-------|
| Named set operations (`minus`) | SETL | Analysts already know JOIN patterns; EXCEPT exists |
| `divide by` / `forall` | Relational division | Very niche |
| Implicit DISTINCT | Pure set theory | Breaking change, confusing |
| Set comprehension syntax | SETL | Too mathematical, not accessible |
| NULL elimination | Codd/Date | Theoretical purity, but too breaking |

---

## Proposed Syntax Additions

### Semijoin/Antijoin with `has`/`has no`

```asql
-- Customers who HAVE placed orders
from customers
  where has orders (on customer_id)

-- Customers who have NOT placed orders  
from customers
  where has no orders (on customer_id)

-- With additional filter
from customers
  where has orders (on customer_id where amount > 100)
```

Compiles to:
```sql
-- has orders
SELECT * FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id);

-- has no orders
SELECT * FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id);
```

### Recursive Traversal

```asql
-- Simple hierarchy traversal
from employees
  starting where id == 1
  traverse through manager_id -> id
  select id, name, level  -- level is auto-generated depth

-- Or even simpler
from employees.id(1).subordinates  -- if relationship is defined
```

### Universal Quantification

```asql
-- Suppliers who supply ALL parts
from suppliers s
  where forall part in parts:
    has supplies (where supplier_id == s.id and part_id == part.id)
```

---

## Conclusion

The set-theoretic database languages of the 1970s weren't just historical curiosities—they represented rigorous thinking about data manipulation that SQL partially abandoned for "user-friendliness." 

ASQL can cherry-pick the best ideas:
- **QUEL's ordering** (already adopted: `from` first)
- **SETL's expressiveness** (comprehension-style thinking)
- **Datalog's recursion** (worth simplifying)
- **Relational algebra's operators** (semijoin, antijoin, division)

The key is adopting these ideas in ways that feel natural to SQL users while providing the power that set theory always promised.

---

## Decision Summary

| Feature | Decision | Rationale |
|---------|----------|-----------|
| `has` / `has no` | **Yes, explore** | Common pain point, natural syntax, real value |
| Recursive `traverse` | **Maybe** | Real need but niche; syntax needs work |
| `define` rules | **Maybe** | Different from `stash as` CTEs; may confuse users |
| `minus`/`intersect` keywords | **No** | Low pain; analysts know JOIN patterns |
| `forall` / `divide by` | **No** | Too niche |
| Set comprehensions | **No** | Too mathematical, not accessible |

---

## References

- Codd, E.F. "A Relational Model of Data for Large Shared Data Banks" (1970)
- Date, C.J. "SQL and Relational Theory" (2009)
- Date & Darwen, "The Third Manifesto" (introducing Tutorial D)
- Stonebraker, M. "The Design of INGRES" (1976)
- Wikipedia: QUEL, SETL, Datalog, Alpha, QBE
- "Out of the Tar Pit" (Moseley & Marks) - modern take on relational programming

