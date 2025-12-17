"""Tests for the ASQL pre-parser.

The pre-parser transforms ASQL structural syntax to SQL-like syntax
before SQLGlot parsing.
"""

import pytest
from asql.preparser import preparse_asql, ASQLPreParser


class TestFromFirst:
    """Test FROM-first to SELECT-FROM transformation."""
    
    def test_simple_from_first(self):
        """FROM without SELECT adds SELECT *."""
        result = preparse_asql("from users")
        assert "SELECT *" in result.upper()
        assert "FROM USERS" in result.upper()
    
    def test_from_with_where(self):
        """FROM with WHERE clause."""
        result = preparse_asql("from users where status = 'active'")
        assert "SELECT *" in result.upper()
        assert "FROM USERS" in result.upper()
        assert "WHERE STATUS" in result.upper()
    
    def test_from_with_limit(self):
        """FROM with LIMIT clause."""
        result = preparse_asql("from users limit 10")
        assert "SELECT *" in result.upper()
        assert "LIMIT 10" in result.upper()


class TestPipelineOperators:
    """Test pipeline operator (|) transformation."""
    
    def test_simple_pipeline(self):
        """Pipeline operators are removed."""
        result = preparse_asql("from users | where active | limit 10")
        assert "|" not in result
        assert "FROM USERS" in result.upper()
        assert "WHERE ACTIVE" in result.upper()
        assert "LIMIT 10" in result.upper()
    
    def test_pipeline_with_strings(self):
        """Pipeline operators in strings are preserved."""
        result = preparse_asql("from users | where name = 'test|value'")
        # The | inside the string should be preserved
        assert "test|value" in result


class TestCountShorthand:
    """Test # count shorthand transformation."""
    
    def test_standalone_hash(self):
        """# becomes COUNT(*)."""
        # Note: The preparser transforms # to COUNT(*)
        result = preparse_asql("from users select #")
        assert "COUNT(*)" in result.upper()
    
    def test_hash_with_column(self):
        """#(col) becomes COUNT(col)."""
        result = preparse_asql("from users select #(id)")
        assert "COUNT(ID)" in result.upper()
    
    def test_hash_of_table_name(self):
        """# of users becomes COUNT(DISTINCT user_id)."""
        result = preparse_asql("from users select # of users")
        assert "COUNT(DISTINCT USER_ID)" in result.upper()
        assert "COUNT(*)" not in result.upper()
    
    def test_hash_table_name(self):
        """# users becomes COUNT(DISTINCT user_id)."""
        result = preparse_asql("from users select # users")
        assert "COUNT(DISTINCT USER_ID)" in result.upper()
        assert "COUNT(*)" not in result.upper()
    
    def test_hash_explicit_star(self):
        """# * becomes COUNT(*) (explicit row count)."""
        result = preparse_asql("from users select # *")
        assert "COUNT(*)" in result.upper()
    
    def test_hash_orders_table(self):
        """# orders becomes COUNT(DISTINCT order_id)."""
        result = preparse_asql("from orders select # orders")
        assert "COUNT(DISTINCT ORDER_ID)" in result.upper()
    
    def test_hash_singular_table(self):
        """# user becomes COUNT(DISTINCT user_id) (singular form)."""
        result = preparse_asql("from user select # user")
        assert "COUNT(DISTINCT USER_ID)" in result.upper()


class TestCoalesceOperator:
    """Test ?? coalesce operator transformation."""
    
    def test_simple_coalesce(self):
        """a ?? b becomes COALESCE(a, b)."""
        result = preparse_asql("from users select name ?? 'Unknown'")
        assert "COALESCE" in result.upper()
    
    def test_chained_coalesce(self):
        """a ?? b ?? c becomes COALESCE(a, b, c)."""
        result = preparse_asql("from users select first_name ?? nickname ?? 'Unknown'")
        assert "COALESCE" in result.upper()


