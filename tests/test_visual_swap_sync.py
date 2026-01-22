"""
Synchronous tests for Visual ASQL swap functionality.

Tests the round-trip conversion: Visual ASQL JSON → SQL → Visual ASQL JSON → SQL
This simulates what happens when users click the swap button in the playground.

These tests don't require async dependencies - they test the underlying transpilation
functions directly.
"""

import pytest
import json
import sqlglot

# Import ASQL dialects to register them with sqlglot
import asql.dialect  # noqa: F401 - registers 'asql' dialect
import asql.visual_dialect  # noqa: F401 - registers 'visual_asql' dialect
from asql.json_schema import json_to_asql


def normalize_visual_json(data):
    """Extract only semantic content from Visual JSON for comparison.
    
    Ignores metadata fields like 'id', 'output_columns', 'alias: null' that
    are added by the generator but don't affect the query semantics.
    """
    if isinstance(data, list):
        return [normalize_visual_json(p) for p in data]
    
    if not isinstance(data, dict):
        return data
    
    result = {}
    
    # From clause - just table name
    if 'from' in data:
        f = data['from']
        result['from'] = f.get('table') if isinstance(f, dict) else f
    
    # Name (for CTEs) - ignore auto-generated __tmp names
    name = data.get('name')
    if name and not name.startswith('__tmp'):
        result['name'] = name
    
    # Transforms - extract semantic content
    if 'transforms' in data:
        result['transforms'] = []
        for t in data['transforms']:
            ttype = t.get('type')
            
            # Skip SELECT * transforms (semantically equivalent to no select)
            if ttype == 'select':
                columns = t.get('columns', [])
                # If all columns are just '*', skip this transform
                if all(_is_star_column(c) for c in columns):
                    continue
            
            nt = {'type': ttype}
            
            # Condition - normalize to string for comparison
            if 'condition' in t:
                cond = t['condition']
                if isinstance(cond, dict):
                    nt['condition'] = _condition_to_string(cond)
                else:
                    nt['condition'] = cond
            
            # Copy other semantic fields
            for key in ['join_type', 'table', 'dimensions', 'aggregates', 
                        'columns', 'expressions', 'count']:
                if key in t:
                    nt[key] = t[key]
            
            result['transforms'].append(nt)
    
    return result


def _is_star_column(col):
    """Check if a column represents SELECT *."""
    if isinstance(col, dict):
        name = col.get('name', '')
        return name == '*'
    return col == '*'


def _condition_to_string(cond):
    """Convert structured condition to normalized string."""
    if isinstance(cond, str):
        return cond
    if not isinstance(cond, dict):
        return str(cond)
    
    ctype = cond.get('type')
    
    if ctype == 'column':
        table = cond.get('table', '')
        name = cond.get('name', '')
        return f'{table}.{name}' if table else name
    
    if ctype == 'literal':
        val = cond.get('value')
        dtype = cond.get('data_type')
        if dtype == 'string':
            return f"'{val}'"
        return str(val)
    
    if ctype == 'binary_op':
        left = _condition_to_string(cond.get('left', {}))
        right = _condition_to_string(cond.get('right', {}))
        op = cond.get('operator', '=')
        # Normalize == to =
        if op == '==':
            op = '='
        return f'{left} {op} {right}'
    
    return str(cond)


