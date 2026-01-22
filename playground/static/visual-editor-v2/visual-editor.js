/**
 * Visual ASQL Editor v2 - Complete rewrite with recursive expressions
 *
 * ARCHITECTURE PRINCIPLES:
 * ========================
 * 1. THE UI IS "DUMB" - No business logic here. All smarts come from the backend.
 *    - Transform schemas/metadata come from /api/metadata
 *    - Column options come from output_columns populated by SQLGlot qualify
 *    - This component just RENDERS what it's told
 *
 * 2. STYLE MODES ARE CSS-ONLY (except Pipes mode)
 *    - Text mode (.visual-style-text) and Blocky mode (.visual-style-blocky)
 *      use the SAME rendering logic, just different CSS
 *    - Pipes mode (.visual-style-pipes) requires different DOM for node layout
 *
 * 3. COLUMN DROPDOWNS depend on output_columns from backend
 *    - Each transform should have output_columns populated by the backend
 *    - The backend uses SQLGlot's qualify() with the schema
 *    - If dropdowns show text inputs instead of selects, check output_columns
 *
 * 4. DON'T ADD UI LOGIC - If something looks wrong:
 *    - Check the metadata (transform schemas from /api/metadata)
 *    - Check output_columns on the transform (from /api/visual/transpile)
 *    - Fix the DATA, not the rendering code
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
   * Check if pipes style is active
   */
  isPipesMode() {
    const container = document.getElementById('visual-editor-container');
    return container && container.classList.contains('visual-style-pipes');
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

    // Check if pipes mode is active - if so, render pipes view
    if (this.isPipesMode()) {
      this.renderPipesMode(container);
      return;
    }

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
   * Render pipes mode view (Yahoo Pipes-style nodes)
   */
  renderPipesMode(container) {
    // Create pipes container with relative positioning for SVG overlay
    const pipesContainer = document.createElement('div');
    pipesContainer.className = 'pipes-nodes-container';

    // Build a map of CTE names for reference detection
    const cteNames = new Set();
    const cteNodeMap = new Map(); // Map CTE name -> node element
    this.pipelines.forEach(p => {
      if (p.name) cteNames.add(p.name.toLowerCase());
    });

    // Track CTE references for drawing connections
    const cteReferences = []; // Array of { sourceNode, targetCteName }

    // Render each pipeline as a node
    this.pipelines.forEach((pipeline, idx) => {
      const node = this.createPipeNode(pipeline, idx, this.pipelines.length, cteNames);
      node.dataset.cteName = pipeline.name || '';
      pipesContainer.appendChild(node);

      // Track CTE nodes by name for connection drawing
      if (pipeline.name) {
        cteNodeMap.set(pipeline.name.toLowerCase(), node);
      }

      // Track if this pipeline references another CTE
      const tableName = pipeline.from?.table || '';
      if (cteNames.has(tableName.toLowerCase()) && tableName.toLowerCase() !== pipeline.name?.toLowerCase()) {
        cteReferences.push({
          sourceNode: node,
          targetCteName: tableName.toLowerCase()
        });
      }

      // Add set operation connector between pipelines
      if (pipeline.set_operation && idx < this.pipelines.length - 1) {
        const setOpDiv = document.createElement('div');
        setOpDiv.className = 'pipe-set-operation';
        const opText = pipeline.set_operation.all
          ? `${pipeline.set_operation.type.toUpperCase()} ALL`
          : pipeline.set_operation.type.toUpperCase();
        setOpDiv.innerHTML = `<span class="pipe-set-op-badge">${opText}</span>`;
        pipesContainer.appendChild(setOpDiv);
      }
    });

    container.appendChild(pipesContainer);

    // Add pipeline button
    container.appendChild(this.renderAddPipelineButton());

    // Draw CTE connection lines after DOM is laid out
    if (cteReferences.length > 0) {
      setTimeout(() => {
        this.drawCteConnections(pipesContainer, cteReferences, cteNodeMap);
      }, 0);
    }
  }

  /**
   * Draw SVG connection lines between CTE references
   */
  drawCteConnections(container, references, cteNodeMap) {
    // Remove any existing SVG
    const existingSvg = container.querySelector('.cte-connections-svg');
    if (existingSvg) existingSvg.remove();

    // Create SVG overlay
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.classList.add('cte-connections-svg');
    svg.style.cssText = 'position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 0;';

    const containerRect = container.getBoundingClientRect();

    references.forEach(({ sourceNode, targetCteName }) => {
      const targetNode = cteNodeMap.get(targetCteName);
      if (!targetNode) return;

      const sourceRect = sourceNode.getBoundingClientRect();
      const targetRect = targetNode.getBoundingClientRect();

      // Calculate connection points relative to container
      // Source: left edge of the source node (the one that references the CTE)
      // Target: right edge of the target CTE node
      const sourceX = sourceRect.left - containerRect.left;
      const sourceY = sourceRect.top - containerRect.top + sourceRect.height / 2;

      const targetX = targetRect.right - containerRect.left;
      const targetY = targetRect.top - containerRect.top + targetRect.height / 2;

      // Create a curved path
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');

      // Bezier curve - curve out to the left then back
      const midX = Math.min(sourceX, targetX) - 30;
      const d = `M ${targetX} ${targetY} C ${midX} ${targetY}, ${midX} ${sourceY}, ${sourceX} ${sourceY}`;

      path.setAttribute('d', d);
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', 'var(--accent-color, #667eea)');
      path.setAttribute('stroke-width', '2');
      path.setAttribute('stroke-dasharray', '4,4');
      path.setAttribute('opacity', '0.6');

      // Add arrow marker at end
      const arrowId = `arrow-${Math.random().toString(36).substr(2, 9)}`;
      const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
      marker.setAttribute('id', arrowId);
      marker.setAttribute('markerWidth', '6');
      marker.setAttribute('markerHeight', '6');
      marker.setAttribute('refX', '5');
      marker.setAttribute('refY', '3');
      marker.setAttribute('orient', 'auto');

      const arrowPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      arrowPath.setAttribute('d', 'M0,0 L0,6 L6,3 z');
      arrowPath.setAttribute('fill', 'var(--accent-color, #667eea)');
      arrowPath.setAttribute('opacity', '0.6');

      marker.appendChild(arrowPath);
      defs.appendChild(marker);
      svg.appendChild(defs);

      path.setAttribute('marker-end', `url(#${arrowId})`);
      svg.appendChild(path);
    });

    // Insert SVG at the beginning of the container
    container.style.position = 'relative';
    container.insertBefore(svg, container.firstChild);
  }

  /**
   * Create a pipe node for a pipeline
   */
  createPipeNode(pipeline, idx, totalPipelines, cteNames) {
    const node = document.createElement('div');
    node.className = 'pipe-node';
    node.dataset.pipelineIndex = idx;

    // Determine node title and type
    const tableName = pipeline.from?.table || '';
    const isNamedCTE = !!pipeline.name;
    const nodeTitle = pipeline.name || tableName || `Query ${idx + 1}`;
    const nodeType = isNamedCTE ? 'CTE' : (tableName ? 'TABLE' : 'QUERY');

    // Check if this references another CTE
    const referencesOtherCTE = cteNames.has(tableName.toLowerCase()) && tableName.toLowerCase() !== pipeline.name?.toLowerCase();

    // Create header
    const header = document.createElement('div');
    header.className = 'pipe-node-header';

    const icon = document.createElement('div');
    icon.className = 'pipe-node-icon';
    icon.textContent = isNamedCTE ? 'C' : (referencesOtherCTE ? '→' : 'T');

    const title = document.createElement('div');
    title.className = 'pipe-node-title';
    title.textContent = nodeTitle;

    const typeLabel = document.createElement('div');
    typeLabel.className = 'pipe-node-type';
    typeLabel.textContent = nodeType;

    header.appendChild(icon);
    header.appendChild(title);
    header.appendChild(typeLabel);

    // Add source badge or reference badge
    if (tableName && !isNamedCTE) {
      const sourceBadge = document.createElement('span');
      sourceBadge.className = 'pipe-source-badge';
      sourceBadge.textContent = 'SOURCE';
      header.appendChild(sourceBadge);
    } else if (referencesOtherCTE) {
      const refBadge = document.createElement('span');
      refBadge.className = 'pipe-ref-badge';
      refBadge.textContent = `← ${tableName}`;
      refBadge.title = `References CTE: ${tableName}`;
      header.appendChild(refBadge);
    }

    node.appendChild(header);

    // Create body with transforms
    const body = document.createElement('div');
    body.className = 'pipe-node-body';

    // Show FROM source if this is a named CTE with a table source
    if (isNamedCTE && tableName) {
      const fromStep = document.createElement('div');
      fromStep.className = 'pipe-step';
      fromStep.innerHTML = `
        <div class="pipe-step-header">
          <span class="pipe-step-type select">FROM</span>
        </div>
        <div class="pipe-step-content">
          <span class="value-column">${this.escapeHtml(tableName)}</span>
        </div>
      `;
      body.appendChild(fromStep);
    }

    // Render transforms
    if (pipeline.transforms && pipeline.transforms.length > 0) {
      pipeline.transforms.forEach(transform => {
        const step = this.createPipeStep(transform);
        body.appendChild(step);
      });
    }

    if (body.children.length === 0) {
      const emptyMsg = document.createElement('div');
      emptyMsg.className = 'pipes-empty-state';
      emptyMsg.textContent = 'No transforms';
      body.appendChild(emptyMsg);
    }

    node.appendChild(body);

    // Add output columns footer if available
    const lastTransform = pipeline.transforms?.[pipeline.transforms.length - 1];
    const outputCols = lastTransform?.output_columns || pipeline.from?.output_columns;
    if (outputCols && outputCols.length > 0) {
      const footer = document.createElement('div');
      footer.className = 'pipe-node-footer';
      footer.appendChild(this.renderOutputColumns(outputCols));
      node.appendChild(footer);
    }

    // Add connection ports for multiple pipelines
    if (totalPipelines > 1) {
      if (idx > 0) {
        const portIn = document.createElement('div');
        portIn.className = 'pipe-port pipe-port-in';
        portIn.title = 'Input';
        node.appendChild(portIn);
      }
      if (idx < totalPipelines - 1) {
        const portOut = document.createElement('div');
        portOut.className = 'pipe-port pipe-port-out';
        portOut.title = 'Output';
        node.appendChild(portOut);
      }
    }

    return node;
  }

  /**
   * Create a step element within a pipe node
   */
  createPipeStep(transform) {
    const step = document.createElement('div');
    step.className = 'pipe-step';

    const stepType = transform.type || 'unknown';
    const header = document.createElement('div');
    header.className = 'pipe-step-header';

    const typeBadge = document.createElement('span');
    typeBadge.className = `pipe-step-type ${stepType}`;
    typeBadge.textContent = stepType.toUpperCase().replace('_', ' ');
    header.appendChild(typeBadge);

    const content = document.createElement('div');
    content.className = 'pipe-step-content';
    content.innerHTML = this.renderPipeStepContent(transform);

    step.appendChild(header);
    step.appendChild(content);

    return step;
  }

  /**
   * Render the content of a pipe step based on transform type
   */
  renderPipeStepContent(transform) {
    const escape = (str) => this.escapeHtml(str);

    switch (transform.type) {
      case 'where':
        return `<span class="value-column">${escape(transform.condition || '')}</span>`;

      case 'select':
        if (transform.columns && transform.columns.length > 0) {
          const cols = transform.columns.map(c => {
            const expr = typeof c === 'string' ? c : (c.expression || c.name || '');
            const alias = typeof c === 'object' && c.name ? ` <span class="value-operator">as</span> ${escape(c.name)}` : '';
            return `<span class="value-column">${escape(expr)}</span>${alias}`;
          });
          return cols.join(', ');
        }
        return '';

      case 'group_by':
        const dims = (transform.dimensions || []).map(d => `<span class="value-column">${escape(d)}</span>`);
        const aggs = (transform.aggregates || []).map(a => {
          const col = a.column || '*';
          const alias = a.alias ? ` <span class="value-operator">as</span> ${escape(a.alias)}` : '';
          return `<span class="value-function">${escape(a.function)}</span>(<span class="value-column">${escape(col)}</span>)${alias}`;
        });
        return [...dims, ...aggs].join(', ');

      case 'order_by':
        if (transform.expressions && transform.expressions.length > 0) {
          const items = transform.expressions.map(e => {
            const col = e.column || '';
            const dir = e.direction === 'desc' ? ' ↓' : ' ↑';
            return `<span class="value-column">${escape(col)}</span>${dir}`;
          });
          return items.join(', ');
        }
        return '';

      case 'limit':
        return `<span class="value-number">${transform.count || ''}</span>`;

      case 'join':
        const joinType = transform.join_type || 'join';
        const joinTable = transform.table || '';
        const joinOn = transform.on || '';
        return `<span class="value-operator">${escape(joinType)}</span> <span class="value-column">${escape(joinTable)}</span> <span class="value-operator">on</span> ${escape(joinOn)}`;

      case 'extend':
        if (transform.columns && transform.columns.length > 0) {
          const cols = transform.columns.map(c => {
            const expr = typeof c === 'string' ? c : (c.expression || '');
            const alias = typeof c === 'object' && c.name ? ` <span class="value-operator">as</span> ${escape(c.name)}` : '';
            return `${escape(expr)}${alias}`;
          });
          return cols.join(', ');
        }
        return '';

      default:
        return JSON.stringify(transform).slice(0, 100);
    }
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
        body.appendChild(this.renderParameter(transform, param, pipelineIdx, transformIdx));
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
  renderParameter(transform, param, pipelineIdx, transformIdx = 0) {
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
        container.appendChild(this.renderExpressionWidget(transform, param, pipelineIdx, transformIdx));
        break;
      case 'list':
        container.appendChild(this.renderListWidget(transform, param, pipelineIdx, transformIdx));
        break;
      case 'aggregate_list':
        container.appendChild(this.renderAggregateList(transform, param, pipelineIdx, transformIdx));
        break;
      case 'order_list':
        container.appendChild(this.renderOrderList(transform, param, pipelineIdx, transformIdx));
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
      const val = e.target.value.trim();
      // Use undefined for empty values so optional fields can be cleared
      transform[param.name] = val === '' ? undefined : (parseInt(val, 10) || 0);
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
  renderExpressionWidget(transform, param, pipelineIdx, transformIdx = 0) {
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
      schema: this.getSchemaContext(pipelineIdx, transformIdx)
    });

    this.expressionInstances.set(exprId, expr);
    return expr.render();
  }

  /**
   * Render list widget (columns, expressions)
   */
  renderListWidget(transform, param, pipelineIdx, transformIdx = 0) {
    const items = transform[param.name] || [];
    const isExpressionType = param.type === 'expression[]' ||
                            param.name === 'columns' ||
                            param.name === 'dimensions';
    const showAlias = param.name === 'columns' && transform.type === 'select';

    const container = document.createElement('div');
    container.className = 'expression-list';

    items.forEach((item, idx) => {
      const itemEl = this.renderExpressionItem(item, idx, transform, param, pipelineIdx, transformIdx, showAlias);
      container.appendChild(itemEl);
    });

    // Add button
    const addBtn = document.createElement('button');
    addBtn.className = 'list-add-btn';
    addBtn.textContent = '+ Add';
    // Store references for the click handler
    const paramName = param.name;
    const transformRef = transform;
    const editorRef = this;
    const needsAlias = showAlias;
    addBtn.onclick = function(e) {
      e.stopPropagation();
      const newItem = needsAlias ? { expression: '', name: '' } : '';
      if (!transformRef[paramName]) {
        transformRef[paramName] = [];
      }
      transformRef[paramName].push(newItem);
      editorRef.renderAll();
      editorRef.notifyChange();
    };
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
          filter: '.list-add-btn, .expr-remove, button',  // Don't drag when clicking buttons
          preventOnFilter: false,  // Allow click events on filtered elements
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
  renderExpressionItem(item, idx, transform, param, pipelineIdx, transformIdx, showAlias) {
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
      schema: this.getSchemaContext(pipelineIdx, transformIdx)
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
  renderAggregateList(transform, param, pipelineIdx, transformIdx = 0) {
    const items = transform[param.name] || [];
    const aggregates = this.metadata.aggregates || {};

    const container = document.createElement('div');
    container.className = 'aggregate-list';

    items.forEach((item, idx) => {
      const itemEl = this.renderAggregateItem(item, idx, transform, param, pipelineIdx, transformIdx, aggregates);
      container.appendChild(itemEl);
    });

    // Add button
    const addBtn = document.createElement('button');
    addBtn.className = 'list-add-btn';
    addBtn.textContent = '+ Add Aggregate';
    const paramName = param.name;
    const transformRef = transform;
    const editorRef = this;
    addBtn.onclick = function(e) {
      e.stopPropagation();
      if (!transformRef[paramName]) {
        transformRef[paramName] = [];
      }
      transformRef[paramName].push({ function: 'count', column: '', alias: '' });
      editorRef.renderAll();
      editorRef.notifyChange();
    };
    container.appendChild(addBtn);

    return container;
  }

  /**
   * Render a single aggregate item
   */
  renderAggregateItem(item, idx, transform, param, pipelineIdx, transformIdx, aggregates) {
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
  renderOrderList(transform, param, pipelineIdx, transformIdx = 0) {
    const items = transform[param.name] || [];

    const container = document.createElement('div');
    container.className = 'order-list';

    items.forEach((item, idx) => {
      const itemEl = this.renderOrderItem(item, idx, transform, param, pipelineIdx, transformIdx);
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
  renderOrderItem(item, idx, transform, param, pipelineIdx, transformIdx) {
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

    // Preserve set_operation when removing a middle pipeline
    const removedSetOp = this.pipelines[pipelineIdx]?.set_operation;
    if (pipelineIdx > 0) {
      if (pipelineIdx < this.pipelines.length - 1) {
        // Middle pipeline: carry forward its set_operation to previous pipeline
        this.pipelines[pipelineIdx - 1].set_operation = 
          removedSetOp || { type: 'union', all: false };
      } else {
        // Last pipeline: remove set_operation from previous
        delete this.pipelines[pipelineIdx - 1].set_operation;
      }
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
   * Get schema context for autocomplete (available columns at a given point in pipeline)
   *
   * This uses output_columns populated by the backend via SQLGlot qualify.
   * If columns aren't showing in dropdowns, check:
   * 1. Is the backend returning output_columns? (check /api/visual/transpile response)
   * 2. Are output_columns being merged into transforms? (check onVisualEditorChange in playground.js)
   *
   * @param {number} pipelineIdx - Index of the pipeline
   * @param {number} transformIdx - Index of the transform (-1 for FROM block, or index of current transform)
   */
  getSchemaContext(pipelineIdx, transformIdx = -1) {
    const pipeline = this.pipelines[pipelineIdx];
    if (!pipeline) return { columns: [] };

    let columns = [];

    if (transformIdx < 0) {
      // For FROM block or before any transforms - use FROM's output_columns
      columns = pipeline.from?.output_columns || [];
    } else if (transformIdx === 0) {
      // First transform - use FROM's output_columns
      columns = pipeline.from?.output_columns || [];
    } else {
      // Use previous transform's output_columns
      const prevTransform = pipeline.transforms?.[transformIdx - 1];
      columns = prevTransform?.output_columns || pipeline.from?.output_columns || [];
    }

    return { columns };
  }

  /**
   * Normalize transform IDs and update nextTransformId to avoid collisions
   */
  normalizeTransformIds() {
    let maxId = -1;
    this.pipelines.forEach(pipeline => {
      (pipeline.transforms || []).forEach(t => {
        if (!t.id) {
          t.id = `t${this.nextTransformId++}`;
        }
        const match = /^t(\d+)$/.exec(t.id);
        if (match) {
          maxId = Math.max(maxId, parseInt(match[1], 10));
        }
      });
    });
    if (maxId >= 0) {
      this.nextTransformId = Math.max(this.nextTransformId, maxId + 1);
    }
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
    
    // Normalize transform IDs to avoid collisions
    this.normalizeTransformIds();

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

    // Normalize transform IDs to avoid collisions
    this.normalizeTransformIds();

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
      if (expr.destroy) expr.destroy();
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
  window.visualEditor = visualEditor; // Expose for debugging
});
