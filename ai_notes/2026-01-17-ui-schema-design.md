# ASQL UI Schema Design

## The Problem

A visual ASQL editor needs to know:
1. What operators are available when building a condition?
2. What transforms can be added to a pipeline?
3. What aggregates are available in GROUP BY?
4. What functions exist and what arguments do they take?
5. What join types are available?

The UI (TypeScript/React) needs this as structured data it can consume.

## Current State

**We already have `dialect_schema.py`** with nested classes containing:
- ✅ Operators (comparison, equality, string, logical)
- ✅ Join types (with symbols, labels, descriptions)
- ✅ Aggregates (count, sum, avg, etc.)
- ✅ Per operations (first, last, number, rank)
- ✅ Transforms (with descriptions, parameters)
- ✅ Time units
- ❌ Functions (not yet)
- ❌ Data types (not yet)

**The issue:** It's Python classes - not directly consumable by TypeScript.

**The question:** Do we need this file at all? Should we:
a) Generate UI schema FROM the dialect parser automatically?
b) Keep `dialect_schema.py` as source of truth and export to JSON?
c) Delete it and put metadata elsewhere?

---

## What the Schema Should Contain

### 1. Operators

```yaml
operators:
  comparison:
    - { symbol: ">", label: "greater than", sql: ">" }
    - { symbol: "<", label: "less than", sql: "<" }
    - { symbol: ">=", label: "greater or equal", sql: ">=" }
    - { symbol: "<=", label: "less or equal", sql: "<=" }
    - { symbol: "=", label: "equals", sql: "=" }
    - { symbol: "!=", label: "not equals", sql: "<>" }
  
  string:
    - { keyword: "contains", label: "contains", description: "Case-sensitive substring match" }
    - { keyword: "icontains", label: "contains (case-insensitive)" }
    - { keyword: "startswith", label: "starts with" }
    - { keyword: "istartswith", label: "starts with (case-insensitive)" }
    - { keyword: "endswith", label: "ends with" }
    - { keyword: "iendswith", label: "ends with (case-insensitive)" }
    - { keyword: "matches", label: "matches regex" }
    - { keyword: "imatches", label: "matches regex (case-insensitive)" }
  
  null:
    - { keyword: "is null", label: "is empty/null" }
    - { keyword: "is not null", label: "has value" }
  
  list:
    - { keyword: "in", label: "is one of" }
    - { keyword: "not in", label: "is not one of" }
  
  logical:
    - { symbol: "&&", label: "and", sql: "AND" }
    - { symbol: "||", label: "or", sql: "OR" }  # Note: in conditions, not string concat
    - { keyword: "not", label: "not", sql: "NOT" }
```

### 2. Transforms (Pipeline Steps)

