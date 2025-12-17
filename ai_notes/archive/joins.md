# ASQL Joins: Current State and Simplification Ideas

**Purpose**: Document how ASQL currently handles joins and explore ideas for making joins simpler and more automatic.

**Last Updated**: December 2025

**See also**:
- [OMNI_COMPARISON.md](OMNI_COMPARISON.md) - Omni's relationship/join model
- [DBT_DEEP_INTEGRATION_IDEATION.md](DBT_DEEP_INTEGRATION_IDEATION.md) - dbt metadata integration

---

## 1. ASQL Join Syntax

### 1.1 Join Operators

ASQL uses symbolic operators for joins, with `&` representing the join point and `?` marking optional (nullable) sides:

| Operator | Join Type | Meaning |
|----------|-----------|---------|
| `&` | INNER | Both sides must match |
| `&?` | LEFT | Right side is optional (can be NULL) |
| `?&` | RIGHT | Left side is optional (can be NULL) |
| `?&?` | FULL OUTER | Both sides are optional |
| `*` | CROSS | Cartesian product |

**Mnemonic**: "The `?` marks the side that might be NULL"

### 1.2 Basic Join Syntax

```asql
-- INNER JOIN: only matching rows
from opportunities & owners
  select opportunities.amount, owners.name

-- LEFT JOIN: all opportunities, owners may be NULL
from opportunities &? owners
  select opportunities.amount, owners.name

-- RIGHT JOIN: all owners, opportunities may be NULL  
from opportunities ?& owners
  select opportunities.amount, owners.name

-- FULL OUTER JOIN: all rows from both sides
from opportunities ?&? owners
  select opportunities.amount, owners.name

-- CROSS JOIN: every combination
from opportunities * owners
  select opportunities.amount, owners.name
```

### 1.3 Aliasing Tables

Use `as` to alias joined tables:

```asql
from opportunities &? users as owner
  select opportunities.amount, owner.name, owner.email
```

### 1.4 Explicit Join Conditions

When automatic FK inference isn't desired or possible, specify the join condition with `on`:

```asql
from opportunities &? owners on opportunities.owner_id = owners.id
  select opportunities.amount, owners.name

-- With alias
from opportunities &? users as owner on opportunities.owner_id = owner.id
  select opportunities.amount, owner.name
```

### 1.5 Automatic FK Inference

When no `on` clause is provided, ASQL infers the join condition based on:

1. **Explicit schema metadata** (if defined in model file)
2. **Naming convention**: Look for `{table}_id` or `{singular_table}_id` columns
3. **Single FK check**: If only one FK exists between tables, use it

```asql
-- If opportunities.owner_id exists and owners table exists
from opportunities &? owners
  -- Automatically becomes: on opportunities.owner_id = owners.id
```

### 1.6 Dot Notation for FK Traversal

**This works WITHOUT a model file** - ASQL recognizes FK naming conventions.

If a column follows the pattern `{name}_id`, you can traverse it using `.{name}.`:

```asql
-- opportunities has owner_id column (FK to users table)
from opportunities
  select 
    opportunities.amount,
    opportunities.owner.name,      -- Auto-joins via owner_id
    opportunities.owner.email      -- Same join, different column
```

Compiles to:
```sql
SELECT 
  opportunities.amount,
  owner_1.name,
  owner_1.email
FROM opportunities
LEFT JOIN users AS owner_1 ON opportunities.owner_id = owner_1.id
```

**Key points:**
- The FK column `owner_id` enables `.owner.` traversal
- ASQL finds the target table by checking: `owners` table, then `users` table (singularization)
- Dot traversal defaults to LEFT JOIN (the FK might be NULL)
- Multiple references to same FK reuse the same join (no duplicate joins)

### 1.7 Combining Explicit Joins and Dot Notation

Both explicit aliases AND FK-based dot notation work in the same query:

```asql
from opportunities &? users as owner on opportunities.owner_id = owner.id
  select 
    owner.name,                    -- Works: explicit alias
    opportunities.owner.name       -- Also works: FK traversal (reuses same join!)
```

ASQL is smart enough to recognize that `opportunities.owner` refers to the same join as the explicit `users as owner` when the FK matches.

### 1.8 Multiple FKs to Same Table

When a table has multiple FKs to the same table, use the `<alias>_<table>_id` convention:

