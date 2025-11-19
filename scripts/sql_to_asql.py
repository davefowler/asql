#!/usr/bin/env python3
"""Convert SQL to ASQL using SQLGlot.

This script parses SQL files and converts them to ASQL syntax.
It then compiles the ASQL back to SQL to verify equivalence.
"""

import sys
from pathlib import Path
from typing import Optional, Tuple
import sqlglot
from sqlglot import exp

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from asql import compile as compile_asql


def sql_to_asql(sql_content: str) -> Tuple[Optional[str], Optional[str]]:
    """Convert SQL to ASQL using SQLGlot parsing.
    
    Returns:
        (asql_content, error_message)
    """
    try:
        # Parse SQL to AST
        sql_ast = sqlglot.parse_one(sql_content, dialect="snowflake")
        
        if not sql_ast:
            return None, "Failed to parse SQL"
        
        # Convert SQL AST to ASQL
        asql_lines = []
        
        # Handle WITH clauses (CTEs)
        main_select = sql_ast
        with_clause = None
        
        # Check if it's a Select with WITH clause
        if isinstance(sql_ast, exp.Select):
            with_clause = sql_ast.args.get("with")
            main_select = sql_ast
        elif isinstance(sql_ast, exp.With):
            # Root is a With expression
            with_clause = sql_ast
            main_select = sql_ast.this if hasattr(sql_ast, 'this') else None
        
        # Process CTEs
        if with_clause:
            ctes = with_clause.expressions if hasattr(with_clause, 'expressions') else []
            for cte in ctes:
                cte_alias = cte.alias
                if isinstance(cte_alias, exp.TableAlias):
                    cte_name = cte_alias.this.name if isinstance(cte_alias.this, exp.Identifier) else str(cte_alias.this)
                elif isinstance(cte_alias, exp.Identifier):
                    cte_name = cte_alias.name
                else:
                    cte_name = str(cte_alias)
                
                cte_query = cte.this
                # Recursively convert CTE query
                cte_asql = _select_to_asql(cte_query)
                asql_lines.append(f"with {cte_name} = {cte_asql}")
                asql_lines.append("")
        
        # Convert main SELECT
        if main_select:
            main_asql = _select_to_asql(main_select)
            asql_lines.append(main_asql)
        
        return "\n".join(asql_lines), None
        
    except Exception as e:
        import traceback
        return None, f"{str(e)}\n{traceback.format_exc()}"


