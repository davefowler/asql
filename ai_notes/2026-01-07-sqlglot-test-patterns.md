# SQLGlot Test Patterns vs ASQL

**Date:** January 7, 2026

## SQLGlot's Testing Approach

SQLGlot uses a clean, unified `Validator` base class with two powerful methods:

### 1. `validate_identity(sql, write_sql=None)`

Parses SQL and regenerates it, verifying it matches (round-trip):

```python
class TestDuckDB(Validator):
    dialect = "duckdb"
    
    def test_duckdb(self):
        # Parse "SELECT str[0:1]" with DuckDB dialect, regenerate, should match
        self.validate_identity("SELECT str[0:1]")
        
        # Parse with one form, expect different output
        self.validate_identity(
            "SELECT INTERVAL '1 hour'::VARCHAR", 
            "SELECT CAST(INTERVAL '1' HOUR AS TEXT)"  # expected output
        )
```

### 2. `validate_all(sql, read={}, write={})`

Tests cross-dialect transpilation in **both directions**:

```python
self.validate_all(
    "ARRAY_TO_STRING(arr, delim)",  # canonical form
    read={
        "bigquery": "ARRAY_TO_STRING(arr, delim)",
        "presto": "ARRAY_JOIN(arr, delim)",
        "spark": "ARRAY_JOIN(arr, delim)",
    },
    write={
        "duckdb": "ARRAY_TO_STRING(arr, delim)",
        "presto": "ARRAY_JOIN(arr, delim)",
        "spark": "ARRAY_JOIN(arr, delim)",
        "tsql": "STRING_AGG(arr, delim)",
    },
)
```

This single test validates:
- Reading from BigQuery/Presto/Spark produces the canonical form
- Writing to DuckDB/Presto/Spark/TSQL produces dialect-specific SQL

### 3. Testing UnsupportedError

They can specify that certain dialect outputs should raise errors:

```python
self.validate_all(
    "SELECT FIRST_VALUE(c IGNORE NULLS) OVER (...)",
    write={
        "duckdb": "SELECT FIRST_VALUE(c IGNORE NULLS) OVER (...)",
        "sqlite": UnsupportedError,  # SQLite doesn't support this
        "mysql": UnsupportedError,
    },
)
```

### PRQL Testing (Pipeline Language)

PRQL is tested similarly - they test PRQL input transpiling to SQL output:

```python
class TestPRQL(Validator):
    dialect = "prql"

    def test_prql(self):
        self.validate_all(
            "from x",
            write={"": "SELECT * FROM x"},  # "" = generic SQL
        )
        self.validate_all(
            "from x filter age > 25",
            write={"": "SELECT * FROM x WHERE age > 25"},
        )
        self.validate_all(
            "from x sort {-age, +name}",
            write={"": "SELECT * FROM x ORDER BY age DESC, name"},
        )
```

---

## ASQL's Current Approach

### Current Test Helpers (`tests/fixtures.py`)

```python
def assert_valid_sql(sql: str, dialect=None):
    """Verify SQL can be parsed by SQLGlot."""
    parsed = sqlglot.parse_one(sql, dialect=dialect)
    assert parsed is not None

def assert_sql_contains(sql: str, *substrings):
    """Verify SQL contains all substrings."""
    for substring in substrings:
        assert substring.lower() in sql.lower()

def assert_sql_structure(sql: str, **kwargs):
    """Verify SQL clause ordering."""
    # Check FROM comes before WHERE, etc.
```

### Current Test Pattern

```python
def test_compile_group_by_count():
    asql = "from users group by country ( # as total_users )"
    sql = compile(asql)
    
    assert_sql_contains(sql, "GROUP BY", "COUNT", "total_users")
    assert_sql_structure(sql, FROM="users", GROUP_BY="country")
    assert_valid_sql(sql)
```

---

## Gap Analysis

| Feature | SQLGlot | ASQL | Gap |
|---------|---------|------|-----|
| Base Validator class | ✅ `Validator` | ❌ None | **Major** |
| Identity/round-trip tests | ✅ `validate_identity()` | ❌ Ad-hoc | **Major** |
| Cross-dialect testing | ✅ `validate_all()` | ⚠️ Manual per-test | **Major** |
| UnsupportedError testing | ✅ Built-in | ❌ Manual | Medium |
| Substring assertions | ✅ Via unittest | ✅ `assert_sql_contains` | OK |
| AST validation | ✅ Via parsed tree | ✅ Via `assert_valid_sql` | OK |

---

## Recommendations

### 1. Create ASQL Validator Base Class