```asql
-- accounts has owner_user_id, manager_user_id, support_rep_user_id all → users
from accounts
  select 
    accounts.owner.name as owner_name,           -- via owner_user_id
    accounts.manager.name as manager_name,       -- via manager_user_id  
    accounts.support_rep.name as support_name    -- via support_rep_user_id
```

The FK naming pattern `<alias>_user_id` enables `.alias.` dot traversal to the `users` table.

Or with explicit joins:
```asql
from accounts 
  &? users as owner on accounts.owner_user_id = owner.id
  &? users as manager on accounts.manager_user_id = manager.id
  select owner.name, manager.name
```

### 1.9 Chained FK Traversal

Navigate through multiple relationships:

```asql
-- order_items.order_id → orders.user_id → users
from order_items
  select 
    order_items.quantity,
    order_items.order.total,           -- → orders
    order_items.order.user.name        -- → orders → users
```

### 1.10 Optional Model Metadata

While not required, you can define relationships explicitly for:
- Non-standard FK names
- Additional validation
- Documentation

```yaml
# asql_schema.yml
relationships:
  - from: opportunities.owner_id
    to: users.id
    alias: owner
    
  - from: accounts.primary_contact
    to: contacts.id  # Non-standard name, needs explicit mapping
```

---

## 2. Convention-Based Inference Rules

ASQL uses naming conventions to auto-detect joins.

### 2.1 FK Naming Patterns

| FK Column | Alias | Target Table | Dot Traversal |
|-----------|-------|--------------|---------------|
| `user_id` | `user` | `users` | `.user.` |
| `account_id` | `account` | `accounts` | `.account.` |
| `owner_user_id` | `owner` | `users` | `.owner.` |
| `manager_user_id` | `manager` | `users` | `.manager.` |
| `parent_account_id` | `parent_account` | `accounts` | `.parent_account.` |
| `created_by_user_id` | `created_by` | `users` | `.created_by.` |

**Pattern**: `<alias>_<table_name>_id` → alias is `<alias>`, traverses to `<table_name>` table

For simple FKs: `<table_name>_id` → alias is `<table_name>`, traverses to that table

### 2.2 FK Target Table Resolution

When ASQL parses an FK column, it extracts:
1. **Alias**: Everything before the final `_id` (e.g., `owner_user` → `owner`)
2. **Table hint**: The last segment before `_id` (e.g., `owner_user_id` → `user`)

**Table matching is flexible** - teams use different conventions:

| FK Column | Table Hint | Checks (in order) | 
|-----------|------------|-------------------|
| `user_id` | `user` | `users` → `user` |
| `owner_user_id` | `user` | `users` → `user` |
| `account_id` | `account` | `accounts` → `account` |

**Resolution steps:**
1. Parse FK column to extract alias and table hint
2. Try plural form of table hint (e.g., `users`)
3. If not found, try singular form (e.g., `user`)
4. If not found → error with suggestions

This accommodates both naming conventions:
- Plural tables: `users`, `accounts`, `orders`
- Singular tables: `user`, `account`, `order`

### 2.3 Reverse Traversal Not Supported

**FK traversal only works in the FK→target direction** (many→one).

```asql
-- ✅ Supported: accounts.owner → users (via owner_user_id on accounts)
from accounts
  select accounts.owner.name

-- ❌ Not supported: users.owned_accounts → accounts
-- There's no FK on users pointing to accounts
from users
  select users.owned_accounts.name  -- Error!
```

**Why?** Reverse traversal (one→many) has no naming convention to derive from - the FK column lives on the OTHER table. Use explicit joins or model metadata for reverse relationships.

```asql
-- Use explicit join for one→many
from users &? accounts on users.id = accounts.owner_user_id
  select users.name, accounts.name
```

### 2.4 Priority Order

1. Explicit `on` clause (always wins)
2. Explicit model metadata (if defined)
3. Naming convention inference
4. Single FK check (if only one FK between tables)
5. Error with suggestions

**Philosophy**: Follow conventions → automatic joins. Non-standard names → explicit syntax (encourages standardization).

### 2.5 Schema Awareness

ASQL's parser has **full schema awareness** - this is a key differentiator enabling automatic FK inference.

**When schema is available:**
- Column lookups can distinguish `table.column` from `table.fk.column`
- FK target tables can be validated
- Ambiguous joins detected and reported

**When schema is NOT available:**
- Fall back to explicit `on` clauses
- Dot notation FK traversal disabled
- Clear error messages suggest running schema compilation

**Future CLI:**
```bash
asql compile-schema --source=dbt    # Generate schema from dbt manifest
asql compile-schema --source=db     # Introspect database directly
```

