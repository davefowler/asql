"""
Tests for asql/json_schema.py

Comprehensive tests for the bidirectional conversion between SQLGlot AST
and JSON representation used by the visual editor.
"""

from sqlglot import exp, parse_one

from asql.json_schema import ast_to_json, json_to_asql, _expression_to_json, _expression_to_asql
from asql.compiler import compile_to_ast


class TestAstToJson:
    """Tests for converting SQLGlot AST to JSON representation."""

    def test_simple_from_clause(self):
        """Test extracting FROM clause from a simple query."""
        ast = parse_one("SELECT * FROM users")
        result = ast_to_json(ast)

        assert result['from']['table'] == 'users'
        assert result['transforms'] == []

    def test_from_with_alias(self):
        """Test FROM clause with table alias."""
        ast = parse_one("SELECT * FROM users u")
        result = ast_to_json(ast)

        assert result['from']['table'] == 'users'

    def test_where_clause(self):
        """Test extracting WHERE clause."""
        ast = parse_one("SELECT * FROM users WHERE status = 'active'")
        result = ast_to_json(ast)

        assert len(result['transforms']) == 1
        transform = result['transforms'][0]
        assert transform['type'] == 'where'
        assert transform['id'] == 't0'
        assert transform['condition']['type'] == 'binary_op'
        assert transform['condition']['operator'] == '='

    def test_where_with_multiple_conditions(self):
        """Test WHERE clause with AND conditions."""
        ast = parse_one("SELECT * FROM users WHERE status = 'active' AND age > 18")
        result = ast_to_json(ast)

        condition = result['transforms'][0]['condition']
        assert condition['type'] == 'binary_op'
        assert condition['operator'] == 'and'
        assert condition['left']['type'] == 'binary_op'
        assert condition['right']['type'] == 'binary_op'

    def test_join_clause(self):
        """Test extracting JOIN clause."""
        ast = parse_one("SELECT * FROM users JOIN orders ON users.id = orders.user_id")
        result = ast_to_json(ast)

        # Find the join transform
        join_transforms = [t for t in result['transforms'] if t['type'] == 'join']
        assert len(join_transforms) == 1

        join = join_transforms[0]
        assert join['join_type'] == 'inner'
        assert join['table'] == 'orders'
        assert join['condition'] is not None
        assert join['condition']['type'] == 'binary_op'

    def test_left_join(self):
        """Test LEFT JOIN extraction."""
        ast = parse_one("SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id")
        result = ast_to_json(ast)

        join_transforms = [t for t in result['transforms'] if t['type'] == 'join']
        assert join_transforms[0]['join_type'] == 'left'

    def test_select_columns(self):
        """Test SELECT column extraction."""
        ast = parse_one("SELECT id, name, email FROM users")
        result = ast_to_json(ast)

        select_transforms = [t for t in result['transforms'] if t['type'] == 'select']
        assert len(select_transforms) == 1

        columns = select_transforms[0]['columns']
        assert len(columns) == 3
        assert columns[0]['name'] == 'id'
        assert columns[1]['name'] == 'name'
        assert columns[2]['name'] == 'email'

    def test_select_star_not_extracted(self):
        """Test that SELECT * does not create a select transform."""
        ast = parse_one("SELECT * FROM users")
        result = ast_to_json(ast)

        select_transforms = [t for t in result['transforms'] if t['type'] == 'select']
        assert len(select_transforms) == 0

    def test_select_with_alias(self):
        """Test SELECT with column aliases."""
        ast = parse_one("SELECT id, first_name as name FROM users")
        result = ast_to_json(ast)

        select_transforms = [t for t in result['transforms'] if t['type'] == 'select']
        columns = select_transforms[0]['columns']

        # Check aliased column
        aliased_col = next((c for c in columns if c.get('name') == 'name'), None)
        assert aliased_col is not None
        assert aliased_col.get('expression') == 'first_name'

    def test_group_by(self):
        """Test GROUP BY extraction."""
        ast = parse_one("SELECT status, COUNT(*) as cnt FROM users GROUP BY status")
        result = ast_to_json(ast)

        group_transforms = [t for t in result['transforms'] if t['type'] == 'group_by']
        assert len(group_transforms) == 1

        group = group_transforms[0]
        assert 'status' in group['dimensions']

    def test_group_by_with_aggregates(self):
        """Test GROUP BY with aggregate functions."""
        ast = parse_one("SELECT status, COUNT(*) as cnt, SUM(amount) as total FROM users GROUP BY status")
        result = ast_to_json(ast)

        group_transforms = [t for t in result['transforms'] if t['type'] == 'group_by']
        group = group_transforms[0]

        # Should have aggregates
        assert len(group['aggregates']) >= 1

    def test_order_by(self):
        """Test ORDER BY extraction."""
        ast = parse_one("SELECT * FROM users ORDER BY created_at DESC")
        result = ast_to_json(ast)

        order_transforms = [t for t in result['transforms'] if t['type'] == 'order_by']
        assert len(order_transforms) == 1

        order = order_transforms[0]
        assert len(order['expressions']) == 1
        assert order['expressions'][0]['column'] == 'created_at'
        assert order['expressions'][0]['direction'] == 'desc'

    def test_order_by_asc(self):
        """Test ORDER BY ASC (default)."""
        ast = parse_one("SELECT * FROM users ORDER BY name ASC")
        result = ast_to_json(ast)

        order_transforms = [t for t in result['transforms'] if t['type'] == 'order_by']
        assert order_transforms[0]['expressions'][0]['direction'] == 'asc'

    def test_limit(self):
        """Test LIMIT extraction."""
        ast = parse_one("SELECT * FROM users LIMIT 25")
        result = ast_to_json(ast)

        limit_transforms = [t for t in result['transforms'] if t['type'] == 'limit']
        assert len(limit_transforms) == 1
        assert limit_transforms[0]['count'] == 25

    def test_complex_query(self):
        """Test a complex query with multiple clauses."""
        ast = parse_one("""
            SELECT id, name, COUNT(*) as order_count
            FROM users
            LEFT JOIN orders ON users.id = orders.user_id
            WHERE status = 'active'
            GROUP BY id, name
            ORDER BY order_count DESC
            LIMIT 10
        """)
        result = ast_to_json(ast)

        assert result['from']['table'] == 'users'

        transform_types = [t['type'] for t in result['transforms']]
        assert 'where' in transform_types
        assert 'join' in transform_types
        assert 'group_by' in transform_types
        assert 'order_by' in transform_types
        assert 'limit' in transform_types

    def test_transform_ids_are_sequential(self):
        """Test that transform IDs are assigned sequentially."""
        ast = parse_one("SELECT * FROM users WHERE x = 1 ORDER BY y LIMIT 10")
        result = ast_to_json(ast)

        ids = [t['id'] for t in result['transforms']]
        expected_ids = [f't{i}' for i in range(len(ids))]
        assert ids == expected_ids


