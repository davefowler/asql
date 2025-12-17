# ASQL Syntax Highlighters

This directory contains syntax highlighting definitions for ASQL (Analytic SQL) for various editors and tools.

## Structure

```
syntax/
├── README.md                    # This file
├── codemirror/                  # CodeMirror syntax highlighter
│   └── asql-mode.js            # CodeMirror mode definition
└── vscode/                      # VS Code syntax highlighter (future)
    └── asql.tmLanguage.json    # TextMate grammar (already exists in vscode-extension/)
```

## CodeMirror

### File: `codemirror/asql-mode.js`

A standalone CodeMirror mode for ASQL syntax highlighting.

### Features

- **Keywords**: `from`, `where`, `select`, `project`, `group by`, `order by`, `limit`, `join`, `with`, etc.
- **Functions**: `sum`, `avg`, `count`, `min`, `max`, `month`, `year`, `date_trunc`, etc.
- **Operators**: `==`, `!=`, `<=`, `>=`, `<`, `>`, `+`, `-`, `*`, `/`, `%`, `|`
- **Strings**: Single and double quoted strings with escape sequences
- **Numbers**: Integers and floats (including negative numbers)
- **Comments**: `#` to end of line
- **Special ASQL syntax**:
  - `#` - Count shorthand
  - `-column` - Descending order prefix
  - Multi-word keywords: `group by`, `not in`, `is null`, `is not null`

### Usage

#### In HTML

```html
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.css">
</head>
<body>
    <div id="editor"></div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.js"></script>
    <script src="syntax/codemirror/asql-mode.js"></script>
    <script>
        const editor = CodeMirror(document.getElementById('editor'), {
            mode: 'text/x-asql',
            lineNumbers: true,
            lineWrapping: true,
            value: 'from users\nwhere status == "active"'
        });
    </script>
</body>
</html>
```

#### With RequireJS/AMD

```javascript
require(['codemirror', 'syntax/codemirror/asql-mode'], function(CodeMirror) {
    const editor = CodeMirror(document.getElementById('editor'), {
        mode: 'text/x-asql',
        lineNumbers: true
    });
});
```

#### With CommonJS/Node.js

```javascript
const CodeMirror = require('codemirror');
require('./syntax/codemirror/asql-mode');

const editor = CodeMirror(document.getElementById('editor'), {
    mode: 'text/x-asql',
    lineNumbers: true
});
```

### Token Types

The mode returns the following token types (which can be styled with CSS):

- `keyword` - ASQL keywords (from, where, select, etc.)
- `def` - Function names (sum, avg, count, etc.)
- `operator` - Operators (==, !=, +, -, etc.)
- `string` - String literals
- `number` - Numeric literals
- `comment` - Comments (# ...)
- `atom` - Boolean and null values
- `variable` - Identifiers (table names, column names, etc.)

### CSS Styling Example

```css
.cm-keyword { color: #ea4335; font-weight: 600; }
.cm-def { color: #ea4335; font-weight: 500; }
.cm-operator { color: #ea4335; }
.cm-string { color: #137333; }
.cm-number { color: #1967d2; }
.cm-comment { color: #999; font-style: italic; }
.cm-atom { color: #1967d2; }
.cm-variable { color: #333; }
```

## VS Code

VS Code syntax highlighting is already implemented in the `vscode-extension/` directory:

- **File**: `vscode-extension/syntaxes/asql.tmLanguage.json`
- **Format**: TextMate grammar (JSON)
- **Usage**: Install the VS Code extension or copy the grammar file

See `vscode-extension/README.md` for more details.

## Contributing

When adding new syntax highlighters:

1. Create a new subdirectory for the editor/tool
2. Add the highlighter files
3. Update this README with usage instructions
4. Ensure the highlighter covers all ASQL features from `SPEC.md`

## References

- [ASQL Language Specification](../SPEC.md)
- [CodeMirror Mode Development Guide](https://codemirror.net/doc/manual.html#modeapi)
- [TextMate Grammar Documentation](https://macromates.com/manual/en/language_grammars)

