# Visual ASQL Dialect: Implementation Plan

**Date**: 2026-01-17  
**Status**: Ready for Implementation  
**Goal**: Register `visual_asql` as a proper SQLGlot dialect with full bidirectional JSON ↔ SQL support

---

## Executive Summary

`visual_asql` will be a **first-class SQLGlot dialect** with no wrapper functions needed. It will:

- Accept JSON input via `sqlglot.parse(json_str, read="visual_asql")`
- Output JSON via `sqlglot.transpile(sql, write="visual_asql")`  
- Include `output_columns` at each pipeline stage (for visual editor column pickers)
- Use SQLGlot's native schema/scope tracking internally
- Reference `asql/ui-metadata.json` for transform/operator definitions

---

## Recent Codebase Changes (2026-01-17)

The ASQL codebase has been restructured:

1. **Dialect split into package**: `asql/dialect/` now contains:
   - `tokenizer.py` - ASQLTokenizer
   - `parser.py` - ASQLParser  
   - `generator.py` - ASQLGenerator
   - `dialect.py` - ASQL class + registration
   - `__init__.py` - exports

2. **UI Metadata file**: `asql/ui-metadata.json` contains all ASQL syntax definitions:
   - Transforms with parameters and widgets
   - Operators (comparison, string, null, list, logical)
   - Functions (date, string, math, conditional, window, array)
   - Join types, aggregates, time units, data types

3. **Sync tests**: `tests/test_schema_sync.py` validates that `ui-metadata.json` stays in sync with the parser

4. **Legacy wrappers removed**: `normalize()`, `get_preparsed()`, `ASQLDialect` alias all deleted

---

## Architecture: No Wrappers Needed

Both parsing and generation fit cleanly into SQLGlot's dialect pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                     VisualASQL Dialect                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  JSON Input                              AST                    │
│      │                                    │                     │
│      ▼                                    ▼                     │
│  Dialect.parse()                    Generator.generate()        │
│      │                                    │                     │
│      │ (intercept JSON,                   │ (build JSON with    │
│      │  convert to ASQL text)             │  output_columns)    │
│      ▼                                    ▼                     │
│  ASQL Parser                         JSON Output                │
│      │                                                          │
│      ▼                                                          │
│     AST                                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Insight**: SQLGlot's `Dialect` class has symmetric entry points:
- `Dialect.parse(sql: str)` → before tokenization
- `Dialect.generate(expression)` → calls `Generator.generate()`

---

## Part 1: JSON → SQL (Parsing)

### Approach: Override `Dialect.parse()`

Intercept JSON at string level, convert to ASQL text, delegate to existing parser:

```python
class VisualASQL(Dialect):
    """JSON-based visual ASQL dialect."""
    
    class Tokenizer(ASQLTokenizer):
        pass
    
    class Parser(ASQLParser):
        pass
    
    class Generator(VisualASQLGenerator):
        pass
    
    def parse(self, sql: str, **opts) -> t.List[t.Optional[exp.Expression]]:
        """Intercept JSON input before tokenization."""
        stripped = sql.strip()
        if stripped.startswith('{') or stripped.startswith('['):
            # It's JSON - convert to ASQL text first
            import json
            from asql.json_schema import json_to_asql
            query_json = json.loads(stripped)
            asql_text = json_to_asql(query_json)
            # Delegate to ASQL parser
            return ASQL().parse(asql_text, **opts)
        
        # Not JSON - parse as regular ASQL
        return super().parse(sql, **opts)
```

### Why This Approach?

**We evaluated 3 options:**

| Approach | Lines of Code | Complexity | Decision |
|----------|---------------|------------|----------|
| `json_to_asql()` + existing parser | ~150 lines | Simple string building | ✅ **Chosen** |
| `json_to_ast()` directly | ~1500+ lines | Duplicates parser logic | ❌ |
| Override `Parser.parse()` | ~200 lines | Hacky, re-tokenizes | ❌ |

**Rationale**: The ASQL parser has ~2500 lines of complex transformation logic (relative dates, natural aggregates, when expressions, string operators, etc.). Going through `json_to_asql()` + existing parser means:
- Zero duplication of parsing logic
- All ASQL features work automatically
- `json_to_asql()` is just simple string concatenation

---

## Part 2: SQL → JSON (Generation)

### Approach: Custom Generator with Schema Support

