# Pipeline CTE Implementation Guide

## Overview

This document explains how to implement pipelined SQL transformations in ASQL, where each pipeline step becomes a separate transformation (either a CTE or nested subquery). This is a core feature that makes ASQL similar to PRQL - allowing queries to be built as a sequence of transformations.

## Current State

**Current Implementation**: ASQL currently generates a single SELECT statement with all clauses attached directly.

**Desired Behavior**: Each pipeline step should become a separate transformation, building up the query incrementally.

## Example: What We Want

### ASQL Input
```asql
from users
  where status == "active"
  group by country ( # as total_users )
  order by -total_users
```

### Desired SQL Output (CTE Approach)
```sql
WITH 1_where_status AS (
  SELECT * FROM users WHERE status = 'active'
),
2_group_by_country AS (
  SELECT country, COUNT(*) AS total_users
  FROM 1_where_status
  GROUP BY country
)
SELECT country, total_users
FROM 2_group_by_country
ORDER BY total_users DESC
```

### Alternative SQL Output (Nested Subquery Approach)
```sql
SELECT country, total_users
FROM (
  SELECT country, COUNT(*) AS total_users
  FROM (
    SELECT * FROM users WHERE status = 'active'
  ) AS 1_where_status
  GROUP BY country
) AS 2_group_by_country
ORDER BY total_users DESC
```

## SQLGlot Capabilities

SQLGlot **fully supports** both CTEs and nested subqueries:

### CTE Support
- `exp.With` - Represents a WITH clause
- `exp.CTE` - Represents a single CTE definition
- `exp.TableAlias` - Used for CTE aliases
- Already used in ASQL for `SET` statements (see `compiler.py` lines 62-71)

### Nested Subquery Support
- `exp.Select` can be nested as a subquery
- `exp.Subquery` - Wraps a SELECT as a subquery
- Can be used in FROM clauses

## Implementation Approaches

### Approach 1: CTE-Based Pipeline (Recommended)

**Concept**: Each pipeline step becomes a CTE, chained together in a WITH clause.

**Pros**:
- ✅ **Readability**: Each step is clearly named and separated
- ✅ **Debugging**: Easy to test individual steps by selecting from a CTE
- ✅ **Reusability**: CTEs can be referenced multiple times
- ✅ **SQL Standard**: CTEs are part of SQL standard (SQL:1999)
- ✅ **Matches PRQL**: PRQL uses CTEs for pipeline steps
- ✅ **Matches SPEC**: ASQL spec explicitly calls for CTE-based pipelines

**Cons**:
- ⚠️ **MySQL < 8.0**: Doesn't support CTEs (but SQLGlot can transpile to nested subqueries)
- ⚠️ **Slightly more verbose**: More SQL text generated
- ⚠️ **Potential performance**: Some databases may materialize CTEs (though modern optimizers handle this well)

**Implementation**:

