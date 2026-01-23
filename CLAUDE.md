# ASQL - Claude Code Configuration

## Project Overview

ASQL (Analytic SQL) is a modern, pipeline-based query language that transpiles to SQL. It uses a FROM-first, pipeline-based syntax that makes complex analytics queries more readable and intuitive.

**Key Components:**
- `asql/preparse/` - Pre-parsing and normalization
- `asql/compiler/` - ASQL → SQL compilation pipeline
- `asql/dialect.py` - SQL dialect support (PostgreSQL, BigQuery, Snowflake, etc.)
- `asql/schema.py` - Schema handling and validation
- `asql/reverse_compiler.py` - SQL → ASQL reverse compilation

## Development Rules

**See `.cursorrules` for all development rules, code style guidelines, testing practices, and workflow conventions.**

The `.cursorrules` file contains:
- Critical virtual environment usage requirements
- Testing and TDD guidelines
- Code style rules
- Development workflow
- Important links and documentation references
- AI notes organization guidelines
- Issue/PR naming conventions

## Quick Reference

### Common Commands
```bash
just install        # Set up virtual environment and install dependencies
just test           # Run all tests
just test-v         # Run tests verbose
just test-file <f>  # Run specific test file
just serve          # Start docs + playground servers
just lint           # Run linter
just fmt            # Format code
just --list         # See all available commands
```

### Documentation & Playground
```bash
just serve
# Documentation: http://localhost:8000
# Playground: http://localhost:5001
```

## Visual Editor Architecture

The playground includes a Visual ASQL Editor for building queries visually. Key architectural principles:

### Backend-Driven UI (No Frontend Logic)
- **The UI is "dumb"** - it renders what the backend tells it, no business logic in the frontend
- **Metadata-driven**: Transform schemas, operators, functions all come from backend metadata
- **Schema-driven column dropdowns**: `output_columns` populated by SQLGlot's `qualify` tells the UI what columns are available at each pipeline stage
- **The frontend just renders** - if something looks wrong, fix the data/metadata, not the UI code

### Style Modes Are CSS-Only
- **Text mode vs Blocky mode**: Pure CSS differences (`.visual-style-text` vs `.visual-style-blocky`)
- Same DOM structure, same rendering logic, just different CSS styling
- **Exception: Pipes mode** - requires different DOM structure for node-based layout with connection lines

### Column Tracking Flow
1. Visual JSON → Backend `/api/visual/transpile`
2. Backend converts to ASQL, uses SQLGlot `qualify` with schema
3. Backend populates `output_columns` on each transform
4. Frontend renders column dropdowns from `output_columns`

### Key Files
- `playground/static/visual-editor-v2/visual-editor.js` - Main visual editor
- `playground/static/visual-editor-v2/visual-editor.css` - Styles for all modes
- `playground/app.py` - Backend API including `enrich_query_with_columns`
- `asql/column_tracking.py` - SQLGlot-based column qualification
- `asql/ui_schema.py` - Transform metadata/schemas for UI

## MCP Tools Available

- **gh** - GitHub CLI for PR workflows
- **Standard tools** - File read/write, grep, terminal, etc.

