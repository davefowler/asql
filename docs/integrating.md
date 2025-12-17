# Integrating Analytic SQL

**Last Updated:** November 16, 2025

This guide shows how to integrate Analytic SQL into your applications and workflows, whether as a Python library or integrated into other tools like dbt, BI platforms, or databases.

## Using as a Python Library

### Basic Usage

The simplest way to use Analytic SQL is as a Python library:

```python
from asql import compile

# Basic query
asql_query = """
from users
where status == "active"
group by country ( # as total_users )
order by -total_users
limit 10
"""

sql = compile(asql_query, dialect="postgres")
print(sql)
```

### API Reference

#### `compile(asql_query, dialect=None, pretty=False)`

Compiles an ASQL query to SQL.

**Parameters:**
- `asql_query` (str): ASQL query string. Can contain multiple queries separated by semicolons.
- `dialect` (str, optional): Target SQL dialect. Supported dialects include:
  - `postgres` / `postgresql`
  - `mysql`
  - `bigquery`
  - `snowflake`
  - `redshift`
  - `sqlite`
  - `oracle`
  - `mssql` / `sqlserver`
  - And more (see SQLGlot dialects)
- `pretty` (bool): Whether to format SQL output with indentation. Default: `False`

**Returns:**
- `str`: Generated SQL query

**Raises:**
- `ASQLSyntaxError`: If ASQL syntax is invalid
- `ASQLCompilationError`: If compilation fails

**Example:**
```python
from asql import compile

# Single query
sql = compile("""
from users
where status == 'active'
""", dialect="postgres")

# Query with CTE using stash as
multi_query = """
from users where status == 'active' stash as active_users
from active_users group by country ( # as total )
"""

sql = compile(multi_query, dialect="bigquery", pretty=True)
```

#### `reverse_compile(sql_query, source_dialect=None)`

Converts SQL back to ASQL syntax.

**Parameters:**
- `sql_query` (str): SQL query string
- `source_dialect` (str, optional): Source SQL dialect for better parsing

**Returns:**
- `str`: ASQL query string

**Example:**
```python
from asql import reverse_compile

sql = "SELECT country, COUNT(*) AS total FROM users WHERE status = 'active' GROUP BY country"
asql = reverse_compile(sql)
# Returns:
# from users
# where status == 'active'
# group by country ( # as total )
```

#### `detect_dialect(sql_query)`

Attempts to detect the SQL dialect from a query.

**Parameters:**
- `sql_query` (str): SQL query string

**Returns:**
- `str` or `None`: Detected dialect name or `None` if detection fails

### Error Handling

```python
from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError

try:
    sql = compile("""
from users
where invalid syntax
""")
except ASQLSyntaxError as e:
    print(f"Syntax error: {e}")
except ASQLCompilationError as e:
    print(f"Compilation error: {e}")
```

### Advanced Usage

#### Pretty Printing

```python
sql = compile(asql_query, dialect="postgres", pretty=True)
# Returns formatted SQL with indentation
```

#### Multiple Dialects

```python
asql_query = """
from users
group by country ( # as total )
"""

dialects = ["postgres", "bigquery", "snowflake"]
for dialect in dialects:
    sql = compile(asql_query, dialect=dialect)
    print(f"{dialect}: {sql}")
```

#### Batch Compilation

```python
queries = [
    """
from users
where status == 'active'
""",
    """
from orders
where amount > 100
""",
    """
from products
where category == 'electronics'
"""
]

compiled = []
for query in queries:
    try:
        sql = compile(query, dialect="postgres")
        compiled.append(sql)
    except ASQLSyntaxError as e:
        print(f"Error in query: {e}")
```

## Integration Patterns

### Integration with dbt

Analytic SQL can be integrated into dbt workflows in several ways:

#### Option 1: Pre-compile ASQL to SQL

Create a dbt macro that compiles ASQL queries:

```python
# macros/asql_compile.sql
{% macro asql_compile(asql_query, dialect=target.type) %}
  {{ return(run_query("SELECT asql_compile('" + asql_query + "', '" + dialect + "')")) }}
{% endmacro %}
```

Then use it in dbt models:

```sql
-- models/active_users.sql
{{ asql_compile("""
from users
where status == 'active'
group by country ( # as total_users )
""", dialect=target.type) }}
```

#### Option 2: Python Script Pre-processing

Use a Python script to compile ASQL files before dbt runs:

```python
# scripts/compile_asql.py
import os
from pathlib import Path
from asql import compile

def compile_asql_files():
    """Compile .asql files to .sql files for dbt."""
    asql_dir = Path("models/asql")
    sql_dir = Path("models/compiled")
    
    for asql_file in asql_dir.glob("*.asql"):
        with open(asql_file) as f:
            asql_query = f.read()
        
        # Compile to SQL
        sql = compile(asql_query, dialect="postgres")
        
        # Write to compiled directory
        sql_file = sql_dir / (asql_file.stem + ".sql")
        with open(sql_file, "w") as f:
            f.write(sql)

if __name__ == "__main__":
    compile_asql_files()
```

Run before dbt:
```bash
python scripts/compile_asql.py && dbt run
```

#### Option 3: dbt Python Model

Use dbt's Python models to compile ASQL dynamically:

```python
# models/active_users.py
def model(dbt, session):
    from asql import compile
    
    asql_query = """
    from {{ ref('users') }}
    where status == 'active'
    group by country ( # as total_users )
    """
    
    # Replace dbt refs with actual table names
    asql_query = asql_query.replace("{{ ref('users') }}", "users")
    
    sql = compile(asql_query, dialect=dbt.config.get('target_type', 'postgres'))
    
    return session.sql(sql)
```

### Integration with BI Tools

#### Tableau Custom SQL

Create a wrapper that converts ASQL to SQL for Tableau:

```python
# tableau_asql_wrapper.py
from asql import compile

def tableau_query(asql_query, dialect="postgres"):
    """Convert ASQL to SQL for Tableau Custom SQL."""
    sql = compile(asql_query, dialect=dialect)
    return sql

# Usage in Tableau Custom SQL:
# Use Python script to generate SQL, then paste into Tableau
```

#### Looker (LookML) Integration

Create a LookML macro that uses ASQL:

```python
# looker_asql_plugin.py
from asql import compile

def compile_asql_for_looker(asql_query, dialect):
    """Compile ASQL for Looker SQL Runner."""
    return compile(asql_query, dialect=dialect)
```

Then use in LookML:
```lookml
sql: |
  {% raw %}
  {{ compile_asql("""
  from users
  where status == 'active'
  """) }}
  {% endraw %}
```

#### Power BI Integration

Use Python script in Power BI:

```python
# powerbi_asql.py
import pandas as pd
from asql import compile
import pyodbc

def execute_asql(asql_query, connection_string, dialect="mssql"):
    """Execute ASQL query in Power BI."""
    sql = compile(asql_query, dialect=dialect)
    
    conn = pyodbc.connect(connection_string)
    df = pd.read_sql(sql, conn)
    conn.close()
    
    return df
```

### Integration with Databases

#### PostgreSQL Function

Create a PostgreSQL function that compiles ASQL:

```python
# postgres_asql_extension.py
from asql import compile
import psycopg2

def create_asql_function(conn):
    """Create PostgreSQL function for ASQL compilation."""
    cursor = conn.cursor()
    
    # This would require a PostgreSQL extension
    # For now, use Python wrapper
    pass

# Alternative: Use PL/Python
```

#### Database Driver Wrapper

Create a database driver that accepts ASQL:

```python
# asql_driver.py
from asql import compile
import psycopg2

class ASQLConnection:
    """Database connection that accepts ASQL queries."""
    
    def __init__(self, connection_string, dialect="postgres"):
        self.conn = psycopg2.connect(connection_string)
        self.dialect = dialect
    
    def execute(self, asql_query):
        """Execute ASQL query."""
        sql = compile(asql_query, dialect=self.dialect)
        cursor = self.conn.cursor()
        cursor.execute(sql)
        return cursor.fetchall()
    
    def close(self):
        self.conn.close()

# Usage
conn = ASQLConnection("postgresql://user:pass@localhost/db")
results = conn.execute("from users where status == 'active'")
conn.close()
```

### Building Custom Integrations

#### REST API Wrapper

Create a REST API that compiles ASQL:

```python
# api.py
from flask import Flask, request, jsonify
from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError

app = Flask(__name__)

@app.route('/api/compile', methods=['POST'])
def compile_asql():
    """Compile ASQL to SQL via REST API."""
    data = request.json
    asql_query = data.get('asql')
    dialect = data.get('dialect', 'postgres')
    pretty = data.get('pretty', False)
    
    try:
        sql = compile(asql_query, dialect=dialect, pretty=pretty)
        return jsonify({'sql': sql})
    except ASQLSyntaxError as e:
        return jsonify({'error': str(e)}), 400
    except ASQLCompilationError as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
```

#### Command-Line Tool

Create a CLI tool:

```python
# asql_cli.py
import argparse
from asql import compile
from asql.errors import ASQLSyntaxError

def main():
    parser = argparse.ArgumentParser(description='Compile ASQL to SQL')
    parser.add_argument('query', help='ASQL query string')
    parser.add_argument('--dialect', default='postgres', help='SQL dialect')
    parser.add_argument('--pretty', action='store_true', help='Pretty print SQL')
    parser.add_argument('--file', help='Read ASQL from file')
    
    args = parser.parse_args()
    
    if args.file:
        with open(args.file) as f:
            asql_query = f.read()
    else:
        asql_query = args.query
    
    try:
        sql = compile(asql_query, dialect=args.dialect, pretty=args.pretty)
        print(sql)
    except ASQLSyntaxError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
```

#### Jupyter Notebook Integration

Use in Jupyter notebooks:

```python
# jupyter_asql.py
from asql import compile
from IPython.display import display, Markdown

def asql_query(query, dialect="postgres", show_sql=True):
    """Execute ASQL query in Jupyter."""
    sql = compile(query, dialect=dialect, pretty=True)
    
    if show_sql:
        display(Markdown(f"**Generated SQL:**\n```sql\n{sql}\n```"))
    
    return sql

# Usage in notebook
sql = asql_query("""
from users
where status == 'active'
group by country ( # as total )
""")
```

#### VS Code Extension

Create a VS Code extension that compiles ASQL:

```typescript
// extension.ts
import * as vscode from 'vscode';
import { exec } from 'child_process';

export function activate(context: vscode.ExtensionContext) {
    let compileCommand = vscode.commands.registerCommand('asql.compile', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        
        const asqlQuery = editor.document.getText();
        const dialect = vscode.workspace.getConfiguration('asql').get('dialect', 'postgres');
        
        exec(`python -c "from asql import compile; print(compile('''${asqlQuery}''', dialect='${dialect}'))"`, 
            (error, stdout, stderr) => {
                if (error) {
                    vscode.window.showErrorMessage(`Compilation error: ${stderr}`);
                    return;
                }
                
                // Open new document with SQL
                vscode.workspace.openTextDocument({
                    content: stdout,
                    language: 'sql'
                }).then(doc => {
                    vscode.window.showTextDocument(doc);
                });
            });
    });
    
    context.subscriptions.push(compileCommand);
}
```

## Best Practices

### Error Handling

Always wrap compilation in try-except blocks:

```python
from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError

def safe_compile(asql_query, dialect="postgres"):
    """Safely compile ASQL with error handling."""
    try:
        return compile(asql_query, dialect=dialect)
    except ASQLSyntaxError as e:
        # Log syntax errors
        logger.error(f"ASQL syntax error: {e}")
        raise
    except ASQLCompilationError as e:
        # Log compilation errors
        logger.error(f"ASQL compilation error: {e}")
        raise
```

### Caching Compiled Queries

Cache compiled SQL for frequently used queries:

```python
from functools import lru_cache
from asql import compile

@lru_cache(maxsize=100)
def cached_compile(asql_query, dialect="postgres"):
    """Cache compiled ASQL queries."""
    return compile(asql_query, dialect=dialect)
```

### Validation

Validate ASQL before compilation:

```python
def validate_asql(asql_query):
    """Validate ASQL query syntax."""
    try:
        compile(asql_query, dialect="postgres")
        return True
    except ASQLSyntaxError:
        return False
```

### Performance Considerations

- Compile queries once and reuse SQL strings
- Use connection pooling for database integrations
- Consider caching for frequently used queries
- Batch compile multiple queries when possible

## Examples

### Complete Integration Example

Here's a complete example of integrating ASQL into a data pipeline:

```python
# data_pipeline.py
from asql import compile
import psycopg2
from typing import List, Dict

class ASQLPipeline:
    """Data pipeline using ASQL."""
    
    def __init__(self, connection_string, dialect="postgres"):
        self.conn = psycopg2.connect(connection_string)
        self.dialect = dialect
    
    def execute_query(self, asql_query: str) -> List[Dict]:
        """Execute ASQL query and return results."""
        sql = compile(asql_query, dialect=self.dialect)
        cursor = self.conn.cursor()
        cursor.execute(sql)
        
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        cursor.close()
        return results
    
    def close(self):
        """Close database connection."""
        self.conn.close()

# Usage
pipeline = ASQLPipeline("postgresql://user:pass@localhost/db")

results = pipeline.execute_query("""
from users
where status == 'active'
group by country ( # as total_users )
order by -total_users
limit 10
""")

for row in results:
    print(f"{row['country']}: {row['total_users']} users")

pipeline.close()
```

## Next Steps

- Check out the [Language Specification](spec.md) for complete syntax reference
- See [Examples](EXAMPLES.md) for more query patterns
- Review [Architecture](architecture.md) for implementation details

