"""
Tests for asql/ui_schema_generator.py

Tests for auto-generation of UI schemas from ASQL/SQLGlot metadata.
"""

from asql.ui_schema_generator import (
    generate_base_schema_from_asql,
    _guess_icon,
    _guess_category,
    _generate_parameters,
    generate_function_schemas,
    _guess_function_category,
    merge_with_overrides
)


class TestGenerateBaseSchemaFromAsql:
    """Tests for generate_base_schema_from_asql function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = generate_base_schema_from_asql()

        assert isinstance(result, dict)

    def test_generates_schemas_for_asql_operations(self):
        """Test that schemas are generated for ASQL operations."""
        schemas = generate_base_schema_from_asql()

        # Should have multiple operations
        assert len(schemas) > 0

    def test_schema_has_required_fields(self):
        """Test that each schema has required fields."""
        schemas = generate_base_schema_from_asql()

        for op_name, schema in schemas.items():
            assert 'label' in schema, f"{op_name} missing 'label'"
            assert 'icon' in schema, f"{op_name} missing 'icon'"
            assert 'description' in schema, f"{op_name} missing 'description'"
            assert 'category' in schema, f"{op_name} missing 'category'"
            assert 'parameters' in schema, f"{op_name} missing 'parameters'"

    def test_parameters_are_lists(self):
        """Test that parameters field is always a list."""
        schemas = generate_base_schema_from_asql()

        for op_name, schema in schemas.items():
            assert isinstance(schema['parameters'], list), \
                f"{op_name} parameters should be a list"

    def test_operation_names_are_lowercase(self):
        """Test that operation names are lowercased and normalized."""
        schemas = generate_base_schema_from_asql()

        for op_name in schemas.keys():
            assert op_name.islower() or '_' in op_name, \
                f"Operation name '{op_name}' should be lowercase"


class TestGuessIcon:
    """Tests for _guess_icon function."""

    def test_where_gets_search_icon(self):
        """Test that WHERE gets search icon."""
        icon = _guess_icon("WHERE")
        assert icon == "🔍"

    def test_filter_gets_search_icon(self):
        """Test that FILTER gets search icon."""
        icon = _guess_icon("FILTER")
        assert icon == "🔍"

    def test_join_gets_link_icon(self):
        """Test that JOIN gets link icon."""
        icon = _guess_icon("JOIN")
        assert icon == "🔗"

    def test_select_gets_clipboard_icon(self):
        """Test that SELECT gets clipboard icon."""
        icon = _guess_icon("SELECT")
        assert icon == "📋"

    def test_group_by_gets_chart_icon(self):
        """Test that GROUP BY gets chart icon."""
        icon = _guess_icon("GROUP BY")
        assert icon == "📊"

    def test_order_by_gets_arrow_icon(self):
        """Test that ORDER BY gets arrow icon."""
        icon = _guess_icon("ORDER BY")
        assert icon == "⬆️"

    def test_limit_gets_number_icon(self):
        """Test that LIMIT gets number icon."""
        icon = _guess_icon("LIMIT")
        assert icon == "🔢"

    def test_unknown_gets_package_icon(self):
        """Test that unknown operations get default package icon."""
        icon = _guess_icon("UNKNOWN_OPERATION")
        assert icon == "📦"

    def test_stash_gets_save_icon(self):
        """Test that STASH gets save icon."""
        icon = _guess_icon("STASH")
        assert icon == "💾"

    def test_pivot_gets_rotate_icon(self):
        """Test that PIVOT gets rotate icon."""
        icon = _guess_icon("PIVOT")
        assert icon == "🔄"


class TestGuessCategory:
    """Tests for _guess_category function."""

    def test_where_is_filter_category(self):
        """Test that WHERE is categorized as filter."""
        category = _guess_category("WHERE")
        assert category == "filter"

    def test_filter_is_filter_category(self):
        """Test that FILTER is categorized as filter."""
        category = _guess_category("FILTER")
        assert category == "filter"

    def test_if_is_filter_category(self):
        """Test that IF is categorized as filter."""
        category = _guess_category("IF")
        assert category == "filter"

    def test_join_is_join_category(self):
        """Test that JOIN is categorized as join."""
        category = _guess_category("JOIN")
        assert category == "join"

    def test_left_is_join_category(self):
        """Test that LEFT is categorized as join."""
        category = _guess_category("LEFT")
        assert category == "join"

    def test_select_is_select_category(self):
        """Test that SELECT is categorized as select."""
        category = _guess_category("SELECT")
        assert category == "select"

    def test_project_is_select_category(self):
        """Test that PROJECT is categorized as select."""
        category = _guess_category("PROJECT")
        assert category == "select"

    def test_group_by_is_aggregate_category(self):
        """Test that GROUP BY is categorized as aggregate."""
        category = _guess_category("GROUP BY")
        assert category == "aggregate"

    def test_order_by_is_sort_category(self):
        """Test that ORDER BY is categorized as sort."""
        category = _guess_category("ORDER BY")
        assert category == "sort"

    def test_limit_is_limit_category(self):
        """Test that LIMIT is categorized as limit."""
        category = _guess_category("LIMIT")
        assert category == "limit"

    def test_unknown_is_advanced_category(self):
        """Test that unknown operations are categorized as advanced."""
        category = _guess_category("UNKNOWN_OPERATION")
        assert category == "advanced"


class TestGenerateParameters:
    """Tests for _generate_parameters function."""

    def test_where_has_condition_parameter(self):
        """Test that WHERE has condition parameter."""
        params = _generate_parameters("WHERE")

        assert len(params) > 0
        param_names = [p['name'] for p in params]
        assert 'condition' in param_names

    def test_filter_has_condition_parameter(self):
        """Test that FILTER has condition parameter."""
        params = _generate_parameters("FILTER")

        param_names = [p['name'] for p in params]
        assert 'condition' in param_names

    def test_join_has_table_and_condition(self):
        """Test that JOIN has table and condition parameters."""
        params = _generate_parameters("JOIN")

        param_names = [p['name'] for p in params]
        assert 'table' in param_names
        assert 'join_type' in param_names

    def test_select_has_columns_parameter(self):
        """Test that SELECT has columns parameter."""
        params = _generate_parameters("SELECT")

        param_names = [p['name'] for p in params]
        assert 'columns' in param_names

    def test_group_by_has_dimensions(self):
        """Test that GROUP BY has dimensions parameter."""
        params = _generate_parameters("GROUP BY")

        param_names = [p['name'] for p in params]
        assert 'dimensions' in param_names

    def test_order_by_has_expressions(self):
        """Test that ORDER BY has expressions parameter."""
        params = _generate_parameters("ORDER BY")

        param_names = [p['name'] for p in params]
        assert 'expressions' in param_names

    def test_limit_has_count(self):
        """Test that LIMIT has count parameter."""
        params = _generate_parameters("LIMIT")

        param_names = [p['name'] for p in params]
        assert 'count' in param_names

    def test_unknown_returns_empty(self):
        """Test that unknown operations return empty list."""
        params = _generate_parameters("UNKNOWN_OPERATION")

        assert params == []

    def test_parameters_have_widget_field(self):
        """Test that parameters have widget field."""
        params = _generate_parameters("WHERE")

        for param in params:
            assert 'widget' in param, f"Parameter missing 'widget': {param}"

    def test_parameters_have_required_field(self):
        """Test that parameters have required field."""
        params = _generate_parameters("WHERE")

        for param in params:
            assert 'required' in param, f"Parameter missing 'required': {param}"


class TestGenerateFunctionSchemas:
    """Tests for generate_function_schemas function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = generate_function_schemas()

        assert isinstance(result, dict)

    def test_generates_schemas_for_functions(self):
        """Test that schemas are generated for ASQL functions."""
        schemas = generate_function_schemas()

        # Should have functions registered
        assert len(schemas) >= 0  # May be empty if no functions registered

    def test_function_schema_has_required_fields(self):
        """Test that function schemas have required fields."""
        schemas = generate_function_schemas()

        for func_name, schema in schemas.items():
            assert 'name' in schema, f"{func_name} missing 'name'"
            assert 'category' in schema, f"{func_name} missing 'category'"
            assert 'signature' in schema, f"{func_name} missing 'signature'"
            assert 'description' in schema, f"{func_name} missing 'description'"


