# Static Assets for ASQL Documentation

This directory contains static assets (CSS, JavaScript) for the ASQL documentation server.

## Files

- `docs.css` - Styles for documentation pages, including dialect tabs
- `docs.js` - JavaScript for dialect tab functionality, localStorage tracking, and tab reordering

## Features

### Dialect Tabs
- Interactive tabs above each ASQL code example
- Pre-compiled SQL for all supported dialects
- Tab ordering based on user view counts
- localStorage persistence of user preferences

### Tab Ordering Logic
1. ASQL tab is always first
2. Top 4 dbt dialects (PostgreSQL, Snowflake, BigQuery, Redshift) are shown next
3. Tabs are ordered by view count (most viewed first)
4. Other dialects accessible via "⋯" (more) tab

### localStorage Keys
- `asql_dialects` - JSON object with dialect view counts: `{"postgres": 5, "snowflake": 3, ...}`
- `asql_preferred_dialect` - User's preferred dialect (used as default second tab)
