/**
 * Visual ASQL Editor - Schema-Driven UI
 *
 * Automatically generates UI from operation schemas,
 * no manual render functions per operation type.
 */

class VisualEditor {
  constructor() {
    this.query = {
      from: { table: '' },
      transforms: []
    };
    this.operations = [];
    this.schemas = {};
    this.initialized = false;
    this.nextTransformId = 0;  // Counter for unique transform IDs
  }

  async init() {
    try {
      // Load operation metadata
      const opsResponse = await fetch('/api/visual/operations');
      if (!opsResponse.ok) {
        console.error('Failed to load operations: HTTP', opsResponse.status);
        return;
      }
      const opsData = await opsResponse.json();
      this.operations = opsData.operations || [];

      // Load schemas for all operations
      await this.loadSchemas();

      // Setup event listeners
      this.setupEventListeners();

      this.initialized = true;
    } catch (error) {
      console.error('Failed to initialize visual editor:', error);
    }
  }

  async loadSchemas() {
    for (const op of this.operations) {
      try {
        const response = await fetch(`/api/visual/operations/${op.type}/schema`);
        if (!response.ok) {
          console.error(`Failed to load schema for ${op.type}: HTTP ${response.status}`);
          continue;
        }
        const schema = await response.json();
        this.schemas[op.type] = schema;
      } catch (error) {
        console.error(`Failed to load schema for ${op.type}:`, error);
      }
    }
  }

  setupEventListeners() {
    // FROM table input
    const fromInput = document.getElementById('from-table');
    if (fromInput) {
      fromInput.addEventListener('input', (e) => {
        this.query.from.table = e.target.value;
        this.notifyChange();
      });
    }

    // Add step button
    const addBtn = document.getElementById('add-step-btn');
    if (addBtn) {
      addBtn.addEventListener('click', () => this.showAddStepModal());
    }

    // Modal close
    const modalClose = document.querySelector('#add-step-modal .modal-close');
    if (modalClose) {
      modalClose.addEventListener('click', () => this.hideAddStepModal());
    }
  }

  showAddStepModal() {
    const modal = document.getElementById('add-step-modal');
    const grid = document.getElementById('operations-grid');

    if (!modal || !grid) return;

    // Clear and populate grid
    grid.innerHTML = '';
    this.operations.forEach(op => {
      const card = document.createElement('div');
      card.className = 'operation-card';
      
      // Build DOM safely to avoid XSS
      const iconDiv = document.createElement('div');
      iconDiv.className = 'operation-icon';
      iconDiv.textContent = op.icon || '';
      
      const labelDiv = document.createElement('div');
      labelDiv.className = 'operation-label';
      labelDiv.textContent = op.label || '';
      
      const descDiv = document.createElement('div');
      descDiv.className = 'operation-description';
      descDiv.textContent = op.description || '';
      
      card.appendChild(iconDiv);
      card.appendChild(labelDiv);
      card.appendChild(descDiv);
      
      card.addEventListener('click', () => {
        this.addTransform(op.type);
        this.hideAddStepModal();
      });
      grid.appendChild(card);
    });

    modal.style.display = 'flex';
  }

  hideAddStepModal() {
    const modal = document.getElementById('add-step-modal');
    if (modal) {
      modal.style.display = 'none';
    }
  }

