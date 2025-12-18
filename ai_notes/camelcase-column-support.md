# CamelCase Column Support: Exploration & Design

**Status**: Exploration document investigating seamless support for camelCase columns (e.g., `createdAt`) without requiring underscores or explicit quoting.

**Related**: 
- `configurable-auto-aliasing.md` - Auto-aliasing configuration
- `underscore-notation-edge-cases.md` - Current underscore notation limitations
- `docs/spec.md` - Case-safe design (Section 18.2)

---

## Overview

Currently, ASQL's underscore notation (`sum_amount`, `day_of_week_created_at`) assumes snake_case column names. This document explores how ASQL could seamlessly handle camelCase columns (like `createdAt`, `userId`, `firstName`) without requiring users to:
- Manually convert to snake_case
- Explicitly quote identifiers
- Remember exact naming conventions

**Goal**: Write `sum(createdAt)` or `sum_createdAt` and have ASQL handle it smoothly, regardless of whether the database column is `created_at`, `createdAt`, or `CreatedAt`.

---

## Current State

### What Works Today

ASQL has **case-safe** design (Section 18.2 of spec):
- Case-insensitive matching for table/column names
- Normalizes identifiers internally
- Resolves against schema case-insensitively

**Example**:
```asql
from Users
  select firstName, createdAt
```

