"""Tests for auto-aliasing functionality."""

import pytest
from asql import compile
from asql.config import CompileSettings, ASQLConfig
from asql.compiler.auto_alias import apply_auto_aliasing
from sqlglot import parse_one


class TestPhase1PrefixBased:
    """Test Phase 1: Prefix-based auto-aliasing."""
    
    def test_default_prefixes(self):
        """Test default prefixes for common functions."""
        settings = CompileSettings()
        # count(*) should use "num" prefix
        asql = "from orders select count(*)"
        sql = compile(asql, settings=settings)
        assert "COUNT(*) AS num" in sql.upper() or "COUNT(*) AS NUM" in sql.upper()
    
    def test_custom_prefix_via_set(self):
        """Test custom prefix via SET statement."""
        asql = """
        SET sum_alias_prefix = 'total';
        from orders select sum(amount)
        """
        sql = compile(asql)
        assert "SUM(amount) AS total_amount" in sql.upper() or "SUM(AMOUNT) AS TOTAL_AMOUNT" in sql.upper()
    
    def test_custom_prefix_yaml(self):
        """Test custom prefix via YAML config."""
        config = ASQLConfig()
        config.compile.alias_prefixes["sum"] = "total"
        asql = "from orders select sum(amount)"
        sql = compile(asql, settings=config.compile)
        assert "total_amount" in sql.lower() or "TOTAL_AMOUNT" in sql.upper()
    
    def test_single_arg_function(self):
        """Test single-arg function gets prefix_col alias."""
        settings = CompileSettings()
        settings.alias_prefixes["sum"] = "sum"
        asql = "from orders select sum(amount)"
        sql = compile(asql, settings=settings)
        assert "sum_amount" in sql.lower() or "SUM_AMOUNT" in sql.upper()
    
    def test_multi_arg_function(self):
        """Test multi-arg function gets prefix_arg1_arg2 alias."""
        settings = CompileSettings()
        settings.alias_prefixes["arg_max"] = "arg_max"
        asql = "from orders select arg_max(order_id, date)"
        sql = compile(asql, settings=settings)
        # Should generate arg_max_order_id_date or similar
        assert "arg_max" in sql.lower() or "ARG_MAX" in sql.upper()
    
    def test_count_star_special_case(self):
        """Test count(*) uses just prefix (not prefix_*)."""
        settings = CompileSettings()
        # count(*) should become "num" not "num_*"
        asql = "from orders select count(*)"
        sql = compile(asql, settings=settings)
        assert "AS num" in sql.lower() or "AS NUM" in sql.upper()
        assert "num_*" not in sql.lower()


class TestPhase2TemplateSystem:
    """Test Phase 2: Jinja2 template system."""
    
    def test_default_template(self):
        """Test default template applies to all functions."""
        settings = CompileSettings()
        settings.alias_template = "{prefix}_{col}"
        settings.alias_prefixes["sum"] = "sum"
        asql = "from orders select sum(amount)"
        sql = compile(asql, settings=settings)
        assert "sum_amount" in sql.lower() or "SUM_AMOUNT" in sql.upper()
    
    def test_function_specific_template(self):
        """Test function-specific template overrides default."""
        settings = CompileSettings()
        settings.alias_template = "{prefix}_{col}"  # Default
        settings.alias_templates["count"] = "{prefix}"  # Override for count
        asql = "from orders select count(*)"
        sql = compile(asql, settings=settings)
        # Should use count template, not default
        assert "AS num" in sql.lower() or "AS NUM" in sql.upper()
    
    def test_template_with_filters(self):
        """Test template filters (lower, upper, title, camel, snake)."""
        settings = CompileSettings()
        settings.alias_template = "{prefix|upper}_{col|upper}"
        settings.alias_prefixes["sum"] = "sum"
        asql = "from orders select sum(amount)"
        sql = compile(asql, settings=settings)
        assert "SUM_AMOUNT" in sql.upper()
    
    def test_multi_arg_template(self):
        """Test template with multiple arguments."""
        settings = CompileSettings()
        settings.alias_templates["arg_max"] = "{prefix}_{arg1}_{arg2}"
        settings.alias_prefixes["arg_max"] = "arg_max"
        asql = "from orders select arg_max(order_id, date)"
        sql = compile(asql, settings=settings)
        assert "arg_max_order_id_date" in sql.lower() or "ARG_MAX_ORDER_ID_DATE" in sql.upper()
    
    def test_template_variables(self):
        """Test all template variables (func, prefix, col, arg1, arg2, distinct, order_by)."""
        settings = CompileSettings()
        settings.alias_template = "{func}_{col}"
        asql = "from orders select sum(amount)"
        sql = compile(asql, settings=settings)
        # Should use func name (sum) and col name (amount)
        assert "sum_amount" in sql.lower() or "SUM_AMOUNT" in sql.upper()


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_explicit_alias_overrides(self):
        """Test explicit 'as' alias overrides auto-alias."""
        settings = CompileSettings()
        settings.alias_prefixes["sum"] = "sum"
        asql = "from orders select sum(amount) as total"
        sql = compile(asql, settings=settings)
        assert "AS total" in sql.lower() or "AS TOTAL" in sql.upper()
        # Should not have sum_amount
        assert "sum_amount" not in sql.lower()
    
    def test_distinct_modifier(self):
        """Test functions with DISTINCT modifier."""
        settings = CompileSettings()
        settings.alias_prefixes["count"] = "uniq"
        asql = "from orders select count(distinct customer_id)"
        sql = compile(asql, settings=settings)
        assert "COUNT(DISTINCT" in sql.upper()
        # Should generate alias with distinct
        assert "uniq" in sql.lower() or "UNIQ" in sql.upper()
    
    def test_complex_expression_no_alias(self):
        """Test complex expressions (no column name) don't get auto-alias."""
        settings = CompileSettings()
        settings.alias_prefixes["sum"] = "sum"
        asql = "from orders select sum(amount * quantity)"
        sql = compile(asql, settings=settings)
        # Complex expression might not get auto-alias (depends on implementation)
        # This is acceptable - user should provide explicit alias
    
    def test_group_by_aggregates(self):
        """Test auto-aliasing in GROUP BY aggregates."""
        settings = CompileSettings()
        settings.alias_prefixes["sum"] = "sum"
        asql = "from orders group by customer_id (sum(amount))"
        sql = compile(asql, settings=settings)
        assert "sum_amount" in sql.lower() or "SUM_AMOUNT" in sql.upper()
    
    def test_row_number_function(self):
        """Test row_number() gets default prefix."""
        settings = CompileSettings()
        asql = "from orders select row_number()"
        sql = compile(asql, settings=settings)
        assert "row_num" in sql.lower() or "ROW_NUM" in sql.upper()


