"""ASQL Interactive Playground - Web-based query editor and executor with bidirectional translation."""

import json
from flask import Flask, render_template_string, request, jsonify
from asql import compile
from asql.errors import ASQLSyntaxError, ASQLCompilationError
from asql.reverse_compiler import reverse_compile, detect_dialect

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
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
        }
        
        h1 {
            text-align: center;
            margin-bottom: 30px;
            color: #2c3e50;
        }
        
        .mode-toggle {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .toggle-btn {
            padding: 12px 24px;
            border: 2px solid #3498db;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            background: white;
            color: #3498db;
            transition: all 0.3s;
        }
        
        .toggle-btn.active {
            background: #3498db;
            color: white;
        }
        
        .toggle-btn:hover {
            background: #2980b9;
            color: white;
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
        
        .panel-header.asql {
            background: #9b59b6;
        }
        
        .dialect-selector {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
            padding: 0 16px;
            padding-top: 12px;
        }
        
        .dialect-selector label {
            font-size: 12px;
            font-weight: 600;
            color: #7f8c8d;
            text-transform: uppercase;
        }
        
        .dialect-selector select {
            flex: 1;
            padding: 6px 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 13px;
            background: white;
        }
        
        .panel-content {
            padding: 16px;
            padding-top: 0;
        }
        
        textarea {
            width: 100%;
            min-height: 350px;
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
            justify-content: center;
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
            margin-top: 20px;
        }
        
        .examples h2 {
            margin-bottom: 15px;
            color: #2c3e50;
        }
        
        .example-section {
            margin-bottom: 25px;
        }
        
        .example-section h3 {
            margin-bottom: 10px;
            color: #34495e;
            font-size: 16px;
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
            background: rgba(255,255,255,0.2);
            padding: 6px 10px;
            font-size: 12px;
            margin-left: 10px;
            border: 1px solid rgba(255,255,255,0.3);
        }
        
        .copy-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        
        .detected-dialect {
            font-size: 11px;
            color: #95a5a6;
            font-style: italic;
            margin-left: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 ASQL Playground</h1>
        
        <div class="mode-toggle">
            <button class="toggle-btn active" id="mode-asql-to-sql" onclick="setMode('asql-to-sql')">
                ASQL → SQL
            </button>
            <button class="toggle-btn" id="mode-sql-to-asql" onclick="setMode('sql-to-asql')">
                SQL → ASQL
            </button>
        </div>
        
        <div class="controls">
            <button onclick="translateQuery()">Translate</button>
            <button onclick="clearAll()">Clear</button>
        </div>
        
        <div class="playground">
            <div class="panel" id="input-panel">
                <div class="panel-header" id="input-header">
                    <span id="input-title">ASQL Query</span>
                    <button class="copy-btn" onclick="copyInput()">Copy</button>
                </div>
                <div class="dialect-selector" id="input-dialect-selector" style="display: none;">
                    <label>From:</label>
                    <select id="input-dialect">
                        <option value="">Auto-detect</option>
                        <option value="bigquery">BigQuery</option>
                        <option value="redshift">Redshift</option>
                        <option value="postgres">PostgreSQL</option>
                        <option value="mysql">MySQL</option>
                        <option value="snowflake">Snowflake</option>
                        <option value="spark">Spark</option>
                    </select>
                    <span class="detected-dialect" id="detected-dialect" style="display: none;"></span>
                </div>
                <div class="panel-content">
                    <textarea id="input" placeholder="Enter your query here...">from users
where status == "active"
group by country ( # as total_users )
sort -total_users
take 10</textarea>
                </div>
            </div>
            
            <div class="panel" id="output-panel">
                <div class="panel-header" id="output-header">
                    <span id="output-title">Generated SQL</span>
                    <button class="copy-btn" onclick="copyOutput()">Copy</button>
                </div>
                <div class="dialect-selector" id="output-dialect-selector">
                    <label>To:</label>
                    <select id="output-dialect">
                        <option value="">Default (ANSI SQL)</option>
                        <option value="postgres">PostgreSQL</option>
                        <option value="mysql">MySQL</option>
                        <option value="bigquery">BigQuery</option>
                        <option value="snowflake">Snowflake</option>
                        <option value="redshift">Redshift</option>
                        <option value="spark">Spark</option>
                    </select>
                </div>
                <div class="panel-content">
                    <textarea id="output" readonly placeholder="Translation will appear here..."></textarea>
                    <div id="error" style="display: none;"></div>
                </div>
            </div>
        </div>
        
        <div class="examples">
            <h2>📚 Example Queries</h2>
            <div id="examples-container"></div>
        </div>
    </div>
    
    <script>
        let currentMode = 'asql-to-sql';
        
        const asqlExamples = [
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
            {
                title: "Fivetran: Shopify Line Items",
                desc: "Complex joins from dbt_shopify",
                query: `from stg_shopify_gql__order_line
join stg_shopify_gql__order on order_line.order_id == order.order_id
select order_line.order_id, order.created_timestamp as created_at, order_line.quantity`
            },
            {
                title: "Fivetran: Stripe Customer Overview",
                desc: "Complex aggregations from dbt_stripe",
                query: `from stripe__balance_transactions
where balance_transaction_type in ("payment", "charge")
group by customer_id ( sum(balance_transaction_amount) as total_sales )`
            },
            {
                title: "Fivetran: Zendesk Ticket Enriched",
                desc: "Multiple user joins from dbt_zendesk",
                query: `from int_zendesk__ticket_aggregates
join int_zendesk__user_aggregates as requester on ticket.requester_id == requester.user_id
join int_zendesk__user_aggregates as submitter on ticket.submitter_id == submitter.user_id
select ticket.*, requester.email as requester_email, submitter.email as submitter_email`
            },
            {
                title: "Fivetran: Stripe Balance Transactions",
                desc: "Complex dispute logic from dbt_stripe",
                query: `from stg_stripe__balance_transaction
left join stg_stripe__charge on charge.balance_transaction_id == balance_transaction.balance_transaction_id
select balance_transaction.balance_transaction_id, balance_transaction.amount, charge.charge_id`
            },
            {
                title: "Fivetran: Shopify Customer Cohorts",
                desc: "Cohort analysis from dbt_shopify",
                query: `from orders
group by customer_id, date_trunc("month", created_timestamp) (
    count(distinct order_id) as order_count_in_month,
    sum(order_adjusted_total) as total_price_in_month
)`
            },
        ];
        
        const sqlExamples = [];
        
        function setMode(mode) {
            currentMode = mode;
            
            // Update toggle buttons
            document.getElementById('mode-asql-to-sql').classList.toggle('active', mode === 'asql-to-sql');
            document.getElementById('mode-sql-to-asql').classList.toggle('active', mode === 'sql-to-asql');
            
            // Update UI
            if (mode === 'asql-to-sql') {
                document.getElementById('input-title').textContent = 'ASQL Query';
                document.getElementById('output-title').textContent = 'Generated SQL';
                document.getElementById('input-header').className = 'panel-header';
                document.getElementById('output-header').className = 'panel-header sql';
                document.getElementById('input-dialect-selector').style.display = 'none';
                document.getElementById('output-dialect-selector').style.display = 'flex';
                document.getElementById('input').placeholder = 'Enter your ASQL query here...';
                document.getElementById('output').placeholder = 'SQL will appear here...';
            } else {
                document.getElementById('input-title').textContent = 'SQL Query';
                document.getElementById('output-title').textContent = 'Generated ASQL';
                document.getElementById('input-header').className = 'panel-header sql';
                document.getElementById('output-header').className = 'panel-header asql';
                document.getElementById('input-dialect-selector').style.display = 'flex';
                document.getElementById('output-dialect-selector').style.display = 'none';
                document.getElementById('input').placeholder = 'Enter your SQL query here...';
                document.getElementById('output').placeholder = 'ASQL will appear here...';
            }
            
            // Clear output
            document.getElementById('output').value = '';
            document.getElementById('error').style.display = 'none';
            document.getElementById('detected-dialect').style.display = 'none';
            
            // Reload examples
            loadExamples();
        }
        
        function loadExamples() {
            const container = document.getElementById('examples-container');
            container.innerHTML = '';
            
            if (currentMode === 'asql-to-sql') {
                const section = document.createElement('div');
                section.className = 'example-section';
                section.innerHTML = '<h3>ASQL Examples</h3><div class="example-list" id="asql-examples"></div>';
                container.appendChild(section);
                
                const examplesDiv = document.getElementById('asql-examples');
                asqlExamples.forEach(example => {
                    const btn = document.createElement('button');
                    btn.className = 'example-btn';
                    btn.innerHTML = `
                        <div class="example-title">${example.title}</div>
                        <div class="example-desc">${example.desc}</div>
                    `;
                    btn.onclick = () => {
                        document.getElementById('input').value = example.query;
                        translateQuery();
                    };
                    examplesDiv.appendChild(btn);
                });
            } else {
                const section = document.createElement('div');
                section.className = 'example-section';
                section.innerHTML = '<h3>SQL Translation Examples</h3><div class="example-list" id="sql-examples"></div>';
                container.appendChild(section);
                
                const examplesDiv = document.getElementById('sql-examples');
                if (sqlExamples.length === 0) {
                    examplesDiv.innerHTML = '<p style="color: #7f8c8d; padding: 20px;">SQL examples will be loaded from the server...</p>';
                    loadSQLExamples();
                } else {
                    sqlExamples.forEach(example => {
                        const btn = document.createElement('button');
                        btn.className = 'example-btn';
                        btn.innerHTML = `
                            <div class="example-title">${example.title}</div>
                            <div class="example-desc">${example.desc}</div>
                        `;
                        btn.onclick = () => {
                            document.getElementById('input').value = example.query;
                            document.getElementById('input-dialect').value = example.dialect || '';
                            translateQuery();
                        };
                        examplesDiv.appendChild(btn);
                    });
                }
            }
        }
        
        async function loadSQLExamples() {
            try {
                const response = await fetch('/api/sql-examples');
                const examples = await response.json();
                sqlExamples.push(...examples);
                loadExamples();
            } catch (error) {
                console.error('Failed to load SQL examples:', error);
            }
        }
        
        async function translateQuery() {
            const input = document.getElementById('input').value;
            const outputTextarea = document.getElementById('output');
            const errorDiv = document.getElementById('error');
            const detectedDialectSpan = document.getElementById('detected-dialect');
            
            // Clear previous results
            outputTextarea.value = '';
            errorDiv.style.display = 'none';
            errorDiv.className = '';
            detectedDialectSpan.style.display = 'none';
            
            if (!input.trim()) {
                return;
            }
            
            try {
                if (currentMode === 'asql-to-sql') {
                    // ASQL to SQL
                    const outputDialect = document.getElementById('output-dialect').value;
                    const response = await fetch('/api/compile', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ asql: input, dialect: outputDialect })
                    });
                    
                    const data = await response.json();
                    
                    if (data.error) {
                        errorDiv.textContent = data.error;
                        errorDiv.className = 'error';
                        errorDiv.style.display = 'block';
                    } else {
                        outputTextarea.value = data.sql;
                    }
                } else {
                    // SQL to ASQL
                    const inputDialect = document.getElementById('input-dialect').value;
                    
                    // First, try to detect dialect if not specified
                    let detectedDialect = null;
                    if (!inputDialect) {
                        const detectResponse = await fetch('/api/detect-dialect', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ sql: input })
                        });
                        const detectData = await detectResponse.json();
                        if (detectData.dialect) {
                            detectedDialect = detectData.dialect;
                            detectedDialectSpan.textContent = `Detected: ${detectedDialect}`;
                            detectedDialectSpan.style.display = 'inline';
                        }
                    }
                    
                    const response = await fetch('/api/reverse-compile', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ 
                            sql: input, 
                            source_dialect: inputDialect || detectedDialect 
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.error) {
                        errorDiv.textContent = data.error;
                        errorDiv.className = 'error';
                        errorDiv.style.display = 'block';
                    } else {
                        outputTextarea.value = data.asql;
                    }
                }
            } catch (error) {
                errorDiv.textContent = 'Error: ' + error.message;
                errorDiv.className = 'error';
                errorDiv.style.display = 'block';
            }
        }
        
        function clearAll() {
            document.getElementById('input').value = '';
            document.getElementById('output').value = '';
            document.getElementById('error').style.display = 'none';
            document.getElementById('detected-dialect').style.display = 'none';
        }
        
        function copyInput() {
            const textarea = document.getElementById('input');
            textarea.select();
            document.execCommand('copy');
        }
        
        function copyOutput() {
            const textarea = document.getElementById('output');
            textarea.select();
            document.execCommand('copy');
        }
        
        // Auto-translate on change (debounced)
        let translateTimeout;
        document.getElementById('input').addEventListener('input', () => {
            clearTimeout(translateTimeout);
            translateTimeout = setTimeout(translateQuery, 500);
        });
        
        // Auto-detect dialect when SQL is pasted (for SQL→ASQL mode)
        document.getElementById('input').addEventListener('paste', () => {
            setTimeout(() => {
                if (currentMode === 'sql-to-asql' && !document.getElementById('input-dialect').value) {
                    translateQuery();
                }
            }, 100);
        });
        
        // Initial load
        loadExamples();
        translateQuery();
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

