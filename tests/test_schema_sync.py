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


def get_all_schema_functions():
    """Get all function names from ui-metadata.json (flattened across categories).
    
    Returns:
        tuple: (primary_funcs set, all_with_aliases set)
        - primary_funcs: Set of primary function names (uppercase)
        - all_with_aliases: Set of all function names including aliases (uppercase)
    """
    schema = get_schema()
    functions = schema.get("functions", {})
    
    primary_funcs = set()
    all_with_aliases = set()
    
    for category, funcs in functions.items():
        for func_name, func_data in funcs.items():
            upper_name = func_name.upper()
            primary_funcs.add(upper_name)
            all_with_aliases.add(upper_name)
            
            # Include aliases
            aliases = func_data.get("aliases", [])
            for alias in aliases:
                all_with_aliases.add(alias.upper())
    
    return primary_funcs, all_with_aliases


def get_all_schema_aggregates():
    """Get all aggregate names from ui-metadata.json.
    
    Returns:
        tuple: (primary_aggs set, all_with_aliases set)
    """
    schema = get_schema()
    aggregates = schema.get("aggregates", {})
    
    primary_aggs = set()
    all_with_aliases = set()
    
    for agg_name, agg_data in aggregates.items():
        upper_name = agg_name.upper()
        primary_aggs.add(upper_name)
        all_with_aliases.add(upper_name)
        
        # Include aliases
        aliases = agg_data.get("aliases", [])
        for alias in aliases:
            all_with_aliases.add(alias.upper())
    
    return primary_aggs, all_with_aliases


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
            "HOURS_SINCE", "MINUTES_SINCE", "SECONDS_SINCE",
            "DAYS_UNTIL", "WEEKS_UNTIL", "MONTHS_UNTIL", "YEARS_UNTIL",
            "HOURS_UNTIL", "MINUTES_UNTIL", "SECONDS_UNTIL",
            "RUNNING_SUM", "RUNNING_AVG", "RUNNING_COUNT", "RUNNING_MIN", "RUNNING_MAX",
            "ROLLING_SUM", "ROLLING_AVG", "ROLLING_COUNT", "ROLLING_MIN", "ROLLING_MAX",
            "FILL_FORWARD", "FILL_BACKWARD",
            "ARG_MAX", "ARG_MIN", "BUCKET"
        }
        
        for func in expected_asql_funcs:
            assert func in schema_funcs, f"ASQL function '{func}' missing from schema"

    def test_function_categories_exist(self):
        """Functions should be organized by category."""
        schema = get_schema()
        functions = schema.get("functions", {})
        
        expected_categories = {"date", "string", "math", "conditional", "window", "special"}
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
    
    def test_asql_function_registry_in_schema(self):
        """All ASQL_FUNCTION_REGISTRY entries should have ui-metadata.json entries.
        
        This ensures the central function registry is completely documented.
        Aliases are allowed to map to a primary function entry.
        """
        from asql.functions import ASQL_FUNCTION_REGISTRY
        
        _, all_with_aliases = get_all_schema_functions()
        
        # Get all ASQL function names from the registry
        registry_funcs = set(ASQL_FUNCTION_REGISTRY.keys())
        
        # Each registry function should be in schema (as primary or alias)
        missing = registry_funcs - all_with_aliases
        assert not missing, (
            f"ASQL_FUNCTION_REGISTRY functions missing from ui-metadata.json: {missing}\n"
            "Add these functions to the appropriate category in asql/ui-metadata.json"
        )
    
    def test_natural_agg_funcs_in_schema(self):
        """All NATURAL_AGG_FUNCS should be in ui-metadata.json.
        
        These functions support natural syntax like 'sum amount'.
        """
        from asql.functions import NATURAL_AGG_FUNCS
        
        _, all_with_aliases = get_all_schema_functions()
        primary_aggs, agg_with_aliases = get_all_schema_aggregates()
        
        # Combine functions and aggregates
        all_schema = all_with_aliases | agg_with_aliases
        
        # Get all natural agg function names
        natural_funcs = set(NATURAL_AGG_FUNCS.keys())
        
        # Each natural function should be in schema (as primary or alias)
        missing = natural_funcs - all_schema
        assert not missing, (
            f"NATURAL_AGG_FUNCS missing from ui-metadata.json: {missing}\n"
            "Add these functions to the appropriate category in asql/ui-metadata.json"
        )
    
    def test_schema_functions_have_parser_support(self):
        """All ui-metadata.json functions should be supported by the parser.
        
        Ensures no orphaned entries in the metadata that don't actually work.
        """
        from asql.functions import ASQL_FUNCTION_REGISTRY
        from asql.dialect import ASQLParser
        
        # Get ASQL-specific function names
        asql_funcs = set(ASQL_FUNCTION_REGISTRY.keys())
        # FUNCTION_PARSERS contains functions with custom parsing (like BUCKET)
        function_parsers = set(ASQLParser.FUNCTION_PARSERS.keys())
        
        # Get schema functions marked as asql_only
        schema = get_schema()
        functions = schema.get("functions", {})
        
        asql_only_funcs = set()
        for category, funcs in functions.items():
            for func_name, func_data in funcs.items():
                if func_data.get("asql_only"):
                    asql_only_funcs.add(func_name.upper())
                    # Also check aliases
                    for alias in func_data.get("aliases", []):
                        asql_only_funcs.add(alias.upper())
        
        # All ASQL-only functions should exist in ASQL_FUNCTION_REGISTRY or FUNCTION_PARSERS
        # (parser base functions like UPPER, LOWER don't need to be in registry)
        asql_supported = asql_funcs | function_parsers
        missing = asql_only_funcs - asql_supported
        assert not missing, (
            f"ui-metadata.json ASQL-only functions missing from parser: {missing}\n"
            "Either add these to asql/functions.py or parser FUNCTION_PARSERS, "
            "or remove asql_only flag"
        )
    
    def test_aggregate_aliases_documented(self):
        """Aggregate aliases should be documented in ui-metadata.json."""
        schema = get_schema()
        aggregates = schema.get("aggregates", {})
        
        # These are the expected aliases based on the parser
        expected_aliases = {
            "sum": ["total"],
            "avg": ["average"],
            "min": ["minimum"],
            "max": ["maximum"],
        }
        
        for agg_name, expected in expected_aliases.items():
            if agg_name in aggregates:
                actual = aggregates[agg_name].get("aliases", [])
                for alias in expected:
                    assert alias in actual, (
                        f"Aggregate '{agg_name}' missing alias '{alias}' in ui-metadata.json"
                    )
    
    def test_window_function_aliases_documented(self):
        """Window function aliases (prior, next) should be documented."""
        schema = get_schema()
        window_funcs = schema.get("functions", {}).get("window", {})
        
        # Check lag -> prior alias
        lag_aliases = window_funcs.get("lag", {}).get("aliases", [])
        assert "prior" in lag_aliases, "lag function missing 'prior' alias"
        
        # Check lead -> next alias
        lead_aliases = window_funcs.get("lead", {}).get("aliases", [])
        assert "next" in lead_aliases, "lead function missing 'next' alias"


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
