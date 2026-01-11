# Visual ASQL Editor - Design Document

## Executive Summary

This document outlines three approaches for building a visual interface for ASQL, a pipeline-based query language. Each approach has different implementation requirements, UX characteristics, and technical trade-offs. After detailed analysis, we recommend **Approach 2: Pipeline Block UI** as the optimal solution for most users, with **Approach 1: Enhanced Text Editor** as a complementary power-user feature.

## Background: ASQL Architecture

### Current Compilation Pipeline

```
ASQL Text → sqlglot.parse(dialect="asql") → AST → Transformations → SQL
```

**Key Components:**
- **Parser**: Custom `ASQLParser` extending SQLGlot's base classes
- **AST**: Native SQLGlot AST (`sqlglot.exp` nodes like `Select`, `Where`, `Join`)
- **Transforms**: Modular transformation passes (cohort expansion, pivot, auto-aliasing, etc.)
- **Schema System**: Relationship inference, column metadata, validation

**Critical Gap**: No JSON serialization layer exists yet - AST is pure Python objects.

### ASQL Syntax Characteristics

**Pipeline-Based:**
```asql
from orders
  & customers on customer_id           # Join with FK inference
  where status == "completed"          # Natural equality operator
  group by region, month(order_date) ( # Inline aggregations
    count(distinct order_id) as orders,
    sum(amount) as revenue
  )
  order by -revenue                    # Minus for descending
  limit 10
```

**Key Features:**
- FROM-first (not SELECT-first)
- Indentation-based or pipe (`|`) for chaining
- Symbolic joins: `&` (inner), `&?` (left), `?&` (right), `?&?` (full), `*` (cross)
- Natural operators: `==`, `!=`, `#` (count), `-col` (descending)
- Date literals: `@2024-01-15`
- String matching: `contains`, `starts with`, `icontains`
- CTEs via `stash as name`

---

## Approach 1: Enhanced Text Editor

### Concept

Build an intelligent code editor with contextual UI overlays that provide visual affordances for ASQL syntax without leaving the text paradigm. Think VS Code IntelliSense meets CodeMirror widgets - the text remains the source of truth, but UI elements provide discoverability and ease-of-use.

### Architecture

#### Frontend Stack
- **Editor**: CodeMirror 6 or Monaco Editor
- **Framework**: React or Svelte (lightweight)
- **UI Components**: Radix UI or Headless UI for menus/popups

#### Backend Requirements

**1. Language Server Protocol (LSP) Implementation**
```
ASQL LSP Server (Python)
├── Parser Integration (sqlglot dialect)
├── Diagnostics (syntax errors, type checking)
├── Completions (columns, functions, tables)
├── Hover Information (function docs, column types)
└── Code Actions (quick fixes, refactorings)
```

**Implementation:**
- Use `pygls` (Python Generic Language Server)
- Leverage existing `asql.dialect.ASQLParser` for parsing
- Use `asql.schema.Schema` for autocomplete metadata
- Parse on every keystroke (incremental parsing)

**2. Widget Overlay System**

Track cursor position and AST context to show contextual UI:

```python
# Backend endpoint: POST /editor/context
{
  "query": "from orders\n  where status == ",
  "cursor_position": {"line": 1, "col": 25}
}

# Response:
{
  "context": {
    "type": "where_condition_value",
    "column": "status",
    "column_type": "string",
    "suggestions": ["completed", "pending", "cancelled"]  # from schema
  }
}
```

**3. AST Manipulation API**

Instead of regex string manipulation, provide structured edits:

```python
# Endpoint: POST /editor/insert_step
{
  "query": "from orders\n  where status == 'completed'",
  "cursor_line": 1,
  "step": {"type": "group_by", "columns": ["region"]}
}

# Returns:
{
  "new_query": "from orders\n  where status == 'completed'\n  group by region",
  "cursor_position": {"line": 2, "col": 16}
}
```

This uses the AST to:
1. Parse existing query
2. Insert new AST node at appropriate location
3. Regenerate ASQL text with proper indentation
4. Return new text + cursor position

#### UI Components

**1. Pipeline Step Insertion Menu**
- Trigger: Keyboard shortcut (Cmd+K), button in toolbar, or right-click
- Shows context-aware step options:
  - After FROM: `where`, `join`, `group by`, `select`, `order by`, `limit`
  - After GROUP BY: `having`, `select`, `order by`, `limit`
- Inserts template with placeholders
- Focuses first placeholder for immediate editing

**2. Column/Function Dropdown Menus**
- Parse AST to detect column references and function calls
- Render inline dropdowns for:
  - Column names (from schema or inferred from upstream)
  - Function names (date functions, aggregations, string functions)
  - Join table names (from schema)
- Widget overlay appears on hover or focus

**3. Operator Palette**
- Natural language operators become buttons:
  - `contains`, `starts with`, `ends with`, `icontains`
  - Date comparisons: `since`, `until`, `between`
- Hover over operator shows description/examples

**4. Schema Panel**
- Side panel showing available tables/columns
- Drag column to insert at cursor
- Shows relationships (FK arrows)
- Search/filter capabilities

**5. Visual Join Builder**
- Detect join expressions in AST
- Show inline diagram:
  ```
  [orders] ──&──> [customers]
           on customer_id
  ```
- Click to change join type: `&` → `&?` → `?&` → `?&?` → `*`
- Edit condition in place

#### Implementation Details

**CodeMirror 6 Extensions:**

```typescript
import { ViewPlugin, Decoration, EditorView } from "@codemirror/view"
import { syntaxTree } from "@codemirror/language"

// Widget for column dropdowns
const columnDropdownPlugin = ViewPlugin.fromClass(class {
  decorations: DecorationSet

  update(update: ViewUpdate) {
    // Parse syntax tree
    const tree = syntaxTree(update.state)
    const widgets = []

    // Find all column references
    tree.iterate({
      enter(node) {
        if (node.name === "Column") {
          // Add dropdown widget decoration
          widgets.push(
            Decoration.widget({
              widget: new ColumnDropdown(node.from, node.to),
              side: 1
            }).range(node.to)
          )
        }
      }
    })

    this.decorations = Decoration.set(widgets)
  }
})
```

**Step Insertion Command:**

```typescript
async function insertPipelineStep(view: EditorView, stepType: string) {
  const cursor = view.state.selection.main.head
  const currentQuery = view.state.doc.toString()

  // Call backend to get structured insert
  const response = await fetch('/editor/insert_step', {
    method: 'POST',
    body: JSON.stringify({
      query: currentQuery,
      cursor_position: cursor,
      step_type: stepType
    })
  })

  const { new_query, cursor_position } = await response.json()

  // Apply edit
  view.dispatch({
    changes: { from: 0, to: view.state.doc.length, insert: new_query },
    selection: { anchor: cursor_position }
  })
}
```

**Column Autocomplete from Schema:**

```typescript
import { autocompletion } from "@codemirror/autocomplete"

const schemaAutocomplete = autocompletion({
  override: [
    async (context) => {
      // Get AST context from backend
      const astContext = await getASTContext(
        context.state.doc.toString(),
        context.pos
      )

      // Return completions based on context
      if (astContext.type === "column_reference") {
        return {
          from: context.pos,
          options: astContext.available_columns.map(col => ({
            label: col.name,
            type: "property",
            detail: col.type,
            info: col.description
          }))
        }
      }

      if (astContext.type === "function_name") {
        return {
          from: context.pos,
          options: ASQL_FUNCTIONS.map(fn => ({
            label: fn.name,
            type: "function",
            apply: `${fn.name}()`,
            detail: fn.signature,
            info: fn.description
          }))
        }
      }
    }
  ]
})
```

#### Pros

