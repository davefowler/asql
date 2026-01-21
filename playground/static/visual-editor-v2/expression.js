/**
 * Expression Component - Recursive expression builder with progressive disclosure
 * 
 * Expression Types:
 * - Leaf nodes: { type: 'column', name: 'amount' }
 *               { type: 'literal', value: 10, dataType: 'number' }
 * - Wrapper nodes: { type: 'function', name: 'min', args: [Expression] }
 *                  { type: 'binary', op: '+', left: Expression, right: Expression }
 *                  { type: 'unary', op: 'NOT', arg: Expression }
 */

class Expression {
  /**
   * @param {object} options
   * @param {object} options.value - The expression value (structured object or string)
   * @param {string} options.id - Unique ID for this expression
   * @param {boolean} options.showAlias - Whether to show alias toggle
   * @param {string[]} options.functionCategories - Which function categories to show
   * @param {Function} options.onChange - Callback when expression changes
   * @param {Function} options.onRemove - Callback when expression is removed
   * @param {object} options.metadata - Reference to metadata (functions, operators, etc.)
   * @param {object} options.schema - Available columns and their types
   */
  constructor(options) {
    this.value = this.parseValue(options.value);
    this.id = options.id || `expr-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
    this.showAlias = options.showAlias ?? false;
    this.functionCategories = options.functionCategories || ['date', 'string', 'math'];
    this.onChange = options.onChange || (() => {});
    this.onRemove = options.onRemove || null;
    this.metadata = options.metadata || {};
    this.schema = options.schema || {};
    this.hoverTimeout = null;
    this.isHovering = false;
    this.element = null;
  }

  /**
   * Parse a value into structured expression format
   */
  parseValue(value) {
    if (!value) {
      return { type: 'column', name: '', alias: null };
    }

    // Already structured
    if (value && typeof value === 'object' && value.type) {
      return value;
    }

    // Object format from existing editor: { expression: 'month(date)', name: 'signup_month' }
    if (value && typeof value === 'object') {
      const expr = value.expression || value.name || '';
      const alias = value.name && value.expression && value.name !== value.expression ? value.name : null;
      const parsed = this.parseExpressionString(expr);
      if (alias) parsed.alias = alias;
      return parsed;
    }

    // String format: parse it
    return this.parseExpressionString(value);
  }

  /**
   * Parse a string expression like "month(date)" or "amount + 10"
   */
  parseExpressionString(str) {
    if (!str || typeof str !== 'string') {
      return { type: 'column', name: str || '', alias: null };
    }

    str = str.trim();

    // Check for function call: func(arg)
    const funcMatch = str.match(/^(\w+)\s*\(\s*(.+)\s*\)$/);
    if (funcMatch) {
      return {
        type: 'function',
        name: funcMatch[1].toLowerCase(),
        args: [this.parseExpressionString(funcMatch[2])],
        alias: null
      };
    }

    // Check for binary operators (simple case)
    // Order matters: check longer operators first
    const binaryOps = ['>=', '<=', '!=', '<>', '||', '=', '>', '<', '+', '-', '*', '/', 'AND', 'OR', 'IS NOT', 'IS'];
    for (const op of binaryOps) {
      const opRegex = new RegExp(`\\s+${op.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s+`, 'i');
      const idx = str.search(opRegex);
      if (idx > 0) {
        const match = str.match(opRegex);
        const left = str.substring(0, idx);
        const right = str.substring(idx + match[0].length);
        return {
          type: 'binary',
          op: op.toUpperCase(),
          left: this.parseExpressionString(left),
          right: this.parseExpressionString(right),
          alias: null
        };
      }
    }

    // Check for literal number
    if (/^-?\d+(\.\d+)?$/.test(str)) {
      return { type: 'literal', value: parseFloat(str), dataType: 'number', alias: null };
    }

    // Check for literal string (quoted)
    if (/^['"].*['"]$/.test(str)) {
      return { type: 'literal', value: str.slice(1, -1), dataType: 'string', alias: null };
    }

    // Check for NULL
    if (str.toUpperCase() === 'NULL') {
      return { type: 'literal', value: null, dataType: 'null', alias: null };
    }

    // Default: treat as column
    return { type: 'column', name: str, alias: null };
  }

  /**
   * Convert structured expression back to string
   */
  toString(expr = this.value) {
    if (!expr) return '';

    switch (expr.type) {
      case 'column':
        return expr.name || '';
      case 'literal':
        if (expr.dataType === 'string') return `'${expr.value}'`;
        if (expr.dataType === 'null') return 'NULL';
        return String(expr.value ?? '');
      case 'function':
        const args = (expr.args || []).map(a => this.toString(a)).join(', ');
        return `${expr.name}(${args})`;
      case 'binary':
        return `${this.toString(expr.left)} ${expr.op} ${this.toString(expr.right)}`;
      case 'unary':
        return `${expr.op} ${this.toString(expr.arg)}`;
      default:
        return '';
    }
  }

  /**
   * Get output format for serialization
   */
  toOutput() {
    const exprStr = this.toString();
    if (this.showAlias && this.value.alias) {
      return { expression: exprStr, name: this.value.alias };
    }
    return exprStr;
  }

  /**
   * Render the expression to DOM
   */
  render() {
    const el = document.createElement('div');
    el.className = 'expression';
    el.dataset.exprId = this.id;
    
    // Render the expression content
    const content = this.renderExpressionNode(this.value, true);
    el.appendChild(content);

    // Add alias if enabled
    if (this.showAlias) {
      el.appendChild(this.renderAliasToggle());
    }

    // Add remove button if removable
    if (this.onRemove) {
      const removeBtn = document.createElement('button');
      removeBtn.className = 'expr-remove';
      removeBtn.textContent = '×';
      removeBtn.title = 'Remove';
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.onRemove();
      });
      el.appendChild(removeBtn);
    }

    this.element = el;
    this.setupEventListeners(el);
    return el;
  }

  /**
   * Render an expression node recursively
   */
  renderExpressionNode(expr, isRoot = false) {
    const wrapper = document.createElement('span');
    wrapper.className = `expr-node ${isRoot ? 'expr-root' : ''}`;
    wrapper.dataset.exprType = expr.type;

    switch (expr.type) {
      case 'column':
        wrapper.appendChild(this.renderColumnInput(expr));
        break;
      case 'literal':
        wrapper.appendChild(this.renderLiteralInput(expr));
        break;
      case 'function':
        wrapper.appendChild(this.renderFunctionCall(expr));
        break;
      case 'binary':
        wrapper.appendChild(this.renderBinaryOp(expr));
        break;
      case 'unary':
        wrapper.appendChild(this.renderUnaryOp(expr));
        break;
    }

    // Add expand button for hover interaction
    const expandBtn = document.createElement('button');
    expandBtn.className = 'expr-expand';
    expandBtn.textContent = '+';
    expandBtn.title = 'Expand expression';
    expandBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.showExpandMenu(wrapper, expr);
    });
    wrapper.appendChild(expandBtn);

    return wrapper;
  }

  /**
   * Render column input with autocomplete
   */
  renderColumnInput(expr) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'expr-column column-autocomplete';
    input.value = expr.name || '';
    input.placeholder = 'column';
    input.setAttribute('list', `columns-${this.id}`);

    // Create datalist for autocomplete
    const datalist = document.createElement('datalist');
    datalist.id = `columns-${this.id}`;
    if (this.schema.columns) {
      this.schema.columns.forEach(col => {
        const option = document.createElement('option');
        option.value = typeof col === 'string' ? col : col.name;
        datalist.appendChild(option);
      });
    }

    const container = document.createElement('span');
    container.className = 'expr-column-container';
    container.appendChild(input);
    container.appendChild(datalist);

    input.addEventListener('input', (e) => {
      expr.name = e.target.value;
      this.notifyChange();
    });

    return container;
  }

  /**
   * Render literal value input
   */
  renderLiteralInput(expr) {
    const input = document.createElement('input');
    input.className = 'expr-literal';
    
    if (expr.dataType === 'number') {
      input.type = 'number';
      input.value = expr.value ?? '';
      input.className += ' expr-literal-number';
    } else if (expr.dataType === 'null') {
      input.type = 'text';
      input.value = 'NULL';
      input.readOnly = true;
      input.className += ' expr-literal-null';
    } else {
      input.type = 'text';
      input.value = expr.value ?? '';
      input.className += ' expr-literal-string';
    }

    input.addEventListener('input', (e) => {
      if (expr.dataType === 'number') {
        expr.value = parseFloat(e.target.value) || 0;
      } else {
        expr.value = e.target.value;
      }
      this.notifyChange();
    });

    return input;
  }

  /**
   * Render function call: func(args)
   */
  renderFunctionCall(expr) {
    const container = document.createElement('span');
    container.className = 'expr-function-call';

    // Function name dropdown
    const funcSelect = document.createElement('select');
    funcSelect.className = 'expr-func-select';
    
    // Add empty option
    const emptyOpt = document.createElement('option');
    emptyOpt.value = '';
    emptyOpt.textContent = '';
    funcSelect.appendChild(emptyOpt);

    // Add function options from metadata
    const groups = this.getFunctionGroups();
    groups.forEach(group => {
      const optgroup = document.createElement('optgroup');
      optgroup.label = group.label;
      group.functions.forEach(fn => {
        const opt = document.createElement('option');
        opt.value = fn.value;
        opt.textContent = fn.label;
        opt.selected = expr.name === fn.value;
        optgroup.appendChild(opt);
      });
      funcSelect.appendChild(optgroup);
    });

    funcSelect.addEventListener('change', (e) => {
      expr.name = e.target.value;
      this.notifyChange();
    });

    // Open paren
    const openParen = document.createElement('span');
    openParen.className = 'expr-paren expr-open';
    openParen.textContent = '(';

    // Args
    const argsContainer = document.createElement('span');
    argsContainer.className = 'expr-args';
    (expr.args || []).forEach((arg, idx) => {
      if (idx > 0) {
        const comma = document.createElement('span');
        comma.className = 'expr-comma';
        comma.textContent = ', ';
        argsContainer.appendChild(comma);
      }
      argsContainer.appendChild(this.renderExpressionNode(arg));
    });

    // Close paren
    const closeParen = document.createElement('span');
    closeParen.className = 'expr-paren expr-close';
    closeParen.textContent = ')';

    container.appendChild(funcSelect);
    container.appendChild(openParen);
    container.appendChild(argsContainer);
    container.appendChild(closeParen);

    return container;
  }

  /**
   * Render binary operation: left op right
   */
  renderBinaryOp(expr) {
    const container = document.createElement('span');
    container.className = 'expr-binary';

    // Left operand
    container.appendChild(this.renderExpressionNode(expr.left));

    // Operator
    const opSelect = document.createElement('select');
    opSelect.className = 'expr-op-select';
    
    const operators = this.getOperators();
    Object.entries(operators).forEach(([category, ops]) => {
      const optgroup = document.createElement('optgroup');
      optgroup.label = category;
      Object.entries(ops).forEach(([op, info]) => {
        const opt = document.createElement('option');
        opt.value = op;
        opt.textContent = info.label || op;
        opt.selected = expr.op === op || expr.op === op.toUpperCase();
        optgroup.appendChild(opt);
      });
      opSelect.appendChild(optgroup);
    });

    opSelect.addEventListener('change', (e) => {
      expr.op = e.target.value;
      this.notifyChange();
    });

    container.appendChild(opSelect);

    // Right operand
    container.appendChild(this.renderExpressionNode(expr.right));

    return container;
  }

  /**
   * Render unary operation: op arg
   */
  renderUnaryOp(expr) {
    const container = document.createElement('span');
    container.className = 'expr-unary';

    const opSpan = document.createElement('span');
    opSpan.className = 'expr-unary-op';
    opSpan.textContent = expr.op;
    container.appendChild(opSpan);

    container.appendChild(this.renderExpressionNode(expr.arg));

    return container;
  }

  /**
   * Render alias toggle
   */
  renderAliasToggle() {
    const container = document.createElement('span');
    container.className = `expr-alias-container ${this.value.alias ? 'has-alias' : ''}`;

    const toggle = document.createElement('span');
    toggle.className = 'expr-as-toggle';
    toggle.textContent = 'as';
    toggle.addEventListener('click', () => {
      if (!this.value.alias) {
        this.value.alias = this.getDefaultAlias();
      }
      container.classList.toggle('has-alias');
      aliasInput.focus();
      this.notifyChange();
    });

    const aliasInput = document.createElement('input');
    aliasInput.type = 'text';
    aliasInput.className = 'expr-alias-input';
    aliasInput.value = this.value.alias || '';
    aliasInput.placeholder = this.getDefaultAlias();
    aliasInput.addEventListener('input', (e) => {
      this.value.alias = e.target.value || null;
      this.notifyChange();
    });

    container.appendChild(toggle);
    container.appendChild(aliasInput);

    return container;
  }

  /**
   * Get default alias based on expression
   */
  getDefaultAlias() {
    const expr = this.value;
    if (expr.type === 'function') {
      const innerName = expr.args?.[0]?.name || 'value';
      return `${expr.name}_${innerName}`;
    }
    if (expr.type === 'column') {
      return expr.name || 'column';
    }
    return 'expr';
  }

  /**
   * Show expand menu for adding operations
   */
  showExpandMenu(target, expr) {
    // Remove any existing menu
    document.querySelectorAll('.expr-expand-menu').forEach(m => m.remove());

    const menu = document.createElement('div');
    menu.className = 'expr-expand-menu';

    // Wrap in function section
    const funcSection = this.createMenuSection('Wrap in function', () => {
      const groups = this.getFunctionGroups();
      const submenu = document.createElement('div');
      submenu.className = 'expr-menu-submenu';
      
      groups.forEach(group => {
        const groupLabel = document.createElement('div');
        groupLabel.className = 'expr-menu-group-label';
        groupLabel.textContent = group.label;
        submenu.appendChild(groupLabel);
        
        group.functions.forEach(fn => {
          const item = document.createElement('div');
          item.className = 'expr-menu-item';
          item.textContent = fn.label;
          item.addEventListener('click', () => {
            this.wrapInFunction(expr, fn.value);
            menu.remove();
          });
          submenu.appendChild(item);
        });
      });
      
      return submenu;
    });
    menu.appendChild(funcSection);

    // Add operator section
    const opSection = this.createMenuSection('Add operation', () => {
      const submenu = document.createElement('div');
      submenu.className = 'expr-menu-submenu';
      
      const operators = [
        { op: '+', label: '+ (add)' },
        { op: '-', label: '- (subtract)' },
        { op: '*', label: '* (multiply)' },
        { op: '/', label: '/ (divide)' },
        { op: '||', label: '|| (concat)' },
      ];
      
      operators.forEach(({ op, label }) => {
        const item = document.createElement('div');
        item.className = 'expr-menu-item';
        item.textContent = label;
        item.addEventListener('click', () => {
          this.addOperator(expr, op);
          menu.remove();
        });
        submenu.appendChild(item);
      });
      
      return submenu;
    });
    menu.appendChild(opSection);

    // Compare to section
    const compareSection = this.createMenuSection('Compare to', () => {
      const submenu = document.createElement('div');
      submenu.className = 'expr-menu-submenu';
      
      const comparisons = [
        { op: '=', label: '= (equals)' },
        { op: '!=', label: '!= (not equals)' },
        { op: '>', label: '> (greater than)' },
        { op: '<', label: '< (less than)' },
        { op: '>=', label: '>= (at least)' },
        { op: '<=', label: '<= (at most)' },
        { op: 'IS', label: 'IS (null check)' },
        { op: 'IS NOT', label: 'IS NOT' },
        { op: 'LIKE', label: 'LIKE (pattern)' },
        { op: 'IN', label: 'IN (list)' },
        { op: 'BETWEEN', label: 'BETWEEN' },
      ];
      
      comparisons.forEach(({ op, label }) => {
        const item = document.createElement('div');
        item.className = 'expr-menu-item';
        item.textContent = label;
        item.addEventListener('click', () => {
          this.addComparison(expr, op);
          menu.remove();
        });
        submenu.appendChild(item);
      });
      
      return submenu;
    });
    menu.appendChild(compareSection);

    // Position menu
    const rect = target.getBoundingClientRect();
    menu.style.position = 'absolute';
    menu.style.left = `${rect.right + 4}px`;
    menu.style.top = `${rect.top}px`;

    document.body.appendChild(menu);

    // Close on outside click
    const closeHandler = (e) => {
      if (!menu.contains(e.target)) {
        menu.remove();
        document.removeEventListener('click', closeHandler);
      }
    };
    setTimeout(() => document.addEventListener('click', closeHandler), 0);
  }

  /**
   * Create a menu section with expandable content
   */
  createMenuSection(title, contentFn) {
    const section = document.createElement('div');
    section.className = 'expr-menu-section';
    
    const header = document.createElement('div');
    header.className = 'expr-menu-section-header';
    header.textContent = title;
    header.addEventListener('click', () => {
      const content = section.querySelector('.expr-menu-submenu');
      if (content) {
        content.remove();
      } else {
        section.appendChild(contentFn());
      }
    });
    
    section.appendChild(header);
    return section;
  }

  /**
   * Wrap current expression in a function
   */
  wrapInFunction(expr, funcName) {
    // Clone the current expression
    const inner = JSON.parse(JSON.stringify(this.value));
    
    // Replace with function wrapping the original
    this.value = {
      type: 'function',
      name: funcName,
      args: [inner],
      alias: this.value.alias
    };
    
    this.rerender();
  }

  /**
   * Add an operator to the expression
   */
  addOperator(expr, op) {
    const inner = JSON.parse(JSON.stringify(this.value));
    
    this.value = {
      type: 'binary',
      op: op,
      left: inner,
      right: { type: 'literal', value: 0, dataType: 'number' },
      alias: this.value.alias
    };
    
    this.rerender();
  }

  /**
   * Add a comparison to the expression
   */
  addComparison(expr, op) {
    const inner = JSON.parse(JSON.stringify(this.value));
    
    let rightValue;
    if (op === 'IS' || op === 'IS NOT') {
      rightValue = { type: 'literal', value: null, dataType: 'null' };
    } else if (op === 'IN') {
      rightValue = { type: 'literal', value: '', dataType: 'string' };
    } else if (op === 'BETWEEN') {
      // BETWEEN needs special handling - for now just add simple comparison
      rightValue = { type: 'literal', value: '', dataType: 'string' };
    } else {
      rightValue = { type: 'literal', value: '', dataType: 'string' };
    }
    
    this.value = {
      type: 'binary',
      op: op,
      left: inner,
      right: rightValue,
      alias: this.value.alias
    };
    
    this.rerender();
  }

  /**
   * Get function groups from metadata
   */
  getFunctionGroups() {
    const functions = this.metadata.functions || {};
    const groups = [];
    
    this.functionCategories.forEach(cat => {
      const catFuncs = functions[cat];
      if (catFuncs) {
        const funcs = Object.entries(catFuncs).map(([key, info]) => ({
          value: key,
          label: info.label || key
        }));
        groups.push({
          name: cat,
          label: cat.charAt(0).toUpperCase() + cat.slice(1),
          functions: funcs
        });
      }
    });

    // Fallback
    if (groups.length === 0) {
      groups.push(
        { name: 'date', label: 'Date', functions: [
          { value: 'year', label: 'year' },
          { value: 'month', label: 'month' },
          { value: 'day', label: 'day' },
          { value: 'week', label: 'week' },
        ]},
        { name: 'string', label: 'String', functions: [
          { value: 'upper', label: 'upper' },
          { value: 'lower', label: 'lower' },
          { value: 'trim', label: 'trim' },
        ]},
        { name: 'math', label: 'Math', functions: [
          { value: 'abs', label: 'abs' },
          { value: 'round', label: 'round' },
        ]}
      );
    }

    return groups;
  }

  /**
   * Get operators from metadata
   */
  getOperators() {
    return this.metadata.operators || {
      comparison: {
        '=': { label: '=' },
        '!=': { label: '!=' },
        '>': { label: '>' },
        '<': { label: '<' },
        '>=': { label: '>=' },
        '<=': { label: '<=' },
      },
      arithmetic: {
        '+': { label: '+' },
        '-': { label: '-' },
        '*': { label: '*' },
        '/': { label: '/' },
      }
    };
  }

  /**
   * Setup event listeners for hover interaction
   */
  setupEventListeners(el) {
    el.addEventListener('mouseenter', () => {
      this.hoverTimeout = setTimeout(() => {
        el.classList.add('expr-hover');
      }, 800);
    });

    el.addEventListener('mouseleave', () => {
      clearTimeout(this.hoverTimeout);
      el.classList.remove('expr-hover');
    });
  }

  /**
   * Re-render the expression
   */
  rerender() {
    if (this.element && this.element.parentNode) {
      const newEl = this.render();
      this.element.parentNode.replaceChild(newEl, this.element);
    }
    this.notifyChange();
  }

  /**
   * Notify parent of changes
   */
  notifyChange() {
    this.onChange(this.toOutput());
  }

  /**
   * Clean up event listeners and timeouts to prevent memory leaks
   */
  destroy() {
    // Clear hover timeout
    if (this.hoverTimeout) {
      clearTimeout(this.hoverTimeout);
      this.hoverTimeout = null;
    }

    // Remove any expand menus that might be open
    document.querySelectorAll('.expr-expand-menu').forEach(m => m.remove());

    // Clear element reference
    if (this.element) {
      this.element = null;
    }

    // Clear callback references
    this.onChange = () => {};
    this.onRemove = null;
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = Expression;
}
