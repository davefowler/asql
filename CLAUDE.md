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

## MCP Tools Available

- **gh** - GitHub CLI for PR workflows
- **Standard tools** - File read/write, grep, terminal, etc.

