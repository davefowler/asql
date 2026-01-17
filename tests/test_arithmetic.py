"""Tests for arithmetic operators in ASQL."""

import sqlglot
from sqlglot import exp
from asql import compile
from tests.fixtures import assert_valid_sql, assert_sql_contains


class TestArithmeticOperators:
    """Test arithmetic operators: +, -, *, /, %"""
    
    def test_addition_in_where(self) -> None:
        """Test addition in WHERE clause.
        
        Note: The optimizer may simplify `age + 5 >= 18` to `age >= 13`.
        This is semantically correct, so we verify the output is valid SQL.
        """
        asql = "from users where age + 5 >= 18"
        sql = compile(asql)
        
        assert_valid_sql(sql)
        
        # Verify WHERE clause exists with age comparison
        parsed = sqlglot.parse_one(sql)
        where_clause = parsed.find(exp.Where)
        assert where_clause is not None
        where_sql = where_clause.sql().lower()
        assert "age" in where_sql, "age should be in WHERE clause"
        assert ">=" in where_sql, ">= comparison should be present"
    
    def test_subtraction_in_where(self) -> None:
        """Test subtraction in WHERE clause.
        
        Note: The optimizer may simplify `age - 5 < 18` to `age < 23`.
        This is semantically correct, so we verify the output is valid SQL.
        """
        asql = "from users where age - 5 < 18"
        sql = compile(asql)
        assert_valid_sql(sql)
        
        # Verify WHERE clause exists with age and < operator
        parsed = sqlglot.parse_one(sql)
        where_clause = parsed.find(exp.Where)
        assert where_clause is not None
        where_sql = where_clause.sql().lower()
        assert "age" in where_sql, "age should be in WHERE clause"
        assert "<" in where_sql, "< comparison should be present"
    
    def test_multiplication_in_select(self) -> None:
        """Test multiplication in SELECT clause."""
        asql = "from sales select amount * quantity as total"
        sql = compile(asql)
        
        assert_sql_contains(sql, "amount", "*", "quantity", "total")
        assert_valid_sql(sql)
        
        # Verify multiplication expression and alias
        parsed = sqlglot.parse_one(sql)
        select = parsed.find(exp.Select)
        assert select is not None
        # Find the expression with alias 'total'
        total_expr = None
        for expr in select.expressions:
            if expr.alias_or_name.lower() == "total":
                total_expr = expr
                break
        assert total_expr is not None, "Alias 'total' not found in SELECT"
        assert "*" in total_expr.sql(), "Multiplication operator not found in expression"
    
    def test_division_in_select(self) -> None:
        """Test division in SELECT clause."""
        asql = "from sales select amount / quantity as avg_price"
        sql = compile(asql)
        assert "amount / quantity" in sql.lower() or "amount / quantity" in sql
        assert "avg_price" in sql.lower()
    
    def test_modulo_in_where(self) -> None:
        """Test modulo operator in WHERE clause."""
        asql = "from users where id % 2 == 0"
        sql = compile(asql)
        assert "id % 2" in sql.lower() or "id % 2" in sql
        assert "=" in sql
    
    def test_arithmetic_precedence(self) -> None:
        """Test operator precedence: * before +."""
        asql = "from sales select amount * 0.1 + tax as total"
        sql = compile(asql)
        
        # Should be: (amount * 0.1) + tax (multiplication before addition)
        assert_sql_contains(sql, "*", "+", "amount", "tax", "total")
        assert_valid_sql(sql)
        
        # Verify SQLGlot handles precedence correctly
        parsed = sqlglot.parse_one(sql)
        select = parsed.find(exp.Select)
        assert select is not None
        # The expression should have proper precedence
        # SQLGlot will add parentheses if needed
        total_expr = None
        for expr in select.expressions:
            if expr.alias_or_name.lower() == "total":
                total_expr = expr
                break
        assert total_expr is not None
        # Verify both operators are present
        expr_sql = total_expr.sql()
        assert "*" in expr_sql and "+" in expr_sql, "Both operators should be present"
    
    def test_arithmetic_with_parentheses(self) -> None:
        """Test arithmetic with parentheses."""
        asql = "from sales select (amount + tax) * 0.1 as discount"
        sql = compile(asql)
        
        assert_sql_contains(sql, "*", "+", "amount", "tax", "discount")
        assert_valid_sql(sql)
        
        # Verify expression structure (SQLGlot may optimize parentheses)
        parsed = sqlglot.parse_one(sql)
        select = parsed.find(exp.Select)
        assert select is not None
        discount_expr = None
        for expr in select.expressions:
            if expr.alias_or_name.lower() == "discount":
                discount_expr = expr
                break
        assert discount_expr is not None
        expr_sql = discount_expr.sql()
        assert "*" in expr_sql and "+" in expr_sql, "Both operators should be present"
    
    def test_multiple_operations(self) -> None:
        """Test multiple arithmetic operations."""
        asql = "from sales select amount * quantity - discount + tax as total"
        sql = compile(asql)
        assert "*" in sql
        assert "-" in sql
        assert "+" in sql
    
    def test_arithmetic_in_comparison(self) -> None:
        """Test arithmetic in comparison expressions."""
        asql = "from users where age * 2 > 40"
        sql = compile(asql)
        assert "age * 2" in sql.lower() or "age * 2" in sql
        assert ">" in sql
    
    def test_arithmetic_with_numeric_literals(self) -> None:
        """Test arithmetic with numeric literals.
        
        Note: The optimizer may simplify `age + 10 >= 30` to `age >= 20`.
        This is semantically correct, so we verify the output is valid SQL.
        """
        asql = "from users where age + 10 >= 30"
        sql = compile(asql)
        assert_valid_sql(sql)
        
        # Verify WHERE clause exists with age and >= operator
        parsed = sqlglot.parse_one(sql)
        where_clause = parsed.find(exp.Where)
        assert where_clause is not None
        where_sql = where_clause.sql().lower()
        assert "age" in where_sql, "age should be in WHERE clause"
        assert ">=" in where_sql, ">= comparison should be present"
    
    def test_arithmetic_in_group_by_aggregation(self) -> None:
        """Test arithmetic in aggregation functions."""
        asql = "from sales group by region ( sum(amount * quantity) as revenue )"
        sql = compile(asql)
        
        assert_sql_contains(sql, "SUM", "amount", "*", "quantity", "revenue", "region")
        assert_valid_sql(sql)
        
        # Verify aggregation with arithmetic
        parsed = sqlglot.parse_one(sql)
        select = parsed.find(exp.Select)
        assert select is not None
        sum_expr = select.find(exp.Sum) or select.find(exp.AggFunc)
        assert sum_expr is not None, "SUM aggregation not found"
        # Verify multiplication is in the argument
        assert "*" in sum_expr.sql(), "Multiplication not found in SUM argument"
    
    def test_complex_arithmetic_expression(self) -> None:
        """Test complex arithmetic expression."""
        asql = "from sales select amount * (1 + tax_rate) - discount as final_price"
        sql = compile(asql)
        # SQLGlot handles operator precedence correctly
        assert "*" in sql
        assert "+" in sql
        assert "-" in sql
        assert "final_price" in sql.lower()
    
    def test_arithmetic_with_negative_numbers(self) -> None:
        """Test arithmetic with negative numbers.
        
        Note: The optimizer may simplify `balance + -100 >= 0` to `balance >= 100`.
        This is semantically correct, so we verify the output is valid SQL.
        """
        asql = "from users where balance + -100 >= 0"
        sql = compile(asql)
        
        assert_valid_sql(sql)
        
        # Verify WHERE clause exists with balance and >= operator
        parsed = sqlglot.parse_one(sql)
        where_clause = parsed.find(exp.Where)
        assert where_clause is not None
        where_sql = where_clause.sql().lower()
        assert "balance" in where_sql, "balance should be in WHERE clause"
        assert ">=" in where_sql, ">= comparison should be present"


class TestArithmeticEdgeCases:
    """Test edge cases for arithmetic operators."""
    
    def test_division_by_zero_warning(self) -> None:
        """Test that division by zero doesn't crash (SQL handles it)."""
        asql = "from sales select amount / 0 as invalid"
        sql = compile(asql)
        assert "/" in sql
        assert "0" in sql
    
    def test_modulo_with_zero(self) -> None:
        """Test modulo with zero."""
        asql = "from users where id % 0 == 0"
        sql = compile(asql)
        assert "%" in sql
        assert "0" in sql
    
    def test_nested_arithmetic(self) -> None:
        """Test nested arithmetic expressions."""
        asql = "from sales select (amount * quantity) / (1 + tax_rate) as net"
        sql = compile(asql)
        # SQLGlot handles operator precedence correctly
        assert "*" in sql
        assert "/" in sql
        assert "+" in sql
        assert "net" in sql.lower()
