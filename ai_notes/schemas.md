# Schema Support in ASQL: Status Report

**Date**: December 2025  
**Status**: Not Implemented (Specified Only)

---

## Executive Summary

Schema support in ASQL is **extensively specified in docs/spec.md but not implemented**. The current codebase has:

- ✅ Explicit join syntax (`& table on condition`) - fully implemented
- ❌ FK dot notation (`orders.user.name`) - specified but not implemented
- ❌ Schema file loading (`asql_schema.yml`) - specified but not implemented
- ❌ dbt schema.yml compatibility - specified but not implemented
- ❌ Join key inference for cohorts - specified but not implemented

---

## Current Implementation Status

### What Works (Implemented)

**Explicit Joins** (`asql/preparse/joins.py`):
```asql
from orders & users on orders.user_id = users.id
from orders &? users on orders.user_id = users.id  -- LEFT JOIN
```

These use the `on` clause to specify join conditions explicitly. No schema inference needed.

**Tests**: `tests/test_join.py` has 25+ tests covering:
- All join operators (`&`, `&?`, `?&`, `?&?`, `*`)
- Aliases (`& users as owner on ...`)
- Chained joins
- Traditional SQL JOIN syntax (backward compatible)

### What's Specified But Not Implemented

#### 1. FK Dot Notation (spec.md §7.4-7.8)

```asql
-- SPECIFIED (not implemented)
from orders
  select orders.user.name  -- Should auto-join via user_id → users.id
```

This would require:
- Parsing `table.fk.column` patterns
- Inferring `user_id` → `users.id` from naming convention
- Auto-generating LEFT JOIN clauses

#### 2. Schema File Loading (spec.md §7.10)

```yaml
# asql_schema.yml (SPECIFIED, not implemented)
relationships:
  - from: opportunities.owner_id
    to: users.id
    alias: owner
```

This would require:
- File discovery (search for `asql_schema.yml`)
- YAML parsing
- Relationship registry
- Lookup during FK resolution

#### 3. dbt Compatibility (spec.md §7.10)

> "ASQL can read dbt's `schema.yml` files to infer relationships from `relationships` tests."

Not implemented.

#### 4. Cohort Join Inference

```asql
-- Infers user_id from users table name
from events
group by month(event_date) (count(distinct user_id) as active)
cohort by month(users.signup_date)
```

The `cohort by` clause now **infers the join key from the cohort table name** using the `{singular_table}_id` convention:
- `users` → `user_id`
- `customers` → `customer_id`
- `accounts` → `account_id`

This was implemented directly in the preparser (`asql/preparse/cohort.py`).

---

## How Schema Would Be Passed

### Option 1: Config File (Specified)

```yaml
# asql.config.yaml or asql_schema.yml
tables:
  orders:
    columns:
      - name: id
        type: integer
        primary_key: true
      - name: user_id
        type: integer
        foreign_key: users.id
      - name: amount
        type: decimal
        
relationships:
  - from: orders.user_id
    to: users.id
    alias: user
```

### Option 2: Programmatic API (Not Designed)

```python
# Potential future API
from asql import compile
from asql.schema import Schema, Table, Column, ForeignKey

schema = Schema()
schema.add_table(Table(
    name="orders",
    columns=[
        Column("id", "integer", primary_key=True),
        Column("user_id", "integer", foreign_key="users.id"),
    ]
))

sql = compile("from orders select orders.user.name", schema=schema)
```

### Option 3: Database Introspection (Not Designed)

```python
# Potential future API
from asql import compile
from asql.schema import Schema

schema = Schema.from_database("postgresql://...")
sql = compile("from orders select orders.user.name", schema=schema)
```

---

## Current Workarounds

### 1. Explicit Joins (Always Works)

```asql
-- Instead of: from orders select orders.user.name
from orders &? users on orders.user_id = users.id
select users.name
```

### 2. `invent_join_keys` Setting (Just Added)

For docs/playground where no real schema exists:

```python
settings = CompileSettings(invent_join_keys=True)
# Will assume user_id → users.id, customer_id → customers.id, etc.
```

---

## What's Needed for Full Schema Support

### Phase 1: Schema Data Structure

```python
# asql/schema.py (new file)
@dataclass
class Column:
    name: str
    type: str
    primary_key: bool = False
    foreign_key: Optional[str] = None  # "table.column"

@dataclass  
class Table:
    name: str
    columns: List[Column]
    
@dataclass
class Schema:
    tables: Dict[str, Table]
    
    def get_foreign_key(self, table: str, column: str) -> Optional[str]:
        """Get FK target for table.column, or None."""
        ...
    
    def infer_join_key(self, from_table: str, to_table: str) -> Optional[str]:
        """Find FK column in from_table that points to to_table."""
        ...
```

### Phase 2: Schema Loading

```python
# Load from YAML
schema = Schema.from_yaml("asql_schema.yml")

# Load from dbt
schema = Schema.from_dbt("dbt_project/models/schema.yml")

# Load from database
schema = Schema.from_database(connection_string)
```

### Phase 3: FK Dot Notation Parser

```python
# In preparser, detect patterns like:
# orders.user.name → orders LEFT JOIN users ON orders.user_id = users.id, SELECT users.name
```

### Phase 4: Integration

```python
# Compile with schema context
sql = compile(asql_query, schema=schema, settings=settings)

# Or global schema in config
config = ASQLConfig(schema=schema)
```

---

## Test Coverage Status

| Feature | Tests | Status |
|---------|-------|--------|
| Explicit joins (`& on`) | 25+ tests | ✅ Implemented |
| Join operators (`&`, `&?`, `?&`, `*`) | ✅ | ✅ Implemented |
| Table aliases | ✅ | ✅ Implemented |
| Cohort join key inference | ❌ (in preparser) | ✅ Implemented (Dec 2025) |
| FK dot notation | ❌ | Not implemented |
| Schema file loading | ❌ | Not implemented |
| dbt compatibility | ❌ | Not implemented |
| `invent_join_keys` setting | ❌ | Added for future use |

---

## Recommendations

### Short-term (Docs/Playground)

1. **Use `invent_join_keys=True`** for doc examples and playground
2. **Document the limitation** - FK dot notation is future feature
3. **Always show explicit joins** in examples as primary pattern

### Medium-term

1. **Design Schema dataclass** - Define the schema shape
2. **Implement YAML loading** - Start with `asql_schema.yml`
3. **Add join key inference** - For cohorts and FK dot notation

### Long-term

1. **dbt compatibility** - Read dbt schema.yml files
2. **Database introspection** - Auto-discover schema from DB
3. **IDE integration** - Schema-aware autocomplete

---

## Related Files

- `docs/spec.md` §7.4-7.11 - FK traversal specification
- `docs/quick_start.md` - FK Dot Notation section (documented but not working)
- `asql/preparse/joins.py` - Current join implementation
- `asql/config.py` - `invent_join_keys` setting
- `tests/test_join.py` - Join tests (explicit only)

