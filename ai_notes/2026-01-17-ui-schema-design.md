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
- ✅ Transforms (with icons, descriptions, parameters!)
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
  - id: "where"
    keywords: ["where"]
    label: "Filter"
    icon: "🔍"
    description: "Filter rows by condition"
    category: "filter"
    fields:
      - { name: "condition", type: "expression", required: true }
  
  - id: "select"
    keywords: ["select", "project"]
    label: "Select Columns"
    icon: "📋"
    description: "Choose which columns to include"
    category: "columns"
    fields:
      - { name: "columns", type: "expression[]", required: true }
  
  - id: "group_by"
    keywords: ["group by"]
    label: "Group & Aggregate"
    icon: "📊"
    description: "Group rows and calculate aggregates"
    category: "aggregate"
    fields:
      - { name: "columns", type: "column[]", required: true }
      - { name: "aggregates", type: "aggregate[]", required: false }
  
  - id: "order_by"
    keywords: ["order by"]
    label: "Sort"
    icon: "↕️"
    description: "Sort rows by columns"
    category: "order"
    fields:
      - { name: "columns", type: "ordered_column[]", required: true }
  
  - id: "limit"
    keywords: ["limit"]
    label: "Limit"
    icon: "✂️"
    description: "Limit number of rows"
    category: "limit"
    fields:
      - { name: "count", type: "number", required: true }
      - { name: "offset", type: "number", required: false }
  
  - id: "join"
    keywords: ["join", "&", "&?", "?&", "?&?"]
    label: "Join"
    icon: "🔗"
    description: "Combine with another table"
    category: "join"
    fields:
      - { name: "table", type: "table", required: true }
      - { name: "type", type: "join_type", required: true }
      - { name: "on", type: "expression", required: false }
  
  - id: "extend"
    keywords: ["extend"]
    label: "Add Column"
    icon: "➕"
    description: "Add a computed column"
    category: "columns"
    fields:
      - { name: "expression", type: "expression", required: true }
      - { name: "alias", type: "identifier", required: true }
  
  - id: "distinct"
    keywords: ["distinct"]
    label: "Deduplicate"
    icon: "🎯"
    description: "Remove duplicate rows"
    category: "filter"
    fields:
      - { name: "on", type: "column[]", required: false }
  
  - id: "except"
    keywords: ["except"]
    label: "Exclude Columns"
    icon: "➖"
    description: "Remove columns from output"
    category: "columns"
    fields:
      - { name: "columns", type: "column[]", required: true }
  
  - id: "rename"
    keywords: ["rename"]
    label: "Rename Columns"
    icon: "✏️"
    description: "Rename one or more columns"
    category: "columns"
    fields:
      - { name: "mappings", type: "rename_pair[]", required: true }
  
  - id: "sample"
    keywords: ["sample"]
    label: "Sample"
    icon: "🎲"
    description: "Random sample of rows"
    category: "filter"
    fields:
      - { name: "count_or_percent", type: "number", required: true }
      - { name: "is_percent", type: "boolean", required: false }
  
  - id: "per"
    keywords: ["per"]
    label: "Window"
    icon: "🪟"
    description: "Window function partitioning"
    category: "window"
    fields:
      - { name: "partition", type: "column[]", required: true }
      - { name: "order", type: "ordered_column[]", required: false }
      - { name: "operation", type: "per_operation", required: true }
  
  - id: "stash"
    keywords: ["stash"]
    label: "Save as CTE"
    icon: "💾"
    description: "Save current query as reusable CTE"
    category: "cte"
    fields:
      - { name: "name", type: "identifier", required: true }
  
  - id: "union"
    keywords: ["union", "union all"]
    label: "Union"
    icon: "⊔"
    description: "Combine with another query"
    category: "set"
    fields:
      - { name: "query", type: "query", required: true }
      - { name: "distinct", type: "boolean", required: false, default: true }
  
  - id: "intersect"
    keywords: ["intersect"]
    label: "Intersect"
    icon: "∩"
    description: "Keep only rows in both queries"
    category: "set"
    fields:
      - { name: "query", type: "query", required: true }
  
  # Advanced
  - id: "cohort"
    keywords: ["cohort"]
    label: "Cohort Analysis"
    icon: "👥"
    description: "Cohort retention analysis"
    category: "analytics"
    fields:
      - { name: "granularity", type: "time_unit", required: true }
      - { name: "date_column", type: "column", required: false }
  
  - id: "deduplicate"
    keywords: ["deduplicate"]
    label: "Deduplicate (keep one)"
    icon: "1️⃣"
    description: "Keep first/last row per group"
    category: "filter"
    fields:
      - { name: "by", type: "column[]", required: true }
      - { name: "keep", type: "first|last", required: false, default: "first" }
  
  - id: "recurse"
    keywords: ["recurse"]
    label: "Recursive Query"
    icon: "🔄"
    description: "Traverse hierarchical data"
    category: "advanced"
    fields:
      - { name: "on", type: "column", required: true }
      - { name: "start", type: "expression", required: true }
      - { name: "max_depth", type: "number", required: false, default: 10 }