  addTransform(type) {
    const id = `t${this.nextTransformId++}`;
    const schema = this.schemas[type];

    // Initialize transform with defaults from schema
    const transform = { id, type };

    if (schema && schema.parameters) {
      schema.parameters.forEach(param => {
        if (param.default !== undefined) {
          transform[param.name] = param.default;
        } else if (param.widget === 'list' || param.widget === 'aggregate_list' || param.widget === 'order_list') {
          transform[param.name] = [];
        }
      });
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
    if (!container) return;

    container.innerHTML = '';

    this.query.transforms.forEach(transform => {
      const blockEl = this.createBlockElement(transform);
      container.appendChild(blockEl);
    });
  }

  createBlockElement(transform) {
    const schema = this.schemas[transform.type];
    if (!schema) {
      return this.createErrorBlock(transform, 'Schema not loaded');
    }

    const block = document.createElement('div');
    block.className = `block transform-block ${transform.type}-block`;
    block.dataset.id = transform.id;

    // Build header safely to avoid XSS with server-provided strings
    const header = document.createElement('div');
    header.className = 'block-header';
    
    const iconSpan = document.createElement('span');
    iconSpan.className = 'block-icon';
    iconSpan.textContent = schema.icon || '📦';
    
    const titleSpan = document.createElement('span');
    titleSpan.className = 'block-title';
    titleSpan.textContent = schema.label || transform.type;
    
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'block-delete';
    deleteBtn.dataset.id = transform.id;
    deleteBtn.textContent = '×';
    deleteBtn.addEventListener('click', () => {
      this.removeTransform(transform.id);
    });
    
    header.appendChild(iconSpan);
    header.appendChild(titleSpan);
    header.appendChild(deleteBtn);
    
    // Body contains form widgets - these use escapeHtml for user values
    const body = document.createElement('div');
    body.className = 'block-body';
    body.innerHTML = this.renderBlockBody(transform, schema);
    
    block.appendChild(header);
    block.appendChild(body);

    return block;
  }

  createErrorBlock(transform, error) {
    const block = document.createElement('div');
    block.className = 'block error-block';
    
    // Build DOM safely to avoid XSS
    const header = document.createElement('div');
    header.className = 'block-header';
    const title = document.createElement('span');
    title.className = 'block-title';
    title.textContent = `${transform.type} (Error)`;
    header.appendChild(title);
    
    const body = document.createElement('div');
    body.className = 'block-body';
    const errorP = document.createElement('p');
    errorP.className = 'error';
    errorP.textContent = error;
    body.appendChild(errorP);
    
    block.appendChild(header);
    block.appendChild(body);
    return block;
  }

  /**
   * Schema-driven rendering - generates UI from schema definition
   */
  renderBlockBody(transform, schema) {
    if (!schema.parameters || schema.parameters.length === 0) {
      return '<p class="empty">No configuration needed</p>';
    }

    return schema.parameters.map(param => {
      return this.renderParameter(transform, param);
    }).join('');
  }

  /**
   * Render a single parameter based on its widget type
   */
  renderParameter(transform, param) {
    const widget = param.widget || 'text';

    // Dispatch to widget renderer
    switch (widget) {
      case 'text':
        return this.renderTextWidget(transform, param);
      case 'number':
        return this.renderNumberWidget(transform, param);
      case 'dropdown':
        return this.renderDropdownWidget(transform, param);
      case 'expression':
        return this.renderExpressionWidget(transform, param);
      case 'list':
        return this.renderListWidget(transform, param);
      case 'aggregate_list':
        return this.renderAggregateListWidget(transform, param);
      case 'order_list':
        return this.renderOrderListWidget(transform, param);
      default:
        return `<div class="field"><p class="error">Unknown widget: ${widget}</p></div>`;
    }
  }

  renderTextWidget(transform, param) {
    const value = transform[param.name] || '';
    return `
      <div class="field">
        <label>${param.label}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${param.help}</p>` : ''}
        <input type="text"
               class="input-field"
               placeholder="${param.placeholder || ''}"
               value="${this.escapeHtml(value)}"
               data-param="${param.name}"
               data-transform-id="${transform.id}">
      </div>
    `;
  }

  renderNumberWidget(transform, param) {
    const value = transform[param.name] !== undefined ? transform[param.name] : (param.default || 0);
    return `
      <div class="field">
        <label>${param.label}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${param.help}</p>` : ''}
        <input type="number"
               class="input-field"
               value="${value}"
               ${param.min !== undefined ? `min="${param.min}"` : ''}
               ${param.max !== undefined ? `max="${param.max}"` : ''}
               data-param="${param.name}"
               data-transform-id="${transform.id}">
      </div>
    `;
  }