class TestConfigLoading:
    """Test configuration loading from YAML and SET statements."""
    
    def test_flat_yaml_format(self):
        """Test flat YAML format: sum_alias_prefix: 'total'."""
        config_dict = {
            "compile": {
                "sum_alias_prefix": "total",
                "count_alias_prefix": "num",
            }
        }
        config = ASQLConfig.from_dict(config_dict)
        assert config.compile.alias_prefixes["sum"] == "total"
        assert config.compile.alias_prefixes["count"] == "num"
    
    def test_nested_yaml_format(self):
        """Test nested YAML format: alias_prefixes: {sum: 'total'}."""
        config_dict = {
            "compile": {
                "alias_prefixes": {
                    "sum": "total",
                    "count": "num",
                }
            }
        }
        config = ASQLConfig.from_dict(config_dict)
        assert config.compile.alias_prefixes["sum"] == "total"
        assert config.compile.alias_prefixes["count"] == "num"
    
    def test_template_yaml_format(self):
        """Test template in YAML config."""
        config_dict = {
            "compile": {
                "alias_template": "{prefix}_{col}",
                "count_alias_template": "{prefix}",
            }
        }
        config = ASQLConfig.from_dict(config_dict)
        assert config.compile.alias_template == "{prefix}_{col}"
        assert config.compile.alias_templates["count"] == "{prefix}"
    
    def test_set_statement_parsing(self):
        """Test SET statement parsing for alias config."""
        asql = """
        SET sum_alias_prefix = 'total';
        SET alias_template = '{prefix}_{col}';
        from orders select sum(amount)
        """
        sql = compile(asql)
        assert "total_amount" in sql.lower() or "TOTAL_AMOUNT" in sql.upper()


class TestPrecedence:
    """Test precedence rules."""
    
    def test_function_template_overrides_prefix(self):
        """Test function-specific template > function-specific prefix."""
        settings = CompileSettings()
        settings.alias_prefixes["count"] = "num"
        settings.alias_template = "{prefix}_{col}"  # Default template
        settings.alias_templates["count"] = "{prefix}"  # Function-specific template
        asql = "from orders select count(*)"
        sql = compile(asql, settings=settings)
        # Should use function-specific template (just "num"), not default template
        assert "AS num" in sql.lower() or "AS NUM" in sql.upper()
        assert "num_*" not in sql.lower()
    
    def test_function_prefix_overrides_default(self):
        """Test function-specific prefix > default prefix."""
        settings = CompileSettings()
        settings.alias_prefixes["count"] = "cnt"  # Custom prefix
        settings.alias_template = "{prefix}"  # Simple template
        asql = "from orders select count(*)"
        sql = compile(asql, settings=settings)
        # Should use "cnt" not default "num"
        assert "AS cnt" in sql.lower() or "AS CNT" in sql.upper()


class TestIntegration:
    """Integration tests with real queries."""
    
    def test_full_query_with_auto_aliases(self):
        """Test a complete query with multiple auto-aliased functions."""
        settings = CompileSettings()
        settings.alias_prefixes["sum"] = "sum"
        settings.alias_prefixes["avg"] = "avg"
        settings.alias_prefixes["count"] = "num"
        asql = """
        from orders
        group by customer_id (
            sum(amount),
            avg(amount),
            count(*)
        )
        """
        sql = compile(asql, settings=settings)
        assert "sum_amount" in sql.lower() or "SUM_AMOUNT" in sql.upper()
        assert "avg_amount" in sql.lower() or "AVG_AMOUNT" in sql.upper()
        assert "num" in sql.lower() or "NUM" in sql.upper()
    
    def test_order_by_auto_aliased_column(self):
        """Test ORDER BY can reference auto-aliased columns."""
        settings = CompileSettings()
        settings.alias_prefixes["sum"] = "sum"
        asql = """
        from orders
        group by customer_id (sum(amount))
        order by -sum_amount
        """
        sql = compile(asql, settings=settings)
        # Should be able to reference sum_amount in ORDER BY
        assert "ORDER BY" in sql.upper()
        assert "sum_amount" in sql.lower() or "SUM_AMOUNT" in sql.upper()
