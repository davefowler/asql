# SQL Pipe Syntax Adoption Analysis: Should ASQL Join an Existing Standard?

## Summary

A friend raised an important strategic question: rather than promoting ASQL as a new standard, should we get behind an existing pipe syntax proposal (like BigQuery's or Spark's) that has more momentum?

This document analyzes:
1. Which pipe syntaxes exist and their adoption
2. Community reception and momentum
3. Strategic options for ASQL
4. Recommendation

**TL;DR:** The industry is converging on a **remarkably consistent pipe syntax** across BigQuery, Spark, and now Snowflake. ASQL should position itself as a **transpiler that adopts this emerging standard** while adding value through multi-dialect support and higher-level abstractions.

---

## Current Landscape

### Major Pipe Syntax Implementations

| Platform | Operator | Released | Status | Backed By |
|----------|----------|----------|--------|-----------|
| **BigQuery** | `\|>` | Oct 2024 | GA (Feb 2025) | Google |
| **Spark SQL** | `\|>` | 2024 (v4.0) | Available | Apache/Databricks |
| **Snowflake** | `->>` | May 2025 | Available | Snowflake |
| **PRQL** | `\|` / newline | 2022 | Early adopter stage | Open source |
| **Malloy** | `->` | 2021 | Experimental | Google (Lloyd Tabb) |
| **ASQL** | newline / `\|` | 2023 | Active development | Open source |

### Academic Foundation

Google published a **peer-reviewed paper at VLDB 2024**:
> "SQL Has Problems. We Can Fix Them: Pipe Syntax In SQL"

This gives the BigQuery/GoogleSQL pipe syntax academic legitimacy and a formal specification.

---

## Adoption & Momentum Analysis

### 1. BigQuery Pipe Syntax 🏆

**Momentum: HIGH**

- **Academic paper** at VLDB 2024 (major database conference)
- **GA for all BigQuery users** as of Feb 4, 2025
- **Formal specification** in GoogleSQL/ZetaSQL
- **Cloud Logging integration** - used beyond just analytics
- **Growing documentation** and examples

**Community Reception:**
- Hacker News discussion with significant engagement
- Mixed but largely positive - developers appreciate FROM-first
- Dr. Richard Hipp (SQLite creator) skeptical but said he'd adopt if it becomes standard

**Key Quote from Hipp:**
> "If future versions of standard SQL adopt a FROM-clause-first query format, SQLite would consider implementing it."

This is crucial - even skeptics will follow if it becomes standard.

### 2. Spark/Databricks Pipe Syntax 🥈

**Momentum: HIGH**

- **Spark 4.0** - massive installed base
- **Databricks Runtime 16.2+** - enterprise adoption
- **Near-identical to BigQuery** - same `|>` operator, same concepts
- **Proposal for `|` alternative** (Nov 2025) - aligning with Unix/Kusto

**Community Reception:**
- Generally positive among Spark users
- Seen as natural evolution
- Benefits from existing FROM-first support in Spark

### 3. Snowflake Pipe Syntax 🥉

**Momentum: MEDIUM**

- **Released May 2025** - newest entrant
- **Different operator: `->>` instead of `|>`**
- **Statement chaining focus** - slightly different use case (multi-statement)
- Shows even Snowflake sees value in pipeline SQL

**Key Difference:** Snowflake's `->>` is more about chaining separate statements than transforming within a query. Still validates the pipeline concept.

### 4. PRQL

**Momentum: LOW-MEDIUM**

- ~4,000+ GitHub stars
- Active development
- Some tooling integration (Pretzel, VSCode)
- **But:** Completely new language, not SQL extension
- **Barrier:** Requires learning entirely new syntax

### 5. Malloy

**Momentum: LOW**

- Created by Looker founder (Lloyd Tabb)
- Backed by Google but **not integrated into Looker**
- Experimental status since 2021
- Interesting ideas but limited adoption

---

## The Emerging Consensus

