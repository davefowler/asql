/**
 * Visual ASQL Editor v2 - Complete rewrite with recursive expressions
 * 
 * Features:
 * - Recursive expression builder with hover-to-expand
 * - SortableJS for drag-and-drop reordering
 * - Metadata-driven UI generation
 * - Both blocky and text style modes via CSS
 */

class VisualEditorV2 {
  constructor() {
    // Pipeline data
    this.pipelines = [{
      name: null,
      from: { table: '' },
      transforms: []
    }];
    this.currentPipelineIndex = 0;
    
    // Metadata
    this.metadata = {
      operators: {},
      joins: {},
      aggregates: {},
      functions: {},
      transforms: {},
      time_units: [],
      data_types: []
    };
    this.availableTables = [];
    this.schemas = {};
    
    // State
    this.initialized = false;
    this.nextTransformId = 0;
    this.expressionInstances = new Map(); // Track Expression instances
    this.sortableInstances = new Map(); // Track SortableList instances
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

  /**
   * Initialize the editor
   */
  async init() {
    if (this.initialized) return;

    try {
      // Load metadata and tables in parallel
      const [metadataRes, tablesRes] = await Promise.all([
        fetch('/api/visual/metadata').catch(() => null),
        fetch('/api/schema/tables').catch(() => null)
      ]);

      if (metadataRes && metadataRes.ok) {
        this.metadata = await metadataRes.json();
      }

      if (tablesRes && tablesRes.ok) {
        const data = await tablesRes.json();
        this.availableTables = data.tables || [];
      }

      // Load transform schemas
      await this.loadSchemas();

      this.initialized = true;
      this.renderAll();
    } catch (error) {
      console.error('Failed to initialize visual editor:', error);
    }
  }

  /**
   * Load schemas for all transforms
   */
  async loadSchemas() {
    const transforms = this.metadata.transforms || {};
    
    for (const [type, info] of Object.entries(transforms)) {
      if (info.parameters) {
        this.schemas[type] = {
          type,
          label: info.label,
          description: info.description,
          category: info.category,
          parameters: info.parameters
        };
      }
    }
  }

  /**
   * Render all pipelines
   */
  renderAll() {
    // Use the parent .visual-editor container, not just transforms-container
    // This allows v2 to take over the full visual editor area
    let container = document.getElementById('transforms-container');
    if (!container) return;

    // Clean up old instances
    this.cleanup();
    container.innerHTML = '';

    // Hide the static HTML elements that conflict with v2
    this.hideStaticElements();

    this.pipelines.forEach((pipeline, pipelineIdx) => {
      const pipelineEl = this.renderPipeline(pipeline, pipelineIdx);
      container.appendChild(pipelineEl);

      // Add set operation between pipelines
      if (pipelineIdx < this.pipelines.length - 1) {
        container.appendChild(this.renderSetOperation(pipelineIdx));
      }
    });

    // Add pipeline button
    container.appendChild(this.renderAddPipelineButton());
  }

  /**
   * Hide static HTML elements that conflict with v2's rendering
   */
  hideStaticElements() {
    // Hide the static FROM block (v2 renders its own)
    // The static block has class "block from-block"
    const staticFromBlock = document.querySelector('#visual-editor-container > .visual-editor > .block.from-block');
    if (staticFromBlock) {
      staticFromBlock.style.display = 'none';
    }

    // Hide the static add-step dropdown (v2 renders its own)
    const staticAddStep = document.getElementById('add-step-btn');
    if (staticAddStep) {
      staticAddStep.style.display = 'none';
    }
  }

  /**
   * Render a single pipeline
   */
  renderPipeline(pipeline, pipelineIdx) {
    const div = document.createElement('div');
    div.className = 'pipeline-block input-pipeline';
    div.dataset.pipelineIndex = pipelineIdx;

    // Remove button (if multiple pipelines)
    if (this.pipelines.length > 1) {
      const removeBtn = document.createElement('button');
      removeBtn.className = 'pipeline-remove-btn';
      removeBtn.textContent = '×';
      removeBtn.title = 'Remove pipeline';
      removeBtn.addEventListener('click', () => this.removePipeline(pipelineIdx));
      div.appendChild(removeBtn);
    }

    // FROM block
    div.appendChild(this.renderFromBlock(pipeline, pipelineIdx));

    // Transforms as sortable list
    div.appendChild(this.renderTransformsList(pipeline, pipelineIdx));

    // Add step dropdown
    div.appendChild(this.renderAddStepDropdown(pipelineIdx));

    return div;
  }

  /**
   * Render FROM block using the same schema-driven approach as transforms
   */
  renderFromBlock(pipeline, pipelineIdx) {
    const schema = this.schemas['from'];
    
    // Ensure pipeline.from exists
    if (!pipeline.from) {
      pipeline.from = { table: '' };
    }
    
    // Create a transform-like object for the schema-driven renderer
    const fromTransform = {
      type: 'from',
      id: `from-${pipelineIdx}`,
      ...pipeline.from
    };

    const block = document.createElement('div');
    block.className = 'block from-block transform-block';
    block.dataset.id = fromTransform.id;
    block.dataset.pipelineIndex = pipelineIdx;

    // No drag handle for from (not sortable per schema)
    const isSortable = schema?.sortable !== false;
    if (isSortable) {
      const handle = document.createElement('span');
      handle.className = 'block-drag-handle';
      handle.innerHTML = '⋮⋮';
      handle.title = 'Drag to reorder';
      block.appendChild(handle);
    }

    // Body with keyword and parameters
    const body = document.createElement('div');
    body.className = 'block-body';

    // Keyword
    const keyword = document.createElement('span');
    keyword.className = 'value-operator';
    keyword.textContent = schema?.label?.toLowerCase() || 'from';
    body.appendChild(keyword);

    // Parameters from schema
    if (schema?.parameters) {
      schema.parameters.forEach(param => {
        // Link changes back to pipeline.from
        const paramProxy = new Proxy(fromTransform, {
          set: (obj, prop, value) => {
            obj[prop] = value;
            pipeline.from[prop] = value;
            return true;
          }
        });
        body.appendChild(this.renderParameter(paramProxy, param, pipelineIdx));
      });
    } else {
      // Fallback if no schema - render basic table select
      body.appendChild(this.renderTableSelect(pipeline.from, { name: 'table' }, pipelineIdx));
    }

    block.appendChild(body);

    // No delete button for from (not deletable per schema)
    const isDeletable = schema?.deletable !== false;
    if (isDeletable) {
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'block-delete';
      deleteBtn.textContent = '×';
      deleteBtn.title = 'Remove step';
      block.appendChild(deleteBtn);
    }

    // Output columns if available (will be populated by backend during transpile)
    if (pipeline.from?.output_columns) {
      block.appendChild(this.renderOutputColumns(pipeline.from.output_columns));
    }

    return block;
  }

  /**
   * Render transforms list with SortableJS
   */
  renderTransformsList(pipeline, pipelineIdx) {
    const container = document.createElement('div');
    container.className = 'transforms-list';

    (pipeline.transforms || []).forEach((transform, transformIdx) => {
      const blockEl = this.renderTransformBlock(transform, pipelineIdx, transformIdx);
      container.appendChild(blockEl);
    });

    // Initialize SortableJS on the container
    if (typeof Sortable !== 'undefined') {
      const sortable = new Sortable(container, {
        animation: 150,
        handle: '.block-drag-handle',
        ghostClass: 'block-ghost',
        onEnd: (evt) => {
          const { oldIndex, newIndex } = evt;
          if (oldIndex !== newIndex) {
            const transforms = pipeline.transforms || [];
            const item = transforms.splice(oldIndex, 1)[0];
            transforms.splice(newIndex, 0, item);
            this.notifyChange();
          }
        }
      });
      this.sortableInstances.set(`pipeline-${pipelineIdx}`, sortable);
    }

    return container;
  }

  /**
   * Render a single transform block
   */
  renderTransformBlock(transform, pipelineIdx, transformIdx) {
    const schema = this.schemas[transform.type];
    if (!schema) {
      return this.renderErrorBlock(transform, 'Unknown transform type');
    }

    const block = document.createElement('div');
    block.className = `block transform-block ${transform.type}-block`;
    block.dataset.id = transform.id;
    block.dataset.pipelineIndex = pipelineIdx;

    // Drag handle
    const handle = document.createElement('span');
    handle.className = 'block-drag-handle';
    handle.innerHTML = '⋮⋮';
    handle.title = 'Drag to reorder';
    block.appendChild(handle);

    // Body with keyword and parameters
    const body = document.createElement('div');
    body.className = 'block-body';

    // Keyword
    const keyword = document.createElement('span');
    keyword.className = 'value-operator';
    keyword.textContent = schema.label?.toLowerCase() || transform.type;
    body.appendChild(keyword);

    // Parameters
    if (schema.parameters) {
      schema.parameters.forEach(param => {
        body.appendChild(this.renderParameter(transform, param, pipelineIdx));
      });
    }

    block.appendChild(body);

    // Delete button
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'block-delete';
    deleteBtn.textContent = '×';
    deleteBtn.title = 'Remove step';
    deleteBtn.addEventListener('click', () => {
      this.removeTransform(transform.id, pipelineIdx);
    });
    block.appendChild(deleteBtn);

    // Output columns if available
    if (transform.output_columns) {
      block.appendChild(this.renderOutputColumns(transform.output_columns));
    }

    return block;
  }

  /**
   * Render a parameter based on its type
   */
  renderParameter(transform, param, pipelineIdx) {
    const container = document.createElement('span');
    container.className = 'param-container';

    const widget = param.widget || 'text';
    
    switch (widget) {
      case 'text':
        container.appendChild(this.renderTextInput(transform, param));
        break;
      case 'number':
        container.appendChild(this.renderNumberInput(transform, param));
        break;
      case 'dropdown':
        container.appendChild(this.renderDropdown(transform, param));
        break;
      case 'expression':
        container.appendChild(this.renderExpressionWidget(transform, param, pipelineIdx));
        break;
      case 'list':
        container.appendChild(this.renderListWidget(transform, param, pipelineIdx));
        break;
      case 'aggregate_list':
        container.appendChild(this.renderAggregateList(transform, param, pipelineIdx));
        break;
      case 'order_list':
        container.appendChild(this.renderOrderList(transform, param, pipelineIdx));
        break;
      case 'table_select':
        container.appendChild(this.renderTableSelect(transform, param, pipelineIdx));
        break;
      default:
        container.textContent = `[${widget}]`;
    }

    return container;
  }

  /**
   * Render table select dropdown
   */
  renderTableSelect(transform, param, pipelineIdx) {
    const select = document.createElement('select');
    select.className = 'inline-select table-select';

    const emptyOpt = document.createElement('option');
    emptyOpt.value = '';
    emptyOpt.textContent = 'select table...';
    select.appendChild(emptyOpt);

    this.availableTables.forEach(table => {
      const opt = document.createElement('option');
      opt.value = table;
      opt.textContent = table;
      opt.selected = transform[param.name] === table;
      select.appendChild(opt);
    });

    select.addEventListener('change', (e) => {
      transform[param.name] = e.target.value;
      this.notifyChange();
    });

    return select;
  }

  /**
   * Render text input
   */
  renderTextInput(transform, param) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'inline-input';
    input.value = transform[param.name] || '';
    input.placeholder = param.placeholder || param.name;
    input.addEventListener('input', (e) => {
      transform[param.name] = e.target.value;
      this.notifyChange();
    });
    return input;
  }

