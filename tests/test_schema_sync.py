"""
Tests to validate that ui-metadata.json stays in sync with the parser.

These tests ensure that the UI metadata (asql/ui-metadata.json) contains entries
for all features that the parser (asql/dialect.py) supports, and vice versa.
"""

import json
from pathlib import Path



def get_schema():
    """Load ui-metadata.json."""
    schema_path = Path(__file__).parent.parent / "asql" / "ui-metadata.json"
    with open(schema_path) as f:
        return json.load(f)


class TestTransformsSync:
    """Test that schema transforms match parser TRANSFORM_PARSERS."""

    def test_all_parser_transforms_in_schema(self):
        """Every parser transform should have a schema entry."""
        from asql.dialect import ASQLParser

        schema = get_schema()
        schema_transforms = set(schema["transforms"].keys())

        # Get parser transforms, normalize to lowercase with underscores
        parser_transforms = set()
        for key in ASQLParser.TRANSFORM_PARSERS.keys():
            # Skip internal ASQL_ prefixed keys (these are implementation details)
            if key.startswith("ASQL_"):
                continue
            # Normalize: "ORDER BY" -> "order_by", "WHERE" -> "where"
            normalized = key.lower().replace(" ", "_")
            parser_transforms.add(normalized)

        missing_in_schema = parser_transforms - schema_transforms
        assert not missing_in_schema, f"Parser transforms missing from ui-metadata.json: {missing_in_schema}"

    def test_all_schema_transforms_in_parser(self):
        """Every schema transform should exist in parser."""
        from asql.dialect import ASQLParser

        schema = get_schema()
        schema_transforms = set(schema["transforms"].keys())

        # Build set of normalized parser transforms
        parser_transforms = set()
        for key in ASQLParser.TRANSFORM_PARSERS.keys():
            if key.startswith("ASQL_"):
                continue
            normalized = key.lower().replace(" ", "_")
            parser_transforms.add(normalized)

        extra_in_schema = schema_transforms - parser_transforms
        assert not extra_in_schema, f"Schema transforms not in parser: {extra_in_schema}"

    def test_transform_keywords_match(self):
        """Schema keywords should match what parser expects."""
        from asql.dialect import ASQLParser

        schema = get_schema()

        for transform_name, transform_data in schema["transforms"].items():
            keywords = transform_data.get("keywords", [])
            if not keywords:
                continue

            # Check that at least one keyword is recognized by parser
            parser_keys = {k.upper() for k in ASQLParser.TRANSFORM_PARSERS.keys()}
            found = any(kw.upper() in parser_keys or kw.upper().replace(" ", "_") in parser_keys 
                       for kw in keywords)
            
            # Allow transforms that use SQL keywords (JOIN, LEFT, etc) which go through different paths
            sql_join_keywords = {"LEFT", "RIGHT", "FULL", "CROSS", "JOIN"}
            is_sql_keyword = any(kw.upper() in sql_join_keywords for kw in keywords)
            
            assert found or is_sql_keyword, \
                f"Transform '{transform_name}' keywords {keywords} not found in parser"


class TestJoinsSync:
    """Test that schema joins match parser join handling."""

    def test_all_join_types_have_symbols(self):
        """Each join type should have a symbol defined."""
        schema = get_schema()
        
        for join_name, join_data in schema["joins"].items():
            assert "symbol" in join_data, f"Join '{join_name}' missing symbol"
            assert "kind" in join_data, f"Join '{join_name}' missing kind"

    def test_join_symbols_are_valid(self):
        """Join symbols should be the expected ASQL symbols."""
        schema = get_schema()
        
        expected_symbols = {"&", "&?", "?&", "?&?", "*"}
        actual_symbols = {j["symbol"] for j in schema["joins"].values()}
        
        assert actual_symbols == expected_symbols, \
            f"Unexpected join symbols. Expected {expected_symbols}, got {actual_symbols}"


class TestOperatorsSync:
    """Test that schema operators are complete."""

    def test_comparison_operators_complete(self):
        """Schema should have all standard comparison operators."""
        schema = get_schema()
        comparison = schema["operators"]["comparison"]
        
        expected = {">", ">=", "<", "<=", "=", "!="}
        actual = set(comparison.keys())
        
        missing = expected - actual
        assert not missing, f"Missing comparison operators: {missing}"

    def test_string_operators_match_parser(self):
        """String operators in schema should match parser's string_ops dict."""
        
        schema = get_schema()
        schema_ops = set(schema["operators"]["string"].keys())
        
        # Get string operators from parser (defined in _parse_comparison)
        # These are the token sequences the parser recognizes
        parser_ops = {
            "contains",      # ("CONTAINS",)
            "icontains",     # ("ICONTAINS",)
            "starts with",   # ("STARTS", "WITH")
            "istarts with",  # ("ISTARTS", "WITH")
            "ends with",     # ("ENDS", "WITH")
            "iends with",    # ("IENDS", "WITH")
            "matches",       # ("MATCHES",)
        }
        
        missing_in_schema = parser_ops - schema_ops
        extra_in_schema = schema_ops - parser_ops
        
        assert not missing_in_schema, f"Parser string ops missing from schema: {missing_in_schema}"
        assert not extra_in_schema, f"Schema string ops not in parser: {extra_in_schema}"

    def test_string_operators_have_case_sensitivity(self):
        """String operators should indicate case sensitivity."""
        schema = get_schema()
        string_ops = schema["operators"]["string"]
        
        for op_name, op_data in string_ops.items():
            assert "case_sensitive" in op_data, \
                f"String operator '{op_name}' missing case_sensitive field"


