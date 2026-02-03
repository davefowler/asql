# Schema Analysis: ASQL vs SQLGlot

**Date**: 2026-01-18  
**Goal**: Determine if we can simplify `asql/schema.py` (921 lines) by building on SQLGlot

## Executive Summary

| Component | Lines | Can Use SQLGlot? | Notes |
|-----------|-------|------------------|-------|
| Column/Table classes | ~95 | ✅ YES | SQLGlot has table/column/type storage |
| Relationship class | ~40 | ❌ NO | **SQLGlot doesn't have FK relationships** |
| Schema core methods | ~150 | Partial | Table lookup ✅, relationships ❌ |
| Relationship inference | ~140 | ❌ NO | ASQL-specific (naming conventions) |
| Loaders (YAML, dbt) | ~500 | ❌ NO | ASQL-specific config format |

**Key Finding**: SQLGlot's `MappingSchema` has NO concept of foreign keys or relationships.

```python
# SQLGlot MappingSchema - what it can do:
schema.column_names("users")  # → ['id', 'name', 'email']
schema.get_column_type("users", "id")  # → 'INT'
schema.has_column("users", "name")  # → True

# What it CANNOT do (no API exists):
schema.find_relationship("orders", "users")  # ❌ No such method
schema.relationships  # ❌ No such attribute
schema.foreign_keys  # ❌ No such attribute
```

## What ASQL Schema Is Used For

### 1. **Join Inference** (PRIMARY USE)
When user writes `JOIN users` without ON clause, ASQL infers the join condition.

```sql
-- Input (no ON clause)
FROM orders JOIN users

-- ASQL uses schema to infer:
FROM orders JOIN users ON orders.user_id = users.id
```

**Requires**: `schema.find_relationship("orders", "users")` → `Relationship`

### 2. **FK Shorthand Expansion**
When user writes `ON user_id` instead of full condition.

```sql
-- Input (column-only ON)
FROM orders JOIN users ON user_id

-- ASQL expands to:
FROM orders JOIN users ON orders.user_id = users.id
```

**Requires**: `schema.find_relationship()` or column/PK detection

### 3. **Dynamic Pivot Values**
When pivot column values aren't specified, look them up from schema.

```sql
-- Input (no VALUES specified)
PIVOT ON category

-- ASQL looks up distinct values from:
schema.get_table("orders").get_distinct_values("category")
```

**Requires**: `Column.distinct_values` attribute

### 4. **Column Operators (EXCEPT, RENAME)**
When using `SELECT * EXCEPT col`, need actual column list.

```sql
-- Input
SELECT * EXCEPT email FROM users

-- Needs schema to know actual columns:
SELECT id, name FROM users
```

**Requires**: `schema.column_names()` → SQLGlot HAS this!

### 5. **Underscore Shorthands**
Validating that `days_since_created_at` column exists.

**Requires**: `schema.get_table().has_column()` → SQLGlot HAS this!

---

## SQLGlot MappingSchema Capabilities

```python
from sqlglot.schema import MappingSchema

schema = MappingSchema(schema={
    'users': {'id': 'INT', 'name': 'VARCHAR'},
    'orders': {'id': 'INT', 'user_id': 'INT'}
})

# ✅ What it CAN do:
schema.column_names("users")           # ['id', 'name']
schema.get_column_type("users", "id")  # 'INT'
schema.has_column("users", "name")     # True
schema.add_table(exp.Table(...), ...)  # Add table

# ❌ What it CANNOT do:
# - Store FK relationships
# - Know that orders.user_id → users.id
# - Distinguish primary keys
# - Store distinct values for columns
```

---

## Recommendation: Thin Wrapper Around MappingSchema

### Option A: Extend MappingSchema (Recommended)