**For Users:**
- ✅ **Low learning curve**: Familiar text editor experience
- ✅ **Flexible**: Power users can type freely, beginners can click
- ✅ **Copyable**: Queries remain plain text (easy to share/version)
- ✅ **Fast**: No mode switching, continuous editing flow
- ✅ **Accessible**: Screen readers work with text

**For Developers:**
- ✅ **Incremental**: Can ship features one at a time
- ✅ **Reusable**: LSP benefits CLI/web/desktop editors
- ✅ **Minimal backend changes**: Mostly leverages existing parser
- ✅ **No sync issues**: Text is always source of truth

#### Cons

**For Users:**
- ❌ **Still requires typing**: Not truly "visual" for non-technical users
- ❌ **Syntax exposure**: Users still see `&`, `==`, etc. (not natural language)
- ❌ **Cognitive load**: Must understand indentation/structure rules
- ❌ **Discovery**: Features hidden behind keyboard shortcuts/right-clicks

**For Developers:**
- ❌ **Complex editor integration**: CodeMirror/Monaco have steep learning curves
- ❌ **LSP overhead**: Requires maintaining a separate server process
- ❌ **Widget positioning**: Complex to get overlays pixel-perfect
- ❌ **Not fully visual**: Doesn't eliminate syntax entirely

#### Implementation Estimate

**Phase 1: Core LSP (2-3 weeks)**
- Basic syntax highlighting
- Error diagnostics
- Simple completions (keywords, tables)

**Phase 2: Schema Integration (1-2 weeks)**
- Column autocomplete
- Type checking
- Relationship inference in joins

**Phase 3: Widget System (3-4 weeks)**
- Column dropdowns
- Function palette
- Join visualizer

**Phase 4: Step Insertion (2 weeks)**
- Template insertion commands
- AST-based editing API
- Keyboard shortcuts

**Total: 8-11 weeks** (2-3 months)

---

## Approach 2: Pipeline Block UI

### Concept

A fully visual interface where each pipeline step is rendered as a discrete UI block/card. Users construct queries by adding, configuring, and reordering blocks. No syntax exposure - all interactions are through forms, dropdowns, and visual connectors. Think Chartio's Visual SQL, Looker's Explore, or dbt's Jaffle Shop UI.

### Architecture

#### Frontend Stack
- **Framework**: React (most mature component ecosystem)
- **Drag & Drop**: `@dnd-kit/core` (modern, accessible)
- **Forms**: React Hook Form + Zod for validation
- **UI Components**: Radix UI or shadcn/ui (form-heavy use case)
- **State**: Zustand or Jotai (lightweight, less boilerplate than Redux)

#### Backend Requirements

**1. JSON Schema for Query Representation**

Define a declarative JSON format that mirrors the ASQL AST structure:

```json
{
  "version": "1.0",
  "from": {
    "table": "orders",
    "alias": null
  },
  "transforms": [
    {
      "id": "t1",
      "type": "join",
      "join_type": "inner",
      "table": "customers",
      "alias": null,
      "on": {
        "type": "binary_op",
        "operator": "=",
        "left": {"type": "column", "name": "customer_id"},
        "right": {"type": "column", "name": "customer_id"}
      }
    },
    {
      "id": "t2",
      "type": "where",
      "condition": {
        "type": "binary_op",
        "operator": "=",
        "left": {"type": "column", "name": "status"},
        "right": {"type": "literal", "value": "completed", "data_type": "string"}
      }
    },
    {
      "id": "t3",
      "type": "group_by",
      "dimensions": [
        {"type": "column", "name": "region"}
      ],
      "aggregates": [
        {
          "function": "count",
          "arguments": [{"type": "column", "name": "order_id"}],
          "distinct": true,
          "alias": "order_count"
        },
        {
          "function": "sum",
          "arguments": [{"type": "column", "name": "amount"}],
          "alias": "total_revenue"
        }
      ]
    },
    {
      "id": "t4",
      "type": "order_by",
      "expressions": [
        {
          "column": "total_revenue",
          "direction": "desc"
        }
      ]
    },
    {
      "id": "t5",
      "type": "limit",
      "count": 10
    }
  ]
}
```

**2. Bidirectional Converters**

```python
# asql/json_schema.py

from typing import Dict, Any, List
from sqlglot import exp
from dataclasses import dataclass

@dataclass
class ASQLQuery:
    """Structured representation of ASQL query"""
    from_: FromClause
    transforms: List[Transform]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON"""
        return {
            "version": "1.0",
            "from": self.from_.to_dict(),
            "transforms": [t.to_dict() for t in self.transforms]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ASQLQuery":
        """Deserialize from JSON"""
        return cls(
            from_=FromClause.from_dict(data["from"]),
            transforms=[Transform.from_dict(t) for t in data["transforms"]]
        )

    def to_ast(self) -> exp.Select:
        """Convert to sqlglot AST"""
        select = exp.Select()
        select.set("from", self.from_.to_ast())

        for transform in self.transforms:
            transform.apply_to_ast(select)

        return select

    @classmethod
    def from_ast(cls, ast: exp.Select) -> "ASQLQuery":
        """Extract from sqlglot AST"""
        from_ = FromClause.from_ast(ast.args.get("from"))
        transforms = []

        # Extract transforms in pipeline order
        if where := ast.args.get("where"):
            transforms.append(WhereTransform.from_ast(where))
        if joins := ast.args.get("joins"):
            transforms.extend(JoinTransform.from_ast(j) for j in joins)
        if group := ast.args.get("group"):
            transforms.append(GroupByTransform.from_ast(group))
        # ... etc

        return cls(from_=from_, transforms=transforms)
```

**Key Classes:**

```python
class Transform(ABC):
    """Base class for all pipeline transforms"""
    id: str
    type: str

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]: ...

    @abstractmethod
    def apply_to_ast(self, select: exp.Select) -> None: ...

class WhereTransform(Transform):
    condition: Expression

class JoinTransform(Transform):
    join_type: str  # "inner", "left", "right", "full", "cross"
    table: str
    on: Optional[Expression]

class GroupByTransform(Transform):
    dimensions: List[Expression]
    aggregates: List[AggregateFunction]

class SelectTransform(Transform):
    columns: List[SelectColumn]  # Can be column, expression, or wildcard

class OrderByTransform(Transform):
    expressions: List[OrderExpression]

# Expression tree types
class Expression(ABC): ...
class ColumnRef(Expression): ...
class BinaryOp(Expression): ...
class FunctionCall(Expression): ...
class Literal(Expression): ...
```

**3. Schema-Driven Form Generation**

```python
# asql/form_schema.py

def get_transform_form_schema(
    transform_type: str,
    context: QueryContext
) -> Dict[str, Any]:
    """
    Generate JSON Schema for configuring a transform.
    Context includes available columns, tables, functions.
    """

    if transform_type == "where":
        return {
            "type": "object",
            "properties": {
                "condition": {
                    "type": "expression",
                    "operators": ["=", "!=", "<", ">", "<=", ">=", "contains", "in"],
                    "available_columns": context.columns,
                    "value_suggestions": context.get_value_suggestions()
                }
            }
        }

    if transform_type == "join":
        return {
            "type": "object",
            "properties": {
                "join_type": {
                    "type": "enum",
                    "options": ["inner", "left", "right", "full", "cross"],
                    "labels": {
                        "inner": "Inner Join (& in ASQL)",
                        "left": "Left Join (&? in ASQL)",
                        # ...
                    }
                },
                "table": {
                    "type": "string",
                    "enum": context.available_tables,
                    "autocomplete": True
                },
                "on": {
                    "type": "expression",
                    "optional": True,  # Can be inferred from schema
                    "inferred_value": context.infer_join_condition()
                }
            }
        }

    if transform_type == "group_by":
        return {
            "type": "object",
            "properties": {
                "dimensions": {
                    "type": "array",
                    "items": {
                        "type": "column_or_expression",
                        "available_columns": context.columns,
                        "available_functions": ["date_trunc", "month", "year", "quarter"]
                    }
                },
                "aggregates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "function": {
                                "type": "enum",
                                "options": ["count", "sum", "avg", "min", "max", "count_distinct"]
                            },
                            "column": {
                                "type": "string",
                                "enum": context.columns
                            },
                            "alias": {"type": "string"}
                        }
                    }
                }
            }
        }
```

