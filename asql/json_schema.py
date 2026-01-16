"""
JSON Schema for Visual ASQL Editor

Provides bidirectional conversion between SQLGlot AST and JSON representation
for use in the visual query builder interface.
"""

from typing import Dict, Any, List, Optional, Union
from sqlglot import exp


def ast_to_json(ast: exp.Select) -> Dict[str, Any]:
    """
    Convert SQLGlot AST to JSON representation for visual editor.

    Args:
        ast: SQLGlot Select expression

    Returns:
        Dict with 'from' and 'transforms' keys
    """
    query = {
        'from': {},
        'transforms': []
    }

    # Extract FROM clause
    if from_clause := ast.args.get('from'):
        table = from_clause.this
        if table:
            query['from'] = {
                'table': table.name if hasattr(table, 'name') else str(table),
                'alias': table.alias if hasattr(table, 'alias') else None
            }

    transform_id = 0

    # Extract WHERE
    if where := ast.args.get('where'):
        query['transforms'].append({
            'id': f't{transform_id}',
            'type': 'where',
            'condition': _expression_to_json(where.this)
        })
        transform_id += 1

    # Extract JOINs
    if joins := ast.args.get('joins'):
        for join in joins:
            join_kind = join.args.get('kind', '').lower() or 'inner'
            table = join.this
            table_name = table.name if hasattr(table, 'name') else str(table)

            condition = None
            if on_clause := join.args.get('on'):
                condition = _expression_to_json(on_clause)

            query['transforms'].append({
                'id': f't{transform_id}',
                'type': 'join',
                'join_type': join_kind,
                'table': table_name,
                'condition': condition
            })
            transform_id += 1

    # Extract SELECT (only if not SELECT *)
    if selections := ast.args.get('expressions'):
        # Check if it's SELECT *
        if not (len(selections) == 1 and isinstance(selections[0], exp.Star)):
            columns = []
            for sel in selections:
                if isinstance(sel, exp.Alias):
                    columns.append({
                        'name': sel.alias,
                        'expression': sel.this.name if hasattr(sel.this, 'name') else str(sel.this)
                    })
                elif hasattr(sel, 'name'):
                    columns.append({'name': sel.name})
                else:
                    columns.append({'name': str(sel)})

            query['transforms'].append({
                'id': f't{transform_id}',
                'type': 'select',
                'columns': columns
            })
            transform_id += 1

    # Extract GROUP BY
    if group_by := ast.args.get('group'):
        dimensions = []
        for expr in group_by.expressions:
            if hasattr(expr, 'name'):
                dimensions.append(expr.name)
            else:
                dimensions.append(str(expr))

        # Extract aggregates from SELECT when in GROUP BY context
        aggregates = []
        if selections := ast.args.get('expressions'):
            for sel in selections:
                if isinstance(sel, exp.Alias) and isinstance(sel.this, exp.AggFunc):
                    func_name = sel.this.__class__.__name__.lower()
                    # Get the column being aggregated
                    if sel.this.this and hasattr(sel.this.this, 'name'):
                        column = sel.this.this.name
                    else:
                        column = str(sel.this.this) if sel.this.this else '*'

                    aggregates.append({
                        'function': func_name,
                        'column': column,
                        'alias': sel.alias
                    })

        query['transforms'].append({
            'id': f't{transform_id}',
            'type': 'group_by',
            'dimensions': dimensions,
            'aggregates': aggregates
        })
        transform_id += 1

    # Extract ORDER BY
    if order_by := ast.args.get('order'):
        expressions = []
        for ordered in order_by.expressions:
            column = ordered.this
            column_name = column.name if hasattr(column, 'name') else str(column)
            direction = 'desc' if ordered.args.get('desc') else 'asc'

            expressions.append({
                'column': column_name,
                'direction': direction
            })

        query['transforms'].append({
            'id': f't{transform_id}',
            'type': 'order_by',
            'expressions': expressions
        })
        transform_id += 1

    # Extract LIMIT
    if limit := ast.args.get('limit'):
        count = 10
        if limit.this:
            try:
                count = int(limit.this.this) if hasattr(limit.this, 'this') else int(limit.this)
            except (ValueError, AttributeError):
                count = 10

        query['transforms'].append({
            'id': f't{transform_id}',
            'type': 'limit',
            'count': count
        })
        transform_id += 1

    return query