ASQL resolves:
- `Users` → `users` (case-insensitive match)
- `firstName` → `first_name` (if that's the actual column)
- `createdAt` → `created_at` (if that's the actual column)

### What Doesn't Work Smoothly

1. **Underscore notation assumes snake_case**:
   ```asql
   -- If column is "createdAt" (camelCase):
   sum_createdAt     -- ❌ Doesn't match underscore pattern cleanly
   sum(createdAt)    -- ✅ Works, but loses shorthand benefit
   ```

2. **Auto-aliasing generates snake_case**:
   ```asql
   -- If column is "createdAt":
   sum(createdAt)    -- → auto-aliases to "sum_createdAt" (mixed convention)
   year(createdAt)   -- → auto-aliases to "year_createdAt" (mixed convention)
   ```

3. **No bidirectional mapping**:
   - Can't write `sum_createdAt` and have it resolve to `sum(createdAt)`
   - Can't preserve original naming convention in output

---

## Problem Statement

### The Analyst's Perspective

**Scenario**: Working with a database that has camelCase columns (common in JavaScript/TypeScript ecosystems, MongoDB, some APIs):

```sql
-- Database schema:
CREATE TABLE users (
  id INTEGER,
  firstName VARCHAR(100),
  lastName VARCHAR(100),
  createdAt TIMESTAMP,
  updatedAt TIMESTAMP,
  userId INTEGER
);
```

**Current ASQL experience**:
```asql
-- Option 1: Use explicit function calls (verbose)
from users
  group by year(createdAt) (
    sum(userId) as total_users
  )

-- Option 2: Try underscore notation (doesn't work cleanly)
from users
  group by year_createdAt (  -- ❌ Ambiguous: year(createdAt) or year(created_at)?
    sum_userId               -- ❌ Ambiguous: sum(userId) or sum(user_id)?
  )
```

**Desired experience**:
```asql
-- Natural, works regardless of naming convention
from users
  group by year_createdAt (  -- ✅ Resolves to year(createdAt)
    sum_userId,              -- ✅ Resolves to sum(userId)
    avg_userId               -- ✅ Resolves to avg(userId)
  )
order by -sum_userId         -- ✅ References auto-aliased column
```

---

## Implementation Approaches

### Approach 1: Auto-Quoting in Transpilation

**Concept**: Detect camelCase identifiers and automatically quote them in generated SQL.

#### How It Works

1. **Parse**: Accept camelCase identifiers as-is
2. **Detect**: Identify camelCase patterns (starts lowercase, contains uppercase)
3. **Quote**: Generate SQL with quoted identifiers: `"createdAt"`, `"userId"`
4. **Preserve**: Keep original case in output

#### Example

```asql
-- ASQL input:
from users
  select firstName, createdAt
  where userId = 123

-- Generated SQL:
SELECT "firstName", "createdAt"
FROM users
WHERE "userId" = 123
```

#### Pros
- ✅ **Simple**: Minimal changes to existing code
- ✅ **Preserves naming**: Original case maintained
- ✅ **Database-agnostic**: Works with any SQL dialect that supports quoted identifiers
- ✅ **No schema dependency**: Doesn't require schema introspection

#### Cons
- ❌ **Dialect-dependent**: Some databases are case-sensitive with quotes (PostgreSQL), others aren't (MySQL)
- ❌ **Mixed conventions**: Output mixes quoted and unquoted identifiers
- ❌ **Doesn't solve underscore notation**: Still can't write `sum_createdAt` cleanly

#### Implementation Notes

```python
def detect_camel_case(identifier: str) -> bool:
    """Detect if identifier is camelCase (starts lowercase, contains uppercase)."""
    return identifier[0].islower() and any(c.isupper() for c in identifier[1:])

def quote_if_camel_case(identifier: str, dialect: str) -> str:
    """Quote identifier if camelCase, respecting dialect rules."""
    if detect_camel_case(identifier):
        return f'"{identifier}"'  # PostgreSQL-style
        # or: return f'`{identifier}`'  # MySQL-style
    return identifier
```

---

### Approach 2: Snake Case Conversion (Bidirectional)

**Concept**: Convert camelCase ↔ snake_case automatically during transpilation, with bidirectional mapping.

#### How It Works

1. **Parse**: Accept camelCase identifiers
2. **Convert**: Transform camelCase → snake_case for internal processing
3. **Map**: Store bidirectional mapping (camelCase ↔ snake_case)
4. **Generate**: Use snake_case in SQL (or convert back based on config)
5. **Reverse**: When loading results, convert back to camelCase if desired

#### Conversion Rules

```python
def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    # createdAt → created_at
    # userId → user_id
    # firstName → first_name
    # XMLParser → xml_parser
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    # created_at → createdAt
    # user_id → userId
    components = name.split('_')
    return components[0] + ''.join(x.capitalize() for x in components[1:])
```

#### Example

```asql
-- ASQL input (camelCase):
from users
  select firstName, createdAt
  group by userId (
    sum_amount
  )

-- Internal processing:
# firstName → first_name (converted)
# createdAt → created_at (converted)
# userId → user_id (converted)
# sum_amount → sum(amount) (function pattern, no conversion needed)

-- Generated SQL (snake_case):
SELECT first_name, created_at
FROM users
GROUP BY user_id (
  SUM(amount) AS sum_amount
)
```

#### Pros
- ✅ **Consistent output**: All identifiers use snake_case (standard SQL convention)
- ✅ **Works with underscore notation**: `sum_createdAt` → `sum(createdAt)` → `sum(created_at)` → `sum_created_at`
- ✅ **Database-friendly**: snake_case is standard SQL convention
- ✅ **Bidirectional**: Can convert back when loading results

#### Cons
- ❌ **Loss of original naming**: Original camelCase is lost unless stored separately
- ❌ **Ambiguity risk**: `userId` and `user_id` both map to `user_id` (but case-insensitive matching helps)
- ❌ **Complexity**: Need to track conversions and reverse them

#### Implementation Notes

```python
class ColumnNameMapper:
    """Bidirectional mapping between naming conventions."""
    
    def __init__(self):
        self.camel_to_snake = {}  # createdAt → created_at
        self.snake_to_camel = {}  # created_at → createdAt
    
    def normalize(self, name: str) -> str:
        """Normalize to snake_case for internal use."""
        if self._is_camel_case(name):
            snake = camel_to_snake(name)
            self.camel_to_snake[name] = snake
            self.snake_to_camel[snake] = name
            return snake
        return name.lower()  # Already snake_case or other
    
    def restore(self, snake_name: str, prefer_camel: bool = False) -> str:
        """Restore original naming convention."""
        if prefer_camel and snake_name in self.snake_to_camel:
            return self.snake_to_camel[snake_name]
        return snake_name
```

---

### Approach 3: Schema-Aware Resolution

**Concept**: Use schema metadata to map between naming conventions automatically.

#### How It Works

1. **Introspect**: Load schema metadata (column names, table names)
2. **Map**: Build mapping between all naming variations (camelCase, snake_case, PascalCase)
3. **Resolve**: Match user input against all variations
4. **Generate**: Use actual database column names in SQL

#### Example

```python
# Schema metadata:
schema = {
    'users': {
        'columns': ['id', 'firstName', 'lastName', 'createdAt', 'userId']
    }
}

# User writes:
from users
  select firstName, createdAt

# ASQL resolves:
# - firstName → matches 'firstName' in schema
# - createdAt → matches 'createdAt' in schema

# Generated SQL uses actual names:
SELECT firstName, createdAt FROM users
```

#### Pros
- ✅ **Accurate**: Uses actual database column names
- ✅ **Flexible**: Handles any naming convention (camelCase, snake_case, PascalCase, etc.)
- ✅ **No conversion needed**: Works with database as-is
- ✅ **Supports underscore notation**: Can resolve `sum_createdAt` → `sum(createdAt)` using schema

#### Cons
- ❌ **Requires schema access**: Needs database connection or schema file
- ❌ **Performance**: Schema introspection adds overhead
- ❌ **Complexity**: Need to handle schema caching, updates, etc.
- ❌ **Not always available**: Some environments don't have schema access

#### Implementation Notes

```python
class SchemaResolver:
    """Resolve identifiers using schema metadata."""
    
    def __init__(self, schema: Dict[str, Dict[str, List[str]]]):
        """
        schema = {
            'table_name': {
                'columns': ['col1', 'col2', ...]
            }
        }
        """
        self.schema = schema
        self.cache = {}  # Cache resolved names
    
    def resolve_column(self, table: str, identifier: str) -> str:
        """Resolve identifier to actual column name."""
        # Check cache first
        key = (table, identifier.lower())
        if key in self.cache:
            return self.cache[key]
        
        # Find case-insensitive match
        columns = self.schema.get(table, {}).get('columns', [])
        for col in columns:
            if col.lower() == identifier.lower():
                self.cache[key] = col
                return col
        
        # Fallback: return as-is (might be a function pattern)
        return identifier
```

---

### Approach 4: Hybrid: Smart Detection + Conversion

**Concept**: Combine multiple approaches - detect naming convention, convert intelligently, preserve when possible.

#### How It Works

1. **Detect convention**: Analyze schema or user input to determine naming convention
2. **Convert on-the-fly**: Transform identifiers to match convention
3. **Preserve originals**: Store original names for reverse compilation
4. **Smart resolution**: Use schema when available, fall back to conversion

#### Detection Strategy

```python
def detect_naming_convention(schema: Dict) -> str:
    """Detect primary naming convention from schema."""
    camel_count = 0
    snake_count = 0
    
    for table_info in schema.values():
        for col in table_info.get('columns', []):
            if '_' in col:
                snake_count += 1
            elif col[0].islower() and any(c.isupper() for c in col[1:]):
                camel_count += 1
    
    if camel_count > snake_count:
        return 'camelCase'
    elif snake_count > camel_count:
        return 'snake_case'
    else:
        return 'mixed'  # Use schema-aware resolution
```

#### Example

```asql
-- Schema has camelCase columns:
# users: [id, firstName, lastName, createdAt]

-- User writes:
from users
  select firstName, createdAt
  group by year_createdAt (
    sum_userId
  )

-- ASQL processing:
# 1. Detect: Schema uses camelCase
# 2. Resolve: year_createdAt → year(createdAt) → year("createdAt")
# 3. Resolve: sum_userId → sum(userId) → sum("userId")
# 4. Generate SQL with quoted identifiers:
SELECT 
  "firstName",
  "createdAt",
  YEAR("createdAt") AS year_createdAt,
  SUM("userId") AS sum_userId
FROM users
GROUP BY YEAR("createdAt")
```

#### Pros
- ✅ **Best of all worlds**: Combines benefits of multiple approaches
- ✅ **Adaptive**: Works with any naming convention
- ✅ **Intelligent**: Uses schema when available, converts when not
- ✅ **Preserves intent**: Maintains user's naming style when possible

#### Cons
- ❌ **Most complex**: Requires multiple systems working together
- ❌ **Harder to debug**: Multiple code paths
- ❌ **Performance**: More processing steps

---

## Benefits to Analysts

### 1. Reduced Cognitive Overhead

**Before** (current):
```asql
-- Analyst must remember exact naming convention
from users
  where created_at > @2024-01-01  -- Must use snake_case
  group by user_id (
    sum_amount
  )
```

**After** (with camelCase support):
```asql
-- Analyst can use natural naming
from users
  where createdAt > @2024-01-01  -- Works with camelCase
  group by userId (
    sum_amount
  )
```

**Benefit**: Analysts don't need to remember or convert between naming conventions. Write queries using whatever feels natural.

---

### 2. Seamless Integration with Frontend/API Code

**Scenario**: Frontend code uses camelCase, database uses camelCase, but SQL tools expect snake_case.

**Before**:
```typescript
// Frontend code
const user = {
  firstName: "John",
  createdAt: new Date(),
  userId: 123
};

// Must convert to snake_case for SQL
const query = `
  SELECT first_name, created_at, user_id
  FROM users
  WHERE user_id = ${user.userId}
`;
```

**After**:
```asql
-- ASQL matches frontend naming
from users
  select firstName, createdAt, userId
  where userId = 123
```

**Benefit**: No mental context switching between frontend code (camelCase) and SQL (snake_case). Write queries that match your application code.

---

### 3. Works with Modern APIs and ORMs

Many modern APIs and ORMs use camelCase:
- **GraphQL**: Typically camelCase (`userName`, `createdAt`)
- **REST APIs**: Often camelCase (JSON convention)
- **MongoDB**: Uses camelCase by default
- **TypeScript/JavaScript**: Standard is camelCase

**Benefit**: ASQL queries can match API response structures directly, making it easier to:
- Compare query results with API responses
- Write queries that mirror API endpoints
- Use the same naming in both contexts

---

### 4. Less Error-Prone

**Before**:
```asql
-- Easy to make mistakes:
from users
  where created_at > @2024-01-01  -- Correct
  -- vs
  where createdAt > @2024-01-01   -- Error: column not found
  -- vs
  where "createdAt" > @2024-01-01 -- Works but verbose
```

**After**:
```asql
-- All of these work:
from users
  where created_at > @2024-01-01   -- ✅ Works
  where createdAt > @2024-01-01    -- ✅ Works (auto-resolved)
  where "createdAt" > @2024-01-01  -- ✅ Works (explicit)
```

**Benefit**: Fewer errors from case/naming mismatches. ASQL handles the conversion automatically.

---

### 5. Natural for JavaScript/TypeScript Developers

Many analysts come from JavaScript/TypeScript backgrounds where camelCase is standard:

```typescript
// TypeScript/JavaScript convention
const user = {
  firstName: "John",
  lastName: "Doe",
  createdAt: new Date(),
  isActive: true
};
```

**Benefit**: Analysts can write ASQL queries using familiar naming conventions without learning SQL-specific conventions.

---

### 6. Underscore Notation Works with Any Convention

**Current limitation**: Underscore notation (`sum_amount`) assumes snake_case.

**With camelCase support**:
```asql
-- All of these work:
from users
  group by userId (
    sum_amount,        -- ✅ Works (amount is snake_case)
    sum_userId,        -- ✅ Works (userId is camelCase, resolves to sum(userId))
    year_createdAt     -- ✅ Works (createdAt is camelCase)
  )
```

**Benefit**: Underscore notation becomes truly universal - works regardless of underlying naming convention.

---

### 7. Easier Onboarding for New Analysts

**Before**: New analysts must learn:
- SQL syntax
- ASQL syntax
- Snake_case convention
- When to quote identifiers

**After**: New analysts learn:
- SQL syntax
- ASQL syntax
- (Naming convention handled automatically)

**Benefit**: Lower barrier to entry. Analysts can focus on learning query logic, not naming conventions.

---

## Implementation Considerations

### 1. Performance Impact

**Questions**:
- How much overhead does conversion add?
- Is schema introspection fast enough?
- Should conversions be cached?

**Recommendation**: 
- Cache conversions aggressively
- Lazy-load schema metadata
- Profile performance with real queries

---

### 2. Ambiguity Resolution

**Problem**: What if both `userId` and `user_id` exist?

**Solutions**:
1. **Prefer exact match**: If user writes `userId`, prefer `userId` over `user_id`
2. **Case-insensitive fallback**: If exact match fails, try case-insensitive
3. **Error on ambiguity**: Raise error if multiple matches found
4. **Explicit qualification**: Require `users.userId` to disambiguate

**Recommendation**: Prefer exact match → case-insensitive → error on ambiguity.

---

### 3. Reverse Compilation (SQL → ASQL)

**Challenge**: When converting SQL back to ASQL, which naming convention to use?

**Options**:
1. **Preserve original**: Use names from original ASQL query (if available)
2. **Detect from SQL**: Infer convention from SQL identifiers
3. **Config-based**: Use user preference from config
4. **Schema-based**: Use convention from schema

**Recommendation**: Config-based with schema fallback.

---

### 4. Configuration

**Proposed config options**:

```yaml
# asql.config.yaml
compile:
  # Naming convention handling
  column_naming:
    # Options: "auto" (detect), "preserve" (keep as-is), "convert_to_snake" (always convert)
    strategy: "auto"
    
    # When to quote identifiers
    quote_camel_case: true  # Quote camelCase in SQL output
    
    # Schema file path (optional)
    schema_file: "schema.json"
    
    # Preferred output convention
    output_convention: "snake_case"  # or "camelCase", "preserve"
```

---

### 5. Backward Compatibility

**Critical**: Must not break existing queries.

**Strategy**:
1. **Default behavior**: Keep current behavior (snake_case assumed)
2. **Opt-in**: Enable camelCase support via config
3. **Gradual migration**: Allow both conventions during transition

**Example**:
```yaml
# Default (backward compatible):
compile:
  column_naming:
    strategy: "preserve"  # Current behavior

# Opt-in (new behavior):
compile:
  column_naming:
    strategy: "auto"  # Enable camelCase support
```

---

## Recommended Approach

### Phase 1: Auto-Quoting (Simple Start)

**Goal**: Make camelCase columns work without breaking existing code.

**Implementation**:
1. Detect camelCase identifiers during parsing
2. Auto-quote them in SQL generation
3. Preserve original case

**Scope**: Minimal changes, low risk, immediate benefit.

---

### Phase 2: Schema-Aware Resolution (Enhanced)

**Goal**: Use schema metadata to resolve naming conventions accurately.

**Implementation**:
1. Add schema introspection support
2. Build identifier mapping (camelCase ↔ snake_case)
3. Resolve identifiers using schema
4. Support underscore notation with camelCase

**Scope**: More complex, requires schema access, but more accurate.

---

### Phase 3: Bidirectional Conversion (Full Support)

**Goal**: Full support for any naming convention with conversion.

**Implementation**:
1. Add camelCase ↔ snake_case conversion functions
2. Store bidirectional mappings
3. Support reverse compilation
4. Configurable output convention

**Scope**: Most complete solution, but most complex.

---

## Open Questions

1. **Should we support PascalCase?** (`CreatedAt`, `UserId`)
   - **Recommendation**: Yes, via case-insensitive matching

2. **What about mixed conventions?** (some columns camelCase, some snake_case)
   - **Recommendation**: Handle per-column, use schema when available

3. **How to handle function patterns with camelCase?** (`sum_createdAt` → `sum(createdAt)`)
   - **Recommendation**: Parse underscore notation, detect camelCase in column part, resolve via schema/conversion

4. **Should auto-aliasing preserve input convention?**
   - **Option A**: Always use snake_case (`sum(createdAt)` → `sum_created_at`)
   - **Option B**: Preserve input (`sum(createdAt)` → `sum_createdAt`)
   - **Recommendation**: Configurable, default to snake_case for consistency

5. **Performance vs. Accuracy tradeoff?**
   - **Option A**: Fast conversion (no schema needed)
   - **Option B**: Accurate resolution (schema required)
   - **Recommendation**: Hybrid - use schema when available, convert when not

---

## Examples: Before & After

### Example 1: Simple Query

**Before**:
```asql
from users
  select firstName, lastName, createdAt
  where userId = 123
```
**Issue**: Must know exact column names, may need quotes

**After**:
```asql
from users
  select firstName, lastName, createdAt
  where userId = 123
```
**Benefit**: Works seamlessly, ASQL handles resolution

---

### Example 2: Aggregation with Underscore Notation

**Before**:
```asql
from orders
  group by customerId (
    sum_amount,
    avg_price
  )
```
**Issue**: `sum_amount` works, but `sum_customerId` doesn't resolve cleanly

**After**:
```asql
from orders
  group by customerId (
    sum_amount,
    sum_customerId,    -- ✅ Resolves to sum(customerId)
    avg_price
  )
```
**Benefit**: Underscore notation works with camelCase columns

---

### Example 3: Date Functions

**Before**:
```asql
from users
  group by year_createdAt (  -- ❌ Ambiguous
    #
  )
```

**After**:
```asql
from users
  group by year_createdAt (  -- ✅ Resolves to year(createdAt)
    #
  )
```
**Benefit**: Natural syntax works regardless of naming convention

---

## Conclusion

Supporting camelCase columns seamlessly would significantly improve ASQL's usability for analysts working with modern APIs, frontend code, and JavaScript/TypeScript ecosystems. The recommended approach is a phased implementation:

1. **Start simple**: Auto-quote camelCase identifiers (Phase 1)
2. **Add intelligence**: Schema-aware resolution (Phase 2)
3. **Complete support**: Bidirectional conversion (Phase 3)

This provides immediate value while building toward a complete solution that works with any naming convention.

**Key Benefits**:
- ✅ Reduced cognitive overhead
- ✅ Seamless integration with frontend/API code
- ✅ Less error-prone
- ✅ Natural for JavaScript/TypeScript developers
- ✅ Universal underscore notation
- ✅ Easier onboarding

**Next Steps**:
1. Implement Phase 1 (auto-quoting) as proof of concept
2. Gather user feedback
3. Evaluate need for Phase 2/3 based on real-world usage
