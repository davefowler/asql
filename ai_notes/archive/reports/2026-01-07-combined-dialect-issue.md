# Combined Dialect Approach for ASQL + Target Dialect

## Summary

Currently ASQL uses a fallback approach: parse with ASQL dialect, if that fails, fall back to target dialect. This is fragile and requires multiple parse attempts.

A better approach discovered during research: create combined dialects that inherit from both ASQL and the target dialect (Postgres, DuckDB, BigQuery, etc.).

## The Combined Approach

```python
class ASQLPostgresParser(ASQLParser, Postgres.Parser):
    pass

class ASQLPostgres(ASQL, Postgres):
    class Parser(ASQLPostgresParser):
        pass

# Single parse with both ASQL and Postgres features
combined = ASQLPostgres()
result = combined.parse('from users where name ILIKE "%test%" and created_at > 7 days ago')
```

## Benefits

1. **Single parse attempt** - No try/catch fallback chain
2. **Full target dialect support** - Dialect-specific functions, operators, syntax all available
3. **ASQL features always active** - Relative dates, date arithmetic, etc. work alongside target syntax
4. **Simpler error handling** - Parse errors are straightforward
5. **Better performance** - No multiple parse attempts

## Implementation Notes

- Use Python multiple inheritance: `class CombinedParser(ASQLParser, TargetDialect.Parser)`
- MRO ensures ASQL methods take precedence (ASQL is superset of SQL)
- Cache combined dialect classes per target dialect
- Dynamically create combined dialects: `create_asql_dialect('postgres')`

## Testing Done

Prototype tested successfully with Postgres, DuckDB, BigQuery:
- ASQL features (`7 days ago`) work
- Target-specific features (`ILIKE`, backtick tables) work  
- Combined queries work

## Scope

This is a refactoring improvement, not a bug fix. The current fallback approach works but is less elegant.

## Files to Change

- `asql/dialect.py` - Add combined dialect factory
- `asql/compiler/api.py` - Use combined dialect instead of fallback
- Tests - Verify dialect-specific features work with ASQL syntax