```python
def compile_with_cte_pipeline(parser: ASQLParser) -> exp.Select:
    """
    Compile ASQL pipeline into CTE-based SQL.
    
    Steps:
    1. Parse pipeline operators into a list of transformations
    2. Create a CTE for each transformation step
    3. Chain CTEs together in a WITH clause
    4. Final SELECT references the last CTE
    """
    # Parse and identify pipeline steps
    steps = identify_pipeline_steps(parser)
    
    # Build CTEs for each step
    ctes = []
    previous_step_name = None
    
    for i, step in enumerate(steps):
        # Generate descriptive CTE name based on operation type
        step_name = generate_step_name(i + 1, step)
        
        # Create SELECT for this step
        step_select = build_select_for_step(step, previous_step_name)
        
        # Create CTE
        cte = exp.CTE(
            this=step_select,
            alias=exp.TableAlias(this=exp.Identifier(this=step_name))
        )
        ctes.append(cte)
        previous_step_name = step_name
    
    # Create final SELECT that uses the last CTE
    final_select = exp.Select()
    final_select.set("expressions", [exp.Star()])  # Or specific columns
    final_select.set("from", exp.From(
        this=exp.Table(this=exp.Identifier(this=previous_step_name))
    ))
    
    # Attach WITH clause with all CTEs
    final_select.set("with", exp.With(expressions=ctes))
    
    return final_select

def generate_step_name(step_number: int, step: PipelineStep) -> str:
    """
    Generate a descriptive CTE name based on the step's primary operation.
    
    Examples:
        - Step with WHERE: "1_where_status" or "1_where"
        - Step with GROUP BY: "2_group_by_country" or "2_group_by"
        - Step with JOIN: "3_join_orders" or "3_join"
    
    The name includes:
        1. Step number (for ordering)
        2. Operation type (where, group_by, join, etc.)
        3. Optional: Key column/table name (if available and not too verbose)
    """
    parts = [str(step_number)]
    
    # Determine primary operation
    if step.group_by:
        parts.append("group_by")
        # Optionally include grouping column name
        if step.group_by.group_expr:
            # Extract column name if simple identifier
            col_name = extract_column_name(step.group_by.group_expr)
            if col_name:
                parts.append(col_name)
    elif step.joins:
        parts.append("join")
        # Optionally include joined table name
        if step.joins[0].this:
            table_name = extract_table_name(step.joins[0].this)
            if table_name:
                parts.append(table_name)
    elif step.where_clauses:
        parts.append("where")
        # Optionally include filter column name
        if step.where_clauses[0].this:
            col_name = extract_column_name(step.where_clauses[0].this)
            if col_name:
                parts.append(col_name)
    elif step.sort:
        parts.append("sort")
    elif step.limit:
        parts.append("limit")
    elif step.select:
        parts.append("select")
    else:
        # Fallback for FROM-only step
        parts.append("from")
    
    return "_".join(parts)

def extract_column_name(expr: exp.Expression) -> Optional[str]:
    """Extract column name from expression if it's a simple identifier."""
    if isinstance(expr, exp.Column):
        return expr.name
    elif isinstance(expr, exp.Identifier):
        return expr.name
    # For complex expressions, return None to keep name simple
    return None

def extract_table_name(expr: exp.Expression) -> Optional[str]:
    """Extract table name from expression if it's a simple table reference."""
    if isinstance(expr, exp.Table):
        return expr.name
    elif isinstance(expr, exp.Identifier):
        return expr.name
    return None
```

**Naming Considerations**:

The descriptive naming approach (`1_where_status`, `2_group_by_country`) provides several benefits:

1. **Self-documenting SQL**: The generated SQL is immediately understandable without reading the ASQL source
2. **Easier debugging**: You can test individual steps: `SELECT * FROM 1_where_status`
3. **Better readability**: Especially helpful when reviewing generated SQL in logs or query plans
4. **Incremental building advantage**: Since CTEs are built incrementally, we know the operation type at each step, making descriptive names straightforward to generate

**Implementation Notes**:
- Names should be sanitized to ensure valid SQL identifiers (handle special characters, reserved words)
- Keep names concise but descriptive - include column/table names only when they add clarity
- For complex expressions, fall back to operation-only names (`1_where` instead of `1_where_complex_expression`)
- The numeric prefix ensures proper ordering and makes it clear these are generated names

**Pipeline Step Identification**:

```python
def identify_pipeline_steps(parser: ASQLParser) -> List[PipelineStep]:
    """
    Identify logical pipeline steps from parsed AST.
    
    Each step represents a transformation that should become a CTE.
    Steps are separated by operations that fundamentally change the result set:
    - WHERE filters (can combine multiple WHEREs into one step)
    - GROUP BY (aggregation - new step)
    - JOIN (new step)
    - SELECT/PROJECT (column selection - usually final step)
    """
    steps = []
    current_step = PipelineStep()
    
    # FROM is always first step
    current_step.from_clause = parser.from_expr
    
    for operator in parser.pipeline_operators:
        if operator.type == "WHERE":
            # WHEREs can be combined in same step
            current_step.add_where(operator)
        elif operator.type == "JOIN":
            # JOIN starts new step
            steps.append(current_step)
            current_step = PipelineStep()
            current_step.add_join(operator)
        elif operator.type == "GROUP_BY":
            # GROUP BY starts new step
            steps.append(current_step)
            current_step = PipelineStep()
            current_step.group_by = operator
        elif operator.type == "SELECT":
            # SELECT is usually final step
            current_step.select = operator
        elif operator.type == "SORT":
            # SORT can be in same step or final step
            current_step.sort = operator
        elif operator.type == "TAKE":
            # TAKE is usually final step
            current_step.limit = operator
    
    if current_step.has_content():
        steps.append(current_step)
    
    return steps
```

