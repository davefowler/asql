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
    this.availableTables = [];  // Available tables from schema
    this.initialized = false;
    this.initializing = false;  // Prevent double init
    this._initPromise = null;   // Store the init promise for awaiting
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
    // If already initialized, return immediately
    if (this.initialized) return;
    
    // If already initializing, return the existing promise
    if (this.initializing && this._initPromise) {
      return this._initPromise;
    }
    
    this.initializing = true;
    this._initPromise = this._doInit();
    return this._initPromise;
  }
  
  async _doInit() {
    try {
      // Load operation metadata and available tables in parallel
      // Wrap tables fetch in catch so it doesn't fail the whole init
      const [opsResponse, tablesResponse] = await Promise.all([
        fetch('/api/visual/operations'),
        fetch('/api/schema/tables').catch(err => {
          console.warn('Failed to load tables:', err);
          return null;
        })
      ]);
      
      if (!opsResponse.ok) {
        console.error('Failed to load operations: HTTP', opsResponse.status);
        return;
      }
      const opsData = await opsResponse.json();
      this.operations = opsData.operations || [];

      // Store available tables
      if (tablesResponse && tablesResponse.ok) {
        const tablesData = await tablesResponse.json();
        this.availableTables = tablesData.tables || [];
      } else {
        this.availableTables = [];
      }

      // Load schemas for all operations
      await this.loadSchemas();

      // Setup event listeners
      this.setupEventListeners();

      this.initialized = true;
    } catch (error) {
      console.error('Failed to initialize visual editor:', error);
    } finally {
      this.initializing = false;
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
    // FROM table select (static one in template)
    const fromSelect = document.getElementById('from-table');
    if (fromSelect) {
      // Populate with available tables
      if (this.availableTables.length > 0) {
        fromSelect.innerHTML = `
          <option value="">select table...</option>
          ${this.availableTables.map(t => 
            `<option value="${this.escapeHtml(t)}">${this.escapeHtml(t)}</option>`
          ).join('')}
        `;
      }
      
      fromSelect.addEventListener('change', (e) => {
        this.query.from.table = e.target.value;
        this.notifyChange();
      });
    }

    // Add step dropdown (main one in header)
    const addBtn = document.getElementById('add-step-btn');
    if (addBtn && addBtn.tagName === 'SELECT') {
      this.populateAddStepDropdown(addBtn);
      addBtn.addEventListener('change', (e) => {
        if (e.target.value) {
          this.addTransform(e.target.value);
          e.target.selectedIndex = 0;
        }
      });
    }

    // Add pipeline button
    const addPipelineBtn = document.getElementById('add-pipeline-btn');
    if (addPipelineBtn) {
      addPipelineBtn.addEventListener('click', () => this.addPipeline());
    }
  }

  // Populate an add-step dropdown with operation options
  populateAddStepDropdown(select) {
    // Keep the first option (placeholder) if it exists
    while (select.options.length > 1) {
      select.remove(1);
    }
    
    this.operations.forEach(op => {
      const opt = document.createElement('option');
      opt.value = op.type;
      opt.textContent = op.label || op.type;
      opt.title = op.description || '';
      select.appendChild(opt);
    });
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
      
      const currentTable = pipeline.from?.table || '';
      
      // Build table select options
      const tableSelectOptions = this.availableTables.length > 0
        ? `<option value="">select table...</option>
           ${this.availableTables.map(t => 
             `<option value="${this.escapeHtml(t)}" ${currentTable === t ? 'selected' : ''}>${this.escapeHtml(t)}</option>`
           ).join('')}`
        : `<option value="${this.escapeHtml(currentTable)}">${this.escapeHtml(currentTable) || 'enter table name'}</option>`;
      
      let fromHtml = `
        <div class="block-body">
          <span class="value-operator">from</span>
          <select class="pipeline-from-select" data-pipeline-index="${pipelineIdx}">
            ${tableSelectOptions}
          </select>
        </div>
      `;
      
      // Add output columns for FROM if present
      if (pipeline.from?.output_columns && pipeline.from.output_columns.length > 0) {
        fromHtml += `<div class="output-columns">${this.renderOutputColumnsTable(pipeline.from.output_columns)}</div>`;
      }
      
      fromBlock.innerHTML = fromHtml;
      pipelineDiv.appendChild(fromBlock);

      // Transforms for this pipeline with insert points between
      (pipeline.transforms || []).forEach((transform, transformIdx) => {
        // Insert point before each transform
        const insertPoint = this.createInsertPoint(pipelineIdx, transformIdx);
        pipelineDiv.appendChild(insertPoint);
        
        const blockEl = this.createBlockElement(transform, pipelineIdx);
        pipelineDiv.appendChild(blockEl);
      });

      // Add step dropdown for this pipeline
      const addStepSelect = document.createElement('select');
      addStepSelect.className = 'add-step-dropdown';
      addStepSelect.dataset.pipelineIndex = pipelineIdx;
      
      // Placeholder option
      const placeholderOpt = document.createElement('option');
      placeholderOpt.value = '';
      placeholderOpt.textContent = '+ add step';
      placeholderOpt.disabled = true;
      placeholderOpt.selected = true;
      addStepSelect.appendChild(placeholderOpt);
      
      // Add operation options with descriptions as titles
      this.operations.forEach(op => {
        const opt = document.createElement('option');
        opt.value = op.type;
        opt.textContent = op.label || op.type;
        opt.title = op.description || '';
        addStepSelect.appendChild(opt);
      });
      
      addStepSelect.addEventListener('change', (e) => {
        if (e.target.value) {
          this.currentPipelineIndex = pipelineIdx;
          this.addTransform(e.target.value, pipelineIdx);
          // Reset to placeholder
          e.target.selectedIndex = 0;
        }
      });
      pipelineDiv.appendChild(addStepSelect);

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

  /**
   * Create an insert point between blocks
   */
  createInsertPoint(pipelineIdx, insertAtIndex) {
    const insertPoint = document.createElement('div');
    insertPoint.className = 'insert-point';
    insertPoint.dataset.pipelineIndex = pipelineIdx;
    insertPoint.dataset.insertIndex = insertAtIndex;
    
    const insertBtn = document.createElement('button');
    insertBtn.className = 'insert-btn';
    insertBtn.textContent = '+';
    insertBtn.title = 'Insert step here';
    
    // Create dropdown for operation selection
    const dropdown = document.createElement('div');
    dropdown.className = 'insert-dropdown';
    dropdown.style.display = 'none';
    
    this.operations.forEach(op => {
      const optBtn = document.createElement('button');
      optBtn.className = 'insert-option';
      optBtn.textContent = op.label || op.type;
      optBtn.title = op.description || '';
      optBtn.dataset.opType = op.type;
      dropdown.appendChild(optBtn);
    });
    
    insertPoint.appendChild(insertBtn);
    insertPoint.appendChild(dropdown);
    
    // Toggle dropdown on click
    insertBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isVisible = dropdown.style.display !== 'none';
      // Hide all other dropdowns
      document.querySelectorAll('.insert-dropdown').forEach(d => d.style.display = 'none');
      dropdown.style.display = isVisible ? 'none' : 'block';
    });
    
    // Handle option selection
    dropdown.addEventListener('click', (e) => {
      const opType = e.target.dataset.opType;
      if (opType) {
        this.insertTransformAt(opType, pipelineIdx, insertAtIndex);
        dropdown.style.display = 'none';
      }
    });
    
    return insertPoint;
  }

  /**
   * Insert a transform at a specific position
   */
  insertTransformAt(type, pipelineIdx, index) {
    const id = `t${this.nextTransformId++}`;
    const schema = this.schemas[type];
    
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
    
    // Insert at position
    if (!this.pipelines[pipelineIdx].transforms) {
      this.pipelines[pipelineIdx].transforms = [];
    }
    this.pipelines[pipelineIdx].transforms.splice(index, 0, transform);
    
    // Use renderAll if we have multiple pipelines, otherwise just render current
    if (this.pipelines.length > 1) {
      this.renderAll();
    } else {
      this.render();
    }
    this.notifyChange();
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

    // Add output columns if present
    if (transform.output_columns && transform.output_columns.length > 0) {
      const colsDiv = document.createElement('div');
      colsDiv.className = 'output-columns';
      colsDiv.innerHTML = this.renderOutputColumnsTable(transform.output_columns);
      block.appendChild(colsDiv);
    }

    return block;
  }

  /**
   * Render output columns as a table row
   */
  renderOutputColumnsTable(columns) {
    if (!columns || columns.length === 0) {
      return '<span class="no-schema-message">No columns</span>';
    }
    
    const headers = columns.map(col => {
      const name = typeof col === 'string' ? col : col.name;
      const type = typeof col === 'object' && col.type ? col.type : '';
      const typeSpan = type ? `<span class="col-type">${this.escapeHtml(type)}</span>` : '';
      return `<th>${this.escapeHtml(name)}${typeSpan}</th>`;
    }).join('');
    
    return `<table><tr>${headers}</tr></table>`;
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
          ${this.renderColumnInput(leftValue, 'column', { param: param.name, 'expr-part': 'left', 'transform-id': transform.id }, transform.id)}
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
    const isColumnType = param.type === 'column[]' || param.name === 'dimensions' || param.name === 'columns';
    // Use expression-style rendering (boxed, one per line) only for GROUP BY dimensions
    const useExpressionStyle = param.name === 'dimensions';
    
    // Helper to extract string value from item (could be object or string)
    const getItemValue = (item) => {
      if (typeof item === 'string') return item;
      if (item && typeof item === 'object') {
        // SELECT columns have name/expression, prefer expression for display
        return item.expression || item.name || '';
      }
      return '';
    };
    
    return `
      <div class="field">
        <label>${this.escapeHtml(param.label)}${param.required ? ' *' : ''}</label>
        ${param.help ? `<p class="help">${this.escapeHtml(param.help)}</p>` : ''}
        <div class="list-items ${useExpressionStyle ? 'dimension-items' : ''}" data-param="${param.name}" data-transform-id="${transform.id}">
          ${items.map((item, idx) => {
            if (useExpressionStyle) {
              return this.renderDimensionItem(getItemValue(item), idx, transform.id);
            }
            const itemValue = getItemValue(item);
            return `
            <div class="list-item">
              ${isColumnType 
                ? this.renderColumnInput(itemValue, param.placeholder || 'column', { 'list-index': idx }, transform.id)
                : `<input type="text"
                         class="input-field"
                         value="${this.escapeHtml(itemValue)}"
                         placeholder="${this.escapeHtml(param.placeholder || '')}"
                         data-list-index="${idx}">`
              }
              <button class="list-item-remove" data-list-index="${idx}">×</button>
            </div>
          `}).join('')}
          <button class="list-add-btn" data-param="${param.name}" data-transform-id="${transform.id}">
            + Add
          </button>
        </div>
      </div>
    `;
  }

  /**
   * Parse a dimension value to extract function and column
   * e.g., "month(date)" -> { func: "month", column: "date" }
   * e.g., "region" -> { func: null, column: "region" }
   */
  parseDimensionValue(value) {
    if (!value) return { func: null, column: '' };
    
    const match = value.match(/^(\w+)\((.+)\)$/);
    if (match) {
      return { func: match[1].toLowerCase(), column: match[2] };
    }
    return { func: null, column: value };
  }

  /**
   * Render a dimension/column item with optional function wrapper
   */
  renderDimensionItem(value, idx, transformId) {
    const { func, column } = this.parseDimensionValue(value);
    const hasFunc = !!func;
    // Common functions grouped by category
    const commonFunctions = [
      // Time functions
      { group: 'Time', funcs: ['year', 'quarter', 'month', 'week', 'day', 'hour'] },
      // String functions
      { group: 'Text', funcs: ['upper', 'lower', 'trim', 'length'] },
      // Math functions
      { group: 'Math', funcs: ['abs', 'round', 'floor', 'ceil'] },
    ];
    
    return `
      <div class="dimension-item ${hasFunc ? 'has-function' : ''}" data-list-index="${idx}">
        <span class="dimension-expr">
          <span class="dim-func-wrapper">
            <select class="input-field dim-function" data-list-index="${idx}" data-dim-field="function">
              <option value="" ${!hasFunc ? 'selected' : ''}></option>
              ${commonFunctions.map(group => `
                <optgroup label="${group.group}">
                  ${group.funcs.map(fn => `
                    <option value="${fn}" ${func === fn ? 'selected' : ''}>${fn}</option>
                  `).join('')}
                </optgroup>
              `).join('')}
            </select>
            <span class="dim-paren dim-open-paren">(</span>
          </span>
          ${this.renderColumnInput(column, 'column', { 'list-index': idx, 'dim-field': 'column' }, transformId)}
          <span class="dim-paren dim-close-paren">)</span>
        </span>
        <button class="list-item-remove" data-list-index="${idx}">×</button>
      </div>
    `;
  }

  renderAggregateListWidget(transform, param) {
    const aggregates = transform[param.name] ?? [];
    const allFunctions = param.functions || ['count', 'sum', 'avg', 'min', 'max', 'count_distinct'];
    // Functions that don't require a column (can use * or no arg)
    const noColumnFns = ['count'];

    return `
      <div class="field">
        <label>${this.escapeHtml(param.label)}</label>
        ${param.help ? `<p class="help">${this.escapeHtml(param.help)}</p>` : ''}
        <div class="aggregate-items" data-param="${param.name}" data-transform-id="${transform.id}">
          ${aggregates.map((agg, idx) => {
            const hasAlias = !!agg.alias;
            const defaultAlias = this.getDefaultAggregateAlias(transform, idx);
            // For COUNT with no column, use * as display value
            const isCountType = noColumnFns.includes(agg.function);
            const displayColumn = agg.column || (isCountType ? '*' : '');
            const colType = this.getColumnType(displayColumn === '*' ? null : displayColumn, transform.id);
            const availableFns = this.filterAggregatesByType(allFunctions, colType);
            const hasColumn = !!agg.column || isCountType; // COUNT always "has" a column (*)
            const showFunction = hasColumn || agg.function;
            
            return `
            <div class="aggregate-item ${hasAlias ? 'has-alias' : ''} ${showFunction ? 'has-column' : ''}">
              <span class="aggregate-expr">
                <span class="agg-func-wrapper">
                  <select class="input-field agg-function" 
                          data-agg-index="${idx}" 
                          data-agg-field="function">
                    ${availableFns.map(fn => `
                      <option value="${this.escapeHtml(fn)}" ${agg.function === fn ? 'selected' : ''}>
                        ${this.escapeHtml(this.getAggregateFunctionLabel(fn))}
                      </option>
                    `).join('')}
                  </select>
                  <span class="agg-paren">(</span>
                </span>
                ${this.renderColumnInput(displayColumn, isCountType ? '*' : 'column', { 'agg-index': idx, 'agg-field': 'column' }, transform.id)}
                <span class="agg-paren agg-close-paren">)</span>
              </span>
              <span class="agg-alias-wrapper" data-agg-index="${idx}" data-default-alias="${this.escapeHtml(defaultAlias)}">
                <span class="agg-as-toggle" data-agg-index="${idx}">as</span>
                <input type="text"
                       class="input-field agg-alias"
                       placeholder="${this.escapeHtml(defaultAlias || 'alias')}"
                       value="${this.escapeHtml(agg.alias || '')}"
                       data-agg-index="${idx}"
                       data-agg-field="alias">
              </span>
              <button class="list-item-remove" data-agg-index="${idx}">×</button>
            </div>
          `}).join('')}
          <button class="list-add-btn" data-param="${param.name}" data-transform-id="${transform.id}">
            + Add Aggregate
          </button>
        </div>
      </div>
    `;
  }

  /**
   * Find the pipeline index that contains a given transform ID.
   * Returns the index or -1 if not found.
   */
  findPipelineByTransformId(transformId) {
    if (!transformId) return -1;
    return this.pipelines.findIndex(p =>
      (p.transforms || []).some(t => t.id === transformId)
    );
  }

  /**
   * Get the type of a column from available columns
   */
  getColumnType(columnName, transformId, pipelineIndex = null) {
    if (!columnName) return null;
    
    // Resolve pipeline index - if not provided, try to find by transformId
    let idx = pipelineIndex !== null ? pipelineIndex : this.currentPipelineIndex;
    if (pipelineIndex === null && transformId) {
      const foundIdx = this.findPipelineByTransformId(transformId);
      if (foundIdx !== -1) idx = foundIdx;
    }
    const pipeline = this.pipelines[idx];
    if (!pipeline) return null;

    // Check FROM columns
    if (pipeline.from?.output_columns) {
      const col = pipeline.from.output_columns.find(c => 
        (typeof c === 'string' ? c : c.name) === columnName
      );
      if (col && typeof col === 'object' && col.type) {
        return col.type.toLowerCase();
      }
    }

    // Check transforms
    if (pipeline.transforms) {
      for (const transform of pipeline.transforms) {
        if (transform.id === transformId) break;
        if (transform.output_columns) {
          const col = transform.output_columns.find(c => 
            (typeof c === 'string' ? c : c.name) === columnName
          );
          if (col && typeof col === 'object' && col.type) {
            return col.type.toLowerCase();
          }
        }
      }
    }

    return null; // Unknown type
  }

  /**
   * Filter aggregate functions by column type
   */
  filterAggregatesByType(functions, colType) {
    if (!colType) return functions; // No type info, show all
    
    // Numeric types
    const numericTypes = ['int', 'integer', 'bigint', 'float', 'double', 'decimal', 'numeric', 'number', 'real'];
    const isNumeric = numericTypes.some(t => colType.includes(t));
    
    // Functions that work on any type
    const anyTypeFns = ['count', 'count_distinct', 'min', 'max', 'array_agg'];
    // Functions that require numeric types
    const numericFns = ['sum', 'avg', 'stddev', 'variance', 'median'];
    
    if (isNumeric) {
      return functions; // All functions work on numeric
    } else {
      // Non-numeric: filter out numeric-only functions
      return functions.filter(fn => anyTypeFns.includes(fn));
    }
  }

  /**
   * Get the default alias for an aggregate from output_columns
   */
  getDefaultAggregateAlias(transform, aggIndex) {
    if (!transform.output_columns) return '';
    
    // Output columns after dimensions are the aggregates
    const dimensions = transform.dimensions || [];
    const aggOutputIdx = dimensions.length + aggIndex;
    
    if (aggOutputIdx < transform.output_columns.length) {
      const col = transform.output_columns[aggOutputIdx];
      return typeof col === 'string' ? col : col.name || '';
    }
    return '';
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
              ${this.renderColumnInput(expr.column, 'column', { 'order-index': idx, 'order-field': 'column' }, transform.id)}
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

  /**
   * Get available columns for a given transform based on:
   * - FROM table output_columns (if schema available)
   * - Previous transforms' output_columns
   */
  getAvailableColumns(transformId, pipelineIndex = null) {
    // Resolve pipeline index - if not provided, try to find by transformId
    let idx = pipelineIndex !== null ? pipelineIndex : this.currentPipelineIndex;
    if (pipelineIndex === null && transformId) {
      const foundIdx = this.findPipelineByTransformId(transformId);
      if (foundIdx !== -1) idx = foundIdx;
    }
    const pipeline = this.pipelines[idx];
    if (!pipeline) return [];

    const columns = new Set();

    // Get columns from FROM clause
    if (pipeline.from?.output_columns) {
      pipeline.from.output_columns.forEach(col => {
        const name = typeof col === 'string' ? col : col.name;
        if (name) columns.add(name);
      });
    }

    // Get columns from transforms before this one
    if (pipeline.transforms) {
      for (const transform of pipeline.transforms) {
        if (transform.id === transformId) break; // Stop at current transform
        
        if (transform.output_columns) {
          transform.output_columns.forEach(col => {
            const name = typeof col === 'string' ? col : col.name;
            if (name) columns.add(name);
          });
        }
        
        // Also add any aliases defined in this transform
        if (transform.type === 'select' && transform.columns) {
          transform.columns.forEach(col => {
            if (typeof col === 'object' && col.name) columns.add(col.name);
          });
        }
        if (transform.type === 'group_by') {
          (transform.dimensions || []).forEach(d => columns.add(d));
          (transform.aggregates || []).forEach(a => {
            if (a.alias) columns.add(a.alias);
          });
        }
        if (transform.type === 'extend' && transform.columns) {
          transform.columns.forEach(col => {
            if (typeof col === 'object' && col.alias) columns.add(col.alias);
          });
        }
      }
    }

    return Array.from(columns).sort();
  }

  /**
   * Render a column input with autocomplete
   */
  renderColumnInput(value, placeholder, dataAttrs, transformId) {
    const columns = this.getAvailableColumns(transformId);
    const datalistId = `columns-${transformId}-${Math.random().toString(36).substr(2, 9)}`;
    
    const attrsStr = Object.entries(dataAttrs)
      .map(([k, v]) => `data-${k}="${this.escapeHtml(String(v))}"`)
      .join(' ');
    
    // If we have known columns, use datalist for autocomplete
    if (columns.length > 0) {
      return `
        <input type="text"
               class="input-field column-autocomplete"
               list="${datalistId}"
               placeholder="${this.escapeHtml(placeholder)}"
               value="${this.escapeHtml(value || '')}"
               ${attrsStr}>
        <datalist id="${datalistId}">
          ${columns.map(col => `<option value="${this.escapeHtml(col)}">`).join('')}
        </datalist>
      `;
    }
    
    // Fallback to regular input
    return `
      <input type="text"
             class="input-field"
             placeholder="${this.escapeHtml(placeholder)}"
             value="${this.escapeHtml(value || '')}"
             ${attrsStr}>
    `;
  }

  /**
   * Get display label for aggregate function
   */
  getAggregateFunctionLabel(fn) {
    const labels = {
      'count_distinct': 'Unique',
      'stddev': 'Std Dev',
    };
    return labels[fn] || fn.charAt(0).toUpperCase() + fn.slice(1);
  }

  escapeHtml(text) {
    if (text === null || text === undefined) return '';
    // Handle objects - extract useful string value
    if (typeof text === 'object') {
      text = text.expression || text.name || text.value || String(text);
    }
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
  
  // Handle pipeline FROM select (handled in change event)
  if (target.classList.contains('pipeline-from-select')) {
    return; // Handled by change event
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
  
  // Check if this is a dimension with function wrapper
  const dimField = target.dataset.dimField;
  if (dimField) {
    const currentValue = items[index] || '';
    const { func: currentFunc, column: currentColumn } = visualEditor.parseDimensionValue(currentValue);
    
    if (dimField === 'function') {
      const newFunc = target.value;
      const dimItem = target.closest('.dimension-item');
      
      if (newFunc) {
        items[index] = `${newFunc}(${currentColumn})`;
        if (dimItem) dimItem.classList.add('has-function');
      } else {
        items[index] = currentColumn;
        if (dimItem) dimItem.classList.remove('has-function');
      }
    } else if (dimField === 'column') {
      if (currentFunc) {
        items[index] = `${currentFunc}(${target.value})`;
      } else {
        items[index] = target.value;
      }
    }
  } else {
    items[index] = target.value;
  }
  
  transform[param] = items;
}

// Aggregate update handler
function handleAggregateUpdate(transform, param, target) {
  const aggregates = transform[param] || [];
  const index = parseInt(target.dataset.aggIndex);
  const field = target.dataset.aggField;
  const noColumnFns = ['count']; // Functions that don't require a column

  if (!aggregates[index]) {
    aggregates[index] = {};
  }

  aggregates[index][field] = target.value;
  transform[param] = aggregates;
  
  const aggItem = target.closest('.aggregate-item');
  if (!aggItem) return;
  
  // Update has-column class based on whether we need to show the function
  const hasColumn = !!aggregates[index].column;
  const currentFn = aggregates[index].function;
  const isCountType = noColumnFns.includes(currentFn);
  const showFunction = hasColumn || isCountType || currentFn;
  aggItem.classList.toggle('has-column', showFunction);
  
  // If column changed, update function dropdown options
  if (field === 'column' && hasColumn) {
    const funcSelect = aggItem.querySelector('.agg-function');
    if (funcSelect) {
      const colType = visualEditor.getColumnType(target.value, transform.id);
      // Get functions list from schema, with fallback
      const schema = visualEditor.schemas[transform.type];
      const aggParam = schema?.parameters?.find(p => p.name === param);
      const allFunctions = aggParam?.functions || ['count', 'sum', 'avg', 'min', 'max', 'count_distinct'];
      const availableFns = visualEditor.filterAggregatesByType(allFunctions, colType);
      
      // Update options
      funcSelect.innerHTML = availableFns.map(fn => `
        <option value="${visualEditor.escapeHtml(fn)}" ${currentFn === fn ? 'selected' : ''}>
          ${visualEditor.escapeHtml(visualEditor.getAggregateFunctionLabel(fn))}
        </option>
      `).join('');
      
      // If current function is not available for this type, set default
      if (!availableFns.includes(currentFn)) {
        funcSelect.value = availableFns[0] || 'count';
        aggregates[index].function = funcSelect.value;
      }
    }
  }
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
  // Close insert dropdowns when clicking outside
  if (!e.target.closest('.insert-point')) {
    document.querySelectorAll('.insert-dropdown').forEach(d => d.style.display = 'none');
  }
  
  if (!visualEditor || !visualEditor.initialized) return;

  const target = e.target;

  // List add button
  if (target.classList.contains('list-add-btn')) {
    const transformId = target.dataset.transformId;
    const param = target.dataset.param;
    const transform = visualEditor.query.transforms.find(t => t.id === transformId);

    if (transform) {
      if (param === 'aggregates') {
        // Add aggregate - default to count(*) 
        if (!transform[param]) transform[param] = [];
        transform[param].push({ function: 'count', column: '*', alias: '' });
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

  // "as" toggle for aggregates - toggle alias visibility
  if (target.classList.contains('agg-as-toggle')) {
    const aggItem = target.closest('.aggregate-item');
    const wrapper = target.closest('.agg-alias-wrapper');
    const aliasInput = aggItem?.querySelector('.agg-alias');
    
    if (aggItem && aliasInput) {
      const hasAlias = aggItem.classList.toggle('has-alias');
      
      if (hasAlias) {
        // If toggling on and no value, use default alias
        if (!aliasInput.value && wrapper?.dataset.defaultAlias) {
          aliasInput.value = wrapper.dataset.defaultAlias;
          // Trigger input event to save the value
          aliasInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
        // Focus the input
        setTimeout(() => aliasInput.focus(), 50);
      } else {
        // If toggling off, clear the alias
        aliasInput.value = '';
        aliasInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
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

// Change event delegation for select elements (set operations, dimension functions)
document.addEventListener('change', (e) => {
  if (!visualEditor || !visualEditor.initialized) return;

  const target = e.target;

  // Handle pipeline FROM select
  if (target.classList.contains('pipeline-from-select')) {
    const pipelineIndex = parseInt(target.dataset.pipelineIndex);
    if (!isNaN(pipelineIndex) && visualEditor.pipelines[pipelineIndex]) {
      visualEditor.pipelines[pipelineIndex].from.table = target.value;
      visualEditor.notifyChange();
    }
    return;
  }
  
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
    return;
  }
  
  // Handle dimension function select
  if (target.classList.contains('dim-function')) {
    const container = target.closest('[data-param][data-transform-id]');
    if (!container) return;
    
    const transformId = container.dataset.transformId;
    const param = container.dataset.param;
    const index = parseInt(target.dataset.listIndex);
    
    // Find transform
    let transform = null;
    for (const pipeline of visualEditor.pipelines) {
      transform = pipeline.transforms.find(t => t.id === transformId);
      if (transform) break;
    }
    
    if (!transform || !transform[param]) return;
    
    const items = transform[param];
    const currentValue = items[index] || '';
    const { func: currentFunc, column: currentColumn } = visualEditor.parseDimensionValue(currentValue);
    const newFunc = target.value;
    const dimItem = target.closest('.dimension-item');
    
    if (newFunc) {
      items[index] = `${newFunc}(${currentColumn})`;
      if (dimItem) dimItem.classList.add('has-function');
    } else {
      items[index] = currentColumn;
      if (dimItem) dimItem.classList.remove('has-function');
    }
    
    visualEditor.notifyChange();
  }
});