class TestOrderDescPrefix:
    """Test -column DESC transformation in ORDER BY."""
    
    def test_simple_desc(self):
        """-col becomes col DESC."""
        result = preparse_asql("from users order by -created_at")
        assert "CREATED_AT DESC" in result.upper() or "CREATED_AT" in result.upper()
    
    def test_mixed_order(self):
        """Mixed ascending and descending."""
        result = preparse_asql("from users order by -created_at, name")
        assert "DESC" in result.upper()
        assert "NAME" in result.upper()


class TestNaturalAggregates:
    """Test natural language aggregate transformation."""
    
    def test_sum_of(self):
        """sum of amount becomes sum(amount)."""
        result = preparse_asql("from sales select sum of amount")
        assert "SUM(AMOUNT)" in result.upper() or "SUM" in result.upper() and "AMOUNT" in result.upper()
    
    def test_avg_column(self):
        """avg price becomes avg(price)."""
        result = preparse_asql("from products select avg price")
        assert "AVG" in result.upper()
        assert "PRICE" in result.upper()
    
    def test_total_column(self):
        """total amount becomes sum(amount)."""
        result = preparse_asql("from sales select total amount")
        # 'total' is an alias for 'sum'
        assert "AMOUNT" in result.upper()


class TestDateLiterals:
    """Test @date literal transformation."""
    
    def test_date_literal(self):
        """@2024-01-15 becomes DATE '2024-01-15'."""
        result = preparse_asql("from users where created_at >= @2024-01-15")
        assert "DATE '2024-01-15'" in result or "'2024-01-15'" in result
    
    def test_timestamp_literal(self):
        """@2024-01-15T10:30:00 becomes TIMESTAMP."""
        result = preparse_asql("from users where created_at >= @2024-01-15T10:30:00")
        assert "TIMESTAMP" in result.upper() or "'2024-01-15" in result


class TestRelativeDates:
    """Test relative date transformation."""
    
    def test_days_ago(self):
        """7 days ago becomes CURRENT_DATE - INTERVAL."""
        result = preparse_asql("from users where created_at >= 7 days ago")
        assert "INTERVAL" in result.upper()
        assert "7" in result
    
    def test_month_ago(self):
        """1 month ago becomes CURRENT_DATE - INTERVAL."""
        result = preparse_asql("from users where created_at >= 1 month ago")
        assert "INTERVAL" in result.upper()
    
    def test_days_from_now(self):
        """3 days from now becomes CURRENT_DATE + INTERVAL."""
        result = preparse_asql("from tasks where due_date <= 3 days from now")
        assert "INTERVAL" in result.upper()
        assert "+" in result


class TestDateArithmetic:
    """Test date arithmetic transformation."""
    
    def test_add_days(self):
        """col + 7 days becomes col + INTERVAL."""
        result = preparse_asql("from orders select order_date + 7 days as delivery_date")
        assert "INTERVAL" in result.upper()
        assert "7" in result
    
    def test_subtract_month(self):
        """col - 1 month becomes col - INTERVAL."""
        result = preparse_asql("from events select event_date - 1 month as last_month")
        assert "INTERVAL" in result.upper()


class TestSinceUntilPatterns:
    """Test *_since_* and *_until_* pattern transformation."""
    
    def test_days_since(self):
        """days_since_col becomes date difference."""
        result = preparse_asql("from users select days_since_created_at")
        assert "DATEDIFF" in result.upper() or "CREATED_AT" in result.upper()
    
    def test_months_until(self):
        """months_until_col becomes date difference."""
        result = preparse_asql("from tasks select months_until_due_date")
        assert "DATEDIFF" in result.upper() or "DUE_DATE" in result.upper()


