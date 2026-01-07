# Explicit FK Column Shorthand for Joins

## Summary

Add support for a "half-explicit" join syntax where users can specify just the foreign key column name instead of the full join condition. This provides a middle ground between fully inferred joins and full SQL explicit joins.

## Motivation

Currently ASQL offers two options for joins:
1. **Fully inferred**: `from accounts & users` - ASQL infers the join keys from schema or naming conventions
2. **Fully explicit**: `from accounts & users on accounts.owner_id = users.id` - Full SQL condition

When there are multiple possible FK relationships between tables (e.g., `accounts` has both `owner_id` and `created_by_id` pointing to `users`), users must fall back to the verbose full SQL syntax.

## Proposed Syntax

Allow specifying just the FK column name after `on`:

```asql
-- Specify which FK to use (expands to accounts.owner_id = users.id)
from accounts
join users on owner_id

-- Works in either direction  
from users
join accounts on owner_id

-- Works with all join operators
from accounts &? users on owner_id
from accounts & users on created_by_id
```

## Behavior

1. **Single identifier after `on`**: Treat as FK column shorthand
   - `on owner_id` → expands to `{from_table}.owner_id = {to_table}.id`
   - The FK column is assumed to be on the "many" side pointing to `id` on the "one" side
   
2. **Complex expression after `on`**: Pass through as regular SQL
   - `on accounts.owner_id = users.id` → unchanged (current behavior)
   - `on accounts.owner_id == users.id` → unchanged
   - Any expression with `.`, `=`, `==`, `AND`, `OR`, etc. → unchanged

## Detection Logic

A condition is treated as "single FK column" if it matches:
- A single identifier: `[a-zA-Z_][a-zA-Z0-9_]*`
- No dots (`.`), no operators (`=`, `==`, `<`, `>`, `AND`, `OR`, etc.)

Otherwise, fall back to regular SQL passthrough.

## Implementation Notes

The change should be in `asql/preparse/joins.py` in the `_replace_join_operator` method. When a condition is captured:
1. Check if it's a single identifier (no dots, no operators)
2. If yes, expand to full equality: `{from_table}.{fk_col} = {to_table}.id`
3. If no, pass through unchanged (current behavior)

## Examples

| ASQL | Generated SQL |
|------|---------------|
| `from accounts & users on owner_id` | `FROM accounts JOIN users ON accounts.owner_id = users.id` |
| `from users &? accounts on owner_id` | `FROM users LEFT JOIN accounts ON accounts.owner_id = users.id` |
| `from orders & users on customer_id` | `FROM orders JOIN users ON orders.customer_id = users.id` |
| `from accounts & users on accounts.owner_id = users.id` | `FROM accounts JOIN users ON accounts.owner_id = users.id` (passthrough) |

## Tasks

- [ ] **Implementation**: Update `_replace_join_operator` in `asql/preparse/joins.py` to detect and expand single-column FK shorthand
- [ ] **Tests**: Add tests in `tests/test_join.py`:
  - `test_explicit_fk_column_inner_join` - basic FK column shorthand
  - `test_explicit_fk_column_left_join` - with `&?` operator  
  - `test_explicit_fk_column_with_alias` - `& users as u on owner_id`
  - `test_explicit_fk_column_chained_joins` - multiple joins with FK shorthand
  - `test_explicit_fk_fallback_to_full_condition` - ensure `on table.col = other.col` still works
  - `test_explicit_fk_fallback_complex_condition` - ensure `on col1 AND col2` falls back
- [ ] **Documentation**: Update `docs/spec.md` section 7.4 "Explicit Join Conditions" to document the new shorthand syntax
- [ ] **Documentation**: Add examples showing when to use each join style (inferred vs FK shorthand vs full explicit)

