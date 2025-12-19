# Execution Testing in ASQL

**Date**: 2025-12-18  
**Status**: Research and recommendations

## Current State

ASQL currently tests **compilation** (ASQL → SQL transformation) but not **execution** (running the generated SQL against data).

### What We Test Today

```python
# Current approach: Check SQL structure
sql = compile("from sales group by region (sum amount)")
assert "GROUP BY" in sql
assert "SUM" in sql
```

### What We Don't Test

- Whether the generated SQL returns correct results
- Whether the spine fills gaps correctly
- Whether edge cases produce correct values (not just valid SQL)

## SQLGlot's Built-in Executor

SQLGlot includes a Python-based SQL executor that can run queries against in-memory tables.

### Capabilities

| Feature | Supported |
|---------|-----------|
| SELECT, FROM, WHERE | ✅ |
| GROUP BY, aggregates | ✅ |
| JOIN (INNER, LEFT, etc.) | ✅ |
| CTEs (WITH clause) | ✅ |
| COALESCE, CASE | ✅ |
| ORDER BY, LIMIT | ✅ |
| generate_series | ❌ |
| Date functions (DATE_TRUNC) | ❌ |
| Window functions | Partial |

### Basic Usage

```python
from sqlglot import executor
from sqlglot.executor.table import Table

# Define test data
sales_data = Table(
    columns=['id', 'amount', 'region'],
    rows=[
        (1, 100, 'North'),
        (2, 200, 'South'),
        (3, 150, 'North'),
    ]
)

tables = {'sales': sales_data}

# Execute a query
result = executor.execute(
    'SELECT region, SUM(amount) as total FROM sales GROUP BY region',
    tables=tables
)

# Access results
print(result.columns)  # ('region', 'total')
for row in result.rows:
    print(row)  # ('North', 250), ('South', 200)
```

### Limitation: generate_series

The executor doesn't support `generate_series`, which our date spines use:

```python
# This fails:
executor.execute("SELECT * FROM generate_series(1, 5)")
# ExecuteError: Step 'Scan: t' failed
```

**Workaround**: Pre-generate the date spine as a table.

## Proposed Execution Testing Strategy

### Approach 1: Test Categorical Spines (Works Today)

Categorical spines use `SELECT DISTINCT`, which the executor supports:

```python
def test_categorical_spine_fills_gaps():
    """Test that categorical spine fills gaps with zeros."""
    # Setup
    sales = Table(
        columns=['region', 'amount'],
        rows=[
            ('North', 100),
            ('North', 50),
            # No 'South' sales!
        ]
    )
    
    region_spine = Table(
        columns=['region'],
        rows=[('North',), ('South',)]
    )
    
    tables = {'sales': sales, 'region_spine': region_spine}
    
    # The generated SQL (simplified)
    sql = """
    SELECT region_spine.region, COALESCE(SUM(sales.amount), 0) as total
    FROM region_spine
    LEFT JOIN sales ON region_spine.region = sales.region
    GROUP BY region_spine.region
    """
    
    result = executor.execute(sql, tables=tables)
    
    # Assert
    rows = list(result.rows)
    assert ('North', 150) in rows
    assert ('South', 0) in rows  # Gap filled!
```

### Approach 2: Mock Date Spines as Tables

For date spines, pre-generate the spine as a test table:

```python
def test_date_spine_fills_gaps():
    """Test that date spine fills monthly gaps."""
    # Pre-generate the date spine (instead of generate_series)
    month_spine = Table(
        columns=['month'],
        rows=[
            ('2021-01-01',),
            ('2021-02-01',),
            ('2021-03-01',),
        ]
    )
    
    sales = Table(
        columns=['created_at', 'amount'],
        rows=[
            ('2021-01-15', 100),  # January
            # No February!
            ('2021-03-20', 200),  # March
        ]
    )
    
    tables = {'month_spine': month_spine, 'sales': sales}
    
    # Execute with pre-generated spine
    sql = """
    SELECT month_spine.month, COALESCE(SUM(sales.amount), 0) as total
    FROM month_spine
    LEFT JOIN sales ON month_spine.month = DATE_TRUNC('month', sales.created_at)
    GROUP BY month_spine.month
    """
    
    # Note: DATE_TRUNC may not work; might need to preprocess
```