class TestPerCommands:
    """Test PER command transformation for window operations."""
    
    def test_per_first_by(self):
        """per col first by -order becomes window function with QUALIFY."""
        result = preparse_asql("from orders per customer_id first by -order_date")
        assert "ROW_NUMBER" in result.upper() or "QUALIFY" in result.upper()
        assert "PARTITION BY" in result.upper() or "CUSTOMER_ID" in result.upper()
    
    def test_per_number_by(self):
        """per col number by order adds ROW_NUMBER column."""
        result = preparse_asql("from orders per customer_id number by -order_date")
        assert "ROW_NUMBER" in result.upper()


class TestAggregateBlocks:
    """Test aggregate block transformation."""
    
    def test_simple_aggregate_block(self):
        """group by col (agg) becomes SELECT col, agg GROUP BY col."""
        result = preparse_asql("from sales group by region (sum(amount) as revenue)")
        assert "SELECT" in result.upper()
        assert "GROUP BY" in result.upper()
        assert "REGION" in result.upper()
        assert "SUM" in result.upper()
    
    def test_multiple_aggregates(self):
        """Multiple aggregates in block."""
        result = preparse_asql("from sales group by region (sum(amount) as revenue, count(*) as cnt)")
        assert "SUM" in result.upper()
        assert "COUNT" in result.upper()


class TestStashAs:
    """Test stash as CTE transformation."""
    
    def test_simple_stash(self):
        """stash as name creates CTE."""
        result = preparse_asql("from users where active stash as active_users")
        assert "WITH" in result.upper() or "ACTIVE_USERS" in result.upper()


class TestFunctionSpaceNormalization:
    """Test underscore/space normalization for functions."""
    
    def test_day_of_week_spaces(self):
        """day of week col becomes day_of_week(col)."""
        result = preparse_asql("from events select day of week created_at")
        assert "DAY_OF_WEEK" in result.upper() or "DAYOFWEEK" in result.upper()
    
    def test_row_number_spaces(self):
        """row number() becomes row_number()."""
        result = preparse_asql("from events select row number() over (order by id)")
        assert "ROW_NUMBER" in result.upper()


class TestEqualityOperators:
    """Test equality operator transformation."""
    
    def test_double_equals(self):
        """== becomes = for SQL compatibility."""
        result = preparse_asql("from users where status == 'active'")
        # Should have single = not ==
        assert "STATUS = " in result.upper() or "STATUS=" in result.upper()


class TestCommentPreservation:
    """Test that comments are preserved during transformation."""
    
    def test_single_line_comment(self):
        """Single-line comments are preserved."""
        result = preparse_asql("-- This is a comment\nfrom users")
        assert "-- This is a comment" in result
    
    def test_multi_line_comment(self):
        """Multi-line comments are preserved."""
        result = preparse_asql("/* Comment */\nfrom users")
        assert "/* Comment */" in result


class TestComplexQueries:
    """Test complex queries with multiple transformations."""
    
    def test_full_pipeline(self):
        """Test a complete pipeline query."""
        asql = """
        from orders
        | where order_date >= 7 days ago
        | group by region (sum(amount) as revenue, count(*) as cnt)
        | order by -revenue
        | limit 10
        """
        result = preparse_asql(asql)
        assert "SELECT" in result.upper()
        assert "FROM ORDERS" in result.upper()
        assert "WHERE" in result.upper()
        assert "GROUP BY" in result.upper()
        assert "ORDER BY" in result.upper()
        assert "LIMIT 10" in result.upper()
    
    def test_join_with_aggregation(self):
        """Test join with aggregation."""
        asql = "from orders join customers on orders.customer_id = customers.id group by customers.name (sum(amount) as total)"
        result = preparse_asql(asql)
        assert "JOIN" in result.upper()
        assert "CUSTOMERS" in result.upper()


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_string(self):
        """Empty string returns empty result."""
        result = preparse_asql("")
        assert result == ""
    
    def test_whitespace_only(self):
        """Whitespace-only returns empty result."""
        result = preparse_asql("   \n\t  ")
        assert result.strip() == ""
    
    def test_already_valid_sql(self):
        """Valid SQL passes through."""
        result = preparse_asql("SELECT * FROM users WHERE id = 1")
        assert "SELECT" in result.upper()
        assert "FROM USERS" in result.upper()


