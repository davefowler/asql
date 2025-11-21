# ASQL Interactive Playground

The ASQL Interactive Playground is a web-based tool that lets you write ASQL queries and see the generated SQL in real-time. It's similar to SQLBox from dataschool.com, providing an interactive learning and experimentation environment.

<div style="margin: 30px 0; border: 1px solid #dadce0; border-radius: 8px; overflow: hidden;">
    <iframe src="/playground/embed" style="width: 100%; height: 900px; border: none;" frameborder="0" title="ASQL Playground"></iframe>
</div>

**Note**: If the playground doesn't load above, you can also [open it in a new tab](/playground) or access it directly at `http://localhost:5001`.

## Features

- ✨ **Real-time Compilation** - See SQL output as you type
- 🎨 **Clean Interface** - Split-panel view with ASQL input and SQL output
- 📝 **Example Library** - Pre-built example queries to learn from
- 🔄 **Multiple Dialects** - Switch between PostgreSQL, MySQL, BigQuery, and more
- 📋 **Copy to Clipboard** - Easy copying of queries
- 🚀 **No Setup Required** - Just run and open in your browser

## Quick Start

### Installation

```bash
# Install playground dependencies
pip install -e ".[playground]"
```

### Running the Playground

```bash
python playground.py
```

Then open http://localhost:5000 in your browser.

## Usage

### Writing Queries

1. Type your ASQL query in the left panel
2. The SQL output appears automatically in the right panel (with a 500ms debounce)
3. Or click "Compile to SQL" to compile immediately

### Selecting a Dialect

Use the dropdown menu to select your target SQL dialect:
- Default (ANSI SQL)
- PostgreSQL
- MySQL
- BigQuery
- Snowflake
- Redshift

### Using Examples

Click any example button to load it into the editor. Examples are organized by category:
- Basic queries
- Filtering
- Aggregations
- Sorting and limiting
- Complex queries

### Copying Queries

Click the "Copy" button in either panel header to copy the query to your clipboard.

## Example Workflow

1. **Start with an example**: Click "Simple FROM" to load a basic query
2. **Modify it**: Change the table name or add conditions
3. **See the SQL**: Watch the SQL update in real-time
4. **Try different dialects**: Switch between PostgreSQL and MySQL to see differences
5. **Experiment**: Try adding GROUP BY, SORT, or other clauses

## API Endpoint

The playground also exposes a REST API endpoint for programmatic use:

```bash
curl -X POST http://localhost:5000/api/compile \
  -H "Content-Type: application/json" \
  -d '{"asql": "from users", "dialect": "postgres"}'
```

Response:
```json
{
  "sql": "SELECT * FROM users"
}
```

## Architecture

The playground consists of:

- **Frontend**: Single-page HTML/JavaScript application
- **Backend**: Flask web server with compilation API
- **Compiler**: ASQL compiler using SQLGlot for SQL generation

## Customization

### Adding Examples

Edit the `examples` array in `playground.py`:

```javascript
const examples = [
    {
        title: "My Example",
        desc: "Description",
        query: "from my_table"
    },
    // ... more examples
];
```

### Changing Port

Modify the `app.run()` call at the bottom of `playground.py`:

```python
app.run(debug=True, host='0.0.0.0', port=8080)  # Change port here
```

### Styling

The playground uses inline CSS. Modify the `<style>` section in `PLAYGROUND_HTML` to customize the appearance.

## Future Enhancements

Potential improvements:
- [ ] Syntax highlighting for ASQL
- [ ] SQL syntax highlighting
- [ ] Query execution against sample databases
- [ ] Query history
- [ ] Export queries as Python code
- [ ] Shareable query links
- [ ] Dark mode
- [ ] Mobile-responsive design improvements

## Troubleshooting

### Port Already in Use

If port 5000 is already in use, change it in `playground.py`:

```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

### Module Not Found

Make sure you've installed the playground dependencies:

```bash
pip install -e ".[playground]"
```

### Compilation Errors

If you see compilation errors, check:
1. Your ASQL syntax is correct
2. You're using supported features
3. The dialect supports the generated SQL

## Contributing

To improve the playground:
1. Add new examples
2. Improve the UI/UX
3. Add new features
4. Fix bugs

Submit pull requests with your improvements!