**Step Building**:

```python
def build_select_for_step(step: PipelineStep, previous_step_name: Optional[str]) -> exp.Select:
    """Build a SELECT statement for a pipeline step."""
    select = exp.Select()
    
    # FROM clause: either base table or previous CTE
    if previous_step_name:
        from_expr = exp.From(
            this=exp.Table(this=exp.Identifier(this=previous_step_name))
        )
    else:
        from_expr = step.from_clause
    
    select.set("from", from_expr)
    
    # Add WHERE clauses
    if step.where_clauses:
        # Combine multiple WHEREs with AND
        combined_where = combine_where_clauses(step.where_clauses)
        select.set("where", combined_where)
    
    # Add JOINs
    if step.joins:
        select.set("joins", step.joins)
    
    # Add GROUP BY
    if step.group_by:
        select.set("group", step.group_by.group_expr)
        # Set SELECT expressions to grouping columns + aggregations
        select.set("expressions", step.group_by.get_expressions())
    
    # Add SELECT columns (if specified)
    if step.select:
        select.set("expressions", step.select.expressions)
    elif not step.group_by:
        # Default to SELECT * if no GROUP BY and no explicit SELECT
        select.set("expressions", [exp.Star()])
    
    # Add SORT (ORDER BY)
    if step.sort:
        select.set("order", step.sort.order_expr)
    
    # Add LIMIT
    if step.limit:
        select.set("limit", step.limit)
    
    return select
```

### Approach 2: Nested Subquery Pipeline

**Concept**: Each pipeline step becomes a nested subquery, with the outer query being the final transformation.

**Pros**:
- ✅ **Universal compatibility**: Works on all SQL databases (including MySQL < 8.0)
- ✅ **More compact**: Less SQL text generated
- ✅ **Familiar pattern**: Many SQL developers are used to nested subqueries

**Cons**:
- ⚠️ **Readability**: Deeply nested queries can be hard to read
- ⚠️ **Debugging**: Harder to test individual steps
- ⚠️ **Doesn't match PRQL**: PRQL uses CTEs, not nested subqueries
- ⚠️ **Doesn't match SPEC**: ASQL spec calls for CTE-based approach

**Implementation**:

```python
def compile_with_nested_subqueries(parser: ASQLParser) -> exp.Select:
    """
    Compile ASQL pipeline into nested subquery SQL.
    
    Steps:
    1. Parse pipeline operators into a list of transformations
    2. Build nested SELECT statements, innermost to outermost
    3. Each step wraps the previous step as a subquery
    """
    steps = identify_pipeline_steps(parser)
    
    # Build from innermost to outermost
    current_query = None
    
    for i, step in enumerate(reversed(steps)):  # Reverse to build from inside out
        step_select = build_select_for_step(step, None)
        
        if current_query:
            # Wrap previous query as subquery in FROM
            # Step number: innermost is 1, outermost is len(steps)
            step_number = len(steps) - i
            step_name = generate_step_name(step_number, step)
            subquery = exp.Subquery(
                this=current_query,
                alias=exp.TableAlias(this=exp.Identifier(this=step_name))
            )
            step_select.set("from", exp.From(this=subquery))
        
        current_query = step_select
    
    return current_query
```

### Approach 3: Hybrid Approach (Recommended for Production)

