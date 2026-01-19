# Implicit-Only Relationships: A Simpler Schema Approach

**Date**: 2026-01-18  
**Question**: Can we eliminate stored relationships entirely and just infer them on-the-fly?

## Current Architecture

```
Schema
├── tables: {name → columns}           ← SQLGlot has this
├── relationships: [Relationship, ...]  ← SQLGlot DOESN'T have this
└── infer_relationships()              ← Builds relationships from naming conventions
```

The current flow:
1. Load schema (from YAML, dbt, or dict)
2. Call `infer_relationships()` to scan for `*_id` columns
3. Store relationships in `schema.relationships` list
4. Query them via `find_relationship(from, to)`

## The Proposal: Infer On-Demand

**What if we never stored relationships and just computed them when needed?**

```python
def find_relationship(from_table: str, to_table: str, schema) -> Relationship | None:
    """Infer relationship on-demand from column names."""
    from_tbl = schema.get_table(from_table)
    to_tbl = schema.get_table(to_table)
    
    if not from_tbl or not to_tbl:
        return None
    
    # Try {to_singular}_id pattern
    to_singular = singularize(to_table)
    fk_col = f"{to_singular}_id"
    
    if fk_col in schema.column_names(from_table):
        to_pk = _get_primary_key(to_table, schema)
        return Relationship(
            from_table=from_table,
            from_column=fk_col,
            to_table=to_table,
            to_column=to_pk or "id",
        )
    
    # Try reverse direction
    from_singular = singularize(from_table)
    reverse_fk = f"{from_singular}_id"
    
    if reverse_fk in schema.column_names(to_table):
        from_pk = _get_primary_key(from_table, schema)
        return Relationship(
            from_table=to_table,
            from_column=reverse_fk,
            to_table=from_table,
            to_column=from_pk or "id",
        )
    
    return None
```

## What We'd Lose

### 1. Explicit Relationships from Config

Currently users can define explicit relationships in YAML:

```yaml
tables:
  orders:
    columns: [id, buyer_id, seller_id]
  users:
    columns: [id, name]

relationships:
  - from: orders.buyer_id
    to: users.id
    alias: buyer
  - from: orders.seller_id
    to: users.id
    alias: seller
```

**With implicit-only**: We can't express `buyer` vs `seller` - both would infer as `user_id → users.id`.

### 2. Ambiguous FK Resolution

When a table has MULTIPLE FKs to the same target:

```sql
-- orders has: buyer_id, seller_id (both → users)
FROM orders JOIN users  -- Which one? buyer_id or seller_id?
```

**Current**: Explicit relationship specifies which one  
**Implicit-only**: Ambiguous, would need to pick first match or error

### 3. Non-Standard Naming

```sql
-- Column named "owner" instead of "owner_id"
orders.owner → users.id
```

**Current**: Explicit relationship can handle this  
**Implicit-only**: Won't find it (doesn't end in `_id`)

## What We'd Gain

### 1. No Schema Extension Needed

Could use SQLGlot's `MappingSchema` directly:

```python
from sqlglot.schema import MappingSchema

schema = MappingSchema(schema={
    'users': {'id': 'INT', 'name': 'VARCHAR'},
    'orders': {'id': 'INT', 'user_id': 'INT'}
})

# Infer on-demand
rel = infer_relationship("orders", "users", schema)
```

**No custom Schema class needed!**

### 2. Simpler Codebase

| Current | Implicit-Only |
|---------|---------------|
| `class Relationship` | Still needed (return type) |
| `Schema.relationships` list | **DELETE** |
| `Schema.add_relationship()` | **DELETE** |
| `Schema.find_relationship()` | Move to function |
| `Schema.infer_relationships()` | **DELETE** |
| YAML relationship loading | **DELETE** |
| dbt relationship loading | **DELETE** |

**Estimated savings**: ~300 lines from schema.py loaders

### 3. Always Consistent

No risk of stale/outdated relationship data - always computed fresh from column names.

## Analysis: How Often Are Explicit Relationships Used?

Let me check the test suite:

```
grep -r "source.*explicit" tests/
```