**4. API Endpoints**

```python
# asql/api/visual_editor.py

from fastapi import APIRouter, HTTPException
from asql.json_schema import ASQLQuery
from asql.compiler.api import compile_query
from asql.schema import Schema

router = APIRouter(prefix="/visual-editor")

@router.post("/query/compile")
async def compile_visual_query(
    query: Dict[str, Any],
    target_dialect: str = "postgres"
):
    """Convert JSON query to SQL"""
    try:
        asql_query = ASQLQuery.from_dict(query)
        ast = asql_query.to_ast()
        result = compile_query(ast, dialect=target_dialect)
        return {
            "sql": result.sql,
            "asql": result.asql,
            "success": True
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/query/parse")
async def parse_asql_to_visual(asql_text: str):
    """Convert ASQL text to JSON representation"""
    try:
        ast = compile_to_ast(asql_text)
        asql_query = ASQLQuery.from_ast(ast)
        return asql_query.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/query/validate")
async def validate_query(
    query: Dict[str, Any],
    schema: Optional[Dict[str, Any]] = None
):
    """Validate query structure and references"""
    asql_query = ASQLQuery.from_dict(query)
    schema_obj = Schema.from_dict(schema) if schema else None

    errors = []
    warnings = []

    # Check for undefined columns
    # Check for type mismatches
    # Check for invalid join conditions
    # ...

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }

@router.get("/forms/transform/{transform_type}")
async def get_transform_form(
    transform_type: str,
    query_context: Dict[str, Any]
):
    """Get form schema for configuring a transform"""
    context = QueryContext.from_dict(query_context)
    form_schema = get_transform_form_schema(transform_type, context)
    return form_schema

@router.post("/query/context")
async def get_query_context(
    query: Dict[str, Any],
    transform_id: str
):
    """Get available columns/tables at a specific point in the query"""
    asql_query = ASQLQuery.from_dict(query)

    # Build context up to transform_id
    available_columns = []
    available_tables = []

    # Walk through transforms up to transform_id
    # Track which columns are available at each step

    return {
        "columns": available_columns,
        "tables": available_tables,
        "relationships": []
    }
```

#### UI Components

**1. Pipeline Canvas**

Main container showing the linear flow of transforms:

```tsx
// components/PipelineCanvas.tsx

import { DndContext, DragEndEvent } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'

interface Pipeline {
  from: FromBlock
  transforms: Transform[]
}

function PipelineCanvas({ pipeline, onChange }: Props) {
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (over && active.id !== over.id) {
      // Reorder transforms
      const oldIndex = transforms.findIndex(t => t.id === active.id)
      const newIndex = transforms.findIndex(t => t.id === over.id)
      onChange(arrayMove(pipeline.transforms, oldIndex, newIndex))
    }
  }

  return (
    <DndContext onDragEnd={handleDragEnd}>
      <div className="pipeline-canvas">
        <FromBlockComponent block={pipeline.from} onChange={...} />

        <SortableContext
          items={pipeline.transforms.map(t => t.id)}
          strategy={verticalListSortingStrategy}
        >
          {pipeline.transforms.map((transform) => (
            <TransformBlock
              key={transform.id}
              transform={transform}
              onChange={...}
              onDelete={...}
            />
          ))}
        </SortableContext>

        <AddStepButton onAdd={handleAddStep} />
      </div>
    </DndContext>
  )
}
```

**2. Transform Block Components**

Each transform type gets a custom component:

```tsx
// components/blocks/WhereBlock.tsx

function WhereBlock({ transform, context, onChange }: Props) {
  const { condition } = transform

  return (
    <BlockContainer
      icon={<FilterIcon />}
      title="Filter"
      color="blue"
    >
      <ExpressionBuilder
        expression={condition}
        availableColumns={context.columns}
        onChange={(newCondition) =>
          onChange({ ...transform, condition: newCondition })
        }
      />

      <Button onClick={addAndCondition}>
        Add AND condition
      </Button>
    </BlockContainer>
  )
}

// components/blocks/JoinBlock.tsx

function JoinBlock({ transform, context, onChange }: Props) {
  const { join_type, table, on } = transform
  const inferredOn = context.inferJoinCondition(table)

  return (
    <BlockContainer
      icon={<JoinIcon />}
      title="Join"
      color="purple"
    >
      <JoinTypeSelector
        value={join_type}
        onChange={(type) => onChange({ ...transform, join_type: type })}
        options={[
          { value: "inner", label: "Inner Join", icon: "⋈" },
          { value: "left", label: "Left Join", icon: "⟕" },
          { value: "right", label: "Right Join", icon: "⟖" },
          { value: "full", label: "Full Join", icon: "⟗" },
          { value: "cross", label: "Cross Join", icon: "×" }
        ]}
      />

      <TableSelector
        value={table}
        options={context.available_tables}
        onChange={(newTable) => onChange({ ...transform, table: newTable })}
      />

      {inferredOn && (
        <InferredBadge>
          Join condition inferred from schema
        </InferredBadge>
      )}

      <ExpressionBuilder
        expression={on || inferredOn}
        availableColumns={context.columns}
        onChange={(newOn) => onChange({ ...transform, on: newOn })}
        placeholder="Specify join condition"
      />
    </BlockContainer>
  )
}

// components/blocks/GroupByBlock.tsx

function GroupByBlock({ transform, context, onChange }: Props) {
  const { dimensions, aggregates } = transform

  return (
    <BlockContainer
      icon={<GroupIcon />}
      title="Group By"
      color="green"
    >
      <Section label="Group By">
        {dimensions.map((dim, i) => (
          <DimensionRow
            key={i}
            dimension={dim}
            availableColumns={context.columns}
            onChange={(newDim) => {
              const newDimensions = [...dimensions]
              newDimensions[i] = newDim
              onChange({ ...transform, dimensions: newDimensions })
            }}
            onRemove={() => removeDimension(i)}
          />
        ))}
        <Button onClick={addDimension}>+ Add dimension</Button>
      </Section>

      <Section label="Aggregations">
        {aggregates.map((agg, i) => (
          <AggregateRow
            key={i}
            aggregate={agg}
            availableColumns={context.columns}
            onChange={(newAgg) => {
              const newAggregates = [...aggregates]
              newAggregates[i] = newAgg
              onChange({ ...transform, aggregates: newAggregates })
            }}
            onRemove={() => removeAggregate(i)}
          />
        ))}
        <Button onClick={addAggregate}>+ Add aggregate</Button>
      </Section>
    </BlockContainer>
  )
}
```

**3. Expression Builder**

Universal component for building WHERE conditions, join ON clauses, computed columns:

```tsx
// components/ExpressionBuilder.tsx

interface Expression {
  type: 'binary_op' | 'column' | 'literal' | 'function'
  // ...
}

function ExpressionBuilder({ expression, availableColumns, onChange }: Props) {
  if (!expression) {
    return <NewExpressionPicker onSelect={onChange} />
  }

  if (expression.type === 'binary_op') {
    return (
      <div className="flex items-center gap-2">
        <ExpressionBuilder
          expression={expression.left}
          availableColumns={availableColumns}
          onChange={(left) => onChange({ ...expression, left })}
        />

        <OperatorSelector
          value={expression.operator}
          onChange={(op) => onChange({ ...expression, operator: op })}
          options={['=', '!=', '<', '>', '<=', '>=', 'contains', 'in']}
        />

        <ExpressionBuilder
          expression={expression.right}
          availableColumns={availableColumns}
          onChange={(right) => onChange({ ...expression, right })}
        />
      </div>
    )
  }

  if (expression.type === 'column') {
    return (
      <Combobox
        value={expression.name}
        options={availableColumns.map(col => ({
          value: col.name,
          label: col.name,
          description: col.type
        }))}
        onChange={(name) => onChange({ ...expression, name })}
      />
    )
  }

  if (expression.type === 'literal') {
    return (
      <LiteralInput
        value={expression.value}
        dataType={expression.data_type}
        onChange={(value) => onChange({ ...expression, value })}
      />
    )
  }

  if (expression.type === 'function') {
    return (
      <FunctionBuilder
        func={expression}
        availableColumns={availableColumns}
        onChange={onChange}
      />
    )
  }
}
```

**4. Schema Panel**

Side panel for drag-and-drop column/table insertion:

```tsx
// components/SchemaPanel.tsx

function SchemaPanel({ schema, onDragStart }: Props) {
  return (
    <div className="schema-panel">
      <SearchInput placeholder="Search tables, columns..." />

      {schema.tables.map(table => (
        <TableItem
          key={table.name}
          table={table}
          expandable
        >
          {table.columns.map(column => (
            <ColumnItem
              key={column.name}
              column={column}
              draggable
              onDragStart={() => onDragStart({ type: 'column', data: column })}
            >
              <ColumnIcon type={column.type} />
              <span>{column.name}</span>
              <TypeBadge>{column.type}</TypeBadge>
            </ColumnItem>
          ))}
        </TableItem>
      ))}

      <RelationshipsSection>
        {schema.relationships.map(rel => (
          <RelationshipDiagram
            from={rel.from_table}
            to={rel.to_table}
            condition={rel.condition}
          />
        ))}
      </RelationshipsSection>
    </div>
  )
}
```

**5. Add Step Modal**

Context-aware step picker:

```tsx
// components/AddStepModal.tsx

function AddStepModal({ position, availableSteps, onSelect }: Props) {
  const steps = [
    {
      type: 'where',
      label: 'Filter',
      description: 'Filter rows by condition',
      icon: <FilterIcon />,
      available: availableSteps.includes('where')
    },
    {
      type: 'join',
      label: 'Join',
      description: 'Join with another table',
      icon: <JoinIcon />,
      available: availableSteps.includes('join')
    },
    {
      type: 'group_by',
      label: 'Group & Aggregate',
      description: 'Group rows and compute aggregations',
      icon: <GroupIcon />,
      available: availableSteps.includes('group_by')
    },
    {
      type: 'select',
      label: 'Select Columns',
      description: 'Choose which columns to return',
      icon: <ColumnsIcon />,
      available: true
    },
    {
      type: 'order_by',
      label: 'Sort',
      description: 'Sort results',
      icon: <SortIcon />,
      available: true
    },
    {
      type: 'limit',
      label: 'Limit',
      description: 'Limit number of rows',
      icon: <LimitIcon />,
      available: true
    }
  ]

  return (
    <Modal>
      <h3>Add Pipeline Step</h3>
      <div className="step-grid">
        {steps.filter(s => s.available).map(step => (
          <StepCard
            key={step.type}
            onClick={() => onSelect(step.type)}
          >
            {step.icon}
            <h4>{step.label}</h4>
            <p>{step.description}</p>
          </StepCard>
        ))}
      </div>
    </Modal>
  )
}
```

#### Advanced Features

**1. Multi-Query Support (CTEs/Stash)**

```tsx
// Support for "stash as name" (CTEs)
function QueryWorkspace() {
  const [queries, setQueries] = useState<Map<string, Pipeline>>({
    main: { from: ..., transforms: [] }
  })

  return (
    <div className="workspace">
      <Tabs>
        {Array.from(queries.keys()).map(name => (
          <Tab key={name} label={name}>
            <PipelineCanvas
              pipeline={queries.get(name)}
              onChange={(p) => setQueries(new Map(queries).set(name, p))}
            />

            {name !== 'main' && (
              <Button onClick={() => stashQuery(name)}>
                Save as "{name}"
              </Button>
            )}
          </Tab>
        ))}

        <AddQueryButton onClick={createNewQuery} />
      </Tabs>
    </div>
  )
}
```

**2. Preview Data at Each Step**

```tsx
// Run query up to a specific transform to preview results
async function previewTransform(pipeline: Pipeline, transformId: string) {
  // Build partial query up to transformId
  const partialQuery = {
    from: pipeline.from,
    transforms: pipeline.transforms.slice(
      0,
      pipeline.transforms.findIndex(t => t.id === transformId) + 1
    )
  }

  // Compile and run
  const { sql } = await compileVisualQuery(partialQuery)
  const results = await executeSql(sql, { limit: 100 })

  return results
}

function TransformBlock({ transform, pipeline }: Props) {
  const [preview, setPreview] = useState(null)

  return (
    <BlockContainer>
      {/* Block config UI */}

      <Button onClick={() => previewTransform(pipeline, transform.id)}>
        Preview results
      </Button>

      {preview && (
        <DataTable
          columns={preview.columns}
          rows={preview.rows}
          maxRows={10}
        />
      )}
    </BlockContainer>
  )
}
```

**3. Undo/Redo System**

```tsx
import { useReducer } from 'react'

interface HistoryState {
  past: Pipeline[]
  present: Pipeline
  future: Pipeline[]
}

function usePipelineHistory(initialPipeline: Pipeline) {
  const [state, dispatch] = useReducer(historyReducer, {
    past: [],
    present: initialPipeline,
    future: []
  })

  const setPipeline = (newPipeline: Pipeline) => {
    dispatch({ type: 'SET', payload: newPipeline })
  }

  const undo = () => dispatch({ type: 'UNDO' })
  const redo = () => dispatch({ type: 'REDO' })

  return { pipeline: state.present, setPipeline, undo, redo, canUndo: state.past.length > 0, canRedo: state.future.length > 0 }
}
```

**4. Import from ASQL Text**

```tsx
function ImportButton() {
  const handleImport = async (asqlText: string) => {
    try {
      const jsonQuery = await parseAsqlToVisual(asqlText)
      setPipeline(jsonQuery)
      toast.success('Query imported successfully')
    } catch (error) {
      toast.error(`Parse error: ${error.message}`)
    }
  }

  return (
    <Dialog>
      <DialogTrigger>Import from ASQL</DialogTrigger>
      <DialogContent>
        <Textarea
          placeholder="Paste ASQL query here..."
          onChange={(e) => setAsqlText(e.target.value)}
        />
        <Button onClick={() => handleImport(asqlText)}>
          Import
        </Button>
      </DialogContent>
    </Dialog>
  )
}
```

#### Pros

**For Users:**
- ✅ **No syntax knowledge required**: Fully visual, no typing
- ✅ **Discoverable**: All options visible through dropdowns/menus
- ✅ **Guided**: Context-aware forms prevent invalid queries
- ✅ **Visualize structure**: See pipeline flow at a glance
- ✅ **Less error-prone**: Validation at every step
- ✅ **Mobile-friendly**: Touch-first UI works on tablets

**For Developers:**
- ✅ **Clear separation**: UI state is JSON, decoupled from AST
- ✅ **Testable**: JSON in/out makes integration tests trivial
- ✅ **Extensible**: New transform = new block component
- ✅ **Version-controlled JSON**: Queries can be stored in JSON format
- ✅ **API-first**: Backend can be used by other clients

