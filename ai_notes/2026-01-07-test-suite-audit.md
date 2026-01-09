# ASQL Test Suite Audit Report

**Date:** January 7, 2026  
**Auditor:** AI Analysis  
**Total Test Files:** 49  
**Total Lines of Test Code:** ~13,615

---

## Executive Summary

The ASQL test suite is **well-structured and comprehensive**, covering the major components of the compiler pipeline. The architecture follows good testing practices with clear separation between unit tests, integration tests, and execution tests. However, there are opportunities for improvement in test organization, coverage gaps, and some architectural inconsistencies.

**Overall Grade: B+**

### Strengths
- Excellent coverage of core compilation features
- Good use of parameterized tests for comprehensive coverage
- Strong execution tests that validate against real databases
- Well-organized test fixtures and utilities
- Good error handling and edge case coverage

### Areas for Improvement
- Some test files are very large (test_preparser.py: 1,143 lines)
- Inconsistent test organization patterns
- Missing negative test cases in some areas
- Some tests have become integration tests masquerading as unit tests

---

## Test Architecture Overview

### Test Categories

| Category | Files | Purpose |
|----------|-------|---------|
| **Unit Tests** | ~25 | Test individual functions/classes in isolation |
| **Integration Tests** | ~15 | Test component interactions |
| **Execution Tests** | 1 | Run compiled SQL against real databases |
| **Code Quality** | 3 | Validate code structure and conventions |

### Test Pyramid Analysis

```
                    /\
                   /  \
                  / E  \     Execution Tests (1 file, 1378 lines)
                 /------\    - DuckDB executor
                /   I    \   
               /----------\  Integration Tests (~15 files)
              /     U      \ - Compiler, preparser, dialect
             /--------------\
            /                \ Unit Tests (~25 files)
           /------------------\ - Individual features
```

**Assessment:** The pyramid is slightly inverted - the execution test file is very large relative to unit tests. This suggests some tests that could be unit tests are instead execution tests.

---

## Detailed Analysis by Test File

### Core Compiler Tests

#### `test_compiler.py` (429 lines) ✅ Good
**What it tests:**
- Basic FROM clause compilation
- WHERE clause with all comparison operators
- GROUP BY with aggregations (COUNT, SUM, AVG)
- ORDER BY (ascending, descending, multiple columns)
- LIMIT/TAKE clause
- Dialect-specific output (postgres)

**Testing approach:** Direct `compile()` calls with string assertions and SQLGlot parsing validation.

**Assessment:** Well-structured, covers the core happy path. Could benefit from more negative test cases.

#### `test_preparser.py` (1,143 lines) ⚠️ Needs Refactoring
**What it tests:**
- FROM-first transformation
- Pipeline operators (`|`)
- Count shorthand (`#`)
- Coalesce operator (`??`)
- Order DESC prefix (`-column`)
- Natural aggregates (`sum of`, `avg`)
- Date literals (`@2024-01-15`)
- Relative dates (`7 days ago`)
- Column operators (except, rename, replace)
- Pivot/Unpivot
- Sample clause
- Explode

**Testing approach:** Mix of `preparse_asql()` unit tests and `compile()` integration tests.

**Issues:**
1. **Too large** - Should be split into multiple files by feature
2. **Mixed concerns** - Some tests use `preparse_asql()`, others use `compile()` due to migration to dialect parser
3. **Migration debt** - Comments indicate features moved to dialect parser but tests remain here

**Recommendation:** Split into:
- `test_preparser_transforms.py` - Pure preparser regex transforms
- `test_dialect_features.py` - Features now in dialect parser (coalesce, dates, etc.)
- `test_pivot_unpivot.py` - Pivot/unpivot specific tests

#### `test_dialect.py` (343 lines) ✅ Good
**What it tests:**
- Dialect registration with SQLGlot
- Basic SQL parsing (SELECT, WHERE, ORDER BY, LIMIT, GROUP BY)
- Aggregate functions (SUM, AVG, COUNT)
- Window functions (ROW_NUMBER, RANK, LAG, LEAD)
- JOINs and CTEs
- Expressions (arithmetic, comparison, CASE WHEN)
- Type casting
- Date functions
- SQL generation for multiple dialects

**Testing approach:** SQLGlot parsing validation with AST inspection.

**Assessment:** Excellent coverage of the dialect parser. Well-organized by feature.

### Feature-Specific Tests

#### `test_join.py` (382 lines) ✅ Excellent
**What it tests:**
- Join operators (`&`, `&?`, `?&`, `?&?`, `*`)
- Table aliases in joins
- Chained joins
- Joins with WHERE, SELECT, GROUP BY, ORDER BY
- Join conditions (multiple, arithmetic)
- Self-joins
- FK column shorthand (`on owner_id`)
- Backward compatibility with traditional JOIN syntax

**Testing approach:** Comprehensive parameterized tests with both string assertions and SQLGlot validation.