  /**
   * Render number input
   */
  renderNumberInput(transform, param) {
    const input = document.createElement('input');
    input.type = 'number';
    input.className = 'inline-input';
    input.value = transform[param.name] ?? '';
    if (param.min !== undefined) input.min = param.min;
    if (param.max !== undefined) input.max = param.max;
    input.addEventListener('input', (e) => {
      transform[param.name] = parseInt(e.target.value, 10) || 0;
      this.notifyChange();
    });
    return input;
  }

  /**
   * Render dropdown select
   */
  renderDropdown(transform, param) {
    const select = document.createElement('select');
    select.className = 'inline-select';
    
    (param.options || []).forEach(opt => {
      const option = document.createElement('option');
      option.value = opt.value;
      option.textContent = opt.label;
      option.selected = transform[param.name] === opt.value;
      select.appendChild(option);
    });

    select.addEventListener('change', (e) => {
      transform[param.name] = e.target.value;
      this.notifyChange();
    });

    return select;
  }

  /**
   * Render expression widget (single expression)
   */
  renderExpressionWidget(transform, param, pipelineIdx) {
    const value = transform[param.name] || {};
    const exprId = `${transform.id}-${param.name}`;
    
    const expr = new Expression({
      value,
      id: exprId,
      showAlias: false,
      functionCategories: ['date', 'string', 'math', 'conditional'],
      onChange: (newValue) => {
        transform[param.name] = newValue;
        this.notifyChange();
      },
      metadata: this.metadata,
      schema: this.getSchemaContext(pipelineIdx)
    });

    this.expressionInstances.set(exprId, expr);
    return expr.render();
  }

