"""
Tests for asql/json_schema.py

Tests for json_to_asql and related functions.
For AST to JSON conversion, see tests/test_visual_dialect.py which tests
the visual_asql dialect.
"""

import json
import sqlglot

from asql.json_schema import json_to_asql, _expression_to_asql, validate_pipelines


class TestJsonToAsql:
    """Tests for converting JSON representation to ASQL text."""

    def test_simple_from_clause(self):
        """Test simple FROM clause generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': []
        }
        result = json_to_asql(query_json)

        assert result == 'from users'

    def test_where_clause(self):
        """Test WHERE clause generation."""
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
        assert 'where status ==' in result
        assert '"active"' in result

    def test_having_clause(self):
        """Test HAVING clause generation."""
        query_json = {
            'from': {'table': 'orders'},
            'transforms': [{
                'type': 'having',
                'condition': {
                    'type': 'binary_op',
                    'operator': '>',
                    'left': {'type': 'function', 'name': 'SUM', 'args': [{'type': 'column', 'name': 'amount'}]},
                    'right': {'type': 'literal', 'value': 1000, 'data_type': 'number'}
                }
            }]
        }
        result = json_to_asql(query_json)
        assert 'having' in result

    def test_qualify_clause(self):
        """Test QUALIFY clause generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'type': 'qualify',
                'condition': {
                    'type': 'binary_op',
                    'operator': '=',
                    'left': {'type': 'function', 'name': 'ROW_NUMBER', 'args': []},
                    'right': {'type': 'literal', 'value': 1, 'data_type': 'number'}
                }
            }]
        }
        result = json_to_asql(query_json)
        assert 'qualify' in result

    def test_join_clause(self):
        """Test JOIN clause generation."""
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

        assert 'from users' in result
        assert '& orders on' in result

    def test_join_types(self):
        """Test different join type symbols."""
        join_types = [
            ('inner', '&'),
            ('left', '&?'),
            ('right', '?&'),
            ('full', '?&?'),
            ('cross', '*'),
        ]

        for join_type, expected_symbol in join_types:
            query_json = {
                'from': {'table': 'users'},
                'transforms': [{
                    'id': 't0',
                    'type': 'join',
                    'join_type': join_type,
                    'table': 'orders',
                    'condition': None if join_type == 'cross' else {
                        'type': 'binary_op',
                        'operator': '=',
                        'left': {'type': 'column', 'name': 'id'},
                        'right': {'type': 'column', 'name': 'user_id'}
                    }
                }]
            }
            result = json_to_asql(query_json)
            assert f'{expected_symbol} orders' in result, f"Failed for join type {join_type}"

    def test_select_clause(self):
        """Test SELECT clause generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'select',
                'columns': [
                    {'name': 'name'},
                    {'name': 'email'}
                ]
            }]
        }
        result = json_to_asql(query_json)

        assert 'select name, email' in result

    def test_select_with_expressions(self):
        """Test SELECT with expressions/aliases."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'select',
                'columns': [
                    {'name': 'name'},
                    {'name': 'total_amount', 'expression': 'SUM(amount)'}
                ]
            }]
        }
        result = json_to_asql(query_json)

        assert 'SUM(amount) as total_amount' in result

    def test_except_clause(self):
        """Test EXCEPT clause generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'type': 'except',
                'columns': [{'name': 'password'}, {'name': 'internal_id'}]
            }]
        }
        result = json_to_asql(query_json)
        assert 'except password, internal_id' in result

    def test_group_by_clause(self):
        """Test GROUP BY clause generation."""
        query_json = {
            'from': {'table': 'orders'},
            'transforms': [{
                'id': 't0',
                'type': 'group_by',
                'dimensions': ['region', 'category'],
                'aggregates': []
            }]
        }
        result = json_to_asql(query_json)

        assert 'group by region, category' in result

    def test_group_by_with_aggregates(self):
        """Test GROUP BY with aggregates."""
        query_json = {
            'from': {'table': 'orders'},
            'transforms': [{
                'id': 't0',
                'type': 'group_by',
                'dimensions': ['region'],
                'aggregates': [
                    {'function': 'sum', 'column': 'amount', 'alias': 'total'},
                    {'function': 'count', 'column': '*', 'alias': 'cnt'}
                ]
            }]
        }
        result = json_to_asql(query_json)

        assert 'group by region' in result
        assert 'sum(amount) as total' in result
        assert 'count(*) as cnt' in result

    def test_order_by_clause(self):
        """Test ORDER BY clause generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'order_by',
                'expressions': [
                    {'column': 'name', 'direction': 'asc'},
                    {'column': 'created_at', 'direction': 'desc'}
                ]
            }]
        }
        result = json_to_asql(query_json)

        assert 'order by name, -created_at' in result

    def test_limit_clause(self):
        """Test LIMIT clause generation."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'limit',
                'count': 100
            }]
        }
        result = json_to_asql(query_json)

        assert 'limit 100' in result

    def test_distinct_transform(self):
        """Test DISTINCT transform."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{'type': 'distinct'}]
        }
        result = json_to_asql(query_json)
        assert 'distinct' in result

    def test_sample_transform(self):
        """Test SAMPLE transform."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{'type': 'sample', 'size': 1000}]
        }
        result = json_to_asql(query_json)
        assert 'sample 1000' in result

    def test_stash_transform(self):
        """Test STASH transform."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{'type': 'stash', 'name': 'active_users'}]
        }
        result = json_to_asql(query_json)
        assert 'stash as active_users' in result

    def test_deduplicate_transform(self):
        """Test DEDUPLICATE transform."""
        query_json = {
            'from': {'table': 'events'},
            'transforms': [{'type': 'deduplicate', 'columns': ['user_id', 'event_type']}]
        }
        result = json_to_asql(query_json)
        assert 'deduplicate user_id, event_type' in result

    def test_deduplicate_without_columns(self):
        """Test DEDUPLICATE without columns."""
        query_json = {
            'from': {'table': 'events'},
            'transforms': [{'type': 'deduplicate'}]
        }
        result = json_to_asql(query_json)
        assert 'deduplicate' in result

    def test_extend_transform(self):
        """Test EXTEND transform."""
        query_json = {
            'from': {'table': 'orders'},
            'transforms': [{
                'type': 'extend',
                'columns': [
                    {'name': 'tax', 'expression': 'amount * 0.1'},
                    {'name': 'total', 'expression': 'amount * 1.1'}
                ]
            }]
        }
        result = json_to_asql(query_json)
        assert 'extend' in result
        assert 'amount * 0.1 as tax' in result
        assert 'amount * 1.1 as total' in result

    def test_rename_transform(self):
        """Test RENAME transform."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'type': 'rename',
                'mappings': [
                    {'from': 'user_name', 'to': 'name'},
                    {'from': 'user_email', 'to': 'email'}
                ]
            }]
        }
        result = json_to_asql(query_json)
        assert 'rename' in result
        assert 'user_name as name' in result
        assert 'user_email as email' in result

    def test_replace_transform(self):
        """Test REPLACE transform."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'type': 'replace',
                'columns': [
                    {'name': 'name', 'expression': 'UPPER(name)'}
                ]
            }]
        }
        result = json_to_asql(query_json)
        assert 'replace' in result
        assert 'UPPER(name) as name' in result

    def test_explode_transform(self):
        """Test EXPLODE transform."""
        query_json = {
            'from': {'table': 'orders'},
            'transforms': [{'type': 'explode', 'column': 'items'}]
        }
        result = json_to_asql(query_json)
        assert 'explode items' in result

    def test_per_transform(self):
        """Test PER transform."""
        query_json = {
            'from': {'table': 'sales'},
            'transforms': [{'type': 'per', 'columns': ['region', 'product']}]
        }
        result = json_to_asql(query_json)
        assert 'per region, product' in result

    def test_number_transform(self):
        """Test NUMBER transform."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{'type': 'number'}]
        }
        result = json_to_asql(query_json)
        assert 'number' in result

    def test_rank_transform(self):
        """Test RANK transform."""
        query_json = {
            'from': {'table': 'sales'},
            'transforms': [{'type': 'rank'}]
        }
        result = json_to_asql(query_json)
        assert 'rank' in result

    def test_dense_transform(self):
        """Test DENSE transform."""
        query_json = {
            'from': {'table': 'sales'},
            'transforms': [{'type': 'dense'}]
        }
        result = json_to_asql(query_json)
        assert 'dense' in result

    def test_cohort_transform(self):
        """Test COHORT transform."""
        query_json = {
            'from': {'table': 'events'},
            'transforms': [{
                'type': 'cohort',
                'entity': 'user_id',
                'cohort_date': 'signup_date',
                'event_date': 'event_date'
            }]
        }
        result = json_to_asql(query_json)
        assert 'cohort user_id by signup_date on event_date' in result

    def test_recurse_transform(self):
        """Test RECURSE transform."""
        query_json = {
            'from': {'table': 'employees'},
            'transforms': [{'type': 'recurse', 'max_depth': 10}]
        }
        result = json_to_asql(query_json)
        assert 'recurse 10' in result

    def test_recurse_without_depth(self):
        """Test RECURSE without max depth."""
        query_json = {
            'from': {'table': 'employees'},
            'transforms': [{'type': 'recurse'}]
        }
        result = json_to_asql(query_json)
        assert 'recurse' in result

    def test_multiple_transforms(self):
        """Test multiple transforms together."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [
                {
                    'id': 't0',
                    'type': 'where',
                    'condition': {
                        'type': 'binary_op',
                        'operator': '=',
                        'left': {'type': 'column', 'name': 'status'},
                        'right': {'type': 'literal', 'value': 'active', 'data_type': 'string'}
                    }
                },
                {
                    'id': 't1',
                    'type': 'order_by',
                    'expressions': [{'column': 'name', 'direction': 'asc'}]
                },
                {
                    'id': 't2',
                    'type': 'limit',
                    'count': 10
                }
            ]
        }
        result = json_to_asql(query_json)

        assert 'from users' in result
        assert 'where' in result
        assert 'order by' in result
        assert 'limit 10' in result