```python
from sqlglot.generator import Generator
from sqlglot.schema import MappingSchema
from sqlglot.optimizer.qualify_columns import qualify_columns
from sqlglot.optimizer.scope import build_scope

class VisualASQLGenerator(Generator):
    """Generator that outputs JSON with column tracking at each stage."""
    
    def __init__(self, schema: MappingSchema = None, **kwargs):
        super().__init__(**kwargs)
        self.schema = schema
    
    def generate(self, expression: exp.Expression, copy: bool = True) -> str:
        """Generate JSON string from AST."""
        if copy:
            expression = expression.copy()
        
        # Pre-qualify columns if schema provided
        if self.schema:
            expression = qualify_columns(expression, self.schema, expand_stars=True)
            self._scope = build_scope(expression)
        else:
            self._scope = None
        
        # Build JSON structure
        result = self._build_json(expression)
        
        import json
        return json.dumps(result, indent=2)
    
    def _build_json(self, expression: exp.Select) -> dict:
        """Build JSON representation of query."""
        result = {'from': None, 'transforms': []}
        current_columns = []
        
        # FROM clause
        if from_clause := expression.args.get('from_'):
            table = from_clause.this
            table_name = table.name
            table_cols = self._get_table_columns(table_name)
            current_columns = table_cols.copy()
            
            result['from'] = {
                'table': table_name,
                'alias': table.alias if table.alias != table_name else None,
                'output_columns': table_cols
            }
        
        # JOINs - accumulate columns
        for join in expression.args.get('joins') or []:
            join_table = join.this.name
            join_cols = self._get_table_columns(join_table)
            current_columns.extend(join_cols)
            
            result['transforms'].append({
                'type': 'join',
                'join_type': self._get_join_type(join),
                'table': join_table,
                'condition': self._expr_to_json(join.args.get('on')),
                'output_columns': current_columns.copy()
            })
        
        # WHERE - columns unchanged
        if where := expression.args.get('where'):
            result['transforms'].append({
                'type': 'where',
                'condition': self._expr_to_json(where.this),
                'output_columns': current_columns.copy()
            })
        
        # GROUP BY - columns change to dimensions + aggregates
        if group := expression.args.get('group'):
            dims, aggs = self._extract_group_by_columns(expression)
            current_columns = dims + aggs
            result['transforms'].append({
                'type': 'group_by',
                'dimensions': dims,
                'aggregates': aggs,
                'output_columns': current_columns.copy()
            })
        
        # SELECT - explicit columns
        elif exprs := expression.args.get('expressions'):
            if not self._is_select_star(exprs):
                current_columns = self._extract_select_columns(exprs)
                result['transforms'].append({
                    'type': 'select',
                    'columns': current_columns,
                    'output_columns': current_columns.copy()
                })
        
        # ORDER BY - columns unchanged
        if order := expression.args.get('order'):
            result['transforms'].append({
                'type': 'order_by',
                'expressions': self._extract_order_columns(order),
                'output_columns': current_columns.copy()
            })
        
        # LIMIT - columns unchanged  
        if limit := expression.args.get('limit'):
            result['transforms'].append({
                'type': 'limit',
                'count': int(limit.this.this),
                'output_columns': current_columns.copy()
            })
        
        return result
    
    def _get_table_columns(self, table_name: str) -> list[dict]:
        """Get columns for a table from schema."""
        if not self.schema:
            return []
        
        cols = self.schema.column_names(table_name)
        return [
            {
                'name': col,
                'type': str(self.schema.get_column_type(table_name, col)),
                'source': table_name
            }
            for col in cols
        ]
    
    # ... additional helper methods ...
```

---

## Part 3: JSON Schema Format

### Mirrors SQLGlot's Internal Structures

**SQLGlot uses:**
```python
# MappingSchema.mapping
{'users': {'id': 'INT', 'name': 'VARCHAR'}, 'orders': {...}}

# Scope.columns  
[Column(table='u', name='id'), Column(table='o', name='amount')]

# Scope.sources
{'u': Table(users), 'o': Table(orders)}
```

**Our JSON format:**
```json
{
  "from": {
    "table": "users",
    "alias": "u",
    "output_columns": [
      {"name": "id", "type": "INT", "source": "users"},
      {"name": "name", "type": "VARCHAR", "source": "users"},
      {"name": "email", "type": "VARCHAR", "source": "users"}
    ]
  },
  "transforms": [
    {
      "type": "join",
      "join_type": "inner",
      "table": "orders",
      "alias": "o",
      "condition": {
        "type": "binary_op",
        "operator": "=",
        "left": {"type": "column", "name": "id", "table": "u"},
        "right": {"type": "column", "name": "user_id", "table": "o"}
      },
      "output_columns": [
        {"name": "id", "type": "INT", "source": "users"},
        {"name": "name", "type": "VARCHAR", "source": "users"},
        {"name": "email", "type": "VARCHAR", "source": "users"},
        {"name": "id", "type": "INT", "source": "orders"},
        {"name": "user_id", "type": "INT", "source": "orders"},
        {"name": "amount", "type": "DECIMAL", "source": "orders"}
      ]
    },
    {
      "type": "where",
      "condition": {...},
      "output_columns": [...]  // Same as after JOIN
    },
    {
      "type": "select",
      "columns": [
        {"name": "name", "source": "users"},
        {"name": "total", "expression": "SUM(orders.amount)"}
      ],
      "output_columns": [
        {"name": "name", "type": "VARCHAR", "source": "users"},
        {"name": "total", "type": "DECIMAL", "expression": "SUM(orders.amount)"}
      ]
    }
  ]
}
```