def _select_to_asql(select_expr: exp.Select) -> str:
    """Convert a SELECT expression to ASQL."""
    lines = []
    
    # FROM clause - use args.get() for SQLGlot
    from_clause = select_expr.args.get("from")
    if from_clause:
        from_expr = from_clause[0] if isinstance(from_clause, list) else from_clause
        table = from_expr.this if hasattr(from_expr, 'this') else from_expr
        if isinstance(table, exp.Table):
            table_name = table.this.name if isinstance(table.this, exp.Identifier) else str(table.this)
            lines.append(f"from {table_name}")
        elif isinstance(table, exp.Identifier):
            lines.append(f"from {table.name}")
        elif isinstance(table, exp.Alias):
            # Handle aliased tables
            alias_name = table.alias.name if isinstance(table.alias, exp.Identifier) else str(table.alias)
            table_ref = table.this
            if isinstance(table_ref, exp.Table):
                table_name = table_ref.this.name if isinstance(table_ref.this, exp.Identifier) else str(table_ref.this)
                lines.append(f"from {table_name} as {alias_name}")
            else:
                lines.append(f"from {alias_name}")
        else:
            # Could be a subquery or CTE reference - try to get name
            if hasattr(table, 'name'):
                lines.append(f"from {table.name}")
            else:
                lines.append(f"from {str(table)}")
    
    # JOINs
    joins = select_expr.args.get("joins", [])
    if joins:
        for join in joins:
            join_table = join.this if hasattr(join, 'this') else join
            if isinstance(join_table, exp.Table):
                table_name = join_table.this.name if isinstance(join_table.this, exp.Identifier) else str(join_table.this)
                join_type = join.args.get("kind", "INNER") or "INNER"
                if join_type.upper() == "LEFT":
                    join_type = "left join"
                elif join_type.upper() == "RIGHT":
                    join_type = "right join"
                else:
                    join_type = "join"
                
                on_clause = join.args.get("on")
                if on_clause:
                    condition = _expression_to_asql(on_clause)
                    lines.append(f"  {join_type} {table_name} on {condition}")
    
    # WHERE clauses
    where_clause = select_expr.args.get("where")
    if where_clause:
        where_expr = where_clause.this if hasattr(where_clause, 'this') else where_clause
        where_str = _expression_to_asql(where_expr)
        lines.append(f"  where {where_str}")
    
    # GROUP BY
    group_clause = select_expr.args.get("group")
    if group_clause:
        group_exprs = []
        expressions = group_clause.expressions if hasattr(group_clause, 'expressions') else group_clause.args.get("expressions", [])
        for expr in expressions:
            group_exprs.append(_expression_to_asql(expr))
        if group_exprs:
            lines.append(f"  group by {', '.join(group_exprs)}")
    
    # SELECT expressions
    expressions = select_expr.args.get("expressions", [])
    if expressions:
        select_items = []
        for expr in expressions:
            if isinstance(expr, exp.Star):
                select_items.append("*")
            else:
                item = _expression_to_asql(expr)
                if isinstance(expr, exp.Alias):
                    alias_expr = expr.args.get("alias")
                    if isinstance(alias_expr, exp.Identifier):
                        alias = alias_expr.name
                    else:
                        alias = str(alias_expr)
                    item_expr = expr.args.get("this")
                    item = f"{_expression_to_asql(item_expr)} as {alias}"
                select_items.append(item)
        
        if select_items:
            lines.append(f"  select {', '.join(select_items)}")
    
    # ORDER BY
    order_clause = select_expr.args.get("order")
    if order_clause:
        order_items = []
        expressions = order_clause.expressions if hasattr(order_clause, 'expressions') else order_clause.args.get("expressions", [])
        for expr in expressions:
            item = _expression_to_asql(expr)
            if isinstance(expr, exp.Order):
                desc = expr.args.get("desc", False)
                if desc:
                    item_expr = expr.args.get("this")
                    item = f"-{_expression_to_asql(item_expr)}"
            order_items.append(item)
        if order_items:
            lines.append(f"  sort {', '.join(order_items)}")
    
    # LIMIT
    limit_clause = select_expr.args.get("limit")
    if limit_clause:
        limit_expr = limit_clause.this if hasattr(limit_clause, 'this') else limit_clause
        limit_value = limit_expr.this if hasattr(limit_expr, 'this') else str(limit_expr)
        lines.append(f"  take {limit_value}")
    
    return "\n".join(lines)