### Approach 3: Use DuckDB for Full Execution Testing

DuckDB is fast, embedded, and supports all SQL features:

```python
import duckdb

def test_full_spine_with_duckdb():
    """Test spine generation with real SQL execution."""
    conn = duckdb.connect(':memory:')
    
    # Create test data
    conn.execute("""
        CREATE TABLE sales AS SELECT * FROM (VALUES
            (1, 100, '2021-01-15'::date),
            (2, 200, '2021-03-15'::date)
        ) AS t(id, amount, created_at)
    """)
    
    # Compile ASQL to SQL
    sql = compile(
        "from sales group by month(created_at) (sum(amount) as revenue)",
        dialect="duckdb"
    )
    
    # Execute and verify
    result = conn.execute(sql).fetchall()
    
    # Check that February is filled with 0
    months = {row[0]: row[1] for row in result}
    assert months.get('2021-02-01') == 0
```

## Recommendations

### Short-term: SQLGlot Executor for Categorical Tests

1. Add execution tests for categorical spines (no date functions needed)
2. Verify gap-filling with COALESCE works correctly
3. Test edge cases like empty tables, NULL values

### Medium-term: DuckDB for Full Integration Tests

1. Use DuckDB for testing date spines (supports generate_series)
2. Test across dialects (DuckDB can approximate others)
3. Create a test fixture pattern for common scenarios

### Long-term: Property-Based Testing

Consider using Hypothesis for property-based testing:

```python
from hypothesis import given, strategies as st

@given(st.lists(st.tuples(st.text(), st.integers())))
def test_spine_always_includes_all_groups(data):
    """Property: Spine should include all distinct values from input."""
    # Generate table, compile, execute, verify
```

## Implementation Example

Here's a proof-of-concept execution test:

```python
# tests/test_execution.py
import pytest
from sqlglot import executor
from sqlglot.executor.table import Table
from asql import compile, CompileSettings


class TestCategoricalSpineExecution:
    """Execute compiled SQL and verify results."""

    def test_spine_fills_missing_categories(self):
        """Test that spine fills gaps for missing categories."""
        # Compile ASQL
        sql = compile(
            "from sales group by region (sum(amount) as total)",
            dialect="duckdb",  # Use duckdb dialect for executor compatibility
            settings=CompileSettings(auto_spine=True)
        )
        
        # For testing, we need to replace the spine CTE with explicit data
        # since executor doesn't support DISTINCT subqueries from same table
        # This is a simplified test
        
        sales = Table(
            columns=['region', 'amount'],
            rows=[
                ('North', 100),
                ('North', 50),
                # No South!
            ]
        )
        
        region_spine = Table(
            columns=['region'],
            rows=[('North',), ('South',)]
        )
        
        # Execute simplified spine query
        result = executor.execute(
            """
            SELECT region_spine.region, 
                   COALESCE(SUM(sales.amount), 0) as total
            FROM region_spine
            LEFT JOIN sales ON region_spine.region = sales.region
            GROUP BY region_spine.region
            ORDER BY region_spine.region
            """,
            tables={'sales': sales, 'region_spine': region_spine}
        )
        
        rows = list(result.rows)
        assert rows[0] == ('North', 150)
        assert rows[1] == ('South', 0)  # Gap filled!
```

## Conclusion

| Approach | Effort | Coverage | Recommendation |
|----------|--------|----------|----------------|
| SQLGlot Executor | Low | Partial (no dates) | ✅ Start here for categorical |
| DuckDB Integration | Medium | Full | ✅ Add for date spines |
| Property-Based | High | Comprehensive | Consider later |

**Next Steps:**
1. Add `tests/test_execution.py` with categorical spine tests
2. Add optional DuckDB tests (skip if not installed)
3. Document test patterns for contributors
