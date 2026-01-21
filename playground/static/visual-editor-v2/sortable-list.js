/**
 * SortableList Component - Drag-to-reorder list wrapper using SortableJS
 * 
 * Usage:
 *   const list = new SortableList({
 *     items: [{ ... }, { ... }],
 *     renderItem: (item, idx) => element,
 *     onChange: (newItems) => {},
 *     addLabel: '+ Add',
 *     onAdd: () => newItem,
 *   });
 *   container.appendChild(list.render());
 */

class SortableList {
  /**
   * @param {object} options
   * @param {Array} options.items - Array of items to render
   * @param {Function} options.renderItem - (item, index) => HTMLElement
   * @param {Function} options.onChange - Callback when order changes
   * @param {string} options.addLabel - Label for add button
   * @param {Function} options.onAdd - Returns new item to add, or shows picker
   * @param {number} options.minItems - Minimum items required
   * @param {number} options.maxItems - Maximum items allowed
   * @param {string} options.className - Additional CSS class for container
   * @param {string} options.itemClassName - CSS class for items
   */
  constructor(options) {
    this.items = options.items || [];
    this.renderItem = options.renderItem;
    this.onChange = options.onChange || (() => {});
    this.addLabel = options.addLabel || '+ Add';
    this.onAdd = options.onAdd;
    this.minItems = options.minItems ?? 0;
    this.maxItems = options.maxItems ?? Infinity;
    this.className = options.className || 'sortable-list';
    this.itemClassName = options.itemClassName || 'sortable-item';
    this.element = null;
    this.sortable = null;
  }

  /**
   * Render the sortable list
   */
  render() {
    const container = document.createElement('div');
    container.className = this.className;

    // Items container
    const itemsContainer = document.createElement('div');
    itemsContainer.className = 'sortable-items';
    
    this.items.forEach((item, idx) => {
      const itemEl = this.createItemWrapper(item, idx);
      itemsContainer.appendChild(itemEl);
    });

    container.appendChild(itemsContainer);

    // Add button
    if (this.onAdd && this.items.length < this.maxItems) {
      const addBtn = document.createElement('button');
      addBtn.className = 'sortable-add-btn';
      addBtn.textContent = this.addLabel;
      addBtn.addEventListener('click', () => this.handleAdd());
      container.appendChild(addBtn);
    }

    this.element = container;
    this.itemsContainer = itemsContainer;

    // Initialize SortableJS if available
    this.initSortable(itemsContainer);

    return container;
  }

  /**
   * Create a wrapper for a single item
   */
  createItemWrapper(item, idx) {
    const wrapper = document.createElement('div');
    wrapper.className = this.itemClassName;
    wrapper.dataset.index = idx;

    // Drag handle
    const handle = document.createElement('span');
    handle.className = 'sortable-handle';
    handle.innerHTML = '⋮⋮';
    handle.title = 'Drag to reorder';
    wrapper.appendChild(handle);

    // Item content
    const content = document.createElement('div');
    content.className = 'sortable-content';
    const rendered = this.renderItem(item, idx);
    if (rendered instanceof HTMLElement) {
      content.appendChild(rendered);
    } else if (typeof rendered === 'string') {
      content.innerHTML = rendered;
    }
    wrapper.appendChild(content);

    // Remove button
    if (this.items.length > this.minItems) {
      const removeBtn = document.createElement('button');
      removeBtn.className = 'sortable-remove';
      removeBtn.textContent = '×';
      removeBtn.title = 'Remove';
      removeBtn.addEventListener('click', () => this.handleRemove(idx));
      wrapper.appendChild(removeBtn);
    }

    return wrapper;
  }

  /**
   * Initialize SortableJS
   */
  initSortable(container) {
    // Check if SortableJS is loaded
    if (typeof Sortable !== 'undefined') {
      this.sortable = new Sortable(container, {
        animation: 150,
        handle: '.sortable-handle',
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        onEnd: (evt) => {
          const { oldIndex, newIndex } = evt;
          if (oldIndex !== newIndex) {
            // Reorder items array
            const item = this.items.splice(oldIndex, 1)[0];
            this.items.splice(newIndex, 0, item);
            this.notifyChange();
          }
        }
      });
    } else {
      console.warn('SortableJS not loaded - drag-and-drop disabled');
    }
  }

  /**
   * Handle adding a new item
   */
  handleAdd() {
    if (this.items.length >= this.maxItems) return;

    const newItem = this.onAdd();
    if (newItem !== undefined && newItem !== null) {
      this.items.push(newItem);
      this.rerender();
      this.notifyChange();
    }
  }

  /**
   * Handle removing an item
   */
  handleRemove(idx) {
    if (this.items.length <= this.minItems) return;

    this.items.splice(idx, 1);
    this.rerender();
    this.notifyChange();
  }

  /**
   * Update an item at index
   */
  updateItem(idx, newValue) {
    if (idx >= 0 && idx < this.items.length) {
      this.items[idx] = newValue;
      this.notifyChange();
    }
  }

  /**
   * Re-render the list
   */
  rerender() {
    if (this.element && this.element.parentNode) {
      const newEl = this.render();
      this.element.parentNode.replaceChild(newEl, this.element);
    }
  }

  /**
   * Notify parent of changes
   */
  notifyChange() {
    this.onChange([...this.items]);
  }

  /**
   * Destroy the sortable instance
   */
  destroy() {
    if (this.sortable) {
      this.sortable.destroy();
      this.sortable = null;
    }
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SortableList;
}