---

## 3. Schema Metadata Sources

ASQL can get schema information from multiple sources:

### 3.1 dbt Manifest/Catalog

```json
// manifest.json
{
  "nodes": {
    "model.project.orders": {
      "columns": {
        "user_id": {
          "name": "user_id",
          "description": "FK to users"
        }
      }
    }
  }
}
```

**Integration**: Read dbt's `manifest.json` and `catalog.json` to get:
- Column names and types
- Relationship metadata (from dbt relationships tests)
- Table descriptions

### 3.2 SQLMesh

SQLMesh also provides schema information via its catalog.

### 3.3 Direct Database Introspection

Query `information_schema` directly:

```sql
-- Get foreign keys
SELECT 
  tc.table_name, kcu.column_name,
  ccu.table_name AS foreign_table,
  ccu.column_name AS foreign_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu 
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY';
```

**Reality**: Many data warehouses (BigQuery, Snowflake, Redshift) don't enforce FKs, so explicit constraints may not exist. Convention-based inference becomes essential.

### 3.4 ASQL Schema File

Define relationships explicitly in an ASQL config:

```yaml
# asql_schema.yml
relationships:
  - from: orders.user_id
    to: users.id
    type: many_to_one
    
  - from: order_items.order_id
    to: orders.id
    type: many_to_one

  - from: accounts.owner_id
    to: users.id
    alias: owner
    
  - from: accounts.manager_id
    to: users.id
    alias: manager
```

---

## 4. Edge Cases and Ambiguity Resolution

### 4.1 Column vs FK Traversal Ambiguity

What if `opportunities.owner` could be either:
- A JSON/struct column named `owner`
- FK traversal via `owner_id`

**Resolution: Column name always wins.**

This is a simple lookup: if the column exists, use it. If it doesn't, check if it might be an FK alias.

```asql
-- If opportunities has BOTH an 'owner' JSON column AND 'owner_id' FK:
from opportunities
  select 
    opportunities.owner,              -- Gets the JSON column (column exists)
    opportunities.owner_user.name     -- FK traversal via owner_user_id
```

**Implementation**: When resolving `table.X.Y`:
1. Does column `X` exist on `table`? → Column access (JSON field `.Y`)
2. Does column `X_id` or `X_<something>_id` exist? → FK traversal
3. Neither → Error: unknown column or relationship

**Recommendation**: This edge case is rare. If you have a JSON column named `owner` AND an `owner_id` FK, consider renaming one for clarity.

### 4.2 Join Deduplication

ASQL should recognize when an explicit join and dot notation refer to the same relationship:

```asql
from opportunities &? users as owner on opportunities.owner_id = owner.id
  select 
    owner.name,                    -- Explicit alias
    opportunities.owner.email      -- FK traversal - REUSES same join!
```

Both references should use the same join, not create two separate joins to users.

**Implementation**: Track join conditions and reuse when FK traversal matches an existing explicit join's condition.

### 4.3 Ambiguous FK Targets

When multiple tables could match an FK:

```asql
-- company_id exists, but both 'company' and 'companies' tables exist
from orders
  select orders.company.name  -- Which table?
```

**Resolution**:
1. Exact match first (`company` table)
2. Pluralized match (`companies` table)
3. Error listing candidates if multiple matches

### 4.4 Circular FK Traversal

```asql
-- employees.manager_id → employees.id (self-referential)
from employees
  select 
    employees.name,
    employees.manager.name,           -- Manager's name
    employees.manager.manager.name    -- Manager's manager's name
```

Each traversal creates a new aliased join:
```sql
SELECT 
  employees.name,
  manager_1.name,
  manager_2.name
FROM employees
LEFT JOIN employees AS manager_1 ON employees.manager_id = manager_1.id
LEFT JOIN employees AS manager_2 ON manager_1.manager_id = manager_2.id
```

### 4.5 Performance Considerations

Dot notation can accidentally trigger expensive joins:

```asql
from orders
  select 
    orders.id,
    orders.user.company.region.country.continent.name  -- 5 joins!
```

**Recommendations:**
- Compiler warning for deep traversal chains (configurable depth)
- Query plan hints in verbose mode
- Consider requiring explicit joins for chains > N deep

---

## 5. Anti-Join Shorthand

Common pattern: find rows that *don't* have a match:

```asql
-- Verbose way
from users &? orders on users.id = orders.user_id
  where orders.id is null

-- Proposed shorthand: 'without' keyword
from users
  without orders  -- Users with no orders
```

The `without` keyword implies LEFT JOIN + WHERE null check on the right side's primary key.

---

## 6. Join Safety and Warnings

### 6.1 Fanout Detection

When joining one-to-many, aggregations on the "one" side can be wrong:

```asql
from orders &? users
  group region (
    # as order_count              -- Correct (order-level)
    total users.lifetime_value    -- ⚠️ Warning: aggregating user column after fanout
  )
```

**Proposed warnings:**
- "Aggregating `users.lifetime_value` after joining orders. Each user is duplicated per order. Did you mean to aggregate at user level first?"
- Suggest: "Use `# of distinct user_id` instead of `#`"

### 6.2 Ambiguous Join Resolution

When multiple paths exist:

```asql
-- If accounts has both created_by_user_id and owner_user_id pointing to users
from accounts &? users  -- ❌ Error: Ambiguous - which FK?
```

**Error message:**
```
Ambiguous join: accounts has multiple FKs to users:
  - accounts.created_by_user_id → users.id
  - accounts.owner_user_id → users.id

Use explicit syntax:
  from accounts &? users as owner on accounts.owner_user_id = owner.id

Or use dot notation for specific FK:
  from accounts
    select accounts.owner.name, accounts.created_by.name
```

### 6.3 Missing Relationship Detection

```asql
from orders &? inventory  -- ❌ Error: No relationship found
```

**Error message:**
```
No relationship found between orders and inventory.

Checked:
  - orders.inventory_id (column doesn't exist)
  - inventory.order_id (column doesn't exist)
  - Schema metadata (no relationship defined)

Use explicit join condition:
  from orders &? inventory on orders.product_id = inventory.product_id
```

---

## 7. Schema Metadata API

ASQL needs a schema metadata layer:

```python
class SchemaMetadata:
    def get_columns(self, table: str) -> List[Column]
    def get_relationships(self, table: str) -> List[Relationship]
    def find_relationship(self, from_table: str, to_table: str) -> Optional[Relationship]
    def get_primary_key(self, table: str) -> Column
```

**Sources (priority order):**
1. Explicit ASQL schema file (`asql_schema.yml`)
2. dbt manifest/catalog
3. SQLMesh catalog
4. Database information_schema
5. Convention-based inference

---

## 8. Examples

### 8.1 Simple Auto-Join

```asql
-- With FK inference: orders.user_id → users.id
from orders &? users
  select orders.id, users.name, orders.amount
```

Compiles to:
```sql
SELECT orders.id, users.name, orders.amount
FROM orders
LEFT JOIN users ON orders.user_id = users.id
```

### 8.2 Dot Notation (No Explicit Join)

```asql
-- FK traversal auto-joins
from orders
  select 
    orders.id, 
    orders.amount,
    orders.user.name,     -- Auto LEFT JOIN via user_id
    orders.user.email
```

Compiles to:
```sql
SELECT 
  orders.id, 
  orders.amount,
  user_1.name,
  user_1.email
FROM orders
LEFT JOIN users AS user_1 ON orders.user_id = user_1.id
```

### 8.3 Multi-Table with Aliases

```asql
from order_items 
  &? orders 
  &? users as customer on orders.user_id = customer.id
  &? products
  group customer.country (
    total amount as revenue
    # of distinct product_id as products_sold
  )
```

### 8.4 Mixed Explicit and Dot Notation

```asql
from order_items
  select 
    order_items.quantity,
    order_items.order.total,              -- via order_id
    order_items.order.user.name,          -- chained: order_id → user_id
    order_items.product.name              -- via product_id
```

### 8.5 Anti-Join Pattern

```asql
-- Find users who haven't ordered in 2024
from users
  without orders where year(orders.created_at) = 2024
  select users.id, users.email
```

### 8.6 Self-Join (Hierarchies)

```asql
-- Employees and their managers (explicit)
from employees &? employees as manager on employees.manager_id = manager.id
  select employees.name, manager.name as manager_name
```

Or with dot notation:
```asql
-- Uses manager_id FK automatically
from employees
  select 
    employees.name, 
    employees.manager.name as manager_name
```

### 8.7 Multiple FKs to Same Table

```asql
-- accounts has owner_user_id, manager_user_id, created_by_user_id all → users
from accounts
  select 
    accounts.name,
    accounts.owner.name as owner_name,        -- via owner_user_id
    accounts.manager.name as manager_name,    -- via manager_user_id
    accounts.created_by.name as creator_name  -- via created_by_user_id
```