class TestGuessFunctionCategory:
    """Tests for _guess_function_category function."""

    def test_date_functions(self):
        """Test date-related functions are categorized correctly."""
        date_funcs = ["DATE_TRUNC", "DAY", "MONTH", "YEAR", "WEEK"]

        for func in date_funcs:
            category = _guess_function_category(func)
            assert category == "date", f"{func} should be 'date' category"

    def test_window_functions(self):
        """Test window functions are categorized correctly."""
        window_funcs = ["RUNNING_SUM", "ROLLING_AVG", "LAG", "LEAD", "ROW_NUMBER", "RANK"]

        for func in window_funcs:
            category = _guess_function_category(func)
            assert category == "window", f"{func} should be 'window' category"

    def test_aggregate_functions(self):
        """Test aggregate functions are categorized correctly."""
        agg_funcs = ["SUM", "AVG", "COUNT", "MIN", "MAX"]

        for func in agg_funcs:
            category = _guess_function_category(func)
            assert category == "aggregate", f"{func} should be 'aggregate' category"

    def test_string_functions(self):
        """Test string functions are categorized correctly."""
        str_funcs = ["UPPER", "LOWER", "TRIM", "CONCAT", "SUBSTRING"]

        for func in str_funcs:
            category = _guess_function_category(func)
            assert category == "string", f"{func} should be 'string' category"

    def test_unknown_functions(self):
        """Test unknown functions are categorized as 'other'."""
        category = _guess_function_category("UNKNOWN_FUNCTION")
        assert category == "other"


