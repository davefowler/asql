# Visual Editor Prototype - Implementation Plan

## Goal

Build a **minimal working prototype** of the Pipeline Block UI that can replace CodeMirror in the playground, allowing users to toggle between text and visual editing modes.

## Scope (MVP/Prototype)

### ✅ In Scope
- **Mode toggle**: Button to switch between Text ↔ Visual modes
- **Core transforms**: FROM, WHERE, SELECT, JOIN, GROUP BY, ORDER BY, LIMIT
- **Basic blocks**: Visual cards for each transform type
- **Bidirectional sync**: Convert ASQL text → JSON → Visual blocks (and reverse)
- **Simple expressions**: Column references, literals, basic operators (=, !=, <, >)
- **Add/remove blocks**: UI to add new pipeline steps
- **Auto-generate from SQLGlot**: Use `arg_types` where possible

### ❌ Out of Scope (Future Work)
- Complex expressions (nested AND/OR, functions)
- All 34+ ASQL transforms (only core 7)
- Drag-and-drop reordering
- Schema integration (table/column dropdowns)
- Data preview
- CTE/Stash support
- Undo/redo
- React migration

## Architecture

### Backend Changes

**New Files**:
1. `/asql/json_schema.py` - JSON representation and converters
2. `/asql/ui_schema.py` - UI metadata for transforms (thin layer on SQLGlot)

**Modified Files**:
1. `/playground/app.py` - Add API endpoints

**New API Endpoints**:
```
POST /api/visual/parse       - ASQL text → JSON
POST /api/visual/compile     - JSON → ASQL text
GET  /api/visual/operations  - List available operations
```

### Frontend Changes

**New Files**:
1. `/playground/static/visual-editor.js` - Visual editor logic
2. `/playground/static/visual-editor.css` - Visual editor styles

**Modified Files**:
1. `/playground/templates/index.html` - Add mode toggle, visual editor container
2. `/playground/static/playground.js` - Add mode switching logic

### Tech Stack (Prototype)

- **Frontend**: Vanilla JS/HTML/CSS (match existing playground)
- **Backend**: Python + FastAPI (existing)
- **No build system**: Keep it simple like current playground

## Detailed Implementation Steps

### Phase 1: Backend - JSON Schema & Converters (3-4 hours)

#### 1.1 Create JSON Schema

```python
# /asql/json_schema.py

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Literal
from sqlglot import exp

@dataclass
class Expression:
    """Base expression in JSON format"""
    type: str  # 'column', 'literal', 'binary_op', 'function'

@dataclass
class ColumnRef(Expression):
    type: Literal['column'] = 'column'
    name: str = ''

@dataclass
class Literal(Expression):
    type: Literal['literal'] = 'literal'
    value: Any = None
    data_type: str = 'string'  # 'string', 'number', 'boolean'

@dataclass
class BinaryOp(Expression):
    type: Literal['binary_op'] = 'binary_op'
    operator: str = '='
    left: Optional[Expression] = None
    right: Optional[Expression] = None

@dataclass
class Transform:
    """Base pipeline transform"""
    id: str
    type: str  # 'where', 'join', 'select', etc.

@dataclass
class FromClause:
    table: str
    alias: Optional[str] = None

@dataclass
class WhereTransform(Transform):
    type: Literal['where'] = 'where'
    condition: Optional[Expression] = None

@dataclass
class SelectTransform(Transform):
    type: Literal['select'] = 'select'
    columns: List[str] = None  # Simplified: just column names

@dataclass
class JoinTransform(Transform):
    type: Literal['join'] = 'join'
    join_type: str = 'inner'  # 'inner', 'left', 'right', 'full'
    table: str = ''
    condition: Optional[Expression] = None

@dataclass
class GroupByTransform(Transform):
    type: Literal['group_by'] = 'group_by'
    dimensions: List[str] = None
    aggregates: List[Dict] = None  # {function, column, alias}

@dataclass
class OrderByTransform(Transform):
    type: Literal['order_by'] = 'order_by'
    expressions: List[Dict] = None  # {column, direction}

@dataclass
class LimitTransform(Transform):
    type: Literal['limit'] = 'limit'
    count: int = 10

@dataclass
class Query:
    """Complete ASQL query in JSON format"""
    from_clause: FromClause
    transforms: List[Transform]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'from': asdict(self.from_clause),
            'transforms': [asdict(t) for t in self.transforms]
        }
```