```python
from sqlglot.schema import MappingSchema
from dataclasses import dataclass, field

@dataclass
class Relationship:
    """FK relationship between tables."""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    alias: str | None = None
    source: str = "inferred"  # "explicit" or "inferred"

class ASQLSchema(MappingSchema):
    """MappingSchema + FK relationships for join inference."""
    
    def __init__(self, schema=None, **kwargs):
        super().__init__(schema=schema, **kwargs)
        self.relationships: list[Relationship] = []
        self._primary_keys: dict[str, str] = {}  # table → pk column
        self._distinct_values: dict[tuple[str, str], list[str]] = {}  # (table, col) → values
    
    def add_relationship(self, rel: Relationship) -> None:
        self.relationships.append(rel)
    
    def find_relationship(self, from_table: str, to_table: str) -> Relationship | None:
        # Explicit first, then inferred
        for rel in self.relationships:
            if rel.from_table == from_table and rel.to_table == to_table:
                if rel.source == "explicit":
                    return rel
        for rel in self.relationships:
            if rel.from_table == from_table and rel.to_table == to_table:
                return rel
        return None
    
    def set_primary_key(self, table: str, column: str) -> None:
        self._primary_keys[table.lower()] = column.lower()
    
    def get_primary_key(self, table: str) -> str | None:
        # Check explicit first, then conventions
        if pk := self._primary_keys.get(table.lower()):
            return pk
        # Convention: 'id' column
        if self.has_column(table, "id"):
            return "id"
        return None
    
    def infer_relationships(self) -> None:
        """Infer FKs from *_id naming conventions."""
        for table in self.mapping:
            for col in self.column_names(table):
                if col.endswith("_id") and col != "id":
                    # Try to find target table
                    base = col[:-3]  # "user" from "user_id"
                    # Try plural/singular variants
                    for variant in [base, base + "s", base[:-1] if base.endswith("s") else base]:
                        if variant in self.mapping:
                            pk = self.get_primary_key(variant)
                            if pk:
                                self.add_relationship(Relationship(
                                    from_table=table,
                                    from_column=col,
                                    to_table=variant,
                                    to_column=pk,
                                    alias=base,
                                    source="inferred"
                                ))
                                break
```

**Benefits**:
- Inherits all SQLGlot schema functionality
- Only adds what SQLGlot lacks (relationships, PK detection)
- ~100 lines instead of 420

### What We Can Delete

| Current Code | Lines | Replacement |
|--------------|-------|-------------|
| `class Column` | 47 | Not needed - SQLGlot stores types |
| `class Table` | 76 | Not needed - use MappingSchema |
| `Schema.add_table`, `get_table`, `has_table` | ~20 | Use MappingSchema methods |
| `Schema.column_names`, `has_column` | N/A | Already in MappingSchema |

### What We Must Keep

| Current Code | Lines | Why |
|--------------|-------|-----|
| `class Relationship` | 40 | SQLGlot has no FK concept |
| `find_relationship` | 30 | Join inference |
| `infer_relationships` | 60 | Naming conventions |
| `get_primary_key` | 30 | PK detection |
| Loaders (YAML, dbt) | 500 | ASQL config format |

---

## Line Count Estimate

| Component | Current | After Refactor |
|-----------|---------|----------------|
| Core classes | 420 | ~100 (Relationship + ASQLSchema) |
| Loaders | 500 | 500 (keep as-is) |
| **Total** | **920** | **~600** |

**Savings**: ~320 lines (35%)

---

## Implementation Steps

1. **Test SQLGlot MappingSchema compatibility**
   - Verify it works with our optimizer calls
   - Verify column_names/has_column work as expected

2. **Create ASQLSchema class extending MappingSchema**
   - Add relationships list
   - Add primary_key tracking
   - Add find_relationship method
   - Add infer_relationships method

3. **Update loaders to build ASQLSchema**
   - from_yaml → populate MappingSchema + relationships
   - from_dbt → populate MappingSchema + relationships

4. **Update consumers**
   - `join_inference.py` - use new find_relationship
   - `join_fk_shorthand.py` - use new schema
   - `column_operators.py` - can use MappingSchema directly

5. **Delete redundant code**
   - Column class (keep Relationship)
   - Table class
   - Schema's table management methods

---

## Questions to Answer

1. **Does MappingSchema handle case-insensitivity correctly?**
   - ASQL normalizes to lowercase everywhere
   - Need to verify MappingSchema's `normalize` param

2. **Can we load dbt schemas into MappingSchema?**
   - Need to test with actual dbt manifest

3. **Is the adapter pattern still needed?**
   - `sqlglot_schema_adapter.py` converts ASQL Schema → MappingSchema
   - If we extend MappingSchema, adapter becomes simpler

4. **Can we contribute FK support upstream to SQLGlot?**
   - See `ai_notes/2026-01-08-sqlglot-schema-relationships-issue.md`
   - Could propose adding relationships to base Schema
