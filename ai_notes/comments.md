# SQL Comments: Storage, Extraction, and Integration

**Last Updated**: December 2025

> **See also**: [dialect.md](dialect.md) - How comments fit into the SQLGlot dialect approach (Section 7)

## Overview

This document explores how ASQL handles comments—extracting them as structured metadata that consuming tools can use for documentation, data catalogs, and AI integration.

### Key Insight: ASQL is a Library

ASQL is a **transpiler/library**, not an execution engine. It:
- Parses ASQL syntax into an AST
- Compiles to SQL for various dialects
- **Extracts comments as structured metadata via API**

ASQL does NOT:
- Execute queries or create tables
- Directly write to databases or YAML files
- Run as a standalone CLI tool (beyond basic transpilation)

**Consuming tools** (dbt, SQLMesh, BI platforms, AI assistants) are responsible for:
- Deciding what to do with extracted metadata
- Persisting comments to databases (`COMMENT ON` statements)
- Generating documentation files (`schema.yml`)
- Displaying comments in UIs

This separation of concerns means comments stay in code (single source of truth), and each tool uses ASQL's API to access them as needed.

## Current Landscape

### How dbt Handles Comments

dbt separates inline SQL comments from structured documentation:

1. **Inline SQL Comments** - Standard `--` and `/* */` comments in `.sql` files
   - These are NOT automatically extracted or stored
   - They exist only in source files

2. **YAML Documentation** - Structured metadata in `schema.yml`:
   ```yaml
   models:
     - name: monthly_signups
       description: "Track user signups by month"
       columns:
         - name: signup_month
           description: "The month the user signed up"
         - name: user_count
           description: "Number of users signed up"
   ```

3. **`persist_docs` Configuration** - Pushes YAML descriptions to database:
   ```yaml
   models:
     my_project:
       +persist_docs:
         relation: true    # Table/view comments
         columns: true     # Column comments
   ```

**The Problem**: Comments in SQL are divorced from documentation in YAML. Developers write comments inline but must duplicate them in YAML for persistence. This friction leads to:
- Outdated YAML descriptions
- Missing documentation
- Duplicate maintenance burden

### How SQLMesh Handles Comments

SQLMesh improves on dbt by:

1. **Automatic Comment Registration** - Model and column descriptions are registered to the database by default
2. **Native SQL Understanding** - SQLMesh parses SQL semantically, enabling column-level lineage
3. **Python Model Decorators** - Metadata can be defined programmatically:
   ```python
   @model(
       "monthly_signups",
       columns={
           "signup_month": "The month the user signed up",
           "user_count": "Number of users signed up"
       }
   )
   def monthly_signups(context):
       ...
   ```

**Still Missing**: Inline SQL comment extraction. SQLMesh still relies on explicit metadata definition rather than extracting from code comments.

### Database Native Comments

All major databases support schema comments:

```sql
-- PostgreSQL
COMMENT ON TABLE users IS 'User account information';
COMMENT ON COLUMN users.created_at IS 'Timestamp when user registered';

-- Snowflake
ALTER TABLE users SET COMMENT = 'User account information';
ALTER TABLE users ALTER COLUMN created_at SET COMMENT 'Timestamp when user registered';

-- BigQuery (via schema definition)
CREATE TABLE users (
  created_at TIMESTAMP OPTIONS(description='Timestamp when user registered')
) OPTIONS(description='User account information');
```

These comments are stored in `INFORMATION_SCHEMA` and queryable, making them excellent for data catalogs and AI consumption.

## SQLGlot's Comment Capabilities

SQLGlot (which ASQL uses) **preserves comments** on AST nodes:

```python
import sqlglot

sql = '''
/* Table: monthly_signups
   Purpose: Track user signups by month */
SELECT 
    DATE_TRUNC('month', created_at) AS signup_month, -- the month user signed up
    COUNT(*) AS user_count /* number of users */
FROM users
'''

parsed = sqlglot.parse_one(sql)

# Comments are attached to the Select node
print(parsed.comments)
# [' Table: monthly_signups\n   Purpose: Track user signups by month ']

# Walk the AST to find all comments
for expr in parsed.walk():
    if hasattr(expr, 'comments') and expr.comments:
        print(f'{type(expr).__name__}: {expr.comments}')
        
# Output:
# Select: [' Table: monthly_signups...']
# Alias: [' the month user signed up']
# Alias: [' number of users ']
```

**Key Insight**: SQLGlot associates comments with the nearest AST node, making it possible to extract column-level documentation automatically!

