/**
 * Visual ASQL Editor - Schema-Driven UI
 *
 * Automatically generates UI from operation schemas,
 * no manual render functions per operation type.
 */

class VisualEditor {
  constructor() {
    // Support multiple pipelines (array format)
    this.pipelines = [{
      name: null,
      from: { table: '' },
      transforms: []
    }];
    this.currentPipelineIndex = 0;  // Currently active pipeline
    this.operations = [];
    this.schemas = {};
    this.initialized = false;
    this.nextTransformId = 0;  // Counter for unique transform IDs
  }

  // Getter for backward compatibility
  get query() {
    return this.pipelines[this.currentPipelineIndex] || this.pipelines[0];
  }

  set query(value) {
    if (Array.isArray(value)) {
      this.pipelines = value;
    } else {
      this.pipelines[this.currentPipelineIndex] = value;
    }
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

    // Add pipeline button
    const addPipelineBtn = document.getElementById('add-pipeline-btn');
    if (addPipelineBtn) {
      addPipelineBtn.addEventListener('click', () => this.addPipeline());
    }

    // Modal close
    const modalClose = document.querySelector('#add-step-modal .modal-close');
    if (modalClose) {
      modalClose.addEventListener('click', () => this.hideAddStepModal());
    }
  }

  addPipeline(setOperation = null) {
    const newPipeline = {
      name: null,
      from: { table: '' },
      transforms: []
    };
    
    // If there's a set operation, add it to the previous pipeline
    if (setOperation && this.pipelines.length > 0) {
      this.pipelines[this.pipelines.length - 1].set_operation = setOperation;
    }
    
    this.pipelines.push(newPipeline);
    this.currentPipelineIndex = this.pipelines.length - 1;
    this.renderAll();
    this.notifyChange();
  }

  removePipeline(index) {
    if (this.pipelines.length <= 1) return; // Keep at least one pipeline
    
    // Remove set_operation from previous pipeline if exists
    if (index > 0 && this.pipelines[index - 1].set_operation) {
      delete this.pipelines[index - 1].set_operation;
    }
    
    this.pipelines.splice(index, 1);
    if (this.currentPipelineIndex >= this.pipelines.length) {
      this.currentPipelineIndex = this.pipelines.length - 1;
    }
    this.renderAll();
    this.notifyChange();
  }

  setPipelineName(index, name) {
    if (this.pipelines[index]) {
      this.pipelines[index].name = name || null;
      this.notifyChange();
    }
  }

