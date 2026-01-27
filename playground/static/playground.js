/**
 * ASQL Playground JavaScript
 */

// ========== Utility Functions ==========

// Constants for visual editor initialization polling
const MAX_VISUAL_EDITOR_WAIT_ATTEMPTS = 50;
const VISUAL_EDITOR_WAIT_INTERVAL_MS = 50;

const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};

/**
 * Wait for the visual editor to be available and optionally initialized.
 * Returns true if editor is ready, false if timeout occurred.
 */
const waitForVisualEditor = async (requireInitialized = false) => {
    let attempts = 0;
    while (attempts < MAX_VISUAL_EDITOR_WAIT_ATTEMPTS) {
        // Use truthy check since visualEditor can be null
        if (visualEditor) {
            if (!requireInitialized || visualEditor.initialized) {
                return true;
            }
        }
        await new Promise(r => setTimeout(r, VISUAL_EDITOR_WAIT_INTERVAL_MS));
        attempts++;
    }
    return false;
};

// ========== Global Error Handling ==========
function showGlobalError(raw) {
    const errorDiv = document.getElementById('error');
    if (!errorDiv) return;

    // Simple error message extraction
    let simplified = raw;
    if (typeof raw === 'string') {
        // Extract main error message, ignoring stack traces
        const match = raw.match(/^([^\n]+)/);
        simplified = match ? match[1] : raw;
    }

    errorDiv.className = 'error error-banner';
    errorDiv.style.display = 'block';
    errorDiv.textContent = '';

    const title = document.createElement('div');
    title.className = 'error-title';
    title.textContent = "Can't transpile";
    errorDiv.appendChild(title);

    const message = document.createElement('div');
    message.className = 'error-message';
    message.textContent = simplified || 'Unknown error';
    errorDiv.appendChild(message);

    if (raw && simplified && String(raw).trim() !== simplified) {
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = 'Details';
        const pre = document.createElement('pre');
        pre.textContent = String(raw).trim();
        details.appendChild(summary);
        details.appendChild(pre);
        errorDiv.appendChild(details);
    }
}

function hideGlobalError() {
    const errorDiv = document.getElementById('error');
    if (!errorDiv) return;
    errorDiv.style.display = 'none';
    errorDiv.className = '';
    errorDiv.textContent = '';
}

// ========== Global Variables ==========
let inputEditor, outputEditor;

// Example arrays - will be set from EXAMPLES_DATA injected by server
let pipeExamples = [];
let cohortExamples = [];
let samplingExamples = [];
let dataReshapingExamples = [];
let columnOperatorExamples = [];
let countInferenceExamples = [];
let syntaxStylesExamples = [];
let sqlExamples = [];
let visualAsqlExamples = [];

// Settings state
let currentSettings = { compile: {}, style: {} };
let settingsSchemaCache = null;

// Visual mode preference: 'json' or 'visual' (persisted in localStorage)
let visualModePreference = localStorage.getItem('asql_visual_mode') || 'json';
let outputVisualModePreference = localStorage.getItem('asql_output_visual_mode') || 'json';

// Visual style preference: 'text' or 'blocky' (persisted in localStorage)
let visualStylePreference = localStorage.getItem('asql_visual_style') || 'text';

// Show columns preference (persisted in localStorage)
let showColumnsPreference = localStorage.getItem('asql_show_columns') === 'true';

const defaultSettings = {
    compile: {
        auto_spine: true,
        week_start: 'monday',
        relative_date_type: 'timestamp',
        invent_join_keys: true,
        passthrough_comments: true,
        include_transpilation_comments: true
    },
    style: {
        equality: 'single',
        count: 'hash',
        coalesce: 'operator',
        descending: 'prefix',
        cast: 'double_colon',
        quotes: 'double',
        function_shorthand: 'underscore'
    }
};

// ========== Embedding Detection ==========
const isEmbedded = window.ASQL_EMBEDDED || (window.parent !== window && window.parent.location.hostname === window.location.hostname);

if (isEmbedded) {
    document.addEventListener('DOMContentLoaded', function() {
        const container = document.querySelector('.container');
        if (container) {
            container.style.maxWidth = '100%';
            container.style.padding = '0';
            container.style.height = 'auto';
            container.style.minHeight = '100%';
        }
        const backLink = document.querySelector('a[href="/docs/"]');
        if (backLink && window.parent !== window) {
            backLink.style.display = 'none';
        }
    });
}

// ========== Initialize Examples Data ==========
// This function is called from the inline script with EXAMPLES_DATA
window.initializeExamplesData = function(data) {
    pipeExamples = data.pipe || [];
    cohortExamples = data.cohort || [];
    samplingExamples = data.sampling || [];
    dataReshapingExamples = data.reshaping || [];
    columnOperatorExamples = data.column_operators || [];
    countInferenceExamples = data.count_inference || [];
    syntaxStylesExamples = data.syntax_styles || [];
    sqlExamples = data.sql || [];
    visualAsqlExamples = data.visual_asql || [];
};

// Try to load from EXAMPLES_DATA if already defined (inline script ran first)
if (typeof EXAMPLES_DATA !== 'undefined') {
    window.initializeExamplesData(EXAMPLES_DATA);
}

// ========== Examples Modal Functions ==========
function openExamplesModal() {
    const modal = document.getElementById('examples-modal');
    if (modal) {
        modal.classList.add('open');
        document.body.style.overflow = 'hidden';
        setTimeout(() => {
            if (typeof loadExamples === 'function') {
                loadExamples();
            }
        }, 0);
    }
}

function closeExamplesModal(event) {
    if (event && event.target !== document.getElementById('examples-modal')) {
        return;
    }
    const modal = document.getElementById('examples-modal');
    if (modal) {
        modal.classList.remove('open');
        document.body.style.overflow = '';
    }
}

// ========== Settings Modal Functions ==========
function loadSettingsFromStorage() {
    try {
        const stored = localStorage.getItem('asql_playground_settings');
        if (stored) {
            const parsed = JSON.parse(stored);
            currentSettings = {
                compile: { ...defaultSettings.compile, ...(parsed.compile || {}) },
                style: { ...defaultSettings.style, ...(parsed.style || {}) }
            };
        } else {
            currentSettings = JSON.parse(JSON.stringify(defaultSettings));
        }
    } catch (e) {
        console.warn('Failed to load settings from localStorage:', e);
        currentSettings = JSON.parse(JSON.stringify(defaultSettings));
    }
    updateSettingsButton();
}

function saveSettingsToStorage() {
    try {
        const toSave = { compile: {}, style: {} };
        
        for (const [key, value] of Object.entries(currentSettings.compile)) {
            if (value !== defaultSettings.compile[key]) {
                toSave.compile[key] = value;
            }
        }
        for (const [key, value] of Object.entries(currentSettings.style)) {
            if (value !== defaultSettings.style[key]) {
                toSave.style[key] = value;
            }
        }
        
        if (Object.keys(toSave.compile).length > 0 || Object.keys(toSave.style).length > 0) {
            localStorage.setItem('asql_playground_settings', JSON.stringify(toSave));
        } else {
            localStorage.removeItem('asql_playground_settings');
        }
    } catch (e) {
        console.warn('Failed to save settings to localStorage:', e);
    }
    updateSettingsButton();
    updateModifiedIndicator();
}

function hasModifiedSettings() {
    for (const [key, value] of Object.entries(currentSettings.compile)) {
        if (value !== defaultSettings.compile[key]) return true;
    }
    for (const [key, value] of Object.entries(currentSettings.style)) {
        if (value !== defaultSettings.style[key]) return true;
    }
    return false;
}

function updateSettingsButton() {
    const btn = document.getElementById('settings-btn');
    if (btn) {
        btn.classList.toggle('has-changes', hasModifiedSettings());
    }
}

function updateModifiedIndicator() {
    const indicator = document.getElementById('settings-modified');
    if (indicator) {
        indicator.classList.toggle('visible', hasModifiedSettings());
    }
}

async function openSettingsModal() {
    const modal = document.getElementById('settings-modal');
    if (modal) {
        modal.classList.add('open');
        document.body.style.overflow = 'hidden';
        await renderSettingsForm();
        updateModifiedIndicator();
    }
}

function closeSettingsModal(event) {
    if (event && event.target !== document.getElementById('settings-modal')) {
        return;
    }
    const modal = document.getElementById('settings-modal');
    if (modal) {
        modal.classList.remove('open');
        document.body.style.overflow = '';
    }
}

async function fetchSettingsSchema() {
    if (settingsSchemaCache) return settingsSchemaCache;
    
    try {
        const response = await fetch('/api/settings-schema');
        if (response.ok) {
            settingsSchemaCache = await response.json();
            return settingsSchemaCache;
        }
    } catch (e) {
        console.warn('Failed to fetch settings schema:', e);
    }
    return null;
}

async function renderSettingsForm() {
    const compileGrid = document.getElementById('compile-settings-grid');
    const styleGrid = document.getElementById('style-settings-grid');
    
    if (!compileGrid || !styleGrid) return;
    
    compileGrid.innerHTML = '';
    styleGrid.innerHTML = '';
    
    const schema = await fetchSettingsSchema();
    
    if (schema) {
        const sortFields = (fields) => [...fields].sort((a, b) => {
            if (a.type === 'boolean' && b.type !== 'boolean') return -1;
            if (a.type !== 'boolean' && b.type === 'boolean') return 1;
            return 0;
        });
        
        if (schema.compile && schema.compile.fields) {
            sortFields(schema.compile.fields).forEach(field => {
                compileGrid.appendChild(createSettingField(field, 'compile'));
            });
        }
        
        if (schema.style && schema.style.fields) {
            sortFields(schema.style.fields).forEach(field => {
                styleGrid.appendChild(createSettingField(field, 'style'));
            });
        }
    } else {
        compileGrid.innerHTML = '<p style="color: #999;">Failed to load settings</p>';
    }
}

function createSettingField(field, category) {
    const container = document.createElement('div');
    container.className = 'setting-field' + (field.type === 'boolean' ? ' setting-field-checkbox' : '');
    
    const currentValue = currentSettings[category][field.name];
    
    if (field.type === 'boolean') {
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `setting-${category}-${field.name}`;
        checkbox.checked = currentValue;
        checkbox.addEventListener('change', () => {
            currentSettings[category][field.name] = checkbox.checked;
            onSettingChanged();
        });
        
        const label = document.createElement('label');
        label.htmlFor = checkbox.id;
        label.textContent = field.label;
        
        container.appendChild(checkbox);
        container.appendChild(label);
    } else if (field.type === 'select') {
        const label = document.createElement('label');
        label.htmlFor = `setting-${category}-${field.name}`;
        label.textContent = field.label;
        
        const select = document.createElement('select');
        select.id = `setting-${category}-${field.name}`;
        
        field.options.forEach(opt => {
            const option = document.createElement('option');
            if (typeof opt === 'object') {
                option.value = opt.value;
                option.textContent = opt.label;
            } else {
                option.value = opt;
                option.textContent = opt;
            }
            if (option.value === currentValue) {
                option.selected = true;
            }
            select.appendChild(option);
        });
        
        select.addEventListener('change', () => {
            currentSettings[category][field.name] = select.value;
            onSettingChanged();
        });
        
        container.appendChild(label);
        container.appendChild(select);
    }
    
    if (field.description) {
        const desc = document.createElement('div');
        desc.className = 'setting-description';
        desc.textContent = field.description;
        container.appendChild(desc);
    }
    
    return container;
}