#### 1.2 Create AST → JSON Converter

```python
# /asql/json_schema.py (continued)

def ast_to_json(ast: exp.Select) -> Dict[str, Any]:
    """Convert SQLGlot AST to JSON representation"""

    query = Query(from_clause=None, transforms=[])

    # Extract FROM
    if from_clause := ast.args.get('from'):
        table_name = from_clause.this.name if from_clause.this else ''
        query.from_clause = FromClause(table=table_name)

    # Extract WHERE
    if where := ast.args.get('where'):
        transform_id = f"t{len(query.transforms)}"
        condition_json = expression_to_json(where.this)
        query.transforms.append(WhereTransform(
            id=transform_id,
            condition=condition_json
        ))

    # Extract JOINs
    if joins := ast.args.get('joins'):
        for join in joins:
            transform_id = f"t{len(query.transforms)}"
            join_kind = join.args.get('kind', 'INNER').lower()
            table_name = join.this.name if join.this else ''
            condition_json = expression_to_json(join.args.get('on')) if join.args.get('on') else None
            query.transforms.append(JoinTransform(
                id=transform_id,
                join_type=join_kind,
                table=table_name,
                condition=condition_json
            ))

    # Extract SELECT (if not SELECT *)
    if selections := ast.args.get('expressions'):
        if not (len(selections) == 1 and isinstance(selections[0], exp.Star)):
            transform_id = f"t{len(query.transforms)}"
            columns = [sel.alias_or_name for sel in selections]
            query.transforms.append(SelectTransform(
                id=transform_id,
                columns=columns
            ))

    # Extract GROUP BY
    if group_by := ast.args.get('group'):
        transform_id = f"t{len(query.transforms)}"
        dimensions = [expr.name for expr in group_by.expressions]
        # TODO: Extract aggregates from SELECT when in GROUP BY context
        query.transforms.append(GroupByTransform(
            id=transform_id,
            dimensions=dimensions,
            aggregates=[]
        ))

    # Extract ORDER BY
    if order_by := ast.args.get('order'):
        transform_id = f"t{len(query.transforms)}"
        expressions = []
        for ordered in order_by.expressions:
            expressions.append({
                'column': ordered.this.name if hasattr(ordered.this, 'name') else str(ordered.this),
                'direction': 'desc' if ordered.args.get('desc') else 'asc'
            })
        query.transforms.append(OrderByTransform(
            id=transform_id,
            expressions=expressions
        ))

    # Extract LIMIT
    if limit := ast.args.get('limit'):
        transform_id = f"t{len(query.transforms)}"
        count = int(limit.this.this) if limit.this else 10
        query.transforms.append(LimitTransform(
            id=transform_id,
            count=count
        ))

    return query.to_dict()

def expression_to_json(expr: exp.Expression) -> Dict[str, Any]:
    """Convert SQLGlot expression to JSON"""
    if isinstance(expr, exp.Column):
        return {'type': 'column', 'name': expr.name}
    elif isinstance(expr, exp.Literal):
        return {'type': 'literal', 'value': expr.this, 'data_type': 'string'}
    elif isinstance(expr, (exp.EQ, exp.NEQ, exp.LT, exp.GT, exp.LTE, exp.GTE)):
        op_map = {
            exp.EQ: '=', exp.NEQ: '!=',
            exp.LT: '<', exp.GT: '>',
            exp.LTE: '<=', exp.GTE: '>='
        }
        return {
            'type': 'binary_op',
            'operator': op_map.get(type(expr), '='),
            'left': expression_to_json(expr.this),
            'right': expression_to_json(expr.expression)
        }
    else:
        # Fallback for unsupported expressions
        return {'type': 'unknown', 'value': str(expr)}
```

#### 1.3 Create JSON → ASQL Converter

