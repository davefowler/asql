# Visual Editor V2 - Debugging Handoff

## Current State

The v2 visual editor (`playground/static/visual-editor-v2/visual-editor.js`) has been created to replace the old visual editor. It's set as the default but has several issues that need debugging with browser tools.

## Known Issues

### 1. Duplicate FROM Blocks
- **Symptom**: Two "FROM" blocks appear - one from static HTML template, one from v2 rendering
- **Root Cause**: The `hideStaticElements()` function isn't working properly
- **Location**: Lines 138-153 in `visual-editor.js`
- **Fix attempted**: Updated CSS selector to `#visual-editor-container > .visual-editor > .block.from-block`
- **Debug**: Check if the selector matches the DOM, check if hideStaticElements() is being called

### 2. Transforms Not Rendering
- **Symptom**: When loading a Visual ASQL example, the SQL output shows the correct query but the visual editor shows empty pipelines (just FROM blocks, no transforms)
- **Possible causes**:
  - `loadFromJSON()` not being called by playground.js
  - Data not flowing through to v2's renderAll()
  - Transform rendering failing silently
- **Debug**: Add console.log in loadFromJSON(), check if pipeline.transforms exists

### 3. "cols" Toggle Not Showing Columns
- **Symptom**: The "cols" button doesn't show output columns
- **Root Cause**: `output_columns` property not populated in example data
- **Fix attempted**: Added `loadTableColumns()` to fetch from `/api/schema/tables/{table}` API
- **Debug**: Check network tab for API calls, verify output_columns is populated after table selection

## Key Files

- **V2 Editor**: `playground/static/visual-editor-v2/visual-editor.js`
- **V2 CSS**: `playground/static/visual-editor-v2/visual-editor.css`  
- **Old Editor** (reference): `playground/static/visual-editor.js`
- **HTML Template**: `playground/templates/index.html`
- **Playground JS**: `playground/static/playground.js`
- **Example Data**: `playground/examples/visual_asql.json`

## API Methods V2 Must Implement

These are called by `playground.js`:

```javascript
// Load from JSON object (visual-asql format)
async loadFromJSON(json)

// Load from ASQL text (calls /api/visual/parse)
async loadFromASQL(asql)

// Get ASQL text (calls /api/visual/compile)
async getASQL()

// Initialize
async init()

// Property
initialized: boolean
```

## Recent Changes Made

1. Removed "Pipeline name (for CTE)" header - ASQL uses "stash as {name}" transform instead
2. Added `hideStaticElements()` to hide conflicting static HTML
3. Added `loadFromJSON()`, `loadFromASQL()`, `getASQL()` API methods
4. Added `loadTableColumns()` to fetch schema for cols toggle

## Debugging Steps

1. **Open browser console** on http://localhost:5001
2. **Check if v2 is initialized**: `console.log(visualEditor, visualEditor?.initialized)`
3. **Load a Visual ASQL example** from Examples modal
4. **Check data flow**: 
   ```javascript
   console.log('Pipelines:', visualEditor.pipelines)
   console.log('Transforms:', visualEditor.pipelines[0]?.transforms)
   ```
5. **Check if static elements hidden**: Inspect DOM for duplicate FROM blocks
6. **Test cols toggle**: Select a table, click "cols", check if output_columns populated

## What Should Work When Fixed

1. Single FROM block (not duplicated)
2. All transforms from example render as blocks (JOIN, WHERE, EXTEND, GROUP BY, etc.)
3. "cols" button shows table columns after selecting a table
4. Adding new transforms via "+ add step" dropdown
5. Drag-and-drop reordering of transforms

## Architecture Notes

- V2 renders into `#transforms-container` (inside `#visual-editor-container > .visual-editor`)
- Uses `Expression` class from `expression.js` for recursive expression building (not fully integrated yet)
- Uses `SortableJS` for drag-and-drop (loaded from CDN)
- CSS supports two modes: `.visual-style-text` and `.visual-style-blocky`

## Server

Run with: `./venv/bin/python -m uvicorn playground.app:app --reload --port 5001`