### Syntax Convergence

BigQuery, Spark, and the academic paper all converged on nearly identical syntax:

```sql
FROM table
|> WHERE condition
|> EXTEND expr AS col    -- or SELECT
|> AGGREGATE agg GROUP BY col
|> ORDER BY col
|> LIMIT n
```

**Common operators across BigQuery and Spark:**
- `|>` pipe operator
- `EXTEND` - add columns
- `SET` - modify columns  
- `DROP` - remove columns
- `RENAME` - rename columns
- `AGGREGATE ... GROUP BY`
- Standard `WHERE`, `ORDER BY`, `LIMIT`, `DISTINCT`

**This is not coincidence - it's convergent evolution.** Two of the world's largest data platforms independently arrived at the same design.

### ISO Standardization Status

- **Not yet submitted** to ISO/IEC SQL committee
- But with Google's VLDB paper and multi-platform adoption, pressure will build
- Dr. Hipp's position suggests standardization would unlock SQLite adoption

---

## Strategic Options for ASQL

### Option A: Continue as Independent Standard

**Pros:**
- Full control over syntax design
- Can innovate faster
- Already has differentiated features (`per`, `running_sum`, etc.)

**Cons:**
- Fighting uphill against BigQuery/Spark momentum
- Users must learn ASQL-specific syntax
- Risk of irrelevance if pipe syntax becomes standard

### Option B: Adopt BigQuery/Spark Pipe Syntax

**Pros:**
- Align with emerging industry standard
- Users' knowledge transfers across platforms
- ASQL becomes the **transpiler** for pipe syntax
- Can still add higher-level abstractions on top

**Cons:**
- Lose some syntactic distinctiveness
- May need to adjust some ASQL features
- Following rather than leading

### Option C: Hybrid - ASQL as Superset of Pipe Syntax

**Pros:**
- Accept pipe syntax as valid input
- Output native pipe syntax when targeting BQ/Spark
- Add ASQL's higher-level abstractions as extensions
- Best of both worlds

**Cons:**
- More complex implementation
- Need to maintain compatibility

---

## Recommendation: Option C (Hybrid Superset)

### The Friend's Insight Was Right

The friend's observation is astute:

> "dbt can basically polyfill future SQL syntax. That could put a lot of momentum behind any particular proposal."

ASQL can be that polyfill! Here's the strategy:

### 1. Accept Pipe Syntax as Input

Make ASQL understand BigQuery/Spark pipe syntax:

```sql
-- This would be valid ASQL input
FROM orders
|> WHERE status = 'completed'
|> EXTEND total * 1.1 AS adjusted_total
|> AGGREGATE SUM(adjusted_total) AS revenue GROUP BY region
|> ORDER BY revenue DESC
```

### 2. Transpile to Any Dialect

ASQL's unique value is **multi-dialect compilation**. Take pipe syntax and output:
- Standard SQL for Postgres, MySQL, SQLite
- Native pipe syntax for BigQuery, Spark
- Snowflake's `->>` syntax for Snowflake

### 3. Add Higher-Level Abstractions

ASQL can extend pipe syntax with conveniences that compile down:

```asql
-- ASQL-specific extensions (compile to standard pipe syntax)
from orders
per customer first by -date    -- ASQL abstraction
sample 100 per region          -- ASQL abstraction
running_sum(amount by customer order by date)  -- ASQL abstraction
```

These compile to the underlying `EXTEND` + window functions in pipe syntax.

### 4. Position as "Pipe Syntax for Every Database"

Marketing angle:
> "ASQL brings BigQuery/Spark pipe syntax to every SQL database. Write modern, readable SQL and deploy anywhere."

This aligns ASQL with the industry direction rather than fighting it.

---

## Implementation Implications

### Syntax Alignment Needed

