# Playground Settings

How to expose ASQL style configuration in the playground.

---

## Overview

The playground should let users set their ASQL style preferences. When users click examples or paste SQL, the output ASQL is normalized to their preferred style.

**Flow:**
```
User clicks example (written in default style)
    ↓
normalize(example, user_config)
    ↓
Display in user's preferred style
```

This means examples are maintained in ONE canonical style, but displayed in whatever style the user prefers.

---

## Style Options to Expose

From `language-config.md`, these are the style options:

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `equality` | `double` / `single` | `double` | `==` vs `=` |
| `count` | `hash` / `function` | `hash` | `#` vs `count(*)` |
| `coalesce` | `operator` / `function` | `operator` | `??` vs `coalesce()` |
| `limit` | `take` / `limit` | `take` | `take 10` vs `limit 10` |
| `descending` | `prefix` / `suffix` | `prefix` | `-col` vs `col DESC` |
| `cast` | `double_colon` / `function` | `double_colon` | `::INT` vs `CAST(x AS INT)` |
| `quotes` | `double` / `single` | `double` | `"text"` vs `'text'` |
| `week_start` | `monday` / `sunday` | `monday` | ISO vs US week start |

---

## Playground UI

### Settings Panel

Add a collapsible settings panel above or beside the editors:

```html
<div class="settings-panel" id="settings-panel">
    <div class="settings-header" onclick="toggleSettings()">
        <span>⚙️ ASQL Style</span>
        <span class="settings-toggle" id="settings-toggle">▼</span>
    </div>
    
    <div class="settings-content" id="settings-content">
        <!-- Preset selector -->
        <div class="setting-group">
            <label>Preset:</label>
            <select id="setting-preset" onchange="applyPreset(this.value)">
                <option value="default">Default (ASQL style)</option>
                <option value="sql-compat">SQL Compatible</option>
                <option value="concise">Concise</option>
            </select>
        </div>
        
        <hr class="settings-divider">
        
        <!-- Individual options -->
        <div class="setting-group">
            <label>Equality:</label>
            <select id="setting-equality" onchange="updateStyle()">
                <option value="double">== (Python style)</option>
                <option value="single">= (SQL style)</option>
            </select>
        </div>
        
        <div class="setting-group">
            <label>Count:</label>
            <select id="setting-count" onchange="updateStyle()">
                <option value="hash"># (shorthand)</option>
                <option value="function">count(*)</option>
            </select>
        </div>
        
        <div class="setting-group">
            <label>Null coalescing:</label>
            <select id="setting-coalesce" onchange="updateStyle()">
                <option value="operator">?? (operator)</option>
                <option value="function">coalesce()</option>
            </select>
        </div>
        
        <div class="setting-group">
            <label>Row limit:</label>
            <select id="setting-limit" onchange="updateStyle()">
                <option value="take">take</option>
                <option value="limit">limit</option>
            </select>
        </div>
        
        <div class="setting-group">
            <label>Descending:</label>
            <select id="setting-descending" onchange="updateStyle()">
                <option value="prefix">-column (prefix)</option>
                <option value="suffix">column DESC (suffix)</option>
            </select>
        </div>
        
        <div class="setting-group">
            <label>Type cast:</label>
            <select id="setting-cast" onchange="updateStyle()">
                <option value="double_colon">::TYPE</option>
                <option value="function">CAST(x AS TYPE)</option>
            </select>
        </div>
        
        <div class="setting-group">
            <label>String quotes:</label>
            <select id="setting-quotes" onchange="updateStyle()">
                <option value="double">"double"</option>
                <option value="single">'single'</option>
            </select>
        </div>
        
        <div class="setting-group">
            <label>Week starts:</label>
            <select id="setting-week-start" onchange="updateStyle()">
                <option value="monday">Monday (ISO)</option>
                <option value="sunday">Sunday (US)</option>
            </select>
        </div>
    </div>
</div>
```

### CSS