class TestExpressionToAsql:
    """Tests for converting JSON expressions to ASQL text."""

    def test_column_expression(self):
        """Test column reference."""
        expr = {'type': 'column', 'name': 'status'}
        result = _expression_to_asql(expr)

        assert result == 'status'

    def test_column_with_table(self):
        """Test column with table reference."""
        expr = {'type': 'column', 'name': 'status', 'table': 'users'}
        result = _expression_to_asql(expr)

        assert result == 'users.status'

    def test_string_literal(self):
        """Test string literal."""
        expr = {'type': 'literal', 'value': 'active', 'data_type': 'string'}
        result = _expression_to_asql(expr)

        assert result == '"active"'

    def test_number_literal(self):
        """Test number literal."""
        expr = {'type': 'literal', 'value': 42, 'data_type': 'number'}
        result = _expression_to_asql(expr)

        assert result == '42'

    def test_boolean_literal(self):
        """Test boolean literal."""
        expr = {'type': 'literal', 'value': True, 'data_type': 'boolean'}
        result = _expression_to_asql(expr)

        assert result == 'true'

    def test_null_literal(self):
        """Test null literal."""
        expr = {'type': 'literal', 'value': None, 'data_type': 'null'}
        result = _expression_to_asql(expr)
        assert result == 'null'

    def test_binary_equality(self):
        """Test binary equality operator."""
        expr = {
            'type': 'binary_op',
            'operator': '=',
            'left': {'type': 'column', 'name': 'status'},
            'right': {'type': 'literal', 'value': 'active', 'data_type': 'string'}
        }
        result = _expression_to_asql(expr)

        assert result == 'status == "active"'

    def test_comparison_operators(self):
        """Test various comparison operators."""
        operators = ['<', '>', '<=', '>=', '!=']

        for op in operators:
            expr = {
                'type': 'binary_op',
                'operator': op,
                'left': {'type': 'column', 'name': 'age'},
                'right': {'type': 'literal', 'value': 18, 'data_type': 'number'}
            }
            result = _expression_to_asql(expr)
            assert f'age {op} 18' in result

    def test_and_operator(self):
        """Test AND operator."""
        expr = {
            'type': 'binary_op',
            'operator': 'and',
            'left': {
                'type': 'binary_op',
                'operator': '=',
                'left': {'type': 'column', 'name': 'status'},
                'right': {'type': 'literal', 'value': 'active', 'data_type': 'string'}
            },
            'right': {
                'type': 'binary_op',
                'operator': '>',
                'left': {'type': 'column', 'name': 'age'},
                'right': {'type': 'literal', 'value': 18, 'data_type': 'number'}
            }
        }
        result = _expression_to_asql(expr)

        assert 'and' in result
        assert 'status ==' in result
        assert 'age > 18' in result

    def test_or_operator(self):
        """Test OR operator."""
        expr = {
            'type': 'binary_op',
            'operator': 'or',
            'left': {
                'type': 'binary_op',
                'operator': '=',
                'left': {'type': 'column', 'name': 'status'},
                'right': {'type': 'literal', 'value': 'active', 'data_type': 'string'}
            },
            'right': {
                'type': 'binary_op',
                'operator': '=',
                'left': {'type': 'column', 'name': 'status'},
                'right': {'type': 'literal', 'value': 'pending', 'data_type': 'string'}
            }
        }
        result = _expression_to_asql(expr)

        assert 'or' in result

    def test_not_operator(self):
        """Test NOT operator."""
        expr = {
            'type': 'unary_op',
            'operator': 'not',
            'operand': {
                'type': 'binary_op',
                'operator': '=',
                'left': {'type': 'column', 'name': 'status'},
                'right': {'type': 'literal', 'value': 'deleted', 'data_type': 'string'}
            }
        }
        result = _expression_to_asql(expr)
        assert 'not' in result

    def test_is_null(self):
        """Test IS NULL operator."""
        expr = {
            'type': 'null_check',
            'operator': 'is null',
            'operand': {'type': 'column', 'name': 'email'}
        }
        result = _expression_to_asql(expr)
        assert result == 'email == null'

    def test_is_not_null(self):
        """Test IS NOT NULL operator."""
        expr = {
            'type': 'null_check',
            'operator': 'is not null',
            'operand': {'type': 'column', 'name': 'email'}
        }
        result = _expression_to_asql(expr)
        assert result == 'email != null'

    def test_in_operator(self):
        """Test IN operator."""
        expr = {
            'type': 'in',
            'operand': {'type': 'column', 'name': 'status'},
            'values': [
                {'type': 'literal', 'value': 'active', 'data_type': 'string'},
                {'type': 'literal', 'value': 'pending', 'data_type': 'string'}
            ]
        }
        result = _expression_to_asql(expr)
        assert 'status in' in result
        assert '"active"' in result
        assert '"pending"' in result

    def test_not_in_operator(self):
        """Test NOT IN operator."""
        expr = {
            'type': 'not_in',
            'operand': {'type': 'column', 'name': 'status'},
            'values': [
                {'type': 'literal', 'value': 'deleted', 'data_type': 'string'}
            ]
        }
        result = _expression_to_asql(expr)
        assert 'status not in' in result

    def test_between_operator(self):
        """Test BETWEEN operator."""
        expr = {
            'type': 'between',
            'operand': {'type': 'column', 'name': 'age'},
            'low': {'type': 'literal', 'value': 18, 'data_type': 'number'},
            'high': {'type': 'literal', 'value': 65, 'data_type': 'number'}
        }
        result = _expression_to_asql(expr)
        assert 'age between 18 and 65' in result

    def test_like_operator(self):
        """Test LIKE operator (converts to matches)."""
        expr = {
            'type': 'like',
            'operand': {'type': 'column', 'name': 'name'},
            'pattern': {'type': 'literal', 'value': '%Smith%', 'data_type': 'string'}
        }
        result = _expression_to_asql(expr)
        assert 'name matches' in result

    def test_contains_operator(self):
        """Test CONTAINS operator."""
        expr = {
            'type': 'contains',
            'operand': {'type': 'column', 'name': 'description'},
            'value': {'type': 'literal', 'value': 'important', 'data_type': 'string'}
        }
        result = _expression_to_asql(expr)
        assert 'description contains "important"' in result

    def test_icontains_operator(self):
        """Test ICONTAINS operator."""
        expr = {
            'type': 'icontains',
            'operand': {'type': 'column', 'name': 'description'},
            'value': {'type': 'literal', 'value': 'important', 'data_type': 'string'}
        }
        result = _expression_to_asql(expr)
        assert 'description icontains "important"' in result

    def test_starts_with_operator(self):
        """Test STARTS WITH operator."""
        expr = {
            'type': 'starts_with',
            'operand': {'type': 'column', 'name': 'name'},
            'value': {'type': 'literal', 'value': 'Dr.', 'data_type': 'string'}
        }
        result = _expression_to_asql(expr)
        assert 'name starts with "Dr."' in result

    def test_ends_with_operator(self):
        """Test ENDS WITH operator."""
        expr = {
            'type': 'ends_with',
            'operand': {'type': 'column', 'name': 'email'},
            'value': {'type': 'literal', 'value': '@gmail.com', 'data_type': 'string'}
        }
        result = _expression_to_asql(expr)
        assert 'email ends with "@gmail.com"' in result

    def test_function_call(self):
        """Test function call expression."""
        expr = {
            'type': 'function',
            'name': 'UPPER',
            'args': [{'type': 'column', 'name': 'name'}]
        }
        result = _expression_to_asql(expr)
        assert result == 'UPPER(name)'

    def test_function_with_multiple_args(self):
        """Test function with multiple arguments."""
        expr = {
            'type': 'function',
            'name': 'CONCAT',
            'args': [
                {'type': 'column', 'name': 'first_name'},
                {'type': 'literal', 'value': ' ', 'data_type': 'string'},
                {'type': 'column', 'name': 'last_name'}
            ]
        }
        result = _expression_to_asql(expr)
        assert 'CONCAT(first_name, " ", last_name)' in result

    def test_unknown_expression(self):
        """Test fallback for unknown expression."""
        expr = {'type': 'unknown', 'value': 'some_expr'}
        result = _expression_to_asql(expr)

        assert result == 'some_expr'

    def test_empty_expression(self):
        """Test empty/missing type."""
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
    """Tests for round-trip conversion: ASQL -> JSON (via visual_asql) -> ASQL."""

    def test_simple_query_roundtrip(self):
        """Test simple query round-trip."""
        original_asql = "from users"

        # ASQL -> JSON using visual_asql dialect
        json_str = sqlglot.transpile(original_asql, read="asql", write="visual_asql")[0]
        json_rep = json.loads(json_str)

        # JSON -> ASQL
        result_asql = json_to_asql(json_rep)

        assert 'from users' in result_asql

    def test_where_roundtrip(self):
        """Test WHERE clause round-trip."""
        original_asql = 'from users where status == "active"'

        json_str = sqlglot.transpile(original_asql, read="asql", write="visual_asql")[0]
        json_rep = json.loads(json_str)
        result_asql = json_to_asql(json_rep)

        assert 'from users' in result_asql
        assert 'where' in result_asql
        assert 'status' in result_asql

    def test_limit_roundtrip(self):
        """Test LIMIT round-trip."""
        original_asql = 'from users limit 50'

        json_str = sqlglot.transpile(original_asql, read="asql", write="visual_asql")[0]
        json_rep = json.loads(json_str)
        result_asql = json_to_asql(json_rep)

        assert 'limit 50' in result_asql

    def test_order_by_roundtrip(self):
        """Test ORDER BY round-trip."""
        original_asql = 'from users order by -created_at'

        json_str = sqlglot.transpile(original_asql, read="asql", write="visual_asql")[0]
        json_rep = json.loads(json_str)
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


