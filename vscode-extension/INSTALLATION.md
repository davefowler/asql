# Installation Guide - ASQL VS Code Extension

## Prerequisites

- Visual Studio Code 1.74.0 or higher
- Node.js (for building from source, optional)

## Installation Methods

### Method 1: Install from VSIX (Recommended)

1. **Download the extension**:
   - Get the latest `.vsix` file from releases
   - Or build it yourself (see Method 3)

2. **Install in VS Code**:
   - Open VS Code
   - Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS)
   - Type "Extensions: Install from VSIX..."
   - Select the `.vsix` file
   - Reload VS Code if prompted

### Method 2: Manual Installation

1. **Locate VS Code extensions directory**:
   - **Windows**: `%USERPROFILE%\.vscode\extensions\`
   - **macOS**: `~/.vscode/extensions/`
   - **Linux**: `~/.vscode/extensions/`

2. **Copy extension files**:
   ```bash
   # Create extension directory
   mkdir -p ~/.vscode/extensions/asql-vscode-0.1.0
   
   # Copy all files from vscode-extension/ to the new directory
   cp -r vscode-extension/* ~/.vscode/extensions/asql-vscode-0.1.0/
   ```

3. **Reload VS Code**:
   - Press `Ctrl+R` (Windows/Linux) or `Cmd+R` (macOS)
   - Or restart VS Code

### Method 3: Build from Source

1. **Install VS Code Extension Manager**:
   ```bash
   npm install -g @vscode/vsce
   ```

2. **Navigate to extension directory**:
   ```bash
   cd vscode-extension
   ```

3. **Package the extension**:
   ```bash
   vsce package
   ```
   This creates `asql-vscode-0.1.0.vsix`

4. **Install the VSIX** (see Method 1)

## Verification

1. **Create a test file**:
   - Create `test.asql` with:
     ```asql
     from users
     where status == "active"
     ```

2. **Check syntax highlighting**:
   - `from` should be highlighted as a keyword
   - `users` should be highlighted as an identifier
   - `where` should be highlighted as a keyword
   - `==` should be highlighted as an operator

3. **Test snippets**:
   - Type `from` and press `Tab`
   - Should expand to: `from ${1:table_name}`

4. **Check file association**:
   - Open `.asql` file
   - Bottom-right corner should show "ASQL" as language mode

## Troubleshooting

### Extension not loading

1. **Check VS Code version**:
   - Ensure VS Code 1.74.0 or higher
   - Check: Help → About

2. **Check extension files**:
   - Ensure `package.json` exists in extension directory
   - Ensure `syntaxes/asql.tmLanguage.json` exists

3. **Reload VS Code**:
   - Press `Ctrl+Shift+P` → "Developer: Reload Window"

### Syntax highlighting not working

1. **Check file association**:
   - Open `.asql` file
   - Click language mode (bottom-right)
   - Select "ASQL"

2. **Check grammar file**:
   - Ensure `syntaxes/asql.tmLanguage.json` is valid JSON
   - Check VS Code Developer Console for errors:
     - Help → Toggle Developer Tools
     - Look for errors in Console tab

### Snippets not working

1. **Check snippets file**:
   - Ensure `snippets/asql.json` exists and is valid JSON

2. **Test snippet**:
   - Open `.asql` file
   - Type snippet prefix (e.g., `from`)
   - Press `Ctrl+Space` to see suggestions
   - Press `Tab` to insert

## Uninstallation

1. **Remove extension**:
   - Press `Ctrl+Shift+X` to open Extensions view
   - Search for "ASQL"
   - Click gear icon → Uninstall

2. **Or manually delete**:
   ```bash
   rm -rf ~/.vscode/extensions/asql-vscode-0.1.0
   ```

3. **Reload VS Code**

## Next Steps

- Read the [README.md](README.md) for usage instructions
- Check out [ASQL documentation](https://github.com/asql-lang/asql) for language features
- Try the [interactive playground](https://github.com/asql-lang/asql#playground)