```python
# /asql/json_schema.py (continued)

def json_to_asql(query_json: Dict[str, Any]) -> str:
    """Convert JSON representation to ASQL text"""

    lines = []

    # FROM clause
    from_clause = query_json.get('from', {})
    table = from_clause.get('table', '')
    lines.append(f"from {table}")

    # Transforms
    for transform in query_json.get('transforms', []):
        transform_type = transform.get('type')

        if transform_type == 'where':
            condition = transform.get('condition', {})
            condition_asql = expression_to_asql(condition)
            lines.append(f"  where {condition_asql}")

        elif transform_type == 'join':
            join_type = transform.get('join_type', 'inner')
            table = transform.get('table', '')
            condition = transform.get('condition')

            join_symbol = {
                'inner': '&', 'left': '&?',
                'right': '?&', 'full': '?&?'
            }.get(join_type, '&')

            if condition:
                condition_asql = expression_to_asql(condition)
                lines.append(f"  {join_symbol} {table} on {condition_asql}")
            else:
                lines.append(f"  {join_symbol} {table}")

        elif transform_type == 'select':
            columns = transform.get('columns', [])
            columns_str = ', '.join(columns)
            lines.append(f"  select {columns_str}")

        elif transform_type == 'group_by':
            dimensions = transform.get('dimensions', [])
            aggregates = transform.get('aggregates', [])

            dims_str = ', '.join(dimensions)
            if aggregates:
                aggs_str = ',\n    '.join([
                    f"{agg['function']}({agg['column']}) as {agg['alias']}"
                    for agg in aggregates
                ])
                lines.append(f"  group by {dims_str} (")
                lines.append(f"    {aggs_str}")
                lines.append(f"  )")
            else:
                lines.append(f"  group by {dims_str}")

        elif transform_type == 'order_by':
            expressions = transform.get('expressions', [])
            order_parts = []
            for expr in expressions:
                col = expr['column']
                direction = expr.get('direction', 'asc')
                order_parts.append(f"{'-' if direction == 'desc' else ''}{col}")
            lines.append(f"  order by {', '.join(order_parts)}")

        elif transform_type == 'limit':
            count = transform.get('count', 10)
            lines.append(f"  limit {count}")

    return '\n'.join(lines)

def expression_to_asql(expr: Dict[str, Any]) -> str:
    """Convert JSON expression to ASQL text"""
    expr_type = expr.get('type')

    if expr_type == 'column':
        return expr.get('name', '')
    elif expr_type == 'literal':
        value = expr.get('value', '')
        data_type = expr.get('data_type', 'string')
        if data_type == 'string':
            return f'"{value}"'
        else:
            return str(value)
    elif expr_type == 'binary_op':
        left = expression_to_asql(expr.get('left', {}))
        right = expression_to_asql(expr.get('right', {}))
        operator = expr.get('operator', '=')
        # Convert = to == for ASQL
        if operator == '=':
            operator = '=='
        return f"{left} {operator} {right}"
    else:
        return str(expr.get('value', ''))
```

#### 1.4 Add API Endpoints

```python
# /playground/app.py (add these routes)

from asql.json_schema import ast_to_json, json_to_asql
from asql.compiler.api import compile_to_ast

@app.post("/api/visual/parse")
async def parse_to_visual(request: Request):
    """Convert ASQL text to JSON for visual editor"""
    try:
        data = await request.json()
        asql_text = data.get('asql', '')

        # Parse to AST
        ast = compile_to_ast(asql_text)

        # Convert AST to JSON
        query_json = ast_to_json(ast)

        return {
            "success": True,
            "query": query_json
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/visual/compile")
async def compile_from_visual(request: Request):
    """Convert JSON from visual editor to ASQL text"""
    try:
        data = await request.json()
        query_json = data.get('query', {})

        # Convert JSON to ASQL
        asql_text = json_to_asql(query_json)

        return {
            "success": True,
            "asql": asql_text
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/visual/operations")
async def list_visual_operations():
    """List available operations for visual editor"""
    # For prototype, return hardcoded list
    return {
        "operations": [
            {"type": "where", "label": "Filter", "icon": "🔍"},
            {"type": "join", "label": "Join", "icon": "🔗"},
            {"type": "select", "label": "Select Columns", "icon": "📋"},
            {"type": "group_by", "label": "Group & Aggregate", "icon": "📊"},
            {"type": "order_by", "label": "Sort", "icon": "⬆️"},
            {"type": "limit", "label": "Limit", "icon": "🔢"}
        ]
    }
```