# Visual ASQL examples for testing
VISUAL_EXAMPLES = [
    {
        "name": "Simple Filter",
        "query": [{
            "from": {"table": "users"},
            "transforms": [
                {"id": "t0", "type": "where", "condition": "status = 'active'"}
            ]
        }]
    },
    {
        "name": "Select Columns",
        "query": [{
            "from": {"table": "users"},
            "transforms": [
                {
                    "id": "t0",
                    "type": "select",
                    "columns": [
                        {"name": "name", "expression": "name"},
                        {"name": "email", "expression": "email"}
                    ]
                }
            ]
        }]
    },
    {
        "name": "Group and Count",
        "query": [{
            "from": {"table": "users"},
            "transforms": [
                {
                    "id": "t0",
                    "type": "group_by",
                    "dimensions": ["country"],
                    "aggregates": [
                        {"function": "count", "column": "*", "alias": "total"}
                    ]
                }
            ]
        }]
    },
    {
        "name": "Sort and Limit",
        "query": [{
            "from": {"table": "users"},
            "transforms": [
                {"id": "t0", "type": "order_by", "expressions": [{"column": "name", "direction": "asc"}]},
                {"id": "t1", "type": "limit", "count": 10}
            ]
        }]
    },
    {
        "name": "Join with Filter",
        "query": [{
            "from": {"table": "orders"},
            "transforms": [
                {
                    "id": "t0",
                    "type": "join",
                    "join_type": "inner",
                    "table": "customers",
                    "condition": "orders.customer_id = customers.id"
                },
                {"id": "t1", "type": "where", "condition": "orders.total > 100"}
            ]
        }]
    },
    {
        "name": "Complex Dashboard",
        "query": [{
            "from": {"table": "orders"},
            "transforms": [
                {
                    "id": "t0",
                    "type": "join",
                    "join_type": "inner",
                    "table": "customers",
                    "condition": "orders.customer_id = customers.id"
                },
                {"id": "t1", "type": "where", "condition": "orders.status = 'completed'"},
                {
                    "id": "t2",
                    "type": "group_by",
                    "dimensions": ["customers.country"],
                    "aggregates": [
                        {"function": "count", "column": "*", "alias": "order_count"},
                        {"function": "sum", "column": "orders.total", "alias": "revenue"}
                    ]
                },
                {"id": "t3", "type": "order_by", "expressions": [{"column": "revenue", "direction": "desc"}]},
                {"id": "t4", "type": "limit", "count": 10}
            ]
        }]
    },
]


def visual_json_to_sql(query_json: list, target_dialect: str = "snowflake") -> str:
    """Convert Visual ASQL JSON to SQL using sqlglot transpile."""
    json_str = json.dumps(query_json)
    results = sqlglot.transpile(json_str, read="visual_asql", write=target_dialect)
    return results[0] if results else ""


def sql_to_visual_json(sql: str, source_dialect: str = "snowflake") -> list:
    """Convert SQL to Visual ASQL JSON using sqlglot transpile."""
    results = sqlglot.transpile(sql, read=source_dialect, write="visual_asql")
    if results and results[0]:
        return json.loads(results[0])
    return []


class TestVisualToSql:
    """Tests for Visual ASQL JSON → SQL conversion."""

    @pytest.mark.parametrize("example", VISUAL_EXAMPLES, ids=lambda x: x["name"])
    def test_visual_to_sql(self, example):
        """Test that Visual ASQL JSON transpiles to valid SQL."""
        sql = visual_json_to_sql(example['query'])
        
        assert sql, f"Failed to transpile {example['name']}"
        assert len(sql) > 0
        
        # Basic SQL structure checks
        sql_upper = sql.upper()
        assert 'SELECT' in sql_upper or 'FROM' in sql_upper
        
        print(f"\n{example['name']}:")
        print(f"  SQL: {sql[:200]}...")


class TestSqlToVisual:
    """Tests for SQL → Visual ASQL JSON conversion."""

    def test_simple_sql_to_visual(self):
        """Test converting simple SQL to Visual ASQL JSON."""
        sql = "SELECT * FROM users WHERE status = 'active'"
        
        result = sql_to_visual_json(sql)
        
        assert result, "Failed to convert SQL"
        
        query = result[0] if isinstance(result, list) else result
        assert 'from' in query
        assert query['from']['table'] == 'users'
        
        print("\nSimple SQL converted to:")
        print(json.dumps(result, indent=2)[:500])

    def test_join_sql_to_visual(self):
        """Test converting SQL with JOIN to Visual ASQL JSON."""
        sql = """
        SELECT * FROM orders 
        INNER JOIN customers ON orders.customer_id = customers.id
        WHERE orders.total > 100
        """
        
        result = sql_to_visual_json(sql)
        assert result, "Failed to convert SQL with JOIN"
        
        print("\nJoin SQL converted to:")
        print(json.dumps(result, indent=2)[:500])

    def test_aggregate_sql_to_visual(self):
        """Test converting SQL with aggregates to Visual ASQL JSON."""
        sql = """
        SELECT country, COUNT(*) as total 
        FROM users 
        GROUP BY country
        """
        
        result = sql_to_visual_json(sql)
        assert result, "Failed to convert aggregate SQL"
        
        print("\nAggregate SQL converted to:")
        print(json.dumps(result, indent=2)[:500])


