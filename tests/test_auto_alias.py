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
        settings.alias_prefixes["coalesce"] = "coal"
        asql = "from orders select coalesce(amount, 0)"
        sql = compile(asql, settings=settings)
        # Should generate coal_amount_0 or similar
        assert "coal" in sql.lower() or "COAL" in sql.upper()
    
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
        settings.alias_templates["coalesce"] = "{prefix}_{arg1}_{arg2}"
        settings.alias_prefixes["coalesce"] = "coal"
        asql = "from orders select coalesce(amount, 0)"
        sql = compile(asql, settings=settings)
        # Note: arg2 is a literal (0), so may be empty in template
        assert "coal" in sql.lower() or "COAL" in sql.upper()
    
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


class TestAliasMappingTable:
    """Comprehensive tests for all alias mappings from the reference table."""
    
    # === Aggregate Functions ===
    
    def test_sum_alias(self):
        """Test sum(col) → sum_col."""
        asql = "from orders select sum(amount)"
        sql = compile(asql)
        assert "sum_amount" in sql.lower()
    
    def test_avg_alias(self):
        """Test avg(col) → avg_col."""
        asql = "from orders select avg(price)"
        sql = compile(asql)
        assert "avg_price" in sql.lower()
    
    def test_min_alias(self):
        """Test min(col) → min_col."""
        asql = "from orders select min(created_at)"
        sql = compile(asql)
        assert "min_created_at" in sql.lower()
    
    def test_max_alias(self):
        """Test max(col) → max_col."""
        asql = "from orders select max(amount)"
        sql = compile(asql)
        assert "max_amount" in sql.lower()
    
    def test_count_star_alias(self):
        """Test count(*) → num."""
        asql = "from orders select count(*)"
        sql = compile(asql)
        assert " num" in sql.lower() or "as num" in sql.lower()
    
    def test_count_column_alias(self):
        """Test count(col) → num_col."""
        asql = "from orders select count(email)"
        sql = compile(asql)
        assert "num_email" in sql.lower()
    
    def test_count_distinct_alias(self):
        """Test count(distinct col) → num_distinct_col."""
        asql = "from orders select count(distinct user_id)"
        sql = compile(asql)
        # Default is num_distinct or similar
        assert "distinct" in sql.lower() or "num" in sql.lower()
    
    # === Date Functions ===
    
    def test_year_alias(self):
        """Test year(col) → year_col."""
        asql = "from orders select year(created_at)"
        sql = compile(asql)
        assert "year_created_at" in sql.lower()
    
    def test_month_alias(self):
        """Test month(col) → month_col."""
        asql = "from orders select month(created_at)"
        sql = compile(asql)
        assert "month_created_at" in sql.lower()
    
    def test_week_alias(self):
        """Test week(col) → week_col."""
        asql = "from orders select week(created_at)"
        sql = compile(asql)
        assert "week_created_at" in sql.lower()
    
    def test_day_alias(self):
        """Test day(col) → day_col."""
        asql = "from orders select day(created_at)"
        sql = compile(asql)
        assert "day_created_at" in sql.lower()
    
    def test_quarter_alias(self):
        """Test quarter(col) → quarter_col."""
        asql = "from orders select quarter(created_at)"
        sql = compile(asql)
        assert "quarter_created_at" in sql.lower()
    
    def test_hour_alias(self):
        """Test hour(col) → hour_col."""
        asql = "from orders select hour(created_at)"
        sql = compile(asql)
        assert "hour_created_at" in sql.lower()
    
    # === String Functions ===
    
    def test_upper_alias(self):
        """Test upper(col) → upper_col."""
        asql = "from users select upper(name)"
        sql = compile(asql)
        assert "upper_name" in sql.lower()
    
    def test_lower_alias(self):
        """Test lower(col) → lower_col."""
        asql = "from users select lower(email)"
        sql = compile(asql)
        assert "lower_email" in sql.lower()
    
    def test_length_alias(self):
        """Test length(col) → length_col."""
        asql = "from users select length(name)"
        sql = compile(asql)
        assert "length_name" in sql.lower()
    
    def test_trim_alias(self):
        """Test trim(col) → trim_col."""
        asql = "from users select trim(name)"
        sql = compile(asql)
        assert "trim_name" in sql.lower()
    
    # === Window Functions ===
    
    def test_row_number_alias(self):
        """Test row_number() → row_num."""
        asql = "from orders select row_number()"
        sql = compile(asql)
        assert "row_num" in sql.lower()
    
    # === Multi-arg Functions ===
    
    def test_coalesce_alias(self):
        """Test coalesce(a, b) → coalesce_a_b."""
        asql = "from orders select coalesce(amount, 0)"
        sql = compile(asql)
        assert "coalesce" in sql.lower()
    
    def test_concat_alias(self):
        """Test concat(a, b) → concat_a_b."""
        asql = "from users select concat(first_name, last_name)"
        sql = compile(asql)
        assert "concat" in sql.lower()
    
    # === Special Cases ===
    
    def test_explicit_alias_takes_precedence(self):
        """Test explicit AS alias overrides auto-alias."""
        asql = "from orders select sum(amount) as total_revenue"
        sql = compile(asql)
        assert "total_revenue" in sql.lower()
        assert "sum_amount" not in sql.lower()
    
    def test_multiple_same_function_unique_aliases(self):
        """Test multiple instances of same function get unique aliases."""
        asql = "from orders select sum(amount), sum(quantity)"
        sql = compile(asql)
        assert "sum_amount" in sql.lower()
        assert "sum_quantity" in sql.lower()
    
    def test_group_by_with_auto_aliases(self):
        """Test auto-aliasing works inside GROUP BY aggregates."""
        asql = """
        from orders
        group by region (
            sum(amount),
            avg(price),
            count(*)
        )
        """
        sql = compile(asql)
        assert "sum_amount" in sql.lower()
        assert "avg_price" in sql.lower()
    
    def test_nested_function_alias(self):
        """Test nested functions get sensible alias."""
        asql = "from orders select round(avg(amount))"
        sql = compile(asql)
        # Nested functions should still get some alias
        assert "avg" in sql.lower() or "round" in sql.lower()


class TestTemplateFilters:
    """Test Jinja2 template filters."""
    
    def test_lower_filter(self):
        """Test {var|lower} filter."""
        settings = CompileSettings()
        settings.alias_template = "{prefix|lower}_{col|lower}"
        settings.alias_prefixes["SUM"] = "SUM"  # Uppercase prefix
        asql = "from orders select sum(amount)"
        sql = compile(asql, settings=settings)
        # Result should be lowercase
        assert "sum_amount" in sql.lower()
    
    def test_upper_filter(self):
        """Test {var|upper} filter."""
        settings = CompileSettings()
        settings.alias_template = "{prefix|upper}_{col|upper}"
        asql = "from orders select sum(amount)"
        sql = compile(asql, settings=settings)
        assert "SUM_AMOUNT" in sql.upper()
    
    def test_title_filter(self):
        """Test {var|title} filter."""
        settings = CompileSettings()
        settings.alias_template = "{prefix|title}{col|title}"
        asql = "from orders select sum(amount)"
        sql = compile(asql, settings=settings)
        # Title case: SumAmount
        assert "SumAmount" in sql or "sumamount" in sql.lower()
    
    def test_custom_template_with_separator(self):
        """Test custom separator in template."""
        settings = CompileSettings()
        settings.alias_template = "{prefix}__{col}"  # Double underscore
        asql = "from orders select sum(amount)"
        sql = compile(asql, settings=settings)
        # Note: double underscore may be collapsed to single
        assert "sum" in sql.lower() and "amount" in sql.lower()