  /**
   * Render list widget (columns, expressions)
   */
  renderListWidget(transform, param, pipelineIdx) {
    const items = transform[param.name] || [];
    const isExpressionType = param.type === 'expression[]' || 
                            param.name === 'columns' || 
                            param.name === 'dimensions';
    const showAlias = param.name === 'columns' && transform.type === 'select';
    
    const container = document.createElement('div');
    container.className = 'expression-list';

    items.forEach((item, idx) => {
      const itemEl = this.renderExpressionItem(item, idx, transform, param, pipelineIdx, showAlias);
      container.appendChild(itemEl);
    });

    // Add button
    const addBtn = document.createElement('button');
    addBtn.className = 'list-add-btn';
    addBtn.textContent = '+ Add';
    addBtn.addEventListener('click', () => {
      const newItem = showAlias ? { expression: '', name: '' } : '';
      items.push(newItem);
      transform[param.name] = items;
      this.renderAll();
      this.notifyChange();
    });
    container.appendChild(addBtn);

    // Make sortable
    if (typeof Sortable !== 'undefined') {
      const sortableId = `${transform.id}-${param.name}`;
      setTimeout(() => {
        const sortable = new Sortable(container, {
          animation: 150,
          handle: '.expr-drag-handle',
          ghostClass: 'expr-ghost',
          draggable: '.expression-item',
          onEnd: (evt) => {
            const { oldIndex, newIndex } = evt;
            if (oldIndex !== newIndex) {
              const item = items.splice(oldIndex, 1)[0];
              items.splice(newIndex, 0, item);
              transform[param.name] = items;
              this.notifyChange();
            }
          }
        });
        this.sortableInstances.set(sortableId, sortable);
      }, 0);
    }

    return container;
  }

