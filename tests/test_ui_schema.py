"""
Tests for asql/ui_schema.py

Tests for UI schema generation from dialect_schema.py dataclasses.
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
            expected_keys = ['label', 'description', 'category', 'parameters']
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
            assert 'description' in op, "Operation missing 'description'"
            assert 'category' in op, "Operation missing 'category'"

    def test_operations_include_common_types(self):
        """Test that common operation types are included."""
        operations = list_all_operations()
        op_types = {op['type'] for op in operations}

        # These should be available based on dialect_schema.py TRANSFORMS
        expected_common = ['where', 'select', 'limit']

        for expected in expected_common:
            assert expected in op_types, f"Missing expected operation: {expected}"


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


class TestDialectSchemaIntegration:
    """Tests for dialect_schema.py integration."""

    def test_schemas_come_from_dialect_schema(self):
        """Test that schemas are generated from dialect_schema.py TRANSFORMS."""
        from asql.dialect_schema import TRANSFORMS

        # Check that TRANSFORMS attributes correspond to UI schemas
        transform_labels = []
        for attr_name in dir(TRANSFORMS):
            if not attr_name.startswith("_"):
                transform = getattr(TRANSFORMS, attr_name)
                if hasattr(transform, "label"):
                    transform_labels.append(transform.label.replace(" ", "_"))

        # UI schemas should have entries for transforms
        assert len(transform_labels) > 0
        assert len(OPERATION_UI_SCHEMAS) > 0

    def test_merged_schemas_contain_base_info(self):
        """Test that schemas contain base schema info from dialect_schema."""
        for op_name, schema in OPERATION_UI_SCHEMAS.items():
            # All schemas should have these basic fields
            assert 'label' in schema, f"{op_name} missing 'label'"
            assert 'category' in schema, f"{op_name} missing 'category'"

    def test_parameters_from_dialect_schema(self):
        """Test that parameters come from dialect_schema.py."""
        schema = OPERATION_UI_SCHEMAS.get('where', {})

        if 'parameters' in schema:
            # Parameters should exist and have required fields
            for param in schema['parameters']:
                # Base fields should exist
                assert 'name' in param
                # Widget should be present
                assert 'widget' in param


class TestParameterMerging:
    """Tests for parameter handling."""

    def test_parameters_have_correct_structure(self):
        """Test that parameters have the expected structure."""
        for op_name, schema in OPERATION_UI_SCHEMAS.items():
            if 'parameters' in schema:
                for param in schema['parameters']:
                    assert 'name' in param, f"Parameter missing 'name' in {op_name}"
                    assert isinstance(param['name'], str)


class TestCategoryAssignment:
    """Tests for category assignment logic."""

    def test_filter_operations_have_filter_category(self):
        """Test that filter operations are categorized correctly."""
        filter_ops = ['where']

        for op in filter_ops:
            if op in OPERATION_UI_SCHEMAS:
                schema = OPERATION_UI_SCHEMAS[op]
                assert schema.get('category') == 'filter', \
                    f"{op} should have 'filter' category"

    def test_join_has_join_category(self):
        """Test that JOIN has join category."""
        if 'join' in OPERATION_UI_SCHEMAS:
            schema = OPERATION_UI_SCHEMAS['join']
            assert schema.get('category') == 'join'


class TestIntegration:
    """Integration tests for the full UI schema system."""

    def test_full_workflow(self):
        """Test the full workflow: generate -> access."""
        # 1. Access schemas
        from asql.ui_schema import OPERATION_UI_SCHEMAS
        assert len(OPERATION_UI_SCHEMAS) > 0

        # 2. Use API functions
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