function onSettingChanged() {
    saveSettingsToStorage();
    if (typeof translateQuery === 'function') {
        translateQuery();
    }
}

async function resetSettings() {
    currentSettings = JSON.parse(JSON.stringify(defaultSettings));
    saveSettingsToStorage();
    await renderSettingsForm();
    if (typeof translateQuery === 'function') {
        translateQuery();
    }
    showToast('Settings reset to defaults');
}

function getCompileSettings() {
    const settings = {};
    for (const [key, value] of Object.entries(currentSettings.compile)) {
        if (value !== defaultSettings.compile[key]) {
            settings[key] = value;
        }
    }
    return settings;
}

function getStyleSettings() {
    const settings = {};
    for (const [key, value] of Object.entries(currentSettings.style)) {
        if (value !== defaultSettings.style[key]) {
            settings[key] = value;
        }
    }
    return settings;
}

// ========== UI Functions ==========
async function swapLanguages() {
    const fromSelect = document.getElementById('from-dialect');
    const toSelect = document.getElementById('to-dialect');
    if (!fromSelect || !toSelect || !inputEditor || !outputEditor) {
        return;
    }
    
    const fromValue = fromSelect.value;
    const toValue = toSelect.value;

    // Prevent visual editor sync from overwriting swapped content
    isSwapping = true;

    try {
        // Handle Visual ASQL conversion during swap
        if (fromValue === 'visual-asql') {
            // Swapping FROM Visual ASQL: output SQL becomes input, Visual ASQL becomes output
            // The output already has SQL text, and we need to convert our JSON to ASQL for the new output
            const outputSql = outputEditor.getValue();
            const inputJson = inputEditor.getValue();
            
            fromSelect.value = toValue;
            toSelect.value = fromValue;
            
            inputEditor.setValue(outputSql);
            outputEditor.setValue(inputJson);
            
        } else if (toValue === 'visual-asql') {
            // Swapping TO Visual ASQL as output: need to convert SQL input to Visual JSON
            // After swap, Visual ASQL will be input, so we need to convert current input SQL to JSON
            const currentInputSql = inputEditor.getValue();
            const currentOutputJson = outputEditor.getValue();
            
            // Convert the current input SQL to Visual ASQL JSON
            const response = await fetch('/api/visual/parse-sql', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    sql: currentInputSql, 
                    dialect: fromValue 
                })
            });
            const data = await response.json();
            
            if (!data.success) {
                console.error('Failed to convert SQL to Visual ASQL:', data.error);
                showOutputError('Swap failed: ' + data.error);
                isSwapping = false;
                return;
            }
            
            fromSelect.value = toValue;
            toSelect.value = fromValue;
            
            // The converted JSON goes into input (now Visual ASQL)
            // The old output (which was JSON) goes into output (now SQL dialect)
            inputEditor.setValue(JSON.stringify(data.query, null, 2));
            outputEditor.setValue(currentOutputJson);
            
        } else {
            // Normal swap - no Visual ASQL involved
            fromSelect.value = toValue;
            toSelect.value = fromValue;

            const temp = inputEditor.getValue();
            inputEditor.setValue(outputEditor.getValue());
            outputEditor.setValue(temp);
        }

        // Update the dialect tracking for auto-transpile
        currentInputDialect = toValue;
        fromSelect.dataset.previousValue = toValue;

        // Wait for UI updates to complete before resetting swap flag
        await updateUITitles();
        
    } finally {
        // Reset the swap flag after UI updates are done
        isSwapping = false;
    }
    
    translateQuery();
}

function ensureFromNotPostgresWhenToEmpty() {
    const fromDialect = document.getElementById('from-dialect').value;
    const toDialect = document.getElementById('to-dialect').value;
    
    if (!toDialect && (fromDialect === 'postgres' || fromDialect === 'postgresql')) {
        document.getElementById('from-dialect').value = 'asql';
    }
}

async function updateUITitles() {
    if (!inputEditor || !outputEditor) return;
    
    ensureFromNotPostgresWhenToEmpty();
    
    const fromDialect = document.getElementById('from-dialect').value;
    const toDialect = document.getElementById('to-dialect').value;
    
    // Handle input panel editor switching
    try {
        await updateEditorVisibility('input', fromDialect);
    } catch (err) {
        console.warn('Failed to update input editor visibility', err);
    }
    
    // Handle output panel editor switching
    try {
        await updateEditorVisibility('output', toDialect);
    } catch (err) {
        console.warn('Failed to update output editor visibility', err);
    }
    
    // Set CodeMirror modes for text editors
    if (fromDialect === 'visual-asql') {
        inputEditor.setOption('mode', 'application/json');
    } else if (fromDialect === 'asql') {
        inputEditor.setOption('mode', 'text/x-asql');
    } else {
        inputEditor.setOption('mode', 'text/x-sql');
    }
    
    if (toDialect === 'visual-asql') {
        outputEditor.setOption('mode', 'application/json');
    } else if (toDialect === 'asql') {
        outputEditor.setOption('mode', 'text/x-asql');
    } else {
        outputEditor.setOption('mode', 'text/x-sql');
    }
}

// Switch between text and visual editors based on dialect
async function updateEditorVisibility(panel, dialect) {
    // Check the data-editor attribute on the selected option
    const selectId = panel === 'input' ? 'from-dialect' : 'to-dialect';
    const select = document.getElementById(selectId);
    const selectedOption = select?.options[select.selectedIndex];
    const editorType = selectedOption?.dataset?.editor || 'text';
    const isVisualDialect = editorType === 'visual';
    
    if (panel === 'input') {
        const textContainer = document.getElementById('input-editor-container');
        const visualContainer = document.getElementById('visual-editor-container');
        const modeToggle = document.getElementById('visual-mode-toggle');
        const styleToggle = document.getElementById('visual-style-toggle');
        const columnsToggle = document.getElementById('show-columns-toggle');
        
        if (!textContainer || !visualContainer) return;
        
        if (isVisualDialect) {
            // Show the mode toggle for visual-asql
            if (modeToggle) modeToggle.style.display = 'flex';
            // Show style and columns toggles only when in visual block mode
            const showExtras = visualModePreference === 'visual';
            if (styleToggle) styleToggle.style.display = showExtras ? 'flex' : 'none';
            if (columnsToggle) columnsToggle.style.display = showExtras ? 'flex' : 'none';
            
            // Use the stored preference to determine which view to show
            const showVisualBlocks = visualModePreference === 'visual';
            
            if (showVisualBlocks) {
                // Wait for visual editor to exist and initialize if needed
                await waitForVisualEditor();
                if (visualEditor && !visualEditor.initialized) {
                    await visualEditor.init();
                }
                
                // Switch to visual blocks mode
                const currentContent = inputEditor.getValue();
                textContainer.style.display = 'none';
                visualContainer.style.display = 'block';
                
                // If content looks like JSON, parse it; otherwise treat as ASQL
                if (currentContent.trim() && visualEditor) {
                    const trimmed = currentContent.trim();
                    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
                        // It's JSON - load directly
                        try {
                            const json = JSON.parse(currentContent);
                            await visualEditor.loadFromJSON(json);
                        } catch (e) {
                            await visualEditor.loadFromASQL(currentContent);
                        }
                    } else {
                        await visualEditor.loadFromASQL(currentContent);
                    }
                }
            } else {
                // Stay in JSON text mode
                textContainer.style.display = 'block';
                visualContainer.style.display = 'none';
                
                // Set editor to JSON mode
                inputEditor.setOption('mode', 'application/json');
            }
            
            updateVisualModeToggleButtons();
        } else {
            // Hide the mode toggle for non-visual dialects
            if (modeToggle) modeToggle.style.display = 'none';
            if (styleToggle) styleToggle.style.display = 'none';
            if (columnsToggle) columnsToggle.style.display = 'none';
            
            // Switch to text mode - sync content from visual editor if it was showing
            // BUT skip this during a swap operation, as the swapped content should be preserved
            if (!isSwapping && visualContainer.style.display !== 'none' && visualEditor) {
                const asql = await visualEditor.getASQL();
                if (asql) {
                    inputEditor.setValue(asql);
                }
            }
            textContainer.style.display = 'block';
            visualContainer.style.display = 'none';
            
            // Reset editor mode based on dialect
            const mode = dialect === 'asql' ? 'text/x-asql' : 'text/x-sql';
            inputEditor.setOption('mode', mode);
        }
    } else if (panel === 'output') {
        const textContainer = document.getElementById('output-editor-container');
        const visualContainer = document.getElementById('output-visual-editor-container');
        const modeToggle = document.getElementById('output-visual-mode-toggle');
        const styleToggle = document.getElementById('output-visual-style-toggle');
        const columnsToggle = document.getElementById('output-show-columns-toggle');
        
        if (!textContainer || !visualContainer) return;
        
        if (isVisualDialect) {
            // Show the mode toggle for visual-asql output
            if (modeToggle) modeToggle.style.display = 'flex';
            // Show style and columns toggles only when in visual block mode
            const showExtras = outputVisualModePreference === 'visual';
            if (styleToggle) styleToggle.style.display = showExtras ? 'flex' : 'none';
            if (columnsToggle) columnsToggle.style.display = showExtras ? 'flex' : 'none';
            
            // Use the stored preference to determine which view to show
            const showVisualBlocks = outputVisualModePreference === 'visual';
            
            if (showVisualBlocks) {
                textContainer.style.display = 'none';
                visualContainer.style.display = 'block';
                // Render the visual blocks from the current JSON output
                const currentOutput = outputEditor.getValue().trim();
                if (currentOutput.startsWith('{') || currentOutput.startsWith('[')) {
                    try {
                        const json = JSON.parse(currentOutput);
                        renderOutputVisual(json);
                    } catch (e) {
                        console.warn('Failed to parse output JSON for visual view:', e);
                    }
                }
            } else {
                textContainer.style.display = 'block';
                visualContainer.style.display = 'none';
                outputEditor.setOption('mode', 'application/json');
            }
            updateOutputVisualModeToggleButtons();
        } else {
            // Hide toggle for non-visual dialects
            if (modeToggle) modeToggle.style.display = 'none';
            if (styleToggle) styleToggle.style.display = 'none';
            if (columnsToggle) columnsToggle.style.display = 'none';
            textContainer.style.display = 'block';
            visualContainer.style.display = 'none';
        }
    }
}

// Update the visual mode toggle button states
function updateVisualModeToggleButtons() {
    const jsonBtn = document.getElementById('json-view-btn');
    const visualBtn = document.getElementById('visual-view-btn');
    const styleToggle = document.getElementById('visual-style-toggle');
    const columnsToggle = document.getElementById('show-columns-toggle');
    
    if (jsonBtn && visualBtn) {
        if (visualModePreference === 'json') {
            jsonBtn.classList.add('active');
            visualBtn.classList.remove('active');
        } else {
            jsonBtn.classList.remove('active');
            visualBtn.classList.add('active');
        }
    }
    
    // Show/hide style toggle and columns toggle based on mode
    const fromDialect = document.getElementById('from-dialect')?.value || '';
    const isVisual = fromDialect === 'visual-asql' && visualModePreference === 'visual';
    
    if (styleToggle) {
        styleToggle.style.display = isVisual ? 'flex' : 'none';
    }
    if (columnsToggle) {
        columnsToggle.style.display = isVisual ? 'flex' : 'none';
    }
}