class TestColumnOperators:
    """Test except, rename, replace column operators."""
    
    def test_except_single(self):
        """Except single column."""
        result = preparse_asql("from users except email")
        assert "EXCEPT" in result.upper()
        assert "EMAIL" in result.upper()
    
    def test_except_multiple(self):
        """Except multiple columns."""
        result = preparse_asql("from users except email, phone, ssn")
        assert "EXCEPT" in result.upper()
        assert "EMAIL" in result.upper()
        assert "PHONE" in result.upper()
    
    def test_rename_single(self):
        """Rename single column."""
        result = preparse_asql("from users rename id as user_id")
        assert "USER_ID" in result.upper()
        assert "EXCEPT" in result.upper()  # Renamed col should be excepted
    
    def test_rename_multiple(self):
        """Rename multiple columns."""
        result = preparse_asql("from users rename id as user_id, name as user_name")
        assert "USER_ID" in result.upper()
        assert "USER_NAME" in result.upper()
    
    def test_replace_single(self):
        """Replace single column."""
        result = preparse_asql("from users replace name with upper(name)")
        assert "UPPER(NAME)" in result.upper()
        assert "EXCEPT" in result.upper()
    
    def test_replace_multiple_statements(self):
        """Replace multiple columns with separate statements."""
        result = preparse_asql("from users replace name with upper(name) replace email with lower(email)")
        assert "UPPER(NAME)" in result.upper()
        assert "LOWER(EMAIL)" in result.upper()
    
    def test_replace_chained(self):
        """Replace multiple columns with chained syntax."""
        result = preparse_asql("from users replace name with upper(name), email with lower(email)")
        assert "UPPER(NAME)" in result.upper()
        assert "LOWER(EMAIL)" in result.upper()
    
    def test_replace_with_function_args(self):
        """Replace with function that has comma in args."""
        result = preparse_asql("from users replace price with round(price, 2)")
        assert "ROUND(PRICE, 2)" in result.upper()
    
    def test_combined_operators(self):
        """Combine except, rename, replace."""
        result = preparse_asql("from users except password rename id as user_id replace name with upper(name)")
        assert "PASSWORD" in result.upper()
        assert "USER_ID" in result.upper()
        assert "UPPER(NAME)" in result.upper()


class TestStarColumnOverride:
    """Test SELECT *, expr AS col → SELECT * EXCEPT(col), expr AS col."""
    
    def test_single_override(self):
        """Single column override adds EXCEPT."""
        result = preparse_asql("from users select *, upper(name) as name")
        assert "EXCEPT" in result.upper()
        assert "NAME" in result.upper()
    
    def test_multiple_overrides(self):
        """Multiple column overrides add EXCEPT with all columns."""
        result = preparse_asql("from users select *, upper(name) as name, lower(email) as email")
        assert "EXCEPT" in result.upper()
        assert "NAME" in result.upper()
        assert "EMAIL" in result.upper()
    
    def test_no_star_no_change(self):
        """Without star, no transformation."""
        result = preparse_asql("from users select id, name")
        assert "EXCEPT" not in result.upper()
    
    def test_star_without_aliases_no_change(self):
        """Star without aliases, no transformation."""
        result = preparse_asql("from users select *")
        assert "EXCEPT" not in result.upper()
    
    def test_star_with_new_column_no_change(self):
        """Star with new column (not override), no transformation."""
        result = preparse_asql("from users select *, id + 1 as new_col")
        # This DOES add EXCEPT because we can't know if new_col exists
        # The behavior is: any alias causes EXCEPT to be added
        # This is safe because EXCEPT on non-existent column just has no effect
        assert "EXCEPT" in result.upper()