**Assessment:** One of the best-organized test files. Good coverage of edge cases.

#### `test_when.py` (230 lines) ✅ Good
**What it tests:**
- Simple CASE with `is` operator
- Multiple comma-separated branches
- Comparison operators (<, <=, >, >=)
- `is not` and `in` operators
- Searched CASE expressions
- `else` vs `otherwise` keywords
- WHEN in aggregations
- WHEN across dialects

**Assessment:** Good coverage of the when/then syntax.

#### `test_coalesce.py` (92 lines) ✅ Good
**What it tests:**
- `??` operator to COALESCE
- Chained coalesce (`a ?? b ?? c`)
- Coalesce in SELECT and WHERE
- Reverse compilation (COALESCE to `??`)

**Assessment:** Focused and complete.

#### `test_alias_reuse.py` (205 lines) ✅ Good
**What it tests:**
- Alias reuse in SELECT (referencing earlier aliases)
- Three-level dependencies
- Alias reuse with WHERE and ORDER BY
- DuckDB direct emit vs PostgreSQL CTE chain
- Circular dependency detection (xfail)

**Assessment:** Good coverage of a complex feature.

#### `test_auto_alias.py` (488 lines) ✅ Excellent
**What it tests:**
- Prefix-based auto-aliasing (sum → sum_col)
- Jinja2 template system for aliases
- Custom prefixes via SET and YAML
- All aggregate functions (sum, avg, min, max, count)
- Date functions (year, month, week, day)
- String functions (upper, lower, length, trim)
- Window functions (row_number)
- Template filters (lower, upper, title)
- Precedence rules

**Assessment:** Very comprehensive. Good use of parameterized tests.

#### `test_auto_spine.py` (805 lines) ✅ Good
**What it tests:**
- Auto-spine default behavior
- Date truncation detection in GROUP BY
- `guarantee()` function for explicit spines
- Mixed GROUP BY (date + categorical)
- Spine with various date functions
- Cross-join for categorical dimensions
- Spine disabling via SET

**Assessment:** Thorough coverage of a complex feature. Could use more execution tests.

### Execution Tests

#### `test_execution.py` (1,378 lines) ✅ Excellent
**What it tests:**
- Basic query execution against DuckDB
- SELECT, WHERE, GROUP BY, ORDER BY, LIMIT, JOIN
- Alias reuse execution
- List comprehension execution
- Example file compilation and syntax validation
- Spine execution
- CTE execution
- Window function execution
- Date function execution
- String matching execution
- UNION, ternary, coalesce, distinct

**Testing approach:** Uses `ExecutorBase` abstraction with DuckDB implementation. Creates real tables, inserts data, executes compiled SQL, validates results.

**Assessment:** Excellent real-world validation. The executor abstraction is well-designed for future database support.

**Issues:**
1. Very large file - could be split by feature
2. Many `xfail` markers indicate known bugs that should be tracked as issues

### Test Infrastructure

#### `tests/fixtures.py` (201 lines) ✅ Good
**Provides:**
- Example schemas (users, sales, orders, events, etc.)
- Valid/invalid query lists for parameterized tests
- `assert_valid_sql()` - SQLGlot parsing validation
- `assert_sql_contains()` - Substring checking
- `assert_sql_structure()` - SQL clause ordering validation

**Assessment:** Well-designed utilities. Could add more assertion helpers.

#### `asql/testing/executors/` ✅ Good
**Provides:**
- `ExecutorBase` - Abstract base class for database executors
- `DuckDBExecutor` - DuckDB implementation
- `PostgresExecutor`, `SQLiteExecutor` - Stubs for future

**Assessment:** Good abstraction for multi-database testing.

### Code Quality Tests

#### `test_code_quality.py` (102 lines) ✅ Good
**What it tests:**
- All public functions have docstrings
- Error classes exist and inherit correctly
- `compile()` function signature
- No syntax errors in code
- Imports work correctly

**Assessment:** Good baseline quality checks.

#### `test_exception_handling.py` (248 lines) ✅ Excellent
**What it tests:**
- Errors surface properly (not swallowed)
- Specific exception types for different failures
- Jinja2 requirement enforcement
- Config loading errors
- Dialect registration idempotency

**Assessment:** Excellent defensive testing. Ensures errors aren't silently swallowed.

---

## Coverage Analysis

### Well-Covered Areas ✅
1. **Core compilation** - FROM, WHERE, SELECT, GROUP BY, ORDER BY, LIMIT
2. **Aggregations** - COUNT, SUM, AVG, MIN, MAX with aliases
3. **Joins** - All join types, operators, aliases, FK shorthand
4. **Conditional expressions** - WHEN/THEN, CASE
5. **Coalesce** - `??` operator
6. **Date handling** - Literals, relative dates, arithmetic
7. **Auto-aliasing** - Templates, prefixes, functions
8. **Dialect support** - PostgreSQL, MySQL, BigQuery, Snowflake, DuckDB
9. **Reverse compilation** - SQL to ASQL