// Switch visual mode preference (input)
async function setVisualModePreference(mode) {
    visualModePreference = mode;
    localStorage.setItem('asql_visual_mode', mode);
    updateVisualModeToggleButtons();
    
    // Re-apply the editor visibility
    const fromDialect = document.getElementById('from-dialect')?.value || '';
    await updateEditorVisibility('input', fromDialect);
}

// Update the output visual mode toggle button states
function updateOutputVisualModeToggleButtons() {
    const jsonBtn = document.getElementById('output-json-view-btn');
    const visualBtn = document.getElementById('output-visual-view-btn');
    const styleToggle = document.getElementById('output-visual-style-toggle');
    const columnsToggle = document.getElementById('output-show-columns-toggle');
    
    if (jsonBtn && visualBtn) {
        if (outputVisualModePreference === 'json') {
            jsonBtn.classList.add('active');
            visualBtn.classList.remove('active');
        } else {
            jsonBtn.classList.remove('active');
            visualBtn.classList.add('active');
        }
    }
    
    // Show/hide style toggle and columns toggle based on mode
    const toDialect = document.getElementById('to-dialect')?.value || '';
    const isVisual = toDialect === 'visual-asql' && outputVisualModePreference === 'visual';
    
    if (styleToggle) {
        styleToggle.style.display = isVisual ? 'flex' : 'none';
    }
    if (columnsToggle) {
        columnsToggle.style.display = isVisual ? 'flex' : 'none';
    }
}

// Switch output visual mode preference
async function setOutputVisualModePreference(mode) {
    outputVisualModePreference = mode;
    localStorage.setItem('asql_output_visual_mode', mode);
    updateOutputVisualModeToggleButtons();
    
    // Re-apply the editor visibility
    const toDialect = document.getElementById('to-dialect')?.value || '';
    await updateEditorVisibility('output', toDialect);
}

// Update visual style toggle button states
function updateVisualStyleToggleButtons() {
    const blockyBtn = document.getElementById('blocky-style-btn');
    const textBtn = document.getElementById('text-style-btn');
    const pipesBtn = document.getElementById('pipes-style-btn');
    const accordionBtn = document.getElementById('accordion-style-btn');
    const outputBlockyBtn = document.getElementById('output-blocky-style-btn');
    const outputTextBtn = document.getElementById('output-text-style-btn');
    const outputPipesBtn = document.getElementById('output-pipes-style-btn');
    const outputAccordionBtn = document.getElementById('output-accordion-style-btn');

    // Input panel
    if (blockyBtn && textBtn && pipesBtn) {
        blockyBtn.classList.toggle('active', visualStylePreference === 'blocky');
        textBtn.classList.toggle('active', visualStylePreference === 'text');
        pipesBtn.classList.toggle('active', visualStylePreference === 'pipes');
        if (accordionBtn) accordionBtn.classList.toggle('active', visualStylePreference === 'accordion');
    }

    // Output panel (uses same preference)
    if (outputBlockyBtn && outputTextBtn && outputPipesBtn) {
        outputBlockyBtn.classList.toggle('active', visualStylePreference === 'blocky');
        outputTextBtn.classList.toggle('active', visualStylePreference === 'text');
        outputPipesBtn.classList.toggle('active', visualStylePreference === 'pipes');
        if (outputAccordionBtn) outputAccordionBtn.classList.toggle('active', visualStylePreference === 'accordion');
    }
}

// Switch visual style preference (blocky vs text vs pipes vs accordion)
function setVisualStylePreference(style) {
    const previousStyle = visualStylePreference;
    visualStylePreference = style;
    localStorage.setItem('asql_visual_style', style);
    updateVisualStyleToggleButtons();
    applyVisualStyle();

    // Re-render when switching to/from modes that need different DOM structure (pipes, accordion)
    const specialModes = ['pipes', 'accordion'];
    const switchingToSpecial = specialModes.includes(style) && !specialModes.includes(previousStyle);
    const switchingFromSpecial = !specialModes.includes(style) && specialModes.includes(previousStyle);
    const switchingBetweenSpecial = specialModes.includes(style) && specialModes.includes(previousStyle) && style !== previousStyle;

    if (switchingToSpecial || switchingFromSpecial || switchingBetweenSpecial) {
        // Re-render input visual editor for mode change
        if (typeof visualEditor !== 'undefined' && visualEditor && visualEditor.renderAll) {
            visualEditor.renderAll();
        }

        // Re-render visual output for mode change
        if (lastRenderedQuery) {
            if (style === 'pipes') {
                renderPipesView(lastRenderedQuery);
            } else if (style === 'accordion') {
                renderAccordionView(lastRenderedQuery);
            } else {
                renderOutputVisual(lastRenderedQuery);
            }
        }
    }
}

// Track last rendered query for pipes mode re-renders
let lastRenderedQuery = null;

// Apply visual style class to containers
function applyVisualStyle() {
    const inputVisualContainer = document.getElementById('visual-editor-container');
    const outputVisualContainer = document.getElementById('output-visual-editor-container');

    const allStyles = ['visual-style-text', 'visual-style-blocky', 'visual-style-pipes', 'visual-style-accordion'];
    const className = `visual-style-${visualStylePreference}`;

    if (inputVisualContainer) {
        allStyles.forEach(s => inputVisualContainer.classList.remove(s));
        inputVisualContainer.classList.add(className);
    }
    if (outputVisualContainer) {
        allStyles.forEach(s => outputVisualContainer.classList.remove(s));
        outputVisualContainer.classList.add(className);
    }
}

// Update show columns toggle button states
function updateShowColumnsToggleButtons() {
    const inputBtn = document.getElementById('show-columns-btn');
    const outputBtn = document.getElementById('output-show-columns-btn');
    
    if (inputBtn) {
        if (showColumnsPreference) {
            inputBtn.classList.add('active');
        } else {
            inputBtn.classList.remove('active');
        }
    }
    if (outputBtn) {
        if (showColumnsPreference) {
            outputBtn.classList.add('active');
        } else {
            outputBtn.classList.remove('active');
        }
    }
}

// Toggle show columns preference
function toggleShowColumns() {
    showColumnsPreference = !showColumnsPreference;
    localStorage.setItem('asql_show_columns', showColumnsPreference);
    updateShowColumnsToggleButtons();
    applyShowColumns();
}

// Apply show columns class to containers
function applyShowColumns() {
    const inputVisualContainer = document.getElementById('visual-editor-container');
    const outputVisualContainer = document.getElementById('output-visual-editor-container');
    
    if (inputVisualContainer) {
        if (showColumnsPreference) {
            inputVisualContainer.classList.add('show-columns');
        } else {
            inputVisualContainer.classList.remove('show-columns');
        }
    }
    if (outputVisualContainer) {
        if (showColumnsPreference) {
            outputVisualContainer.classList.add('show-columns');
        } else {
            outputVisualContainer.classList.remove('show-columns');
        }
    }
}

// Check if a dialect uses the visual editor
function isVisualDialect(selectId) {
    const select = document.getElementById(selectId);
    const selectedOption = select?.options[select.selectedIndex];
    return selectedOption?.dataset?.editor === 'visual';
}

function showToast(message) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
}

function copyInput() {
    if (!inputEditor) return;
    navigator.clipboard.writeText(inputEditor.getValue())
        .then(() => showToast('Copied!'))
        .catch(() => showToast('Failed to copy'));
}

function copyOutput() {
    if (!outputEditor) return;
    navigator.clipboard.writeText(outputEditor.getValue())
        .then(() => showToast('Copied!'))
        .catch(() => showToast('Failed to copy'));
}

// ========== Translation Functions ==========
function getCurrentMode() {
    try {
        const fromSelect = document.getElementById('from-dialect');
        const toSelect = document.getElementById('to-dialect');
        
        if (!fromSelect || !toSelect) return 'asql-to-sql';
        
        const fromDialect = fromSelect.value;
        const toDialect = toSelect.value;
        
        // Treat visual-asql as asql for mode detection
        const fromIsAsql = fromDialect === 'asql' || fromDialect === 'visual-asql';
        const toIsAsql = toDialect === 'asql' || toDialect === 'visual-asql';
        
        if (fromIsAsql && !toIsAsql) return 'asql-to-sql';
        if (!fromIsAsql && toIsAsql) return 'sql-to-asql';
        if (fromIsAsql && toIsAsql) return 'asql-to-asql';
        return 'sql-to-sql';
    } catch (error) {
        console.error('Error getting current mode:', error);
        return 'asql-to-sql';
    }
}

// Get the actual dialect to send to the API (visual-asql -> asql)
function getApiDialect(dialect) {
    if (dialect === 'visual-asql') return 'asql';
    return dialect;
}

// Track what dialect the current input is in (for transpiling when From changes)
let currentInputDialect = null;

// Flag to prevent visual editor sync during swap operations
let isSwapping = false;

// Transpile the input text to a new dialect when "From" changes
async function transpileInputToNewDialect(currentInput, newDialect) {
    // Detect if current input looks like JSON (visual-asql)
    const isJSON = currentInput.startsWith('{') || currentInput.startsWith('[');
    
    // Determine what the current input dialect likely is
    const previousFromDialect = currentInputDialect || document.getElementById('from-dialect').dataset.previousValue || 'asql';
    const previousIsAsql = previousFromDialect === 'asql' || previousFromDialect === 'visual-asql';
    const newIsAsql = newDialect === 'asql' || newDialect === 'visual-asql';
    
    // Store the new dialect as current
    currentInputDialect = newDialect;
    document.getElementById('from-dialect').dataset.previousValue = newDialect;
    
    if (newDialect === 'visual-asql') {
        // Convert to JSON
        let asqlText = currentInput;
        
        // If previous was SQL, first convert to ASQL
        if (!previousIsAsql && !isJSON) {
            const reverseResponse = await fetch('/api/reverse-compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sql: currentInput, source_dialect: previousFromDialect || '' })
            });
            const reverseData = await reverseResponse.json();
            if (reverseData.error) throw new Error(reverseData.error);
            asqlText = reverseData.asql;
        }
        
        // Now convert ASQL to JSON
        const response = await fetch('/api/visual/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asql: asqlText })
        });
        const data = await response.json();
        if (data.success) {
            inputEditor.setValue(JSON.stringify(data.query, null, 2));
            inputEditor.setOption('mode', 'application/json');
        } else {
            throw new Error(data.error || 'Failed to parse to visual');
        }
    } else if (newDialect === 'asql') {
        // Convert to ASQL text
        if (isJSON) {
            // JSON to ASQL
            const json = JSON.parse(currentInput);
            const response = await fetch('/api/visual/compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: json })
            });
            const data = await response.json();
            if (data.success) {
                inputEditor.setValue(data.asql);
                inputEditor.setOption('mode', 'text/x-asql');
            } else {
                throw new Error(data.error || 'Failed to compile from visual');
            }
        } else if (!previousIsAsql) {
            // SQL to ASQL
            const response = await fetch('/api/reverse-compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sql: currentInput, source_dialect: previousFromDialect || '' })
            });
            const data = await response.json();
            if (data.asql) {
                inputEditor.setValue(data.asql);
                inputEditor.setOption('mode', 'text/x-asql');
            } else {
                throw new Error(data.error || 'Failed to convert to ASQL');
            }
        }
        // If already ASQL, nothing to do
    } else {
        // Converting to a SQL dialect
        let asqlText = currentInput;
        
        // First get to ASQL if needed
        if (isJSON) {
            const json = JSON.parse(currentInput);
            const response = await fetch('/api/visual/compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: json })
            });
            const data = await response.json();
            if (!data.success) throw new Error(data.error || 'Failed to compile from visual');
            asqlText = data.asql;
        } else if (!previousIsAsql) {
            // SQL to ASQL first
            const reverseResponse = await fetch('/api/reverse-compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sql: currentInput, source_dialect: previousFromDialect || '' })
            });
            const reverseData = await reverseResponse.json();
            if (reverseData.error) throw new Error(reverseData.error);
            asqlText = reverseData.asql;
        }
        
        // Now compile ASQL to target SQL dialect
        const compileResponse = await fetch('/api/compile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asql: asqlText, dialect: newDialect })
        });
        const compileData = await compileResponse.json();
        if (compileData.sql) {
            inputEditor.setValue(compileData.sql);
            inputEditor.setOption('mode', 'text/x-sql');
        } else {
            throw new Error(compileData.error || 'Failed to compile to SQL');
        }
    }
}