```yaml
transforms:
  where:
    label: "Filter"
    description: "Filter rows by condition"
    fields:
      - { name: "condition", type: "expression", required: true }
  
  select:
    label: "Select Columns"
    description: "Choose which columns to include"
    fields:
      - { name: "columns", type: "expression[]", required: true }
  
  group_by:
    label: "Group & Aggregate"
    description: "Group rows and calculate aggregates"
    fields:
      - { name: "columns", type: "column[]", required: true }
      - { name: "aggregates", type: "aggregate[]", required: false }
  
  order_by:
    label: "Sort"
    description: "Sort rows by columns"
    fields:
      - { name: "columns", type: "ordered_column[]", required: true }
  
  limit:
    label: "Limit"
    description: "Limit number of rows"
    fields:
      - { name: "count", type: "number", required: true }
      - { name: "offset", type: "number", required: false }
  
  join:
    label: "Join"
    description: "Combine with another table"
    fields:
      - { name: "table", type: "table", required: true }
      - { name: "type", type: "join_type", required: true }
      - { name: "on", type: "expression", required: false }
  
  extend:
    label: "Add Column"
    description: "Add a computed column"
    fields:
      - { name: "expression", type: "expression", required: true }
      - { name: "alias", type: "identifier", required: true }
  
  distinct:
    label: "Deduplicate"
    description: "Remove duplicate rows"
    fields:
      - { name: "on", type: "column[]", required: false }
  
  except:
    label: "Exclude Columns"
    description: "Remove columns from output"
    fields:
      - { name: "columns", type: "column[]", required: true }
  
  rename:
    label: "Rename Columns"
    description: "Rename one or more columns"
    fields:
      - { name: "mappings", type: "rename_pair[]", required: true }
  
  sample:
    label: "Sample"
    description: "Random sample of rows"
    fields:
      - { name: "count_or_percent", type: "number", required: true }
      - { name: "is_percent", type: "boolean", required: false }
  
  per:
    label: "Window"
    description: "Window function partitioning"
    fields:
      - { name: "partition", type: "column[]", required: true }
      - { name: "order", type: "ordered_column[]", required: false }
      - { name: "operation", type: "per_operation", required: true }
  
  stash:
    label: "Save as CTE"
    description: "Save current query as reusable CTE"
    fields:
      - { name: "name", type: "identifier", required: true }
  
  union:
    label: "Union"
    description: "Combine with another query"
    fields:
      - { name: "query", type: "query", required: true }
      - { name: "distinct", type: "boolean", required: false, default: true }
  
  intersect:
    label: "Intersect"
    description: "Keep only rows in both queries"
    fields:
      - { name: "query", type: "query", required: true }
  
  cohort:
    label: "Cohort Analysis"
    description: "Cohort retention analysis"
    fields:
      - { name: "granularity", type: "time_unit", required: true }
      - { name: "date_column", type: "column", required: false }
  
  deduplicate:
    label: "Deduplicate (keep one)"
    description: "Keep first/last row per group"
    fields:
      - { name: "by", type: "column[]", required: true }
      - { name: "keep", type: "first|last", required: false, default: "first" }
  
  recurse:
    label: "Recursive Query"
    description: "Traverse hierarchical data"
    fields:
      - { name: "on", type: "column", required: true }
      - { name: "start", type: "expression", required: true }
      - { name: "max_depth", type: "number", required: false, default: 10 }
```

### 3. Join Types

```yaml
join_types:
  inner: { symbol: "&", label: "Inner Join" }
  left: { symbol: "&?", label: "Left Join" }
  right: { symbol: "?&", label: "Right Join" }
  full: { symbol: "?&?", label: "Full Outer Join" }
  cross: { symbol: "*", label: "Cross Join" }
```

### 4. Aggregates

```yaml
aggregates:
  # Basic
  - { name: "sum", label: "Sum", description: "Total of values", args: ["column"] }
  - { name: "avg", label: "Average", description: "Mean of values", args: ["column"] }
  - { name: "count", label: "Count", description: "Number of rows", args: ["column?"] }
  - { name: "count_distinct", label: "Count Distinct", description: "Number of unique values", args: ["column"] }
  - { name: "min", label: "Minimum", description: "Smallest value", args: ["column"] }
  - { name: "max", label: "Maximum", description: "Largest value", args: ["column"] }
  
  # Statistical
  - { name: "stddev", label: "Std Deviation", description: "Standard deviation", args: ["column"] }
  - { name: "variance", label: "Variance", description: "Statistical variance", args: ["column"] }
  - { name: "median", label: "Median", description: "Middle value", args: ["column"] }
  - { name: "percentile", label: "Percentile", description: "Value at percentile", args: ["column", "percentile"] }
  
  # List/Array
  - { name: "array_agg", label: "Collect to Array", description: "All values as array", args: ["column"] }
  - { name: "string_agg", label: "Concatenate", description: "Join values with separator", args: ["column", "separator"] }
  
  # Conditional
  - { name: "first", label: "First", description: "First value by order", args: ["column", "order_by"] }
  - { name: "last", label: "Last", description: "Last value by order", args: ["column", "order_by"] }
  - { name: "arg_max", label: "Value at Max", description: "Value when another column is max", args: ["return_col", "max_col"] }
  - { name: "arg_min", label: "Value at Min", description: "Value when another column is min", args: ["return_col", "min_col"] }
```

