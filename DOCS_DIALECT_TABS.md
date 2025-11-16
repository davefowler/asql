# Documentation with Dialect Tabs - Implementation Summary

## Overview

The ASQL documentation now includes interactive dialect tabs above every ASQL code example, allowing users to see how queries translate to different SQL dialects.

## Features Implemented

### 1. Dialect Tabs
- **ASQL tab** (always first) - Shows the original ASQL query
- **Top 4 dbt dialects** - PostgreSQL, Snowflake, BigQuery, Redshift (shown as tabs)
- **⋯ (More) tab** - Dropdown menu for other dialects (MySQL, SQLite, Oracle, etc.)

### 2. Pre-compilation
- All ASQL queries are pre-compiled to all supported dialects when docs are served
- Compilation happens server-side for performance
- Errors are gracefully handled (shown as SQL comments)

### 3. User Preferences
- Dialect preferences saved in `localStorage`
- Preferred dialect becomes the default second tab (after ASQL)
- View counts tracked in `localStorage` for tab ordering

### 4. Tab Ordering
- Tabs ordered by view count (most viewed first)
- Order updates on page load based on usage statistics
- ASQL tab always remains first

## Files Created/Modified

### New Files
- `docs_server.py` - Flask server that processes markdown and serves docs with tabs
- `static/docs.css` - Styles for documentation and dialect tabs
- `static/docs.js` - JavaScript for tab functionality and localStorage tracking
- `start_servers.py` - Script to run both docs server and playground
- `Dockerfile` - Docker image for hosting docs + playground
- `docker-compose.yml` - Docker Compose configuration
- `DOCKER.md` - Docker deployment documentation
- `.dockerignore` - Docker ignore file

### Modified Files
- `pyproject.toml` - Added `docs` extra with markdown dependency

## How It Works

### Server-Side Processing
1. Markdown files are read from `docs/` directory
2. ASQL code blocks (```asql ... ```) are detected
3. Each ASQL query is compiled to all supported dialects
4. HTML with tabs is generated and embedded in the markdown
5. Markdown is converted to HTML and served

### Client-Side Behavior
1. On page load, tabs are reordered based on view counts from localStorage
2. User clicks a dialect tab → SQL is displayed
3. View count is incremented and saved to localStorage
4. Preferred dialect is saved for future visits

## Usage

### Local Development
```bash
# Install dependencies
pip install -e ".[docs,playground]"

# Start docs server
python docs_server.py
# Visit http://localhost:5000

# Start playground (in another terminal)
python playground.py
# Visit http://localhost:5001
```

### Docker Deployment
```bash
# Build and start
docker-compose up --build

# Access
# Documentation: http://localhost:5000
# Playground: http://localhost:5001
```

## Supported Dialects

### Top 4 (Always Shown as Tabs)
- PostgreSQL
- Snowflake
- BigQuery
- Redshift

### Other Dialects (Available via "⋯" tab)
- MySQL
- SQLite
- Oracle
- SQL Server (MSSQL)
- Presto
- Trino
- Spark
- Hive
- ClickHouse
- DuckDB
- Databricks

## Technical Details

### localStorage Structure
```javascript
// Dialect view counts
asql_dialects = {
  "postgres": 10,
  "snowflake": 5,
  "bigquery": 3,
  ...
}

// Preferred dialect
asql_preferred_dialect = "postgres"
```

### HTML Structure
Each ASQL code block is replaced with:
```html
<div class="asql-code-block" data-block-id="..." data-compiled="...">
  <div class="dialect-tabs">
    <button class="tab-btn active" data-dialect="asql">ASQL</button>
    <button class="tab-btn" data-dialect="postgres">PostgreSQL</button>
    ...
    <button class="tab-btn more-tab">⋯</button>
  </div>
  <div class="code-content">
    <pre><code class="language-sql">...</code></pre>
  </div>
</div>
```

### Compilation Data
Compiled SQL for all dialects is base64-encoded and embedded in the HTML as a data attribute. This allows the JavaScript to switch between dialects without additional server requests.

## Future Enhancements

- [ ] Server-side tracking of dialect usage (analytics)
- [ ] Copy-to-clipboard button for each dialect
- [ ] Syntax highlighting improvements
- [ ] Mobile-responsive tab layout improvements
- [ ] Export dialect preferences