function updateURL() {
    if (!inputEditor) return;
    
    const fromDialect = document.getElementById('from-dialect').value || 'asql';
    const toDialect = document.getElementById('to-dialect').value || '';
    const inputQuery = inputEditor.getValue();
    const outputQuery = outputEditor ? outputEditor.getValue() : '';
    
    const params = new URLSearchParams();
    
    if (fromDialect === 'asql') {
        params.set('d_f', 'ASQL');
    } else if (fromDialect) {
        params.set('d_f', fromDialect);
    }
    
    if (toDialect) {
        params.set('d_t', toDialect === 'asql' ? 'ASQL' : toDialect);
    }
    
    if (inputQuery && inputQuery.trim()) {
        params.set('sql_f', encodeURIComponent(inputQuery));
    }
    
    if (outputQuery && outputQuery.trim()) {
        params.set('sql_t', encodeURIComponent(outputQuery));
    }
    
    const newURL = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
    window.history.pushState({}, '', newURL);
}

async function translateQuery() {
    const input = inputEditor.getValue();
    const errorDiv = document.getElementById('error');
    const detectedDialectSpan = document.getElementById('detected-dialect');
    
    outputEditor.setValue('');
    errorDiv.style.display = 'none';
    errorDiv.className = '';
    errorDiv.textContent = '';
    detectedDialectSpan.style.display = 'none';
    
    if (!input.trim()) return;
    
    const currentMode = getCurrentMode();
    const fromDialect = document.getElementById('from-dialect').value;
    const toDialect = document.getElementById('to-dialect').value;

    const simplifyErrorMessage = (raw) => {
        if (!raw) return '';
        let cleaned = String(raw).replace(/\x1b\[[0-9;]*m/g, '');
        const wrappers = [/^Error:\s*/i, /^Compilation Error:\s*/i, /^Syntax Error:\s*/i, /^Reverse compilation error:\s*/i];
        let changed = true;
        while (changed) {
            changed = false;
            for (const re of wrappers) {
                if (re.test(cleaned)) {
                    cleaned = cleaned.replace(re, '');
                    changed = true;
                }
            }
        }
        return cleaned.trim();
    };

    const showError = (raw) => {
        const simplified = simplifyErrorMessage(raw);
        errorDiv.className = 'error error-banner';
        errorDiv.style.display = 'block';
        errorDiv.textContent = '';

        const title = document.createElement('div');
        title.className = 'error-title';
        title.textContent = "Can't transpile";
        errorDiv.appendChild(title);

        const message = document.createElement('div');
        message.className = 'error-message';
        message.textContent = simplified || 'Unknown error';
        errorDiv.appendChild(message);

        if (raw && simplified && String(raw).trim() !== simplified) {
            const details = document.createElement('details');
            const summary = document.createElement('summary');
            summary.textContent = 'Details';
            const pre = document.createElement('pre');
            pre.textContent = String(raw).trim();
            details.appendChild(summary);
            details.appendChild(pre);
            errorDiv.appendChild(details);
        }
    };
    
    const hideError = () => {
        errorDiv.style.display = 'none';
        errorDiv.className = '';
        errorDiv.textContent = '';
    };
    
    try {
        if (currentMode === 'asql-to-sql') {
            // If output is visual-asql, parse to visual representation
            if (toDialect === 'visual-asql') {
                const response = await fetch('/api/visual/parse', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ asql: input })
                });
                
                if (!response.ok) {
                    showError(`HTTP Error ${response.status}`);
                    return;
                }
                
                const data = await response.json();
                if (!data.success) {
                    showError(data.error || 'Failed to parse ASQL');
                } else {
                    // Show JSON in text editor
                    outputEditor.setValue(JSON.stringify(data.query, null, 2));
                    outputEditor.setOption('mode', 'application/json');
                    // Also render to visual editor (for toggle)
                    renderOutputVisual(data.query);
                    updateURL();
                }
            } else {
                // Normal SQL output
                let asqlInput = input;
                
                // If input is visual-asql (JSON), convert to ASQL text first
                if (fromDialect === 'visual-asql') {
                    const inputIsJSON = input.trim().startsWith('{') || input.trim().startsWith('[');
                    if (inputIsJSON) {
                        try {
                            const jsonData = JSON.parse(input);
                            const compileResponse = await fetch('/api/visual/compile', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ query: jsonData })
                            });
                            const compileData = await compileResponse.json();
                            if (!compileData.success) {
                                showError(compileData.error || 'Failed to convert visual query');
                                return;
                            }
                            asqlInput = compileData.asql;
                        } catch (e) {
                            showError('Invalid JSON in visual-asql input: ' + e.message);
                            return;
                        }
                    }
                }
                
                const compileSettings = getCompileSettings();
                const response = await fetch('/api/compile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ asql: asqlInput, dialect: getApiDialect(toDialect) || '', settings: compileSettings })
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    errorDiv.textContent = `HTTP Error ${response.status}: ${errorText}`;
                    errorDiv.className = 'error';
                    errorDiv.style.display = 'block';
                    return;
                }
                
                const data = await response.json();
                if (data.error) {
                    showError(data.error);
                } else if (data.sql) {
                    outputEditor.setValue(data.sql);
                    updateURL();
                }
            }
        } else if (currentMode === 'sql-to-asql') {
            let sourceDialect = fromDialect;
            
            if (!sourceDialect) {
                const detectResponse = await fetch('/api/detect-dialect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sql: input })
                });
                const detectData = await detectResponse.json();
                if (detectData.dialect) {
                    sourceDialect = detectData.dialect;
                    detectedDialectSpan.textContent = `Detected: ${sourceDialect}`;
                    detectedDialectSpan.style.display = 'inline';
                }
            }
            
            // If output is visual-asql, use direct SQL -> Visual JSON conversion
            // This bypasses ASQL text intermediate and handles CTEs better
            if (toDialect === 'visual-asql') {
                const parseResponse = await fetch('/api/visual/parse-sql', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sql: input, dialect: sourceDialect || '' })
                });
                
                const parseData = await parseResponse.json();
                if (!parseData.success) {
                    showError(parseData.error || 'Failed to convert SQL to visual format');
                } else {
                    // Show JSON in text editor
                    outputEditor.setValue(JSON.stringify(parseData.query, null, 2));
                    outputEditor.setOption('mode', 'application/json');
                    // Also render to visual editor (for toggle)
                    renderOutputVisual(parseData.query);
                    updateURL();
                }
            } else {
                // Normal ASQL text output - use reverse-compile
                const styleSettings = getStyleSettings();
                const response = await fetch('/api/reverse-compile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sql: input, source_dialect: sourceDialect || '', settings: styleSettings })
                });
                
                const data = await response.json();
                if (data.error) {
                    showError(data.error);
                } else {
                    outputEditor.setValue(data.asql);
                    updateURL();
                }
            }
        } else if (currentMode === 'sql-to-sql') {
            let sourceDialect = fromDialect;
            
            if (!sourceDialect) {
                const detectResponse = await fetch('/api/detect-dialect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sql: input })
                });
                const detectData = await detectResponse.json();
                if (detectData.dialect) {
                    sourceDialect = detectData.dialect;
                    detectedDialectSpan.textContent = `Detected: ${sourceDialect}`;
                    detectedDialectSpan.style.display = 'inline';
                }
            }
            
            const styleSettings = getStyleSettings();
            const reverseResponse = await fetch('/api/reverse-compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sql: input, source_dialect: sourceDialect || '', settings: styleSettings })
            });
            
            // If output is visual-asql, use direct SQL -> Visual JSON conversion
            // This bypasses ASQL text and preserves CTEs/window functions better
            if (toDialect === 'visual-asql') {
                const parseResponse = await fetch('/api/visual/parse-sql', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sql: input, dialect: sourceDialect || '' })
                });
                
                const parseData = await parseResponse.json();
                if (!parseData.success) {
                    showError(parseData.error || 'Failed to convert SQL to visual format');
                } else {
                    // Show JSON in text editor
                    outputEditor.setValue(JSON.stringify(parseData.query, null, 2));
                    outputEditor.setOption('mode', 'application/json');
                    // Also render to visual editor (for toggle)
                    renderOutputVisual(parseData.query);
                    updateURL();
                }
                return;
            }
            
            const reverseData = await reverseResponse.json();
            if (reverseData.error) {
                showError(reverseData.error);
                return;
            }
            
            // For non-visual output dialects
            const compileSettings = getCompileSettings();
            const compileResponse = await fetch('/api/compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ asql: reverseData.asql, dialect: getApiDialect(toDialect) || '', settings: compileSettings })
            });
            
            const compileData = await compileResponse.json();
            if (compileData.error) {
                showError(compileData.error);
            } else {
                outputEditor.setValue(compileData.sql);
                updateURL();
            }
        } else {
            // asql-to-asql mode (includes visual-asql variants)
            const inputIsJSON = input.trim().startsWith('{') || input.trim().startsWith('[');
            
            if (toDialect === 'visual-asql') {
                if (inputIsJSON) {
                    // Already JSON, just show it
                    outputEditor.setValue(input);
                    outputEditor.setOption('mode', 'application/json');
                    try {
                        const parsed = JSON.parse(input);
                        renderOutputVisual(parsed);
                    } catch (e) {
                        // Invalid JSON
                    }
                    updateURL();
                } else {
                    // Convert ASQL to visual JSON
                    const response = await fetch('/api/visual/parse', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ asql: input })
                    });
                    
                    const data = await response.json();
                    if (!data.success) {
                        showError(data.error || 'Failed to parse ASQL');
                    } else {
                        outputEditor.setValue(JSON.stringify(data.query, null, 2));
                        outputEditor.setOption('mode', 'application/json');
                        renderOutputVisual(data.query);
                        updateURL();
                    }
                }
            } else if (toDialect === 'asql') {
                if (inputIsJSON) {
                    // Convert JSON to ASQL
                    try {
                        const json = JSON.parse(input);
                        const response = await fetch('/api/visual/compile', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ query: json })
                        });
                        const data = await response.json();
                        if (data.success) {
                            outputEditor.setValue(data.asql);
                            outputEditor.setOption('mode', 'text/x-asql');
                            updateURL();
                        } else {
                            showError(data.error || 'Failed to convert to ASQL');
                        }
                    } catch (e) {
                        showError('Invalid JSON: ' + e.message);
                    }
                } else {
                    // Plain ASQL to ASQL - just copy
                    outputEditor.setValue(input);
                    outputEditor.setOption('mode', 'text/x-asql');
                    updateURL();
                }
            }
        }
    } catch (error) {
        showError('Error: ' + (error && error.message ? error.message : String(error)));
    }
}