**Concept**: Use CTEs by default, but allow configuration to use nested subqueries for compatibility.

**Pros**:
- ✅ **Best of both worlds**: CTEs when possible, subqueries when needed
- ✅ **Database compatibility**: Can adapt to target database capabilities
- ✅ **User choice**: Can be configured per query or globally

**Cons**:
- ⚠️ **More complex**: Need to implement both approaches
- ⚠️ **Configuration overhead**: Need to decide which to use

**Implementation**:

```python
def compile(
    asql_query: str,
    dialect: Optional[str] = None,
    pretty: bool = False,
    use_ctes: Optional[bool] = None,  # None = auto-detect based on dialect
) -> str:
    """
    Compile ASQL with configurable pipeline approach.
    
    Args:
        use_ctes: If True, use CTEs. If False, use nested subqueries.
                  If None, auto-detect based on dialect capabilities.
    """
    parser = ASQLParser(asql_query)
    select_expr = parser.parse()
    
    # Auto-detect CTE support
    if use_ctes is None:
        use_ctes = dialect_supports_ctes(dialect)
    
    # Transform to pipeline-based query
    if use_ctes:
        pipeline_select = compile_with_cte_pipeline(parser)
    else:
        pipeline_select = compile_with_nested_subqueries(parser)
    
    # Generate SQL
    sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
    return pipeline_select.sql(dialect=sql_dialect, pretty=pretty)

def dialect_supports_ctes(dialect: Optional[str]) -> bool:
    """Check if dialect supports CTEs."""
    if dialect is None:
        return True  # Default to CTEs
    
    # MySQL < 8.0 doesn't support CTEs
    if dialect.lower() == "mysql":
        # Would need to check MySQL version, default to False for safety
        return False
    
    # Most modern databases support CTEs
    cte_supporting = ["postgres", "postgresql", "bigquery", "snowflake", 
                      "redshift", "sqlite", "duckdb", "spark"]
    return dialect.lower() in cte_supporting
```

## Detailed Tradeoffs

### Performance Considerations

#### CTEs
- **Materialization**: Some databases (like PostgreSQL) may materialize CTEs, which can be slower for large datasets
- **Optimization**: Modern databases (PostgreSQL 12+, MySQL 8.0+) optimize CTEs well
- **Query planning**: CTEs can help query planners optimize better by breaking down complex queries

#### Nested Subqueries
- **Inlining**: Most databases inline subqueries, which can be faster
- **Optimization**: Query planners can optimize across subquery boundaries
- **Memory**: No intermediate result sets stored

**Verdict**: Performance differences are usually negligible. Modern databases handle both well. Choose based on readability and compatibility.

### Readability Comparison

#### CTE Example (with descriptive names)
```sql
WITH 1_where_status AS (
  SELECT * FROM users WHERE status = 'active'
),
2_group_by_country AS (
  SELECT country, COUNT(*) AS total
  FROM 1_where_status
  GROUP BY country
)
SELECT country, total
FROM 2_group_by_country
ORDER BY total DESC
```

**Readability**: ⭐⭐⭐⭐⭐ Excellent - Each step is clearly named with operation type and key columns

#### Nested Subquery Example (with descriptive names)
```sql
SELECT country, total
FROM (
  SELECT country, COUNT(*) AS total
  FROM (
    SELECT * FROM users WHERE status = 'active'
  ) AS 1_where_status
  GROUP BY country
) AS 2_group_by_country
ORDER BY total DESC
```

**Readability**: ⭐⭐⭐ Good - Clear but requires reading inside-out; descriptive names help identify steps

**Verdict**: CTEs are significantly more readable, especially for complex pipelines.

### Compatibility

| Database | CTE Support | Notes |
|----------|-------------|-------|
| PostgreSQL | ✅ Yes (8.4+) | Full support |
| MySQL | ✅ Yes (8.0+) | Not supported < 8.0 |
| SQLite | ✅ Yes (3.8.3+) | Full support |
| BigQuery | ✅ Yes | Full support |
| Snowflake | ✅ Yes | Full support |
| SQL Server | ✅ Yes (2005+) | Full support |
| Oracle | ✅ Yes (9i+) | Full support |