  renderDropdownWidget(transform, param) {
    const value = transform[param.name] || param.default || '';
    return `
      <div class="field">
        <label>${param.label}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${param.help}</p>` : ''}
        <select class="input-field"
                data-param="${param.name}"
                data-transform-id="${transform.id}">
          ${(param.options || []).map(opt => `
            <option value="${opt.value}" ${value === opt.value ? 'selected' : ''}>
              ${opt.label}
            </option>
          `).join('')}
        </select>
      </div>
    `;
  }

  renderExpressionWidget(transform, param) {
    const expr = transform[param.name] || {};
    const leftValue = expr.left?.name || '';
    const operator = expr.operator || '=';
    const rightValue = expr.right?.value || '';

    return `
      <div class="field">
        <label>${param.label}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${param.help}</p>` : ''}
        <div class="expression-inputs">
          <input type="text"
                 class="input-field"
                 placeholder="column"
                 value="${this.escapeHtml(leftValue)}"
                 data-param="${param.name}"
                 data-expr-part="left"
                 data-transform-id="${transform.id}">
          <select class="input-field"
                  data-param="${param.name}"
                  data-expr-part="operator"
                  data-transform-id="${transform.id}">
            ${(param.operators || ['=']).map(op => `
              <option value="${op}" ${operator === op ? 'selected' : ''}>${op}</option>
            `).join('')}
          </select>
          <input type="text"
                 class="input-field"
                 placeholder="value"
                 value="${this.escapeHtml(rightValue)}"
                 data-param="${param.name}"
                 data-expr-part="right"
                 data-transform-id="${transform.id}">
        </div>
      </div>
    `;
  }

  renderListWidget(transform, param) {
    const items = transform[param.name] || [];
    return `
      <div class="field">
        <label>${param.label}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${param.help}</p>` : ''}
        <div class="list-items" data-param="${param.name}" data-transform-id="${transform.id}">
          ${items.map((item, idx) => `
            <div class="list-item">
              <input type="text"
                     class="input-field"
                     value="${this.escapeHtml(item)}"
                     placeholder="${param.placeholder || ''}"
                     data-list-index="${idx}">
              <button class="list-item-remove" data-list-index="${idx}">×</button>
            </div>
          `).join('')}
          <button class="list-add-btn" data-param="${param.name}" data-transform-id="${transform.id}">
            + Add ${param.label}
          </button>
        </div>
      </div>
    `;
  }

  renderAggregateListWidget(transform, param) {
    const aggregates = transform[param.name] || [];
    const functions = param.functions || ['count', 'sum', 'avg'];

    return `
      <div class="field">
        <label>${param.label}</label>
        ${param.help ? `<p class="help">${param.help}</p>` : ''}
        <div class="aggregate-items" data-param="${param.name}" data-transform-id="${transform.id}">
          ${aggregates.map((agg, idx) => `
            <div class="aggregate-item">
              <select class="input-field" data-agg-index="${idx}" data-agg-field="function">
                ${functions.map(fn => `
                  <option value="${fn}" ${agg.function === fn ? 'selected' : ''}>
                    ${fn.charAt(0).toUpperCase() + fn.slice(1)}
                  </option>
                `).join('')}
              </select>
              <input type="text"
                     class="input-field"
                     placeholder="column"
                     value="${this.escapeHtml(agg.column || '')}"
                     data-agg-index="${idx}"
                     data-agg-field="column">
              <input type="text"
                     class="input-field"
                     placeholder="alias"
                     value="${this.escapeHtml(agg.alias || '')}"
                     data-agg-index="${idx}"
                     data-agg-field="alias">
              <button class="list-item-remove" data-agg-index="${idx}">×</button>
            </div>
          `).join('')}
          <button class="list-add-btn" data-param="${param.name}" data-transform-id="${transform.id}">
            + Add Aggregate
          </button>
        </div>
      </div>
    `;
  }

  renderOrderListWidget(transform, param) {
    const expressions = transform[param.name] || [];

    return `
      <div class="field">
        <label>${param.label}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${param.help}</p>` : ''}
        <div class="order-items" data-param="${param.name}" data-transform-id="${transform.id}">
          ${expressions.map((expr, idx) => `
            <div class="order-item">
              <input type="text"
                     class="input-field"
                     placeholder="column"
                     value="${this.escapeHtml(expr.column || '')}"
                     data-order-index="${idx}"
                     data-order-field="column">
              <select class="input-field" data-order-index="${idx}" data-order-field="direction">
                <option value="asc" ${expr.direction === 'asc' ? 'selected' : ''}>Ascending</option>
                <option value="desc" ${expr.direction === 'desc' ? 'selected' : ''}>Descending</option>
              </select>
              <button class="list-item-remove" data-order-index="${idx}">×</button>
            </div>
          `).join('')}
          <button class="list-add-btn" data-param="${param.name}" data-transform-id="${transform.id}">
            + Add Column
          </button>
        </div>
      </div>
    `;
  }

  /**
   * Load query from ASQL text
   */
  async loadFromASQL(asql) {
    if (!asql.trim()) {
      this.query = { from: { table: '' }, transforms: [] };
      this.render();
      return;
    }

    try {
      const response = await fetch('/api/visual/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asql })
      });
      
      if (!response.ok) {
        console.error('Failed to parse ASQL: HTTP', response.status);
        return;
      }
      
      const data = await response.json();

      if (data.success) {
        this.query = data.query;

        // Compute max existing transform ID to prevent collisions
        if (this.query.transforms && this.query.transforms.length > 0) {
          const maxId = this.query.transforms
            .map(t => parseInt(String(t.id || '').replace(/^t/, ''), 10))
            .filter(n => !Number.isNaN(n))
            .reduce((a, b) => Math.max(a, b), -1);
          this.nextTransformId = maxId + 1;
          
          // Ensure all transforms have unique IDs for event handling
          this.query.transforms.forEach(transform => {
            if (!transform.id) {
              transform.id = `t${this.nextTransformId++}`;
            }
          });
        }

        const fromInput = document.getElementById('from-table');
        if (fromInput) {
          fromInput.value = this.query.from?.table || '';
        }
        this.render();
      } else {
        console.error('Failed to parse ASQL:', data.error);
      }
    } catch (error) {
      console.error('Error parsing ASQL:', error);
    }
  }

  /**
   * Get ASQL text from current query
   */
  async getASQL() {
    try {
      const response = await fetch('/api/visual/compile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: this.query })
      });
      
      if (!response.ok) {
        console.error('Failed to compile ASQL: HTTP', response.status);
        return '';
      }
      
      const data = await response.json();

      if (data.success) {
        return data.asql;
      } else {
        console.error('Compilation error:', data.error);
        return '';
      }
    } catch (error) {
      console.error('Error compiling to ASQL:', error);
      return '';
    }
  }

  notifyChange() {
    // Trigger compilation after changes
    if (window.onVisualEditorChange) {
      window.onVisualEditorChange();
    }
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Global instance - will be initialized when visual mode is activated
let visualEditor = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  visualEditor = new VisualEditor();
  visualEditor.init();
});