class TestExpressionToJson:
    """Tests for _expression_to_json helper function."""

    def test_column_expression(self):
        """Test converting a column reference."""
        expr = exp.Column(this=exp.Identifier(this='name'))
        result = _expression_to_json(expr)

        assert result['type'] == 'column'
        assert result['name'] == 'name'

    def test_string_literal(self):
        """Test converting a string literal."""
        expr = exp.Literal.string('hello')
        result = _expression_to_json(expr)

        assert result['type'] == 'literal'
        assert result['value'] == 'hello'
        assert result['data_type'] == 'string'

    def test_number_literal_integer(self):
        """Test converting an integer literal."""
        expr = exp.Literal.number(42)
        result = _expression_to_json(expr)

        assert result['type'] == 'literal'
        assert result['value'] == 42
        assert result['data_type'] == 'number'

    def test_number_literal_float(self):
        """Test converting a float literal."""
        expr = exp.Literal.number(3.14)
        result = _expression_to_json(expr)

        assert result['type'] == 'literal'
        assert result['value'] == 3.14
        assert result['data_type'] == 'number'

    def test_equality_operator(self):
        """Test converting equality comparison."""
        left = exp.Column(this=exp.Identifier(this='status'))
        right = exp.Literal.string('active')
        expr = exp.EQ(this=left, expression=right)
        result = _expression_to_json(expr)

        assert result['type'] == 'binary_op'
        assert result['operator'] == '='
        assert result['left']['type'] == 'column'
        assert result['right']['type'] == 'literal'

    def test_all_comparison_operators(self):
        """Test all comparison operators."""
        operators = [
            (exp.EQ, '='),
            (exp.NEQ, '!='),
            (exp.LT, '<'),
            (exp.GT, '>'),
            (exp.LTE, '<='),
            (exp.GTE, '>='),
        ]

        for exp_class, expected_op in operators:
            left = exp.Column(this=exp.Identifier(this='x'))
            right = exp.Literal.number(1)
            expr = exp_class(this=left, expression=right)
            result = _expression_to_json(expr)

            assert result['operator'] == expected_op, f"Failed for {exp_class.__name__}"

    def test_and_operator(self):
        """Test AND logical operator."""
        left = exp.EQ(
            this=exp.Column(this=exp.Identifier(this='a')),
            expression=exp.Literal.number(1)
        )
        right = exp.EQ(
            this=exp.Column(this=exp.Identifier(this='b')),
            expression=exp.Literal.number(2)
        )
        expr = exp.And(this=left, expression=right)
        result = _expression_to_json(expr)

        assert result['type'] == 'binary_op'
        assert result['operator'] == 'and'

    def test_or_operator(self):
        """Test OR logical operator."""
        left = exp.EQ(
            this=exp.Column(this=exp.Identifier(this='a')),
            expression=exp.Literal.number(1)
        )
        right = exp.EQ(
            this=exp.Column(this=exp.Identifier(this='b')),
            expression=exp.Literal.number(2)
        )
        expr = exp.Or(this=left, expression=right)
        result = _expression_to_json(expr)

        assert result['type'] == 'binary_op'
        assert result['operator'] == 'or'

    def test_unknown_expression_fallback(self):
        """Test fallback for unsupported expressions."""
        # Create an expression type not explicitly handled
        expr = exp.Paren(this=exp.Column(this=exp.Identifier(this='x')))
        result = _expression_to_json(expr)

        assert result['type'] == 'unknown'
        assert 'value' in result


