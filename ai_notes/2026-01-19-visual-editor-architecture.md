# Visual ASQL Editor - Comprehensive Architecture Plan

## Part 1: Pipeline Steps and Their Input Types

### FROM (Pipeline Root)
- **table**: TableSelect (dropdown from schema, with autocomplete)

### Transforms (Pipeline Steps)

#### Filter Category
- **where** (Filter)
  - `condition`: Expression (with comparison operators)

- **having** (Having)
  - `condition`: Expression (same as where, but post-aggregation)

- **qualify** (Qualify)
  - `condition`: Expression (same as where, but post-window)

#### Select Category  
- **select** (Select)
  - `columns`: SortableList of Expression (with optional alias)

- **except** (Except)
  - `columns`: SortableList of column names to exclude

#### Aggregate Category
- **group_by** (Group)
  - `dimensions`: SortableList of Expression
  - `aggregates`: SortableList of Expression (with aggregate functions)

#### Sort Category
- **order_by** (Sort)
  - `expressions`: SortableList of Expression + Direction

#### Join Category
- **join** (Join)
  - `join_type`: EnumSelect (inner, left, right, full, cross)
  - `table`: TableSelect
  - `condition`: Expression (ON clause)

#### Transform Category
- **extend** (Extend - Add Computed Columns)
  - `columns`: SortableList of Expression (alias auto-generated)

- **replace** (Replace - Modify Existing Columns)
  - `mappings`: SortableList of (column WITH expression)

- **rename** (Rename)
  - `mappings`: SortableList of (old_name → new_name)

- **explode** (Explode Array)
  - `column`: ColumnSelect

#### Window Category
- **per** (Window Partition)
  - `columns`: SortableList of column names

- **number** (Row Number) - no parameters
- **rank** (Rank) - no parameters  
- **dense** (Dense Rank) - no parameters

#### Utility Category
- **limit** (Limit)
  - `count`: NumberInput

- **offset** (Offset)
  - `count`: NumberInput

- **sample** (Sample)
  - `size`: NumberInput

- **distinct** (Distinct) - no parameters

- **deduplicate** (Deduplicate)
  - `columns`: SortableList of column names (optional)

- **stash** (Stash as CTE)
  - `name`: IdentifierInput

#### Analytics Category
- **cohort** (Cohort Analysis)
  - `entity`: ColumnSelect
  - `cohort_date`: Expression
  - `event_date`: Expression

- **spine** (Gap-Filling Spine)
  - `columns`: SortableList of Expression
  - `aggregations`: SortableList of Expression

#### Advanced Category
- **recurse** (Recursive CTE)
  - `max_depth`: NumberInput (optional)

---

## Part 2: Core Expression System (Recursive Wrapper Pattern)

The heart of the visual editor is a **recursive expression builder** using progressive disclosure.

### Expression Types

Every expression is one of:
```javascript
// Leaf nodes
{ type: 'column', name: 'amount' }
{ type: 'literal', value: 10, dataType: 'number' }
{ type: 'literal', value: 'active', dataType: 'string' }

// Wrapper nodes (contain other expressions)
{ type: 'function', name: 'min', args: [Expression] }
{ type: 'function', name: 'month', args: [Expression] }
{ type: 'binary', op: '+', left: Expression, right: Expression }
{ type: 'binary', op: '=', left: Expression, right: Expression }
{ type: 'unary', op: 'NOT', arg: Expression }
```

### Interaction: Hover → Bracket → Expand

**Normal state:**
```
amount
```

**Hover for 1 second → shows expansion brackets:**
```
┌─ amount ─ + ─┐
└──────────────┘
```

**Click + → dropdown menu:**
```
┌─ amount ─ + ─┐
└──────┬───────┘
       │
┌──────▼──────────────┐
│ 📦 Wrap in function │
│    min, max, sum    │
│    month, year      │
│ ➕ Add operation    │
│    + - * / ||       │
│ 🔄 Compare to       │
│    = != > < >= <=   │
│ 📝 Add value        │
│    number, text     │
└─────────────────────┘
```

**Select "wrap in min()":**
```
┌─ min( ┌─ amount ─ + ─┐ ) ─ + ─┐
│       └──────────────┘        │
└───────────────────────────────┘
```

### Building Complex Expressions

Example: Building `min(amount - 10) + 20`

