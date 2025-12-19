/**
 * ASQL Playground JavaScript
 */

// ========== Global Variables ==========
let inputEditor, outputEditor;

// Example arrays - will be set from EXAMPLES_DATA injected by server
let asqlExamples = [];
let asqlPipelineExamples = [];
let cohortExamples = [];
let samplingExamples = [];
let dataReshapingExamples = [];
let columnOperatorExamples = [];
let countInferenceExamples = [];
let sqlExamples = [];

// Settings state
let currentSettings = { compile: {}, style: {} };
let settingsSchemaCache = null;

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
    asqlExamples = data.asql || [];
    asqlPipelineExamples = data.pipeline || [];
    cohortExamples = data.cohort || [];
    samplingExamples = data.sampling || [];
    dataReshapingExamples = data.reshaping || [];
    columnOperatorExamples = data.column_operators || [];
    countInferenceExamples = data.count_inference || [];
    sqlExamples = data.sql || [];
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
function swapLanguages() {
    const fromSelect = document.getElementById('from-dialect');
    const toSelect = document.getElementById('to-dialect');
    if (!fromSelect || !toSelect || !inputEditor || !outputEditor) {
        return;
    }
    
    const fromValue = fromSelect.value;
    const toValue = toSelect.value;

    fromSelect.value = toValue;
    toSelect.value = fromValue;

    const temp = inputEditor.getValue();
    inputEditor.setValue(outputEditor.getValue());
    outputEditor.setValue(temp);

    updateUITitles();
    translateQuery();
}

function ensureFromNotPostgresWhenToEmpty() {
    const fromDialect = document.getElementById('from-dialect').value;
    const toDialect = document.getElementById('to-dialect').value;
    
    if (!toDialect && (fromDialect === 'postgres' || fromDialect === 'postgresql')) {
        document.getElementById('from-dialect').value = 'asql';
    }
}

function updateUITitles() {
    if (!inputEditor || !outputEditor) return;
    
    ensureFromNotPostgresWhenToEmpty();
    
    const fromDialect = document.getElementById('from-dialect').value;
    const toDialect = document.getElementById('to-dialect').value;
    
    if (fromDialect === 'asql') {
        inputEditor.setOption('mode', 'text/x-asql');
    } else {
        inputEditor.setOption('mode', 'text/x-sql');
    }
    
    if (toDialect === 'asql') {
        outputEditor.setOption('mode', 'text/x-asql');
    } else {
        outputEditor.setOption('mode', 'text/x-sql');
    }
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
        
        if (fromDialect === 'asql' && toDialect !== 'asql') return 'asql-to-sql';
        if (fromDialect !== 'asql' && toDialect === 'asql') return 'sql-to-asql';
        if (fromDialect === 'asql' && toDialect === 'asql') return 'asql-to-asql';
        return 'sql-to-sql';
    } catch (error) {
        console.error('Error getting current mode:', error);
        return 'asql-to-sql';
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
    
    try {
        if (currentMode === 'asql-to-sql') {
            const compileSettings = getCompileSettings();
            const response = await fetch('/api/compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ asql: input, dialect: toDialect || '', settings: compileSettings })
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
            
            const reverseData = await reverseResponse.json();
            if (reverseData.error) {
                showError(reverseData.error);
                return;
            }
            
            const compileSettings = getCompileSettings();
            const compileResponse = await fetch('/api/compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ asql: reverseData.asql, dialect: toDialect || '', settings: compileSettings })
            });
            
            const compileData = await compileResponse.json();
            if (compileData.error) {
                showError(compileData.error);
            } else {
                outputEditor.setValue(compileData.sql);
                updateURL();
            }
        } else {
            outputEditor.setValue(input);
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
            
            if (example.dialect || options.fromDialect) {
                document.getElementById('from-dialect').value = example.dialect || options.fromDialect || '';
            } else if (options.ensureAsql) {
                if (document.getElementById('from-dialect').value !== 'asql') {
                    document.getElementById('from-dialect').value = 'asql';
                }
            }
            if (example.toLanguage) {
                document.getElementById('to-dialect').value = example.toLanguage;
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
        const currentMode = getCurrentMode();
        
        if (currentMode === 'asql-to-sql' || currentMode === 'asql-to-asql') {
            createExampleSection(container, 'Basic Examples',
                'Basic ASQL queries that showcase the language syntax.',
                asqlExamples, { ensureAsql: true });
            
            createExampleSection(container, 'ASQL Pipeline Examples',
                'Complex queries that showcase pipeline features and generate multiple CTEs.',
                asqlPipelineExamples, { ensureAsql: true });
            
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
        } else {
            const examplesDiv = createExampleSection(container, 'SQL Translation Examples', null, sqlExamples);
            if (sqlExamples.length === 0) {
                examplesDiv.innerHTML = '<p style="color: #666; padding: 20px;">SQL examples will be loaded...</p>';
                loadSQLExamples();
            }
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
                    document.getElementById('from-dialect').value = example.language || '';
                    if (example.toLanguage) {
                        document.getElementById('to-dialect').value = example.toLanguage;
                    }
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
        
        document.getElementById('from-dialect').addEventListener('change', () => {
            ensureFromNotPostgresWhenToEmpty();
            updateUITitles();
            translateQuery();
            updateURL();
        });
        
        document.getElementById('to-dialect').addEventListener('change', () => {
            ensureFromNotPostgresWhenToEmpty();
            updateUITitles();
            translateQuery();
            updateURL();
        });
        
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
            updateUITitles();
            loadExamples();
            if (sql_f && !sql_t) {
                translateQuery();
            } else if (!sql_f && !sql_t) {
                translateQuery();
            }
        } catch (e) {
            console.error('Error during initial load:', e);
            try { loadExamples(); } catch (e2) {}
        }
    }
    
    checkASQLMode();
});