def _expression_to_json(expr: exp.Expression) -> Dict[str, Any]:
    """Convert SQLGlot expression to JSON representation."""
    if isinstance(expr, exp.Column):
        return {
            'type': 'column',
            'name': expr.name
        }

    elif isinstance(expr, exp.Literal):
        value = expr.this
        # Determine data type
        if isinstance(value, str):
            data_type = 'string'
        elif isinstance(value, (int, float)):
            data_type = 'number'
        elif isinstance(value, bool):
            data_type = 'boolean'
        else:
            data_type = 'string'

        return {
            'type': 'literal',
            'value': value,
            'data_type': data_type
        }

    elif isinstance(expr, exp.EQ):
        return {
            'type': 'binary_op',
            'operator': '=',
            'left': _expression_to_json(expr.this),
            'right': _expression_to_json(expr.expression)
        }

    elif isinstance(expr, exp.NEQ):
        return {
            'type': 'binary_op',
            'operator': '!=',
            'left': _expression_to_json(expr.this),
            'right': _expression_to_json(expr.expression)
        }

    elif isinstance(expr, exp.LT):
        return {
            'type': 'binary_op',
            'operator': '<',
            'left': _expression_to_json(expr.this),
            'right': _expression_to_json(expr.expression)
        }

    elif isinstance(expr, exp.GT):
        return {
            'type': 'binary_op',
            'operator': '>',
            'left': _expression_to_json(expr.this),
            'right': _expression_to_json(expr.expression)
        }

    elif isinstance(expr, exp.LTE):
        return {
            'type': 'binary_op',
            'operator': '<=',
            'left': _expression_to_json(expr.this),
            'right': _expression_to_json(expr.expression)
        }

    elif isinstance(expr, exp.GTE):
        return {
            'type': 'binary_op',
            'operator': '>=',
            'left': _expression_to_json(expr.this),
            'right': _expression_to_json(expr.expression)
        }

    elif isinstance(expr, exp.And):
        return {
            'type': 'binary_op',
            'operator': 'and',
            'left': _expression_to_json(expr.this),
            'right': _expression_to_json(expr.expression)
        }

    elif isinstance(expr, exp.Or):
        return {
            'type': 'binary_op',
            'operator': 'or',
            'left': _expression_to_json(expr.this),
            'right': _expression_to_json(expr.expression)
        }

    else:
        # Fallback for unsupported expressions
        return {
            'type': 'unknown',
            'value': str(expr)
        }


def json_to_asql(query_json: Dict[str, Any]) -> str:
    """
    Convert JSON representation to ASQL text.

    Args:
        query_json: Dict with 'from' and 'transforms' keys

    Returns:
        ASQL query as string
    """
    lines = []

    # FROM clause
    from_clause = query_json.get('from', {})
    table = from_clause.get('table', '')
    if not table:
        return "from # Enter table name"

    lines.append(f"from {table}")

    # Process transforms
    for transform in query_json.get('transforms', []):
        transform_type = transform.get('type')

        if transform_type == 'where':
            condition = transform.get('condition', {})
            condition_asql = _expression_to_asql(condition)
            if condition_asql:
                lines.append(f"  where {condition_asql}")

        elif transform_type == 'join':
            join_type = transform.get('join_type', 'inner')
            table = transform.get('table', '')
            condition = transform.get('condition')

            # Map join type to ASQL symbol
            join_symbol = {
                'inner': '&',
                'left': '&?',
                'right': '?&',
                'full': '?&?',
                'cross': '*'
            }.get(join_type, '&')

            if condition:
                condition_asql = _expression_to_asql(condition)
                lines.append(f"  {join_symbol} {table} on {condition_asql}")
            else:
                lines.append(f"  {join_symbol} {table}")

        elif transform_type == 'select':
            columns = transform.get('columns', [])
            if columns:
                column_strs = []
                for col in columns:
                    if isinstance(col, dict):
                        if 'expression' in col:
                            column_strs.append(f"{col['expression']} as {col['name']}")
                        else:
                            column_strs.append(col.get('name', ''))
                    else:
                        column_strs.append(str(col))

                lines.append(f"  select {', '.join(column_strs)}")

        elif transform_type == 'group_by':
            dimensions = transform.get('dimensions', [])
            aggregates = transform.get('aggregates', [])

            if dimensions:
                dims_str = ', '.join(dimensions)

                if aggregates:
                    # Use ASQL's inline aggregate syntax
                    agg_strs = []
                    for agg in aggregates:
                        func = agg.get('function', 'count')
                        col = agg.get('column', '*')
                        alias = agg.get('alias', f'{func}_{col}')
                        agg_strs.append(f"{func}({col}) as {alias}")

                    aggs_str = ',\n    '.join(agg_strs)
                    lines.append(f"  group by {dims_str} (")
                    lines.append(f"    {aggs_str}")
                    lines.append("  )")
                else:
                    lines.append(f"  group by {dims_str}")

        elif transform_type == 'order_by':
            expressions = transform.get('expressions', [])
            if expressions:
                order_parts = []
                for expr in expressions:
                    col = expr.get('column', '')
                    direction = expr.get('direction', 'asc')
                    # Use ASQL's - prefix for descending
                    if direction == 'desc':
                        order_parts.append(f"-{col}")
                    else:
                        order_parts.append(col)

                lines.append(f"  order by {', '.join(order_parts)}")

        elif transform_type == 'limit':
            count = transform.get('count', 10)
            lines.append(f"  limit {count}")

    return '\n'.join(lines)


def _expression_to_asql(expr: Dict[str, Any]) -> str:
    """Convert JSON expression to ASQL text."""
    expr_type = expr.get('type')

    if expr_type == 'column':
        return expr.get('name', '')

    elif expr_type == 'literal':
        value = expr.get('value', '')
        data_type = expr.get('data_type', 'string')

        if data_type == 'string':
            # Use double quotes for ASQL strings
            return f'"{value}"'
        elif data_type == 'number':
            return str(value)
        elif data_type == 'boolean':
            return str(value).lower()
        else:
            return f'"{value}"'

    elif expr_type == 'binary_op':
        left = _expression_to_asql(expr.get('left', {}))
        right = _expression_to_asql(expr.get('right', {}))
        operator = expr.get('operator', '=')

        # Convert SQL = to ASQL ==
        if operator == '=':
            operator = '=='

        # Handle AND/OR
        if operator in ('and', 'or'):
            return f"({left} {operator} {right})"

        return f"{left} {operator} {right}"

    elif expr_type == 'unknown':
        return expr.get('value', '')

    else:
        return ''
