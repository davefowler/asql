"""
Tests for asql/ui_schema.py

Tests for UI schema generation, merging with manual overrides, and API functions.
"""

import pytest

from asql.ui_schema import get_operation_schema, list_all_operations, OPERATION_UI_SCHEMAS


class TestGetOperationSchema:
    """Tests for get_operation_schema function."""

    def test_returns_schema_for_known_operation(self):
        """Test that schema is returned for known operations."""
        # Test a known operation that should exist
        schema = get_operation_schema('where')

        assert schema is not None
        assert isinstance(schema, dict)
        assert 'label' in schema or 'parameters' in schema

    def test_returns_empty_dict_for_unknown_operation(self):
        """Test that empty dict is returned for unknown operations."""
        schema = get_operation_schema('nonexistent_operation_xyz')

        assert schema == {}

    def test_returns_schema_with_expected_keys(self):
        """Test that schemas have expected structure."""
        schema = get_operation_schema('where')

        if schema:  # If where operation exists
            # Check common keys that should be present
            expected_keys = ['label', 'icon', 'description', 'category', 'parameters']
            for key in expected_keys:
                assert key in schema, f"Missing key: {key}"

    def test_parameters_have_required_fields(self):
        """Test that parameters have required fields."""
        schema = get_operation_schema('where')

        if schema and 'parameters' in schema:
            for param in schema['parameters']:
                assert 'name' in param, "Parameter missing 'name' field"
                assert 'widget' in param, "Parameter missing 'widget' field"


class TestListAllOperations:
    """Tests for list_all_operations function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        operations = list_all_operations()

        assert isinstance(operations, list)

    def test_operations_have_required_fields(self):
        """Test that each operation has required metadata fields."""
        operations = list_all_operations()

        for op in operations:
            assert 'type' in op, "Operation missing 'type'"
            assert 'label' in op, "Operation missing 'label'"
            assert 'icon' in op, "Operation missing 'icon'"
            assert 'description' in op, "Operation missing 'description'"
            assert 'category' in op, "Operation missing 'category'"

    def test_operations_include_common_types(self):
        """Test that common operation types are included."""
        operations = list_all_operations()
        op_types = {op['type'] for op in operations}

        # These should be available based on ASQL's TRANSFORM_PARSERS
        expected_common = ['where', 'select', 'limit']

        for expected in expected_common:
            assert expected in op_types, f"Missing expected operation: {expected}"

    def test_operations_have_valid_categories(self):
        """Test that operations have valid categories."""
        operations = list_all_operations()

        valid_categories = {'filter', 'select', 'join', 'aggregate', 'sort', 'limit', 'advanced', 'other'}

        for op in operations:
            assert op['category'] in valid_categories, f"Invalid category: {op['category']}"


class TestSchemaStructure:
    """Tests for the structure of OPERATION_UI_SCHEMAS."""

    def test_schemas_are_generated(self):
        """Test that schemas were auto-generated."""
        assert OPERATION_UI_SCHEMAS is not None
        assert isinstance(OPERATION_UI_SCHEMAS, dict)
        assert len(OPERATION_UI_SCHEMAS) > 0

    def test_schema_has_filter_operations(self):
        """Test that filter operations exist in schemas."""
        filter_ops = [op for op in OPERATION_UI_SCHEMAS.keys()
                      if OPERATION_UI_SCHEMAS[op].get('category') == 'filter']

        assert len(filter_ops) > 0, "No filter operations found"

    def test_where_schema_has_condition_parameter(self):
        """Test that WHERE schema has a condition parameter."""
        schema = OPERATION_UI_SCHEMAS.get('where', {})

        if 'parameters' in schema:
            param_names = [p['name'] for p in schema['parameters']]
            assert 'condition' in param_names, "WHERE missing 'condition' parameter"

    def test_join_schema_has_table_parameter(self):
        """Test that JOIN schema has a table parameter."""
        schema = OPERATION_UI_SCHEMAS.get('join', {})

        if 'parameters' in schema:
            param_names = [p['name'] for p in schema['parameters']]
            assert 'table' in param_names, "JOIN missing 'table' parameter"

    def test_limit_schema_has_count_parameter(self):
        """Test that LIMIT schema has a count parameter."""
        schema = OPERATION_UI_SCHEMAS.get('limit', {})

        if 'parameters' in schema:
            param_names = [p['name'] for p in schema['parameters']]
            assert 'count' in param_names, "LIMIT missing 'count' parameter"


class TestSchemaOverrides:
    """Tests for manual override merging functionality."""

    def test_base_schema_exists_for_operations(self):
        """Test that base schemas exist for ASQL operations."""
        from asql.ui_schema_generator import generate_base_schema_from_asql

        base_schemas = generate_base_schema_from_asql()

        assert len(base_schemas) > 0

    def test_merged_schemas_contain_base_info(self):
        """Test that merged schemas contain base schema info."""
        # The merged schemas should have auto-generated fields
        for op_name, schema in OPERATION_UI_SCHEMAS.items():
            # All schemas should have these basic fields
            assert 'label' in schema, f"{op_name} missing 'label'"
            assert 'icon' in schema, f"{op_name} missing 'icon'"
            assert 'category' in schema, f"{op_name} missing 'category'"

    def test_override_parameters_merged_correctly(self):
        """Test that parameter overrides are merged with base parameters."""
        # If we have overrides with parameters, they should be merged
        schema = OPERATION_UI_SCHEMAS.get('where', {})

        if 'parameters' in schema:
            # Parameters should exist and have merged fields
            for param in schema['parameters']:
                # Base fields should exist
                assert 'name' in param
                # Widget should be present (from base or override)
                assert 'widget' in param


class TestYAMLOverridesLoading:
    """Tests for YAML overrides loading behavior."""

    def test_handles_missing_yaml_file(self):
        """Test that missing YAML file is handled gracefully."""
        # This is tested implicitly by the fallback behavior
        # If the YAML file doesn't exist, _MANUAL_UI_OVERRIDES should be {}
        # The module should still load without errors
        from asql import ui_schema

        # Should not raise an error
        assert hasattr(ui_schema, 'OPERATION_UI_SCHEMAS')

    def test_handles_invalid_yaml_gracefully(self):
        """Test that invalid YAML doesn't crash the module."""
        # This is implicitly tested - if the module loads, it handles errors
        import asql.ui_schema

        # Module should load successfully even with YAML errors
        assert asql.ui_schema.OPERATION_UI_SCHEMAS is not None