---

## Part 4: Usage Examples

### Transpile SQL → JSON
```python
import sqlglot
from sqlglot.schema import MappingSchema

schema = MappingSchema({
    'users': {'id': 'INT', 'name': 'VARCHAR', 'email': 'VARCHAR'},
    'orders': {'id': 'INT', 'user_id': 'INT', 'amount': 'DECIMAL'}
})

# SQL → JSON (with column tracking)
json_output = sqlglot.transpile(
    "SELECT name, SUM(amount) as total FROM users JOIN orders ON users.id = orders.user_id GROUP BY name",
    read="postgres",
    write="visual_asql"
)[0]
```

### Transpile JSON → SQL
```python
import sqlglot

json_input = '''
{
  "from": {"table": "users"},
  "transforms": [
    {"type": "where", "condition": {"type": "binary_op", "operator": "=", "left": {"type": "column", "name": "status"}, "right": {"type": "literal", "value": "active"}}},
    {"type": "limit", "count": 10}
  ]
}
'''

# JSON → SQL
sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
# → SELECT * FROM users WHERE status = 'active' LIMIT 10
```

---

## Part 5: File Structure

```
asql/
├── dialect/                   # ASQL dialect package (EXISTING)
│   ├── __init__.py           # Package exports
│   ├── tokenizer.py          # ASQLTokenizer
│   ├── parser.py             # ASQLParser
│   ├── generator.py          # ASQLGenerator
│   └── dialect.py            # ASQL class + registration
│
├── visual_dialect/            # NEW: VisualASQL dialect package
│   ├── __init__.py           # Package exports + registration
│   ├── generator.py          # VisualASQLGenerator (JSON output)
│   └── dialect.py            # VisualASQL class with parse() override
│
├── ui-metadata.json          # UI metadata (EXISTING - used by visual editor)
├── json_schema.py            # Keep existing json_to_asql()
└── __init__.py               # Register both dialects
```

**Note**: The `VisualASQLGenerator` can reference `ui-metadata.json` for consistent
transform/operator definitions between the visual editor and JSON output.

---

## Part 6: Implementation Checklist

### Phase 1: Core Dialect
- [ ] Create `asql/visual_dialect/` package
- [ ] Create `asql/visual_dialect/__init__.py` with exports
- [ ] Implement `VisualASQLGenerator` in `asql/visual_dialect/generator.py`
- [ ] Implement `VisualASQL` dialect in `asql/visual_dialect/dialect.py`
- [ ] Register dialect in `asql/__init__.py`
- [ ] Basic tests: JSON → SQL → JSON roundtrip

### Phase 2: Column Tracking
- [ ] Add `schema` parameter to `VisualASQLGenerator.__init__`
- [ ] Integrate `qualify_columns()` and `annotate_types()`
- [ ] Add `output_columns` to each transform
- [ ] Handle all transform types (JOIN, WHERE, GROUP BY, SELECT, ORDER, LIMIT)
- [ ] Tests with schema provided

### Phase 3: Full ASQL Feature Support
- [ ] Ensure `json_to_asql()` handles all ASQL syntax in `ui-metadata.json`
- [ ] Test relative dates, natural aggregates, string operators
- [ ] Test pipeline semantics (GROUP BY | WHERE → CTE wrapping)
- [ ] Add sync test to ensure JSON schema matches `ui-metadata.json`

### Phase 4: Integration
- [ ] Update playground to use new dialect
- [ ] Documentation

---

## Summary of Key Decisions

| Decision | Rationale |
|----------|-----------|
| **No wrapper functions** | Dialect.parse() and Generator.generate() are symmetric |
| **JSON → ASQL text → AST** | Avoids duplicating 2500 lines of parser logic |
| **Schema passed to Generator** | Generator can use `qualify_columns` + `annotate_types` internally |
| **output_columns at each stage** | Visual editor needs column pickers per transform |
| **Mirror SQLGlot structures** | Consistent with how SQLGlot tracks scope/columns internally |
| **Use ui-metadata.json** | Consistent definitions between visual editor and JSON dialect |

---

## Schema.from_dict Format

The ASQL schema supports SQLGlot-style `{col: type}` format:

```python
Schema.from_dict({
    'tables': {
        'users': {'columns': {'id': 'INT', 'name': 'VARCHAR'}}
    }
})
```

When schema is passed to `VisualASQLGenerator`, it will:
1. Call `qualify_columns()` to resolve table references
2. Call `annotate_types()` to add type info to columns
3. Build JSON with `output_columns` at each stage
