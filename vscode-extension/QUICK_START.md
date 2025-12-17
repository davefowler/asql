# Quick Start - ASQL VS Code Extension

Get up and running with ASQL syntax highlighting in VS Code in under 2 minutes!

## Installation

### Option 1: Install from VSIX (Easiest)

1. Download `asql-vscode-0.1.0.vsix` from releases
2. Open VS Code
3. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS)
4. Type "Extensions: Install from VSIX..."
5. Select the `.vsix` file
6. Done! ✅

### Option 2: Manual Installation

1. Copy the `vscode-extension` folder to:
   - **Windows**: `%USERPROFILE%\.vscode\extensions\asql-vscode-0.1.0\`
   - **macOS/Linux**: `~/.vscode/extensions/asql-vscode-0.1.0/`

2. Reload VS Code (`Ctrl+R` or `Cmd+R`)

## Test It Out

1. **Create a new file**: `test.asql`

2. **Type this query**:
   ```asql
   from users
   where status == "active"
   group by country ( # as total_users )
   order by -total_users
   ```

3. **You should see**:
   - `from`, `where`, `group by`, `order by` highlighted as keywords
   - `==` highlighted as an operator
   - `"active"` highlighted as a string
   - `#` highlighted as a special symbol

## Try Snippets

1. **Type `from`** and press `Tab`
   - Expands to: `from ${1:table_name}`

2. **Type `groupby`** and press `Tab`
   - Expands to: `group by ${1:column} ( # as ${2:count_name} )`

3. **Type `query`** and press `Tab`
   - Expands to a complete query template

## What's Next?

- 📖 Read the [full README](README.md) for all features
- 🔧 See [installation guide](INSTALLATION.md) for detailed setup
- 🎨 Check [VS Code integration guide](VSCODE_INTEGRATION.md) for advanced features
- 💻 Try the [ASQL playground](../playground.py) to test queries

## Troubleshooting

**Syntax highlighting not working?**
- Make sure file has `.asql` extension
- Check language mode (bottom-right): should say "ASQL"
- Reload VS Code: `Ctrl+Shift+P` → "Developer: Reload Window"

**Snippets not working?**
- Type snippet prefix (e.g., `from`)
- Press `Ctrl+Space` to see suggestions
- Press `Tab` to insert

Need help? Check the [main ASQL repository](https://github.com/asql-lang/asql)!