// Event delegation for dynamically created form fields
document.addEventListener('input', (e) => {
  if (!visualEditor || !visualEditor.initialized) return;

  const target = e.target;
  const transformId = target.dataset.transformId;
  const param = target.dataset.param;

  if (!transformId || !param) return;

  const transform = visualEditor.query.transforms.find(t => t.id === transformId);
  if (!transform) return;

  // Handle different widget types
  if (target.dataset.exprPart) {
    // Expression widget
    handleExpressionUpdate(transform, param, target);
  } else if (target.dataset.listIndex !== undefined) {
    // List widget
    handleListUpdate(transform, param, target);
  } else if (target.dataset.aggIndex !== undefined) {
    // Aggregate widget
    handleAggregateUpdate(transform, param, target);
  } else if (target.dataset.orderIndex !== undefined) {
    // Order widget
    handleOrderUpdate(transform, param, target);
  } else {
    // Simple field
    const value = target.type === 'number' ? parseInt(target.value) : target.value;
    transform[param] = value;
  }

  visualEditor.notifyChange();
});

// Expression update handler
function handleExpressionUpdate(transform, param, target) {
  if (!transform[param]) {
    transform[param] = { type: 'binary_op' };
  }

  const part = target.dataset.exprPart;
  if (part === 'left') {
    transform[param].left = { type: 'column', name: target.value };
  } else if (part === 'operator') {
    transform[param].operator = target.value;
  } else if (part === 'right') {
    transform[param].right = { type: 'literal', value: target.value, data_type: 'string' };
  }
}

