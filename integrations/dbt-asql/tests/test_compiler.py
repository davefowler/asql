"""Tests for the dbt-asql compiler."""

import pytest
from dbt_asql.compiler import (
    _extract_config,
    _expand_variables,
    _resolve_refs,
    _parse_value,
    compile_asql_model,
)


class TestExtractConfig:
    """Tests for SET statement extraction."""
    
    def test_simple_string(self):
        code = "SET materialized = table;\n\nfrom orders"
        config, remaining = _extract_config(code)
        
        assert config == {"materialized": "table"}
        assert "SET" not in remaining
        assert "from orders" in remaining
    
    def test_multiple_configs(self):
        code = """SET materialized = incremental;
SET unique_key = id;
SET schema = marts;

from orders"""
        config, remaining = _extract_config(code)
        
        assert config == {
            "materialized": "incremental",
            "unique_key": "id",
            "schema": "marts",
        }
        assert "from orders" in remaining
    
    def test_list_value(self):
        code = "SET tags = [daily, core];\n\nfrom orders"
        config, _ = _extract_config(code)
        
        assert config == {"tags": ["daily", "core"]}
    
    def test_boolean_values(self):
        code = "SET enabled = true;\nSET persist = false;"
        config, _ = _extract_config(code)
        
        assert config["enabled"] is True
        assert config["persist"] is False
    
    def test_integer_value(self):
        code = "SET priority = 42;"
        config, _ = _extract_config(code)
        
        assert config["priority"] == 42


class TestParseValue:
    """Tests for value parsing."""
    
    def test_string(self):
        assert _parse_value("table") == "table"
        assert _parse_value("'quoted'") == "quoted"
        assert _parse_value('"double"') == "double"
    
    def test_boolean(self):
        assert _parse_value("true") is True
        assert _parse_value("TRUE") is True
        assert _parse_value("false") is False
    
    def test_integer(self):
        assert _parse_value("42") == 42
        assert _parse_value("-1") == -1
    
    def test_float(self):
        assert _parse_value("3.14") == 3.14
        assert _parse_value("-0.5") == -0.5
    
    def test_list(self):
        assert _parse_value("[a, b, c]") == ["a", "b", "c"]
        assert _parse_value("['x', 'y']") == ["x", "y"]


class TestExpandVariables:
    """Tests for variable syntax expansion."""
    
    def test_simple_variable(self):
        code = "WHERE date > {{ start_date }}"
        result = _expand_variables(code)
        
        assert result == "WHERE date > {{ var('start_date') }}"
    
    def test_variable_with_default(self):
        code = "LIMIT {{ row_limit || 100 }}"
        result = _expand_variables(code)
        
        assert result == "LIMIT {{ var('row_limit', 100) }}"
    
    def test_variable_with_string_default(self):
        code = "WHERE status = {{ status || 'active' }}"
        result = _expand_variables(code)
        
        assert result == "WHERE status = {{ var('status', 'active') }}"
    
    def test_env_variable(self):
        code = "{{ env.API_KEY }}"
        result = _expand_variables(code)
        
        assert result == "{{ env_var('API_KEY') }}"
    
    def test_skip_existing_var(self):
        code = "{{ var('x') }}"
        result = _expand_variables(code)
        
        assert result == "{{ var('x') }}"  # Unchanged
    
    def test_skip_ref(self):
        code = "{{ ref('orders') }}"
        result = _expand_variables(code)
        
        assert result == "{{ ref('orders') }}"  # Unchanged
    
    def test_skip_this(self):
        code = "{{ this }}"
        result = _expand_variables(code)
        
        assert result == "{{ this }}"  # Unchanged
    
    def test_skip_is_incremental(self):
        code = "{{ is_incremental() }}"
        result = _expand_variables(code)
        
        assert result == "{{ is_incremental() }}"  # Unchanged


class TestResolveRefs:
    """Tests for model reference resolution."""
    
    def test_simple_from(self):
        sql = "SELECT * FROM orders"
        known = {"orders", "customers"}
        result = _resolve_refs(sql, known)
        
        assert result == "SELECT * FROM {{ ref('orders') }}"
    
    def test_join(self):
        sql = "SELECT * FROM orders JOIN customers ON ..."
        known = {"orders", "customers"}
        result = _resolve_refs(sql, known)
        
        assert "{{ ref('orders') }}" in result
        assert "{{ ref('customers') }}" in result
    
    def test_unknown_table(self):
        sql = "SELECT * FROM raw_events"
        known = {"orders"}  # raw_events is not a model
        result = _resolve_refs(sql, known)
        
        assert result == "SELECT * FROM raw_events"  # Unchanged
    
    def test_qualified_table(self):
        sql = "SELECT * FROM raw.orders"
        known = {"orders"}
        result = _resolve_refs(sql, known)
        
        # Qualified names should NOT be converted to refs
        assert result == "SELECT * FROM raw.orders"
    
    def test_already_has_ref(self):
        sql = "SELECT * FROM {{ ref('orders') }}"
        known = {"orders"}
        result = _resolve_refs(sql, known)
        
        assert result == "SELECT * FROM {{ ref('orders') }}"


class TestCompileAsqlModel:
    """Integration tests for full model compilation."""
    
    def test_simple_model(self):
        asql = """SET materialized = table;

from orders
  select id, amount"""
        
        result = compile_asql_model(asql, dialect="postgres")
        
        assert "{{ config(materialized='table') }}" in result
        assert "SELECT" in result
        assert "FROM orders" in result
    
    def test_with_variable(self):
        asql = """from orders
  where created_at > {{ start_date }}"""
        
        result = compile_asql_model(asql, dialect="postgres")
        
        assert "{{ var('start_date') }}" in result
    
    def test_with_model_refs(self):
        asql = """from stg_orders
  select id, amount"""
        
        result = compile_asql_model(
            asql,
            known_models={"stg_orders"},
            dialect="postgres"
        )
        
        assert "{{ ref('stg_orders') }}" in result


# Run with: ./venv/bin/pytest integrations/dbt-asql/tests/