### 5. Functions (by category)

```yaml
functions:
  date:
    - name: "year"
      label: "Year"
      description: "Extract year from date"
      args: [{ name: "date", type: "date|timestamp" }]
      returns: "number"
    
    - name: "month"
      label: "Month"
      args: [{ name: "date", type: "date|timestamp" }]
      returns: "number"
    
    - name: "day"
      label: "Day"
      args: [{ name: "date", type: "date|timestamp" }]
      returns: "number"
    
    - name: "week"
      label: "Week of Year"
      args: [{ name: "date", type: "date|timestamp" }]
      returns: "number"
    
    - name: "date_trunc"
      label: "Truncate Date"
      description: "Truncate to time unit boundary"
      args: [{ name: "unit", type: "time_unit" }, { name: "date", type: "date|timestamp" }]
      returns: "date|timestamp"
    
    - name: "date_diff"
      label: "Date Difference"
      description: "Difference between dates in units"
      args: [{ name: "unit", type: "time_unit" }, { name: "start", type: "date" }, { name: "end", type: "date" }]
      returns: "number"
    
    - name: "date_add"
      label: "Add to Date"
      args: [{ name: "date", type: "date" }, { name: "interval", type: "interval" }]
      returns: "date"
    
    # Natural date functions (ASQL sugar)
    - name: "days_since"
      label: "Days Since"
      description: "Number of days since date"
      args: [{ name: "date", type: "date|timestamp" }]
      returns: "number"
      asql_only: true
    
    - name: "months_since"
      label: "Months Since"
      args: [{ name: "date", type: "date|timestamp" }]
      returns: "number"
      asql_only: true

  string:
    - name: "upper"
      label: "Uppercase"
      args: [{ name: "text", type: "string" }]
      returns: "string"
    
    - name: "lower"
      label: "Lowercase"
      args: [{ name: "text", type: "string" }]
      returns: "string"
    
    - name: "trim"
      label: "Trim Whitespace"
      args: [{ name: "text", type: "string" }]
      returns: "string"
    
    - name: "length"
      label: "Length"
      args: [{ name: "text", type: "string" }]
      returns: "number"
    
    - name: "substr"
      label: "Substring"
      args: [{ name: "text", type: "string" }, { name: "start", type: "number" }, { name: "length", type: "number", optional: true }]
      returns: "string"
    
    - name: "replace"
      label: "Replace"
      args: [{ name: "text", type: "string" }, { name: "search", type: "string" }, { name: "replace", type: "string" }]
      returns: "string"
    
    - name: "concat"
      label: "Concatenate"
      args: [{ name: "parts", type: "string", variadic: true }]
      returns: "string"
    
    - name: "split"
      label: "Split"
      args: [{ name: "text", type: "string" }, { name: "delimiter", type: "string" }]
      returns: "string[]"

  math:
    - name: "abs"
      label: "Absolute Value"
      args: [{ name: "number", type: "number" }]
      returns: "number"
    
    - name: "round"
      label: "Round"
      args: [{ name: "number", type: "number" }, { name: "decimals", type: "number", optional: true }]
      returns: "number"
    
    - name: "floor"
      label: "Floor"
      args: [{ name: "number", type: "number" }]
      returns: "number"
    
    - name: "ceil"
      label: "Ceiling"
      args: [{ name: "number", type: "number" }]
      returns: "number"
    
    - name: "power"
      label: "Power"
      args: [{ name: "base", type: "number" }, { name: "exponent", type: "number" }]
      returns: "number"
    
    - name: "sqrt"
      label: "Square Root"
      args: [{ name: "number", type: "number" }]
      returns: "number"
    
    - name: "log"
      label: "Logarithm"
      args: [{ name: "number", type: "number" }, { name: "base", type: "number", optional: true }]
      returns: "number"

  conditional:
    - name: "coalesce"
      label: "First Non-Null"
      description: "Return first non-null value"
      args: [{ name: "values", type: "any", variadic: true }]
      returns: "any"
    
    - name: "nullif"
      label: "Null If Equal"
      args: [{ name: "value", type: "any" }, { name: "compare", type: "any" }]
      returns: "any"
    
    - name: "if"
      label: "If/Then"
      description: "Conditional expression"
      args: [{ name: "condition", type: "boolean" }, { name: "then", type: "any" }, { name: "else", type: "any" }]
      returns: "any"

  array:
    - name: "array_length"
      label: "Array Length"
      args: [{ name: "array", type: "any[]" }]
      returns: "number"
    
    - name: "array_contains"
      label: "Array Contains"
      args: [{ name: "array", type: "any[]" }, { name: "value", type: "any" }]
      returns: "boolean"
    
    - name: "unnest"
      label: "Unnest Array"
      description: "Expand array to rows"
      args: [{ name: "array", type: "any[]" }]
      returns: "any"

  type:
    - name: "cast"
      label: "Cast"
      description: "Convert to type"
      args: [{ name: "value", type: "any" }, { name: "type", type: "data_type" }]
      returns: "any"
    
    - name: "typeof"
      label: "Type Of"
      args: [{ name: "value", type: "any" }]
      returns: "string"
```

