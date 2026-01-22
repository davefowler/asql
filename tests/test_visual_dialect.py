"""
Tests for the VisualASQL dialect.

Tests bidirectional JSON <-> SQL conversion with column tracking.
"""

import json
import pytest
import sqlglot
from sqlglot.schema import MappingSchema

from asql.visual_dialect import VisualASQLGenerator


class TestJSONToSQL:
    """Test JSON input -> SQL output."""

    def test_simple_from(self):
        """Test simple FROM clause."""
        json_input = '{"from": {"table": "users"}, "transforms": []}'
        sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
        assert "FROM" in sql.upper() and "USERS" in sql.upper()

    def test_where_condition(self):
        """Test WHERE with condition."""
        json_input = json.dumps({
            "from": {"table": "users"},
            "transforms": [
                {
                    "type": "where",
                    "condition": {
                        "type": "binary_op",
                        "operator": "=",
                        "left": {"type": "column", "name": "status"},
                        "right": {"type": "literal", "value": "active", "data_type": "string"}
                    }
                }
            ]
        })
        sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
        assert "WHERE" in sql.upper()
        assert "status" in sql.lower()
        assert "'active'" in sql

    def test_limit(self):
        """Test LIMIT clause."""
        json_input = json.dumps({
            "from": {"table": "users"},
            "transforms": [{"type": "limit", "count": 10}]
        })
        sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
        assert "LIMIT 10" in sql.upper()

    def test_offset(self):
        """Test OFFSET clause."""
        json_input = json.dumps({
            "from": {"table": "users"},
            "transforms": [
                {"type": "limit", "count": 10},
                {"type": "offset", "count": 20}
            ]
        })
        sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
        assert "LIMIT 10" in sql.upper()
        assert "OFFSET 20" in sql.upper()

    def test_order_by(self):
        """Test ORDER BY clause."""
        json_input = json.dumps({
            "from": {"table": "users"},
            "transforms": [
                {
                    "type": "order_by",
                    "expressions": [
                        {"column": "name", "direction": "asc"},
                        {"column": "created_at", "direction": "desc"}
                    ]
                }
            ]
        })
        sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
        assert "ORDER BY" in sql.upper()
        assert "DESC" in sql.upper()

    def test_join(self):
        """Test JOIN clause."""
        json_input = json.dumps({
            "from": {"table": "users"},
            "transforms": [
                {
                    "type": "join",
                    "join_type": "left",
                    "table": "orders",
                    "condition": {
                        "type": "binary_op",
                        "operator": "=",
                        "left": {"type": "column", "name": "id"},
                        "right": {"type": "column", "name": "user_id"}
                    }
                }
            ]
        })
        sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
        assert "JOIN" in sql.upper()
        assert "orders" in sql.lower()

    def test_group_by(self):
        """Test GROUP BY clause."""
        json_input = json.dumps({
            "from": {"table": "orders"},
            "transforms": [
                {
                    "type": "group_by",
                    "dimensions": ["user_id"],
                    "aggregates": [
                        {"function": "sum", "column": "amount", "alias": "total"}
                    ]
                }
            ]
        })
        sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
        assert "GROUP BY" in sql.upper()

    def test_combined_transforms(self):
        """Test multiple transforms together."""
        json_input = json.dumps({
            "from": {"table": "users"},
            "transforms": [
                {
                    "type": "where",
                    "condition": {
                        "type": "binary_op",
                        "operator": "=",
                        "left": {"type": "column", "name": "status"},
                        "right": {"type": "literal", "value": "active", "data_type": "string"}
                    }
                },
                {
                    "type": "order_by",
                    "expressions": [{"column": "name", "direction": "asc"}]
                },
                {"type": "limit", "count": 10}
            ]
        })
        sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
        assert "WHERE" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()


def get_first_pipeline(json_out: str):
    """Helper to get the first pipeline from array format."""
    result = json.loads(json_out)
    if isinstance(result, list):
        return result[0] if result else {}
    return result