#### Cons

**For Users:**
- ❌ **Slower for experts**: More clicks than typing for power users
- ❌ **Limited expressiveness**: May not support all ASQL features initially
- ❌ **Not copyable as text**: Queries are UI state, not plain text
- ❌ **Vertical space**: Long pipelines require scrolling
- ❌ **Learning curve**: Different mental model than SQL

**For Developers:**
- ❌ **Large upfront investment**: Requires building entire component library
- ❌ **JSON schema complexity**: Must mirror entire ASQL grammar
- ❌ **Sync burden**: JSON format must stay in sync with ASQL features
- ❌ **Complex state management**: Nested expressions, validation, etc.
- ❌ **Accessibility challenges**: Custom components harder to make accessible

#### Implementation Estimate

**Phase 1: Core JSON Schema (3-4 weeks)**
- Define JSON format
- Build AST ↔ JSON converters
- API endpoints for compile/parse/validate

**Phase 2: Basic Blocks (4-5 weeks)**
- FROM, WHERE, SELECT, LIMIT blocks
- Expression builder component
- Pipeline canvas with drag-and-drop

**Phase 3: Advanced Blocks (3-4 weeks)**
- JOIN block with visual join type selector
- GROUP BY with aggregations
- ORDER BY

**Phase 4: Polish (3-4 weeks)**
- Schema panel integration
- Preview data feature
- Undo/redo
- Import/export

**Total: 13-17 weeks** (3-4 months)

---

## Approach 3: Node-Based Visual Programming Interface

### Concept