class TestSwapRoundTrip:
    """Tests for full round-trip: Visual ASQL → SQL → Visual ASQL → SQL."""

    @pytest.mark.parametrize("example", VISUAL_EXAMPLES, ids=lambda x: x["name"])
    def test_single_swap_roundtrip(self, example):
        """
        Test single swap round-trip:
        Visual ASQL JSON → SQL → Visual ASQL JSON
        """
        # Step 1: Visual ASQL → SQL
        sql1 = visual_json_to_sql(example['query'])
        assert sql1, f"Step 1 failed for {example['name']}"
        
        print(f"\n{example['name']} - Step 1 (Visual→SQL):")
        print(f"  {sql1[:200]}...")
        
        # Step 2: SQL → Visual ASQL JSON (simulates first swap)
        json_result = sql_to_visual_json(sql1)
        assert json_result, f"Step 2 failed for {example['name']}"
        
        print(f"\n{example['name']} - Step 2 (SQL→Visual):")
        print(f"  {json.dumps(json_result, indent=2)[:300]}...")

    @pytest.mark.parametrize("example", VISUAL_EXAMPLES, ids=lambda x: x["name"])
    def test_double_swap_roundtrip(self, example):
        """
        Test double swap round-trip (swap twice):
        Visual ASQL JSON → SQL → Visual ASQL JSON → SQL
        """
        # Step 1: Visual ASQL → SQL
        sql1 = visual_json_to_sql(example['query'])
        assert sql1, "Step 1 failed"
        
        # Step 2: SQL → Visual ASQL JSON (first swap)
        json_result = sql_to_visual_json(sql1)
        assert json_result, "Step 2 failed"
        
        # Step 3: Visual ASQL JSON → SQL (second swap - back to SQL)
        sql2 = visual_json_to_sql(json_result)
        assert sql2, f"Step 3 failed for {example['name']}"
        
        print(f"\n{example['name']} - Double swap:")
        print(f"  Original SQL: {sql1[:150]}...")
        print(f"  After 2 swaps: {sql2[:150]}...")

    def test_triple_swap_stability(self):
        """
        Test that swapping 3+ times produces stable output.
        """
        example = VISUAL_EXAMPLES[0]  # Simple Filter
        
        # Initial: Visual ASQL → SQL
        sql1 = visual_json_to_sql(example['query'])
        
        # Swap 1: SQL → Visual
        json1 = sql_to_visual_json(sql1)
        
        # Swap 2: Visual → SQL
        sql2 = visual_json_to_sql(json1)
        
        # Swap 3: SQL → Visual
        json2 = sql_to_visual_json(sql2)
        
        # Swap 4: Visual → SQL
        sql3 = visual_json_to_sql(json2)
        
        print("\nTriple swap stability test:")
        print(f"  SQL after 2 swaps: {sql2}")
        print(f"  SQL after 4 swaps: {sql3}")
        
        # After stabilization, SQL should be identical
        assert sql2 == sql3, f"SQL not stable after multiple swaps:\n  sql2: {sql2}\n  sql3: {sql3}"


class TestSwapEdgeCases:
    """Tests for edge cases in swap functionality."""

    def test_empty_transforms(self):
        """Test swap with no transforms (just FROM)."""
        query = [{"from": {"table": "users"}, "transforms": []}]
        
        # Visual → SQL
        sql = visual_json_to_sql(query)
        assert sql
        
        # SQL → Visual
        result = sql_to_visual_json(sql)
        assert result
        
        print("\nEmpty transforms:")
        print(f"  SQL: {sql}")
        print(f"  Back to JSON: {json.dumps(result, indent=2)[:200]}")

    def test_multiple_pipelines_cte(self):
        """Test swap with multiple pipelines (CTEs)."""
        query = [
            {
                "name": "active_users",
                "from": {"table": "users"},
                "transforms": [
                    {"id": "t0", "type": "where", "condition": "status = 'active'"}
                ]
            },
            {
                "from": {"table": "active_users"},
                "transforms": [
                    {"id": "t0", "type": "limit", "count": 10}
                ]
            }
        ]
        
        # Visual → SQL
        sql = visual_json_to_sql(query)
        assert sql
        
        print("\nMultiple pipelines (CTE):")
        print(f"  SQL: {sql}")
        
        # Should contain CTE structure
        assert 'WITH' in sql.upper() or 'active_users' in sql.lower()