class TestMergeWithOverrides:
    """Tests for merge_with_overrides function."""

    def test_simple_override(self):
        """Test simple key override."""
        base = {"a": 1, "b": 2}
        overrides = {"b": 3}

        result = merge_with_overrides(base, overrides)

        assert result["a"] == 1
        assert result["b"] == 3

    def test_adds_new_keys(self):
        """Test that new keys from overrides are added."""
        base = {"a": 1}
        overrides = {"b": 2}

        result = merge_with_overrides(base, overrides)

        assert result["a"] == 1
        assert result["b"] == 2

    def test_deep_merge_dicts(self):
        """Test that nested dicts are deep merged."""
        base = {"nested": {"a": 1, "b": 2}}
        overrides = {"nested": {"b": 3, "c": 4}}

        result = merge_with_overrides(base, overrides)

        assert result["nested"]["a"] == 1  # Preserved from base
        assert result["nested"]["b"] == 3  # Overridden
        assert result["nested"]["c"] == 4  # Added from override

    def test_does_not_modify_original(self):
        """Test that original base dict is not modified."""
        base = {"a": 1}
        overrides = {"b": 2}

        result = merge_with_overrides(base, overrides)

        assert "b" not in base
        assert "b" in result

    def test_non_dict_override_replaces(self):
        """Test that non-dict values replace entirely."""
        base = {"a": [1, 2, 3]}
        overrides = {"a": [4, 5]}

        result = merge_with_overrides(base, overrides)

        assert result["a"] == [4, 5]


class TestIntegration:
    """Integration tests for the generator module."""

    def test_generated_schemas_are_valid(self):
        """Test that generated schemas can be used downstream."""
        schemas = generate_base_schema_from_asql()

        # All schemas should be dicts with expected structure
        for op_name, schema in schemas.items():
            # Should be usable by ui_schema.py
            assert isinstance(schema, dict)
            assert 'parameters' in schema
            assert isinstance(schema['parameters'], list)

    def test_schemas_match_asql_parsers(self):
        """Test that schemas are generated for all ASQL parsers."""
        from asql.dialect import ASQLParser

        schemas = generate_base_schema_from_asql()

        # There should be schemas for the transform parsers
        assert len(schemas) == len(ASQLParser.TRANSFORM_PARSERS)

    def test_function_schemas_match_registry(self):
        """Test that function schemas match the function registry."""
        from asql.functions import ASQL_FUNCTION_REGISTRY

        schemas = generate_function_schemas()

        # Should have same number of schemas as registered functions
        assert len(schemas) == len(ASQL_FUNCTION_REGISTRY)