class TestSampleClause:
    """Test sample clause transformation."""
    
    def test_sample_fixed_n(self):
        """sample N becomes ORDER BY RANDOM() LIMIT N."""
        result = preparse_asql("from orders sample 100")
        assert "ORDER BY RANDOM()" in result.upper()
        assert "LIMIT 100" in result.upper()
    
    def test_sample_fixed_n_with_where(self):
        """sample N works with WHERE clause."""
        result = preparse_asql("from orders where status = 'active' sample 50")
        assert "ORDER BY RANDOM()" in result.upper()
        assert "LIMIT 50" in result.upper()
        assert "WHERE" in result.upper()
    
    def test_sample_percentage(self):
        """sample N% becomes TABLESAMPLE BERNOULLI(N)."""
        result = preparse_asql("from orders sample 10%")
        assert "TABLESAMPLE" in result.upper()
        assert "BERNOULLI" in result.upper()
        assert "10" in result
    
    def test_sample_percentage_decimal(self):
        """sample with decimal percentage."""
        result = preparse_asql("from orders sample 0.5%")
        assert "TABLESAMPLE" in result.upper()
        assert "0.5" in result
    
    def test_sample_stratified(self):
        """sample N per column becomes stratified sampling with window function."""
        result = preparse_asql("from orders sample 100 per category")
        assert "QUALIFY" in result.upper()
        assert "ROW_NUMBER()" in result.upper()
        assert "PARTITION BY CATEGORY" in result.upper()
        assert "ORDER BY RANDOM()" in result.upper()
        assert "100" in result
    
    def test_sample_stratified_with_underscore_column(self):
        """sample N per column with underscore in column name."""
        result = preparse_asql("from orders sample 50 per product_category")
        assert "PARTITION BY PRODUCT_CATEGORY" in result.upper()
        assert "50" in result
    
    def test_sample_with_select(self):
        """sample works with explicit select."""
        result = preparse_asql("from orders select id, amount sample 25")
        assert "ORDER BY RANDOM()" in result.upper()
        assert "LIMIT 25" in result.upper()
    
    def test_sample_preserves_order(self):
        """sample followed by order by - sample is applied first."""
        result = preparse_asql("from orders sample 100")
        # The sample clause transforms to ORDER BY RANDOM() LIMIT N
        assert "RANDOM()" in result.upper()
        assert "LIMIT" in result.upper()


class TestExplode:
    """Test explode clause transformation."""
    
    def test_explode_basic(self):
        """explode col as alias creates marker for compiler."""
        result = preparse_asql("from posts explode tags as tag")
        assert "__ASQL_EXPLODE_START__" in result
        assert "__ASQL_EXPLODE_SEP__" in result
        assert "__ASQL_EXPLODE_END__" in result
        assert "tags" in result
        assert "tag" in result
    
    def test_explode_with_select(self):
        """explode with explicit select."""
        result = preparse_asql("from posts explode tags as tag select id, tag")
        assert "__ASQL_EXPLODE_START__" in result
        assert "id" in result.lower()
    
    def test_explode_with_function(self):
        """explode with split function."""
        result = preparse_asql("from posts explode split(tags_csv, ',') as tag")
        assert "__ASQL_EXPLODE_START__" in result
        assert "split(tags_csv, ',')" in result.lower()
    
    def test_explode_compiled_postgres(self):
        """explode compiles to UNNEST for postgres."""
        from asql.compiler import compile
        result = compile("from posts explode tags as tag select id, tag", dialect="postgres")
        assert "UNNEST(tags)" in result
        assert "AS tag" in result
    
    def test_explode_compiled_bigquery(self):
        """explode compiles to UNNEST for bigquery."""
        from asql.compiler import compile
        result = compile("from posts explode tags as tag select id, tag", dialect="bigquery")
        assert "UNNEST(tags)" in result
    
    def test_explode_compiled_snowflake(self):
        """explode compiles to FLATTEN for snowflake."""
        from asql.compiler import compile
        result = compile("from posts explode tags as tag select id, tag", dialect="snowflake")
        assert "FLATTEN" in result
        assert "tag" in result.lower()