### Phase 2: Frontend - Visual Block UI (4-5 hours)

#### 2.1 Create Visual Editor HTML Structure

```html
<!-- /playground/templates/index.html (add to input-panel) -->

<div id="input-panel" class="panel input">
  <div class="panel-header">
    <!-- Existing header content -->
    <button id="mode-toggle" class="mode-toggle" title="Toggle Visual Editor">
      <span class="icon">👁️</span>
      <span class="label">Visual</span>
    </button>
  </div>

  <!-- Existing CodeMirror editor -->
  <div id="input-editor-container">
    <textarea id="input-editor"></textarea>
  </div>

  <!-- NEW: Visual editor container -->
  <div id="visual-editor-container" style="display: none;">
    <div class="visual-editor">
      <!-- FROM block (always visible) -->
      <div class="block from-block">
        <div class="block-header">
          <span class="block-icon">📁</span>
          <span class="block-title">From</span>
        </div>
        <div class="block-body">
          <input type="text" id="from-table" placeholder="table_name" class="input-field">
        </div>
      </div>

      <!-- Transform blocks container -->
      <div id="transforms-container">
        <!-- Blocks will be added here dynamically -->
      </div>

      <!-- Add step button -->
      <button id="add-step-btn" class="add-step-btn">
        <span>+ Add Step</span>
      </button>
    </div>
  </div>
</div>

<!-- Add Step Modal -->
<div id="add-step-modal" class="modal" style="display: none;">
  <div class="modal-content">
    <div class="modal-header">
      <h3>Add Pipeline Step</h3>
      <button class="modal-close">&times;</button>
    </div>
    <div class="modal-body">
      <div id="operations-grid" class="operations-grid">
        <!-- Operations will be loaded here -->
      </div>
    </div>
  </div>
</div>
```

#### 2.2 Create Visual Editor JavaScript