  /**
   * Render a single expression item in a list
   */
  renderExpressionItem(item, idx, transform, param, pipelineIdx, showAlias) {
    const wrapper = document.createElement('div');
    wrapper.className = 'expression-item';
    wrapper.dataset.index = idx;

    // Drag handle
    const handle = document.createElement('span');
    handle.className = 'expr-drag-handle';
    handle.innerHTML = '⋮⋮';
    wrapper.appendChild(handle);

    // Expression
    const exprId = `${transform.id}-${param.name}-${idx}`;
    const expr = new Expression({
      value: item,
      id: exprId,
      showAlias,
      functionCategories: this.getFunctionCategoriesForParam(param, transform.type),
      onChange: (newValue) => {
        const items = transform[param.name] || [];
        items[idx] = newValue;
        transform[param.name] = items;
        this.notifyChange();
      },
      metadata: this.metadata,
      schema: this.getSchemaContext(pipelineIdx)
    });

    this.expressionInstances.set(exprId, expr);
    wrapper.appendChild(expr.render());

    // Remove button
    const removeBtn = document.createElement('button');
    removeBtn.className = 'expr-remove';
    removeBtn.textContent = '×';
    removeBtn.addEventListener('click', () => {
      const items = transform[param.name] || [];
      items.splice(idx, 1);
      transform[param.name] = items;
      this.renderAll();
      this.notifyChange();
    });
    wrapper.appendChild(removeBtn);

    return wrapper;
  }