### 6. Time Units

```yaml
time_units:
  - { name: "year", label: "Year", plural: "years" }
  - { name: "quarter", label: "Quarter", plural: "quarters" }
  - { name: "month", label: "Month", plural: "months" }
  - { name: "week", label: "Week", plural: "weeks" }
  - { name: "day", label: "Day", plural: "days" }
  - { name: "hour", label: "Hour", plural: "hours" }
  - { name: "minute", label: "Minute", plural: "minutes" }
  - { name: "second", label: "Second", plural: "seconds" }
```

### 7. Data Types

```yaml
data_types:
  - { name: "string", label: "Text", sql: "VARCHAR" }
  - { name: "number", label: "Number", sql: "NUMERIC" }
  - { name: "integer", label: "Integer", sql: "INTEGER" }
  - { name: "float", label: "Decimal", sql: "FLOAT" }
  - { name: "boolean", label: "Boolean", sql: "BOOLEAN" }
  - { name: "date", label: "Date", sql: "DATE" }
  - { name: "timestamp", label: "Timestamp", sql: "TIMESTAMP" }
  - { name: "time", label: "Time", sql: "TIME" }
  - { name: "json", label: "JSON", sql: "JSON" }
  - { name: "array", label: "Array", sql: "ARRAY" }
```

---

## Schema Format Recommendation

### Option 1: JSON Schema (Recommended for UI)

**Pros:**
- Native to TypeScript/JavaScript
- Well-established tooling (ajv, json-schema-to-typescript)
- Can validate at runtime
- Easy to serve as static file

**Cons:**
- Verbose
- No type inference without codegen

### Option 2: Zod (TypeScript-first)

**Pros:**
- TypeScript-native, great inference
- Runtime validation built-in
- Composable

**Cons:**
- TypeScript only - can't use from Python
- Need to duplicate in Python for dialect

### Option 3: JSON-LD / Schema.org

**Pros:**
- Semantic web standards
- Rich linking

**Cons:**
- Overkill for this use case
- Complex

### Option 4: Pydantic (Python-first) → JSON Schema

**Pros:**
- Define once in Python (near the dialect)
- Auto-generate JSON Schema for TypeScript
- Runtime validation
- Can validate against actual dialect

**Cons:**
- Extra build step to generate JSON Schema

---