// ========== Examples Functions ==========
function createExampleSection(container, title, description, examples, options = {}) {
    const section = document.createElement('div');
    section.className = 'example-section';
    if (options.id) section.id = options.id;
    
    const h3 = document.createElement('h3');
    h3.textContent = title;
    section.appendChild(h3);
    
    if (description) {
        const p = document.createElement('p');
        p.style.cssText = 'color: #666; margin-bottom: 15px; font-size: 13px;';
        p.textContent = description;
        section.appendChild(p);
    }
    
    const examplesDiv = document.createElement('div');
    examplesDiv.className = 'example-list';
    section.appendChild(examplesDiv);
    container.appendChild(section);
    
    if (!examples || !Array.isArray(examples) || examples.length === 0) {
        return examplesDiv;
    }
    
    examples.forEach(example => {
        const btn = document.createElement('button');
        btn.className = 'example-btn';
        
        const titleDiv = document.createElement('div');
        titleDiv.className = 'example-title';
        titleDiv.textContent = example.title;
        btn.appendChild(titleDiv);
        
        const descDiv = document.createElement('div');
        descDiv.className = 'example-desc';
        descDiv.textContent = example.desc;
        btn.appendChild(descDiv);
        
        btn.onclick = () => {
            closeExamplesModal();
            inputEditor.setValue(example.query);
            
            const fromSelect = document.getElementById('from-dialect');
            const toSelect = document.getElementById('to-dialect');
            
            if (example.dialect || options.fromDialect) {
                // SQL example with a specific dialect - set direction to SQL -> ASQL
                fromSelect.value = example.dialect || options.fromDialect || '';
                toSelect.value = 'asql';
            } else if (options.ensureAsql) {
                // ASQL example - set direction to ASQL -> SQL
                fromSelect.value = 'asql';
                // If to-dialect is currently ASQL, change it to a SQL dialect
                if (toSelect.value === 'asql') {
                    toSelect.value = 'snowflake';
                }
            }
            
            // Allow explicit toLanguage/toDialect override
            if (example.toLanguage) {
                toSelect.value = example.toLanguage;
            }
            if (options.toDialect) {
                toSelect.value = options.toDialect;
            }
            
            // If this is a visual-asql example, also load into the visual editor
            const finalFromDialect = fromSelect.value;
            if (finalFromDialect === 'visual-asql' && visualEditor && visualEditor.initialized) {
                try {
                    const jsonData = JSON.parse(example.query);
                    visualEditor.loadFromJSON(jsonData);
                } catch (e) {
                    console.error('Failed to parse visual-asql example JSON:', e);
                }
            }
            
            updateUITitles();
            translateQuery();
            setTimeout(updateURL, 1000);
        };
        examplesDiv.appendChild(btn);
    });
    
    return examplesDiv;
}

function loadExamples() {
    const container = document.getElementById('examples-container');
    if (!container) return;
    
    try {
        container.innerHTML = '';
        
        // ASQL examples - they will set direction to ASQL -> SQL when clicked
        createExampleSection(container, 'ASQL Pipe Syntax Examples',
            'Queries showcasing ASQL pipe syntax features.',
            pipeExamples, { ensureAsql: true });
        
        createExampleSection(container, 'Cohort Analysis Examples',
            'Cohort analysis patterns using first(), running_sum(), prior(), and other window functions.',
            cohortExamples, { ensureAsql: true });
        
        createExampleSection(container, 'Sampling Examples',
            'Random sampling for data exploration.',
            samplingExamples, { ensureAsql: true });
        
        createExampleSection(container, 'Data Reshaping Examples',
            'Pivot, unpivot, and explode operations for reshaping data.',
            dataReshapingExamples, { ensureAsql: true });
        
        createExampleSection(container, 'Column Operator Examples',
            'Except, rename, and replace operators for column manipulation.',
            columnOperatorExamples, { ensureAsql: true });
        
        createExampleSection(container, 'Smart Count Examples',
            'The # shorthand with table names infers primary keys.',
            countInferenceExamples, { ensureAsql: true });
        
        createExampleSection(container, 'Syntax Styles Examples',
            'Different syntax styles and shorthand options in ASQL.',
            syntaxStylesExamples, { ensureAsql: true });
        
        // Visual ASQL examples - they start in visual-asql format
        createExampleSection(container, 'Visual ASQL Examples',
            'Pre-built queries in the visual editor format.',
            visualAsqlExamples, { toDialect: 'snowflake' });
        
        // Always show SQL examples too - they will set direction to SQL -> ASQL when clicked
        const examplesDiv = createExampleSection(container, 'SQL Translation Examples',
            'SQL queries that can be translated to ASQL.',
            sqlExamples, { toDialect: 'asql' });
        if (sqlExamples.length === 0) {
            examplesDiv.innerHTML = '<p style="color: #666; padding: 20px;">SQL examples will be loaded...</p>';
            loadSQLExamples();
        }
        
        loadFivetranExamples();
    } catch (error) {
        console.error('Error loading examples:', error);
        container.innerHTML = '<p style="color: var(--asql-red-dark); padding: 20px;">Error loading examples.</p>';
    }
}

window.loadExamples = loadExamples;

async function loadFivetranExamples() {
    const container = document.getElementById('examples-container');
    
    let fivetranSection = document.getElementById('fivetran-examples-section');
    if (!fivetranSection) {
        fivetranSection = document.createElement('div');
        fivetranSection.id = 'fivetran-examples-section';
        fivetranSection.className = 'example-section';
        
        const h3 = document.createElement('h3');
        h3.textContent = 'Fivetran_dbt Examples';
        fivetranSection.appendChild(h3);
        
        const p = document.createElement('p');
        p.style.cssText = 'color: #666; margin-bottom: 15px; font-size: 13px;';
        p.textContent = 'Examples from fivetran_dbt libraries.';
        fivetranSection.appendChild(p);
        
        const examplesDiv = document.createElement('div');
        examplesDiv.className = 'example-list';
        examplesDiv.id = 'fivetran-examples';
        fivetranSection.appendChild(examplesDiv);
        container.appendChild(fivetranSection);
    }
    
    const examplesDiv = document.getElementById('fivetran-examples');
    if (examplesDiv.children.length === 0) {
        examplesDiv.innerHTML = '<p style="color: #666; padding: 20px;">Loading...</p>';
        try {
            const response = await fetch('/api/fivetran-examples');
            const examples = await response.json();
            
            examplesDiv.innerHTML = '';
            examples.forEach(example => {
                const btn = document.createElement('button');
                btn.className = 'example-btn';
                
                const titleDiv = document.createElement('div');
                titleDiv.className = 'example-title';
                titleDiv.textContent = example.title;
                btn.appendChild(titleDiv);
                
                const descDiv = document.createElement('div');
                descDiv.className = 'example-desc';
                descDiv.textContent = example.desc;
                btn.appendChild(descDiv);
                
                btn.onclick = () => {
                    closeExamplesModal();
                    inputEditor.setValue(example.query);
                    // Fivetran examples are SQL -> ASQL translations
                    document.getElementById('from-dialect').value = example.language || 'snowflake';
                    document.getElementById('to-dialect').value = example.toLanguage || 'asql';
                    updateUITitles();
                    translateQuery();
                };
                examplesDiv.appendChild(btn);
            });
        } catch (error) {
            console.error('Failed to load Fivetran examples:', error);
            examplesDiv.innerHTML = '<p style="color: var(--asql-red-dark); padding: 20px;">Failed to load.</p>';
        }
    }
}

async function loadSQLExamples() {
    try {
        const response = await fetch('/api/sql-examples');
        const examples = await response.json();
        sqlExamples.push(...examples);
        loadExamples();
    } catch (error) {
        console.error('Failed to load SQL examples:', error);
    }
}

// ========== Keyboard Shortcuts ==========
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeExamplesModal();
        closeSettingsModal();
    }
});

// ========== Initialize ==========
loadSettingsFromStorage();