  /**
   * Render aggregate list widget
   */
  renderAggregateList(transform, param, pipelineIdx) {
    const items = transform[param.name] || [];
    const aggregates = this.metadata.aggregates || {};
    
    const container = document.createElement('div');
    container.className = 'aggregate-list';

    items.forEach((item, idx) => {
      const itemEl = this.renderAggregateItem(item, idx, transform, param, pipelineIdx, aggregates);
      container.appendChild(itemEl);
    });

    // Add button
    const addBtn = document.createElement('button');
    addBtn.className = 'list-add-btn';
    addBtn.textContent = '+ Add Aggregate';
    addBtn.addEventListener('click', () => {
      items.push({ function: 'count', column: '', alias: '' });
      transform[param.name] = items;
      this.renderAll();
      this.notifyChange();
    });
    container.appendChild(addBtn);

    return container;
  }

  /**
   * Render a single aggregate item
   */
  renderAggregateItem(item, idx, transform, param, pipelineIdx, aggregates) {
    const wrapper = document.createElement('div');
    wrapper.className = `aggregate-item ${item.alias ? 'has-alias' : ''}`;
    wrapper.dataset.index = idx;

    // Drag handle
    const handle = document.createElement('span');
    handle.className = 'expr-drag-handle';
    handle.innerHTML = '⋮⋮';
    wrapper.appendChild(handle);

    // Function select
    const funcSelect = document.createElement('select');
    funcSelect.className = 'agg-function';
    
    Object.entries(aggregates).forEach(([key, info]) => {
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = info.label || key;
      opt.selected = item.function === key;
      funcSelect.appendChild(opt);
    });

    funcSelect.addEventListener('change', (e) => {
      item.function = e.target.value;
      this.notifyChange();
    });

    const expr = document.createElement('span');
    expr.className = 'aggregate-expr';
    expr.appendChild(funcSelect);

    // Open paren
    const openParen = document.createElement('span');
    openParen.className = 'agg-paren';
    openParen.textContent = '(';
    expr.appendChild(openParen);

    // Column input
    const colInput = document.createElement('input');
    colInput.type = 'text';
    colInput.className = 'column-autocomplete';
    colInput.value = item.column || (item.function === 'count' ? '*' : '');
    colInput.placeholder = item.function === 'count' ? '*' : 'column';
    colInput.addEventListener('input', (e) => {
      item.column = e.target.value === '*' ? '' : e.target.value;
      this.notifyChange();
    });
    expr.appendChild(colInput);

    // Close paren
    const closeParen = document.createElement('span');
    closeParen.className = 'agg-paren';
    closeParen.textContent = ')';
    expr.appendChild(closeParen);

    wrapper.appendChild(expr);

    // Alias
    const aliasContainer = document.createElement('span');
    aliasContainer.className = 'agg-alias-container';

    const asToggle = document.createElement('span');
    asToggle.className = 'agg-as-toggle';
    asToggle.textContent = 'as';
    asToggle.addEventListener('click', () => {
      wrapper.classList.toggle('has-alias');
      if (!item.alias) {
        item.alias = `${item.function}_${item.column || 'all'}`;
      }
      this.notifyChange();
    });
    aliasContainer.appendChild(asToggle);

    const aliasInput = document.createElement('input');
    aliasInput.type = 'text';
    aliasInput.className = 'agg-alias';
    aliasInput.value = item.alias || '';
    aliasInput.placeholder = `${item.function}_${item.column || 'all'}`;
    aliasInput.addEventListener('input', (e) => {
      item.alias = e.target.value;
      this.notifyChange();
    });
    aliasContainer.appendChild(aliasInput);

    wrapper.appendChild(aliasContainer);

    // Remove button
    const removeBtn = document.createElement('button');
    removeBtn.className = 'expr-remove';
    removeBtn.textContent = '×';
    removeBtn.addEventListener('click', () => {
      const items = transform[param.name] || [];
      items.splice(idx, 1);
      transform[param.name] = items;
      this.renderAll();
      this.notifyChange();
    });
    wrapper.appendChild(removeBtn);

    return wrapper;
  }

