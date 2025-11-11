"""ASQL Interactive Playground - Web-based query editor and executor."""

import json
from flask import Flask, render_template_string, request, jsonify
from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError

app = Flask(__name__)

# HTML template for the playground
PLAYGROUND_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASQL Playground</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        h1 {
            text-align: center;
            margin-bottom: 30px;
            color: #2c3e50;
        }
        
        .playground {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        @media (max-width: 968px) {
            .playground {
                grid-template-columns: 1fr;
            }
        }
        
        .panel {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .panel-header {
            background: #3498db;
            color: white;
            padding: 12px 16px;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .panel-header.sql {
            background: #27ae60;
        }
        
        .panel-content {
            padding: 16px;
        }
        
        textarea {
            width: 100%;
            min-height: 300px;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 14px;
            line-height: 1.5;
            resize: vertical;
        }
        
        textarea:focus {
            outline: none;
            border-color: #3498db;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        select, button {
            padding: 10px 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            cursor: pointer;
            background: white;
        }
        
        button {
            background: #3498db;
            color: white;
            border: none;
            font-weight: 600;
        }
        
        button:hover {
            background: #2980b9;
        }
        
        button:disabled {
            background: #95a5a6;
            cursor: not-allowed;
        }
        
        .error {
            background: #e74c3c;
            color: white;
            padding: 12px;
            border-radius: 4px;
            margin-top: 10px;
        }
        
        .examples {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 20px;
        }
        
        .examples h2 {
            margin-bottom: 15px;
            color: #2c3e50;
        }
        
        .example-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 10px;
        }
        
        .example-btn {
            padding: 8px 12px;
            background: #ecf0f1;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            cursor: pointer;
            text-align: left;
            font-size: 13px;
            transition: all 0.2s;
        }
        
        .example-btn:hover {
            background: #d5dbdb;
            border-color: #95a5a6;
        }
        
        .example-title {
            font-weight: 600;
            margin-bottom: 4px;
            color: #2c3e50;
        }
        
        .example-desc {
            color: #7f8c8d;
            font-size: 12px;
        }
        
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .copy-btn {
            background: #95a5a6;
            padding: 6px 10px;
            font-size: 12px;
            margin-left: 10px;
        }
        
        .copy-btn:hover {
            background: #7f8c8d;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 ASQL Playground</h1>
        
        <div class="controls">
            <select id="dialect">
                <option value="">Default (ANSI SQL)</option>
                <option value="postgres">PostgreSQL</option>
                <option value="mysql">MySQL</option>
                <option value="bigquery">BigQuery</option>
                <option value="snowflake">Snowflake</option>
                <option value="redshift">Redshift</option>
            </select>
            <button onclick="compileQuery()">Compile to SQL</button>
            <button onclick="clearAll()">Clear</button>
        </div>
        
        <div class="playground">
            <div class="panel">
                <div class="panel-header">
                    <span>ASQL Query</span>
                    <button class="copy-btn" onclick="copyASQL()">Copy</button>
                </div>
                <div class="panel-content">
                    <textarea id="asql" placeholder="Enter your ASQL query here...">from users
where status == "active"
group by country ( # as total_users )
sort -total_users
take 10</textarea>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-header sql">
                    <span>Generated SQL</span>
                    <button class="copy-btn" onclick="copySQL()">Copy</button>
                </div>
                <div class="panel-content">
                    <textarea id="sql" readonly placeholder="SQL will appear here..."></textarea>
                    <div id="error" style="display: none;"></div>
                </div>
            </div>
        </div>
        
        <div class="examples">
            <h2>📚 Example Queries</h2>
            <div class="example-list" id="examples"></div>
        </div>
    </div>
    
    <script>
        const examples = [
            {
                title: "Simple FROM",
                desc: "Basic table selection",
                query: "from users"
            },
            {
                title: "WHERE Filter",
                desc: "Filter with conditions",
                query: 'from users where status == "active"'
            },
            {
                title: "GROUP BY",
                desc: "Aggregate with COUNT",
                query: "from users group by country ( # as total_users )"
            },
            {
                title: "Multiple Aggregations",
                desc: "SUM, COUNT, AVG together",
                query: "from sales group by region ( sum(amount) as revenue, # as orders, avg(amount) as avg_order )"
            },
            {
                title: "SORT Descending",
                desc: "Order by descending",
                query: "from users group by country ( # as total_users ) sort -total_users"
            },
            {
                title: "TAKE/LIMIT",
                desc: "Limit results",
                query: "from users take 10"
            },
            {
                title: "Complex Query",
                desc: "Full pipeline example",
                query: `from sales
where status == "completed" and amount > 100
group by region ( sum(amount) as revenue, # as orders )
sort -revenue
take 10`
            },
            {
                title: "Multiple Conditions",
                desc: "AND/OR operators",
                query: 'from users where status == "active" and age >= 18 and email is not null'
            },
            {
                title: "OR Conditions",
                desc: "Multiple OR conditions",
                query: 'from users where status == "active" or status == "pending"'
            },
            {
                title: "NULL Checks",
                desc: "IS NULL / IS NOT NULL",
                query: "from users where email is not null"
            },
            {
                title: "Comparisons",
                desc: "All comparison operators",
                query: "from users where age >= 18 and age <= 65"
            },
        ];
        
        // Render examples
        const examplesContainer = document.getElementById('examples');
        examples.forEach(example => {
            const btn = document.createElement('button');
            btn.className = 'example-btn';
            btn.innerHTML = `
                <div class="example-title">${example.title}</div>
                <div class="example-desc">${example.desc}</div>
            `;
            btn.onclick = () => {
                document.getElementById('asql').value = example.query;
                compileQuery();
            };
            examplesContainer.appendChild(btn);
        });
        
        async function compileQuery() {
            const asql = document.getElementById('asql').value;
            const dialect = document.getElementById('dialect').value;
            const sqlTextarea = document.getElementById('sql');
            const errorDiv = document.getElementById('error');
            
            // Clear previous results
            sqlTextarea.value = '';
            errorDiv.style.display = 'none';
            errorDiv.className = '';
            
            if (!asql.trim()) {
                return;
            }
            
            try {
                const response = await fetch('/api/compile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ asql, dialect })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    errorDiv.textContent = data.error;
                    errorDiv.className = 'error';
                    errorDiv.style.display = 'block';
                } else {
                    sqlTextarea.value = data.sql;
                }
            } catch (error) {
                errorDiv.textContent = 'Error: ' + error.message;
                errorDiv.className = 'error';
                errorDiv.style.display = 'block';
            }
        }
        
        function clearAll() {
            document.getElementById('asql').value = '';
            document.getElementById('sql').value = '';
            document.getElementById('error').style.display = 'none';
        }
        
        function copyASQL() {
            const textarea = document.getElementById('asql');
            textarea.select();
            document.execCommand('copy');
        }
        
        function copySQL() {
            const textarea = document.getElementById('sql');
            textarea.select();
            document.execCommand('copy');
        }
        
        // Auto-compile on change (debounced)
        let compileTimeout;
        document.getElementById('asql').addEventListener('input', () => {
            clearTimeout(compileTimeout);
            compileTimeout = setTimeout(compileQuery, 500);
        });
        
        // Initial compile
        compileQuery();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Render the playground interface."""
    return render_template_string(PLAYGROUND_HTML)

@app.route('/api/compile', methods=['POST'])
def api_compile():
    """API endpoint to compile ASQL to SQL."""
    try:
        data = request.get_json()
        asql_query = data.get('asql', '')
        dialect = data.get('dialect', '')
        
        if not asql_query.strip():
            return jsonify({'error': 'Empty ASQL query'})
        
        sql = compile(asql_query, dialect=dialect if dialect else None)
        return jsonify({'sql': sql})
        
    except ASQLSyntaxError as e:
        return jsonify({'error': f'Syntax Error: {str(e)}'})
    except ASQLCompilationError as e:
        return jsonify({'error': f'Compilation Error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'})

if __name__ == '__main__':
    print("Starting ASQL Playground...")
    print("Open http://localhost:5001 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5001)