class TestJsonToAsql:
    """Tests for converting JSON representation to ASQL text."""

    def test_simple_from(self):
        """Test simple FROM clause generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': []
        }
        result = json_to_asql(query_json)

        assert result == 'from users'

    def test_empty_table_placeholder(self):
        """Test placeholder for empty table name."""
        query_json = {
            'from': {'table': ''},
            'transforms': []
        }
        result = json_to_asql(query_json)

        assert '# Enter table name' in result

    def test_where_transform(self):
        """Test WHERE transform generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'where',
                'condition': {
                    'type': 'binary_op',
                    'operator': '=',
                    'left': {'type': 'column', 'name': 'status'},
                    'right': {'type': 'literal', 'value': 'active', 'data_type': 'string'}
                }
            }]
        }
        result = json_to_asql(query_json)

        assert 'from users' in result
        assert 'where' in result
        assert 'status' in result
        assert '==' in result  # ASQL uses == for equality

    def test_join_transform(self):
        """Test JOIN transform generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'join',
                'join_type': 'inner',
                'table': 'orders',
                'condition': {
                    'type': 'binary_op',
                    'operator': '=',
                    'left': {'type': 'column', 'name': 'id'},
                    'right': {'type': 'column', 'name': 'user_id'}
                }
            }]
        }
        result = json_to_asql(query_json)

        assert '& orders' in result
        assert 'on' in result

    def test_left_join_symbol(self):
        """Test left join uses correct ASQL symbol."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'join',
                'join_type': 'left',
                'table': 'orders',
                'condition': None
            }]
        }
        result = json_to_asql(query_json)

        assert '&? orders' in result

    def test_all_join_types(self):
        """Test all join type symbols."""
        join_types = {
            'inner': '&',
            'left': '&?',
            'right': '?&',
            'full': '?&?',
            'cross': '*'
        }

        for join_type, symbol in join_types.items():
            query_json = {
                'from': {'table': 'a'},
                'transforms': [{
                    'id': 't0',
                    'type': 'join',
                    'join_type': join_type,
                    'table': 'b',
                    'condition': None
                }]
            }
            result = json_to_asql(query_json)
            assert f'{symbol} b' in result, f"Failed for {join_type}"

    def test_select_transform(self):
        """Test SELECT transform generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'select',
                'columns': [
                    {'name': 'id'},
                    {'name': 'name'},
                    {'name': 'email'}
                ]
            }]
        }
        result = json_to_asql(query_json)

        assert 'select id, name, email' in result

    def test_select_with_alias(self):
        """Test SELECT with column alias."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'select',
                'columns': [
                    {'name': 'full_name', 'expression': 'first_name'}
                ]
            }]
        }
        result = json_to_asql(query_json)

        assert 'first_name as full_name' in result

    def test_group_by_transform(self):
        """Test GROUP BY transform generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'group_by',
                'dimensions': ['status', 'country'],
                'aggregates': []
            }]
        }
        result = json_to_asql(query_json)

        assert 'group by status, country' in result

    def test_group_by_with_aggregates(self):
        """Test GROUP BY with aggregate functions."""
        query_json = {
            'from': {'table': 'orders'},
            'transforms': [{
                'id': 't0',
                'type': 'group_by',
                'dimensions': ['status'],
                'aggregates': [{
                    'function': 'count',
                    'column': '*',
                    'alias': 'cnt'
                }, {
                    'function': 'sum',
                    'column': 'amount',
                    'alias': 'total'
                }]
            }]
        }
        result = json_to_asql(query_json)

        assert 'group by status' in result
        assert 'count(*)' in result
        assert 'sum(amount)' in result

    def test_order_by_transform(self):
        """Test ORDER BY transform generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'order_by',
                'expressions': [
                    {'column': 'created_at', 'direction': 'desc'},
                    {'column': 'name', 'direction': 'asc'}
                ]
            }]
        }
        result = json_to_asql(query_json)

        # ASQL uses - prefix for descending
        assert 'order by -created_at, name' in result

    def test_limit_transform(self):
        """Test LIMIT transform generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'limit',
                'count': 25
            }]
        }
        result = json_to_asql(query_json)

        assert 'limit 25' in result

    def test_multiple_transforms(self):
        """Test query with multiple transforms."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [
                {'id': 't0', 'type': 'where', 'condition': {
                    'type': 'binary_op', 'operator': '=',
                    'left': {'type': 'column', 'name': 'active'},
                    'right': {'type': 'literal', 'value': True, 'data_type': 'boolean'}
                }},
                {'id': 't1', 'type': 'order_by', 'expressions': [
                    {'column': 'name', 'direction': 'asc'}
                ]},
                {'id': 't2', 'type': 'limit', 'count': 10}
            ]
        }
        result = json_to_asql(query_json)

        lines = result.split('\n')
        assert len(lines) >= 4