class TestSQLToJSON:
    """Test SQL input -> JSON output."""

    def test_simple_select(self):
        """Test simple SELECT * FROM."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users", read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        assert result["from"]["table"] == "users"
        assert isinstance(result["transforms"], list)

    def test_where_extracted(self):
        """Test WHERE clause is extracted."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE id = 1", read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        where_transforms = [t for t in result["transforms"] if t["type"] == "where"]
        assert len(where_transforms) == 1
        assert where_transforms[0]["condition"]["op"] == "="

    def test_limit_extracted(self):
        """Test LIMIT clause is extracted."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users LIMIT 10", read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        limit_transforms = [t for t in result["transforms"] if t["type"] == "limit"]
        assert len(limit_transforms) == 1
        assert limit_transforms[0]["count"] == 10

    def test_offset_extracted(self):
        """Test OFFSET clause is extracted."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users LIMIT 10 OFFSET 20", read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        offset_transforms = [t for t in result["transforms"] if t["type"] == "offset"]
        assert len(offset_transforms) == 1
        assert offset_transforms[0]["count"] == 20

    def test_order_by_extracted(self):
        """Test ORDER BY clause is extracted."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users ORDER BY name DESC", read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        order_transforms = [t for t in result["transforms"] if t["type"] == "order_by"]
        assert len(order_transforms) == 1
        assert order_transforms[0]["expressions"][0]["column"] == "name"
        assert order_transforms[0]["expressions"][0]["direction"] == "desc"

    def test_join_extracted(self):
        """Test JOIN is extracted."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        join_transforms = [t for t in result["transforms"] if t["type"] == "join"]
        assert len(join_transforms) == 1
        assert join_transforms[0]["join_type"] == "left"
        assert join_transforms[0]["table"] == "orders"

    def test_group_by_extracted(self):
        """Test GROUP BY is extracted."""
        json_out = sqlglot.transpile(
            "SELECT region, SUM(amount) as total FROM orders GROUP BY region",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        group_transforms = [t for t in result["transforms"] if t["type"] == "group_by"]
        assert len(group_transforms) == 1
        assert "region" in group_transforms[0]["dimensions"]


class TestRoundtrip:
    """Test roundtrip JSON -> SQL -> JSON."""

    def test_basic_roundtrip(self):
        """Test basic query roundtrip."""
        original_json = {
            "from": {"table": "users"},
            "transforms": [
                {
                    "type": "where",
                    "condition": {
                        "type": "binary_op",
                        "operator": "=",
                        "left": {"type": "column", "name": "status"},
                        "right": {"type": "literal", "value": "active", "data_type": "string"}
                    }
                },
                {"type": "limit", "count": 10}
            ]
        }
        
        # JSON -> SQL
        sql = sqlglot.transpile(
            json.dumps(original_json), read="visual_asql", write="postgres"
        )[0]
        
        # SQL -> JSON
        result_json = sqlglot.transpile(sql, read="postgres", write="visual_asql")[0]
        result = get_first_pipeline(result_json)
        
        # Verify key elements preserved
        assert result["from"]["table"] == "users"
        
        where_transforms = [t for t in result["transforms"] if t["type"] == "where"]
        assert len(where_transforms) == 1
        
        limit_transforms = [t for t in result["transforms"] if t["type"] == "limit"]
        assert len(limit_transforms) == 1
        assert limit_transforms[0]["count"] == 10


class TestOutputColumnsWithSchema:
    """Test output_columns tracking with schema."""

    @pytest.fixture
    def schema(self):
        """Create test schema."""
        return MappingSchema({
            'users': {'id': 'INT', 'name': 'VARCHAR', 'email': 'VARCHAR', 'status': 'VARCHAR'},
            'orders': {'id': 'INT', 'user_id': 'INT', 'amount': 'DECIMAL', 'created_at': 'TIMESTAMP'}
        })

    def test_from_output_columns(self, schema):
        """Test output_columns in FROM clause."""
        ast = sqlglot.parse_one("SELECT * FROM users", read="postgres")
        gen = VisualASQLGenerator(schema=schema)
        result = get_first_pipeline(gen.generate(ast))
        
        output_cols = result["from"]["output_columns"]
        assert len(output_cols) == 4
        
        # Column names are unqualified for single-table queries (no JOINs)
        col_names = {c["name"] for c in output_cols}
        assert col_names == {"id", "name", "email", "status"}
        
        # Check types
        id_col = next(c for c in output_cols if c["name"] == "id")
        assert id_col["type"] == "INT"

    def test_where_preserves_columns(self, schema):
        """Test WHERE doesn't change output columns."""
        ast = sqlglot.parse_one("SELECT * FROM users WHERE id = 1", read="postgres")
        gen = VisualASQLGenerator(schema=schema)
        result = get_first_pipeline(gen.generate(ast))
        
        from_cols = result["from"]["output_columns"]
        where_transforms = [t for t in result["transforms"] if t["type"] == "where"]
        where_cols = where_transforms[0]["output_columns"]
        
        # Same columns before and after WHERE
        assert len(from_cols) == len(where_cols)

    def test_join_accumulates_columns(self, schema):
        """Test JOIN adds columns from joined table."""
        ast = sqlglot.parse_one(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id",
            read="postgres"
        )
        gen = VisualASQLGenerator(schema=schema)
        result = get_first_pipeline(gen.generate(ast))
        
        from_cols = result["from"]["output_columns"]
        join_transforms = [t for t in result["transforms"] if t["type"] == "join"]
        join_cols = join_transforms[0]["output_columns"]
        
        # FROM has 4 columns, JOIN adds 4 more = 8 total
        assert len(from_cols) == 4
        assert len(join_cols) == 8

    def test_group_by_changes_columns(self, schema):
        """Test GROUP BY changes output columns to dimensions + aggregates."""
        ast = sqlglot.parse_one(
            "SELECT name, SUM(amount) as total FROM users JOIN orders ON users.id = orders.user_id GROUP BY name",
            read="postgres"
        )
        gen = VisualASQLGenerator(schema=schema)
        result = get_first_pipeline(gen.generate(ast))
        
        group_transforms = [t for t in result["transforms"] if t["type"] == "group_by"]
        group_cols = group_transforms[0]["output_columns"]
        
        # Should have dimension (name) + aggregate (total)
        assert len(group_cols) == 2
        col_names = {c["name"] for c in group_cols}
        assert col_names == {"name", "total"}


class TestExpressionToJSON:
    """Test expression conversion to JSON."""

    def test_column_expression(self):
        """Test column reference."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE name = 'test'", read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["left"]["type"] == "column"
        assert condition["left"]["name"] == "name"

    def test_literal_string(self):
        """Test string literal."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE status = 'active'", read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["right"]["type"] == "literal"
        assert condition["right"]["value"] == "active"
        assert condition["right"]["data_type"] == "string"

    def test_literal_number(self):
        """Test numeric literal."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE id = 42", read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["right"]["type"] == "literal"
        assert condition["right"]["value"] == 42
        assert condition["right"]["data_type"] == "number"

    def test_comparison_operators(self):
        """Test various comparison operators."""
        operators = [
            ("=", "="),
            ("!=", "!="),
            ("<", "<"),
            (">", ">"),
            ("<=", "<="),
            (">=", ">="),
        ]
        
        for sql_op, expected_op in operators:
            json_out = sqlglot.transpile(
                f"SELECT * FROM users WHERE id {sql_op} 1", read="postgres", write="visual_asql"
            )[0]
            result = get_first_pipeline(json_out)
            condition = result["transforms"][0]["condition"]
            assert condition["op"] == expected_op, f"Failed for operator {sql_op}"

    def test_logical_and(self):
        """Test AND operator."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE id = 1 AND status = 'active'",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "binary"
        assert condition["op"] == "AND"

    def test_logical_or(self):
        """Test OR operator."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE id = 1 OR status = 'active'",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "binary"
        assert condition["op"] == "OR"


class TestErrorCases:
    """Test error handling."""

    def test_invalid_json_structure(self):
        """Test error on invalid JSON structure."""
        # Valid JSON but wrong structure - causes parse error due to missing table
        json_input = '{"invalid": "structure"}'
        # This raises an error when json_to_asql produces invalid ASQL
        with pytest.raises((ValueError, Exception)):
            sqlglot.transpile(json_input, read="visual_asql", write="postgres")

    def test_empty_transforms_array(self):
        """Test empty transforms array."""
        json_input = json.dumps({
            "from": {"table": "users"},
            "transforms": []
        })
        sql = sqlglot.transpile(json_input, read="visual_asql", write="postgres")[0]
        assert "FROM" in sql.upper()
        assert "users" in sql.lower()

    def test_missing_from_table(self):
        """Test missing from table raises error."""
        json_input = json.dumps({
            "from": {},
            "transforms": []
        })
        # Missing table name causes parse error
        with pytest.raises((ValueError, Exception)):
            sqlglot.transpile(json_input, read="visual_asql", write="postgres")

    def test_malformed_transform(self):
        """Test malformed transform is skipped gracefully."""
        json_input = json.dumps({
            "from": {"table": "users"},
            "transforms": [{"type": "nonexistent_transform"}]
        })
        # Unknown transform types are skipped
        result = sqlglot.transpile(json_input, read="visual_asql", write="postgres")
        assert result is not None


class TestHavingClause:
    """Test HAVING clause extraction."""

    def test_having_extracted(self):
        """Test HAVING clause is extracted."""
        json_out = sqlglot.transpile(
            "SELECT region, SUM(amount) as total FROM orders GROUP BY region HAVING SUM(amount) > 1000",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        having_transforms = [t for t in result["transforms"] if t["type"] == "having"]
        assert len(having_transforms) == 1
        assert having_transforms[0]["condition"] is not None


class TestMultipleJoins:
    """Test multiple JOIN handling."""

    def test_multiple_joins_accumulated(self):
        """Test multiple JOINs accumulate columns."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id JOIN products ON orders.product_id = products.id",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        join_transforms = [t for t in result["transforms"] if t["type"] == "join"]
        assert len(join_transforms) == 2
        assert join_transforms[0]["table"] == "orders"
        assert join_transforms[1]["table"] == "products"

    def test_mixed_join_types(self):
        """Test mixed join types are preserved."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users LEFT JOIN orders ON users.id = orders.user_id INNER JOIN products ON orders.product_id = products.id",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        join_transforms = [t for t in result["transforms"] if t["type"] == "join"]
        assert join_transforms[0]["join_type"] == "left"
        assert join_transforms[1]["join_type"] == "inner"


class TestNullConditions:
    """Test IS NULL / IS NOT NULL handling."""

    def test_is_null(self):
        """Test IS NULL condition extraction."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE email IS NULL",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "null_check"
        assert condition["operator"] == "is null"
        assert condition["operand"]["name"] == "email"

    def test_is_not_null(self):
        """Test IS NOT NULL condition extraction."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE email IS NOT NULL",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        # IS NOT NULL is represented as NOT(IS NULL)
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "unary_op"
        assert condition["operator"] == "not"


class TestBetweenConditions:
    """Test BETWEEN clause handling."""

    def test_between_numbers(self):
        """Test BETWEEN with numeric values."""
        json_out = sqlglot.transpile(
            "SELECT * FROM orders WHERE amount BETWEEN 100 AND 500",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "between"
        assert condition["operand"]["name"] == "amount"
        assert condition["low"]["value"] == 100
        assert condition["high"]["value"] == 500

    def test_between_strings(self):
        """Test BETWEEN with string values."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE name BETWEEN 'A' AND 'M'",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "between"
        assert condition["low"]["value"] == "A"
        assert condition["high"]["value"] == "M"


class TestInConditions:
    """Test IN clause handling."""

    def test_in_with_numbers(self):
        """Test IN with numeric values."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE id IN (1, 2, 3)",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "in"
        assert condition["operand"]["name"] == "id"
        assert len(condition["values"]) == 3
        assert condition["values"][0]["value"] == 1

    def test_in_with_strings(self):
        """Test IN with string values."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE status IN ('active', 'pending', 'approved')",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "in"
        assert len(condition["values"]) == 3
        values = [v["value"] for v in condition["values"]]
        assert "active" in values
        assert "pending" in values


class TestNestedConditions:
    """Test nested/complex condition handling."""

    def test_parenthesized_or(self):
        """Test parenthesized OR within AND."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE status = 'active' AND (role = 'admin' OR role = 'superuser')",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "binary"
        assert condition["op"] == "AND"
        # Right side should be the OR condition
        assert condition["right"]["op"] == "OR"

    def test_deeply_nested(self):
        """Test deeply nested conditions."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE (a = 1 AND b = 2) OR (c = 3 AND d = 4)",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "binary"
        assert condition["op"] == "OR"
        assert condition["left"]["op"] == "AND"
        assert condition["right"]["op"] == "AND"

    def test_not_condition(self):
        """Test NOT operator."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE NOT (status = 'deleted')",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "unary_op"
        assert condition["operator"] == "not"


class TestLikeConditions:
    """Test LIKE clause handling."""

    def test_like_pattern(self):
        """Test LIKE with pattern."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE name LIKE '%john%'",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "like"
        assert condition["operand"]["name"] == "name"
        assert condition["pattern"]["value"] == "%john%"


class TestFunctionConditions:
    """Test function call handling in conditions."""

    def test_function_in_condition(self):
        """Test function call in WHERE condition."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users WHERE UPPER(name) = 'JOHN'",
            read="postgres", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        condition = result["transforms"][0]["condition"]
        assert condition["type"] == "binary"
        assert condition["left"]["type"] == "function"
        assert condition["left"]["name"] == "UPPER"


class TestASQLSpecificFeatures:
    """Test ASQL-specific features through visual_asql."""

    def test_asql_pipe_syntax(self):
        """Test ASQL pipe syntax is preserved through JSON."""
        # ASQL -> JSON
        json_out = sqlglot.transpile(
            "from users where status == 'active' limit 10",
            read="asql", write="visual_asql"
        )[0]
        result = get_first_pipeline(json_out)
        
        assert result["from"]["table"] == "users"
        
        where_transforms = [t for t in result["transforms"] if t["type"] == "where"]
        assert len(where_transforms) == 1
        
        limit_transforms = [t for t in result["transforms"] if t["type"] == "limit"]
        assert len(limit_transforms) == 1

    def test_json_to_asql_to_sql(self):
        """Test JSON -> ASQL -> SQL chain."""
        json_input = json.dumps({
            "from": {"table": "users"},
            "transforms": [
                {
                    "type": "where",
                    "condition": {
                        "type": "binary_op",
                        "operator": "=",
                        "left": {"type": "column", "name": "status"},
                        "right": {"type": "literal", "value": "active", "data_type": "string"}
                    }
                }
            ]
        })
        
        # JSON -> ASQL
        asql_out = sqlglot.transpile(json_input, read="visual_asql", write="asql")[0]
        assert "from users" in asql_out.lower()
        assert "where" in asql_out.lower()
        
        # ASQL -> SQL
        sql_out = sqlglot.transpile(asql_out, read="asql", write="postgres")[0]
        assert "SELECT" in sql_out.upper()
        assert "FROM" in sql_out.upper() and "USERS" in sql_out.upper()
        assert "WHERE" in sql_out.upper()


class TestArrayFormat:
    """Tests for array format output (CTEs, set operations)."""

    def test_output_is_always_array(self):
        """Test that generator always outputs array format."""
        json_out = sqlglot.transpile(
            "SELECT * FROM users", read="postgres", write="visual_asql"
        )[0]
        result = json.loads(json_out)
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] is None  # Final output pipeline

    def test_union_generates_array(self):
        """Test UNION produces array of pipelines."""
        json_out = sqlglot.transpile(
            "SELECT id FROM users UNION SELECT id FROM admins",
            read="postgres", write="visual_asql"
        )[0]
        result = json.loads(json_out)
        
        assert isinstance(result, list)
        assert len(result) == 2
        # First pipeline should have set_operation
        assert result[0].get("set_operation", {}).get("type") == "union"
        # Check tables
        assert result[0]["from"]["table"] == "users"
        assert result[1]["from"]["table"] == "admins"

    def test_union_all_generates_array(self):
        """Test UNION ALL produces correct set_operation flags."""
        json_out = sqlglot.transpile(
            "SELECT id FROM users UNION ALL SELECT id FROM admins",
            read="postgres", write="visual_asql"
        )[0]
        result = json.loads(json_out)
        
        assert result[0]["set_operation"]["type"] == "union"
        assert result[0]["set_operation"]["all"] is True

    def test_intersect_generates_array(self):
        """Test INTERSECT produces array of pipelines."""
        json_out = sqlglot.transpile(
            "SELECT id FROM users INTERSECT SELECT id FROM active_users",
            read="postgres", write="visual_asql"
        )[0]
        result = json.loads(json_out)
        
        assert len(result) == 2
        assert result[0]["set_operation"]["type"] == "intersect"

    def test_except_generates_array(self):
        """Test EXCEPT produces array of pipelines."""
        json_out = sqlglot.transpile(
            "SELECT id FROM users EXCEPT SELECT id FROM banned",
            read="postgres", write="visual_asql"
        )[0]
        result = json.loads(json_out)
        
        assert len(result) == 2
        assert result[0]["set_operation"]["type"] == "except"

    def test_cte_generates_named_pipelines(self):
        """Test CTEs generate named pipelines."""
        json_out = sqlglot.transpile(
            "WITH active AS (SELECT * FROM users WHERE status = 'active') SELECT * FROM active",
            read="postgres", write="visual_asql"
        )[0]
        result = json.loads(json_out)
        
        assert isinstance(result, list)
        assert len(result) == 2
        
        # First is the CTE
        assert result[0]["name"] == "active"
        assert result[0]["from"]["table"] == "users"
        
        # Second is the main query
        assert result[1]["name"] is None
        assert result[1]["from"]["table"] == "active"

    def test_multiple_ctes(self):
        """Test multiple CTEs generate multiple named pipelines."""
        json_out = sqlglot.transpile(
            """
            WITH 
                active AS (SELECT * FROM users WHERE status = 'active'),
                orders_2024 AS (SELECT * FROM orders WHERE year = 2024)
            SELECT * FROM active JOIN orders_2024 ON active.id = orders_2024.user_id
            """,
            read="postgres", write="visual_asql"
        )[0]
        result = json.loads(json_out)
        
        assert len(result) == 3
        assert result[0]["name"] == "active"
        assert result[1]["name"] == "orders_2024"
        assert result[2]["name"] is None  # Main query
