/**
 * Accordion Utilities - Shared functions for accordion/spreadsheet mode
 * 
 * These utilities are used by both:
 * - visual-editor.js (input panel - interactive editing)
 * - playground.js (output panel - read-only display)
 */

// Number of sample data rows to show in accordion preview
const ACCORDION_PREVIEW_ROWS = 10;

/**
 * Generate fake/sample data based on column type
 * Used to populate preview rows in the accordion view
 * 
 * @param {string} colType - The column type (e.g., 'int', 'varchar', 'timestamp')
 * @param {number} rowIdx - Row index (for deterministic variation)
 * @param {number} colIdx - Column index (for deterministic variation)
 * @returns {string|number} Fake data value appropriate for the column type
 */
function generateFakeData(colType, rowIdx, colIdx) {
    const typeNorm = (colType || '').toLowerCase();
    const currentYear = new Date().getFullYear();

    // Integer types
    if (typeNorm.includes('int') || typeNorm.includes('bigint')) {
        return Math.floor(Math.random() * 10000) + rowIdx * 100;
    }

    // Float/decimal types
    if (typeNorm.includes('float') || typeNorm.includes('double') || typeNorm.includes('decimal') || typeNorm.includes('numeric')) {
        return (Math.random() * 1000).toFixed(2);
    }

    // Date types
    if (typeNorm.includes('date') && !typeNorm.includes('time')) {
        const d = new Date(currentYear, Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1);
        return d.toISOString().split('T')[0];
    }

    // Timestamp types
    if (typeNorm.includes('timestamp') || typeNorm.includes('datetime')) {
        const d = new Date(currentYear, Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1,
                          Math.floor(Math.random() * 24), Math.floor(Math.random() * 60));
        return d.toISOString().replace('T', ' ').slice(0, 19);
    }

    // Boolean types
    if (typeNorm.includes('bool')) {
        return Math.random() > 0.5 ? 'true' : 'false';
    }

    // Text/string types (default)
    const sampleStrings = [
        'alpha', 'beta', 'gamma', 'delta', 'epsilon',
        'sample', 'test', 'demo', 'example', 'data',
        'foo', 'bar', 'baz', 'qux', 'quux'
    ];
    return sampleStrings[(rowIdx + colIdx) % sampleStrings.length] + '_' + (rowIdx + 1);
}

/**
 * Get a human-readable label for a transform
 * 
 * @param {Object} transform - The transform object with type and other properties
 * @returns {string} A short label describing the transform
 */
function getTransformLabel(transform) {
    if (!transform || !transform.type) return 'unknown';
    
    switch (transform.type) {
        case 'where':
            return transform.condition || 'condition...';
        case 'select':
            if (transform.columns && transform.columns.length > 0) {
                const names = transform.columns.slice(0, 3).map(c =>
                    typeof c === 'string' ? c : (c.name || c.expression || '')
                );
                return names.join(', ') + (transform.columns.length > 3 ? '...' : '');
            }
            return '*';
        case 'group_by':
            const dims = (transform.dimensions || []).slice(0, 2).join(', ');
            const aggCount = (transform.aggregates || []).length;
            return dims + (aggCount > 0 ? ` + ${aggCount} aggs` : '');
        case 'order_by':
            if (transform.expressions && transform.expressions.length > 0) {
                return transform.expressions.slice(0, 2).map(e => 
                    e.column + (e.direction === 'desc' ? ' ↓' : ' ↑')
                ).join(', ');
            }
            return 'order...';
        case 'limit':
            return `LIMIT ${transform.count || '?'}`;
        case 'join':
            return `${transform.join_type || 'JOIN'} ${transform.table || '?'}`;
        case 'extend':
            if (transform.columns && transform.columns.length > 0) {
                return `+ ${transform.columns.length} columns`;
            }
            return '+ columns';
        default:
            return transform.type;
    }
}

/**
 * Create column headers row for accordion step
 * 
 * @param {Array} columns - Array of column objects with name and optional type
 * @param {Object} options - Optional configuration
 * @param {Function} options.onColumnClick - Click handler for column headers (optional)
 * @returns {HTMLElement} The column headers row element
 */