```javascript
// /playground/static/visual-editor.js

class VisualEditor {
  constructor() {
    this.query = {
      from: { table: '' },
      transforms: []
    };
    this.operations = [];
    this.init();
  }

  async init() {
    // Load available operations
    await this.loadOperations();

    // Setup event listeners
    this.setupEventListeners();

    // Initialize from table input
    document.getElementById('from-table').addEventListener('input', (e) => {
      this.query.from.table = e.target.value;
      this.notifyChange();
    });
  }

  async loadOperations() {
    const response = await fetch('/api/visual/operations');
    const data = await response.json();
    this.operations = data.operations;
  }

  setupEventListeners() {
    // Add step button
    document.getElementById('add-step-btn').addEventListener('click', () => {
      this.showAddStepModal();
    });

    // Modal close
    document.querySelector('#add-step-modal .modal-close').addEventListener('click', () => {
      this.hideAddStepModal();
    });
  }

  showAddStepModal() {
    const modal = document.getElementById('add-step-modal');
    const grid = document.getElementById('operations-grid');

    // Clear and populate grid
    grid.innerHTML = '';
    this.operations.forEach(op => {
      const card = document.createElement('div');
      card.className = 'operation-card';
      card.innerHTML = `
        <div class="operation-icon">${op.icon}</div>
        <div class="operation-label">${op.label}</div>
      `;
      card.addEventListener('click', () => {
        this.addTransform(op.type);
        this.hideAddStepModal();
      });
      grid.appendChild(card);
    });

    modal.style.display = 'flex';
  }

  hideAddStepModal() {
    document.getElementById('add-step-modal').style.display = 'none';
  }

  addTransform(type) {
    const id = `t${this.query.transforms.length}`;
    const transform = { id, type };

    // Initialize with defaults based on type
    if (type === 'where') {
      transform.condition = { type: 'binary_op', operator: '=', left: {}, right: {} };
    } else if (type === 'join') {
      transform.join_type = 'inner';
      transform.table = '';
    } else if (type === 'select') {
      transform.columns = [];
    } else if (type === 'group_by') {
      transform.dimensions = [];
      transform.aggregates = [];
    } else if (type === 'order_by') {
      transform.expressions = [];
    } else if (type === 'limit') {
      transform.count = 10;
    }

    this.query.transforms.push(transform);
    this.render();
    this.notifyChange();
  }

  removeTransform(id) {
    this.query.transforms = this.query.transforms.filter(t => t.id !== id);
    this.render();
    this.notifyChange();
  }

  render() {
    const container = document.getElementById('transforms-container');
    container.innerHTML = '';

    this.query.transforms.forEach(transform => {
      const blockEl = this.createBlockElement(transform);
      container.appendChild(blockEl);
    });
  }

  createBlockElement(transform) {
    const block = document.createElement('div');
    block.className = `block transform-block ${transform.type}-block`;
    block.dataset.id = transform.id;

    const icons = {
      where: '🔍',
      join: '🔗',
      select: '📋',
      group_by: '📊',
      order_by: '⬆️',
      limit: '🔢'
    };

    const labels = {
      where: 'Filter',
      join: 'Join',
      select: 'Select',
      group_by: 'Group By',
      order_by: 'Sort',
      limit: 'Limit'
    };

    block.innerHTML = `
      <div class="block-header">
        <span class="block-icon">${icons[transform.type]}</span>
        <span class="block-title">${labels[transform.type]}</span>
        <button class="block-delete" data-id="${transform.id}">×</button>
      </div>
      <div class="block-body">
        ${this.renderBlockBody(transform)}
      </div>
    `;

    // Add delete handler
    block.querySelector('.block-delete').addEventListener('click', (e) => {
      this.removeTransform(e.target.dataset.id);
    });

    return block;
  }

  renderBlockBody(transform) {
    switch(transform.type) {
      case 'where':
        return this.renderWhereBlock(transform);
      case 'join':
        return this.renderJoinBlock(transform);
      case 'select':
        return this.renderSelectBlock(transform);
      case 'group_by':
        return this.renderGroupByBlock(transform);
      case 'order_by':
        return this.renderOrderByBlock(transform);
      case 'limit':
        return this.renderLimitBlock(transform);
      default:
        return '<div>Unknown block type</div>';
    }
  }

  renderWhereBlock(transform) {
    // Simplified: just text input for condition
    const condition = transform.condition || {};
    const left = condition.left?.name || '';
    const operator = condition.operator || '=';
    const right = condition.right?.value || '';

    return `
      <div class="where-inputs">
        <input type="text" class="input-field" placeholder="column" value="${left}"
               onchange="visualEditor.updateWhereCondition('${transform.id}', 'left', this.value)">
        <select class="input-field" onchange="visualEditor.updateWhereCondition('${transform.id}', 'operator', this.value)">
          <option value="=" ${operator === '=' ? 'selected' : ''}>=</option>
          <option value="!=" ${operator === '!=' ? 'selected' : ''}>!=</option>
          <option value="<" ${operator === '<' ? 'selected' : ''}><</option>
          <option value=">" ${operator === '>' ? 'selected' : ''}>></option>
        </select>
        <input type="text" class="input-field" placeholder="value" value="${right}"
               onchange="visualEditor.updateWhereCondition('${transform.id}', 'right', this.value)">
      </div>
    `;
  }

  renderJoinBlock(transform) {
    return `
      <div class="join-inputs">
        <select class="input-field" onchange="visualEditor.updateJoin('${transform.id}', 'type', this.value)">
          <option value="inner" ${transform.join_type === 'inner' ? 'selected' : ''}>Inner Join (&)</option>
          <option value="left" ${transform.join_type === 'left' ? 'selected' : ''}>Left Join (&?)</option>
          <option value="right" ${transform.join_type === 'right' ? 'selected' : ''}>Right Join (?&)</option>
          <option value="full" ${transform.join_type === 'full' ? 'selected' : ''}>Full Join (?&?)</option>
        </select>
        <input type="text" class="input-field" placeholder="table_name" value="${transform.table || ''}"
               onchange="visualEditor.updateJoin('${transform.id}', 'table', this.value)">
      </div>
    `;
  }

  renderLimitBlock(transform) {
    return `
      <div class="limit-inputs">
        <input type="number" class="input-field" value="${transform.count || 10}"
               onchange="visualEditor.updateLimit('${transform.id}', this.value)">
      </div>
    `;
  }

  // Simplified renderers for other blocks
  renderSelectBlock(transform) {
    return `<div>Select columns: <input type="text" placeholder="col1, col2, col3" class="input-field"></div>`;
  }

  renderGroupByBlock(transform) {
    return `<div>Group by: <input type="text" placeholder="column" class="input-field"></div>`;
  }

  renderOrderByBlock(transform) {
    return `<div>Order by: <input type="text" placeholder="column" class="input-field"></div>`;
  }

  // Update methods
  updateWhereCondition(id, field, value) {
    const transform = this.query.transforms.find(t => t.id === id);
    if (!transform) return;

    if (field === 'left') {
      transform.condition.left = { type: 'column', name: value };
    } else if (field === 'operator') {
      transform.condition.operator = value;
    } else if (field === 'right') {
      transform.condition.right = { type: 'literal', value: value, data_type: 'string' };
    }

    this.notifyChange();
  }

  updateJoin(id, field, value) {
    const transform = this.query.transforms.find(t => t.id === id);
    if (!transform) return;

    if (field === 'type') {
      transform.join_type = value;
    } else if (field === 'table') {
      transform.table = value;
    }

    this.notifyChange();
  }

  updateLimit(id, value) {
    const transform = this.query.transforms.find(t => t.id === id);
    if (!transform) return;
    transform.count = parseInt(value);
    this.notifyChange();
  }

  async loadFromASQL(asql) {
    try {
      const response = await fetch('/api/visual/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asql })
      });
      const data = await response.json();

      if (data.success) {
        this.query = data.query;
        document.getElementById('from-table').value = this.query.from?.table || '';
        this.render();
      }
    } catch (error) {
      console.error('Failed to parse ASQL:', error);
    }
  }

  async getASQL() {
    try {
      const response = await fetch('/api/visual/compile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: this.query })
      });
      const data = await response.json();

      if (data.success) {
        return data.asql;
      }
    } catch (error) {
      console.error('Failed to compile to ASQL:', error);
    }
    return '';
  }

  notifyChange() {
    // Trigger compilation after changes
    if (window.onVisualEditorChange) {
      window.onVisualEditorChange();
    }
  }
}

// Global instance
let visualEditor;
document.addEventListener('DOMContentLoaded', () => {
  visualEditor = new VisualEditor();
});
```

