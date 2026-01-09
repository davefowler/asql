"""Tests for shared join inference logic."""

import pytest
from asql.compiler.join_inference import resolve_join_condition, JoinCondition
from asql.schema import Schema, Table, Column, Relationship


class TestResolveJoinCondition:
    """Test the unified join condition resolution."""
    
    def test_explicit_relationship_takes_precedence(self) -> None:
        """Explicit relationships should be used first."""
        schema = Schema()
        schema.add_table(Table.from_column_list("orders", ["id", "customer_id"]))
        schema.add_table(Table.from_column_list("customers", ["id", "name"]))
        schema.add_relationship(Relationship(
            from_table="orders",
            from_column="customer_id",
            to_table="customers",
            to_column="id",
            source="explicit"
        ))
        
        condition = resolve_join_condition("orders", "customers", schema)
        
        assert condition is not None
        assert condition.source == "explicit"
        assert condition.left_column == "customer_id"
        assert condition.right_column == "id"
    
    def test_inferred_relationship_used_when_no_explicit(self) -> None:
        """Inferred relationships should be used when no explicit exists."""
        schema = Schema()
        schema.add_table(Table.from_column_list("orders", ["id", "user_id"]))
        schema.add_table(Table.from_column_list("users", ["id", "name"]))
        schema.infer_relationships()
        
        condition = resolve_join_condition("orders", "users", schema)
        
        assert condition is not None
        assert condition.source == "inferred"
        assert condition.left_column == "user_id"
        assert condition.right_column == "id"
    
    def test_hint_column_with_schema(self) -> None:
        """Hint column should help resolve when schema available."""
        schema = Schema()
        users = Table(name="users")
        users.add_column(Column(name="user_id", primary_key=True))
        users.add_column(Column(name="name"))
        schema.add_table(users)
        
        orders = Table(name="orders")
        orders.add_column(Column(name="id", primary_key=True))
        orders.add_column(Column(name="user_id"))
        schema.add_table(orders)
        
        condition = resolve_join_condition("orders", "users", schema, hint_column="user_id")
        
        assert condition is not None
        # user_id IS the PK of users, so should be detected
        assert condition.left_column == "user_id"
        assert condition.right_column == "user_id"
    
    def test_convention_fallback_without_schema(self) -> None:
        """Without schema, should use convention-based guessing."""
        condition = resolve_join_condition("orders", "users", schema=None)
        
        assert condition is not None
        assert condition.source == "convention"
        assert condition.left_column == "user_id"  # {singular}_id convention
        assert condition.right_column == "id"
    
    def test_convention_fallback_with_hint(self) -> None:
        """With hint but no schema, should use hint on left, 'id' on right."""
        condition = resolve_join_condition("orders", "customers", schema=None, hint_column="customer_id")
        
        assert condition is not None
        assert condition.source == "convention"
        assert condition.left_column == "customer_id"
        assert condition.right_column == "id"
    
    def test_singularization_variations(self) -> None:
        """Test various table name singularization."""
        # Regular plural
        condition = resolve_join_condition("orders", "users", schema=None)
        assert condition.left_column == "user_id"
        
        # -ies → -y
        condition = resolve_join_condition("orders", "categories", schema=None)
        assert condition.left_column == "category_id"
        
        # -es ending
        condition = resolve_join_condition("orders", "boxes", schema=None)
        assert condition.left_column == "box_id"
    
    def test_as_sql(self) -> None:
        """Test the as_sql helper method."""
        condition = JoinCondition(
            left_table="orders",
            left_column="user_id",
            right_table="users",
            right_column="id",
            source="explicit"
        )
        
        assert condition.as_sql() == "orders.user_id = users.id"


class TestJoinConditionDataclass:
    """Test the JoinCondition dataclass."""
    
    def test_attributes(self) -> None:
        """Test that all attributes are accessible."""
        condition = JoinCondition(
            left_table="a",
            left_column="b_id",
            right_table="b",
            right_column="id",
            source="inferred"
        )
        
        assert condition.left_table == "a"
        assert condition.left_column == "b_id"
        assert condition.right_table == "b"
        assert condition.right_column == "id"
        assert condition.source == "inferred"