  /**
   * Render order by list
   */
  renderOrderList(transform, param, pipelineIdx) {
    const items = transform[param.name] || [];
    
    const container = document.createElement('div');
    container.className = 'order-list';

    items.forEach((item, idx) => {
      const itemEl = this.renderOrderItem(item, idx, transform, param, pipelineIdx);
      container.appendChild(itemEl);
    });

    // Add button
    const addBtn = document.createElement('button');
    addBtn.className = 'list-add-btn';
    addBtn.textContent = '+ Add';
    addBtn.addEventListener('click', () => {
      items.push({ column: '', direction: 'asc' });
      transform[param.name] = items;
      this.renderAll();
      this.notifyChange();
    });
    container.appendChild(addBtn);

    return container;
  }

  /**
   * Render order by item
   */
  renderOrderItem(item, idx, transform, param, pipelineIdx) {
    const wrapper = document.createElement('div');
    wrapper.className = 'order-item';
    wrapper.dataset.index = idx;

    // Drag handle
    const handle = document.createElement('span');
    handle.className = 'expr-drag-handle';
    handle.innerHTML = '⋮⋮';
    wrapper.appendChild(handle);

    // Column input
    const colInput = document.createElement('input');
    colInput.type = 'text';
    colInput.className = 'column-autocomplete';
    colInput.value = item.column || '';
    colInput.placeholder = 'column';
    colInput.addEventListener('input', (e) => {
      item.column = e.target.value;
      this.notifyChange();
    });
    wrapper.appendChild(colInput);

    // Direction toggle
    const dirBtn = document.createElement('button');
    dirBtn.className = `order-direction ${item.direction || 'asc'}`;
    dirBtn.textContent = item.direction === 'desc' ? '↓' : '↑';
    dirBtn.title = item.direction === 'desc' ? 'Descending' : 'Ascending';
    dirBtn.addEventListener('click', () => {
      item.direction = item.direction === 'desc' ? 'asc' : 'desc';
      dirBtn.textContent = item.direction === 'desc' ? '↓' : '↑';
      dirBtn.title = item.direction === 'desc' ? 'Descending' : 'Ascending';
      dirBtn.className = `order-direction ${item.direction}`;
      this.notifyChange();
    });
    wrapper.appendChild(dirBtn);

    // Remove button
    const removeBtn = document.createElement('button');
    removeBtn.className = 'expr-remove';
    removeBtn.textContent = '×';
    removeBtn.addEventListener('click', () => {
      const items = transform[param.name] || [];
      items.splice(idx, 1);
      transform[param.name] = items;
      this.renderAll();
      this.notifyChange();
    });
    wrapper.appendChild(removeBtn);

    return wrapper;
  }

  /**
   * Render output columns display
   */
  renderOutputColumns(columns) {
    if (!columns || columns.length === 0) return document.createElement('div');

    const container = document.createElement('div');
    container.className = 'output-columns';

    const table = document.createElement('table');
    const row = document.createElement('tr');

    columns.forEach(col => {
      const th = document.createElement('th');
      const name = typeof col === 'string' ? col : col.name;
      const type = typeof col === 'object' ? col.type : '';
      th.textContent = name;
      if (type) {
        const typeSpan = document.createElement('span');
        typeSpan.className = 'col-type';
        typeSpan.textContent = type;
        th.appendChild(typeSpan);
      }
      row.appendChild(th);
    });

    table.appendChild(row);
    container.appendChild(table);
    return container;
  }