#### 2.3 Add Mode Toggle Logic

```javascript
// /playground/static/playground.js (add to existing file)

let isVisualMode = false;

// Add mode toggle handler
document.getElementById('mode-toggle').addEventListener('click', toggleEditorMode);

function toggleEditorMode() {
  isVisualMode = !isVisualMode;

  const textContainer = document.getElementById('input-editor-container');
  const visualContainer = document.getElementById('visual-editor-container');
  const toggleBtn = document.getElementById('mode-toggle');

  if (isVisualMode) {
    // Switch to visual mode
    textContainer.style.display = 'none';
    visualContainer.style.display = 'block';
    toggleBtn.classList.add('active');
    toggleBtn.querySelector('.label').textContent = 'Text';

    // Load current ASQL into visual editor
    const currentASQL = inputEditor.getValue();
    if (currentASQL.trim()) {
      visualEditor.loadFromASQL(currentASQL);
    }
  } else {
    // Switch to text mode
    textContainer.style.display = 'block';
    visualContainer.style.display = 'none';
    toggleBtn.classList.remove('active');
    toggleBtn.querySelector('.label').textContent = 'Visual';

    // Update text editor with visual query
    (async () => {
      const asql = await visualEditor.getASQL();
      if (asql) {
        inputEditor.setValue(asql);
      }
    })();
  }
}

// Handle visual editor changes
window.onVisualEditorChange = debounce(async () => {
  if (isVisualMode) {
    const asql = await visualEditor.getASQL();
    // Compile to SQL and update output
    translateQuery(asql);
  }
}, 500);
```