  setSetOperation(index, opType, all = false) {
    if (this.pipelines[index] && index < this.pipelines.length - 1) {
      this.pipelines[index].set_operation = { type: opType, all };
      this.renderAll();
      this.notifyChange();
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
      const labelDiv = document.createElement('div');
      labelDiv.className = 'operation-label';
      labelDiv.textContent = op.label || '';
      
      const descDiv = document.createElement('div');
      descDiv.className = 'operation-description';
      descDiv.textContent = op.description || '';
      
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

  addTransform(type, pipelineIndex = null) {
    const idx = pipelineIndex !== null ? pipelineIndex : this.currentPipelineIndex;
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

    if (this.pipelines[idx]) {
      this.pipelines[idx].transforms.push(transform);
    }
    
    // Use renderAll if we have multiple pipelines, otherwise just render current
    if (this.pipelines.length > 1) {
      this.renderAll();
    } else {
      this.render();
    }
    this.notifyChange();
  }

  removeTransform(id, pipelineIndex = null) {
    const idx = pipelineIndex !== null ? pipelineIndex : this.currentPipelineIndex;
    
    if (this.pipelines[idx]) {
      this.pipelines[idx].transforms = this.pipelines[idx].transforms.filter(t => t.id !== id);
    }
    
    // Use renderAll if we have multiple pipelines, otherwise just render current
    if (this.pipelines.length > 1) {
      this.renderAll();
    } else {
      this.render();
    }
    this.notifyChange();
  }

  render() {
    // Render transforms for current pipeline only (for backward compat)
    const container = document.getElementById('transforms-container');
    if (!container) return;

    container.innerHTML = '';

    this.query.transforms.forEach(transform => {
      const blockEl = this.createBlockElement(transform);
      container.appendChild(blockEl);
    });
  }

  renderAll() {
    // Render all pipelines (for multi-pipeline support)
    const container = document.getElementById('transforms-container');
    if (!container) return;

    container.innerHTML = '';

    this.pipelines.forEach((pipeline, pipelineIdx) => {
      // Pipeline wrapper
      const pipelineDiv = document.createElement('div');
      pipelineDiv.className = 'pipeline-block input-pipeline';
      pipelineDiv.dataset.pipelineIndex = pipelineIdx;

      // Pipeline header with name input
      const header = document.createElement('div');
      header.className = 'pipeline-header';
      
      // Pipeline name input
      const nameLabel = document.createElement('span');
      nameLabel.className = 'pipeline-name-label';
      nameLabel.textContent = 'Pipeline name (for CTE):';
      
      const nameInput = document.createElement('input');
      nameInput.type = 'text';
      nameInput.className = 'pipeline-name-input';
      nameInput.placeholder = 'optional (e.g. active_users)';
      nameInput.value = pipeline.name || '';
      nameInput.dataset.pipelineIndex = pipelineIdx;
      nameInput.addEventListener('input', (e) => {
        this.setPipelineName(pipelineIdx, e.target.value);
      });

      // Remove pipeline button (only show if more than one pipeline)
      if (this.pipelines.length > 1) {
        const removeBtn = document.createElement('button');
        removeBtn.className = 'pipeline-remove-btn';
        removeBtn.textContent = '×';
        removeBtn.title = 'Remove pipeline';
        removeBtn.addEventListener('click', () => this.removePipeline(pipelineIdx));
        header.appendChild(removeBtn);
      }

      header.appendChild(nameLabel);
      header.appendChild(nameInput);
      pipelineDiv.appendChild(header);

      // FROM block for this pipeline
      const fromBlock = document.createElement('div');
      fromBlock.className = 'block from-block';
      fromBlock.innerHTML = `
        <div class="block-body">
          <span class="value-operator">from</span>
          <input type="text" 
                 class="pipeline-from-input" 
                 placeholder="table name"
                 value="${this.escapeHtml(pipeline.from?.table || '')}"
                 data-pipeline-index="${pipelineIdx}">
        </div>
      `;
      pipelineDiv.appendChild(fromBlock);

      // Transforms for this pipeline
      (pipeline.transforms || []).forEach(transform => {
        const blockEl = this.createBlockElement(transform, pipelineIdx);
        pipelineDiv.appendChild(blockEl);
      });

      // Add step button for this pipeline
      const addStepBtn = document.createElement('button');
      addStepBtn.className = 'add-step-btn-inline';
      addStepBtn.textContent = '+ Add Step';
      addStepBtn.dataset.pipelineIndex = pipelineIdx;
      addStepBtn.addEventListener('click', () => {
        this.currentPipelineIndex = pipelineIdx;
        this.showAddStepModal();
      });
      pipelineDiv.appendChild(addStepBtn);

      container.appendChild(pipelineDiv);

      // Set operation between pipelines
      if (pipelineIdx < this.pipelines.length - 1) {
        const setOpDiv = document.createElement('div');
        setOpDiv.className = 'set-operation-selector';
        
        const currentOp = pipeline.set_operation?.type || 'union';
        const isAll = pipeline.set_operation?.all || false;
        
        setOpDiv.innerHTML = `
          <select class="set-op-select" data-pipeline-index="${pipelineIdx}">
            <option value="union" ${currentOp === 'union' && !isAll ? 'selected' : ''}>UNION</option>
            <option value="union_all" ${currentOp === 'union' && isAll ? 'selected' : ''}>UNION ALL</option>
            <option value="intersect" ${currentOp === 'intersect' ? 'selected' : ''}>INTERSECT</option>
            <option value="except" ${currentOp === 'except' ? 'selected' : ''}>EXCEPT</option>
          </select>
        `;
        container.appendChild(setOpDiv);
      }
    });

    // Add new pipeline button
    const addPipelineDiv = document.createElement('div');
    addPipelineDiv.className = 'add-pipeline-container';
    addPipelineDiv.innerHTML = `
      <button class="add-pipeline-btn" id="add-pipeline-btn-inline">+ Add Pipeline (CTE / Set Operation)</button>
    `;
    addPipelineDiv.querySelector('button').addEventListener('click', () => {
      this.addPipeline({ type: 'union', all: false });
    });
    container.appendChild(addPipelineDiv);

    // Update the main FROM input (for first pipeline, backward compat)
    const mainFromInput = document.getElementById('from-table');
    if (mainFromInput && this.pipelines[0]) {
      mainFromInput.value = this.pipelines[0].from?.table || '';
    }
  }

  createBlockElement(transform, pipelineIndex = null) {
    const idx = pipelineIndex !== null ? pipelineIndex : this.currentPipelineIndex;
    const schema = this.schemas[transform.type];
    if (!schema) {
      return this.createErrorBlock(transform, 'Schema not loaded');
    }

    const block = document.createElement('div');
    block.className = `block transform-block ${transform.type}-block`;
    block.dataset.id = transform.id;
    block.dataset.pipelineIndex = idx;

    // Build header safely to avoid XSS with server-provided strings
    const header = document.createElement('div');
    header.className = 'block-header';
    
    const titleSpan = document.createElement('span');
    titleSpan.className = 'block-title';
    titleSpan.textContent = schema.label || transform.type;
    
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'block-delete';
    deleteBtn.dataset.id = transform.id;
    deleteBtn.dataset.pipelineIndex = idx;
    deleteBtn.textContent = '×';
    deleteBtn.addEventListener('click', () => {
      this.removeTransform(transform.id, idx);
    });
    
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
    const value = transform[param.name] ?? '';
    return `
      <div class="field">
        <label>${this.escapeHtml(param.label)}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${this.escapeHtml(param.help)}</p>` : ''}
        <input type="text"
               class="input-field"
               placeholder="${this.escapeHtml(param.placeholder || '')}"
               value="${this.escapeHtml(value)}"
               data-param="${param.name}"
               data-transform-id="${transform.id}">
      </div>
    `;
  }

  renderNumberWidget(transform, param) {
    const rawValue = transform[param.name] !== undefined ? transform[param.name] : (param.default ?? 0);
    const value = rawValue === null || Number.isNaN(rawValue) ? '' : rawValue;
    return `
      <div class="field">
        <label>${this.escapeHtml(param.label)}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${this.escapeHtml(param.help)}</p>` : ''}
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
    const value = transform[param.name] ?? param.default ?? '';
    return `
      <div class="field">
        <label>${this.escapeHtml(param.label)}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${this.escapeHtml(param.help)}</p>` : ''}
        <select class="input-field"
                data-param="${param.name}"
                data-transform-id="${transform.id}">
          ${(param.options || []).map(opt => `
            <option value="${this.escapeHtml(opt.value)}" ${value === opt.value ? 'selected' : ''}>
              ${this.escapeHtml(opt.label)}
            </option>
          `).join('')}
        </select>
      </div>
    `;
  }

  renderExpressionWidget(transform, param) {
    const expr = transform[param.name] ?? {};
    const leftValue = expr.left?.name ?? '';
    const operator = expr.operator ?? '=';
    const rightValue = expr.right?.value ?? '';

    return `
      <div class="field">
        <label>${this.escapeHtml(param.label)}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${this.escapeHtml(param.help)}</p>` : ''}
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
              <option value="${this.escapeHtml(op)}" ${operator === op ? 'selected' : ''}>${this.escapeHtml(op)}</option>
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
    const items = transform[param.name] ?? [];
    return `
      <div class="field">
        <label>${this.escapeHtml(param.label)}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${this.escapeHtml(param.help)}</p>` : ''}
        <div class="list-items" data-param="${param.name}" data-transform-id="${transform.id}">
          ${items.map((item, idx) => `
            <div class="list-item">
              <input type="text"
                     class="input-field"
                     value="${this.escapeHtml(item)}"
                     placeholder="${this.escapeHtml(param.placeholder || '')}"
                     data-list-index="${idx}">
              <button class="list-item-remove" data-list-index="${idx}">×</button>
            </div>
          `).join('')}
          <button class="list-add-btn" data-param="${param.name}" data-transform-id="${transform.id}">
            + Add ${this.escapeHtml(param.label)}
          </button>
        </div>
      </div>
    `;
  }

  renderAggregateListWidget(transform, param) {
    const aggregates = transform[param.name] ?? [];
    const functions = param.functions || ['count', 'sum', 'avg'];

    return `
      <div class="field">
        <label>${this.escapeHtml(param.label)}</label>
        ${param.help ? `<p class="help">${this.escapeHtml(param.help)}</p>` : ''}
        <div class="aggregate-items" data-param="${param.name}" data-transform-id="${transform.id}">
          ${aggregates.map((agg, idx) => `
            <div class="aggregate-item">
              <select class="input-field" data-agg-index="${idx}" data-agg-field="function">
                ${functions.map(fn => `
                  <option value="${this.escapeHtml(fn)}" ${agg.function === fn ? 'selected' : ''}>
                    ${this.escapeHtml(fn.charAt(0).toUpperCase() + fn.slice(1))}
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
    const expressions = transform[param.name] ?? [];

    return `
      <div class="field">
        <label>${this.escapeHtml(param.label)}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${this.escapeHtml(param.help)}</p>` : ''}
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
      this.pipelines = [{ name: null, from: { table: '' }, transforms: [] }];
      this.currentPipelineIndex = 0;
      this.renderAll();
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
        this.loadFromJSON(data.query);
      } else {
        console.error('Failed to parse ASQL:', data.error);
      }
    } catch (error) {
      console.error('Error parsing ASQL:', error);
    }
  }

  /**
   * Load query from JSON object directly (supports both array and single object format)
   */
  loadFromJSON(json) {
    if (!json) {
      this.pipelines = [{ name: null, from: { table: '' }, transforms: [] }];
      this.currentPipelineIndex = 0;
      this.renderAll();
      return;
    }

    // Handle both array and single object format
    if (Array.isArray(json)) {
      this.pipelines = json.length > 0 ? json : [{ name: null, from: { table: '' }, transforms: [] }];
    } else if (typeof json === 'object') {
      this.pipelines = [json];
    } else {
      this.pipelines = [{ name: null, from: { table: '' }, transforms: [] }];
    }

    this.currentPipelineIndex = 0;

    // Compute max existing transform ID across all pipelines to prevent collisions
    let maxId = -1;
    this.pipelines.forEach(pipeline => {
      if (pipeline.transforms && pipeline.transforms.length > 0) {
        pipeline.transforms.forEach(transform => {
          const id = parseInt(String(transform.id || '').replace(/^t/, ''), 10);
          if (!Number.isNaN(id) && id > maxId) {
            maxId = id;
          }
          // Ensure transform has an ID
          if (!transform.id) {
            transform.id = `t${++maxId}`;
          }
        });
      }
    });
    this.nextTransformId = maxId + 1;

    // Render based on number of pipelines
    if (this.pipelines.length > 1) {
      this.renderAll();
    } else {
      // Single pipeline - use simple rendering
      const fromInput = document.getElementById('from-table');
      if (fromInput && this.pipelines[0]) {
        fromInput.value = this.pipelines[0].from?.table || '';
      }
      this.render();
    }
  }

  /**
   * Get ASQL text from current query (supports multiple pipelines)
   */
  async getASQL() {
    try {
      // Send array format for multiple pipelines, single object for one
      const queryData = this.pipelines.length > 1 ? this.pipelines : this.pipelines[0];
      
      const response = await fetch('/api/visual/compile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryData })
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

  /**
   * Get JSON representation of current query
   */
  getJSON() {
    return this.pipelines.length > 1 ? this.pipelines : this.pipelines[0];
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
  
  // Handle pipeline FROM inputs
  if (target.classList.contains('pipeline-from-input')) {
    const pipelineIndex = parseInt(target.dataset.pipelineIndex);
    if (!isNaN(pipelineIndex) && visualEditor.pipelines[pipelineIndex]) {
      visualEditor.pipelines[pipelineIndex].from.table = target.value;
      visualEditor.notifyChange();
    }
    return;
  }
  
  const transformId = target.dataset.transformId;
  const param = target.dataset.param;

  if (!transformId || !param) return;

  // Find transform across all pipelines
  let transform = null;
  const pipelineIdx = target.dataset.pipelineIndex !== undefined 
    ? parseInt(target.dataset.pipelineIndex) 
    : visualEditor.currentPipelineIndex;
  
  if (visualEditor.pipelines[pipelineIdx]) {
    transform = visualEditor.pipelines[pipelineIdx].transforms.find(t => t.id === transformId);
  }
  
  // Fallback: search all pipelines
  if (!transform) {
    for (const pipeline of visualEditor.pipelines) {
      transform = pipeline.transforms.find(t => t.id === transformId);
      if (transform) break;
    }
  }
  
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
    if (target.type === 'number') {
      const numericValue = target.valueAsNumber;
      transform[param] = Number.isNaN(numericValue) ? null : numericValue;
    } else {
      transform[param] = target.value;
    }
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

// Change event delegation for select elements (set operations)
document.addEventListener('change', (e) => {
  if (!visualEditor || !visualEditor.initialized) return;

  const target = e.target;

  // Handle set operation select
  if (target.classList.contains('set-op-select')) {
    const pipelineIndex = parseInt(target.dataset.pipelineIndex);
    const value = target.value;
    
    if (!isNaN(pipelineIndex) && visualEditor.pipelines[pipelineIndex]) {
      if (value === 'union_all') {
        visualEditor.pipelines[pipelineIndex].set_operation = { type: 'union', all: true };
      } else {
        visualEditor.pipelines[pipelineIndex].set_operation = { type: value, all: false };
      }
      visualEditor.notifyChange();
    }
  }
});