```css
.settings-panel {
    background: white;
    border: 1px solid #dadce0;
    border-radius: 8px;
    margin-bottom: 20px;
    overflow: hidden;
}

.settings-header {
    padding: 12px 16px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #f8f9fa;
    border-bottom: 1px solid #dadce0;
    font-weight: 500;
}

.settings-header:hover {
    background: #f1f3f4;
}

.settings-content {
    padding: 16px;
    display: none;  /* Hidden by default */
}

.settings-content.open {
    display: block;
}

.settings-toggle {
    transition: transform 0.2s;
}

.settings-toggle.open {
    transform: rotate(180deg);
}

.setting-group {
    display: flex;
    align-items: center;
    margin-bottom: 12px;
    gap: 12px;
}

.setting-group label {
    min-width: 120px;
    font-size: 13px;
    color: #666;
}

.setting-group select {
    flex: 1;
    padding: 6px 10px;
    border: 1px solid #dadce0;
    border-radius: 4px;
    font-size: 13px;
    background: white;
}

.settings-divider {
    border: none;
    border-top: 1px solid #e8eaed;
    margin: 12px 0;
}
```

---

## JavaScript Implementation

### State Management

```javascript
// Style configuration state
let styleConfig = {
    equality: 'double',
    count: 'hash',
    coalesce: 'operator',
    limit: 'take',
    descending: 'prefix',
    cast: 'double_colon',
    quotes: 'double',
    week_start: 'monday',
};

// Preset definitions
const PRESETS = {
    'default': {
        equality: 'double',
        count: 'hash',
        coalesce: 'operator',
        limit: 'take',
        descending: 'prefix',
        cast: 'double_colon',
        quotes: 'double',
        week_start: 'monday',
    },
    'sql-compat': {
        equality: 'single',
        count: 'function',
        coalesce: 'function',
        limit: 'limit',
        descending: 'suffix',
        cast: 'function',
        quotes: 'single',
        week_start: 'monday',
    },
    'concise': {
        equality: 'double',
        count: 'hash',
        coalesce: 'operator',
        limit: 'take',
        descending: 'prefix',
        cast: 'double_colon',
        quotes: 'double',
        week_start: 'monday',
    },
};

// Load from localStorage on init
function loadStyleConfig() {
    const saved = localStorage.getItem('asql_style_config');
    if (saved) {
        styleConfig = { ...styleConfig, ...JSON.parse(saved) };
        applyConfigToUI();
    }
}

// Save to localStorage
function saveStyleConfig() {
    localStorage.setItem('asql_style_config', JSON.stringify(styleConfig));
}

// Apply config to UI dropdowns
function applyConfigToUI() {
    document.getElementById('setting-equality').value = styleConfig.equality;
    document.getElementById('setting-count').value = styleConfig.count;
    document.getElementById('setting-coalesce').value = styleConfig.coalesce;
    document.getElementById('setting-limit').value = styleConfig.limit;
    document.getElementById('setting-descending').value = styleConfig.descending;
    document.getElementById('setting-cast').value = styleConfig.cast;
    document.getElementById('setting-quotes').value = styleConfig.quotes;
    document.getElementById('setting-week-start').value = styleConfig.week_start;
}

// Read config from UI dropdowns
function readConfigFromUI() {
    styleConfig = {
        equality: document.getElementById('setting-equality').value,
        count: document.getElementById('setting-count').value,
        coalesce: document.getElementById('setting-coalesce').value,
        limit: document.getElementById('setting-limit').value,
        descending: document.getElementById('setting-descending').value,
        cast: document.getElementById('setting-cast').value,
        quotes: document.getElementById('setting-quotes').value,
        week_start: document.getElementById('setting-week-start').value,
    };
}
```

### Event Handlers

```javascript
// Toggle settings panel
function toggleSettings() {
    const content = document.getElementById('settings-content');
    const toggle = document.getElementById('settings-toggle');
    content.classList.toggle('open');
    toggle.classList.toggle('open');
}

// Apply preset
function applyPreset(presetName) {
    if (PRESETS[presetName]) {
        styleConfig = { ...PRESETS[presetName] };
        applyConfigToUI();
        saveStyleConfig();
        
        // Re-normalize current input if it's ASQL
        const fromDialect = document.getElementById('from-dialect').value;
        if (fromDialect === 'asql') {
            normalizeInput();
        }
    }
}

// Called when any individual setting changes
function updateStyle() {
    readConfigFromUI();
    saveStyleConfig();
    
    // Update preset dropdown to "Custom" if it doesn't match any preset
    updatePresetDropdown();
    
    // Re-normalize current input if it's ASQL
    const fromDialect = document.getElementById('from-dialect').value;
    if (fromDialect === 'asql') {
        normalizeInput();
    }
}

// Check if current config matches a preset
function updatePresetDropdown() {
    const presetSelect = document.getElementById('setting-preset');
    
    for (const [name, preset] of Object.entries(PRESETS)) {
        if (JSON.stringify(styleConfig) === JSON.stringify(preset)) {
            presetSelect.value = name;
            return;
        }
    }
    
    // No match - could add a "Custom" option
    // presetSelect.value = 'custom';
}
```