#### 2.4 Add Styles

```css
/* /playground/static/visual-editor.css */

/* Visual Editor Container */
.visual-editor {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
  background: #f8f9fa;
}

/* Blocks */
.block {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin-bottom: 16px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.block-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
  border-radius: 8px 8px 0 0;
}

.block-icon {
  font-size: 20px;
  margin-right: 8px;
}

.block-title {
  font-weight: 600;
  flex: 1;
}

.block-delete {
  background: none;
  border: none;
  font-size: 24px;
  color: #999;
  cursor: pointer;
  padding: 0 8px;
  line-height: 1;
}

.block-delete:hover {
  color: #e53935;
}

.block-body {
  padding: 16px;
}

/* Input Fields */
.input-field {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  font-family: 'Monaco', 'Menlo', monospace;
}

.input-field:focus {
  outline: none;
  border-color: #4CAF50;
}

/* WHERE Block */
.where-inputs {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 8px;
  align-items: center;
}

.where-inputs select {
  width: 80px;
}

/* JOIN Block */
.join-inputs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

/* Add Step Button */
.add-step-btn {
  width: 100%;
  padding: 16px;
  background: #e3f2fd;
  border: 2px dashed #2196F3;
  border-radius: 8px;
  color: #2196F3;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.add-step-btn:hover {
  background: #bbdefb;
  border-color: #1976D2;
  color: #1976D2;
}

/* Operations Grid (Modal) */
.operations-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding: 16px;
}

.operation-card {
  padding: 24px;
  background: white;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.operation-card:hover {
  border-color: #4CAF50;
  background: #f1f8e9;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.operation-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.operation-label {
  font-weight: 600;
  color: #333;
}

/* Mode Toggle Button */
.mode-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #f0f0f0;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-toggle:hover {
  background: #e0e0e0;
}

.mode-toggle.active {
  background: #4CAF50;
  color: white;
  border-color: #4CAF50;
}

.mode-toggle .icon {
  font-size: 16px;
}

.mode-toggle .label {
  font-size: 13px;
  font-weight: 500;
}
```

### Phase 3: Testing & Polish (1-2 hours)

#### Test Cases
1. **Text → Visual**: Parse sample ASQL queries
2. **Visual → Text**: Build query visually, check ASQL output
3. **Roundtrip**: Text → Visual → Text should match
4. **Add/Remove blocks**: Ensure UI updates correctly
5. **Mode switching**: Toggle between modes preserves query

#### Example Test Query
```asql
from orders
  where status == "completed"
  & customers on customer_id
  group by region (
    count(order_id) as orders,
    sum(amount) as revenue
  )
  order by -revenue
  limit 10
```

## Timeline

| Phase | Task | Estimated Time |
|-------|------|---------------|
| 1 | Backend JSON Schema | 3-4 hours |
| 2 | Frontend Visual UI | 4-5 hours |
| 3 | Testing & Polish | 1-2 hours |
| **Total** | **MVP Prototype** | **8-11 hours** |

## Success Criteria

- ✅ Mode toggle button switches between text/visual
- ✅ Visual mode shows FROM + pipeline blocks
- ✅ Can add WHERE, JOIN, SELECT, GROUP BY, ORDER BY, LIMIT
- ✅ Switching to visual mode parses current ASQL
- ✅ Switching to text mode generates valid ASQL
- ✅ Changes in visual mode update output panel (SQL compilation)
- ✅ Basic expressions work (column = "value")

## Future Enhancements (Post-Prototype)

- Schema integration (column/table dropdowns)
- Complex expressions (nested AND/OR, functions)
- All 34+ ASQL transforms
- Drag-and-drop reordering
- CTE/Stash support
- Data preview
- Undo/redo
- Migration to React
