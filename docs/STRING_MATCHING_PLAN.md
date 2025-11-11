# String Matching Implementation Plan

This document outlines the plan for implementing intuitive string matching operators in ASQL.

## Research Summary

After researching various libraries and query languages, here's what we found:

### Best Practices from Other Languages

1. **KQL (Kusto Query Language)** - Excellent examples:
   - `contains` - substring matching
   - `startswith` - prefix matching
   - `endswith` - suffix matching
   - `matches regex` - regex support
   - Very intuitive and readable

2. **Python pandas** - Clear and explicit:
   - `.str.contains()` - substring
   - `.str.startswith()` - prefix
   - `.str.endswith()` - suffix
   - Method chaining feels natural

3. **JavaScript** - Simple and familiar:
   - `.includes()` - substring
   - `.startsWith()` - prefix
   - `.endsWith()` - suffix
   - Very readable

4. **SQL LIKE** - What we're improving on:
   - `LIKE '%pattern%'` - cryptic wildcards
   - `LIKE 'pattern%'` - unclear intent
   - `LIKE '%pattern'` - unclear intent
   - Requires learning wildcard syntax

## Proposed ASQL Syntax

### Basic Operations

```asql
# Contains (substring match)
from users where email contains "@gmail.com"
from products where name contains "premium"

# Starts with (prefix match)
from users where email starts with "admin"
from urls where domain starts with "https://"

# Ends with (suffix match)
from users where email ends with ".com"
from files where filename ends with ".pdf"
```

### Case Handling

```asql
# Case-sensitive (default)
from users where email contains "GMAIL"

# Case-insensitive (explicit)
from users where email contains "GMAIL" ignore case
from users where name starts with "john" ignore case
```

### Regex Support

```asql
# Regex matching (advanced)
from users where email matches "^[a-z]+@[a-z]+\\.com$"
from users where phone matches "^\d{3}-\d{3}-\d{4}$"
```

## Implementation Details

### Parser Changes

1. Add keyword recognition for:
   - `contains`
   - `starts with` (two-word keyword)
   - `ends with` (two-word keyword)
   - `matches`
   - `ignore case` (optional modifier)

2. Parse as comparison-like expressions:
   ```python
   # Structure similar to comparison operators
   exp.Contains(this=left_expr, expression=right_expr)
   exp.StartsWith(this=left_expr, expression=right_expr)
   exp.EndsWith(this=left_expr, expression=right_expr)
   exp.Matches(this=left_expr, expression=right_expr, case_sensitive=True)
   ```

### SQL Generation

1. **Contains**:
   - Case-sensitive: `column LIKE '%pattern%'`
   - Case-insensitive: `LOWER(column) LIKE LOWER('%pattern%')` or `ILIKE '%pattern%'` (PostgreSQL)

2. **Starts with**:
   - Case-sensitive: `column LIKE 'pattern%'`
   - Case-insensitive: `LOWER(column) LIKE LOWER('pattern%')` or `ILIKE 'pattern%'`

3. **Ends with**:
   - Case-sensitive: `column LIKE '%pattern'`
   - Case-insensitive: `LOWER(column) LIKE LOWER('%pattern%')` or `ILIKE '%pattern'`

4. **Matches**:
   - PostgreSQL: `column ~ 'regex'` (case-sensitive) or `column ~* 'regex'` (case-insensitive)
   - MySQL: `column REGEXP 'regex'`
   - SQLite: `column REGEXP 'regex'`
   - Other: Use SQLGlot's regex support

### Test Cases

```python
# Contains
test_compile_where_contains()
test_compile_where_contains_case_insensitive()

# Starts with
test_compile_where_starts_with()
test_compile_where_starts_with_case_insensitive()

# Ends with
test_compile_where_ends_with()
test_compile_where_ends_with_case_insensitive()

# Matches
test_compile_where_matches_regex()
test_compile_where_matches_regex_case_insensitive()

# Combined with other operators
test_compile_where_contains_and_condition()
test_compile_where_starts_with_or_ends_with()
```

## Priority

**Priority: MEDIUM**

- String matching is common but can be worked around with SQL `LIKE` syntax
- Should be implemented after arithmetic operators
- Before advanced features like JOIN and CTEs

## Design Decisions

1. **Natural language syntax** - Chosen for readability and ASQL philosophy
2. **Case-sensitive by default** - Matches SQL behavior, explicit `ignore case` for clarity
3. **Regex as secondary** - Most users don't need regex, but it's available
4. **No wildcards required** - `contains` is clearer than `LIKE '%pattern%'`

## Future Considerations

- Could add `similar to` for fuzzy matching (PostgreSQL)
- Could add `soundex` or `levenshtein` for similarity matching
- Could add `like` as alias for backward compatibility with SQL users