class TestExpressionToAsql:
    """Tests for _expression_to_asql helper function."""

    def test_column_expression(self):
        """Test converting column to ASQL."""
        expr = {'type': 'column', 'name': 'status'}
        result = _expression_to_asql(expr)

        assert result == 'status'

    def test_string_literal(self):
        """Test converting string literal to ASQL."""
        expr = {'type': 'literal', 'value': 'hello', 'data_type': 'string'}
        result = _expression_to_asql(expr)

        assert result == '"hello"'

    def test_number_literal(self):
        """Test converting number literal to ASQL."""
        expr = {'type': 'literal', 'value': 42, 'data_type': 'number'}
        result = _expression_to_asql(expr)

        assert result == '42'

    def test_boolean_literal(self):
        """Test converting boolean literal to ASQL."""
        expr = {'type': 'literal', 'value': True, 'data_type': 'boolean'}
        result = _expression_to_asql(expr)

        assert result == 'true'

    def test_binary_op_equality(self):
        """Test converting equality to ASQL (= becomes ==)."""
        expr = {
            'type': 'binary_op',
            'operator': '=',
            'left': {'type': 'column', 'name': 'x'},
            'right': {'type': 'literal', 'value': 1, 'data_type': 'number'}
        }
        result = _expression_to_asql(expr)

        assert result == 'x == 1'

    def test_binary_op_comparison(self):
        """Test converting comparison operators."""
        expr = {
            'type': 'binary_op',
            'operator': '>',
            'left': {'type': 'column', 'name': 'age'},
            'right': {'type': 'literal', 'value': 18, 'data_type': 'number'}
        }
        result = _expression_to_asql(expr)

        assert result == 'age > 18'

    def test_and_operator(self):
        """Test converting AND operator."""
        expr = {
            'type': 'binary_op',
            'operator': 'and',
            'left': {'type': 'column', 'name': 'a'},
            'right': {'type': 'column', 'name': 'b'}
        }
        result = _expression_to_asql(expr)

        assert result == '(a and b)'

    def test_or_operator(self):
        """Test converting OR operator."""
        expr = {
            'type': 'binary_op',
            'operator': 'or',
            'left': {'type': 'column', 'name': 'a'},
            'right': {'type': 'column', 'name': 'b'}
        }
        result = _expression_to_asql(expr)

        assert result == '(a or b)'

    def test_unknown_expression(self):
        """Test converting unknown expression type."""
        expr = {'type': 'unknown', 'value': 'CUSTOM()'}
        result = _expression_to_asql(expr)

        assert result == 'CUSTOM()'

    def test_empty_expression(self):
        """Test converting empty/missing expression type."""
        expr = {}
        result = _expression_to_asql(expr)

        assert result == ''