document.addEventListener('DOMContentLoaded', function() {
    let modeCheckAttempts = 0;
    const maxModeCheckAttempts = 20;
    
    function checkASQLMode() {
        try {
            if (typeof CodeMirror === 'undefined') {
                modeCheckAttempts++;
                if (modeCheckAttempts < maxModeCheckAttempts) {
                    setTimeout(checkASQLMode, 100);
                    return;
                }
                initializeEditors();
                return;
            }
            
            const modeExists = CodeMirror.modes && CodeMirror.modes['asql'];
            const mimeExists = CodeMirror.mimeModes && CodeMirror.mimeModes['text/x-asql'];
            
            if (!modeExists && !mimeExists) {
                modeCheckAttempts++;
                if (modeCheckAttempts < maxModeCheckAttempts) {
                    setTimeout(checkASQLMode, 100);
                    return;
                }
            }
        } catch (e) {
            console.warn('Error checking ASQL mode:', e);
        }
        initializeEditors();
        
        setTimeout(function() {
            if (inputEditor) {
                const fromDialect = document.getElementById('from-dialect').value;
                if (fromDialect === 'asql' && CodeMirror.modes && CodeMirror.modes['asql']) {
                    inputEditor.setOption('mode', 'text/x-asql');
                }
            }
            if (outputEditor) {
                const toDialect = document.getElementById('to-dialect').value;
                if (toDialect === 'asql' && CodeMirror.modes && CodeMirror.modes['asql']) {
                    outputEditor.setOption('mode', 'text/x-asql');
                }
            }
        }, 100);
    }
    
    function initializeEditors() {
        const urlParams = new URLSearchParams(window.location.search);
        const d_f = urlParams.get('d_f') || 'asql';
        const d_t = urlParams.get('d_t') || '';
        const sql_f = urlParams.get('sql_f') || '';
        const sql_t = urlParams.get('sql_t') || '';
        
        let initialInput = '';
        let initialOutput = '';
        try { initialInput = sql_f ? decodeURIComponent(sql_f) : ''; } catch (e) {}
        try { initialOutput = sql_t ? decodeURIComponent(sql_t) : ''; } catch (e) {}
        
        if (d_f) document.getElementById('from-dialect').value = d_f.toLowerCase();
        else document.getElementById('from-dialect').value = 'asql';
        
        if (d_t) document.getElementById('to-dialect').value = d_t.toLowerCase();
        else document.getElementById('to-dialect').value = 'snowflake';
        
        const fromDialectValue = d_f ? d_f.toLowerCase() : 'asql';
        inputEditor = CodeMirror(document.getElementById('input-editor'), {
            value: initialInput,
            mode: fromDialectValue === 'asql' ? 'text/x-asql' : 'text/x-sql',
            lineNumbers: true,
            matchBrackets: true,
            autoCloseBrackets: true,
            theme: 'default',
            lineWrapping: true,
            placeholder: 'Enter your query here...',
            viewportMargin: Infinity
        });
    
        outputEditor = CodeMirror(document.getElementById('output-editor'), {
            value: initialOutput,
            mode: d_t && d_t.toLowerCase() === 'asql' ? 'text/x-asql' : 'text/x-sql',
            lineNumbers: true,
            matchBrackets: true,
            autoCloseBrackets: true,
            theme: 'default',
            readOnly: true,
            lineWrapping: true,
            placeholder: 'Translation will appear here...',
            viewportMargin: Infinity
        });
        
        setTimeout(() => {
            if (inputEditor) inputEditor.refresh();
            if (outputEditor) outputEditor.refresh();
        }, 100);
        
        document.getElementById('from-dialect').addEventListener('change', async () => {
            const newFromDialect = document.getElementById('from-dialect').value;
            const currentInput = inputEditor.getValue().trim();
            
            // Try to transpile the current input to the new dialect
            if (currentInput) {
                try {
                    await transpileInputToNewDialect(currentInput, newFromDialect);
                } catch (e) {
                    console.warn('Quick transpile of input failed:', e);
                }
            }
            
            ensureFromNotPostgresWhenToEmpty();
            updateUITitles();
            translateQuery();
            updateURL();
            // Update visual mode toggle visibility
            updateEditorVisibility('input', newFromDialect);
        });
        
        document.getElementById('to-dialect').addEventListener('change', () => {
            ensureFromNotPostgresWhenToEmpty();
            updateUITitles();
            // Re-translate from input to the new dialect
            translateQuery();
            updateURL();
            // Update output visual mode toggle visibility
            const toDialect = document.getElementById('to-dialect').value;
            updateEditorVisibility('output', toDialect);
        });
        
        // Visual mode toggle buttons (input)
        const jsonViewBtn = document.getElementById('json-view-btn');
        const visualViewBtn = document.getElementById('visual-view-btn');
        
        if (jsonViewBtn) {
            jsonViewBtn.addEventListener('click', () => setVisualModePreference('json'));
        }
        if (visualViewBtn) {
            visualViewBtn.addEventListener('click', () => setVisualModePreference('visual'));
        }
        
        // Visual mode toggle buttons (output)
        const outputJsonViewBtn = document.getElementById('output-json-view-btn');
        const outputVisualViewBtn = document.getElementById('output-visual-view-btn');
        
        if (outputJsonViewBtn) {
            outputJsonViewBtn.addEventListener('click', () => setOutputVisualModePreference('json'));
        }
        if (outputVisualViewBtn) {
            outputVisualViewBtn.addEventListener('click', () => setOutputVisualModePreference('visual'));
        }
        
        // Visual style toggle buttons (blocky vs text vs pipes vs accordion)
        const blockyStyleBtn = document.getElementById('blocky-style-btn');
        const textStyleBtn = document.getElementById('text-style-btn');
        const pipesStyleBtn = document.getElementById('pipes-style-btn');
        const accordionStyleBtn = document.getElementById('accordion-style-btn');
        const outputBlockyStyleBtn = document.getElementById('output-blocky-style-btn');
        const outputTextStyleBtn = document.getElementById('output-text-style-btn');
        const outputPipesStyleBtn = document.getElementById('output-pipes-style-btn');
        const outputAccordionStyleBtn = document.getElementById('output-accordion-style-btn');

        if (blockyStyleBtn) {
            blockyStyleBtn.addEventListener('click', () => setVisualStylePreference('blocky'));
        }
        if (textStyleBtn) {
            textStyleBtn.addEventListener('click', () => setVisualStylePreference('text'));
        }
        if (pipesStyleBtn) {
            pipesStyleBtn.addEventListener('click', () => setVisualStylePreference('pipes'));
        }
        if (accordionStyleBtn) {
            accordionStyleBtn.addEventListener('click', () => setVisualStylePreference('accordion'));
        }
        if (outputBlockyStyleBtn) {
            outputBlockyStyleBtn.addEventListener('click', () => setVisualStylePreference('blocky'));
        }
        if (outputTextStyleBtn) {
            outputTextStyleBtn.addEventListener('click', () => setVisualStylePreference('text'));
        }
        if (outputPipesStyleBtn) {
            outputPipesStyleBtn.addEventListener('click', () => setVisualStylePreference('pipes'));
        }
        if (outputAccordionStyleBtn) {
            outputAccordionStyleBtn.addEventListener('click', () => setVisualStylePreference('accordion'));
        }
        
        // Show columns toggle buttons
        const showColumnsBtn = document.getElementById('show-columns-btn');
        const outputShowColumnsBtn = document.getElementById('output-show-columns-btn');
        
        if (showColumnsBtn) {
            showColumnsBtn.addEventListener('click', toggleShowColumns);
        }
        if (outputShowColumnsBtn) {
            outputShowColumnsBtn.addEventListener('click', toggleShowColumns);
        }
        
        // Initialize visual mode toggle states
        updateVisualModeToggleButtons();
        updateOutputVisualModeToggleButtons();
        updateVisualStyleToggleButtons();
        updateShowColumnsToggleButtons();
        applyVisualStyle();
        applyShowColumns();
        
        let translateTimeout;
        let urlUpdateTimeout;
        inputEditor.on('change', () => {
            clearTimeout(translateTimeout);
            translateTimeout = setTimeout(translateQuery, 500);
            clearTimeout(urlUpdateTimeout);
            urlUpdateTimeout = setTimeout(updateURL, 1000);
        });
        
        inputEditor.on('paste', () => {
            setTimeout(() => {
                const fromDialect = document.getElementById('from-dialect').value;
                if (fromDialect !== 'asql' && !fromDialect) {
                    translateQuery();
                }
            }, 100);
        });
        
        try {
            loadExamples();
            
            // Async initialization - wait for visual editor if needed
            (async () => {
                // Wait for visual editor to be created (from visual-editor.js DOMContentLoaded)
                const fromDialect = document.getElementById('from-dialect').value;
                if (fromDialect === 'visual-asql') {
                    await waitForVisualEditor();
                }
                
                await updateUITitles();
                
                if (sql_f && !sql_t) {
                    translateQuery();
                } else if (!sql_f && !sql_t) {
                    translateQuery();
                }
            })().catch(e => console.error('Error during async initialization:', e));
        } catch (e) {
            console.error('Error during initial load:', e);
            try { loadExamples(); } catch (e2) {}
        }
    }
    
    checkASQLMode();
});

// ========== Visual Editor Integration ==========

// Render query JSON to the output visual editor (read-only display)
// Handles both new array format and legacy single-object format
function renderOutputVisual(query) {
    // Store query for re-renders (e.g., when switching to pipes mode)
    lastRenderedQuery = query;

    const fromDisplay = document.getElementById('output-from-table-display');
    const fromInput = document.getElementById('output-from-table');
    const transformsContainer = document.getElementById('output-transforms-container');

    if (!transformsContainer) return;

    // Normalize to array format
    const pipelines = Array.isArray(query) ? query : [query];

    // If in pipes mode, render the pipes view
    if (visualStylePreference === 'pipes') {
        renderPipesView(query);
        return;
    }

    // If in accordion mode, render the accordion view
    if (visualStylePreference === 'accordion') {
        renderAccordionView(query);
        return;
    }
    
    // Clear container
    transformsContainer.innerHTML = '';
    
    // For single pipeline with no name, use the legacy simple display
    if (pipelines.length === 1 && !pipelines[0].name) {
        const pipeline = pipelines[0];
        const tableName = pipeline.from?.table || '';
        
        if (fromDisplay) {
            fromDisplay.textContent = tableName;
        }
        if (fromInput) {
            fromInput.value = tableName;
        }
        
        // Add pipeline-level comments above FROM if present
        if (pipeline.comments && pipeline.comments.length > 0) {
            const commentDiv = document.createElement('div');
            commentDiv.className = 'pipeline-comment';
            commentDiv.textContent = '// ' + pipeline.comments.join(' | ');
            transformsContainer.appendChild(commentDiv);
        }
        
        // Show the from block in container
        const fromBlock = document.querySelector('#output-visual-editor-container .from-block');
        if (fromBlock) {
            fromBlock.style.display = 'block';
            
            // Add output columns for FROM if present
            let existingCols = fromBlock.querySelector('.output-columns');
            if (existingCols) existingCols.remove();
            
            // Add FROM comments if present
            let existingComment = fromBlock.querySelector('.block-comment');
            if (existingComment) existingComment.remove();
            
            if (pipeline.from?.comments && pipeline.from.comments.length > 0) {
                const commentDiv = document.createElement('div');
                commentDiv.className = 'block-comment';
                commentDiv.textContent = '// ' + pipeline.from.comments.join(' | ');
                fromBlock.insertBefore(commentDiv, fromBlock.firstChild);
            }
            
            if (pipeline.from?.output_columns && pipeline.from.output_columns.length > 0) {
                const colsDiv = document.createElement('div');
                colsDiv.className = 'output-columns';
                colsDiv.innerHTML = renderOutputColumnsTable(pipeline.from.output_columns);
                fromBlock.appendChild(colsDiv);
            }
        }
        
        if (pipeline.transforms && pipeline.transforms.length > 0) {
            pipeline.transforms.forEach(transform => {
                const block = createOutputBlock(transform);
                transformsContainer.appendChild(block);
            });
        }
        return;
    }
    
    // Multiple pipelines or named pipelines - hide the static from block
    const fromBlock = document.querySelector('#output-visual-editor-container .from-block');
    if (fromBlock) fromBlock.style.display = 'none';
    if (fromDisplay) fromDisplay.textContent = '';
    if (fromInput) fromInput.value = '';
    
    // Render each pipeline
    pipelines.forEach((pipeline, idx) => {
        // Pipeline header with name
        const pipelineDiv = document.createElement('div');
        pipelineDiv.className = 'pipeline-block';
        
        // Pipeline-level comments (header comments)
        if (pipeline.comments && pipeline.comments.length > 0) {
            const commentDiv = document.createElement('div');
            commentDiv.className = 'pipeline-comment';
            commentDiv.textContent = '// ' + pipeline.comments.join(' | ');
            pipelineDiv.appendChild(commentDiv);
        }
        
        // Pipeline name or "Query N"
        const nameLabel = pipeline.name || (pipelines.length > 1 ? `Query ${idx + 1}` : null);
        if (nameLabel) {
            const nameDiv = document.createElement('div');
            nameDiv.className = 'pipeline-name';
            nameDiv.innerHTML = `<span class="value-operator">●</span> <span class="value-column">${escapeHtmlText(nameLabel)}</span>`;
            pipelineDiv.appendChild(nameDiv);
        }
        
        // From block comments
        const tableName = pipeline.from?.table || '';
        if (tableName) {
            const fromDiv = document.createElement('div');
            fromDiv.className = 'block from-block';
            fromDiv.innerHTML = `<div class="block-body"><span class="value-operator">from</span> <span class="value-column">${escapeHtmlText(tableName)}</span></div>`;
            
            // Add output columns for FROM if present
            if (pipeline.from?.output_columns && pipeline.from.output_columns.length > 0) {
                const colsDiv = document.createElement('div');
                colsDiv.className = 'output-columns';
                colsDiv.innerHTML = renderOutputColumnsTable(pipeline.from.output_columns);
                fromDiv.appendChild(colsDiv);
            }
            
            pipelineDiv.appendChild(fromDiv);
        }
        
        // Transforms
        if (pipeline.transforms && pipeline.transforms.length > 0) {
            pipeline.transforms.forEach(transform => {
                const block = createOutputBlock(transform);
                pipelineDiv.appendChild(block);
            });
        }
        
        // Set operation (UNION, etc.) between pipelines
        if (pipeline.set_operation && idx < pipelines.length - 1) {
            const setOpDiv = document.createElement('div');
            setOpDiv.className = 'set-operation';
            const opText = pipeline.set_operation.all 
                ? `${pipeline.set_operation.type.toUpperCase()} ALL` 
                : pipeline.set_operation.type.toUpperCase();
            setOpDiv.innerHTML = `<span class="value-operator">${opText}</span>`;
            pipelineDiv.appendChild(setOpDiv);
        }
        
        transformsContainer.appendChild(pipelineDiv);
    });
}