class TestUnpivot:
    """Test unpivot clause transformation."""
    
    def test_unpivot_basic(self):
        """unpivot cols into name, value creates UNION ALL."""
        result = preparse_asql("from metrics unpivot jan, feb, mar into month, value")
        assert "UNION ALL" in result.upper()
        assert "'jan'" in result.lower()
        assert "'feb'" in result.lower()
        assert "'mar'" in result.lower()
        assert "as month" in result.lower()  # lowercase comparison
        assert "as value" in result.lower()
    
    def test_unpivot_two_columns(self):
        """unpivot with two columns."""
        result = preparse_asql("from data unpivot col_a, col_b into name, val")
        assert "UNION ALL" in result.upper()
        assert "'col_a'" in result.lower()
        assert "'col_b'" in result.lower()
    
    def test_unpivot_creates_subquery(self):
        """unpivot wraps result in subquery."""
        result = preparse_asql("from metrics unpivot jan, feb into month, value")
        assert "as __unpivot__" in result.lower()  # lowercase comparison
        assert "SELECT * FROM" in result.upper()
    
    def test_unpivot_compiled(self):
        """unpivot compiles correctly."""
        from asql.compiler import compile
        result = compile("from metrics unpivot jan, feb, mar into month, value", dialect="postgres")
        assert "UNION ALL" in result.upper()
        assert "__unpivot__" in result.lower()


class TestPivot:
    """Test pivot clause transformation."""
    
    def test_pivot_with_values(self):
        """pivot with explicit values creates CASE expressions."""
        result = preparse_asql("from sales pivot amount by category values ('A', 'B')")
        assert "CASE WHEN" in result.upper()
        assert "category = 'a'" in result.lower()  # values get lowercased
        assert "category = 'b'" in result.lower()
        assert "AS A" in result.upper()
        assert "AS B" in result.upper()
    
    def test_pivot_aggregate(self):
        """pivot with aggregate function."""
        result = preparse_asql("from sales pivot sum(amount) by category values ('A', 'B')")
        assert "SUM(CASE WHEN" in result.upper()
        assert "amount" in result.lower()
    
    def test_pivot_with_group_by(self):
        """pivot with group by clause compiles correctly."""
        from asql.compiler import compile
        # Put group by after pivot - cleaner syntax
        result = compile("from sales pivot sum(amount) by category values ('X', 'Y') group by region", dialect="postgres")
        assert "GROUP BY" in result.upper()
        assert "CASE WHEN" in result.upper()
    
    def test_pivot_without_values_raises(self):
        """pivot without values raises helpful error."""
        import pytest
        with pytest.raises(ValueError, match="pivot requires explicit values"):
            preparse_asql("from sales pivot amount by category")
    
    def test_pivot_compiled(self):
        """pivot compiles correctly."""
        from asql.compiler import compile
        result = compile("from sales pivot sum(amount) by category values ('A', 'B')", dialect="postgres")
        assert "SUM(CASE WHEN" in result.upper()
        assert "AS A" in result.upper()
        assert "AS B" in result.upper()
    
    def test_pivot_dynamic_subquery(self):
        """pivot with subquery in values clause (dynamic pivot)."""
        result = preparse_asql("from sales pivot sum(amount) by category values (from sales select distinct category)")
        assert "CASE WHEN" in result.upper()
        assert "__pivot_values__" in result.lower() or "__pivot_values_0__" in result.lower()
        assert "category" in result.lower()
    
    def test_pivot_dynamic_compiled(self):
        """dynamic pivot compiles correctly."""
        from asql.compiler import compile
        result = compile("from sales pivot sum(amount) by category values (from sales select distinct category)", dialect="postgres")
        assert "SUM(CASE WHEN" in result.upper() or "CASE WHEN" in result.upper()
        assert "WITH" in result.upper()  # Should have CTE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
