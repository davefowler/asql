# Auto-Deriving Transform Parameters from SQLGlot

**Date:** 2026-01-17  
**Status:** Research / Future Work  
**Question:** Can we auto-generate parameter definitions for UI forms from SQLGlot's existing metadata?

---

## The Problem

For the visual editor, we need to know what parameters each transform accepts:

```python
# What UI needs to render a form:
{
    "where": {
        "parameters": [
            {"name": "condition", "type": "expression", "required": True}
        ]
    },
    "join": {
        "parameters": [
            {"name": "table", "type": "table", "required": True},
            {"name": "on", "type": "expression", "required": False},
            {"name": "kind", "type": "enum", "options": ["inner", "left", "right"], "required": False}
        ]
    }
}
```

Manually defining this for every transform is tedious and error-prone. Can we derive it?

---

## SQLGlot's Existing Metadata

### 1. Expression `arg_types`

Every SQLGlot expression class defines what arguments it accepts:

```python
# From sqlglot/expressions.py
class Select(Query):
    arg_types = {
        "with": False,
        "kind": False,
        "expressions": False,
        "hint": False,
        "distinct": False,
        "into": False,
        "from": False,
        "match": False,
        "laterals": False,
        "joins": False,
        "connect": False,
        "pivots": False,
        "prewhere": False,
        "where": False,
        "group": False,
        "having": False,
        "qualify": False,
        "windows": False,
        "order": False,
        "limit": False,
        "offset": False,
        "locks": False,
        "sample": False,
        "settings": False,
        "format": False,
        "options": False,
    }

class Join(Expression):
    arg_types = {
        "this": True,      # The table to join
        "on": False,       # ON condition
        "side": False,     # LEFT, RIGHT, etc.
        "kind": False,     # INNER, OUTER, CROSS
        "using": False,    # USING columns
        "method": False,   # NATURAL, etc.
        "global": False,
        "hint": False,
    }
```

**Key insight:** `True` = required, `False` = optional.

### 2. Function Signatures

SQLGlot functions have `from_arg_list` that shows expected args:

```python
class Count(AggFunc):
    arg_types = {"this": False, "expressions": False, "big_int": False}
```

### 3. Parser Method Signatures

Our `TRANSFORM_PARSERS` lambdas show what method is called:

```python
"WHERE": lambda self, query: query.where(self._parse_assignment(), copy=False),
"JOIN": lambda self, query: self._parse_asql_join(query, kind="INNER"),
```

---

## Potential Approaches

### Approach A: Map Transforms to Expression Classes

Create a mapping from transform name to the SQLGlot expression it produces:

```python
TRANSFORM_TO_EXPRESSION = {
    "where": exp.Where,
    "select": exp.Select,
    "join": exp.Join,
    "group_by": exp.Group,
    "order_by": exp.Order,
    "limit": exp.Limit,
    "having": exp.Having,
}

def get_parameters(transform_name: str) -> list[dict]:
    expr_class = TRANSFORM_TO_EXPRESSION.get(transform_name)
    if not expr_class:
        return []
    
    params = []
    for arg_name, required in expr_class.arg_types.items():
        params.append({
            "name": arg_name,
            "required": required,
            "type": infer_type(arg_name),  # Heuristic
        })
    return params
```

**Problem:** SQLGlot's arg names are internal (e.g., "this", "expressions") not user-friendly ("condition", "columns").

### Approach B: Use ASQL Parser Method Introspection

Look at what our parser methods call:

```python
def _parse_asql_where(self, query):
    condition = self._parse_assignment()  # <-- One expression parameter
    return query.where(condition, copy=False)

def _parse_asql_join(self, query, kind="INNER"):
    table = self._parse_table()           # <-- Table parameter
    on = self._parse_on_condition()       # <-- Optional expression
    return query.join(table, on=on, kind=kind, copy=False)
```

Could potentially parse/analyze these methods to extract parameters. Complex though.

### Approach C: Explicit Minimal Mapping

Just maintain a simple mapping for ASQL transforms (not auto-derived):

```python
# Manual but simple - only ~20 transforms
TRANSFORM_PARAMETERS = {
    "where": [("condition", "expression", True)],
    "select": [("columns", "column_list", True)],
    "join": [
        ("table", "table", True),
        ("on", "expression", False),
    ],
    "group_by": [("columns", "column_list", True)],
    "order_by": [("columns", "order_list", True)],
    "limit": [("count", "integer", True)],
    "extend": [("expressions", "aliased_list", True)],
    "stash": [("name", "identifier", True)],
    # ... ~12 more
}
```

**Pros:** Simple, explicit, easy to maintain for ~20 transforms.

### Approach D: Hybrid - Derive What We Can

```python
def get_parameters(transform_name: str) -> list[dict]:
    # Check for explicit override first
    if transform_name in EXPLICIT_PARAMETERS:
        return EXPLICIT_PARAMETERS[transform_name]
    
    # Try to derive from expression class
    expr_class = TRANSFORM_TO_EXPRESSION.get(transform_name)
    if expr_class:
        return derive_from_arg_types(expr_class)
    
    # Default: assume single expression parameter
    return [{"name": "expression", "type": "expression", "required": True}]
```

---

## Type Mapping

What "type" values would the UI understand?

| Type | UI Widget | Examples |
|------|-----------|----------|
| `expression` | Expression builder | WHERE condition, ON clause |
| `column` | Column picker | Single column reference |
| `column_list` | Multi-column picker | GROUP BY columns |
| `table` | Table picker | JOIN table |
| `identifier` | Text input | STASH name |
| `integer` | Number input | LIMIT count |
| `order_list` | Order builder | ORDER BY with ASC/DESC |
| `aliased_list` | Expression + alias builder | EXTEND expressions |

---

## Questions to Resolve

1. **Do we even need full parameter definitions?**
   - The UI could use a generic "expression input" for most things
   - Only need special widgets for tables, column lists, etc.

2. **Can the UI introspect at runtime?**
   - Pass the transform name to backend
   - Backend returns parameter schema dynamically
   - Avoids duplicating in frontend

3. **What about ASQL-specific syntax?**
   - `per customer_id first by created_at` has partition cols + operation + order
   - SQLGlot doesn't know about this - must be explicit

---

## Recommendation

**Start with Approach C (explicit minimal mapping)** because:
- Only ~20 transforms to define
- ASQL transforms don't map 1:1 to SQLGlot expressions anyway
- More control over user-friendly names
- Can add Approach D later if needed

Keep the parameter definitions in `dialect_schema.py` alongside transform metadata:

```python
TRANSFORM_SCHEMA = {
    "where": {
        "description": "Filter rows by condition",
        "parameters": [
            {"name": "condition", "type": "expression", "required": True}
        ],
    },
    # ...
}
```

---

## Future: AST-Based Derivation

If we wanted to be clever, we could:

1. Parse a transform's parser method AST
2. Find calls to `self._parse_*` methods
3. Infer parameter types from method names

```python
import ast

def extract_parse_calls(method):
    """Extract _parse_* calls from a method."""
    source = inspect.getsource(method)
    tree = ast.parse(source)
    # Find Call nodes where func is Attribute with attr starting with "_parse_"
    # ...
```

This is probably over-engineering for ~20 transforms, but could be interesting for validation.
