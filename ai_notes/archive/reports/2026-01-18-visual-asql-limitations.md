# Visual ASQL Limitations & CTE Support Plan

**Date:** 2026-01-18

## Current Limitations

### Visual Editor Feature Support

| Feature | ASQL Support | Visual Support | Notes |
|---------|--------------|----------------|-------|
| **CTEs / WITH / stash** | ✅ Yes | ✅ Implementing | Multiple pipelines in array |
| **Multiple Queries** | ✅ Yes | ✅ Implementing | Array of unnamed pipelines |
| **Set Operations** | ✅ Yes | ✅ Implementing | UNION/INTERSECT/EXCEPT as `set_operation` field |
| **Complex Window** | ✅ Yes (`per`, `number`, etc) | ⚠️ Partial | Full OVER clause not visualized |
| **Arithmetic** | ✅ Yes | ⚠️ Partial | Stored as string in `expression` field |
| **PIVOT/UNPIVOT** | ✅ Yes (`explode`) | 🔜 Could add | `explode` = UNPIVOT; PIVOT could be added |

### ❌ Not Planned for Visual Editor

These features are supported in ASQL text mode but won't be in the visual editor:

- **Inline Subqueries** - Use CTEs/stash instead (cleaner, more readable)
- **Lateral Joins** - Complex correlated references between outer and inner query
- **CASE/when expressions** - Complex branching logic; use text mode

### ✅ Supported Transforms

From `ui-metadata.json`:

| Category | Transforms |
|----------|------------|
| **Filter** | where, having, qualify |
| **Join** | inner (&), left (&?), right (?&), full (?&?), cross (*) |
| **Select** | select, except |
| **Aggregate** | group_by (with inline aggregates) |
| **Sort** | order_by |
| **Limit** | limit, offset |
| **Unique** | distinct, deduplicate |
| **Column Ops** | extend, rename, replace, explode |
| **Window** | per, number, rank, dense |
| **Analytics** | cohort, recurse |
| **Utility** | sample, stash |

---

## JSON Format (Always a List)

The JSON format is **always** an array of pipelines. Even a simple single-table query is a list with one element.

### Simple Query (Single Pipeline)

```json
[
  {
    "name": null,
    "from": {"table": "users"},
    "transforms": [
      {"type": "where", "condition": {...}}
    ]
  }
]
```

### Query with CTEs (Multiple Pipelines)

```json
[
  {
    "name": "active_users",
    "from": {"table": "users"},
    "transforms": [
      {"type": "where", "condition": {"type": "binary_op", "operator": "=", "left": {"type": "column", "name": "status"}, "right": {"type": "literal", "value": "active"}}}
    ]
  },
  {
    "name": "user_orders",
    "from": {"table": "orders"},
    "transforms": [
      {"type": "join", "join_type": "inner", "table": "active_users", "condition": {...}}
    ]
  },
  {
    "name": null,
    "from": {"table": "user_orders"},
    "transforms": [
      {"type": "group_by", "dimensions": ["user_id"], "aggregates": [...]}
    ]
  }
]
```

**Rules:**
- **Always an array** at the top level
- Pipelines with `name: null` are standalone queries (output)
- Named pipelines (`name: "something"`) become CTEs/stash references
- Named pipelines can be referenced by later pipelines in `from.table` or `join.table`
- **Multiple unnamed pipelines = multiple queries** (like a SQL file with multiple statements)

### Multiple Standalone Queries (No CTEs)

Like a SQL file with multiple statements:

```json
[
  {
    "name": null,
    "from": {"table": "users"},
    "transforms": [{"type": "limit", "count": 10}]
  },
  {
    "name": null,
    "from": {"table": "orders"},
    "transforms": [{"type": "limit", "count": 10}]
  }
]
```

Generates:
```sql
from users limit 10;
from orders limit 10;
```

### Set Operations (UNION, INTERSECT, EXCEPT)

Pipelines can be combined with set operations:

```json
[
  {
    "name": null,
    "from": {"table": "us_customers"},
    "transforms": [{"type": "select", "columns": ["id", "name", "email"]}],
    "set_operation": {"type": "union", "all": false}
  },
  {
    "name": null,
    "from": {"table": "eu_customers"},
    "transforms": [{"type": "select", "columns": ["id", "name", "email"]}]
  }
]
```

Generates:
```sql
from us_customers
  select id, name, email
UNION
from eu_customers
  select id, name, email
```

**Set operation types:** `union`, `union_all`, `intersect`, `except`

### Visual Representation

In the visual editor, each pipeline would be a separate block:

```
┌─────────────────────────────────────┐
│ ● active_users                      │
│   from users                        │
│   where status == "active"          │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ ● user_orders                       │
│   from orders                       │
│   & active_users on user_id         │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ ● (output)                          │
│   from user_orders                  │
│   group by user_id (count(*) as n)  │
└─────────────────────────────────────┘
```

### ASQL Output

Would generate:

```sql
from users
  where status == "active"
  stash as active_users
from orders
  & active_users on user_id
  stash as user_orders
from user_orders
  group by user_id (
    count(*) as n
  )
```

---

## Implementation Checklist

### Phase 1: JSON Schema Update ✅

- [x] Update `json_to_asql()` to handle array of pipelines
- [x] Backward compatible - old `{from, transforms}` format still works (wrap in array)
- [x] Add `stash as {name}` automatically between named pipelines
- [x] Support set operations (UNION, INTERSECT, EXCEPT)

### Phase 2: Generator Update ✅

- [x] Detect CTEs (`exp.With`) in `VisualASQLGenerator._build_pipelines()`
- [x] Generate `pipelines` array for queries with CTEs
- [x] Handle set operations (UNION, INTERSECT, EXCEPT)
- [x] Handle references between CTEs

### Phase 3: Visual Editor UI ✅

- [x] Output rendering handles multiple pipelines
- [x] Visual separator between pipelines (set operations)
- [x] Pipeline name display
- [x] Add "New Pipeline" button (input editor)
- [x] Pipeline name input field (input editor)
- [x] Set operation selector between pipelines
- [ ] Drag to reorder pipelines (future)
- [ ] Reference autocomplete (future)

### Phase 4: Validation ✅

- [x] Detect circular references
- [x] Validate pipeline names (no spaces, valid identifiers)
- [x] Detect duplicate pipeline names
- [x] Warn about set_operation on last pipeline
- [x] `validate_pipelines()` function in `json_schema.py`

---

## Files to Modify

| File | Changes |
|------|---------|
| `asql/json_schema.py` | Update `json_to_asql()` for pipelines |
| `asql/visual_dialect/generator.py` | Add CTE detection in `_build_json()` |
| `playground/static/visual-editor.js` | Multi-pipeline UI |
| `playground/static/visual-editor.css` | Pipeline block styling |
| `playground/app.py` | Remove CTE rejection in `/api/visual/parse` |
| `tests/test_visual_dialect.py` | Add CTE roundtrip tests |
| `tests/test_json_schema.py` | Add multi-pipeline tests |

---

## Priority

1. **High**: JSON format support (schema + json_to_asql)
2. **Medium**: Generator support (AST → JSON with CTEs)
3. **Lower**: Visual editor UI for multi-pipeline editing