class TestAggregatesSync:
    """Test that schema aggregates are complete."""

    def test_basic_aggregates_present(self):
        """Schema should have all basic aggregate functions."""
        schema = get_schema()
        aggregates = schema["aggregates"]
        
        expected = {"count", "sum", "avg", "min", "max"}
        actual = set(aggregates.keys())
        
        missing = expected - actual
        assert not missing, f"Missing basic aggregates: {missing}"

    def test_aggregates_have_labels(self):
        """Each aggregate should have a label and description."""
        schema = get_schema()
        
        for name, agg in schema["aggregates"].items():
            assert "label" in agg, f"Aggregate '{name}' missing label"
            assert "description" in agg, f"Aggregate '{name}' missing description"


class TestFunctionsSync:
    """Test that schema functions are complete."""

    def test_asql_functions_in_schema(self):
        """ASQL-specific functions should be in schema."""
        
        schema = get_schema()
        functions = schema.get("functions", {})
        
        # Flatten all function names from schema
        schema_funcs = set()
        for category, funcs in functions.items():
            for func_name in funcs.keys():
                schema_funcs.add(func_name.upper())
        
        # Check key ASQL functions are present (not all aliases, just primary ones)
        expected_asql_funcs = {
            "DAYS_SINCE", "WEEKS_SINCE", "MONTHS_SINCE", "YEARS_SINCE",
            "DAYS_UNTIL", "WEEKS_UNTIL", "MONTHS_UNTIL", "YEARS_UNTIL",
            "RUNNING_SUM", "RUNNING_AVG", "ROLLING_SUM", "ROLLING_AVG",
            "FILL_FORWARD", "FILL_BACKWARD"
        }
        
        for func in expected_asql_funcs:
            assert func in schema_funcs, f"ASQL function '{func}' missing from schema"

    def test_function_categories_exist(self):
        """Functions should be organized by category."""
        schema = get_schema()
        functions = schema.get("functions", {})
        
        expected_categories = {"date", "string", "math", "conditional", "window"}
        actual_categories = set(functions.keys())
        
        missing = expected_categories - actual_categories
        assert not missing, f"Missing function categories: {missing}"

    def test_functions_have_required_fields(self):
        """Each function should have label, description, args."""
        schema = get_schema()
        functions = schema.get("functions", {})
        
        for category, funcs in functions.items():
            for name, func in funcs.items():
                assert "label" in func, f"Function '{category}.{name}' missing label"
                assert "description" in func, f"Function '{category}.{name}' missing description"
                assert "args" in func, f"Function '{category}.{name}' missing args"


class TestSchemaStructure:
    """Test overall schema structure."""

    def test_required_top_level_keys(self):
        """Schema should have all required sections."""
        schema = get_schema()
        
        required = ["operators", "transforms", "joins", "aggregates"]
        for key in required:
            assert key in schema, f"Schema missing required section: {key}"

    def test_transforms_have_required_fields(self):
        """Each transform should have label, category, description."""
        schema = get_schema()
        
        for name, transform in schema["transforms"].items():
            assert "label" in transform, f"Transform '{name}' missing label"
            assert "category" in transform, f"Transform '{name}' missing category"
            assert "description" in transform, f"Transform '{name}' missing description"

    def test_aggregates_have_labels(self):
        """Each aggregate should have a label."""
        schema = get_schema()
        
        for name, agg in schema["aggregates"].items():
            assert "label" in agg, f"Aggregate '{name}' missing label"

    def test_schema_is_valid_json(self):
        """Schema should be valid JSON (no trailing commas, etc)."""
        schema_path = Path(__file__).parent.parent / "asql" / "ui-metadata.json"
        
        # This will raise if JSON is invalid
        with open(schema_path) as f:
            json.load(f)


class TestUISchemaModule:
    """Test that ui_schema.py correctly loads the JSON."""

    def test_get_schema_returns_dict(self):
        """get_schema should return the full schema dict."""
        from asql.ui_schema import get_schema
        
        schema = get_schema()
        assert isinstance(schema, dict)
        assert "transforms" in schema

    def test_get_operation_schema(self):
        """get_operation_schema should return transform data."""
        from asql.ui_schema import get_operation_schema
        
        where_schema = get_operation_schema("where")
        assert where_schema.get("label") == "Filter"
        assert where_schema.get("category") == "filter"

    def test_list_all_operations(self):
        """list_all_operations should return all transforms."""
        from asql.ui_schema import list_all_operations
        
        ops = list_all_operations()
        assert isinstance(ops, list)
        assert len(ops) > 0
        
        op_types = {op["type"] for op in ops}
        assert "where" in op_types
        assert "select" in op_types
        assert "join" in op_types

    def test_transforms_schema_populated(self):
        """Transforms should be populated from JSON."""
        from asql.ui_schema import get_schema
        
        transforms = get_schema()["transforms"]
        assert isinstance(transforms, dict)
        assert len(transforms) > 0
        assert "where" in transforms