// List update handler
function handleListUpdate(transform, param, target) {
  const items = transform[param] || [];
  const index = parseInt(target.dataset.listIndex);
  items[index] = target.value;
  transform[param] = items;
}

// Aggregate update handler
function handleAggregateUpdate(transform, param, target) {
  const aggregates = transform[param] || [];
  const index = parseInt(target.dataset.aggIndex);
  const field = target.dataset.aggField;

  if (!aggregates[index]) {
    aggregates[index] = {};
  }

  aggregates[index][field] = target.value;
  transform[param] = aggregates;
}

// Order update handler
function handleOrderUpdate(transform, param, target) {
  const expressions = transform[param] || [];
  const index = parseInt(target.dataset.orderIndex);
  const field = target.dataset.orderField;

  if (!expressions[index]) {
    expressions[index] = {};
  }

  expressions[index][field] = target.value;
  transform[param] = expressions;
}

// Click event delegation for buttons
document.addEventListener('click', (e) => {
  if (!visualEditor || !visualEditor.initialized) return;

  const target = e.target;

  // List add button
  if (target.classList.contains('list-add-btn')) {
    const transformId = target.dataset.transformId;
    const param = target.dataset.param;
    const transform = visualEditor.query.transforms.find(t => t.id === transformId);

    if (transform) {
      if (param === 'aggregates') {
        // Add aggregate
        if (!transform[param]) transform[param] = [];
        transform[param].push({ function: 'count', column: '', alias: '' });
      } else if (param === 'expressions' && target.closest('.order-items')) {
        // Add order expression
        if (!transform[param]) transform[param] = [];
        transform[param].push({ column: '', direction: 'asc' });
      } else {
        // Add list item
        if (!transform[param]) transform[param] = [];
        transform[param].push('');
      }
      visualEditor.render();
      visualEditor.notifyChange();
    }
  }

  // List remove button
  if (target.classList.contains('list-item-remove')) {
    const listItem = target.closest('.list-item, .aggregate-item, .order-item');
    if (!listItem) return;

    const container = target.closest('[data-param][data-transform-id]');
    if (!container) return;

    const transformId = container.dataset.transformId;
    const param = container.dataset.param;
    const transform = visualEditor.query.transforms.find(t => t.id === transformId);

    if (transform && transform[param]) {
      let index;
      if (target.dataset.listIndex !== undefined) {
        index = parseInt(target.dataset.listIndex);
      } else if (target.dataset.aggIndex !== undefined) {
        index = parseInt(target.dataset.aggIndex);
      } else if (target.dataset.orderIndex !== undefined) {
        index = parseInt(target.dataset.orderIndex);
      }

      if (index !== undefined) {
        transform[param].splice(index, 1);
        visualEditor.render();
        visualEditor.notifyChange();
      }
    }
  }
});