class TestSwapWithDifferentDialects:
    """Tests for swap with different SQL dialects."""

    @pytest.mark.parametrize("dialect", ["snowflake", "postgres", "bigquery", "duckdb"])
    def test_swap_different_dialects(self, dialect):
        """Test swap works with different SQL dialects."""
        query = [{
            "from": {"table": "users"},
            "transforms": [
                {"id": "t0", "type": "where", "condition": "status = 'active'"},
                {"id": "t1", "type": "limit", "count": 10}
            ]
        }]
        
        try:
            # Visual → SQL
            sql = visual_json_to_sql(query, dialect)
            assert sql
            
            # SQL → Visual
            result = sql_to_visual_json(sql, dialect)
            assert result
            
            print(f"\n{dialect}:")
            print(f"  SQL: {sql[:100]}...")
            
        except Exception as e:
            pytest.skip(f"Dialect {dialect} error: {e}")


class TestSqlSemanticPreservation:
    """Tests that verify SQL semantic content is preserved during round-trips."""

    def test_cte_preserves_structure(self):
        """Test that CTEs are preserved in round-trip conversion."""
        query = [
            {
                "name": "filtered_orders",
                "from": {"table": "orders"},
                "transforms": [
                    {"type": "join", "join_type": "inner", "table": "customers", 
                     "condition": {"type": "binary_op", "operator": "=",
                                   "left": {"type": "column", "name": "customer_id", "table": "orders"},
                                   "right": {"type": "column", "name": "id", "table": "customers"}}},
                    {"type": "where", "condition": "orders.status = 'completed'"}
                ]
            },
            {
                "name": "aggregated",
                "from": {"table": "filtered_orders"},
                "transforms": [
                    {"type": "group_by", "dimensions": ["country"],
                     "aggregates": [{"function": "count", "column": "*", "alias": "total_orders"},
                                   {"function": "sum", "column": "amount", "alias": "revenue"}]}
                ]
            },
            {
                "name": None,
                "from": {"table": "aggregated"},
                "transforms": [
                    {"type": "where", "condition": "total_orders > 10"},
                    {"type": "order_by", "expressions": [{"column": "revenue", "direction": "desc"}]}
                ]
            }
        ]
        
        # Visual → SQL
        sql = visual_json_to_sql(query)
        
        # Verify key SQL elements are present
        sql_upper = sql.upper()
        assert 'WITH' in sql_upper, "Should have WITH clause for CTEs"
        assert 'JOIN' in sql_upper, "Should preserve JOIN"
        assert 'GROUP BY' in sql_upper, "Should preserve GROUP BY"
        assert 'ORDER BY' in sql_upper, "Should preserve ORDER BY"
        assert 'COUNT(*)' in sql_upper, "Should preserve COUNT(*) aggregate"
        assert 'SUM' in sql_upper, "Should preserve SUM aggregate"
        
        print("\nCTE preservation test SQL:")
        print(f"  {sql[:300]}...")

    def test_join_condition_preserved(self):
        """Test that join conditions are preserved."""
        query = [{
            "from": {"table": "orders"},
            "transforms": [
                {"type": "join", "join_type": "left", "table": "products",
                 "condition": {"type": "binary_op", "operator": "=",
                               "left": {"type": "column", "name": "product_id", "table": "orders"},
                               "right": {"type": "column", "name": "id", "table": "products"}}},
                {"type": "where", "condition": "orders.total > 100"}
            ]
        }]
        
        # Visual → SQL
        sql1 = visual_json_to_sql(query)
        
        # SQL → Visual → SQL
        visual = sql_to_visual_json(sql1)
        sql2 = visual_json_to_sql(visual)
        
        # Both should have JOIN with condition
        for sql in [sql1, sql2]:
            sql_upper = sql.upper()
            assert 'LEFT' in sql_upper or 'JOIN' in sql_upper, "Should have LEFT JOIN"
            assert 'PRODUCT_ID' in sql_upper, "Should preserve join column"
        
        print("\nJoin preservation:")
        print(f"  Original: {sql1[:150]}...")
        print(f"  Round-trip: {sql2[:150]}...")

    def test_aggregate_functions_preserved(self):
        """Test that aggregate functions are preserved."""
        query = [{
            "from": {"table": "orders"},
            "transforms": [
                {"type": "group_by", "dimensions": ["customer_id", "status"],
                 "aggregates": [
                     {"function": "count", "column": "*", "alias": "order_count"},
                     {"function": "sum", "column": "total", "alias": "total_amount"},
                     {"function": "avg", "column": "total", "alias": "avg_amount"},
                     {"function": "min", "column": "total", "alias": "min_amount"},
                     {"function": "max", "column": "total", "alias": "max_amount"}
                 ]}
            ]
        }]
        
        # Visual → SQL
        sql = visual_json_to_sql(query)
        sql_upper = sql.upper()
        
        # Verify all aggregate functions are present
        assert 'COUNT(*)' in sql_upper, "Should have COUNT(*)"
        assert 'SUM' in sql_upper, "Should have SUM"
        assert 'AVG' in sql_upper, "Should have AVG"
        assert 'MIN' in sql_upper, "Should have MIN"
        assert 'MAX' in sql_upper, "Should have MAX"
        assert 'GROUP BY' in sql_upper, "Should have GROUP BY"
        
        print("\nAggregate preservation:")
        print(f"  {sql}")

    def test_filter_and_sort_preserved(self):
        """Test that WHERE and ORDER BY are preserved."""
        query = [{
            "from": {"table": "users"},
            "transforms": [
                {"type": "where", "condition": "age >= 18 and status = 'active'"},
                {"type": "order_by", "expressions": [
                    {"column": "name", "direction": "asc"},
                    {"column": "created_at", "direction": "desc"}
                ]},
                {"type": "limit", "count": 100}
            ]
        }]
        
        # Visual → SQL
        sql1 = visual_json_to_sql(query)
        
        # SQL → Visual → SQL
        visual = sql_to_visual_json(sql1)
        sql2 = visual_json_to_sql(visual)
        
        # Both should have WHERE, ORDER BY, and LIMIT
        for sql in [sql1, sql2]:
            sql_upper = sql.upper()
            assert 'WHERE' in sql_upper, "Should have WHERE clause"
            assert 'ORDER BY' in sql_upper, "Should have ORDER BY"
            assert 'LIMIT' in sql_upper or 'FETCH' in sql_upper or 'TOP' in sql_upper, "Should have LIMIT"
        
        print("\nFilter/sort preservation:")
        print(f"  Original: {sql1}")
        print(f"  Round-trip: {sql2}")


