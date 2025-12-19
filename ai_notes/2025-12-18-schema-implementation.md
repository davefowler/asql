# Schema Support Implementation

**Date**: December 18, 2025  
**Status**: Implemented

---

## Overview

Implemented schema support with a two-layer architecture:
1. **Raw Schema Layer** - Column names/types from DB, dbt, or YAML files
2. **Relationship Map** - Both explicit (from config) and inferred (from naming conventions)

This enables smart join inference when only table names are provided.

---

## Architecture

```
Schema Sources:
├── asql_schema.yml     → Schema.from_yaml()
├── dbt manifest.json   → Schema.from_dbt() (preferred)
└── dbt schema.yml      → Schema.from_dbt() (fallback)

At compile time:
1. Load schema from file
2. Pass to CompileSettings(schema=schema)
3. Preparser uses schema for join/cohort inference
4. Falls back to invent_join_keys convention if no schema
```

---

## FK Naming Convention Inference

Uses the `inflect` library for proper pluralization (handles "person" → "people", etc.)

### Algorithm

For each column ending in `_id`:

1. Remove the `_id` suffix to get `base_name`
2. Try to find a table matching `base_name` (exact, plural, or singular variants)
3. If not found, progressively split on underscores from the left:
   - Split off segments as potential alias
   - Try remaining part as table name
4. Once a table is found, get its primary key (id, pk, or {singular}_id)
5. Create relationship with alias = the split-off prefix (or base_name if no split)

### Examples

| Column Name | First Try | If Not Found | Target Table | Alias |
|-------------|-----------|--------------|--------------|-------|
| `user_id` | `user/users` | - | `users` | `user` |
| `users_id` | `users` | - | `users` | `users` |
| `customer_id` | `customer/customers` | - | `customers` | `customer` |
| `owner_user_id` | `owner_user(s)` | `user(s)` | `users` | `owner` |
| `manager_user_id` | `manager_user(s)` | `user(s)` | `users` | `manager` |
| `created_by_user_id` | `created_by_user(s)` | `by_user(s)`, then `user(s)` | `users` | `created_by` |
| `person_id` | `person/people` | - | `people` | `person` |

### Primary Key Detection

The `Table.get_primary_key()` method checks in order:
1. Columns explicitly marked as `primary_key=True`
2. Column named `id`
3. Column named `pk`
4. Column named `{singular_table_name}_id` (e.g., `users.user_id`)

### Key Functions

- `pluralize(word)` - Uses inflect library for proper plurals
- `singularize(word)` - Uses inflect library for proper singulars
- `Table.get_primary_key()` - Find PK by convention
- `Schema._find_fk_target(base_name)` - Progressive split algorithm
- `Schema._find_table_by_name(name)` - Try exact, plural, singular variants

---

## Files Changed

### New Files

- **`asql/schema.py`** - Core schema module with:
  - `Column`, `Table`, `Relationship`, `Schema` dataclasses
  - `Schema.from_yaml()` - Load from `asql_schema.yml` format
  - `Schema.from_dbt()` - Load from dbt project (manifest.json or schema.yml)
  - `Schema._from_dbt_manifest()` - Parse dbt manifest.json (best source)
  - `Schema.infer_relationships()` - Infer from `{name}_id` naming conventions
  - `find_relationship()` - Look up relationships (explicit > inferred)

- **`tests/test_schema.py`** - 28 comprehensive tests

### Modified Files

- **`asql/config.py`** - Added `schema: Optional[Schema]` to `CompileSettings`
- **`asql/preparse/__init__.py`** - `preparse_asql()` accepts settings
- **`asql/preparse/preparser.py`** - Store settings for schema access in mixins
- **`asql/compiler/api.py`** - Pass settings to preparser
- **`asql/preparse/joins.py`** - Use schema for join inference when no ON clause
- **`asql/preparse/cohort.py`** - Prefer schema lookup over convention inference
- **`docs/spec_future.md`** - Added FK dot notation and DB introspection sections

---

## Usage

### Load Schema from YAML

```python
from asql.schema import Schema
from asql.config import CompileSettings
from asql import compile

# Load schema
schema = Schema.from_yaml("asql_schema.yml")

# Compile with schema
settings = CompileSettings(schema=schema)
sql = compile("from orders & users", settings=settings)
# Uses orders.user_id = users.id from schema
```

### Load Schema from dbt

```python
# From dbt project (checks target/manifest.json first)
schema = Schema.from_dbt("/path/to/dbt/project")

# Or from specific schema files
schema = Schema.from_dbt("/path/to/models/schema.yml")
```

### YAML Format

```yaml
# asql_schema.yml
tables:
  orders:
    columns: [id, user_id, amount, created_at]
  users:
    columns: [id, name, email]
    
relationships:
  - from: orders.user_id
    to: users.id
    alias: user
```

---

## Future Work (in spec_future.md)

1. **FK Dot Notation** - `orders.user.name` auto-join traversal
2. **Database Introspection** - `Schema.from_database(connection_string)`
3. **IDE Integration** - Schema-aware autocomplete

---

## Tests

All 38 schema tests pass:
- Column/Table/Relationship dataclass tests
- Schema methods (add, find, inference)
- YAML loading
- dbt loading (manifest.json and schema.yml)
- Join inference integration
- Serialization (to_dict/from_dict)
- Multi-underscore alias inference (created_by_user_id)
- Irregular plural handling (person → people)
- PK convention detection (id, pk, {singular}_id)
- Plural FK support (users_id)

Plus all 1549 existing tests still pass.

## Dependencies

Added `inflect>=7.0.0` to requirements.txt for proper pluralization.