| Test | Why Explicit? |
|------|---------------|
| `test_explicit_relationship_takes_precedence` | Tests priority over inferred |
| `test_find_relationship_explicit_wins` | Tests priority |
| `test_yaml_explicit_relationships` | Tests YAML loading |
| `test_dbt_explicit_relationships` | Tests dbt loading |
| Several integration tests | Use explicit for predictability |

**Key insight**: Most tests use explicit relationships for **test predictability**, not because users actually need them.

## Real-World Use Cases

### Case 1: Simple FK (99% of cases)
```sql
FROM orders JOIN users
-- orders.user_id → users.id ✅ Implicit works
```

### Case 2: Named Relationship (buyer vs seller)
```sql
FROM orders JOIN users AS buyer ON orders.buyer_id = buyer.id
-- User MUST specify ON clause anyway ❌ Explicit doesn't help much
```

### Case 3: Non-standard naming
```sql
FROM orders JOIN users ON orders.owner = users.id
-- User MUST specify ON clause anyway ❌ Explicit doesn't help much
```

**Observation**: When relationships are ambiguous or non-standard, users already need to write explicit ON clauses. The explicit relationship metadata mainly helps when:
- Column follows convention (`user_id`)
- AND you want to omit the ON clause

## Recommendation

### Option A: Implicit-Only (Simpler)

**Do this if**:
- Users rarely configure explicit relationships
- Convention-based inference handles 95%+ of cases
- Ambiguous cases require explicit ON anyway

**Implementation**:
```python
# Just use MappingSchema directly
from sqlglot.schema import MappingSchema

# Add helper function (not a class)
def infer_join_condition(from_table, to_table, schema) -> JoinCondition | None:
    # ... convention-based inference
```

**Savings**: ~500 lines (most of schema.py)

### Option B: Thin Extension (Keep Explicit Option)

**Do this if**:
- Some users rely on explicit relationship config
- dbt relationship tests are valuable
- Need to handle `buyer_id` vs `seller_id` cases

**Implementation**: See `2026-01-18-schema-analysis.md` - extend MappingSchema

**Savings**: ~320 lines

### Option C: Hybrid (Best of Both?)

Keep implicit inference as primary, allow explicit override via simple dict:

```python
# No custom Schema class
schema = MappingSchema(schema={...})

# Optional: explicit overrides passed separately
explicit_relationships = {
    ("orders", "users"): ("buyer_id", "id"),  # orders.buyer_id → users.id
}

def find_relationship(from_t, to_t, schema, explicit=None):
    # Check explicit first
    if explicit and (from_t, to_t) in explicit:
        fk, pk = explicit[(from_t, to_t)]
        return Relationship(from_t, fk, to_t, pk)
    # Fall back to inference
    return _infer_from_conventions(from_t, to_t, schema)
```

**Savings**: ~400 lines (no Relationship class storage, simpler loaders)

---

## Decision Matrix

| Factor | Implicit-Only | Thin Extension | Hybrid |
|--------|---------------|----------------|--------|
| Code savings | ~500 lines | ~320 lines | ~400 lines |
| SQLGlot native | ✅ Yes | ⚠️ Subclass | ✅ Yes |
| Handles ambiguous FKs | ❌ No | ✅ Yes | ✅ Yes |
| dbt compatibility | ⚠️ Limited | ✅ Full | ⚠️ Partial |
| Complexity | Low | Medium | Low |

## My Recommendation: Start with Implicit-Only

1. **Most users won't notice** - convention-based inference handles typical schemas
2. **Explicit ON is always available** - ambiguous cases require it anyway
3. **Can add explicit later** if real user demand emerges
4. **Massive simplification** - can use MappingSchema directly

### Migration Path

1. Delete `Schema` class, use `MappingSchema`
2. Replace `find_relationship()` with `infer_join_condition()` function
3. Update `join_inference.py` to use the function
4. Delete YAML/dbt relationship loading (keep table/column loading)
5. Update tests to use ON clauses where needed

### What Breaks?

- Tests that rely on explicit relationships → add ON clauses
- Users who configured explicit relationships → add ON clauses (likely none exist yet)
- dbt relationship test extraction → drop this feature (limited value)
