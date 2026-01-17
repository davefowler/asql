# Column Tracking Integration Plan

## Overview

Add dynamic column tracking to visual editor using SQLGlot's schema awareness. This enables intelligent autocomplete showing only columns available at each pipeline step.

## How It Works

### 1. Track Columns Through Pipeline

For each step, compile ASQL up to that point and use SQLGlot to determine output columns:

```python
# Step 1: from users
asql = "from users"
columns = get_output_columns_for_step(asql, schema)
# → [{"name": "id", "type": "INT"}, {"name": "name", "type": "VARCHAR"}, ...]

# Step 2: from users | select id, name
asql = "from users\nselect id, name"
columns = get_output_columns_for_step(asql, schema)
# → [{"name": "id", "type": "INT"}, {"name": "name", "type": "VARCHAR"}]

# Step 3: from users | select id, name | extend full_name = name || ' ' || id
asql = "from users\nselect id, name\nextend full_name = name || ' ' || id"
columns = get_output_columns_for_step(asql, schema)
# → [{"name": "id", ...}, {"name": "name", ...}, {"name": "full_name", "type": "VARCHAR"}]
```

### 2. Update Parameter Definitions

Add `populate_function` to Parameter dataclass:

```python
@dataclass(frozen=True)
class Parameter:
    # ... existing fields ...

    # NEW: Dynamic population
    populate_function: Optional[str] = None  # Name of function in column_tracking.py
```

### 3. Update TRANSFORMS in dialect_schema.py

```python
SELECT = Transform(
    keywords=["SELECT", "PROJECT"],
    label="select",
    category="select",
    description="Choose which columns to return",
    parameters={
        "columns": Parameter(
            name="columns",
            type="list[column]",
            required=True,
            label="columns",
            widget="multi-select",
            description="Columns available at this point",

            # OLD WAY: Static query
            # populate_query="""
            #     from information_schema.columns
            #     where table_name = $table
            #     select column_name, data_type
            # """,

            # NEW WAY: Dynamic function
            populate_function="populate_select_columns",
            # This function receives:
            # - current_step_index
            # - all_steps (pipeline up to this point)
            # - schema
            # Returns: List of available columns
        ),
    },
)

WHERE = Transform(
    keywords=["WHERE", "FILTER", "IF"],
    label="where",
    category="filter",
    description="Filter rows by condition",
    parameters={
        "condition": Parameter(
            name="condition",
            type="expression",
            required=True,
            label="condition",
            widget="expression",
            description="Boolean expression",
            operators=["=", "!=", "<", ">", "<=", ">="],

            # Column suggestions for left side of expression
            populate_function="populate_where_columns",
        ),
    },
)

JOIN = Transform(
    keywords=["JOIN", ...],
    label="join",
    category="join",
    description="Join with another table",
    parameters={
        "table": Parameter(
            name="table",
            type="table",
            required=True,
            label="table",
            widget="dropdown",

            # List available tables from schema
            populate_function="populate_join_tables",
        ),
        "condition": Parameter(
            name="condition",
            type="expression",
            required=False,
            label="on",
            widget="expression",

            # Columns from joined table
            populate_function="populate_join_columns",
            populate_depends_on="table",  # Needs table parameter first
        ),
    },
)
```

### 4. Visual Editor Integration

Update visual-editor.js to call population functions:

```javascript
async function populateColumnDropdown(parameter, stepIndex) {
    // Get all pipeline steps up to this point
    const previousSteps = visualEditor.query.transforms.slice(0, stepIndex);

    // Call backend to get available columns
    const response = await fetch('/api/visual/populate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            populate_function: parameter.populate_function,
            step_index: stepIndex,
            steps: previousSteps,
            schema: visualEditor.schema  // If available
        })
    });

    const data = await response.json();
    return data.options;  // [{"name": "id", "type": "INT"}, ...]
}
```

### 5. API Endpoint

Add to playground/app.py:

```python
@app.post("/api/visual/populate")
async def populate_parameter_options(request: Request):
    """
    Dynamically populate parameter options based on pipeline state.

    Handles:
    - Column lists (based on previous steps)
    - Table lists (from schema)
    - Type-aware suggestions
    """
    data = await request.json()

    func_name = data.get('populate_function')
    step_index = data.get('step_index', 0)
    steps = data.get('steps', [])
    schema_dict = data.get('schema')

    # Convert schema dict to SQLGlot MappingSchema
    schema = None
    if schema_dict:
        schema = MappingSchema(schema_dict)

    # Call the appropriate population function
    from asql.column_tracking import (
        populate_select_columns,
        populate_where_columns,
        populate_join_tables,
        populate_join_columns
    )

    func_map = {
        'populate_select_columns': populate_select_columns,
        'populate_where_columns': populate_where_columns,
        'populate_join_tables': populate_join_tables,
        'populate_join_columns': populate_join_columns,
    }

    func = func_map.get(func_name)
    if not func:
        return {"success": False, "error": f"Unknown function: {func_name}"}

    try:
        options = func(step_index, steps, schema)
        return {"success": True, "options": options}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## Benefits

### ✅ Intelligent Autocomplete
- Only shows columns that actually exist at each step
- Shows types (INT, VARCHAR, etc.)
- Shows source table for joined columns

### ✅ Catches Errors Early
- Can't select column that doesn't exist
- Can't reference column that was excluded
- Knows about computed columns from EXTEND

### ✅ Self-Documenting
- User sees what's available without guessing
- Types help choose appropriate operators
- Table context helps understand joins

### ✅ Schema-Aware
- Reads from information_schema or schema config
- Updates automatically when schema changes
- Works with any SQL dialect

## Example User Flow

```text
Step 1: FROM users
  Available columns: id, name, email, created_at

Step 2: SELECT id, name
  Available columns: id, name
  (email and created_at are hidden - they were excluded!)

Step 3: EXTEND full_name = name
  Available columns: id, name, full_name
  (full_name appeared - it's a computed column!)

Step 4: WHERE full_name contains 'john'
  Column dropdown shows: id, name, full_name
  (only shows columns that exist at this step)

Step 5: JOIN orders ON user_id
  JOIN table dropdown: all tables from schema
  JOIN ON left side: id, name, full_name (from current query)
  JOIN ON right side: id, user_id, amount, status (from orders table)
```

## Implementation Strategy

### Phase 1: Basic Column Tracking
- Implement column_tracking.py ✅ DONE
- Add populate_function to Parameter dataclass
- Update SELECT and WHERE in dialect_schema.py

### Phase 2: API Integration
- Add /api/visual/populate endpoint
- Update visual-editor.js to call endpoint
- Test with simple queries

### Phase 3: Advanced Features
- Handle JOINs (columns from multiple tables)
- Handle EXTEND (computed columns)
- Handle RENAME (column name changes)
- Handle EXCEPT (column exclusions)

### Phase 4: Schema Integration
- Load schema from database connection
- Support information_schema queries
- Support dbt manifest.json
- Cache schema for performance

## Alternative: Client-Side Tracking

Could also track columns entirely in JavaScript:

```javascript
class ColumnTracker {
    constructor(schema) {
        this.schema = schema;
    }

    getColumnsAfterStep(steps, stepIndex) {
        let columns = [];

        for (let i = 0; i <= stepIndex; i++) {
            const step = steps[i];

            if (step.type === 'from') {
                columns = this.schema[step.table];
            } else if (step.type === 'select') {
                columns = step.columns.map(c =>
                    columns.find(col => col.name === c)
                );
            } else if (step.type === 'extend') {
                columns.push({
                    name: step.column_name,
                    type: 'COMPUTED'
                });
            }
            // ... handle other step types
        }

        return columns;
    }
}
```

Pros:
- Faster (no backend round trip)
- Works offline
- Simpler architecture

Cons:
- Have to reimplement ASQL semantics in JS
- Might diverge from actual parser behavior
- Complex steps (JOINs, CTEs) harder to handle

**Recommendation**: Start with backend approach (uses real ASQL compiler), add client-side caching later for performance.