## Recommended Approach: Pydantic → JSON Schema → TypeScript

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Python (source of truth)                     │
├─────────────────────────────────────────────────────────────────────┤
│  asql/ui_schema.py                                                   │
│                                                                      │
│  class Operator(BaseModel):                                          │
│      symbol: str                                                     │
│      label: str                                                      │
│      description: Optional[str]                                      │
│                                                                      │
│  class Transform(BaseModel):                                         │
│      label: str                                                      │
│      description: Optional[str]                                      │
│      fields: list[Field]                                             │
│                                                                      │
│  class ASQLUISchema(BaseModel):                                      │
│      operators: Operators                                            │
│      transforms: list[Transform]                                     │
│      aggregates: list[Aggregate]                                     │
│      functions: dict[str, list[Function]]                            │
│      ...                                                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼  (build step: generate)
┌─────────────────────────────────────────────────────────────────────┐
│                         Generated Files                              │
├─────────────────────────────────────────────────────────────────────┤
│  asql/generated/ui_schema.json    ← JSON Schema                      │
│  asql/generated/ui_data.json      ← Actual data populated            │
│  playground/static/asql_schema.ts ← TypeScript types                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         TypeScript UI                                │
├─────────────────────────────────────────────────────────────────────┤
│  import { ASQLUISchema } from './asql_schema';                       │
│  import schemaData from './ui_data.json';                            │
│                                                                      │
│  const schema: ASQLUISchema = schemaData;                            │
│                                                                      │
│  // Now fully typed!                                                 │
│  schema.transforms.map(t => (                                        │
│    <MenuItem>{t.label}</MenuItem>                                     │
│  ))                                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Auto-Generation from Dialect

The schema should be auto-populated from the actual dialect to stay in sync:

```python
# scripts/generate_ui_schema.py

from asql.dialect import ASQLParser, ASQLGenerator
from asql.ui_schema import ASQLUISchema, Transform, Operator

def generate_schema() -> ASQLUISchema:
    """Generate UI schema from dialect definitions."""
    
    transforms = []
    for name, parser_fn in ASQLParser.TRANSFORM_PARSERS.items():
        transforms.append(Transform(
            id=name.lower().replace(" ", "_"),
            keywords=[name],
            label=get_label(name),  # From DIALECT_SCHEMA or derive
            # ... extract other metadata
        ))
    
    operators = extract_operators_from_parser()
    aggregates = extract_from_functions()
    # ...
    
    return ASQLUISchema(
        transforms=transforms,
        operators=operators,
        # ...
    )

def main():
    schema = generate_schema()
    
    # Write JSON data
    with open("asql/generated/ui_data.json", "w") as f:
        f.write(schema.model_dump_json(indent=2))
    
    # Write JSON Schema
    with open("asql/generated/ui_schema.json", "w") as f:
        f.write(schema.model_json_schema())
```

### Where Metadata Lives

The question is: where does human-readable metadata (labels, descriptions) live?

**Option A: In `dialect_schema.py`** (current approach)
```python
class DIALECT:
    class TRANSFORMS:
        WHERE = {"label": "Filter", "description": "Filter rows by condition", ...}
```

**Option B: In `ui_schema.py`** (separate from dialect)
```python
TRANSFORM_METADATA = {
    "WHERE": {"label": "Filter", "description": "..."},
}
```

**Option C: Derive from dialect, enrich separately**
```python
# Auto-extract transform names from TRANSFORM_PARSERS
# Add labels/descriptions in a separate file
```

**Recommendation: Option A (keep in dialect_schema.py)**

- Single source of truth
- Labels/descriptions are useful for docs too
- Parser doesn't care about extra fields
- Simpler than maintaining two files

---

## Implementation Plan

### Phase 1: Write Export Script
1. Create `scripts/export_ui_schema.py`
2. Extract from `dialect_schema.py`
3. Output JSON