```python
# tests/validator.py
import unittest
from asql import compile
from sqlglot import parse_one, UnsupportedError

class ASQLValidator(unittest.TestCase):
    """Base class for ASQL dialect tests."""
    
    target_dialect = None  # e.g., "postgres", "duckdb"
    
    def validate_asql(self, asql: str, expected_sql: str = None, dialect: str = None):
        """Compile ASQL and optionally verify output matches expected SQL."""
        dialect = dialect or self.target_dialect
        sql = compile(asql, dialect=dialect)
        
        if expected_sql:
            # Normalize and compare
            self.assertEqual(
                parse_one(sql, dialect=dialect).sql(dialect=dialect),
                parse_one(expected_sql, dialect=dialect).sql(dialect=dialect)
            )
        return sql
    
    def validate_all(self, asql: str, write: dict):
        """
        Test ASQL compiles correctly to multiple dialects.
        
        Args:
            asql: ASQL input
            write: Dict of {dialect: expected_sql | UnsupportedError}
        """
        for dialect, expected in write.items():
            with self.subTest(f"{asql} -> {dialect}"):
                if expected is UnsupportedError:
                    with self.assertRaises(UnsupportedError):
                        compile(asql, dialect=dialect)
                else:
                    sql = compile(asql, dialect=dialect)
                    # Normalize both and compare
                    self.assertEqual(
                        parse_one(sql, dialect=dialect).sql(dialect=dialect),
                        parse_one(expected, dialect=dialect).sql(dialect=dialect)
                    )
```

### 2. Refactor Tests to Use Validator

```python
# tests/dialects/test_duckdb.py
from tests.validator import ASQLValidator

class TestDuckDBDialect(ASQLValidator):
    target_dialect = "duckdb"
    
    def test_basic_from(self):
        self.validate_asql(
            "from users",
            "SELECT * FROM users"
        )
    
    def test_group_by_count(self):
        self.validate_asql(
            "from users group by country ( # as total_users )",
            "SELECT country, COUNT(*) AS total_users FROM users GROUP BY country"
        )
    
    def test_coalesce_operator(self):
        self.validate_all(
            "from users select name ?? 'Unknown' as display_name",
            write={
                "duckdb": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                "postgres": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
                "mysql": "SELECT COALESCE(name, 'Unknown') AS display_name FROM users",
            }
        )
    
    def test_desc_order(self):
        self.validate_all(
            "from users order by -created_at",
            write={
                "duckdb": "SELECT * FROM users ORDER BY created_at DESC",
                "postgres": "SELECT * FROM users ORDER BY created_at DESC",
            }
        )
```

### 3. Add Dialect-Specific Test Files

Create focused test files per dialect:

```
tests/
├── dialects/
│   ├── __init__.py
│   ├── test_duckdb.py      # DuckDB-specific behaviors
│   ├── test_postgres.py    # PostgreSQL-specific 
│   ├── test_bigquery.py    # BigQuery-specific
│   ├── test_snowflake.py   # Snowflake-specific
│   └── test_mysql.py       # MySQL-specific
├── validator.py            # ASQLValidator base class
├── test_compiler.py        # General compilation tests
└── ...
```

### 4. Cross-Dialect Matrix Tests

```python
class TestCrossDialect(ASQLValidator):
    """Test that ASQL compiles correctly across all dialects."""
    
    DIALECTS = ["duckdb", "postgres", "bigquery", "snowflake", "mysql"]
    
    def test_basic_query_all_dialects(self):
        """Basic query should work on all dialects."""
        for dialect in self.DIALECTS:
            with self.subTest(dialect=dialect):
                sql = compile("from users where age > 18", dialect=dialect)
                # Should parse without error
                parse_one(sql, dialect=dialect)
    
    def test_date_functions_vary_by_dialect(self):
        """Date functions have dialect-specific output."""
        self.validate_all(
            "from users select year(created_at) as year_created",
            write={
                "duckdb": "SELECT YEAR(created_at) AS year_created FROM users",
                "postgres": "SELECT EXTRACT(YEAR FROM created_at) AS year_created FROM users",
                "bigquery": "SELECT EXTRACT(YEAR FROM created_at) AS year_created FROM users",
            }
        )
```

---

## Benefits of This Approach

1. **Consistency**: All tests follow same pattern
2. **Cross-dialect coverage**: Easy to test all dialects at once
3. **Normalized comparison**: Compare ASTs, not strings (avoids whitespace issues)
4. **Clear failure messages**: `subTest` shows which dialect failed
5. **Easy to add new dialects**: Just add to the `write` dict
6. **Tracks unsupported features**: Explicitly mark what's not supported per dialect

---

## Migration Path

1. **Phase 1**: Create `ASQLValidator` base class and `validate_all()` method
2. **Phase 2**: Add `tests/dialects/` directory with per-dialect tests
3. **Phase 3**: Migrate existing cross-dialect tests to use `validate_all()`
4. **Phase 4**: Add comprehensive cross-dialect matrix tests

This aligns ASQL's testing with SQLGlot's proven patterns while keeping ASQL-specific needs (pipeline syntax → SQL output).