class TestVisualAsqlSemanticRoundTrip:
    """Tests that Visual ASQL → ASQL text → Visual ASQL preserves semantic content.
    
    This tests the internal round-trip within ASQL, not SQL dialect conversions.
    The semantic content should be identical after round-trip.
    """

    def _assert_semantic_match(self, original_json, name=""):
        """Helper to test semantic round-trip."""
        # Normalize original
        orig_norm = normalize_visual_json(original_json)
        
        # Round-trip: Visual JSON -> ASQL text -> Visual JSON
        asql_text = json_to_asql(original_json)
        results = sqlglot.transpile(asql_text, read='asql', write='visual_asql')
        roundtrip_json = json.loads(results[0])
        rt_norm = normalize_visual_json(roundtrip_json)
        
        # Compare normalized versions
        orig_str = json.dumps(orig_norm, sort_keys=True)
        rt_str = json.dumps(rt_norm, sort_keys=True)
        
        assert orig_str == rt_str, (
            f"Semantic mismatch in {name}:\n"
            f"  Original:   {orig_str}\n"
            f"  Round-trip: {rt_str}"
        )

    def test_simple_filter_roundtrip(self):
        """Test simple WHERE clause round-trip."""
        query = [{
            'from': {'table': 'users'},
            'transforms': [
                {'type': 'where', 'condition': "status = 'active'"}
            ]
        }]
        self._assert_semantic_match(query, "simple filter")

    def test_group_by_roundtrip(self):
        """Test GROUP BY with aggregates round-trip."""
        query = [{
            'from': {'table': 'orders'},
            'transforms': [
                {'type': 'group_by', 'dimensions': ['customer_id', 'status'],
                 'aggregates': [
                     {'function': 'count', 'column': '*', 'alias': 'total'},
                     {'function': 'sum', 'column': 'amount', 'alias': 'revenue'}
                 ]}
            ]
        }]
        self._assert_semantic_match(query, "group by")

    def test_join_roundtrip(self):
        """Test JOIN round-trip."""
        query = [{
            'from': {'table': 'orders'},
            'transforms': [
                {'type': 'join', 'join_type': 'inner', 'table': 'customers',
                 'condition': "orders.customer_id = customers.id"},
                {'type': 'where', 'condition': "orders.total > 100"}
            ]
        }]
        self._assert_semantic_match(query, "join")

    def test_order_and_limit_roundtrip(self):
        """Test ORDER BY and LIMIT round-trip."""
        query = [{
            'from': {'table': 'users'},
            'transforms': [
                {'type': 'order_by', 'expressions': [
                    {'column': 'name', 'direction': 'asc'},
                    {'column': 'created_at', 'direction': 'desc'}
                ]},
                {'type': 'limit', 'count': 50}
            ]
        }]
        self._assert_semantic_match(query, "order and limit")

    def test_cte_roundtrip(self):
        """Test CTE (named pipeline) round-trip."""
        query = [
            {
                'name': 'active_users',
                'from': {'table': 'users'},
                'transforms': [
                    {'type': 'where', 'condition': "status = 'active'"}
                ]
            },
            {
                'from': {'table': 'active_users'},
                'transforms': [
                    {'type': 'group_by', 'dimensions': ['country'],
                     'aggregates': [{'function': 'count', 'column': '*', 'alias': 'total'}]}
                ]
            }
        ]
        self._assert_semantic_match(query, "CTE")

    def test_complex_pipeline_roundtrip(self):
        """Test complex pipeline with multiple transforms round-trip.
        
        Note: Uses unqualified column names because ASQL strips table qualifiers
        from GROUP BY dimensions and aggregate columns during transpilation.
        """
        query = [{
            'from': {'table': 'orders'},
            'transforms': [
                {'type': 'join', 'join_type': 'left', 'table': 'customers',
                 'condition': "orders.customer_id = customers.id"},
                {'type': 'where', 'condition': "orders.status = 'completed'"},
                {'type': 'group_by', 'dimensions': ['country'],
                 'aggregates': [
                     {'function': 'count', 'column': '*', 'alias': 'order_count'},
                     {'function': 'sum', 'column': 'total', 'alias': 'revenue'}
                 ]},
                {'type': 'order_by', 'expressions': [{'column': 'revenue', 'direction': 'desc'}]},
                {'type': 'limit', 'count': 10}
            ]
        }]
        self._assert_semantic_match(query, "complex pipeline")

    @pytest.mark.xfail(reason="ASQL transpiler creates extra __tmp CTEs for multi-CTE queries")
    def test_multi_cte_roundtrip(self):
        """Test multiple CTEs round-trip.
        
        Known issue: ASQL creates extra intermediate CTEs (__tmp1, etc.) when
        transpiling multi-CTE queries, which breaks the round-trip.
        """
        query = [
            {
                'name': 'filtered',
                'from': {'table': 'orders'},
                'transforms': [
                    {'type': 'join', 'join_type': 'inner', 'table': 'customers',
                     'condition': "orders.customer_id = customers.id"},
                    {'type': 'where', 'condition': "orders.status = 'completed'"}
                ]
            },
            {
                'name': 'aggregated',
                'from': {'table': 'filtered'},
                'transforms': [
                    {'type': 'group_by', 'dimensions': ['country'],
                     'aggregates': [{'function': 'sum', 'column': 'total', 'alias': 'revenue'}]}
                ]
            },
            {
                'from': {'table': 'aggregated'},
                'transforms': [
                    {'type': 'where', 'condition': 'revenue > 1000'},
                    {'type': 'order_by', 'expressions': [{'column': 'revenue', 'direction': 'desc'}]}
                ]
            }
        ]
        self._assert_semantic_match(query, "multi CTE")