### Potential Coverage Gaps ⚠️
1. **Complex expressions** - Nested functions, complex arithmetic
2. **Schema-aware compilation** - More edge cases needed
3. **Error messages** - Quality of error messages for various failures
4. **Performance** - No performance/stress tests
5. **Concurrency** - No thread-safety tests
6. **Multi-query pipelines** - `stash as` with multiple stages
7. **Pipeline edge cases** - Very long pipelines, deeply nested CTEs

*Note: Traditional SQL constructs like subqueries, HAVING, and UNION don't apply to ASQL's pipeline model. In ASQL:*
- *Subqueries → Use `stash as` or pipeline stages*
- *HAVING → Use `where` after `group by` (automatically compiles to HAVING)*
- *Set operations → Would be pipeline operators if supported*

### Missing Test Files (Suggested)
1. `test_multi_stage_pipelines.py` - Complex `stash as` chains
2. `test_performance.py` - Compilation speed benchmarks
3. `test_error_quality.py` - Error message clarity
4. `test_deeply_nested.py` - Long pipeline stress tests

---

## Testing Patterns Analysis

### Good Patterns Used ✅

1. **Parameterized Tests**
```python
@pytest.mark.parametrize("asql_query", VALID_ASQL_QUERIES)
def test_valid_query_compiles(self, asql_query: str) -> None:
```

2. **Fixture-Based Testing**
```python
@pytest.fixture(params=get_available_executors())
def executor(request: pytest.FixtureRequest) -> Any:
```

3. **Class-Based Organization**
```python
class TestJoinOperators:
class TestJoinWithAlias:
class TestChainedJoins:
```

4. **Multi-Level Validation**
```python
assert_sql_contains(sql, "JOIN", "users", "orders", "ON")
assert_valid_sql(sql)
parsed = sqlglot.parse_one(sql)
join = parsed.find(exp.Join)
assert join is not None
```

### Anti-Patterns Found ⚠️

1. **Overly Long Test Files**
   - `test_preparser.py` at 1,143 lines is too large
   - `test_execution.py` at 1,378 lines could be split

2. **Mixed Unit/Integration Tests**
   - Some files mix `preparse_asql()` unit tests with `compile()` integration tests
   - Makes it unclear what's being tested

3. **String-Based Assertions**
```python
# Fragile - depends on exact SQL formatting
assert "LEFT JOIN" in sql.upper()
```
Better:
```python
# More robust - uses AST
join = parsed.find(exp.Join)
assert join.side == "LEFT"
```

4. **Excessive xfail Markers**
   - Many tests marked as xfail for known bugs
   - These should be tracked as GitHub issues

---

## Recommendations

### High Priority

1. **Split Large Test Files**
   - Break `test_preparser.py` into feature-specific files
   - Split `test_execution.py` by feature category

2. **Track xfail Tests as Issues**
   - Create GitHub issues for all xfail tests
   - Link issues in test comments

3. **Add Missing Coverage**
   - Multi-stage pipeline tests (`stash as` chains)
   - Complex nested expressions
   - Pipeline edge cases (very long pipelines)

### Medium Priority

4. **Standardize Testing Patterns**
   - Prefer AST-based assertions over string matching
   - Consistent class organization across files

5. **Add Performance Tests**
   - Compilation speed benchmarks
   - Memory usage tests

6. **Improve Test Documentation**
   - Add docstrings explaining test purpose
   - Document test categories in README

### Low Priority

7. **Add More Database Executors**
   - PostgreSQL executor
   - SQLite executor
   - Snowflake executor (if feasible)

8. **Property-Based Testing**
   - Use Hypothesis for fuzzing
   - Generate random valid ASQL queries

---

## Test Metrics Summary

| Metric | Value | Assessment |
|--------|-------|------------|
| Total test files | 49 | Good |
| Total test lines | ~13,615 | Good |
| Largest file | 1,378 lines | Too large |
| Average file size | ~278 lines | Good |
| Parameterized tests | ~30% | Good |
| Execution tests | ~10% | Could increase |
| xfail markers | ~15 | Should track as issues |
| Code coverage | Unknown | Should measure |

---

## Conclusion

The ASQL test suite is **fundamentally sound** with good coverage of core features. The main issues are organizational (large files, mixed concerns) rather than fundamental gaps. The execution testing infrastructure is particularly well-designed and provides confidence that compiled SQL actually works.

**Key Takeaways:**
1. The test suite is testing the right things
2. Organization could be improved
3. Some coverage gaps exist in advanced features
4. The executor abstraction is excellent for future expansion
5. Error handling tests are thorough

**Recommended Next Steps:**
1. Split `test_preparser.py` into smaller files
2. Create GitHub issues for all xfail tests
3. Add subquery and HAVING tests
4. Measure and track code coverage