| Current ASQL | Pipe Syntax Standard | Change Needed? |
|--------------|---------------------|----------------|
| `from table` | `FROM table` | ✅ Compatible |
| `where cond` | `\|> WHERE cond` | ✅ Compatible (implicit pipe) |
| `select cols` | `\|> SELECT cols` | ✅ Compatible |
| `except cols` | `\|> DROP cols` | 🔶 Consider alias |
| `rename` | `\|> RENAME` | ✅ Identical |
| `group by col (agg)` | `\|> AGGREGATE agg GROUP BY col` | 🔶 Different syntax |
| N/A | `\|> EXTEND expr AS col` | 🔶 Add support |
| N/A | `\|> SET col = expr` | 🔶 Add support |

### Additions to Consider

1. **Accept `|>` explicitly** (currently ASQL uses implicit newlines or `|`)
2. **Add `extend` keyword** - matches pipe syntax
3. **Add `set`/`replace` keyword** - matches pipe syntax
4. **Support `aggregate` keyword** - alternative to inline syntax
5. **Output pipe syntax** when targeting BigQuery/Spark

---

## The dbt Connection

The friend mentioned:
> "It's interesting to think about providing new syntax support in databases that don't yet support it in dbt at the compilation step."

This is exactly right. ASQL could:

1. **Integrate with dbt** as a SQL preprocessor
2. **Polyfill pipe syntax** for databases that don't support it natively
3. **Enable teams to write pipe syntax today** and run anywhere

This could be a powerful adoption driver:
- Teams use pipe syntax in their dbt models
- ASQL transpiles to whatever dialect their warehouse needs
- When warehouses add native support, ASQL passes through

---

## Risks of Not Adopting

If ASQL stays fully independent while pipe syntax becomes standard:

1. **Learning curve**: Users know pipe syntax, must learn ASQL differences
2. **Tooling gap**: LSPs, linters, formatters will target pipe syntax
3. **Market position**: "Why use ASQL when I can use native pipe syntax?"
4. **Irrelevance risk**: Could become niche as pipe syntax goes mainstream

---

## Conclusion

### Key Findings

1. **BigQuery and Spark pipe syntax are converging** on a common standard
2. **VLDB paper** gives academic legitimacy
3. **Snowflake joining** (with slight variation) shows industry momentum
4. **SQLite will follow** if it becomes standard (per Hipp)
5. **PRQL and Malloy** are losing to SQL-native pipe extensions

### Strategic Recommendation

**ASQL should embrace pipe syntax as its foundation while adding value through:**

1. **Multi-dialect transpilation** - write once, run anywhere
2. **Higher-level abstractions** - `per`, `running_sum`, `sample N per col`
3. **Polyfill capability** - bring pipe syntax to Postgres, MySQL, SQLite today
4. **dbt integration** - become the pipe syntax preprocessor

### Positioning

> "ASQL: Pipe Syntax SQL for Every Database"

This positions ASQL as:
- Aligned with industry direction (BigQuery, Spark)
- Additive rather than competitive
- The bridge that brings modern SQL everywhere

### Next Steps

1. **Accept `|>` operator** as input syntax option
2. **Add `extend` and `set` keywords** matching pipe syntax
3. **Output native pipe syntax** for BigQuery/Spark targets
4. **Document alignment** with BigQuery/Spark pipe syntax
5. **Explore dbt integration** for polyfill use case

---

## References

- [SQL Has Problems. We Can Fix Them: Pipe Syntax In SQL](https://www.vldb.org/pvldb/vol17/p4051-shute.pdf) - VLDB 2024
- [BigQuery Pipe Syntax Documentation](https://cloud.google.com/bigquery/docs/reference/standard-sql/pipe-syntax)
- [Databricks Pipe Syntax Announcement](https://www.databricks.com/blog/sql-gets-easier-announcing-new-pipe-syntax)
- [Snowflake Flow Operators](https://docs.snowflake.com/en/sql-reference/operators-flow)
- [Dr. Hipp's Comments on Pipe Syntax](https://simonwillison.net/2024/Aug/28/d-richard-hipp/)