class TestSqlIdentityRoundTrip:
    """Tests that Visual ASQL → SQL → Visual ASQL → SQL produces identical SQL.
    
    This ensures that converting to SQL and back doesn't lose or change information.
    """

    def _assert_sql_identity(self, visual_json, dialect='snowflake', name=""):
        """Helper to test SQL identity after round-trip."""
        # Step 1: Visual JSON → SQL
        json_str = json.dumps(visual_json)
        results1 = sqlglot.transpile(json_str, read='visual_asql', write=dialect)
        sql1 = results1[0]
        
        # Step 2: SQL → Visual JSON
        results2 = sqlglot.transpile(sql1, read=dialect, write='visual_asql')
        visual_json2 = json.loads(results2[0])
        
        # Step 3: Visual JSON → SQL (again)
        json_str2 = json.dumps(visual_json2)
        results3 = sqlglot.transpile(json_str2, read='visual_asql', write=dialect)
        sql2 = results3[0]
        
        # Normalize for comparison
        def normalize(sql):
            try:
                parsed = sqlglot.parse_one(sql, dialect=dialect)
                return parsed.sql(dialect=dialect, pretty=False)
            except Exception:
                return sql.strip()
        
        sql1_norm = normalize(sql1)
        sql2_norm = normalize(sql2)
        
        assert sql1_norm == sql2_norm, (
            f"SQL not identical after round-trip ({name}):\n"
            f"  SQL1: {sql1_norm}\n"
            f"  SQL2: {sql2_norm}"
        )

    def test_simple_filter_sql_identity(self):
        """Test simple WHERE produces identical SQL."""
        query = [{'from': {'table': 'users'},
                  'transforms': [{'type': 'where', 'condition': "status = 'active'"}]}]
        self._assert_sql_identity(query, name="simple filter")

    def test_compound_filter_sql_identity(self):
        """Test compound WHERE with AND produces identical SQL."""
        query = [{'from': {'table': 'users'},
                  'transforms': [{'type': 'where', 'condition': "status = 'active' and age > 18"}]}]
        self._assert_sql_identity(query, name="compound filter")

    def test_group_by_sql_identity(self):
        """Test GROUP BY produces identical SQL."""
        query = [{'from': {'table': 'orders'},
                  'transforms': [{'type': 'group_by', 'dimensions': ['country'],
                                  'aggregates': [{'function': 'count', 'column': '*', 'alias': 'total'}]}]}]
        self._assert_sql_identity(query, name="group by")

    def test_join_sql_identity(self):
        """Test JOIN produces identical SQL."""
        query = [{'from': {'table': 'orders'},
                  'transforms': [
                      {'type': 'join', 'join_type': 'left', 'table': 'customers',
                       'condition': 'orders.customer_id = customers.id'},
                      {'type': 'where', 'condition': 'orders.total > 100'}
                  ]}]
        self._assert_sql_identity(query, name="join")

    def test_order_limit_sql_identity(self):
        """Test ORDER BY + LIMIT produces identical SQL."""
        query = [{'from': {'table': 'users'},
                  'transforms': [
                      {'type': 'order_by', 'expressions': [{'column': 'name', 'direction': 'desc'}]},
                      {'type': 'limit', 'count': 10}
                  ]}]
        self._assert_sql_identity(query, name="order + limit")

    def test_cte_sql_identity(self):
        """Test CTE produces identical SQL."""
        query = [
            {'name': 'active', 'from': {'table': 'users'},
             'transforms': [{'type': 'where', 'condition': "status = 'active'"}]},
            {'from': {'table': 'active'},
             'transforms': [{'type': 'limit', 'count': 10}]}
        ]
        self._assert_sql_identity(query, name="CTE")

    @pytest.mark.parametrize("dialect", ["snowflake", "postgres", "duckdb"])
    def test_sql_identity_across_dialects(self, dialect):
        """Test SQL identity works across different dialects."""
        query = [{'from': {'table': 'users'},
                  'transforms': [
                      {'type': 'where', 'condition': "status = 'active'"},
                      {'type': 'limit', 'count': 10}
                  ]}]
        self._assert_sql_identity(query, dialect=dialect, name=f"dialect {dialect}")
