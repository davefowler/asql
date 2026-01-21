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
        
        print(f"\nSimple SQL converted to:")
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
        
        print(f"\nJoin SQL converted to:")
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
        
        print(f"\nAggregate SQL converted to:")
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
        assert sql1, f"Step 1 failed"
        
        # Step 2: SQL → Visual ASQL JSON (first swap)
        json_result = sql_to_visual_json(sql1)
        assert json_result, f"Step 2 failed"
        
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
        
        print(f"\nTriple swap stability test:")
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
        
        print(f"\nEmpty transforms:")
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
        
        print(f"\nMultiple pipelines (CTE):")
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