  /**
   * Render add step dropdown
   */
  renderAddStepDropdown(pipelineIdx) {
    const select = document.createElement('select');
    select.className = 'add-step-dropdown';

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = '+ add step';
    placeholder.disabled = true;
    placeholder.selected = true;
    select.appendChild(placeholder);

    // Group transforms by category
    const transforms = this.metadata.transforms || {};
    const categories = {};
    
    Object.entries(transforms).forEach(([type, info]) => {
      const cat = info.category || 'other';
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push({ type, ...info });
    });

    Object.entries(categories).forEach(([cat, items]) => {
      const group = document.createElement('optgroup');
      group.label = cat.charAt(0).toUpperCase() + cat.slice(1);
      
      items.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item.type;
        opt.textContent = item.label || item.type;
        opt.title = item.description || '';
        group.appendChild(opt);
      });
      
      select.appendChild(group);
    });

    select.addEventListener('change', (e) => {
      if (e.target.value) {
        this.addTransform(e.target.value, pipelineIdx);
        e.target.selectedIndex = 0;
      }
    });

    return select;
  }

  /**
   * Render set operation between pipelines
   */
  renderSetOperation(pipelineIdx) {
    const pipeline = this.pipelines[pipelineIdx];
    const currentOp = pipeline.set_operation?.type || 'union';
    const isAll = pipeline.set_operation?.all || false;

    const container = document.createElement('div');
    container.className = 'set-operation-selector';

    const select = document.createElement('select');
    select.className = 'set-op-select';

    const options = [
      { value: 'union', label: 'UNION' },
      { value: 'union_all', label: 'UNION ALL' },
      { value: 'intersect', label: 'INTERSECT' },
      { value: 'except', label: 'EXCEPT' },
    ];

    options.forEach(opt => {
      const option = document.createElement('option');
      option.value = opt.value;
      option.textContent = opt.label;
      option.selected = (opt.value === 'union_all' && currentOp === 'union' && isAll) ||
                       (opt.value === currentOp && !isAll);
      select.appendChild(option);
    });

    select.addEventListener('change', (e) => {
      const val = e.target.value;
      pipeline.set_operation = {
        type: val === 'union_all' ? 'union' : val,
        all: val === 'union_all'
      };
      this.notifyChange();
    });

    container.appendChild(select);
    return container;
  }

  /**
   * Render add pipeline button
   */
  renderAddPipelineButton() {
    const container = document.createElement('div');
    container.className = 'add-pipeline-container';

    const btn = document.createElement('button');
    btn.className = 'add-pipeline-btn';
    btn.textContent = '+ Add Pipeline (CTE / Set Operation)';
    btn.addEventListener('click', () => this.addPipeline());

    container.appendChild(btn);
    return container;
  }

  /**
   * Render error block
   */
  renderErrorBlock(transform, message) {
    const block = document.createElement('div');
    block.className = 'block error-block';
    block.innerHTML = `<div class="block-body"><span class="error">${this.escapeHtml(message)}</span></div>`;
    return block;
  }

  /**
   * Add a new transform
   */
  addTransform(type, pipelineIdx = null) {
    const idx = pipelineIdx ?? this.currentPipelineIndex;
    const schema = this.schemas[type];
    const id = `t${this.nextTransformId++}`;

    const transform = { id, type };

    // Initialize with defaults
    if (schema?.parameters) {
      schema.parameters.forEach(param => {
        if (param.default !== undefined) {
          transform[param.name] = param.default;
        } else if (param.widget?.includes('list')) {
          transform[param.name] = [];
        }
      });
    }

    this.pipelines[idx].transforms.push(transform);
    this.renderAll();
    this.notifyChange();
  }

  /**
   * Remove a transform
   */
  removeTransform(id, pipelineIdx = null) {
    const idx = pipelineIdx ?? this.currentPipelineIndex;
    this.pipelines[idx].transforms = this.pipelines[idx].transforms.filter(t => t.id !== id);
    this.renderAll();
    this.notifyChange();
  }

  /**
   * Add a new pipeline
   */
  addPipeline() {
    // Add set operation to previous pipeline
    if (this.pipelines.length > 0) {
      this.pipelines[this.pipelines.length - 1].set_operation = { type: 'union', all: false };
    }

    this.pipelines.push({
      name: null,
      from: { table: '' },
      transforms: []
    });

    this.currentPipelineIndex = this.pipelines.length - 1;
    this.renderAll();
    this.notifyChange();
  }

  /**
   * Remove a pipeline
   */
  removePipeline(pipelineIdx) {
    if (this.pipelines.length <= 1) return;

    // Remove set operation from previous pipeline
    if (pipelineIdx > 0) {
      delete this.pipelines[pipelineIdx - 1].set_operation;
    }

    this.pipelines.splice(pipelineIdx, 1);
    if (this.currentPipelineIndex >= this.pipelines.length) {
      this.currentPipelineIndex = this.pipelines.length - 1;
    }

    this.renderAll();
    this.notifyChange();
  }

  /**
   * Get function categories for a parameter
   */
  getFunctionCategoriesForParam(param, transformType) {
    // Different transforms need different function categories
    const categories = {
      'group_by': { dimensions: ['date', 'string', 'math'], aggregates: ['aggregates'] },
      'select': { columns: ['date', 'string', 'math', 'aggregates'] },
      'where': { condition: ['date', 'string', 'math'] },
      'order_by': { expressions: ['date', 'string', 'math'] },
    };

    const config = categories[transformType];
    if (config && config[param.name]) {
      return config[param.name];
    }

    return ['date', 'string', 'math'];
  }

  /**
   * Get schema context for autocomplete
   */
  getSchemaContext(pipelineIdx) {
    // TODO: Get available columns based on FROM table and previous transforms
    return {
      columns: this.availableTables.length > 0 ? [] : []
    };
  }

  /**
   * Set query data (for loading saved queries)
   */
  async setQuery(data) {
    if (Array.isArray(data)) {
      this.pipelines = data;
    } else if (data && typeof data === 'object') {
      this.pipelines = [data];
    }
    
    // Ensure transform IDs exist
    this.pipelines.forEach(pipeline => {
      (pipeline.transforms || []).forEach(t => {
        if (!t.id) {
          t.id = `t${this.nextTransformId++}`;
        }
      });
    });

    this.renderAll();
  }

  /**
   * Get current query data
   */
  getQuery() {
    return this.pipelines.length === 1 ? this.pipelines[0] : this.pipelines;
  }

  /**
   * Load query from JSON object (API expected by playground.js)
   */
  async loadFromJSON(json) {
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

    // Ensure transform IDs exist
    this.pipelines.forEach(pipeline => {
      (pipeline.transforms || []).forEach(t => {
        if (!t.id) {
          t.id = `t${this.nextTransformId++}`;
        }
      });
    });

    this.renderAll();
  }

  /**
   * Load query from ASQL text (API expected by playground.js)
   */
  async loadFromASQL(asql) {
    if (!asql || !asql.trim()) {
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
        await this.loadFromJSON(data.query);
      } else {
        console.error('Failed to parse ASQL:', data.error);
      }
    } catch (error) {
      console.error('Error parsing ASQL:', error);
    }
  }

  /**
   * Get ASQL text from current query (API expected by playground.js)
   */
  async getASQL() {
    try {
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
        console.error('Failed to compile ASQL:', data.error);
        return '';
      }
    } catch (error) {
      console.error('Error compiling ASQL:', error);
      return '';
    }
  }

  /**
   * Notify listeners of changes
   */
  notifyChange() {
    const event = new CustomEvent('visual-editor-change', {
      detail: { query: this.getQuery() }
    });
    document.dispatchEvent(event);
  }

  /**
   * Clean up instances
   */
  cleanup() {
    this.expressionInstances.forEach(expr => {
      // Expression cleanup if needed
    });
    this.expressionInstances.clear();

    this.sortableInstances.forEach(sortable => {
      if (sortable.destroy) sortable.destroy();
    });
    this.sortableInstances.clear();
  }

  /**
   * Escape HTML special characters
   */
  escapeHtml(str) {
    if (typeof str !== 'string') return str;
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = VisualEditorV2;
}

// Global instance - v2 is now the default
let visualEditor = null;

document.addEventListener('DOMContentLoaded', () => {
  visualEditor = new VisualEditorV2();
  visualEditor.init();
});
