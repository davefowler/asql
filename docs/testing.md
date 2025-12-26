# Testing

ASQL has a comprehensive test suite that validates both **compilation** (ASQL → SQL transformation) and **execution** (running SQL against real databases).

## Test Categories

### Unit Tests (Compilation)

The majority of tests verify that ASQL compiles correctly to SQL:

- **Syntax parsing** - ASQL syntax is parsed correctly
- **Transformation** - Features like `group by ... ()`, `when/then`, `#` are transformed properly
- **Dialect generation** - SQL is generated correctly for each target dialect

These tests run fast (~8 seconds) and don't require any database.

```bash
# Run all unit tests
./venv/bin/pytest tests/
```

### Execution Tests

Execution tests run compiled SQL against real databases to verify correctness:

- **Result validation** - Queries return expected values
- **Syntax validation** - Generated SQL is syntactically valid
- **Feature testing** - ASQL-specific features work correctly

```bash
# Run execution tests
./venv/bin/pytest tests/test_execution.py -v
```

## Database Coverage

### Currently Tested

| Database | Status | Notes |
|----------|--------|-------|
| **DuckDB** | ✅ Full execution testing | In-memory, fast, comprehensive |
| **PostgreSQL** | ✅ Full execution testing | Requires local PostgreSQL server |

### Compilation Validated

These dialects have SQL generation tested via SQLGlot parsing:

| Dialect | Status |
|---------|--------|
| PostgreSQL | ✅ |
| MySQL | ✅ |
| Snowflake | ✅ |
| BigQuery | ✅ |
| Redshift | ✅ |
| Databricks | ✅ |
| Trino | ✅ |

### Planned

| Database | Status | Tracking |
|----------|--------|----------|
| All dialects syntax | 🔜 Planned | [#90](https://github.com/davefowler/asql/issues/90) |
| BigQuery/Snowflake | 🔜 Planned | [#91](https://github.com/davefowler/asql/issues/91) |

## Features Tested

### Execution Tests Coverage

| Feature | Tested | Notes |
|---------|--------|-------|
| SELECT, WHERE, ORDER BY, LIMIT | ✅ | Basic SQL operations |
| GROUP BY with aggregations | ✅ | sum, avg, count, multiple aggs |
| JOINs | ✅ | INNER, LEFT |
| Window functions | ✅ | row_number, rank, running_sum |
| Date comparisons | ✅ | @date syntax |
| String matching | ✅ | contains, starts_with, ends_with |
| Coalesce (??) | ✅ | NULL handling |
| DISTINCT | ✅ | |
| When/then expressions | ✅ | Single condition |
| Spine/gap-filling | ✅ | Core ASQL feature |
| CTEs (stash as) | ⚠️ | Multi-query syntax in progress |
| UNION | ⚠️ | Pipeline syntax in progress |
| Nested when/then | ⚠️ | Bug in parser |

### Example Files

All 20 example files in `examples/pairs/` are tested for:
- Successful compilation
- Valid SQL syntax

## Running Tests

### Prerequisites

```bash
# Install dev dependencies
pip install -e ".[dev]"
```

### Setting Up PostgreSQL (Optional)

PostgreSQL tests are optional but recommended for full coverage. The easiest setup on macOS is [Postgres.app](https://postgresapp.com/):

1. **Install Postgres.app** from [postgresapp.com](https://postgresapp.com/)
2. **Start the server** by opening the app and clicking "Initialize"
3. **Create a test database**:
   ```bash
   /Applications/Postgres.app/Contents/Versions/latest/bin/createdb test
   ```
4. **Set the connection URL**:
   ```bash
   export POSTGRES_URL="postgresql://localhost:5432/test"
   ```

Or add it to your `~/.zshrc` for persistence:
```bash
echo 'export POSTGRES_URL="postgresql://localhost:5432/test"' >> ~/.zshrc
```

The test suite auto-detects available databases. If PostgreSQL is configured, tests run against both DuckDB and PostgreSQL.

### Commands

```bash
# Run all tests
./venv/bin/pytest tests/

# Run with verbose output
./venv/bin/pytest tests/ -v

# Run specific test file
./venv/bin/pytest tests/test_execution.py -v

# Run specific test class
./venv/bin/pytest tests/test_execution.py::TestWindowFunctionExecution -v

# Run with coverage
./venv/bin/pytest tests/ --cov=asql
```

## Test Architecture

### Executor Framework

ASQL uses an executor abstraction for database-agnostic testing:

```python
from asql.testing.executors import get_available_executors, EXECUTORS

# Get available database executors
executors = get_available_executors()  # ['duckdb', 'postgres']

# Each executor implements:
class ExecutorBase:
    def execute(self, sql: str) -> List[Tuple]: ...
    def create_table(self, name, columns, rows): ...
    def validate_syntax(self, sql: str) -> bool: ...
```

### Adding New Executors

To add support for a new database:

1. Create `asql/testing/executors/{db}_executor.py`
2. Implement `ExecutorBase` interface
3. Register in `asql/testing/executors/__init__.py`
4. Add optional dependency to `pyproject.toml`

Tests automatically run against all available executors.

## Continuous Integration

Tests run automatically on:
- Every push to main
- Every pull request

The test suite must pass before merging.

## Contributing Tests

When adding new features:

1. **Add unit tests** for compilation in `tests/test_{feature}.py`
2. **Add execution tests** for runtime behavior in `tests/test_execution.py`
3. **Use xfail** for known limitations (documents issues without blocking CI)

```python
def test_new_feature(self, executor):
    try:
        sql = compile("from t ...", dialect=executor.dialect)
        rows = executor.execute(sql)
        assert ...
    except Exception as e:
        pytest.xfail(f"Feature not yet implemented: {e}")
```
