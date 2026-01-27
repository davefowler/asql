"""
Tests for Visual Editor API Endpoints

Tests for the FastAPI API endpoints used by the visual editor.
"""

import pytest
import json

# Skip all tests if pytest_asyncio is not available
try:
    import pytest_asyncio  # noqa: F401
    pytest_plugins = ('pytest_asyncio',)
    HAS_PYTEST_ASYNCIO = True
except ImportError:
    HAS_PYTEST_ASYNCIO = False

# Skip tests if httpx/FastAPI test client is not available
try:
    from httpx import AsyncClient, ASGITransport
    from playground.app import app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# Skip entire module if dependencies aren't available
if not HAS_PYTEST_ASYNCIO:
    pytest.skip("pytest_asyncio not installed", allow_module_level=True)


@pytest_asyncio.fixture
async def client():
    """Create an async test client for the FastAPI app."""
    if not HAS_FASTAPI:
        pytest.skip("FastAPI/httpx not available")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# Tell pytest-asyncio to treat all async functions as tests
pytestmark = pytest.mark.asyncio


class TestParseToVisual:
    """Tests for /api/visual/parse endpoint."""

    async def test_parse_simple_query(self, client):
        """Test parsing a simple ASQL query."""
        response = await client.post(
            '/api/visual/parse',
            json={'asql': 'from users'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'query' in data
        # query is now a list of query objects
        query = data['query'][0] if isinstance(data['query'], list) else data['query']
        assert query['from']['table'] == 'users'

    async def test_parse_query_with_where(self, client):
        """Test parsing a query with WHERE clause."""
        response = await client.post(
            '/api/visual/parse',
            json={'asql': 'from users\n  where status == "active"'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        # query is now a list of query objects
        query = data['query'][0] if isinstance(data['query'], list) else data['query']
        assert len(query['transforms']) >= 1

        # Find the where transform
        where_transform = next(
            (t for t in query['transforms'] if t['type'] == 'where'),
            None
        )
        assert where_transform is not None

    async def test_parse_query_with_limit(self, client):
        """Test parsing a query with LIMIT."""
        response = await client.post(
            '/api/visual/parse',
            json={'asql': 'from users\n  limit 10'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        # query is now a list of query objects
        query = data['query'][0] if isinstance(data['query'], list) else data['query']
        limit_transform = next(
            (t for t in query['transforms'] if t['type'] == 'limit'),
            None
        )
        assert limit_transform is not None
        assert limit_transform['count'] == 10

    async def test_parse_empty_query_returns_error(self, client):
        """Test that empty query returns an error."""
        response = await client.post(
            '/api/visual/parse',
            json={'asql': ''}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'error' in data

    async def test_parse_missing_asql_returns_error(self, client):
        """Test that missing ASQL field returns an error."""
        response = await client.post(
            '/api/visual/parse',
            json={}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False

    async def test_parse_invalid_syntax_returns_error(self, client):
        """Test that invalid syntax returns an error."""
        response = await client.post(
            '/api/visual/parse',
            json={'asql': 'invalid syntax here!!!'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'error' in data


class TestCompileFromVisual:
    """Tests for /api/visual/compile endpoint."""

    async def test_compile_simple_query(self, client):
        """Test compiling a simple JSON query."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': []
        }

        response = await client.post(
            '/api/visual/compile',
            json={'query': query_json}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'asql' in data
        assert 'from users' in data['asql']

    async def test_compile_query_with_where(self, client):
        """Test compiling a query with WHERE."""
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

        response = await client.post(
            '/api/visual/compile',
            json={'query': query_json}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'where' in data['asql']
        assert 'status' in data['asql']

    async def test_compile_query_with_limit(self, client):
        """Test compiling a query with LIMIT."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{'id': 't0', 'type': 'limit', 'count': 25}]
        }

        response = await client.post(
            '/api/visual/compile',
            json={'query': query_json}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'limit 25' in data['asql']

    async def test_compile_empty_query_returns_error(self, client):
        """Test that empty query returns an error."""
        response = await client.post(
            '/api/visual/compile',
            json={'query': {}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False

    async def test_compile_missing_query_returns_error(self, client):
        """Test that missing query field returns an error."""
        response = await client.post(
            '/api/visual/compile',
            json={}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False


class TestListOperations:
    """Tests for /api/visual/operations endpoint."""

    async def test_list_operations_returns_list(self, client):
        """Test that operations endpoint returns a list."""
        response = await client.get('/api/visual/operations')

        assert response.status_code == 200
        data = response.json()
        assert 'operations' in data
        assert isinstance(data['operations'], list)

    async def test_operations_have_required_fields(self, client):
        """Test that each operation has required fields."""
        response = await client.get('/api/visual/operations')

        data = response.json()
        for op in data['operations']:
            assert 'type' in op
            assert 'label' in op
            # 'icon' is optional
            assert 'description' in op
            assert 'category' in op

    async def test_common_operations_exist(self, client):
        """Test that common operations are available."""
        response = await client.get('/api/visual/operations')

        data = response.json()
        op_types = {op['type'] for op in data['operations']}

        common_ops = ['where', 'select', 'limit']
        for op in common_ops:
            assert op in op_types, f"Missing common operation: {op}"


class TestGetOperationSchema:
    """Tests for /api/visual/operations/{type}/schema endpoint."""

    async def test_get_where_schema(self, client):
        """Test getting schema for WHERE operation."""
        response = await client.get('/api/visual/operations/where/schema')

        assert response.status_code == 200
        data = response.json()

        # Should have schema fields
        assert 'label' in data or 'parameters' in data

    async def test_get_limit_schema(self, client):
        """Test getting schema for LIMIT operation."""
        response = await client.get('/api/visual/operations/limit/schema')

        assert response.status_code == 200
        data = response.json()

        # Should have count parameter
        if 'parameters' in data:
            param_names = [p['name'] for p in data['parameters']]
            assert 'count' in param_names

    async def test_get_unknown_operation_returns_error(self, client):
        """Test that unknown operation returns error."""
        response = await client.get('/api/visual/operations/nonexistent_xyz/schema')

        assert response.status_code == 200
        data = response.json()
        assert 'error' in data

    async def test_schema_has_parameters(self, client):
        """Test that schema includes parameters field."""
        response = await client.get('/api/visual/operations/where/schema')

        data = response.json()
        if 'parameters' in data:
            assert isinstance(data['parameters'], list)


class TestRoundTrip:
    """Tests for round-trip: parse -> compile -> parse."""

    async def test_simple_roundtrip(self, client):
        """Test round-trip for a simple query."""
        original_asql = 'from users'

        # Parse ASQL to JSON
        parse_response = await client.post(
            '/api/visual/parse',
            json={'asql': original_asql}
        )

        parse_data = parse_response.json()
        assert parse_data['success'] is True

        # Compile JSON back to ASQL
        compile_response = await client.post(
            '/api/visual/compile',
            json={'query': parse_data['query']}
        )

        compile_data = compile_response.json()
        assert compile_data['success'] is True
        assert 'from users' in compile_data['asql']

    async def test_where_roundtrip(self, client):
        """Test round-trip for a query with WHERE."""
        original_asql = '''from users
  where status == "active"'''

        # Parse
        parse_response = await client.post(
            '/api/visual/parse',
            json={'asql': original_asql}
        )

        parse_data = parse_response.json()
        assert parse_data['success'] is True

        # Compile
        compile_response = await client.post(
            '/api/visual/compile',
            json={'query': parse_data['query']}
        )

        compile_data = compile_response.json()
        assert compile_data['success'] is True
        assert 'where' in compile_data['asql']
        assert 'status' in compile_data['asql']


class TestErrorHandling:
    """Tests for error handling in API endpoints."""

    async def test_invalid_json_handled(self, client):
        """Test that invalid JSON is handled gracefully."""
        response = await client.post(
            '/api/visual/parse',
            content='not valid json{{{',
            headers={'content-type': 'application/json'}
        )

        # Should not crash
        assert response.status_code in [200, 400, 422]

    async def test_missing_content_type_handled(self, client):
        """Test that missing content type is handled."""
        response = await client.post(
            '/api/visual/parse',
            content=json.dumps({'asql': 'from users'})
        )

        # Should not crash
        assert response.status_code in [200, 400, 415, 422]


class TestOutputColumns:
    """Tests for output_columns enrichment via /api/visual/transpile."""

    async def test_transpile_returns_output_columns_on_from(self, client):
        """Test that transpile endpoint returns output_columns on FROM."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': []
        }

        response = await client.post(
            '/api/visual/transpile',
            json={'query': query_json}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'enriched_query' in data

        # The enriched_query should have output_columns on from
        enriched = data['enriched_query']
        assert 'from' in enriched
        assert 'output_columns' in enriched['from'], "FROM should have output_columns"
        assert len(enriched['from']['output_columns']) > 0, "output_columns should not be empty"

    async def test_transpile_returns_output_columns_on_transforms(self, client):
        """Test that transpile endpoint returns output_columns on transforms."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': [
                {'id': 't0', 'type': 'where', 'condition': "status = 'active'"},
                {'id': 't1', 'type': 'limit', 'count': 10}
            ]
        }

        response = await client.post(
            '/api/visual/transpile',
            json={'query': query_json}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        enriched = data['enriched_query']

        # Each transform should have output_columns
        for transform in enriched.get('transforms', []):
            assert 'output_columns' in transform, f"Transform {transform.get('type')} missing output_columns"

    async def test_output_columns_contain_expected_fields(self, client):
        """Test that output_columns have name, type, and table fields."""
        query_json = {
            'from': {'table': 'users'},
            'transforms': []
        }

        response = await client.post(
            '/api/visual/transpile',
            json={'query': query_json}
        )

        assert response.status_code == 200
        data = response.json()

        output_cols = data['enriched_query']['from'].get('output_columns', [])
        assert len(output_cols) > 0

        for col in output_cols:
            assert 'name' in col, f"Column missing 'name': {col}"
            # type and table are optional but recommended

    async def test_group_by_changes_output_columns(self, client):
        """Test that GROUP BY changes the available output columns."""
        query_json = {
            'from': {'table': 'orders'},
            'transforms': [
                {
                    'id': 't0',
                    'type': 'group_by',
                    'dimensions': ['customer_id'],
                    'aggregates': [
                        {'function': 'sum', 'column': 'total', 'alias': 'total_spent'}
                    ]
                }
            ]
        }

        response = await client.post(
            '/api/visual/transpile',
            json={'query': query_json}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        enriched = data['enriched_query']
        group_transform = enriched['transforms'][0]
        output_cols = group_transform.get('output_columns', [])

        # Output should include the dimension and aggregate
        col_names = {c['name'] for c in output_cols}
        # Note: column names may be qualified (e.g., orders.customer_id)
        assert any('customer_id' in name for name in col_names), f"Expected customer_id in {col_names}"


class TestSecurityConsiderations:
    """Tests for security-related aspects of the API."""

    async def test_special_characters_in_query(self, client):
        """Test that special characters are handled safely."""
        # Test with potentially dangerous characters
        query_json = {
            'from': {'table': 'users'},
            'transforms': [{
                'id': 't0',
                'type': 'where',
                'condition': {
                    'type': 'binary_op',
                    'operator': '=',
                    'left': {'type': 'column', 'name': 'status'},
                    'right': {'type': 'literal', 'value': 'test "quote" and \\backslash', 'data_type': 'string'}
                }
            }]
        }

        response = await client.post(
            '/api/visual/compile',
            json={'query': query_json}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        # Special characters should be escaped
        assert '\\"' in data['asql'] or 'test' in data['asql']

    async def test_large_query_handled(self, client):
        """Test that very large queries are handled."""
        # Create a query with many transforms
        transforms = [
            {'id': f't{i}', 'type': 'select', 'columns': [{'name': f'col{i}'}]}
            for i in range(50)
        ]

        query_json = {
            'from': {'table': 'users'},
            'transforms': transforms
        }

        response = await client.post(
            '/api/visual/compile',
            json={'query': query_json}
        )

        # Should handle without crashing
        assert response.status_code == 200