function createAccordionColumnHeaders(columns, options = {}) {
    const headerRow = document.createElement('div');
    headerRow.className = 'accordion-col-headers';

    if (!columns || columns.length === 0) {
        const emptyCell = document.createElement('div');
        emptyCell.className = 'accordion-col-header accordion-empty-header';
        emptyCell.textContent = 'No columns';
        headerRow.appendChild(emptyCell);
        return headerRow;
    }

    columns.forEach((col, colIdx) => {
        const colName = typeof col === 'string' ? col : (col.name || '');
        const colType = typeof col === 'object' ? col.type : '';

        const headerCell = document.createElement('div');
        headerCell.className = 'accordion-col-header';
        headerCell.dataset.columnIndex = colIdx;

        const nameSpan = document.createElement('span');
        nameSpan.className = 'accordion-col-name';
        nameSpan.textContent = colName;
        headerCell.appendChild(nameSpan);

        if (colType) {
            const typeSpan = document.createElement('span');
            typeSpan.className = 'accordion-col-type';
            typeSpan.textContent = colType;
            headerCell.appendChild(typeSpan);
        }

        // Optional click handler for interactive mode
        if (options.onColumnClick) {
            headerCell.addEventListener('click', (e) => {
                e.stopPropagation();
                options.onColumnClick(headerCell, colName, colIdx);
            });
        }

        headerRow.appendChild(headerCell);
    });

    return headerRow;
}

/**
 * Create a data row with sample/fake data
 * 
 * @param {Array} columns - Array of column objects with name and optional type
 * @param {number} rowIdx - Row index
 * @returns {HTMLElement} The data row element
 */
function createAccordionDataRow(columns, rowIdx) {
    const row = document.createElement('div');
    row.className = 'accordion-data-row';
    row.dataset.rowIndex = rowIdx;

    if (!columns || columns.length === 0) {
        const emptyCell = document.createElement('div');
        emptyCell.className = 'accordion-data-cell accordion-empty-cell';
        emptyCell.textContent = '—';
        row.appendChild(emptyCell);
        return row;
    }

    columns.forEach((col, colIdx) => {
        const colType = typeof col === 'object' ? (col.type || '').toLowerCase() : '';
        const fakeValue = generateFakeData(colType, rowIdx, colIdx);

        const cell = document.createElement('div');
        cell.className = `accordion-data-cell cell-type-${colType || 'unknown'}`;
        cell.textContent = fakeValue;
        cell.dataset.columnIndex = colIdx;
        row.appendChild(cell);
    });

    return row;
}

/**
 * Create data container with sample rows
 * 
 * @param {Array} columns - Array of column objects
 * @returns {HTMLElement} The data container element
 */
function createAccordionDataContainer(columns) {
    const dataContainer = document.createElement('div');
    dataContainer.className = 'accordion-data-container';

    // Generate sample data rows
    for (let rowIdx = 0; rowIdx < ACCORDION_PREVIEW_ROWS; rowIdx++) {
        const row = createAccordionDataRow(columns, rowIdx);
        dataContainer.appendChild(row);
    }

    return dataContainer;
}

/**
 * Create accordion step header element with ARIA attributes
 * 
 * @param {string} type - Transform type (e.g., 'select', 'where')
 * @param {string} label - Label text for the step
 * @param {number} columnCount - Number of columns in this step
 * @param {boolean} isExpanded - Whether the step is currently expanded
 * @param {Function} onToggle - Callback function when header is clicked
 * @returns {Object} Object containing { header, expandIndicator } elements
 */
function createAccordionStepHeader(type, label, columnCount, isExpanded, onToggle) {
    const header = document.createElement('div');
    header.className = 'accordion-step-header';
    header.setAttribute('role', 'button');
    header.setAttribute('tabindex', '0');
    header.setAttribute('aria-expanded', String(isExpanded));
    header.setAttribute('aria-label', `${isExpanded ? 'Collapse' : 'Expand'} ${type.toUpperCase()} step`);

    const headerLeft = document.createElement('div');
    headerLeft.className = 'accordion-header-left';

    const typeBadge = document.createElement('span');
    typeBadge.className = `accordion-step-type type-${type}`;
    typeBadge.textContent = type.toUpperCase().replace('_', ' ');
    headerLeft.appendChild(typeBadge);

    const labelSpan = document.createElement('span');
    labelSpan.className = 'accordion-step-label';
    labelSpan.textContent = label;
    headerLeft.appendChild(labelSpan);

    header.appendChild(headerLeft);

    const headerRight = document.createElement('div');
    headerRight.className = 'accordion-header-right';

    const colCount = document.createElement('span');
    colCount.className = 'accordion-col-count';
    colCount.textContent = `${columnCount} cols`;
    headerRight.appendChild(colCount);

    const expandIndicator = document.createElement('span');
    expandIndicator.className = 'accordion-expand-indicator';
    expandIndicator.textContent = isExpanded ? '▼' : '▶';
    headerRight.appendChild(expandIndicator);

    header.appendChild(headerRight);

    // Click and keyboard handlers
    header.addEventListener('click', onToggle);
    header.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle();
        }
    });

    return { header, expandIndicator };
}

// Export for use in both modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ACCORDION_PREVIEW_ROWS,
        generateFakeData,
        getTransformLabel,
        createAccordionColumnHeaders,
        createAccordionDataRow,
        createAccordionDataContainer,
        createAccordionStepHeader
    };
}