## Proposed ASQL Comment System

### Comment Format Specification

ASQL should support three levels of comments:

#### 1. Table/Query-Level Documentation Block

```asql
/*
 * @table monthly_signups  
 * @description Track user signups by month for retention analysis
 * @author data-team
 * @tags analytics, users, retention
 * @depends users, subscriptions
 */
from users
...
```

Or simpler natural format:
```asql
/* Monthly signups for retention analysis
   Groups users by the month they signed up.
   Used by: retention dashboard, executive reports
*/
from users
...
```

#### 2. Inline Column Comments

```asql
from users
order by created_at -- want older users first
where created_at > (now() - 3 months) -- just the past 3 months
group by 
  month(created_at), -- the signup month
  user_id,           -- deduplicated user identifier  
  age                -- age at signup
  (
   # as user_count   -- count of users per group
  )
```

#### 3. Select/Project Column Comments

```asql
from users
select
  user_id,                    -- primary key
  email,                      -- user contact email
  created_at as signup_date,  -- when they joined
  age                         -- current age
```

### Comment Extraction Algorithm

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import re

@dataclass
class ColumnMetadata:
    name: str
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
@dataclass
class QueryMetadata:
    table_name: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    columns: Dict[str, ColumnMetadata] = field(default_factory=dict)
    general_notes: List[str] = field(default_factory=list)

def extract_metadata(asql_query: str) -> QueryMetadata:
    """Extract metadata from ASQL comments."""
    import sqlglot
    from sqlglot import exp
    
    # First, compile ASQL to SQL to get proper AST
    # (In practice, this would use the ASQL parser)
    parsed = sqlglot.parse_one(asql_query)
    
    metadata = QueryMetadata()
    
    # Extract table-level comments from the Select node
    if parsed.comments:
        table_comment = ' '.join(parsed.comments)
        metadata.description = _parse_table_comment(table_comment)
        metadata.tags = _extract_tags(table_comment)
        metadata.author = _extract_author(table_comment)
    
    # Walk AST to find column-level comments
    for expr in parsed.walk():
        if not (hasattr(expr, 'comments') and expr.comments):
            continue
            
        comment_text = ' '.join(expr.comments).strip()
        
        # Try to get column name from expression
        col_name = _get_column_name(expr)
        
        if col_name:
            # Matched to a column
            metadata.columns[col_name] = ColumnMetadata(
                name=col_name,
                description=comment_text,
                tags=_extract_inline_tags(comment_text)
            )
        else:
            # Unmatched comment - add to general notes
            metadata.general_notes.append(comment_text)
    
    return metadata

def _get_column_name(expr) -> Optional[str]:
    """Extract column name from an expression."""
    from sqlglot import exp
    
    if isinstance(expr, exp.Alias):
        return expr.alias
    elif isinstance(expr, exp.Column):
        return expr.name
    elif isinstance(expr, exp.Ordered):
        # ORDER BY expression
        if isinstance(expr.this, exp.Column):
            return expr.this.name
    return None