```
Step 1: Start with column
[ amount ]

Step 2: Hover 1s, click +, select "- number", type 10
[ amount - 10 ]

Step 3: Hover 1s on whole thing, click +, select "wrap in min()"
[ min( amount - 10 ) ]

Step 4: Hover 1s, click +, select "+ number", type 20
[ min( amount - 10 ) + 20 ]
```

### Hover Actions

When hovering for 1 second on ANY expression part:
```
┌─ [expression] ─ × ─ + ─┐
└────────────────────────┘
     │           │   │
     │           │   └─ Expand menu
     │           └───── Delete this part
     └───────────────── The expression content
```

### The Expand Menu

```
┌─────────────────────────────┐
│ 📦 Wrap in function...      │
│   ├─ Aggregate: min, max,   │
│   │   sum, avg, count       │
│   ├─ Date: month, year,     │
│   │   day, week             │
│   ├─ String: upper, lower,  │
│   │   trim, length          │
│   └─ Math: abs, round,      │
│       floor, ceil           │
├─────────────────────────────┤
│ ➕ Add operation            │
│   ├─ + (add)                │
│   ├─ - (subtract)           │
│   ├─ * (multiply)           │
│   ├─ / (divide)             │
│   └─ || (concat)            │
├─────────────────────────────┤
│ 🔄 Compare to...            │
│   ├─ = (equals)             │
│   ├─ != (not equals)        │
│   ├─ > < >= <=              │
│   ├─ contains, starts with  │
│   └─ is null, is not null   │
├─────────────────────────────┤
│ 📝 Add value                │
│   ├─ Number                 │
│   ├─ Text                   │
│   └─ Date/Time              │
└─────────────────────────────┘
```

### Expression with Alias

Alias is shown on hover (existing pattern), works at any level:
```
Normal:     min(amount - 10) + 20

Hover:      min(amount - 10) + 20  as ___
                                   └─ click to add alias
```

### Nested Hover Targets

For complex expressions, hovering targets are hierarchical:
```
Expression: min(amount - 10) + 20

Hover targets (from inner to outer):
1. "amount"           → can wrap/operate on amount
2. "10"               → can change the literal
3. "amount - 10"      → can wrap/operate on subtraction
4. "min(amount - 10)" → can wrap/operate on min result
5. whole expression   → can wrap/operate on everything
```

### Visual Nesting (Collapsed vs Expanded)

For deeply nested expressions, show collapsed by default:
```
Collapsed:  min(amount - 10) + 20

Expanded:   ┌─ min( ┌─ amount - 10 ─┐ ) + 20 ─┐
            │       └───────────────┘          │
            └──────────────────────────────────┘
```

Toggle between views with a collapse/expand button.

---

## Part 3: Widget/Component Inventory (Simplified)

### Primitive Widgets
1. **TextInput** - Plain text entry
2. **NumberInput** - Numeric entry with min/max/step
3. **IdentifierInput** - SQL identifier

### Selection Widgets
4. **TableSelect** - Dropdown of available tables
5. **ColumnSelect** - Dropdown/autocomplete of available columns
6. **EnumSelect** - Generic dropdown from options list

### Core Expression Widget
7. **Expression** - The recursive expression builder
   - Renders based on expression type (column, literal, function, binary)
   - Hover → bracket → expand interaction
   - Handles alias (hover to show "as")
   - Config options:
     - `showAlias`: boolean (false for GROUP BY dimensions)
     - `functionCategories`: which functions to show in menu

### Container Widgets
8. **SortableList** - Drag-to-reorder list of any item type
   - Drag handle (⋮⋮)
   - Item content (any widget)
   - Remove button (×)
   - Add button at bottom

9. **PipelineEditor** - SortableList of transform blocks
   - FROM block (not removable)
   - Transform blocks (sortable, removable)
   - Add step dropdown

### Specialized Mappings
10. **ReplaceMapping** - `column WITH expression`
11. **RenameMapping** - `old_name → new_name`
12. **OrderItem** - `expression + direction toggle`

---

## Part 4: Metadata Gap Analysis

### Current Metadata Has:
- ✅ Transform list with parameters
- ✅ Parameter types and widgets
- ✅ Function list by category (date, string, math, window, etc.)
- ✅ Aggregate list with types
- ✅ Operator list by category (comparison, string, null, list, logical)
- ✅ Join types with symbols
- ✅ Time units
- ✅ Data types

### Missing from Metadata:

#### 1. Expression Widget Config
Current: `"widget": "list"` - doesn't specify expression behavior
Need: Config for the Expression widget

**Proposed Enhancement:**
```json
{
  "name": "columns",
  "type": "expression[]",
  "widget": {
    "type": "sortable_list",
    "item": {
      "type": "expression",
      "showAlias": true,
      "functionCategories": ["date", "string", "math", "aggregates"]
    }
  }
}
```

#### 2. Expression Menu Categories
Need: Define which functions/operators appear in the expand menu

**Proposed:**
```json
"expression_menu": {
  "wrap_functions": {
    "aggregates": ["min", "max", "sum", "avg", "count"],
    "date": ["month", "year", "day", "week", "quarter"],
    "string": ["upper", "lower", "trim", "length"],
    "math": ["abs", "round", "floor", "ceil"]
  },
  "operators": {
    "arithmetic": ["+", "-", "*", "/"],
    "comparison": ["=", "!=", ">", "<", ">=", "<="],
    "string": ["contains", "starts with", "ends with"],
    "null": ["is null", "is not null"],
    "logical": ["and", "or", "not"]
  },
  "literals": ["number", "string", "date"]
}
```

#### 3. Column Type Filtering
Current: Functions have `args` types but UI doesn't filter
Need: Smart filtering based on column type

**Current:**
```json
"month": { "args": ["date"], "returns": "integer" }
"sum": { "types": ["number", "integer", "float"] }
```

**UI Behavior:**
- When column type is known, filter function list
- Date column → show date functions prominently
- String column → hide numeric aggregates
- Unknown type → show all

#### 4. Sortable List Config
Need: Metadata for sortable behavior

**Proposed:**
```json
{
  "name": "columns",
  "widget": {
    "type": "sortable_list",
    "sortable": true,
    "addLabel": "+ Add Column",
    "minItems": 1,
    "maxItems": null
  }
}
```

#### 5. Transform-Specific Expression Configs
Different transforms need different expression configs:

| Transform | showAlias | functionCategories | operators |
|-----------|-----------|-------------------|-----------|
| SELECT | true | date, string, math, aggregates | all |
| GROUP BY dims | false | date, string, math | none |
| GROUP BY aggs | true | aggregates only | arithmetic |
| WHERE | false | date, string, math | comparison, logical |
| ORDER BY | false | date, string, math | none |
| EXTEND | true | all | all |

---

## Part 5: Implementation Approach Recommendation

### Option Analysis

#### A. Continue with Vanilla JS (Current)
**Pros:**
- No dependencies
- Already working
- Simple deployment

**Cons:**
- Growing complexity
- Manual DOM management
- Event handling scattered

#### B. Add SortableJS (One Small Dependency)
**Pros:**
- Battle-tested drag-and-drop
- Touch support
- ~10KB gzipped
- No build step needed (CDN)

**Cons:**
- External dependency

### Recommendation: **Organized Vanilla JS + SortableJS**

Given:
- Current code is vanilla JS and working
- Playground is a demo, not production app
- Simplicity is valued
- No build step preferred
- Drag-and-drop is essential for good UX

**Strategy: Refactor into component pattern, add SortableJS for drag-and-drop.**

---

## Part 6: Proposed Code Organization

### Current Structure (Flat)
```
visual-editor.js          # Everything in one file (~1900 lines)
visual-editor.css         # All styles
```

### Proposed Structure (Modular)
```
playground/static/
├── visual-editor/
│   ├── index.js              # Main entry, VisualEditor class
│   ├── components/
│   │   ├── base.js           # BaseComponent class
│   │   ├── primitives/
│   │   │   ├── text-input.js
│   │   │   ├── number-input.js
│   │   │   └── enum-select.js
│   │   ├── selectors/
│   │   │   ├── table-select.js
│   │   │   └── column-select.js
│   │   ├── expression/
│   │   │   ├── expression.js      # THE core recursive component
│   │   │   ├── expand-menu.js     # The hover → expand dropdown
│   │   │   └── alias-input.js     # The "as ___" hover input
│   │   ├── containers/
│   │   │   ├── sortable-list.js   # Wraps SortableJS
│   │   │   └── pipeline.js        # Transform block list
│   │   └── blocks/
│   │       ├── transform-block.js # Generic transform wrapper
│   │       └── from-block.js      # FROM block
│   ├── services/
│   │   ├── schema-service.js      # Fetch tables/columns
│   │   └── metadata-service.js    # Load UI metadata
│   └── styles/
│       ├── base.css
│       ├── expression.css         # Expression + expand menu styles
│       ├── sortable.css           # Drag handles, drop zones
│       └── blocks.css
```