class TestArrayFormat:
    """Tests for the new array format (multiple pipelines, CTEs, set operations)."""

    def test_single_pipeline_array(self):
        """Test single pipeline in array format."""
        query_json = [
            {
                'name': None,
                'from': {'table': 'users'},
                'transforms': [{'type': 'limit', 'count': 10}]
            }
        ]
        result = json_to_asql(query_json)

        assert 'from users' in result
        assert 'limit 10' in result

    def test_multiple_unnamed_pipelines(self):
        """Test multiple unnamed pipelines (multiple queries)."""
        query_json = [
            {
                'name': None,
                'from': {'table': 'users'},
                'transforms': [{'type': 'limit', 'count': 10}]
            },
            {
                'name': None,
                'from': {'table': 'orders'},
                'transforms': [{'type': 'limit', 'count': 20}]
            }
        ]
        result = json_to_asql(query_json)

        assert 'from users' in result
        assert 'limit 10' in result
        assert 'from orders' in result
        assert 'limit 20' in result

    def test_named_pipeline_generates_stash(self):
        """Test named pipelines generate stash statements.
        
        When a subsequent pipeline references a CTE we just created,
        it continues the pipeline (no new FROM) instead of starting a new statement.
        This produces a single SQL statement with all CTEs in one WITH clause.
        """
        query_json = [
            {
                'name': 'active_users',
                'from': {'table': 'users'},
                'transforms': [
                    {'type': 'where', 'condition': {'type': 'binary_op', 'operator': '=', 'left': {'type': 'column', 'name': 'status'}, 'right': {'type': 'literal', 'value': 'active', 'data_type': 'string'}}}
                ]
            },
            {
                'name': None,
                'from': {'table': 'active_users'},
                'transforms': []
            }
        ]
        result = json_to_asql(query_json)

        assert 'from users' in result
        assert 'stash as active_users' in result
        # No separate 'from active_users' - pipeline continues after stash

    def test_union_set_operation(self):
        """Test UNION set operation between pipelines."""
        query_json = [
            {
                'name': None,
                'from': {'table': 'us_customers'},
                'transforms': [],
                'set_operation': {'type': 'union', 'all': False}
            },
            {
                'name': None,
                'from': {'table': 'eu_customers'},
                'transforms': []
            }
        ]
        result = json_to_asql(query_json)

        assert 'from us_customers' in result
        assert 'UNION' in result
        assert 'from eu_customers' in result

    def test_union_all_set_operation(self):
        """Test UNION ALL set operation."""
        query_json = [
            {
                'name': None,
                'from': {'table': 'table_a'},
                'transforms': [],
                'set_operation': {'type': 'union', 'all': True}
            },
            {
                'name': None,
                'from': {'table': 'table_b'},
                'transforms': []
            }
        ]
        result = json_to_asql(query_json)

        assert 'UNION ALL' in result

    def test_intersect_set_operation(self):
        """Test INTERSECT set operation."""
        query_json = [
            {
                'name': None,
                'from': {'table': 'table_a'},
                'transforms': [],
                'set_operation': {'type': 'intersect', 'all': False}
            },
            {
                'name': None,
                'from': {'table': 'table_b'},
                'transforms': []
            }
        ]
        result = json_to_asql(query_json)

        assert 'INTERSECT' in result

    def test_except_set_operation(self):
        """Test EXCEPT set operation."""
        query_json = [
            {
                'name': None,
                'from': {'table': 'all_users'},
                'transforms': [],
                'set_operation': {'type': 'except', 'all': False}
            },
            {
                'name': None,
                'from': {'table': 'banned_users'},
                'transforms': []
            }
        ]
        result = json_to_asql(query_json)

        assert 'EXCEPT' in result

    def test_backward_compatible_with_single_dict(self):
        """Test backward compatibility with legacy single dict format."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{'type': 'limit', 'count': 5}]
        }
        result = json_to_asql(query_json)

        assert 'from users' in result
        assert 'limit 5' in result

    def test_cte_with_transforms_and_final_query(self):
        """Test full CTE pattern with transforms.
        
        When a subsequent pipeline references a CTE we just created,
        it continues the pipeline (no new FROM) instead of starting a new statement.
        This produces a single SQL statement with all CTEs in one WITH clause.
        """
        query_json = [
            {
                'name': 'recent_orders',
                'from': {'table': 'orders'},
                'transforms': [
                    {'type': 'where', 'condition': {'type': 'binary_op', 'operator': '>', 'left': {'type': 'column', 'name': 'created_at'}, 'right': {'type': 'literal', 'value': '2024-01-01', 'data_type': 'string'}}}
                ]
            },
            {
                'name': None,
                'from': {'table': 'recent_orders'},
                'transforms': [
                    {'type': 'group_by', 'dimensions': ['customer_id'], 'aggregates': [{'function': 'count', 'column': '*', 'alias': 'order_count'}]}
                ]
            }
        ]
        result = json_to_asql(query_json)

        assert 'from orders' in result
        assert 'stash as recent_orders' in result
        # No separate 'from recent_orders' - pipeline continues after stash
        assert 'group by customer_id' in result


class TestPipelineValidation:
    """Tests for pipeline validation."""

    def test_valid_single_pipeline(self):
        """Test valid single pipeline has no errors."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{'type': 'limit', 'count': 10}]
        }
        errors = validate_pipelines(query_json)
        assert len(errors) == 0

    def test_valid_cte_pipeline(self):
        """Test valid CTE pattern has no errors."""
        query_json = [
            {'name': 'active_users', 'from': {'table': 'users'}, 'transforms': []},
            {'name': None, 'from': {'table': 'active_users'}, 'transforms': []}
        ]
        errors = validate_pipelines(query_json)
        assert len(errors) == 0

    def test_missing_from_table(self):
        """Test validation catches missing FROM table."""
        query_json = [
            {'name': None, 'from': {'table': ''}, 'transforms': []}
        ]
        errors = validate_pipelines(query_json)
        assert any('Missing FROM table' in e for e in errors)

    def test_invalid_pipeline_name(self):
        """Test validation catches invalid pipeline names."""
        query_json = [
            {'name': 'invalid name', 'from': {'table': 'users'}, 'transforms': []},
            {'name': None, 'from': {'table': 'invalid name'}, 'transforms': []}
        ]
        errors = validate_pipelines(query_json)
        assert any('Invalid pipeline name' in e for e in errors)

    def test_duplicate_pipeline_name(self):
        """Test validation catches duplicate pipeline names."""
        query_json = [
            {'name': 'cte1', 'from': {'table': 'users'}, 'transforms': []},
            {'name': 'cte1', 'from': {'table': 'orders'}, 'transforms': []},
            {'name': None, 'from': {'table': 'cte1'}, 'transforms': []}
        ]
        errors = validate_pipelines(query_json)
        assert any('Duplicate pipeline name' in e for e in errors)

    def test_circular_reference_direct(self):
        """Test validation catches direct circular reference."""
        query_json = [
            {'name': 'a', 'from': {'table': 'b'}, 'transforms': []},
            {'name': 'b', 'from': {'table': 'a'}, 'transforms': []},
            {'name': None, 'from': {'table': 'a'}, 'transforms': []}
        ]
        errors = validate_pipelines(query_json)
        assert any('Circular reference' in e for e in errors)

    def test_circular_reference_indirect(self):
        """Test validation catches indirect circular reference."""
        query_json = [
            {'name': 'a', 'from': {'table': 'c'}, 'transforms': []},
            {'name': 'b', 'from': {'table': 'a'}, 'transforms': []},
            {'name': 'c', 'from': {'table': 'b'}, 'transforms': []},
            {'name': None, 'from': {'table': 'a'}, 'transforms': []}
        ]
        errors = validate_pipelines(query_json)
        assert any('Circular reference' in e for e in errors)

    def test_set_operation_on_last_pipeline(self):
        """Test validation warns about set_operation on last pipeline."""
        query_json = [
            {'name': None, 'from': {'table': 'users'}, 'transforms': [], 'set_operation': {'type': 'union', 'all': False}}
        ]
        errors = validate_pipelines(query_json)
        assert any('set_operation should not be on the last pipeline' in e for e in errors)

    def test_empty_pipelines(self):
        """Test validation handles empty pipelines list."""
        errors = validate_pipelines([])
        assert any('No pipelines provided' in e for e in errors)
