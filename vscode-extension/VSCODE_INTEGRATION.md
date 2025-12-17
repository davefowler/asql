# VS Code Integration Guide

This document describes the VS Code integration features for ASQL, inspired by PRQL's VS Code tooling.

## Overview

The ASQL VS Code extension provides:
- **Syntax Highlighting** - Full TextMate grammar support
- **Code Snippets** - Quick templates for common patterns
- **Language Configuration** - Comments, brackets, indentation
- **File Association** - Automatic recognition of `.asql` files

## Comparison with PRQL

PRQL's VS Code extension includes:
- Syntax highlighting (TextMate grammar)
- Language server (LSP) for diagnostics and formatting
- Code snippets
- Language configuration

Our ASQL extension currently provides:
- ✅ Syntax highlighting (TextMate grammar)
- ✅ Code snippets
- ✅ Language configuration
- ⏳ Language server (planned for future)

## Features

### 1. Syntax Highlighting

The TextMate grammar (`syntaxes/asql.tmLanguage.json`) highlights:

- **Keywords**: `from`, `where`, `select`, `group by`, `order by`, `limit`, `join`, `with`
- **Operators**: `==`, `!=`, `in`, `not in`, `and`, `or`, `not`
- **Functions**: `sum()`, `avg()`, `count()`, `month()`, `year()`, etc.
- **Literals**: Strings (`"..."`), numbers, booleans (`true`, `false`, `null`)
- **Comments**: `#` line comments
- **Special syntax**: `#` for COUNT shorthand, `-` prefix for descending sort

### 2. Code Snippets

Quick snippets for common ASQL patterns:

| Prefix | Description | Output |
|--------|-------------|--------|
| `from` | Basic FROM clause | `from ${1:table_name}` |
| `fromwhere` | FROM with WHERE | `from ${1:table_name}\nwhere ${2:condition}` |
| `groupby` | GROUP BY with COUNT | `group by ${1:column} ( # as ${2:count_name} )` |
| `order by` | Sort descending | `order by -${1:column}` |
| `query` | Complete pipeline | Full query template |

### 3. Language Configuration

Configured in `language-configuration.json`:

- **Comments**: `#` for line comments
- **Brackets**: `()`, `[]`, `{}`
- **Auto-closing**: Parentheses, brackets, quotes
- **Word pattern**: Identifiers (alphanumeric + underscore)
- **Indentation**: Smart indentation for pipeline syntax

### 4. File Association

Files with `.asql` extension are automatically recognized.

To associate other extensions:
```json
{
  "files.associations": {
    "*.asql": "asql"
  }
}
```

## Future Enhancements

### Language Server Protocol (LSP)

Planned features:
- **Syntax validation** - Real-time error checking
- **SQL preview** - Show generated SQL on hover
- **Formatting** - Auto-format ASQL queries
- **Go to definition** - Navigate to table/column definitions
- **Hover information** - Show SQL translation on hover
- **Code actions** - Quick fixes and refactorings

### Integration with ASQL Compiler

- Use Python ASQL compiler for validation
- Show compilation errors inline
- Preview SQL output in side panel
- Support for multiple SQL dialects

### Additional Features

- **Query execution** - Run ASQL queries directly from VS Code
- **Schema awareness** - Autocomplete table/column names
- **Query history** - Track and replay queries
- **Export options** - Export to SQL, copy as SQL, etc.

## Development

### Building the Extension

```bash
# Install VS Code Extension Manager
npm install -g @vscode/vsce

# Package extension
cd vscode-extension
vsce package
```

### Testing

1. Open VS Code
2. Press `F5` to launch Extension Development Host
3. Create `.asql` file and test syntax highlighting
4. Test snippets and language features

### File Structure

```
vscode-extension/
├── package.json              # Extension manifest
├── language-configuration.json  # Language settings
├── syntaxes/
│   └── asql.tmLanguage.json  # TextMate grammar
├── snippets/
│   └── asql.json             # Code snippets
├── README.md                 # User documentation
├── INSTALLATION.md           # Installation guide
└── CHANGELOG.md              # Version history
```

## Resources

- [VS Code Extension API](https://code.visualstudio.com/api)
- [TextMate Grammar Guide](https://macromates.com/manual/en/language_grammars)
- [Language Server Protocol](https://microsoft.github.io/language-server-protocol/)
- [PRQL VS Code Extension](https://github.com/prql-lang/prql/tree/main/prql-vscode) (reference)

## Contributing

To improve the VS Code integration:

1. **Syntax highlighting**: Edit `syntaxes/asql.tmLanguage.json`
2. **Snippets**: Edit `snippets/asql.json`
3. **Language config**: Edit `language-configuration.json`
4. **Documentation**: Update README.md and this file

See the main [ASQL repository](https://github.com/asql-lang/asql) for contribution guidelines.