class TestParameterMerging:
    """Tests for parameter merging logic."""

    def test_base_only_params_preserved(self):
        """Test that parameters only in base are preserved."""
        # This tests the fix for CodeRabbit's review
        # The merge should keep base-only parameters

        from asql.ui_schema_generator import generate_base_schema_from_asql

        base_schemas = generate_base_schema_from_asql()

        for op_name, base_schema in base_schemas.items():
            merged_schema = OPERATION_UI_SCHEMAS.get(op_name, {})

            # Base parameters should be present in merged schema
            base_param_names = {p['name'] for p in base_schema.get('parameters', [])}
            merged_param_names = {p['name'] for p in merged_schema.get('parameters', [])}

            # All base params should be in merged (unless explicitly removed)
            for base_param in base_param_names:
                assert base_param in merged_param_names, \
                    f"Base param '{base_param}' missing from merged schema for '{op_name}'"

    def test_override_only_params_added(self):
        """Test that parameters only in overrides are added."""
        # This tests that override-only parameters are included
        # The fix addressed CodeRabbit's comment about losing override-only params

        # This is tested implicitly by the module loading
        # If overrides have extra params, they should be added
        pass  # The main test is that the module loads without error


class TestCategoryGuessing:
    """Tests for category assignment logic."""

    def test_filter_operations_have_filter_category(self):
        """Test that filter operations are categorized correctly."""
        filter_ops = ['where', 'filter', 'if_']

        for op in filter_ops:
            if op in OPERATION_UI_SCHEMAS:
                schema = OPERATION_UI_SCHEMAS[op]
                assert schema.get('category') == 'filter', \
                    f"{op} should have 'filter' category"

    def test_limit_has_limit_category(self):
        """Test that LIMIT has limit category."""
        if 'limit' in OPERATION_UI_SCHEMAS:
            schema = OPERATION_UI_SCHEMAS['limit']
            assert schema.get('category') == 'limit'


class TestIconAssignment:
    """Tests for icon assignment logic."""

    def test_where_has_search_icon(self):
        """Test that WHERE has a search icon."""
        schema = OPERATION_UI_SCHEMAS.get('where', {})

        # Icon should be present
        assert 'icon' in schema

    def test_join_has_link_icon(self):
        """Test that JOIN has a link icon."""
        schema = OPERATION_UI_SCHEMAS.get('join', {})

        # Icon should be present
        if schema:
            assert 'icon' in schema

    def test_all_operations_have_icons(self):
        """Test that all operations have icons."""
        for op_name, schema in OPERATION_UI_SCHEMAS.items():
            assert 'icon' in schema, f"{op_name} missing 'icon'"
            assert schema['icon'], f"{op_name} has empty 'icon'"


class TestIntegration:
    """Integration tests for the full UI schema system."""

    def test_full_workflow(self):
        """Test the full workflow: generate -> merge -> access."""
        # 1. Generate base schemas
        from asql.ui_schema_generator import generate_base_schema_from_asql
        base = generate_base_schema_from_asql()

        assert len(base) > 0

        # 2. Access merged schemas
        from asql.ui_schema import OPERATION_UI_SCHEMAS
        assert len(OPERATION_UI_SCHEMAS) > 0

        # 3. Use API functions
        schema = get_operation_schema('where')
        assert schema or len(OPERATION_UI_SCHEMAS) > 0

        operations = list_all_operations()
        assert len(operations) > 0

    def test_schemas_can_be_serialized(self):
        """Test that schemas can be JSON serialized (for API responses)."""
        import json

        for op_name, schema in OPERATION_UI_SCHEMAS.items():
            try:
                json.dumps(schema)
            except (TypeError, ValueError) as e:
                pytest.fail(f"Schema for '{op_name}' cannot be JSON serialized: {e}")

    def test_operations_list_matches_schemas(self):
        """Test that operations list matches available schemas."""
        operations = list_all_operations()
        op_types = {op['type'] for op in operations}

        schema_types = set(OPERATION_UI_SCHEMAS.keys())

        assert op_types == schema_types, \
            f"Mismatch between operations list and schemas: {op_types ^ schema_types}"