### Phase 3: Generate TypeScript Types
1. Use `pydantic-to-typescript` or `json-schema-to-typescript`
2. Generate `asql_schema.ts` for the UI

### Phase 4: Integrate into Build
1. Add to `make build` or pre-commit hook
2. Ensure generated files stay in sync

### Phase 5: Use in UI
1. Import generated types and data
2. Build transform picker, operator dropdown, function autocomplete

---

## Example UI Components Enabled

### Transform Picker
```tsx
function TransformPicker({ onSelect }) {
  return (
    <Menu>
      {Object.entries(schema.transforms).map(([id, t]) => (
        <MenuItem 
          key={id}
          onClick={() => onSelect(id, t)}
        >
          {t.label}
          <Description>{t.description}</Description>
        </MenuItem>
      ))}
    </Menu>
  );
}
```

### Operator Dropdown
```tsx
function OperatorSelect({ columnType, value, onChange }) {
  // Filter operators by column type
  const available = [
    ...schema.operators.comparison,
    ...(columnType === 'string' ? schema.operators.string : []),
    ...schema.operators.null,
  ];
  
  return (
    <Select value={value} onChange={onChange}>
      {available.map(op => (
        <Option key={op.symbol || op.keyword} value={op.symbol || op.keyword}>
          {op.label}
        </Option>
      ))}
    </Select>
  );
}
```

### Function Autocomplete
```tsx
function FunctionAutocomplete({ search }) {
  const allFunctions = Object.values(schema.functions).flat();
  const matches = allFunctions.filter(f => 
    f.name.includes(search) || f.label.includes(search)
  );
  
  return matches.map(fn => (
    <Suggestion key={fn.name}>
      <FunctionName>{fn.name}</FunctionName>
      <Args>{fn.args.map(a => a.name).join(', ')}</Args>
      <ReturnType>{fn.returns}</ReturnType>
    </Suggestion>
  ));
}
```

---

---

## Key Decision: Where Should Metadata Live?

### Option A: Keep `dialect_schema.py` as Source of Truth

```
dialect_schema.py (has labels, descriptions, params)
         │
         ▼  (export script)
    ui_schema.json  →  TypeScript imports
```

**Pros:**
- Already exists with most data
- Single place to update
- Parser can use same definitions

**Cons:**
- Mixes parser concerns with UI concerns
- Python classes aren't ideal format

### Option B: Delete `dialect_schema.py`, Generate from Dialect

```
dialect.py (TRANSFORM_PARSERS, FUNCTIONS, etc.)
         │
         ▼  (introspect + enrich)
enrichments.py (labels, descriptions)
         │
         ▼  (generate script)
    ui_schema.json  →  TypeScript imports
```

**Pros:**
- Dialect stays clean (parser logic only)
- Can't get out of sync with parser
- UI metadata is UI's concern

**Cons:**
- More indirection
- Enrichments file can drift from parser

### Option C: Pydantic Models as Schema (New)

```
ui_schema.py (Pydantic models - define the SHAPE)
         │
         ├───────────────────────┐
         ▼                       ▼
dialect_data.py           JSON Schema export
(populate from dialect)   TypeScript types
         │
         ▼
    ui_data.json
```

**Pros:**
- Clear separation: shape vs data
- Type-safe in both languages
- Pydantic validates data

**Cons:**
- New abstraction
- More files

---

## Recommendation: Option C (Pydantic Schema + Data)

The issue with current `dialect_schema.py` is it conflates:
1. **Shape** (what fields exist)
2. **Data** (actual operators/transforms)
3. **Parser concerns** (expr_class, tokens)

Better structure:

```
asql/
  ui_schema.py      ← Pydantic models (shape only, no data)
  ui_data.py        ← Function to populate schema from dialect
  
scripts/
  export_ui_schema.py  ← Generates JSON + TypeScript
  
generated/
  ui_schema.json    ← JSON Schema (validates structure)
  ui_data.json      ← Actual data for UI
  
playground/static/
  asql_schema.ts    ← TypeScript types
```