### The Expression Component (Core)

```javascript
// components/expression/expression.js
class Expression extends BaseComponent {
  constructor(options) {
    super(options);
    this.hoverTimeout = null;
    this.isExpanded = false;
  }
  
  render() {
    const { value, showAlias } = this.options;
    const container = document.createElement('div');
    container.className = 'expression';
    
    // Render based on expression type
    if (value.type === 'column') {
      container.innerHTML = this.renderColumn(value);
    } else if (value.type === 'literal') {
      container.innerHTML = this.renderLiteral(value);
    } else if (value.type === 'function') {
      container.innerHTML = this.renderFunction(value);
    } else if (value.type === 'binary') {
      container.innerHTML = this.renderBinary(value);
    }
    
    // Alias (shown on hover)
    if (showAlias) {
      this.aliasEl = this.renderAliasToggle(value.alias);
      container.appendChild(this.aliasEl);
    }
    
    return container;
  }
  
  renderColumn(value) {
    return `<span class="expr-column">${value.name}</span>`;
  }
  
  renderLiteral(value) {
    const cls = `expr-literal expr-${value.dataType}`;
    return `<span class="${cls}">${value.value}</span>`;
  }
  
  renderFunction(value) {
    // Recursively render args
    const argsHtml = value.args.map(arg => 
      new Expression({ value: arg, showAlias: false }).render().outerHTML
    ).join(', ');
    
    return `
      <span class="expr-func">
        <span class="expr-func-name">${value.name}</span>
        <span class="expr-paren">(</span>
        <span class="expr-args">${argsHtml}</span>
        <span class="expr-paren">)</span>
      </span>
    `;
  }
  
  renderBinary(value) {
    const leftHtml = new Expression({ value: value.left, showAlias: false }).render().outerHTML;
    const rightHtml = new Expression({ value: value.right, showAlias: false }).render().outerHTML;
    
    return `
      <span class="expr-binary">
        ${leftHtml}
        <span class="expr-op">${value.op}</span>
        ${rightHtml}
      </span>
    `;
  }
  
  afterMount() {
    // Hover for 1s → show expand brackets
    this.on(this.element, 'mouseenter', () => {
      this.hoverTimeout = setTimeout(() => this.showExpandBrackets(), 1000);
    });
    
    this.on(this.element, 'mouseleave', () => {
      clearTimeout(this.hoverTimeout);
      if (!this.isMenuOpen) {
        this.hideExpandBrackets();
      }
    });
  }
  
  showExpandBrackets() {
    this.element.classList.add('expr-expandable');
    // Add × and + buttons
  }
  
  hideExpandBrackets() {
    this.element.classList.remove('expr-expandable');
  }
  
  showExpandMenu(event) {
    const menu = new ExpandMenu({
      position: { x: event.clientX, y: event.clientY },
      onSelect: (action) => this.handleMenuAction(action)
    });
    menu.show();
    this.isMenuOpen = true;
  }
  
  handleMenuAction(action) {
    // action: { type: 'wrap', func: 'min' }
    // action: { type: 'binary', op: '+' }
    // action: { type: 'compare', op: '=' }
    
    const currentValue = this.options.value;
    let newValue;
    
    if (action.type === 'wrap') {
      newValue = {
        type: 'function',
        name: action.func,
        args: [currentValue]
      };
    } else if (action.type === 'binary') {
      newValue = {
        type: 'binary',
        op: action.op,
        left: currentValue,
        right: { type: 'literal', value: '', dataType: 'number' }
      };
    }
    
    this.emit('expression-change', newValue);
  }
}
```

### SortableList Component

