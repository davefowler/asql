"""Tests for shared join inference utilities."""

from asql.preparse.inference import infer_fk_column, infer_join_key_from_schema


class TestInferFkColumn:
    """Tests for infer_fk_column function."""
    
    def test_plural_table_name(self):
        """Test singularization of plural table names."""
        assert infer_fk_column("users") == "user_id"
        assert infer_fk_column("customers") == "customer_id"
        assert infer_fk_column("orders") == "order_id"
        assert infer_fk_column("products") == "product_id"
    
    def test_singular_table_name(self):
        """Test handling of already-singular table names."""
        assert infer_fk_column("user") == "user_id"
        assert infer_fk_column("customer") == "customer_id"
        assert infer_fk_column("order") == "order_id"
    
    def test_table_not_ending_in_s(self):
        """Test tables that don't end in 's'."""
        assert infer_fk_column("staff") == "staff_id"
        assert infer_fk_column("person") == "person_id"
        assert infer_fk_column("data") == "data_id"
    
    def test_irregular_plurals_not_handled(self):
        """Test that irregular plurals are not specially handled.
        
        Note: This is expected behavior - irregular plurals like 'people'
        will produce 'people_id' not 'person_id'. Users should use explicit
        join keys for these cases.
        """
        # 'people' -> 'people_id' (not 'person_id')
        assert infer_fk_column("people") == "people_id"
        # 'children' -> 'children_id' (not 'child_id')
        assert infer_fk_column("children") == "children_id"


class TestInferJoinKeyFromSchema:
    """Tests for infer_join_key_from_schema function."""
    
    def test_no_schema_returns_none(self):
        """Test that None is returned when no schema is provided."""
        assert infer_join_key_from_schema("orders", "users", None) is None
    
    def test_schema_with_relationship(self):
        """Test schema-based lookup when relationship exists."""
        from asql.schema import Schema, Table, Column, Relationship
        
        # Create a schema with orders -> users relationship
        schema = Schema(
            tables=[
                Table(name="orders", columns=[
                    Column(name="id"),
                    Column(name="user_id"),
                ]),
                Table(name="users", columns=[
                    Column(name="id"),
                    Column(name="name"),
                ]),
            ],
            relationships=[
                Relationship(
                    from_table="orders",
                    from_column="user_id",
                    to_table="users",
                    to_column="id",
                ),
            ],
        )
        
        # Forward lookup: orders -> users
        result = infer_join_key_from_schema("orders", "users", schema)
        assert result == "user_id"
    
    def test_schema_with_reverse_relationship(self):
        """Test schema-based lookup for reverse direction."""
        from asql.schema import Schema, Table, Column, Relationship
        
        # Create a schema with orders -> users relationship
        schema = Schema(
            tables=[
                Table(name="orders", columns=[
                    Column(name="id"),
                    Column(name="user_id"),
                ]),
                Table(name="users", columns=[
                    Column(name="id"),
                    Column(name="name"),
                ]),
            ],
            relationships=[
                Relationship(
                    from_table="orders",
                    from_column="user_id",
                    to_table="users",
                    to_column="id",
                ),
            ],
        )
        
        # Reverse lookup: users -> orders (should find the relationship)
        result = infer_join_key_from_schema("users", "orders", schema)
        assert result == "id"  # to_column from the reverse relationship
    
    def test_schema_without_matching_relationship(self):
        """Test that None is returned when no matching relationship exists."""
        from asql.schema import Schema, Table, Column
        
        schema = Schema(
            tables=[
                Table(name="orders", columns=[Column(name="id")]),
                Table(name="products", columns=[Column(name="id")]),
            ],
            relationships=[],
        )
        
        result = infer_join_key_from_schema("orders", "products", schema)
        assert result is None
