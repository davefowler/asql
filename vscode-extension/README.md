# ASQL VS Code Extension

VS Code extension providing syntax highlighting, snippets, and language support for ASQL (Analytic SQL).

## Features

- ✅ **Syntax Highlighting** - Full TextMate grammar support for ASQL syntax
- ✅ **Code Snippets** - Quick snippets for common ASQL patterns
- ✅ **Language Configuration** - Comments, brackets, auto-closing pairs
- ✅ **Indentation Support** - Smart indentation for pipeline syntax

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/asql-lang/asql.git
   cd asql/vscode-extension
   ```

2. Install dependencies (if needed):
   ```bash
   npm install -g vsce
   ```

3. Package the extension:
   ```bash
   vsce package
   ```

4. Install the `.vsix` file:
   - Open VS Code
   - Go to Extensions view (`Ctrl+Shift+X` / `Cmd+Shift+X`)
   - Click `...` menu → "Install from VSIX..."
   - Select the generated `.vsix` file

### Manual Installation

1. Copy the `vscode-extension` folder to your VS Code extensions directory:
   - **Windows**: `%USERPROFILE%\.vscode\extensions\asql-vscode-0.1.0\`
   - **macOS**: `~/.vscode/extensions/asql-vscode-0.1.0/`
   - **Linux**: `~/.vscode/extensions/asql-vscode-0.1.0/`

2. Reload VS Code (`Ctrl+R` / `Cmd+R`)

## Usage

### File Association

Files with `.asql` extension will automatically be recognized as ASQL files.

To associate other extensions:
1. Open VS Code Settings (`Ctrl+,` / `Cmd+,`)
2. Search for "file associations"
3. Add: `"*.asql": "asql"`

### Snippets

Type snippet prefixes and press `Tab`:

- `from` → Basic FROM clause
- `fromwhere` → FROM with WHERE
- `groupby` → GROUP BY with aggregation
- `sort` → Sort descending
- `query` → Complete query pipeline
- `join` → JOIN clause
- `set` → SET variable (CTE)

### Syntax Highlighting

The extension highlights:
- **Keywords**: `from`, `where`, `select`, `group by`, `sort`, `take`
- **Operators**: `==`, `!=`, `in`, `not in`, `and`, `or`
- **Functions**: `sum()`, `avg()`, `count()`, `month()`, etc.
- **Literals**: Strings, numbers, booleans
- **Comments**: `#` line comments

## Language Features

### Comments
- Line comments: `# This is a comment`

### Auto-closing Pairs
- Parentheses: `()`
- Brackets: `[]`
- Braces: `{}`
- Quotes: `""` and `''`

### Indentation
The extension supports smart indentation for ASQL's pipeline syntax:
```asql
from users
  where status == "active"
  group by country ( # as total_users )
  sort -total_users
```

## Example ASQL File

Create a file `example.asql`:

```asql
# Get active users by country
from users
  where status == "active"
  group by country ( # as total_users )
  sort -total_users
  take 10
```

## Contributing

Contributions welcome! Please see the main [ASQL repository](https://github.com/asql-lang/asql) for contribution guidelines.

## Related Tools

- **ASQL Compiler**: [asql Python package](https://github.com/asql-lang/asql)
- **Language Specification**: See `SPEC.md` in the main repository
- **Documentation**: See `docs/` directory in the main repository


### 0.1.0
- Initial release
- Syntax highlighting for ASQL
- Code snippets for common patterns
- Language configuration
- Indentation support