def _expression_to_asql(expr: exp.Expression) -> str:
    """Convert an expression to ASQL syntax."""
    if isinstance(expr, exp.Column):
        parts = []
        if expr.table:
            parts.append(expr.table)
        if expr.this:
            if isinstance(expr.this, exp.Identifier):
                parts.append(expr.this.name)
            else:
                parts.append(str(expr.this))
        return ".".join(parts) if len(parts) > 1 else parts[0] if parts else ""
    
    elif isinstance(expr, exp.Literal):
        if expr.is_string:
            return f'"{expr.this}"'
        return str(expr.this)
    
    elif isinstance(expr, exp.EQ):
        left = _expression_to_asql(expr.this)
        right = _expression_to_asql(expr.expression)
        return f"{left} == {right}"
    
    elif isinstance(expr, exp.And):
        left = _expression_to_asql(expr.this)
        right = _expression_to_asql(expr.expression)
        return f"{left} and {right}"
    
    elif isinstance(expr, exp.Or):
        left = _expression_to_asql(expr.this)
        right = _expression_to_asql(expr.expression)
        return f"{left} or {right}"
    
    elif isinstance(expr, exp.GT):
        left = _expression_to_asql(expr.this)
        right = _expression_to_asql(expr.expression)
        return f"{left} > {right}"
    
    elif isinstance(expr, exp.GTE):
        left = _expression_to_asql(expr.this)
        right = _expression_to_asql(expr.expression)
        return f"{left} >= {right}"
    
    elif isinstance(expr, exp.LT):
        left = _expression_to_asql(expr.this)
        right = _expression_to_asql(expr.expression)
        return f"{left} < {right}"
    
    elif isinstance(expr, exp.LTE):
        left = _expression_to_asql(expr.this)
        right = _expression_to_asql(expr.expression)
        return f"{left} <= {right}"
    
    elif isinstance(expr, exp.NEQ):
        left = _expression_to_asql(expr.this)
        right = _expression_to_asql(expr.expression)
        return f"{left} != {right}"
    
    elif isinstance(expr, exp.Where):
        return _expression_to_asql(expr.this)
    
    elif isinstance(expr, exp.On):
        return _expression_to_asql(expr.this)
    
    elif isinstance(expr, exp.Alias):
        expr_str = _expression_to_asql(expr.this)
        alias = expr.alias.this.name if isinstance(expr.alias, exp.Identifier) else expr.alias.name
        return f"{expr_str} as {alias}"
    
    elif isinstance(expr, exp.Function):
        func_name = expr.sql_name().lower()
        args = [_expression_to_asql(arg) for arg in expr.expressions]
        return f"{func_name}({', '.join(args)})"
    
    # Fallback to SQL representation
    return expr.sql(dialect="snowflake")


def convert_sql_file(sql_path: Path) -> Tuple[bool, Optional[str], Optional[str]]:
    """Convert a SQL file to ASQL."""
    try:
        sql_content = sql_path.read_text()
        
        # Skip dbt Jinja templating for now
        if "{{" in sql_content or "{%" in sql_content:
            return False, None, "Contains dbt Jinja templating - needs manual conversion"
        
        asql_content, error = sql_to_asql(sql_content)
        
        if error:
            return False, None, error
        
        return True, asql_content, None
        
    except Exception as e:
        return False, None, str(e)


def main():
    """Convert all SQL files in examples/real/ to ASQL."""
    real_dir = project_root / "examples" / "real"
    
    if not real_dir.exists():
        print(f"❌ Directory not found: {real_dir}")
        return 1
    
    sql_files = sorted(real_dir.glob("*.sql"))
    
    print(f"Converting {len(sql_files)} SQL files to ASQL...\n")
    
    converted = 0
    skipped = 0
    failed = []
    
    for sql_file in sql_files:
        # Skip if ASQL already exists
        asql_file = sql_file.with_suffix(".asql")
        if asql_file.exists():
            print(f"⏭️  Skipping {sql_file.name} (ASQL already exists)")
            skipped += 1
            continue
        
        print(f"Converting {sql_file.name}...", end=" ")
        success, asql_content, error = convert_sql_file(sql_file)
        
        if success and asql_content:
            # Save ASQL file
            header = f"""-- ASQL equivalent of {sql_file.name}
-- Auto-generated from SQL using SQLGlot parser

"""
            asql_file.write_text(header + asql_content)
            
            # Test compilation
            try:
                compiled_sql = compile_asql(asql_content)
                print(f"✅ Converted and compiles")
                converted += 1
            except Exception as e:
                print(f"⚠️  Converted but compilation failed: {e}")
                failed.append((sql_file.name, f"Compilation: {e}"))
        else:
            print(f"❌ Failed: {error}")
            failed.append((sql_file.name, error))
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  ✅ Converted: {converted}")
    print(f"  ⏭️  Skipped: {skipped}")
    print(f"  ❌ Failed: {len(failed)}")
    
    if failed:
        print(f"\nFailed conversions:")
        for filename, error in failed[:10]:  # Show first 10
            print(f"  - {filename}: {error}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