```

### 3. Join Types

```yaml
join_types:
  - { symbol: "&", keyword: "join", label: "Inner Join", sql_kind: "INNER" }
  - { symbol: "&?", keyword: "left join", label: "Left Join", sql_kind: "LEFT" }
  - { symbol: "?&", keyword: "right join", label: "Right Join", sql_kind: "RIGHT" }
  - { symbol: "?&?", keyword: "full join", label: "Full Outer Join", sql_kind: "FULL OUTER" }
  - { symbol: "*", keyword: "cross join", label: "Cross Join", sql_kind: "CROSS" }
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
│      id: str                                                         │
│      keywords: list[str]                                             │
│      label: str                                                      │
│      icon: Optional[str]                                             │
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
│    <MenuItem icon={t.icon}>{t.label}</MenuItem>                      │
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

The question is: where does human-readable metadata (labels, descriptions, icons) live?

**Option A: In `dialect_schema.py`** (current approach)
```python
class DIALECT:
    class TRANSFORMS:
        WHERE = {"keywords": ["WHERE"], "label": "Filter", "icon": "🔍", ...}
```

**Option B: In `ui_schema.py`** (separate from dialect)
```python
TRANSFORM_METADATA = {
    "WHERE": {"label": "Filter", "icon": "🔍", "description": "..."},
}
```

**Option C: Derive from dialect, enrich separately**
```python
# ui_schema.py
# Auto-extract from TRANSFORM_PARSERS, then add UI metadata
ENRICHMENTS = {
    "WHERE": {"icon": "🔍"},  # Only what can't be derived
}
```

**Recommendation: Option C**

- Dialect stays clean (parsing logic only)
- UI metadata is UI's concern
- Auto-generation ensures sync
- Enrichments are minimal

---

## Implementation Plan

### Phase 1: Define Pydantic Models
1. Create `asql/ui_schema.py` with Pydantic models for all schema types
2. Define the full `ASQLUISchema` model

### Phase 2: Write Generator Script
1. Create `scripts/generate_ui_schema.py`
2. Extract transforms from `TRANSFORM_PARSERS`
3. Extract operators from parser comparison/string dicts
4. Extract functions from `FUNCTIONS` dict
5. Add UI enrichments (icons, descriptions)

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
  const grouped = groupBy(schema.transforms, 'category');
  
  return (
    <Menu>
      {Object.entries(grouped).map(([category, transforms]) => (
        <MenuGroup label={category}>
          {transforms.map(t => (
            <MenuItem 
              key={t.id}
              icon={t.icon}
              onClick={() => onSelect(t)}
            >
              {t.label}
              <Description>{t.description}</Description>
            </MenuItem>
          ))}
        </MenuGroup>
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
dialect_schema.py (has icons, descriptions, params)
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
- Parser doesn't need icons/descriptions

### Option B: Delete `dialect_schema.py`, Generate from Dialect

```
dialect.py (TRANSFORM_PARSERS, FUNCTIONS, etc.)
         │
         ▼  (introspect + enrich)
enrichments.py (icons, descriptions)
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

## Simplified Approach: Just Export JSON

Actually, for MVP, we might not need Pydantic at all:

```python
# scripts/export_ui_schema.py

def export_ui_schema():
    """Export ASQL schema for UI consumption."""
    
    schema = {
        "operators": {
            "comparison": [
                {"symbol": ">", "label": "greater than"},
                {"symbol": "<", "label": "less than"},
                # ...
            ],
            "string": [
                {"keyword": "contains", "label": "contains"},
                # ...
            ],
        },
        "transforms": [
            {
                "id": "where",
                "keywords": ["where"],
                "label": "Filter",
                "icon": "🔍",
                "category": "filter",
                "description": "Filter rows by condition",
            },
            # ... extract from TRANSFORM_PARSERS
        ],
        "joins": [
            {"symbol": "&", "label": "Inner Join", "kind": "INNER"},
            # ...
        ],
        "aggregates": [...],
        "functions": {...},
    }
    
    with open("playground/static/ui_schema.json", "w") as f:
        json.dump(schema, f, indent=2)
```

Then TypeScript just imports it:
```typescript
import schema from './ui_schema.json';

// Use directly - JSON is already typed by inference
schema.transforms.map(t => <MenuItem icon={t.icon}>{t.label}</MenuItem>)
```

---

## What About `dialect_schema.py`?

Current uses:
1. `DIALECT.TIME_UNITS` - used by parser
2. `DIALECT.OPERATORS.COMPARISON` - used by parser for `_build_comparison`
3. `DIALECT.OPERATORS.STRING` - used by parser for `_parse_comparison`
4. `DIALECT.PER_OPERATIONS` - used by parser
5. `DIALECT.COHORT.GRANULARITIES` - used by parser
6. `DIALECT.TRANSFORMS.all_keywords()` - used to detect transform boundaries

**Recommendation:** Keep `dialect_schema.py` for parser use, but:
1. Remove UI-only fields (icons) from it
2. Keep only what parser needs
3. Generate UI schema separately, enriching with icons/descriptions

Or simpler: Keep it as-is, add an export function that filters out parser-only fields.

---

## Summary

| Aspect | Decision |
|--------|----------|
| **Keep `dialect_schema.py`?** | Yes, for parser use |
| **UI schema format** | JSON (simplest) |
| **Source of truth for UI** | Export script that reads dialect |
| **TypeScript types** | Infer from JSON (or add .d.ts) |
| **Build integration** | `make ui-schema` or pre-commit |

**Immediate action:**
1. Add `scripts/export_ui_schema.py`
2. Generate `playground/static/ui_schema.json`
3. Import in UI components

**Later:**
1. Add Pydantic models if we need validation
2. Add TypeScript type generation if inference isn't enough
3. Consider consolidating `dialect_schema.py` if duplication becomes a problem