---

## FINAL APPROACH: Static JSON + Validation Tests

After discussion, the simplest approach is:

1. **`asql/schema.json`** - Static JSON file with all UI metadata
2. **`tests/test_schema_sync.py`** - Tests that validate JSON keys match parser

```
┌─────────────────┐      ┌─────────────────┐
│  schema.json    │      │   dialect.py    │
│  (UI metadata)  │      │   (parser)      │
│                 │      │                 │
│  - labels       │      │  - TokenTypes   │
│  - descriptions │      │  - keywords     │
│  - parameters   │      │  - actual logic │
└────────┬────────┘      └────────┬────────┘
         │                        │
         └──────────┬─────────────┘
                    │
             ┌──────▼──────┐
             │    TESTS    │
             │  validate   │
             │  keys match │
             └─────────────┘
```

### Why This Works

- **No code generation** - just a JSON file
- **No Pydantic/dataclasses** - plain data
- **No imports between schema and parser** - clean separation
- **JSON is directly consumable by JS** - no build step
- **Tests catch drift immediately** - if you add a parser feature and forget schema, test fails
- **"Duplication" is useful** - parser needs `expr_class`, UI needs `label`

### The Files

**`asql/schema.json`** - Hand-written, all UI metadata:
```json
{
  "operators": {
    "comparison": {
      ">": { "label": ">", "description": "Greater than" },
      "<": { "label": "<", "description": "Less than" }
    },
    "string": {
      "contains": { "label": "contains", "description": "Case-sensitive substring" }
    }
  },
  "transforms": {
    "where": { "label": "Filter", "category": "filter", "description": "..." }
  },
  "joins": {
    "inner": { "symbol": "&", "label": "inner (&)" }
  }
}
```

**`tests/test_schema_sync.py`** - Validation:
```python
def test_transforms_sync():
    """Ensure schema transforms match parser TRANSFORM_PARSERS."""
    from asql.dialect import ASQLParser
    import json
    
    with open("asql/schema.json") as f:
        schema = json.load(f)
    
    # Normalize keys for comparison
    parser_transforms = {k.lower().replace(" ", "_") for k in ASQLParser.TRANSFORM_PARSERS.keys()}
    schema_transforms = set(schema["transforms"].keys())
    
    # Some parser keys are internal (ASQL_INNER_JOIN etc)
    internal_keys = {k for k in parser_transforms if k.startswith("asql_")}
    parser_transforms -= internal_keys
    
    assert parser_transforms == schema_transforms, f"""
        In parser only: {parser_transforms - schema_transforms}
        In schema only: {schema_transforms - parser_transforms}
    """
```

**`asql/ui_schema.py`** - Thin wrapper:
```python
import json
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.json"

def get_schema():
    with open(_SCHEMA_PATH) as f:
        return json.load(f)

def get_operation_schema(op_type: str):
    return get_schema()["transforms"].get(op_type, {})
```

---

## What to Delete

**`asql/dialect_schema.py`** - DELETE entirely. It was trying to be:
- Source of truth for parser (but parser has its own dicts)
- Source of truth for UI (but we now have schema.json)
- Type-safe with dataclasses (but added complexity without benefit)

The 2 places in `dialect.py` that import from it can be refactored to use simple dicts.

---

## Summary

| Aspect | Decision |
|--------|----------|
| **Delete `dialect_schema.py`?** | YES |
| **UI schema format** | Static JSON file |
| **Source of truth for UI** | `asql/schema.json` |
| **Validation** | Tests compare JSON keys to parser |
| **TypeScript types** | Infer from JSON (add later if needed) |

**Implementation:**
1. Create `asql/schema.json` with all UI data
2. Update `asql/ui_schema.py` to read from JSON
3. Write `tests/test_schema_sync.py` 
4. Remove dialect_schema imports from `dialect.py`
5. Delete `dialect_schema.py`