// Render Yahoo Pipes-style visualization for pipelines/CTEs
function renderPipesView(query) {
    const transformsContainer = document.getElementById('output-transforms-container');
    if (!transformsContainer) return;

    // Hide the static from block
    const fromBlock = document.querySelector('#output-visual-editor-container .from-block');
    if (fromBlock) fromBlock.style.display = 'none';

    // Clear container
    transformsContainer.innerHTML = '';

    // Normalize to array format
    const pipelines = Array.isArray(query) ? query : [query];

    // Create pipes container
    const pipesContainer = document.createElement('div');
    pipesContainer.className = 'pipes-nodes-container';

    // Build a map of CTE names for reference detection
    const cteNames = new Set();
    pipelines.forEach(p => {
        if (p.name) cteNames.add(p.name.toLowerCase());
    });

    // Render each pipeline as a node
    pipelines.forEach((pipeline, idx) => {
        const node = createPipeNode(pipeline, idx, pipelines.length, cteNames);
        pipesContainer.appendChild(node);

        // Add set operation connector between pipelines
        if (pipeline.set_operation && idx < pipelines.length - 1) {
            const setOpDiv = document.createElement('div');
            setOpDiv.className = 'pipe-set-operation';
            const opText = pipeline.set_operation.all
                ? `${pipeline.set_operation.type.toUpperCase()} ALL`
                : pipeline.set_operation.type.toUpperCase();
            setOpDiv.innerHTML = `<span class="pipe-set-op-badge">${opText}</span>`;
            pipesContainer.appendChild(setOpDiv);
        }
    });

    transformsContainer.appendChild(pipesContainer);
}

// Render output in accordion/spreadsheet mode
function renderAccordionView(query) {
    const transformsContainer = document.getElementById('output-transforms-container');
    if (!transformsContainer) return;

    // Hide the static from block
    const fromBlock = document.querySelector('#output-visual-editor-container .from-block');
    if (fromBlock) fromBlock.style.display = 'none';

    // Clear container
    transformsContainer.innerHTML = '';

    // Normalize to array format
    const pipelines = Array.isArray(query) ? query : [query];

    // Create accordion container
    const accordionContainer = document.createElement('div');
    accordionContainer.className = 'accordion-container';

    // Render each pipeline
    pipelines.forEach((pipeline, pipelineIdx) => {
        const pipelineAccordion = createAccordionPipeline(pipeline, pipelineIdx);
        accordionContainer.appendChild(pipelineAccordion);

        // Add set operation between pipelines if exists
        if (pipelineIdx < pipelines.length - 1 && pipeline.set_operation) {
            const setOpDiv = document.createElement('div');
            setOpDiv.className = 'accordion-set-operation';
            const opText = pipeline.set_operation.all
                ? `${pipeline.set_operation.type.toUpperCase()} ALL`
                : pipeline.set_operation.type.toUpperCase();
            setOpDiv.innerHTML = `<span class="accordion-set-op-badge">${opText}</span>`;
            accordionContainer.appendChild(setOpDiv);
        }
    });

    transformsContainer.appendChild(accordionContainer);
}

// Create an accordion pipeline with stacked spreadsheet steps
function createAccordionPipeline(pipeline, pipelineIdx) {
    const pipelineDiv = document.createElement('div');
    pipelineDiv.className = 'accordion-pipeline';
    pipelineDiv.dataset.pipelineIndex = pipelineIdx;

    // Pipeline header (if named CTE)
    if (pipeline.name) {
        const header = document.createElement('div');
        header.className = 'accordion-pipeline-header';
        header.innerHTML = `<span class="accordion-cte-badge">CTE</span> <span class="accordion-cte-name">${escapeHtmlText(pipeline.name)}</span>`;
        pipelineDiv.appendChild(header);
    }

    // Step 0: FROM step
    const fromStep = createAccordionStep(
        'from',
        pipeline.from?.table || 'select table...',
        pipeline.from?.output_columns || [],
        true // expanded by default for FROM
    );
    pipelineDiv.appendChild(fromStep);

    // Subsequent transform steps
    (pipeline.transforms || []).forEach((transform, transformIdx) => {
        const stepLabel = getTransformLabel(transform);
        const columns = transform.output_columns || pipeline.from?.output_columns || [];
        const isLast = transformIdx === (pipeline.transforms || []).length - 1;

        const step = createAccordionStep(
            transform.type,
            stepLabel,
            columns,
            isLast // expand last step
        );
        pipelineDiv.appendChild(step);
    });

    return pipelineDiv;
}

// Create a single accordion step (spreadsheet section) - read-only version
function createAccordionStep(type, label, columns, isExpanded) {
    const step = document.createElement('div');
    step.className = `accordion-step ${isExpanded ? 'expanded' : 'collapsed'} step-type-${type}`;

    // Step header
    const header = document.createElement('div');
    header.className = 'accordion-step-header';

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

    // Column count indicator
    const colCount = document.createElement('span');
    colCount.className = 'accordion-col-count';
    colCount.textContent = `${columns.length} cols`;
    headerRight.appendChild(colCount);

    // Expand indicator
    const expandIndicator = document.createElement('span');
    expandIndicator.className = 'accordion-expand-indicator';
    expandIndicator.textContent = isExpanded ? '▼' : '▶';
    headerRight.appendChild(expandIndicator);

    header.appendChild(headerRight);

    // Click to toggle expand/collapse
    header.addEventListener('click', () => {
        const wasExpanded = step.classList.contains('expanded');
        // Collapse all siblings first
        const siblings = step.parentElement.querySelectorAll('.accordion-step');
        siblings.forEach(s => {
            s.classList.remove('expanded');
            s.classList.add('collapsed');
            const indicator = s.querySelector('.accordion-expand-indicator');
            if (indicator) indicator.textContent = '▶';
            const dataContainer = s.querySelector('.accordion-data-container');
            if (dataContainer) dataContainer.remove();
        });
        
        // If it wasn't expanded, expand this one
        if (!wasExpanded) {
            step.classList.remove('collapsed');
            step.classList.add('expanded');
            expandIndicator.textContent = '▼';
            
            // Add data rows
            const dataContainer = createAccordionDataContainer(columns);
            step.appendChild(dataContainer);
        }
    });

    step.appendChild(header);

    // Column headers row (always visible)
    const colHeaders = createAccordionColumnHeaders(columns);
    step.appendChild(colHeaders);

    // Data rows (only visible when expanded)
    if (isExpanded) {
        const dataContainer = createAccordionDataContainer(columns);
        step.appendChild(dataContainer);
    }

    return step;
}

// Create column headers row for accordion step
function createAccordionColumnHeaders(columns) {
    const headerRow = document.createElement('div');
    headerRow.className = 'accordion-col-headers';

    if (columns.length === 0) {
        const emptyCell = document.createElement('div');
        emptyCell.className = 'accordion-col-header accordion-empty-header';
        emptyCell.textContent = 'No columns';
        headerRow.appendChild(emptyCell);
        return headerRow;
    }

    columns.forEach((col) => {
        const colName = typeof col === 'string' ? col : col.name;
        const colType = typeof col === 'object' ? col.type : '';

        const headerCell = document.createElement('div');
        headerCell.className = 'accordion-col-header';

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

        headerRow.appendChild(headerCell);
    });

    return headerRow;
}

// Create data container with sample rows
function createAccordionDataContainer(columns) {
    const dataContainer = document.createElement('div');
    dataContainer.className = 'accordion-data-container';

    // Generate 10 rows of sample data
    for (let rowIdx = 0; rowIdx < 10; rowIdx++) {
        const row = createAccordionDataRow(columns, rowIdx);
        dataContainer.appendChild(row);
    }

    return dataContainer;
}