def _parse_table_comment(comment: str) -> str:
    """Parse structured or natural table comment."""
    # Check for @description tag
    match = re.search(r'@description\s+(.+?)(?=@|$)', comment, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Otherwise, use the whole comment (cleaned up)
    lines = [l.strip().lstrip('*').strip() for l in comment.split('\n')]
    lines = [l for l in lines if l and not l.startswith('@')]
    return ' '.join(lines)

def _extract_tags(comment: str) -> List[str]:
    """Extract @tags from comment."""
    match = re.search(r'@tags?\s+(.+?)(?=@|$)', comment, re.IGNORECASE)
    if match:
        return [t.strip() for t in match.group(1).split(',')]
    return []

def _extract_author(comment: str) -> Optional[str]:
    """Extract @author from comment."""
    match = re.search(r'@author\s+(\S+)', comment, re.IGNORECASE)
    return match.group(1) if match else None

def _extract_inline_tags(comment: str) -> List[str]:
    """Extract any #hashtags from inline comments."""
    return re.findall(r'#(\w+)', comment)
```

### Metadata Serialization Methods

The `QueryMetadata` object provides convenience methods for common formats:

```python
# After extracting metadata
metadata = asql.extract_metadata(ast)

# Convert to dbt schema.yml format (dict ready for yaml.dump)
dbt_schema = metadata.to_dbt_schema()
# Returns: {'name': 'monthly_signups', 'description': '...', 'columns': [...]}

# Generate SQL COMMENT ON statements
sql_comments = metadata.to_sql_comments(table_name="analytics.monthly_signups")
# Returns:
# COMMENT ON TABLE analytics.monthly_signups IS 'User signups...';
# COMMENT ON COLUMN analytics.monthly_signups.user_count IS 'Count of users...';

# Export as JSON for APIs or AI consumption
json_data = metadata.to_json()
# Returns: '{"name": "monthly_signups", "description": "...", ...}'

# Raw dict access for custom integrations
raw_dict = metadata.to_dict()
```

Example implementation:

```python
@dataclass
class QueryMetadata:
    name: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    owner: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    columns: Dict[str, ColumnMetadata] = field(default_factory=dict)
    general_notes: List[str] = field(default_factory=list)
    
    def to_dbt_schema(self) -> dict:
        """Convert to dbt schema.yml format."""
        return {
            'name': self.name or 'query',
            'description': self.description or '',
            'meta': {
                k: v for k, v in [
                    ('author', self.author),
                    ('owner', self.owner),
                    ('tags', self.tags if self.tags else None),
                ] if v
            },
            'columns': [
                {'name': col.name, 'description': col.description or ''}
                for col in self.columns.values()
            ]
        }
    
    def to_sql_comments(self, table_name: str, dialect: str = "postgres") -> str:
        """Generate SQL COMMENT ON statements."""
        statements = []
        
        if self.description:
            statements.append(
                f"COMMENT ON TABLE {table_name} IS '{self.description}';"
            )
        
        for col in self.columns.values():
            if col.description:
                statements.append(
                    f"COMMENT ON COLUMN {table_name}.{col.name} IS '{col.description}';"
                )
        
        return '\n'.join(statements)
    
    def to_json(self) -> str:
        """Export as JSON for API consumption."""
        import json
        return json.dumps(self.to_dict(), indent=2)
    
    def to_dict(self) -> dict:
        """Convert to plain dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'author': self.author,
            'owner': self.owner,
            'tags': self.tags,
            'columns': {
                name: {'description': col.description, 'tags': col.tags}
                for name, col in self.columns.items()
            }
        }
```

## Recommended Comment Format

ASQL supports both natural language comments and structured metadata tags. Natural comments work great for most cases, but when `@` tags are present, ASQL extracts them as structured metadata.

### Recommended Format (Structured with Natural Fallback)

```asql
/**
 * @name monthly_signups
 * @description User signups grouped by month for retention analysis
 * @author analytics-team
 * @owner finance
 * @tags retention, users, monthly
 * @freshness daily
 * @pii false
 */
from users
where created_at > (now() - 3 months)  -- recent users only
group by 
  month created_at as signup_month,    -- the monthly cohort
  age                                  -- user age at signup
  (
    # as user_count                    -- count of users in cohort
  )
```

### Natural Comments (Also Fully Supported)

When no `@` tags are present, the entire comment block becomes the description:

```asql
/* User signups by month
   Groups users by signup month for retention analysis.
   Filters to last 3 months to focus on recent cohorts.
*/
from users
order by created_at        -- start with oldest users
where created_at > (now() - 3 months)  -- recent users only
group by 
  month created_at,        -- signup cohort month
  age                      -- age at signup time
  (
    # as user_count        -- users in this cohort
  )
select
  signup_month,            -- the cohort month
  age,                     -- user age bucket
  user_count               -- count of users
```

### Inline Tag Vocabulary

Suggested inline tags for structured extraction:

| Tag | Purpose | Example |
|-----|---------|---------|
| `@desc` | Column description | `-- @desc: Primary user identifier` |
| `@filter` | Explain filter logic | `-- @filter: Only active users` |
| `@grain` | Describe grouping grain | `-- @grain: Monthly cohort` |
| `@metric` | Mark as metric column | `-- @metric: Revenue total` |
| `@dimension` | Mark as dimension | `-- @dimension: User segment` |
| `@pii` | Mark PII columns | `-- @pii: Contains email` |
| `@deprecated` | Mark deprecated | `-- @deprecated: Use new_col instead` |

## ASQL as a Library: How Consuming Tools Access Comments

ASQL is a **transpiler/library**, not an execution engine. It doesn't create tables or run queries directly. Instead, tools like dbt, SQLMesh, BI platforms, or custom applications use ASQL to:

1. Parse ASQL syntax into an AST
2. Compile to target SQL dialect
3. **Access extracted metadata** (including comments)

The consuming tool is responsible for deciding what to do with that metadata—persist it to the database, display it in a UI, store it in a data catalog, etc.

### API for Accessing Comments

ASQL exposes comments through the parsed AST and a dedicated metadata extraction API:

```python
import asql

# Method 1: Access the raw AST with comments attached
ast = asql.parse("""
/**
 * @name monthly_signups
 * @description Track user signups by month
 * @author data-team
 */
from users
where created_at > (now() - 3 months)  -- recent users only
group by month created_at (
    # as user_count  -- count of users
)
""")

# The AST nodes have .comments attributes (from SQLGlot)
print(ast.comments)  # Table-level comment block

# Method 2: Extract structured metadata
metadata = asql.extract_metadata(ast)

print(metadata.name)         # "monthly_signups"
print(metadata.description)  # "Track user signups by month"
print(metadata.author)       # "data-team"
print(metadata.columns)      # {"user_count": ColumnMetadata(...)}

# Method 3: Compile to SQL with comments preserved
sql = asql.compile(ast, dialect="postgres", preserve_comments=True)
```

### How dbt Would Use ASQL Comments

A dbt integration could use ASQL to auto-generate `schema.yml`:

```python
# In a dbt plugin or pre-commit hook
import asql
import yaml
from pathlib import Path

def generate_schema_from_asql(asql_file: Path) -> dict:
    """Generate dbt schema.yml entries from ASQL comments."""
    
    ast = asql.parse(asql_file.read_text())
    metadata = asql.extract_metadata(ast)
    
    return {
        'name': metadata.name or asql_file.stem,
        'description': metadata.description or '',
        'meta': {
            'author': metadata.author,
            'tags': metadata.tags,
            'owner': metadata.owner,
        },
        'columns': [
            {
                'name': col.name,
                'description': col.description or '',
                'meta': {'pii': col.pii} if col.pii else {}
            }
            for col in metadata.columns.values()
        ]
    }

# dbt could then call this to populate schema.yml automatically
# or a dbt adapter could read comments and call persist_docs internally
```

### How SQLMesh Would Use ASQL Comments

SQLMesh could use ASQL's metadata to populate model definitions:

```python
# In SQLMesh model loader
import asql

def load_asql_model(model_path: str):
    """Load an ASQL model with comment-based metadata."""
    
    source = Path(model_path).read_text()
    ast = asql.parse(source)
    metadata = asql.extract_metadata(ast)
    sql = asql.compile(ast, dialect=context.dialect)
    
    # SQLMesh uses this metadata for:
    # 1. Registering COMMENT ON statements to the database
    # 2. Column-level lineage documentation  
    # 3. Data catalog integration
    
    return Model(
        name=metadata.name,
        description=metadata.description,
        columns={
            col.name: col.description 
            for col in metadata.columns.values()
        },
        query=sql
    )
```

### How a BI Tool Would Use ASQL Comments

A BI tool (like Metabase, Superset, or a custom dashboard) could display comments:

```python
# In a BI tool's query editor
import asql

def parse_query_with_docs(user_query: str):
    """Parse user's ASQL query and extract documentation."""
    
    ast = asql.parse(user_query)
    metadata = asql.extract_metadata(ast)
    sql = asql.compile(ast, dialect="snowflake")
    
    return {
        'sql': sql,
        'documentation': {
            'title': metadata.name,
            'description': metadata.description,
            'columns': {
                col.name: {
                    'description': col.description,
                    'tags': col.tags,
                    'is_pii': col.pii,
                }
                for col in metadata.columns.values()
            }
        }
    }

# The BI tool can then:
# - Show column descriptions on hover
# - Warn users about PII columns
# - Display query purpose in dashboards
# - Feed this to AI for natural language queries
```

### How an AI Assistant Would Use ASQL Comments

An AI coding assistant or data analyst could use the metadata:

```python
# In an AI-powered data assistant
import asql

def analyze_query_for_ai(query: str) -> dict:
    """Prepare query context for AI consumption."""
    
    ast = asql.parse(query)
    metadata = asql.extract_metadata(ast)
    
    # Create rich context for the AI
    return {
        'query_intent': metadata.description,
        'author': metadata.author,
        'semantic_layer': {
            col.name: {
                'meaning': col.description,
                'type': 'metric' if '@metric' in (col.tags or []) else 'dimension',
                'sensitive': col.pii,
            }
            for col in metadata.columns.values()
        },
        'lineage_hints': metadata.depends,  # @depends tag
        'business_tags': metadata.tags,
    }

# AI can now answer questions like:
# "What does user_count mean in this query?"
# "Which columns contain PII?"
# "What team owns this analysis?"
```

## Implementation Phases

### Phase 1: Comment Preservation (Low Effort)
- Ensure ASQL parser preserves comments through to compiled SQL output
- SQLGlot already handles this; verify it works through ASQL pipeline
- Add `preserve_comments` flag to `asql.compile()`

### Phase 2: Metadata Extraction API (Medium Effort)
- Build `asql.extract_metadata()` function as described above
- Parse structured `@` tags when present
- Fall back to natural language extraction when no tags
- Return `QueryMetadata` dataclass with all extracted info

### Phase 3: Serialization Helpers (Low Effort)
- `metadata.to_dbt_schema()` → Returns dict suitable for dbt schema.yml
- `metadata.to_sql_comments(table_name)` → Returns COMMENT ON SQL
- `metadata.to_json()` → Returns JSON for API consumption
- These are convenience methods; consuming tools can also access raw metadata

### Phase 4: Integration Examples (Documentation)
- Document how dbt adapters can use ASQL metadata
- Document SQLMesh integration pattern
- Provide example BI tool integration
- Create sample AI assistant integration

## Design Decisions

### ✅ Decided: Comment Preservation Flag

Comments are preserved by default, following SQLGlot/SQLMesh conventions. Add a `comments` parameter to control output:

```python
# Default: comments preserved (like SQLGlot)
sql = asql.compile(query, dialect="postgres")
# Output includes comments

# Explicitly control comment preservation
sql = asql.compile(query, dialect="postgres", comments=True)   # Include comments
sql = asql.compile(query, dialect="postgres", comments=False)  # Strip comments

# SQLGlot's pattern (which we follow):
parsed.sql(dialect="postgres", comments=True)   # Default behavior
parsed.sql(dialect="postgres", comments=False)  # Strip comments
```

This matches SQLGlot's API, so it's familiar to users and easy to implement—we just pass through to SQLGlot's `.sql()` method.

### ✅ Decided: Multi-line Inline Comments

SQLGlot already handles multi-line comments well:

```asql
group by 
  user_id  /* This is a long comment
             that spans multiple lines
             explaining the deduplication logic */
```

ASQL inherits this from SQLGlot. Just need to ensure our parser doesn't interfere with comment tokens before passing to SQLGlot.

## Open Questions

1. **Should unmatched comments become table-level notes?**
   ```asql
   from users
   -- This comment isn't next to any column
   where active = true
   ```
   - Recommendation: Yes, add to `general_notes` in metadata

2. **Comment format standardization vs flexibility?**
   - Strict JSDoc-style: Better for tooling, worse for adoption
   - Flexible natural language: Better UX, harder to parse
   - Recommendation: Support both; prefer natural, extract structured when present

## Comparison Summary

| Feature | dbt | SQLMesh | ASQL (Library) |
|---------|-----|---------|----------------|
| Inline SQL comments preserved | ✅ | ✅ | ✅ |
| Auto-extract to structured metadata | ❌ | ❌ | ✅ |
| Exposes metadata via API | ❌ | ⚠️ (limited) | ✅ |
| Column-level comment extraction | ❌ | ❌ | ✅ |
| Structured @tag support | ❌ | ❌ | ✅ |
| Natural language fallback | N/A | N/A | ✅ |
| AI-friendly metadata output | ⚠️ | ⚠️ | ✅ |

**Note**: ASQL is a transpiler library. "Push to database" and "YAML generation" are responsibilities of the consuming tools (dbt, SQLMesh, BI platforms) that use ASQL's metadata API.

## Conclusion

ASQL's key innovation is **automatic extraction of inline comments to structured metadata**, exposed through a clean API. This enables consuming tools to:

1. **dbt**: Auto-generate `schema.yml` from code comments, eliminating duplicate documentation
2. **SQLMesh**: Populate model metadata for `COMMENT ON` registration
3. **BI Tools**: Display column descriptions, warn about PII, enhance UX
4. **AI Assistants**: Understand query intent, semantic meaning, and data lineage

By keeping comments in the code (the single source of truth) and providing an extraction API, we:
- Reduce documentation burden (write once in code, consume everywhere)
- Keep documentation fresh (comments evolve with code)
- Enable AI consumption of code knowledge
- Let each consuming tool decide how to use the metadata

The recommended format supports both natural language comments and structured `@` tags. Natural comments are parsed as descriptions; when `@` tags are present (like `@name`, `@author`, `@tags`), they're extracted as structured fields.