**Verdict**: CTEs are widely supported. Only MySQL < 8.0 is a concern, and SQLGlot can transpile CTEs to nested subqueries for MySQL.

## Implementation Strategy

### Phase 1: Refactor Parser to Track Pipeline Steps

**Current**: Parser builds a single SELECT with all clauses attached.

**Needed**: Parser should track pipeline steps as separate transformations.

```python
class PipelineStep:
    """Represents a single pipeline transformation step."""
    from_clause: Optional[exp.From] = None
    where_clauses: List[exp.Where] = []
    joins: List[exp.Join] = []
    group_by: Optional[exp.Group] = None
    aggregations: List[exp.Expression] = []
    select: Optional[List[exp.Expression]] = None
    sort: Optional[exp.Order] = None
    limit: Optional[exp.Limit] = None
    
    def has_content(self) -> bool:
        """Check if step has any content."""
        return any([
            self.from_clause,
            self.where_clauses,
            self.joins,
            self.group_by,
            self.select,
            self.sort,
            self.limit
        ])
```

### Phase 2: Implement CTE Pipeline Compiler

1. Modify parser to return pipeline steps instead of single SELECT
2. Implement `compile_with_cte_pipeline()` function
3. Update main `compile()` function to use CTE pipeline
4. Add tests for multi-step pipelines

### Phase 3: Add Configuration Option

1. Add `use_ctes` parameter to `compile()` function
2. Implement `compile_with_nested_subqueries()` function
3. Add dialect detection for CTE support
4. Add tests for both approaches

### Phase 4: Optimization

1. Combine multiple WHERE clauses in same step
2. Combine multiple JOINs in same step
3. Optimize step boundaries (when to create new step)
4. Handle edge cases (empty steps, single-step queries)

## Code Structure

```
asql/
├── compiler.py           # Main compile() function
├── pipeline.py           # NEW: Pipeline step tracking and CTE generation
│   ├── identify_steps()  # Identify pipeline steps from AST
│   ├── build_cte_pipeline()  # Build CTE-based pipeline
│   └── build_nested_pipeline()  # Build nested subquery pipeline
└── parser.py            # Modified to track pipeline steps
```

## Testing Strategy

### Test Cases

1. **Simple pipeline**: `from users where status == "active"`
2. **Multi-step**: `from users where X group by Y order by Z`
3. **With JOINs**: `from users join orders group by country`
4. **Complex**: Multiple WHEREs, JOINs, GROUP BYs
5. **Edge cases**: Single step, empty steps, only SELECT

### Expected Outputs

For each test, verify:
- Correct number of CTEs/steps
- Correct step boundaries
- Correct column references between steps
- Correct final SELECT
- SQL is valid and executable

## Migration Path

1. **Keep current single-SELECT approach as fallback**
2. **Add pipeline CTE as opt-in** (via parameter or config)
3. **Make pipeline CTE default** after testing
4. **Remove single-SELECT approach** (or keep as optimization for single-step queries)

## Recommendations

1. **Use CTE approach by default** - Matches PRQL and ASQL spec, better readability
2. **Support nested subqueries for MySQL < 8.0** - Via SQLGlot transpilation or explicit option
3. **Allow user configuration** - Let users choose if needed
4. **Optimize step boundaries** - Don't create unnecessary steps
5. **Combine compatible operations** - Multiple WHEREs in same step, etc.

## Conclusion

**Yes, SQLGlot fully supports implementing pipelined CTEs.** The implementation is straightforward and aligns with ASQL's design goals. The CTE approach is recommended for readability and alignment with PRQL, with nested subqueries as a fallback for compatibility.

The main work is:
1. Refactoring the parser to track pipeline steps
2. Implementing the CTE pipeline builder
3. Testing with various query patterns

This is a significant architectural improvement that will make ASQL truly pipeline-based like PRQL.