@app.route('/api/reverse-compile', methods=['POST'])
def api_reverse_compile():
    """API endpoint to compile SQL to ASQL."""
    try:
        data = request.get_json()
        sql_query = data.get('sql', '')
        source_dialect = data.get('source_dialect', '')
        
        if not sql_query.strip():
            return jsonify({'error': 'Empty SQL query'})
        
        asql = reverse_compile(sql_query, source_dialect=source_dialect if source_dialect else None)
        return jsonify({'asql': asql})
        
    except ASQLCompilationError as e:
        return jsonify({'error': f'Compilation Error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'})

@app.route('/api/detect-dialect', methods=['POST'])
def api_detect_dialect():
    """API endpoint to detect SQL dialect."""
    try:
        data = request.get_json()
        sql_query = data.get('sql', '')
        
        if not sql_query.strip():
            return jsonify({'dialect': None})
        
        dialect = detect_dialect(sql_query)
        return jsonify({'dialect': dialect})
        
    except Exception as e:
        return jsonify({'dialect': None, 'error': str(e)})

@app.route('/api/sql-examples', methods=['GET'])
def api_sql_examples():
    """API endpoint to get SQL translation examples."""
    examples = [
        {
            "title": "BigQuery CTE with Joins",
            "desc": "Complex query with CTEs and aggregations",
            "dialect": "bigquery",
            "query": """WITH active_users AS (
  SELECT user_id, country, signup_date
  FROM users
  WHERE status = 'active' AND signup_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),
user_orders AS (
  SELECT au.user_id, au.country,
    COUNT(o.order_id) AS order_count,
    SUM(o.amount) AS total_spent
  FROM active_users au
  LEFT JOIN orders o ON au.user_id = o.user_id
  GROUP BY au.user_id, au.country
)
SELECT country,
  COUNT(*) AS user_count,
  AVG(order_count) AS avg_orders,
  SUM(total_spent) AS total_revenue
FROM user_orders
GROUP BY country
ORDER BY total_revenue DESC
LIMIT 10"""
        },
        {
            "title": "Redshift Window Functions",
            "desc": "Running totals with window functions",
            "dialect": "redshift",
            "query": """SELECT product_id, category, sale_date, amount,
  SUM(amount) OVER (
    PARTITION BY category 
    ORDER BY sale_date 
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_total
FROM sales
WHERE sale_date >= '2024-01-01'
ORDER BY category, sale_date"""
        },
        {
            "title": "PostgreSQL Complex Join",
            "desc": "Multiple joins with HAVING clause",
            "dialect": "postgres",
            "query": """SELECT u.user_id, u.email,
  COUNT(DISTINCT o.order_id) AS order_count,
  SUM(o.amount) AS total_spent,
  AVG(o.amount) AS avg_order_value
FROM users u
INNER JOIN orders o ON u.user_id = o.user_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
WHERE u.created_at >= '2024-01-01' AND o.status = 'completed'
GROUP BY u.user_id, u.email
HAVING COUNT(DISTINCT o.order_id) > 5
ORDER BY total_spent DESC
LIMIT 20"""
        },
        {
            "title": "BigQuery Nested CTEs",
            "desc": "Multiple CTEs with window functions",
            "dialect": "bigquery",
            "query": """WITH monthly_sales AS (
  SELECT DATE_TRUNC(order_date, MONTH) AS month, region,
    SUM(amount) AS revenue, COUNT(*) AS order_count
  FROM orders
  WHERE order_date >= '2023-01-01'
  GROUP BY month, region
),
region_rankings AS (
  SELECT month, region, revenue, order_count,
    RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS revenue_rank
  FROM monthly_sales
)
SELECT month, region, revenue, order_count
FROM region_rankings
WHERE revenue_rank <= 3
ORDER BY month DESC, revenue DESC"""
        },
        {
            "title": "Redshift Date Aggregation",
            "desc": "Weekly aggregations with HAVING",
            "dialect": "redshift",
            "query": """SELECT DATE_TRUNC('week', event_timestamp) AS week, event_type,
  COUNT(*) AS event_count,
  COUNT(DISTINCT user_id) AS unique_users
FROM events
WHERE event_timestamp >= '2024-01-01'
  AND event_type IN ('click', 'view', 'purchase')
GROUP BY week, event_type
HAVING COUNT(*) > 100
ORDER BY week DESC, event_count DESC"""
        },
        {
            "title": "BigQuery Multiple CTEs",
            "desc": "Complex multi-CTE query",
            "dialect": "bigquery",
            "query": """WITH customers AS (
  SELECT DISTINCT user_id, country, signup_date
  FROM users WHERE status = 'active'
),
orders_summary AS (
  SELECT user_id, COUNT(*) AS order_count, SUM(amount) AS total_amount
  FROM orders WHERE status = 'completed'
  GROUP BY user_id
),
customer_metrics AS (
  SELECT c.user_id, c.country,
    COALESCE(o.order_count, 0) AS order_count,
    COALESCE(o.total_amount, 0) AS total_amount
  FROM customers c
  LEFT JOIN orders_summary o ON c.user_id = o.user_id
)
SELECT country, COUNT(*) AS customer_count,
  AVG(order_count) AS avg_orders,
  SUM(total_amount) AS total_revenue
FROM customer_metrics
GROUP BY country
ORDER BY total_revenue DESC"""
        },
        {
            "title": "PostgreSQL Subquery",
            "desc": "Correlated subquery example",
            "dialect": "postgres",
            "query": """SELECT p.product_id, p.name, p.price,
  (SELECT AVG(price) FROM products WHERE category = p.category) AS avg_category_price
FROM products p
WHERE p.price > (SELECT AVG(price) FROM products WHERE category = p.category)
ORDER BY p.price DESC"""
        },
        {
            "title": "BigQuery Time Series",
            "desc": "Time series analysis with CTEs",
            "dialect": "bigquery",
            "query": """WITH daily_metrics AS (
  SELECT DATE(timestamp) AS date, event_type,
    COUNT(*) AS event_count,
    COUNT(DISTINCT user_id) AS unique_users
  FROM events
  WHERE timestamp >= TIMESTAMP('2024-01-01')
    AND timestamp < TIMESTAMP('2024-02-01')
  GROUP BY date, event_type
),
daily_totals AS (
  SELECT date, SUM(event_count) AS total_events, SUM(unique_users) AS total_users
  FROM daily_metrics
  GROUP BY date
)
SELECT dt.date, dt.total_events, dt.total_users, dm.event_type, dm.event_count
FROM daily_totals dt
LEFT JOIN daily_metrics dm ON dt.date = dm.date
ORDER BY dt.date DESC, dm.event_count DESC"""
        },
        {
            "title": "Redshift CASE Statement",
            "desc": "CASE with aggregations",
            "dialect": "redshift",
            "query": """SELECT user_id, amount,
  CASE 
    WHEN amount < 50 THEN 'low'
    WHEN amount < 200 THEN 'medium'
    ELSE 'high'
  END AS order_tier,
  COUNT(*) AS order_count
FROM orders
WHERE order_date >= '2024-01-01'
GROUP BY user_id, amount, order_tier
ORDER BY amount DESC
LIMIT 50"""
        },
        {
            "title": "BigQuery Array Operations",
            "desc": "Array aggregations",
            "dialect": "bigquery",
            "query": """SELECT category, COUNT(*) AS product_count,
  ARRAY_AGG(DISTINCT brand IGNORE NULLS) AS brands,
  AVG(price) AS avg_price
FROM products
WHERE in_stock = TRUE
GROUP BY category
ORDER BY product_count DESC"""
        },
        {
            "title": "PostgreSQL JSON Operations",
            "desc": "JSON field extraction",
            "dialect": "postgres",
            "query": """SELECT user_id, metadata->>'source' AS source, COUNT(*) AS event_count
FROM events
WHERE metadata ? 'source' AND event_timestamp >= '2024-01-01'
GROUP BY user_id, metadata->>'source'
ORDER BY event_count DESC
LIMIT 100"""
        },
        {
            "title": "Simple SELECT with WHERE",
            "desc": "Basic filtering example",
            "dialect": "",
            "query": """SELECT user_id, email, status
FROM users
WHERE status = 'active' AND created_at >= '2024-01-01'
ORDER BY created_at DESC
LIMIT 100"""
        }
    ]
    return jsonify(examples)

if __name__ == '__main__':
    print("Starting ASQL Playground...")
    print("Open http://localhost:5001 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5001)