// Create a data row with sample data
function createAccordionDataRow(columns, rowIdx) {
    const row = document.createElement('div');
    row.className = 'accordion-data-row';
    row.dataset.rowIndex = rowIdx;

    if (columns.length === 0) {
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

// Generate fake data based on column type
function generateFakeData(colType, rowIdx, colIdx) {
    const typeNorm = (colType || '').toLowerCase();

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
        const d = new Date(2024, Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1);
        return d.toISOString().split('T')[0];
    }

    // Timestamp types
    if (typeNorm.includes('timestamp') || typeNorm.includes('datetime')) {
        const d = new Date(2024, Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1,
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

// Get a label for a transform
function getTransformLabel(transform) {
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
                return transform.expressions.slice(0, 2).map(e => e.column + (e.direction === 'desc' ? ' ↓' : ' ↑')).join(', ');
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

// Create a single pipe node for a pipeline/CTE
function createPipeNode(pipeline, idx, totalPipelines, cteNames) {
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
    icon.textContent = isNamedCTE ? 'C' : (referencesOtherCTE ? '⟶' : 'T');

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
                <span class="value-column">${escapeHtmlText(tableName)}</span>
            </div>
        `;
        body.appendChild(fromStep);
    }

    // Render transforms
    if (pipeline.transforms && pipeline.transforms.length > 0) {
        pipeline.transforms.forEach(transform => {
            const step = createPipeStep(transform);
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
        const colsDiv = document.createElement('div');
        colsDiv.className = 'output-columns';
        colsDiv.innerHTML = renderOutputColumnsTable(outputCols);
        footer.appendChild(colsDiv);
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

// Create a step element within a pipe node
function createPipeStep(transform) {
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
    content.innerHTML = renderPipeStepContent(transform);

    step.appendChild(header);
    step.appendChild(content);

    return step;
}

// Render the content of a pipe step based on transform type
function renderPipeStepContent(transform) {
    const escape = escapeHtmlText;

    switch (transform.type) {
        case 'where':
            return `<span class="value-column">${escape(transform.condition || '')}</span>`;

        case 'select':
            if (transform.columns && transform.columns.length > 0) {
                const cols = transform.columns.map(c => {
                    const expr = typeof c === 'string' ? c : (c.expression || c.name || '');
                    const alias = typeof c === 'object' && c.name !== c.expression ? c.name : null;
                    if (alias && alias !== expr) {
                        return `<span class="value-column">${escape(expr)}</span> <span class="value-operator">as</span> <span class="value-column">${escape(alias)}</span>`;
                    }
                    return `<span class="value-column">${escape(expr)}</span>`;
                });
                return cols.join(', ');
            }
            return '*';

        case 'join':
            const joinType = (transform.join_type || 'inner').toUpperCase();
            const joinTable = transform.table || '';
            const joinCond = transform.condition || '';
            return `<span class="value-operator">${joinType}</span> <span class="value-column">${escape(joinTable)}</span> <span class="value-operator">on</span> ${escape(joinCond)}`;

        case 'group_by':
            let groupContent = '';
            if (transform.dimensions && transform.dimensions.length > 0) {
                const dims = transform.dimensions.map(d => `<span class="value-column">${escape(d)}</span>`).join(', ');
                groupContent += dims;
            }
            if (transform.aggregates && transform.aggregates.length > 0) {
                const aggs = transform.aggregates.map(a => {
                    const fn = a.function || 'count';
                    const col = a.column || '*';
                    const alias = a.alias ? ` <span class="value-operator">as</span> <span class="value-column">${escape(a.alias)}</span>` : '';
                    return `<span class="value-function">${escape(fn)}</span>(<span class="value-column">${escape(col)}</span>)${alias}`;
                }).join(', ');
                if (groupContent) groupContent += '<br>';
                groupContent += aggs;
            }
            return groupContent || 'no dimensions';

        case 'order_by':
            if (transform.expressions && transform.expressions.length > 0) {
                return transform.expressions.map(e => {
                    const col = e.column || e.expression || '';
                    const dir = (e.direction || 'asc').toUpperCase();
                    return `<span class="value-column">${escape(col)}</span> <span class="value-operator">${dir}</span>`;
                }).join(', ');
            }
            return '';

        case 'limit':
            const count = transform.count || transform.limit || 0;
            const offset = transform.offset;
            let limitStr = `<span class="value-number">${count}</span>`;
            if (offset) {
                limitStr += ` <span class="value-operator">offset</span> <span class="value-number">${offset}</span>`;
            }
            return limitStr;

        case 'extend':
            if (transform.columns && transform.columns.length > 0) {
                return transform.columns.map(c => `<span class="value-column">${escape(typeof c === 'string' ? c : c.expression || '')}</span>`).join(', ');
            }
            return '';

        default:
            // Generic fallback - show any condition or expression
            if (transform.condition) return escape(transform.condition);
            if (transform.expression) return escape(transform.expression);
            if (transform.columns) {
                return transform.columns.map(c => escape(typeof c === 'string' ? c : JSON.stringify(c))).join(', ');
            }
            return JSON.stringify(transform);
    }
}

// Helper to escape HTML in text
function escapeHtmlText(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Create a read-only block for output visual display - code-like inline style
function createOutputBlock(transform) {
    const block = document.createElement('div');
    block.className = `block transform-block ${transform.type}-block`;
    
    // Add comments if present
    if (transform.comments && transform.comments.length > 0) {
        const commentDiv = document.createElement('div');
        commentDiv.className = 'block-comment';
        commentDiv.textContent = '// ' + transform.comments.join(' | ');
        block.appendChild(commentDiv);
    }
    
    // No header - just inline content
    const body = document.createElement('div');
    body.className = 'block-body';
    body.innerHTML = renderOutputBlockBody(transform);
    
    block.appendChild(body);
    
    // Add output columns if present
    if (transform.output_columns && transform.output_columns.length > 0) {
        const colsDiv = document.createElement('div');
        colsDiv.className = 'output-columns';
        colsDiv.innerHTML = renderOutputColumnsTable(transform.output_columns);
        block.appendChild(colsDiv);
    }
    
    return block;
}

// Render output columns as a table header row
function renderOutputColumnsTable(columns) {
    if (!columns || columns.length === 0) {
        // Return a message when no schema is available
        return '<span class="no-schema-message">No schema available for this table</span>';
    }
    
    const headers = columns.map(col => {
        const name = escapeHtmlText(typeof col === 'string' ? col : col.name || '');
        const type = typeof col === 'object' && col.type ? `<span class="col-type">${escapeHtmlText(col.type)}</span>` : '';
        return `<th>${name}${type}</th>`;
    }).join('');
    
    return `<table><tr>${headers}</tr></table>`;
}

// Render the body of an output block - code-like inline format
function renderOutputBlockBody(transform) {
    const escapeHtml = (text) => {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };
    
    // Format as: keyword content
    const keyword = (kw) => `<span class="value-operator">${kw}</span>`;
    const column = (col) => `<span class="value-column">${escapeHtml(col)}</span>`;
    const str = (s) => `<span class="value-string">'${escapeHtml(s)}'</span>`;
    const num = (n) => `<span class="value-number">${escapeHtml(String(n))}</span>`;
    
    switch (transform.type) {
        case 'where':
        case 'having':
        case 'qualify':
            return `${keyword(transform.type)} ${formatConditionStyled(transform.condition)}`;
        case 'join': {
            const joinType = transform.join_type || 'inner';
            const table = transform.table || '';
            const on = transform.condition ? ` ${keyword('on')} ${formatConditionStyled(transform.condition)}` : '';
            return `${keyword(joinType + ' join')} ${column(table)}${on}`;
        }
        case 'select': {
            const cols = (transform.columns || []).map(c => {
                if (typeof c === 'string') return column(c);
                return column(c.name || c.expression || JSON.stringify(c));
            }).join(', ');
            return `${keyword('select')} ${cols || '*'}`;
        }
        case 'group_by': {
            const dims = (transform.dimensions || []).map(d => column(d)).join(', ');
            const aggs = (transform.aggregates || []).map(a => 
                `${keyword(a.function)}(${column(a.column)})`
            ).join(', ');
            let result = `${keyword('group by')} ${dims}`;
            if (aggs) result += ` (${aggs})`;
            return result;
        }
        case 'order_by': {
            const orders = (transform.expressions || []).map(e => 
                `${column(e.column)} ${keyword(e.direction || 'asc')}`
            ).join(', ');
            return `${keyword('order by')} ${orders}`;
        }
        case 'limit':
            return `${keyword('limit')} ${num(transform.count ?? 10)}`;
        case 'offset':
            return `${keyword('offset')} ${num(transform.offset ?? 0)}`;
        case 'distinct':
            return keyword('distinct');
        case 'except': {
            const cols = (transform.columns || []).map(c => column(c)).join(', ');
            return `${keyword('except')} ${cols}`;
        }
        case 'extend': {
            const cols = (transform.columns || []).map(c => column(c)).join(', ');
            return `${keyword('extend')} ${cols}`;
        }
        case 'rename': {
            const renames = Object.entries(transform.mapping || {}).map(([k, v]) => 
                `${column(k)} → ${column(v)}`
            ).join(', ');
            return `${keyword('rename')} ${renames}`;
        }
        default:
            // Fallback - show type and key info
            const entries = Object.entries(transform)
                .filter(([k]) => k !== 'id' && k !== 'type' && k !== 'output_columns')
                .map(([k, v]) => `${k}: ${typeof v === 'string' ? str(v) : JSON.stringify(v)}`)
                .join(', ');
            return `${keyword(transform.type)} ${entries}`;
    }
}

// Format a condition object with syntax highlighting
function formatConditionStyled(cond) {
    if (!cond) return '';
    
    const escapeHtml = (text) => {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };
    
    const column = (col) => `<span class="value-column">${escapeHtml(col)}</span>`;
    const str = (s) => `<span class="value-string">'${escapeHtml(s)}'</span>`;
    const num = (n) => `<span class="value-number">${escapeHtml(String(n))}</span>`;
    const op = (o) => `<span class="value-operator">${escapeHtml(o)}</span>`;
    
    if (cond.type === 'column') {
        const name = cond.table ? `${cond.table}.${cond.name}` : cond.name;
        return column(name || '');
    }
    if (cond.type === 'literal') {
        const v = cond.value;
        if (typeof v === 'string') return str(v);
        if (typeof v === 'number') return num(v);
        if (v === null) return op('null');
        if (typeof v === 'boolean') return op(v ? 'true' : 'false');
        return escapeHtml(JSON.stringify(v));
    }
    if (cond.type === 'binary_op' || cond.operator) {
        const left = formatConditionStyled(cond.left);
        const right = formatConditionStyled(cond.right);
        return `${left} ${op(cond.operator)} ${right}`;
    }
    if (cond.type === 'like') {
        const operand = formatConditionStyled(cond.operand);
        const pattern = formatConditionStyled(cond.pattern);
        return `${operand} ${op('like')} ${pattern}`;
    }
    if (cond.type === 'and' || cond.type === 'or') {
        const conditions = (cond.conditions || []).map(c => formatConditionStyled(c));
        return conditions.join(` ${op(cond.type)} `);
    }
    if (cond.type === 'not') {
        return `${op('not')} ${formatConditionStyled(cond.condition)}`;
    }
    if (cond.type === 'is_null') {
        return `${formatConditionStyled(cond.operand)} ${op('is null')}`;
    }
    if (cond.type === 'is_not_null') {
        return `${formatConditionStyled(cond.operand)} ${op('is not null')}`;
    }
    if (cond.type === 'in') {
        const operand = formatConditionStyled(cond.operand);
        const values = (cond.values || []).map(v => formatConditionStyled(v)).join(', ');
        return `${operand} ${op('in')} (${values})`;
    }
    if (cond.type === 'between') {
        const operand = formatConditionStyled(cond.operand);
        const low = formatConditionStyled(cond.low);
        const high = formatConditionStyled(cond.high);
        return `${operand} ${op('between')} ${low} ${op('and')} ${high}`;
    }
    if (cond.type === 'function') {
        const args = (cond.arguments || []).map(a => formatConditionStyled(a)).join(', ');
        return `${op(cond.name)}(${args})`;
    }
    
    // Fallback
    return escapeHtml(JSON.stringify(cond));
}

// Format a condition object to plain string (for input editor)
function formatCondition(cond) {
    if (!cond) return '';
    if (cond.type === 'column') return cond.name || '';
    if (cond.type === 'literal') return JSON.stringify(cond.value);
    if (cond.type === 'binary_op') {
        const left = formatCondition(cond.left);
        const right = formatCondition(cond.right);
        return `${left} ${cond.operator} ${right}`;
    }
    return cond.value || JSON.stringify(cond);
}

// Handle visual editor changes - triggers translation when visual editor content changes
const onVisualEditorChange = debounce(async () => {
    // Only process if input is using visual editor
    if (isVisualDialect('from-dialect') && visualEditor) {
        const query = visualEditor.getQuery();
        if (!query) return;
        
        const toDialect = document.getElementById('to-dialect')?.value || 'duckdb';
        
        try {
            // Use the new transpile endpoint that does compile + transpile + column enrichment
            const response = await fetch('/api/visual/transpile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    query, 
                    target_dialect: toDialect 
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update text editor with ASQL
                if (data.asql) {
                    inputEditor.setValue(data.asql);
                }
                
                // Update output with SQL
                if (data.sql) {
                    outputEditor.setValue(data.sql);
                }
                
                // Update visual editor with enriched query (has output_columns)
                // IMPORTANT: Merge enriched data into existing objects instead of replacing them
                // to preserve references held by DOM event handlers
                if (data.enriched_query) {
                    const enrichedPipelines = Array.isArray(data.enriched_query)
                        ? data.enriched_query
                        : [data.enriched_query];

                    // Merge output_columns into existing transforms
                    enrichedPipelines.forEach((enrichedPipeline, pIdx) => {
                        const existingPipeline = visualEditor.pipelines[pIdx];
                        if (!existingPipeline) return;

                        // Merge from output_columns
                        if (enrichedPipeline.from?.output_columns) {
                            existingPipeline.from = existingPipeline.from || {};
                            existingPipeline.from.output_columns = enrichedPipeline.from.output_columns;
                        }

                        // Merge transform output_columns by matching IDs
                        (enrichedPipeline.transforms || []).forEach(enrichedTransform => {
                            const existingTransform = (existingPipeline.transforms || [])
                                .find(t => t.id === enrichedTransform.id);
                            if (existingTransform && enrichedTransform.output_columns) {
                                existingTransform.output_columns = enrichedTransform.output_columns;
                            }
                        });
                    });
                }
                
                hideGlobalError();
                updateURL();
            } else {
                showGlobalError(data.error || 'Transpile failed');
            }
        } catch (error) {
            console.error('Visual editor transpile error:', error);
            // Fallback to old behavior
            const asql = await visualEditor.getASQL();
            if (asql) {
                inputEditor.setValue(asql);
                translateQuery();
            }
        }
    }
}, 500);

// Register the event listener for visual editor changes
document.addEventListener('visual-editor-change', onVisualEditorChange);