```javascript
// components/containers/sortable-list.js
class SortableList extends BaseComponent {
  render() {
    const { items, itemRenderer, addLabel } = this.options;
    
    const container = document.createElement('div');
    container.className = 'sortable-list';
    
    const list = document.createElement('div');
    list.className = 'sortable-list-items';
    
    items.forEach((item, index) => {
      const itemEl = document.createElement('div');
      itemEl.className = 'sortable-item';
      itemEl.dataset.index = index;
      
      // Drag handle
      itemEl.innerHTML = `
        <span class="drag-handle">⋮⋮</span>
        <div class="item-content"></div>
        <button class="remove-btn">×</button>
      `;
      
      // Render item content
      const content = itemEl.querySelector('.item-content');
      itemRenderer(item, index).mount(content);
      
      list.appendChild(itemEl);
    });
    
    container.appendChild(list);
    
    // Add button
    const addBtn = document.createElement('button');
    addBtn.className = 'add-item-btn';
    addBtn.textContent = addLabel || '+ Add';
    container.appendChild(addBtn);
    
    return container;
  }
  
  afterMount() {
    const list = this.element.querySelector('.sortable-list-items');
    
    // Initialize SortableJS
    this.sortable = new Sortable(list, {
      handle: '.drag-handle',
      animation: 150,
      onEnd: (evt) => {
        this.emit('reorder', {
          oldIndex: evt.oldIndex,
          newIndex: evt.newIndex
        });
      }
    });
    
    // Add button
    this.on(this.element.querySelector('.add-item-btn'), 'click', () => {
      this.emit('add-item');
    });
    
    // Remove buttons
    this.element.querySelectorAll('.remove-btn').forEach((btn, index) => {
      this.on(btn, 'click', () => this.emit('remove-item', { index }));
    });
  }
}
```

---

## Part 7: Migration Plan

### Phase 1: Expression Component (Core)
1. Build the recursive Expression component
2. Build ExpandMenu (the hover dropdown)
3. Build hover → bracket → expand interaction
4. Test with simple expressions

### Phase 2: SortableList
1. Add SortableJS via CDN
2. Build SortableList wrapper component
3. Add drag handles and reorder events
4. Test with column lists

### Phase 3: Transform Blocks
1. Refactor transform rendering to use Expression
2. Wire up SortableList for all list parameters
3. Make pipeline itself sortable

### Phase 4: Metadata-Driven Rendering
1. Update metadata with expression configs
2. Build schema-driven transform renderer
3. Remove hardcoded transform rendering

### Phase 5: Polish
1. CSS for expand brackets and menus
2. Keyboard accessibility
3. Touch support testing
4. Performance optimization

---

## Summary

The visual editor architecture centers on:

1. **Expression Component** - Recursive, self-rendering expression builder
   - Hover 1s → show expand brackets
   - Click + → expand menu
   - Wrap in function, add operator, compare, etc.
   - Works at any nesting level

2. **SortableList** - Drag-to-reorder container
   - Works for columns, transforms, conditions
   - Uses SortableJS (small, battle-tested)

3. **Minimal Widget Set**
   - Primitives: TextInput, NumberInput, EnumSelect
   - Selectors: TableSelect, ColumnSelect
   - Core: Expression (recursive)
   - Containers: SortableList, Pipeline

4. **Metadata-Driven** - Expression configs per transform
   - showAlias, functionCategories, operators
   - Enables declarative transform definitions

---

## Appendix: Expression Type Coverage

### Fully Supported
- Columns, Literals (number, string, boolean, date)
- Functions (any with args)
- Binary operators (+, -, *, /, =, !=, >, <, >=, <=, AND, OR)
- Unary operators (NOT, negative)

### Phase 2 Additions
- IS NULL / IS NOT NULL (postfix operators)
- BETWEEN (ternary: value, low, high)
- IN (list) (value + list of expressions)
- CASE/WHEN (branches + else)
- Type casts

### Phase 3 Additions
- Aggregate modifiers (DISTINCT, FILTER, ORDER BY)
- Window OVER clauses (complex, may use text fallback)

### Intentionally NOT Supported: Subqueries

ASQL's pipeline model **replaces subqueries entirely**. This is a feature, not a limitation.

Instead of:
```sql
SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE amount > 100)
```

Use pipeline composition:
```asql
from orders
  where amount > 100
  select user_id
  stash high_value_buyers

from users
  where id in high_value_buyers
```

**Benefits:**
- More readable (each step is explicit)
- Easier to debug (can inspect intermediate results)
- Natural fit for visual editor (just pipeline blocks)
- No nested query builders needed

**Behavior by mode:**

| Mode | Subqueries | Notes |
|------|-----------|-------|
| **Visual ASQL** | Always converted | Required - no subquery UI exists |
| **Text ASQL** | Optionally converted | `normalize_subqueries=True` setting |

**Implementation:** See GitHub issue #165.