### Normalize API Call

```javascript
// Normalize ASQL to user's preferred style
async function normalizeASQL(asqlInput) {
    try {
        const response = await fetch('/api/normalize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                asql: asqlInput,
                style: styleConfig,
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            console.error('Normalize error:', data.error);
            return asqlInput;  // Return original on error
        }
        
        return data.asql;
    } catch (error) {
        console.error('Normalize failed:', error);
        return asqlInput;  // Return original on error
    }
}

// Re-normalize the input editor
async function normalizeInput() {
    const input = inputEditor.getValue();
    if (!input.trim()) return;
    
    const normalized = await normalizeASQL(input);
    
    // Only update if different (avoid cursor jump)
    if (normalized !== input) {
        const cursor = inputEditor.getCursor();
        inputEditor.setValue(normalized);
        inputEditor.setCursor(cursor);
    }
}
```

### Loading Examples with Style

```javascript
// When user clicks an example
async function loadExample(exampleQuery) {
    // Normalize to user's preferred style
    const normalized = await normalizeASQL(exampleQuery);
    
    // Set in editor
    inputEditor.setValue(normalized);
    
    // Trigger translation to SQL
    translateQuery();
}
```

---

## Backend API Endpoint

Add to `playground.py`:

```python
@app.route('/api/normalize', methods=['POST'])
def api_normalize():
    """Normalize ASQL to configured style."""
    try:
        data = request.get_json()
        asql_query = data.get('asql', '')
        style_config = data.get('style', {})
        
        if not asql_query.strip():
            return jsonify({'error': 'Empty ASQL query'})
        
        # Build config from style options
        from asql.config import ASQLConfig, StyleConfig
        
        style = StyleConfig(
            equality=style_config.get('equality', 'double'),
            count=style_config.get('count', 'hash'),
            coalesce=style_config.get('coalesce', 'operator'),
            limit=style_config.get('limit', 'take'),
            descending=style_config.get('descending', 'prefix'),
            cast=style_config.get('cast', 'double_colon'),
            quotes=style_config.get('quotes', 'double'),
            week_start=style_config.get('week_start', 'monday'),
        )
        
        config = ASQLConfig(style=style)
        
        # Normalize: ASQL → SQL → ASQL (with config)
        from asql import compile
        from asql.reverse_compiler import reverse_compile
        
        sql = compile(asql_query, dialect='snowflake')
        normalized = reverse_compile(sql, config=config)
        
        return jsonify({'asql': normalized})
        
    except Exception as e:
        return jsonify({'error': str(e)})
```

---

## Integration with Existing Playground

### Initialization

Add to the `DOMContentLoaded` handler:

```javascript
document.addEventListener('DOMContentLoaded', function() {
    // ... existing init code ...
    
    // Load style config from localStorage
    loadStyleConfig();
    
    // ... rest of init ...
});
```

### Modify Example Loading

Update the example button click handlers:

```javascript
// Before:
btn.onclick = () => {
    inputEditor.setValue(example.query);
    translateQuery();
};

// After:
btn.onclick = async () => {
    // Normalize example to user's style before displaying
    const normalized = await normalizeASQL(example.query);
    inputEditor.setValue(normalized);
    translateQuery();
};
```

### Modify SQL → ASQL Translation

When converting SQL to ASQL, use the style config:

```javascript
// In the sql-to-asql branch of translateQuery()
const response = await fetch('/api/reverse-compile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
        sql: input, 
        source_dialect: sourceDialect || '',
        style: styleConfig,  // Add style config
    })
});
```

---

## Example Transformation

With `sql-compat` preset:

**Example (stored in default style):**
```asql
from users
where status == "active"
group by country ( # as total_users )
order by -total_users
take 10
```

**Displayed to user (normalized to sql-compat):**
```asql
from users
where status = 'active'
group by country ( count(*) as total_users )
order by total_users DESC
limit 10
```

---

## Summary

1. **Settings panel** with preset selector + individual option dropdowns
2. **localStorage** persistence for user preferences
3. **`/api/normalize` endpoint** that uses ASQL config system
4. **Examples normalized on click** to user's preferred style
5. **SQL→ASQL uses style config** for consistent output

The key insight: examples are written ONCE, displayed in user's chosen style via `normalize()`.