Treat query building as visual programming using a node graph editor (like Unreal Blueprints, Blender's shader nodes, n8n workflows, or Houdini). Each operation (table, filter, join, aggregate) is a node with input/output ports. Users connect nodes via edges to build complex query graphs. This approach excels at visualizing complex queries with multiple CTEs, self-joins, and unions.

### Architecture

#### Frontend Stack
- **Graph Editor**: React Flow or Rete.js (mature node editor libraries)
- **Framework**: React
- **State**: React Flow has built-in state management
- **UI Components**: Radix UI for node configuration panels

#### Backend Requirements

**1. Graph-Based Query Representation**

Instead of a linear pipeline, represent queries as a directed acyclic graph (DAG):

```json
{
  "version": "1.0",
  "nodes": [
    {
      "id": "n1",
      "type": "table_source",
      "position": {"x": 100, "y": 100},
      "data": {
        "table": "orders",
        "alias": "o"
      },
      "outputs": [
        {"id": "out", "type": "dataset"}
      ]
    },
    {
      "id": "n2",
      "type": "table_source",
      "position": {"x": 100, "y": 300},
      "data": {
        "table": "customers",
        "alias": "c"
      },
      "outputs": [
        {"id": "out", "type": "dataset"}
      ]
    },
    {
      "id": "n3",
      "type": "join",
      "position": {"x": 400, "y": 200},
      "data": {
        "join_type": "inner",
        "condition": {
          "type": "binary_op",
          "operator": "=",
          "left": "o.customer_id",
          "right": "c.customer_id"
        }
      },
      "inputs": [
        {"id": "left", "type": "dataset"},
        {"id": "right", "type": "dataset"}
      ],
      "outputs": [
        {"id": "out", "type": "dataset"}
      ]
    },
    {
      "id": "n4",
      "type": "filter",
      "position": {"x": 700, "y": 200},
      "data": {
        "condition": {
          "type": "binary_op",
          "operator": "=",
          "left": "status",
          "right": "completed"
        }
      },
      "inputs": [
        {"id": "in", "type": "dataset"}
      ],
      "outputs": [
        {"id": "out", "type": "dataset"}
      ]
    },
    {
      "id": "n5",
      "type": "aggregate",
      "position": {"x": 1000, "y": 200},
      "data": {
        "group_by": ["region"],
        "aggregates": [
          {"function": "count", "column": "order_id", "alias": "order_count"},
          {"function": "sum", "column": "amount", "alias": "revenue"}
        ]
      },
      "inputs": [
        {"id": "in", "type": "dataset"}
      ],
      "outputs": [
        {"id": "out", "type": "dataset"}
      ]
    },
    {
      "id": "n6",
      "type": "output",
      "position": {"x": 1300, "y": 200},
      "data": {
        "order_by": [{"column": "revenue", "direction": "desc"}],
        "limit": 10
      },
      "inputs": [
        {"id": "in", "type": "dataset"}
      ]
    }
  ],
  "edges": [
    {"id": "e1", "source": "n1", "sourceHandle": "out", "target": "n3", "targetHandle": "left"},
    {"id": "e2", "source": "n2", "sourceHandle": "out", "target": "n3", "targetHandle": "right"},
    {"id": "e3", "source": "n3", "sourceHandle": "out", "target": "n4", "targetHandle": "in"},
    {"id": "e4", "source": "n4", "sourceHandle": "out", "target": "n5", "targetHandle": "in"},
    {"id": "e5", "source": "n5", "sourceHandle": "out", "target": "n6", "targetHandle": "in"}
  ]
}
```

**2. Graph → ASQL/SQL Compiler**

```python
# asql/graph_compiler.py

from typing import Dict, List, Set
from dataclasses import dataclass
import networkx as nx

@dataclass
class QueryNode:
    id: str
    type: str
    data: Dict
    inputs: List[str]
    outputs: List[str]

@dataclass
class QueryGraph:
    nodes: Dict[str, QueryNode]
    edges: List[Tuple[str, str]]  # (source_node_id, target_node_id)

    def to_asql(self) -> str:
        """Compile graph to ASQL text"""

        # Build dependency graph
        dag = nx.DiGraph()
        for node_id, node in self.nodes.items():
            dag.add_node(node_id, data=node)
        for source, target in self.edges:
            dag.add_edge(source, target)

        # Topological sort to determine execution order
        execution_order = list(nx.topological_sort(dag))

        # Find output node (sink with no outgoing edges)
        output_nodes = [n for n in dag.nodes() if dag.out_degree(n) == 0]
        if len(output_nodes) != 1:
            raise ValueError("Graph must have exactly one output node")

        output_node = output_nodes[0]

        # Trace back from output to build query
        return self._compile_from_node(output_node, dag)

    def _compile_from_node(self, node_id: str, dag: nx.DiGraph) -> str:
        """Recursively compile from a node back to sources"""
        node = self.nodes[node_id]

        if node.type == "table_source":
            return f"from {node.data['table']}"

        if node.type == "join":
            # Get input nodes
            left_input = self._get_input_node(node_id, "left", dag)
            right_input = self._get_input_node(node_id, "right", dag)

            # Compile inputs (may be CTEs)
            left_query = self._compile_from_node(left_input, dag)
            right_query = self._compile_from_node(right_input, dag)

            # If either input is complex, wrap in CTE
            if self._is_complex_query(left_input):
                left_query = self._wrap_in_cte(left_query, "left_table")
            if self._is_complex_query(right_input):
                right_query = self._wrap_in_cte(right_query, "right_table")

            # Build join syntax
            join_symbol = {
                "inner": "&",
                "left": "&?",
                "right": "?&",
                "full": "?&?",
                "cross": "*"
            }[node.data["join_type"]]

            condition = self._compile_condition(node.data["condition"])

            return f"{left_query}\n  {join_symbol} {right_query} on {condition}"

        if node.type == "filter":
            input_node = self._get_input_node(node_id, "in", dag)
            input_query = self._compile_from_node(input_node, dag)
            condition = self._compile_condition(node.data["condition"])
            return f"{input_query}\n  where {condition}"

        if node.type == "aggregate":
            input_node = self._get_input_node(node_id, "in", dag)
            input_query = self._compile_from_node(input_node, dag)

            group_by = ", ".join(node.data["group_by"])
            aggregates = []
            for agg in node.data["aggregates"]:
                func = agg["function"]
                col = agg["column"]
                alias = agg["alias"]
                aggregates.append(f"{func}({col}) as {alias}")

            agg_list = ",\n    ".join(aggregates)
            return f"{input_query}\n  group by {group_by} (\n    {agg_list}\n  )"

        if node.type == "output":
            input_node = self._get_input_node(node_id, "in", dag)
            query = self._compile_from_node(input_node, dag)

            if order_by := node.data.get("order_by"):
                order_clause = ", ".join(
                    f"{'-' if o['direction'] == 'desc' else ''}{o['column']}"
                    for o in order_by
                )
                query += f"\n  order by {order_clause}"

            if limit := node.data.get("limit"):
                query += f"\n  limit {limit}"

            return query

        raise ValueError(f"Unknown node type: {node.type}")
```

**3. ASQL → Graph Decompiler**

```python
def asql_to_graph(asql_text: str) -> QueryGraph:
    """Convert ASQL to graph representation"""

    # Parse to AST
    ast = compile_to_ast(asql_text)

    # Convert AST to graph nodes
    nodes = {}
    edges = []
    node_counter = 0

    def create_node(node_type: str, data: Dict) -> str:
        nonlocal node_counter
        node_id = f"n{node_counter}"
        node_counter += 1
        nodes[node_id] = QueryNode(
            id=node_id,
            type=node_type,
            data=data,
            inputs=[],
            outputs=[]
        )
        return node_id

    # Extract FROM as table source node
    from_table = ast.args["from"].this.name
    from_node = create_node("table_source", {"table": from_table})

    current_node = from_node

    # Walk through transforms and create nodes
    for transform in extract_transforms(ast):
        if transform["type"] == "where":
            filter_node = create_node("filter", {
                "condition": transform["condition"]
            })
            edges.append((current_node, filter_node))
            current_node = filter_node

        elif transform["type"] == "join":
            join_table = transform["table"]
            table_node = create_node("table_source", {"table": join_table})

            join_node = create_node("join", {
                "join_type": transform["join_type"],
                "condition": transform["condition"]
            })
            edges.append((current_node, join_node))
            edges.append((table_node, join_node))
            current_node = join_node

        # ... handle other transform types

    # Add output node
    output_node = create_node("output", {})
    edges.append((current_node, output_node))

    return QueryGraph(nodes=nodes, edges=edges)
```

**4. API Endpoints**

```python
@router.post("/graph/compile")
async def compile_graph(graph: Dict[str, Any], target_dialect: str = "postgres"):
    """Compile node graph to SQL"""
    try:
        query_graph = QueryGraph.from_dict(graph)
        asql = query_graph.to_asql()
        result = compile_query(asql, dialect=target_dialect)
        return {
            "sql": result.sql,
            "asql": asql,
            "success": True
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/graph/parse")
async def parse_asql_to_graph(asql_text: str):
    """Convert ASQL to graph representation"""
    try:
        graph = asql_to_graph(asql_text)
        return graph.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/graph/validate")
async def validate_graph(graph: Dict[str, Any]):
    """Validate graph structure"""
    errors = []

    # Check for cycles
    # Check for disconnected nodes
    # Check for multiple output nodes
    # Validate port connections (type compatibility)

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }
```

#### UI Components

**1. Node Graph Canvas**

```tsx
// components/NodeGraphCanvas.tsx

import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  NodeTypes,
  EdgeTypes
} from 'reactflow'
import 'reactflow/dist/style.css'

const nodeTypes: NodeTypes = {
  table_source: TableSourceNode,
  filter: FilterNode,
  join: JoinNode,
  aggregate: AggregateNode,
  output: OutputNode,
  union: UnionNode,
  cte: CTENode
}

function NodeGraphCanvas({ graph, onChange }: Props) {
  const [nodes, setNodes] = useState(graph.nodes)
  const [edges, setEdges] = useState(graph.edges)

  const onNodesChange = useCallback((changes) => {
    setNodes((nds) => applyNodeChanges(changes, nds))
  }, [])

  const onEdgesChange = useCallback((changes) => {
    setEdges((eds) => applyEdgeChanges(changes, eds))
  }, [])

  const onConnect = useCallback((connection) => {
    // Validate connection types
    if (isValidConnection(connection)) {
      setEdges((eds) => addEdge(connection, eds))
    }
  }, [])

  return (
    <div style={{ width: '100%', height: '100vh' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
        <NodePalette onAddNode={addNode} />
      </ReactFlow>
    </div>
  )
}
```

**2. Node Type Components**

```tsx
// components/nodes/TableSourceNode.tsx

function TableSourceNode({ data, isConnectable }: NodeProps) {
  const [table, setTable] = useState(data.table)

  return (
    <div className="node table-source-node">
      <div className="node-header">
        <TableIcon />
        <span>Table</span>
      </div>

      <div className="node-body">
        <TableSelector
          value={table}
          onChange={(t) => {
            setTable(t)
            data.onChange({ table: t })
          }}
        />
      </div>

      <Handle
        type="source"
        position={Position.Right}
        id="out"
        isConnectable={isConnectable}
        style={{ background: '#555' }}
      />
    </div>
  )
}

// components/nodes/JoinNode.tsx

function JoinNode({ data, isConnectable }: NodeProps) {
  const [joinType, setJoinType] = useState(data.join_type)
  const [condition, setCondition] = useState(data.condition)

  return (
    <div className="node join-node">
      <div className="node-header">
        <JoinIcon />
        <span>Join</span>
      </div>

      <div className="node-body">
        <JoinTypeSelector
          value={joinType}
          onChange={(type) => {
            setJoinType(type)
            data.onChange({ ...data, join_type: type })
          }}
          compact
        />

        <ExpressionBuilder
          expression={condition}
          onChange={(cond) => {
            setCondition(cond)
            data.onChange({ ...data, condition: cond })
          }}
          compact
        />
      </div>

      <Handle
        type="target"
        position={Position.Left}
        id="left"
        style={{ top: '30%' }}
        isConnectable={isConnectable}
      />
      <Handle
        type="target"
        position={Position.Left}
        id="right"
        style={{ top: '70%' }}
        isConnectable={isConnectable}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="out"
        isConnectable={isConnectable}
      />
    </div>
  )
}

// components/nodes/AggregateNode.tsx

function AggregateNode({ data, isConnectable }: NodeProps) {
  const [groupBy, setGroupBy] = useState(data.group_by || [])
  const [aggregates, setAggregates] = useState(data.aggregates || [])

  return (
    <div className="node aggregate-node">
      <div className="node-header">
        <GroupIcon />
        <span>Group & Aggregate</span>
      </div>

      <div className="node-body">
        <label>Group By:</label>
        <ColumnPicker
          columns={groupBy}
          onChange={setGroupBy}
        />

        <label>Aggregates:</label>
        {aggregates.map((agg, i) => (
          <AggregateInput
            key={i}
            aggregate={agg}
            onChange={(newAgg) => {
              const updated = [...aggregates]
              updated[i] = newAgg
              setAggregates(updated)
            }}
          />
        ))}

        <Button onClick={addAggregate} size="sm">
          + Add
        </Button>
      </div>

      <Handle
        type="target"
        position={Position.Left}
        id="in"
        isConnectable={isConnectable}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="out"
        isConnectable={isConnectable}
      />
    </div>
  )
}

// components/nodes/OutputNode.tsx

function OutputNode({ data, isConnectable }: NodeProps) {
  return (
    <div className="node output-node">
      <div className="node-header">
        <OutputIcon />
        <span>Query Output</span>
      </div>

      <div className="node-body">
        <OrderByInput
          orderBy={data.order_by}
          onChange={(o) => data.onChange({ ...data, order_by: o })}
        />

        <LimitInput
          limit={data.limit}
          onChange={(l) => data.onChange({ ...data, limit: l })}
        />
      </div>

      <Handle
        type="target"
        position={Position.Left}
        id="in"
        isConnectable={isConnectable}
      />
    </div>
  )
}
```

**3. Node Palette (Add Node Menu)**

```tsx
// components/NodePalette.tsx

function NodePalette({ onAddNode }: Props) {
  const nodeTemplates = [
    {
      type: 'table_source',
      label: 'Table',
      icon: <TableIcon />,
      description: 'Data source'
    },
    {
      type: 'filter',
      label: 'Filter',
      icon: <FilterIcon />,
      description: 'WHERE condition'
    },
    {
      type: 'join',
      label: 'Join',
      icon: <JoinIcon />,
      description: 'Join two datasets'
    },
    {
      type: 'aggregate',
      label: 'Aggregate',
      icon: <GroupIcon />,
      description: 'GROUP BY + aggregations'
    },
    {
      type: 'union',
      label: 'Union',
      icon: <UnionIcon />,
      description: 'Combine two datasets'
    },
    {
      type: 'output',
      label: 'Output',
      icon: <OutputIcon />,
      description: 'Final query result'
    }
  ]

  return (
    <div className="node-palette">
      <h3>Add Node</h3>
      <div className="palette-grid">
        {nodeTemplates.map(template => (
          <button
            key={template.type}
            className="palette-item"
            onClick={() => onAddNode(template.type)}
            title={template.description}
          >
            {template.icon}
            <span>{template.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
```

**4. Advanced Features**

**CTE/Stash Support:**
```tsx
// User can mark a node as "stash point"
function StashNode({ data }: NodeProps) {
  const [stashName, setStashName] = useState(data.name)

  return (
    <div className="node stash-node">
      <div className="node-header">
        <StashIcon />
        <input
          value={stashName}
          onChange={(e) => setStashName(e.target.value)}
          placeholder="CTE name"
        />
      </div>

      {/* Pass-through node that creates a CTE */}
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />

      {/* Additional output allows reusing this CTE elsewhere */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="reference"
        style={{ background: '#22c55e' }}
      />
    </div>
  )
}
```

**Subquery Support:**
```tsx
// Collapse a section of the graph into a subquery node
function SubqueryNode({ data }: NodeProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="node subquery-node">
      <div className="node-header">
        <SubqueryIcon />
        <span>Subquery</span>
        <button onClick={() => setExpanded(!expanded)}>
          {expanded ? <CollapseIcon /> : <ExpandIcon />}
        </button>
      </div>

      {expanded ? (
        <div className="subgraph-container">
          {/* Render nested graph */}
          <NodeGraphCanvas graph={data.subgraph} />
        </div>
      ) : (
        <div className="collapsed-info">
          {data.subgraph.nodes.length} nodes
        </div>
      )}

      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
    </div>
  )
}
```

**Column Flow Visualization:**
```tsx
// Show which columns are available at each node
function ColumnFlowOverlay({ graph }: Props) {
  const [hoveredNode, setHoveredNode] = useState(null)

  // Calculate available columns at hoveredNode
  const availableColumns = useMemo(() => {
    if (!hoveredNode) return []
    return computeAvailableColumns(graph, hoveredNode.id)
  }, [graph, hoveredNode])

  return (
    <div className="column-flow-overlay">
      {hoveredNode && (
        <div className="column-list">
          <h4>Available Columns:</h4>
          <ul>
            {availableColumns.map(col => (
              <li key={col.name}>
                {col.name}
                <TypeBadge>{col.type}</TypeBadge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
```

#### Pros

**For Users:**
- ✅ **Visualize complex queries**: See data flow and dependencies clearly
- ✅ **Excellent for CTEs**: Multiple branches and reuse are intuitive
- ✅ **Parallel operations**: Union, multiple joins are natural
- ✅ **Flexible layout**: Arrange nodes spatially for clarity
- ✅ **Incremental building**: Add nodes and connect progressively
- ✅ **Reusable subgraphs**: Save and reuse common patterns

**For Developers:**
- ✅ **Graph theory applies**: Leverage existing algorithms (toposort, cycle detection)
- ✅ **Mature libraries**: React Flow is battle-tested
- ✅ **Natural DAG representation**: Matches how databases execute queries
- ✅ **Extensible**: Easy to add new node types
- ✅ **Debugging**: Can visualize execution order

#### Cons

**For Users:**
- ❌ **Unfamiliar paradigm**: Most users haven't used node editors
- ❌ **Space-intensive**: Complex queries require large canvas
- ❌ **Not linear**: Doesn't match the linear ASQL/SQL mental model
- ❌ **Overwhelming**: Lots of UI elements on screen at once
- ❌ **Hard to print/share**: Graph layouts don't fit standard documents
- ❌ **Mobile-hostile**: Requires large screen and precise mouse/touch

**For Developers:**
- ❌ **Graph → ASQL is complex**: Not all graphs map cleanly to ASQL
- ❌ **Layout management**: Auto-layout algorithms are hard to get right
- ❌ **Performance**: Large graphs with many nodes can be slow
- ❌ **Learning curve**: React Flow has significant API surface
- ❌ **Validation complexity**: Type checking ports, cycle detection, etc.

#### Implementation Estimate

**Phase 1: Core Graph Engine (3-4 weeks)**
- React Flow integration
- Basic node types (table, filter, output)
- Graph → ASQL compiler
- ASQL → Graph decompiler

**Phase 2: Advanced Nodes (3-4 weeks)**
- Join node with multiple inputs
- Aggregate node
- Union node
- Subquery/CTE nodes

**Phase 3: UX Polish (2-3 weeks)**
- Auto-layout algorithms
- Node palette
- Column flow visualization
- Validation and error display

**Phase 4: Advanced Features (2-3 weeks)**
- Stash/CTE reuse
- Subgraph collapsing
- Schema integration
- Preview data at nodes

**Total: 10-14 weeks** (2.5-3.5 months)

---

## Comparison Matrix

| Aspect | Enhanced Text Editor | Pipeline Block UI | Node Graph UI |
|--------|---------------------|------------------|---------------|
| **Implementation Time** | 2-3 months | 3-4 months | 2.5-3.5 months |
| **Learning Curve** | Low | Medium | High |
| **Power User Efficiency** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Beginner Friendliness** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Complex Queries (CTEs)** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Mobile Support** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| **Query Sharing** | ⭐⭐⭐⭐⭐ (text) | ⭐⭐⭐ (JSON) | ⭐⭐ (JSON+layout) |
| **Discoverability** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Matches ASQL Paradigm** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Backend Complexity** | Low-Medium | Medium-High | Medium |
| **Extensibility** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Accessibility** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |

---

## Recommendation

### Primary Recommendation: **Approach 2 - Pipeline Block UI**

**Rationale:**

1. **Best Fit for ASQL's Design**: ASQL is explicitly pipeline-based. A block UI where each step is a card perfectly mirrors the language's mental model. Users building queries visually will develop the same intuition as ASQL syntax.

2. **Maximum Accessibility**: This approach serves the widest audience - from SQL novices to analysts who understand the concepts but struggle with syntax. It eliminates the barrier of memorizing operators like `&?` or `==`.

3. **Guided Experience**: Context-aware forms prevent invalid queries at every step. Users discover capabilities through dropdowns and menus rather than documentation.

4. **Schema-Driven Design**: The form generation system means adding new ASQL features automatically creates UI components. This keeps the visual editor in sync with language evolution.

5. **Mobile-Ready**: Touch-first design works on tablets, expanding ASQL to a broader device ecosystem.

6. **Strong Foundation**: The JSON schema layer provides a stable API for future features (query libraries, templates, collaboration, version control).

**Trade-offs Accepted:**

- **Slower for Power Users**: This is mitigated by providing text import/export. Expert users can draft in ASQL and switch to visual for refinement.
- **Larger Implementation**: The 3-4 month timeline is justified by the long-term maintainability and user adoption benefits.

### Secondary Recommendation: **Approach 1 - Enhanced Text Editor (Complement)**

**Build this AFTER the block UI as a power-user feature.**

**Rationale:**

1. **Dual-Mode Strategy**: Offer both visual and text modes, allowing users to pick their preferred workflow. Many modern tools (Figma, Notion) succeed by supporting multiple interaction paradigms.

2. **Incremental Value**: Once the JSON schema exists (from building the block UI), adding LSP autocomplete and widgets is lower-effort because the hard backend work is done.

3. **Power User Retention**: Some users will always prefer text. A great text editor experience prevents them from leaving for raw SQL editors.

4. **Learning Path**: Beginners start with blocks, graduate to enhanced text editor, eventually write raw ASQL. This creates a growth path.

**Implementation Path:**

1. **Phase 1 (Months 1-4)**: Build Pipeline Block UI + JSON schema layer
2. **Phase 2 (Months 5-6)**: Add "View as ASQL" text pane with syntax highlighting
3. **Phase 3 (Months 7-8)**: Build LSP server with autocomplete
4. **Phase 4 (Months 9-10)**: Add widget overlays and step insertion commands

### Why NOT Approach 3 (Node Graph)?

**Misaligned with ASQL Philosophy:**

ASQL's core value is **linearizing** complex SQL into readable pipelines. A node graph reintroduces the complexity that ASQL was designed to eliminate. While powerful for truly graph-like workflows (e.g., dbt DAGs, ETL pipelines), it's overkill for individual queries.

**Use Cases Where Node Graph Excels:**

- Multi-CTE queries with significant reuse (>5 CTEs)
- Union/intersect of many branches
- Visualizing query execution plans (optimization tool, not query builder)

**Recommendation**: Build node graph as a **specialized tool for advanced users**, not the primary interface. It could be a "power user mode" unlocked after mastering blocks and text.

---

## Implementation Roadmap

### Recommended Build Sequence

**Phase 1: MVP Block UI (Months 1-2)**
- JSON schema for FROM, WHERE, SELECT, LIMIT
- Basic block components
- Compile JSON → SQL
- Simple pipeline canvas

**Phase 2: Essential Features (Month 3)**
- JOIN block with visual join type picker
- GROUP BY with aggregations
- ORDER BY
- Import from ASQL text

**Phase 3: Polish & Schema (Month 4)**
- Schema panel with drag-and-drop
- Column autocomplete from schema
- Preview data at each step
- Error validation and helpful messages

**Phase 4: Enhanced Text Editor Foundation (Months 5-6)**
- LSP server with basic autocomplete
- Syntax highlighting
- Bidirectional sync with block UI

**Phase 5: Advanced Features (Months 7-8)**
- CTE/Stash support in block UI
- Window functions block
- Cohort analysis block
- Text editor widget overlays

**Phase 6: Node Graph (Optional, Months 9-10)**
- Build as separate "Advanced Mode"
- Focus on CTE visualization
- Target power users with complex queries

---

## Technical Architecture Summary

### Shared Backend Components

All three approaches benefit from these common backend services:

```
┌─────────────────────────────────────────────────────────┐
│                    ASQL Backend Core                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌────────────────┐    ┌────────────────┐            │
│  │  SQL Glot AST  │    │  JSON Schema   │            │
│  │   (existing)   │◄──►│   (new layer)  │            │
│  └────────────────┘    └────────────────┘            │
│           ▲                     ▲                      │
│           │                     │                      │
│  ┌────────┴──────────┬─────────┴──────────┐          │
│  │                   │                     │          │
│  │  ASQL Compiler    │  Schema Inference   │          │
│  │  (existing)       │  (existing)         │          │
│  │                   │                     │          │
│  └───────────────────┴─────────────────────┘          │
│                                                         │
│  ┌──────────────────────────────────────────┐         │
│  │          FastAPI Endpoints               │         │
│  │  • /compile (text → SQL)                 │         │
│  │  • /visual-editor/compile (JSON → SQL)   │         │
│  │  • /visual-editor/parse (ASQL → JSON)    │         │
│  │  • /lsp/* (LSP protocol endpoints)       │         │
│  │  • /graph/compile (graph → SQL)          │         │
│  └──────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────┘
```

### Frontend Architecture (Block UI Focus)

```
┌─────────────────────────────────────────────────────────┐
│                     React Frontend                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌────────────────────────────────────────┐            │
│  │        Pipeline Canvas (Zustand)       │            │
│  │  • FROM block                          │            │
│  │  • Transform blocks (drag & drop)      │            │
│  │  • Add step button                     │            │
│  └────────────────────────────────────────┘            │
│                    │                                    │
│         ┌──────────┼──────────┬────────────┐           │
│         │          │          │            │           │
│  ┌──────▼───┐ ┌───▼────┐ ┌──▼──────┐ ┌──▼──────┐     │
│  │  WHERE   │ │  JOIN  │ │ GROUP   │ │  ORDER  │     │
│  │  Block   │ │  Block │ │  Block  │ │  Block  │     │
│  └──────────┘ └────────┘ └─────────┘ └─────────┘     │
│                                                         │
│  ┌────────────────────────────────────────┐            │
│  │      Expression Builder (Shared)       │            │
│  │  • Binary operations                   │            │
│  │  • Column/literal/function pickers     │            │
│  │  • Nested expression support           │            │
│  └────────────────────────────────────────┘            │
│                                                         │
│  ┌────────────────────────────────────────┐            │
│  │         Schema Panel (Side)            │            │
│  │  • Table/column browser                │            │
│  │  • Relationship diagram                │            │
│  │  • Drag to insert                      │            │
│  └────────────────────────────────────────┘            │
│                                                         │
│  ┌────────────────────────────────────────┐            │
│  │      Results Preview (Bottom)          │            │
│  │  • Run query up to step                │            │
│  │  • Data table view                     │            │
│  │  • Export results                      │            │
│  └────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Conclusion

The **Pipeline Block UI (Approach 2)** is the optimal primary interface for visual ASQL because it:

1. **Mirrors ASQL's Pipeline Philosophy**: Direct conceptual mapping between visual blocks and ASQL syntax
2. **Maximizes Adoption**: Lowers barrier to entry for non-technical users while remaining powerful
3. **Provides Strong Foundation**: JSON schema enables future features (templates, collaboration, API integrations)
4. **Scales with Complexity**: Handles simple filters and complex multi-CTE queries equally well

The **Enhanced Text Editor (Approach 1)** should be built as a **complementary power-user feature** after the block UI is mature, enabling a dual-mode strategy that serves both beginners and experts.

The **Node Graph UI (Approach 3)** is **not recommended** as a primary interface due to misalignment with ASQL's linear pipeline paradigm, but could be a specialized tool for visualizing complex CTE dependencies.

**Recommended Tech Stack:**

- **Frontend**: React + React Hook Form + Radix UI + @dnd-kit + Zustand
- **Backend**: Extend existing FastAPI + SQLGlot + new JSON schema layer
- **Later**: LSP server with pygls for text editor mode

**Timeline**: MVP in 2 months, production-ready in 4 months, dual-mode in 6 months.