### 8.8 Inner Join (Both Sides Required)

```asql
-- Only orders that have a valid user
from orders & users
  select orders.id, users.name
```

### 8.9 Full Outer Join

```asql
-- All orders and all users, matched where possible
from orders ?&? users on orders.user_id = users.id
  select orders.id, users.name
```

---

## 9. Implementation Considerations

### 9.1 AST Representation

Joins need to be represented in the AST:

```python
class JoinOperator(Enum):
    INNER = "&"      # Both sides required
    LEFT = "&?"      # Right side optional
    RIGHT = "?&"     # Left side optional  
    FULL = "?&?"     # Both sides optional
    CROSS = "*"      # Cartesian product

class Join:
    operator: JoinOperator
    target_table: str
    alias: Optional[str]
    condition: Optional[Expression]  # None if auto-resolved
    resolved_from: Literal["explicit", "convention", "metadata"]

class FKTraversal:
    """Represents table.fk.column dot notation"""
    base_table: str
    fk_column: str      # e.g., "owner_id"  
    fk_alias: str       # e.g., "owner" (without _id)
    target_column: str  # e.g., "name"
    # Resolved during compilation to a Join + column reference
```

### 9.2 Resolution Phase

During compilation:
1. Parse join operators (`&`, `&?`, `?&`, `?&?`, `*`)
2. Parse `on` clause if present; otherwise mark for FK inference
3. Collect all FK traversals (`.fk.column` patterns)
4. Resolve FK traversals:
   a. Find matching FK column (`{fk}_id`)
   b. Determine target table
   c. Create implicit LEFT JOIN if not already joined
   d. If explicit join exists with matching FK, reuse it
5. Generate SQL with all joins and proper aliases

### 9.3 Join Deduplication Logic

```python
def resolve_fk_traversal(traversal: FKTraversal, existing_joins: List[Join]) -> Join:
    """Check if this FK traversal matches an existing explicit join."""
    fk_column = f"{traversal.fk_alias}_id"
    
    for join in existing_joins:
        if join.condition matches f"{traversal.base_table}.{fk_column} = {join.alias}.id":
            return join  # Reuse existing join
    
    # Create new implicit LEFT JOIN
    return create_implicit_join(traversal)
```

### 9.4 Error Handling

- Ambiguous FK target → error listing candidate tables
- Multiple FKs to same table without `on` clause → error with suggestions
- Missing FK column for traversal → error explaining pattern expected
- Potential fanout → warning (configurable to error)
- Deep traversal chain → warning (configurable depth limit)

---

## 10. Summary: Join Syntax

| SQL | ASQL Operator | ASQL with ON clause |
|-----|---------------|---------------------|
| `INNER JOIN` | `&` | `& users on ...` |
| `LEFT JOIN` | `&?` | `&? users on ...` |
| `RIGHT JOIN` | `?&` | `?& users on ...` |
| `FULL OUTER JOIN` | `?&?` | `?&? users on ...` |
| `CROSS JOIN` | `*` | `* users` |

| Feature | Syntax | Example |
|---------|--------|---------|
| Aliasing | `as` | `&? users as owner` |
| Explicit condition | `on` | `&? users on orders.user_id = users.id` |
| FK traversal | `.fk.` | `orders.user.name` (via `user_id`) |
| Anti-join | `without` | `without orders` |

**Key principles:**
1. **`?` marks the optional/nullable side**: Easy to remember
2. **FK inference via naming convention**: `{name}_id` enables `.{name}.` traversal
3. **No model file required**: Convention-based inference works out of the box
4. **Explicit always works**: Full `on` clause syntax never fails
5. **Smart deduplication**: Dot traversal reuses explicit joins when FK matches
6. **Clear errors**: Tell users exactly what went wrong and how to fix

---

## 11. Open Questions

1. **Default join for dot notation?** Currently LEFT (FK might be NULL). Should it be configurable?
2. **Deep traversal limits?** Warn/error for chains > N joins?
3. **Schema file format?** YAML? Part of ASQL? Compatible with dbt?
4. **Fanout handling?** Warn? Error? Auto-fix with symmetric aggregates?
5. **Ambiguity precedence**: Column vs FK traversal—is "column wins" the right default?
6. **Table resolution**: How to handle `owner_id` when both `owner` and `owners` tables exist?
