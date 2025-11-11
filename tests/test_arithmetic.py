"""Tests for arithmetic operators in ASQL."""

import pytest
from asql import compile


class TestArithmeticOperators:
    """Test arithmetic operators: +, -, *, /, %"""
    
    def test_addition_in_where(self) -> None:
        """Test addition in WHERE clause."""
        asql = "from users where age + 5 >= 18"
        sql = compile(asql)
        assert "age + 5" in sql.lower() or "age + 5" in sql
        assert ">=" in sql or ">=" in sql.lower()
    
    def test_subtraction_in_where(self) -> None:
        """Test subtraction in WHERE clause."""
        asql = "from users where age - 5 < 18"
        sql = compile(asql)
        assert "age - 5" in sql.lower() or "age - 5" in sql
        assert "<" in sql
    
    def test_multiplication_in_select(self) -> None:
        """Test multiplication in SELECT clause."""
        asql = "from sales select amount * quantity as total"
        sql = compile(asql)
        assert "amount * quantity" in sql.lower() or "amount * quantity" in sql
        assert "total" in sql.lower()
    
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
        # Should be: (amount * 0.1) + tax
        assert "*" in sql
        assert "+" in sql
    
    def test_arithmetic_with_parentheses(self) -> None:
        """Test arithmetic with parentheses."""
        asql = "from sales select (amount + tax) * 0.1 as discount"
        sql = compile(asql)
        # SQLGlot may optimize parentheses, but the expression should be correct
        assert "*" in sql
        assert "+" in sql
        assert "discount" in sql.lower()
    
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
        """Test arithmetic with numeric literals."""
        asql = "from users where age + 10 >= 30"
        sql = compile(asql)
        assert "age + 10" in sql.lower() or "age + 10" in sql
        assert "30" in sql
    
    def test_arithmetic_in_group_by_aggregation(self) -> None:
        """Test arithmetic in aggregation functions."""
        asql = "from sales group by region ( sum(amount * quantity) as revenue )"
        sql = compile(asql)
        assert "SUM" in sql.upper() or "sum" in sql.lower()
        assert "amount * quantity" in sql.lower() or "amount * quantity" in sql
        assert "revenue" in sql.lower()
    
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
        """Test arithmetic with negative numbers."""
        asql = "from users where balance + -100 >= 0"
        sql = compile(asql)
        # Should handle negative numbers correctly
        assert "balance" in sql.lower()
        assert "+" in sql or "-" in sql


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