class TestStringEscaping:
    """Tests for string escaping to prevent injection."""

    def test_escapes_double_quotes(self):
        """Test that double quotes are escaped."""
        expr = {'type': 'literal', 'value': 'hello "world"', 'data_type': 'string'}
        result = _expression_to_asql(expr)

        assert result == '"hello \\"world\\""'

    def test_escapes_backslashes(self):
        """Test that backslashes are escaped."""
        expr = {'type': 'literal', 'value': 'path\\to\\file', 'data_type': 'string'}
        result = _expression_to_asql(expr)

        assert result == '"path\\\\to\\\\file"'

    def test_escapes_combined(self):
        """Test escaping quotes and backslashes together."""
        expr = {'type': 'literal', 'value': 'say \\"hi\\"', 'data_type': 'string'}
        result = _expression_to_asql(expr)

        # Should double-escape backslashes and escape quotes
        assert '\\"' in result or '\\\\' in result

    def test_fallback_escaping(self):
        """Test that fallback case also escapes properly."""
        # Test with an unknown data_type to trigger fallback
        expr = {'type': 'literal', 'value': 'test "value"', 'data_type': 'unknown_type'}
        result = _expression_to_asql(expr)

        # Should still be wrapped in quotes and escaped
        assert '\\"' in result


class TestRoundTrip:
    """Tests for round-trip conversion: ASQL -> JSON -> ASQL."""

    def test_simple_query_roundtrip(self):
        """Test simple query round-trip."""
        original_asql = "from users"

        # Parse ASQL to AST, convert to JSON
        ast = compile_to_ast(original_asql)
        json_rep = ast_to_json(ast)

        # Convert JSON back to ASQL
        result_asql = json_to_asql(json_rep)

        assert 'from users' in result_asql

    def test_where_roundtrip(self):
        """Test WHERE clause round-trip."""
        original_asql = '''from users
  where status == "active"'''

        ast = compile_to_ast(original_asql)
        json_rep = ast_to_json(ast)
        result_asql = json_to_asql(json_rep)

        assert 'from users' in result_asql
        assert 'where' in result_asql
        assert 'status' in result_asql

    def test_limit_roundtrip(self):
        """Test LIMIT round-trip."""
        original_asql = '''from users
  limit 50'''

        ast = compile_to_ast(original_asql)
        json_rep = ast_to_json(ast)
        result_asql = json_to_asql(json_rep)

        assert 'limit 50' in result_asql

    def test_order_by_roundtrip(self):
        """Test ORDER BY round-trip."""
        original_asql = '''from users
  order by -created_at'''

        ast = compile_to_ast(original_asql)
        json_rep = ast_to_json(ast)
        result_asql = json_to_asql(json_rep)

        assert 'order by' in result_asql
        assert '-created_at' in result_asql


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_transforms(self):
        """Test query with no transforms."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': []
        }
        result = json_to_asql(query_json)

        assert result == 'from users'

    def test_missing_from_clause(self):
        """Test handling missing FROM clause."""
        query_json = {
            'from': {},
            'transforms': []
        }
        result = json_to_asql(query_json)

        assert '# Enter table name' in result

    def test_none_condition(self):
        """Test join without condition."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'join',
                'join_type': 'cross',
                'table': 'products',
                'condition': None
            }]
        }
        result = json_to_asql(query_json)

        assert '* products' in result
        assert 'on' not in result

    def test_empty_columns_list(self):
        """Test SELECT with empty columns list."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'select',
                'columns': []
            }]
        }
        result = json_to_asql(query_json)

        # Should not add select line for empty columns
        assert 'select' not in result or 'select ' not in result

    def test_empty_order_expressions(self):
        """Test ORDER BY with empty expressions."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'order_by',
                'expressions': []
            }]
        }
        result = json_to_asql(query_json)

        # Should not add order by line for empty expressions
        assert 'order by' not in result
