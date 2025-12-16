# SQL Comments: Storage, Extraction, and Integration

## Overview

This document explores how to store, extract, and leverage SQL/ASQL comments for documentation, metadata, and AI-assisted workflows. The goal is to make comments first-class citizens that flow from code to documentation to data catalogs.

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
  month created_at, -- the signup month
  user_id,          -- deduplicated user identifier  
  age               -- age at signup
  (
   # as user_count  -- count of users per group
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

### Integration with dbt/SQLMesh

ASQL could generate the required YAML/Python metadata files:

```python
def generate_dbt_schema(metadata: QueryMetadata) -> str:
    """Generate dbt schema.yml from extracted metadata."""
    import yaml
    
    schema = {
        'version': 2,
        'models': [{
            'name': metadata.table_name or 'query',
            'description': metadata.description or '',
            'columns': [
                {
                    'name': col.name,
                    'description': col.description or ''
                }
                for col in metadata.columns.values()
            ]
        }]
    }
    
    return yaml.dump(schema, default_flow_style=False)

def generate_sqlmesh_model(metadata: QueryMetadata, sql: str) -> str:
    """Generate SQLMesh model with metadata."""
    columns_dict = {
        col.name: col.description 
        for col in metadata.columns.values() 
        if col.description
    }
    
    return f'''
MODEL (
    name {metadata.table_name or 'query'},
    description '{metadata.description or ''}',
    columns (
        {', '.join(f"{k} '{v}'" for k, v in columns_dict.items())}
    )
);

{sql}
'''

def generate_sql_comments(metadata: QueryMetadata, table_name: str) -> str:
    """Generate SQL COMMENT ON statements."""
    statements = []
    
    if metadata.description:
        statements.append(
            f"COMMENT ON TABLE {table_name} IS '{metadata.description}';"
        )
    
    for col in metadata.columns.values():
        if col.description:
            statements.append(
                f"COMMENT ON COLUMN {table_name}.{col.name} IS '{col.description}';"
            )
    
    return '\n'.join(statements)
```

## Recommended Comment Format

After researching various approaches, here's the recommended format for ASQL:

### Simple Natural Comments (Preferred for Most Cases)

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

### Structured Metadata (For Data Catalog Integration)

When richer metadata is needed:

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
where created_at > (now() - 3 months)  -- @filter: recent users only
group by 
  month created_at as signup_month,    -- @grain: monthly cohort
  age                                  -- @dimension: user age
  (
    # as user_count                    -- @metric: user count
  )
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

## Implementation Phases

### Phase 1: Comment Preservation (Low Effort)
- Ensure ASQL parser preserves comments through to SQL output
- SQLGlot already handles this; verify it works through ASQL pipeline

### Phase 2: Metadata Extraction (Medium Effort)
- Build `extract_metadata()` function as described above
- Create CLI command: `asql metadata query.asql`
- Output JSON/YAML metadata

### Phase 3: Integration Generators (Medium Effort)
- `asql generate-dbt-schema query.asql` → `schema.yml`
- `asql generate-sql-comments query.asql` → `COMMENT ON` statements
- `asql generate-sqlmesh-model query.asql` → SQLMesh model file

### Phase 4: Bidirectional Sync (Higher Effort)
- Read existing dbt schema.yml and merge with extracted comments
- Update comments in ASQL files from YAML changes
- Git-friendly conflict resolution

### Phase 5: AI Integration (Future)
- Store extracted metadata in vector database
- Enable AI queries like "what columns contain PII?"
- Auto-suggest comments based on column names and usage

## Open Questions

1. **Should we strip comments from compiled SQL?**
   - Pro: Cleaner output, smaller queries
   - Con: Loses documentation at execution time
   - Recommendation: Make configurable with `preserve_comments=True/False`

2. **How to handle multi-line inline comments?**
   ```asql
   group by 
     user_id  /* This is a long comment
                that spans multiple lines
                explaining the deduplication logic */
   ```
   - SQLGlot handles this well
   - Need to ensure ASQL parser doesn't break on them

3. **Should unmatched comments become table-level notes?**
   ```asql
   from users
   -- This comment isn't next to any column
   where active = true
   ```
   - Recommendation: Yes, add to `general_notes` in metadata

4. **Comment format standardization vs flexibility?**
   - Strict JSDoc-style: Better for tooling, worse for adoption
   - Flexible natural language: Better UX, harder to parse
   - Recommendation: Support both; prefer natural, extract structured when present

## Comparison Summary

| Feature | dbt | SQLMesh | ASQL (Proposed) |
|---------|-----|---------|-----------------|
| Inline SQL comments preserved | ✅ | ✅ | ✅ |
| Auto-extract to metadata | ❌ | ❌ | ✅ |
| YAML documentation | ✅ | ✅ | ✅ (generated) |
| Push to database | ✅ | ✅ | ✅ (via SQL) |
| Column-level extraction | ❌ | ❌ | ✅ |
| AI-friendly output | ⚠️ | ⚠️ | ✅ |

## Conclusion

The key innovation ASQL can bring is **automatic extraction of inline comments to structured metadata**. This closes the gap between "comments in code" and "documentation in catalogs" that exists in dbt and SQLMesh.

By leveraging SQLGlot's comment preservation and building extraction tooling, we can:
1. Reduce documentation burden (write once, propagate everywhere)
2. Keep documentation close to code (single source of truth)
3. Enable AI consumption of code knowledge
4. Generate dbt/SQLMesh metadata automatically

The recommended approach is natural language comments with optional structured tags, supporting both developer ergonomics and tooling needs.

