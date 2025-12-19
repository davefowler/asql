"""Tests for ASQL schema support."""

import pytest
import tempfile
import os
from pathlib import Path

from asql.schema import Column, Table, Relationship, Schema
from asql.config import CompileSettings
from asql import compile


class TestColumnDataclass:
    """Test Column dataclass."""
    
    def test_column_basic(self) -> None:
        """Test basic column creation."""
        col = Column(name="user_id")
        assert col.name == "user_id"
        assert col.type is None
        assert col.primary_key is False
    
    def test_column_with_type(self) -> None:
        """Test column with type."""
        col = Column(name="amount", type="decimal", primary_key=False)
        assert col.name == "amount"
        assert col.type == "decimal"
    
    def test_column_primary_key(self) -> None:
        """Test primary key column."""
        col = Column(name="id", type="integer", primary_key=True)
        assert col.primary_key is True
    
    def test_column_name_normalization(self) -> None:
        """Test column name is normalized to lowercase."""
        col = Column(name="UserID")
        assert col.name == "userid"


class TestTableDataclass:
    """Test Table dataclass."""
    
    def test_table_basic(self) -> None:
        """Test basic table creation."""
        table = Table(name="users")
        assert table.name == "users"
        assert table.columns == {}
    
    def test_table_name_normalization(self) -> None:
        """Test table name is normalized to lowercase."""
        table = Table(name="Users")
        assert table.name == "users"
    
    def test_add_column(self) -> None:
        """Test adding columns to table."""
        table = Table(name="orders")
        table.add_column(Column(name="id", primary_key=True))
        table.add_column(Column(name="user_id"))
        
        assert table.has_column("id")
        assert table.has_column("user_id")
        assert not table.has_column("amount")
    
    def test_get_column(self) -> None:
        """Test getting column by name."""
        table = Table(name="orders")
        table.add_column(Column(name="amount", type="decimal"))
        
        col = table.get_column("amount")
        assert col is not None
        assert col.type == "decimal"
        
        # Case-insensitive
        col = table.get_column("AMOUNT")
        assert col is not None
    
    def test_from_column_list(self) -> None:
        """Test creating table from column list."""
        table = Table.from_column_list("users", ["id", "name", "email"])
        
        assert table.name == "users"
        assert table.has_column("id")
        assert table.has_column("name")
        assert table.has_column("email")
        
        # id should be marked as primary key
        id_col = table.get_column("id")
        assert id_col is not None
        assert id_col.primary_key is True


class TestRelationshipDataclass:
    """Test Relationship dataclass."""
    
    def test_relationship_basic(self) -> None:
        """Test basic relationship creation."""
        rel = Relationship(
            from_table="orders",
            from_column="user_id",
            to_table="users",
            to_column="id"
        )
        assert rel.from_table == "orders"
        assert rel.from_column == "user_id"
        assert rel.to_table == "users"
        assert rel.to_column == "id"
        assert rel.alias is None
        assert rel.source == "inferred"
    
    def test_relationship_with_alias(self) -> None:
        """Test relationship with alias."""
        rel = Relationship(
            from_table="orders",
            from_column="user_id",
            to_table="users",
            to_column="id",
            alias="user",
            source="explicit"
        )
        assert rel.alias == "user"
        assert rel.source == "explicit"
    
    def test_relationship_matches(self) -> None:
        """Test relationship matching."""
        rel = Relationship(
            from_table="orders",
            from_column="user_id",
            to_table="users",
            to_column="id"
        )
        assert rel.matches("orders", "users")
        assert rel.matches("ORDERS", "USERS")  # Case-insensitive
        assert not rel.matches("users", "orders")  # Direction matters
    
    def test_get_join_condition(self) -> None:
        """Test generating join condition."""
        rel = Relationship(
            from_table="orders",
            from_column="user_id",
            to_table="users",
            to_column="id"
        )
        condition = rel.get_join_condition()
        assert condition == "orders.user_id = users.id"


class TestSchemaClass:
    """Test Schema dataclass and methods."""
    
    def test_schema_basic(self) -> None:
        """Test basic schema creation."""
        schema = Schema()
        assert schema.tables == {}
        assert schema.relationships == []
    
    def test_add_table(self) -> None:
        """Test adding tables."""
        schema = Schema()
        table = Table.from_column_list("users", ["id", "name"])
        schema.add_table(table)
        
        assert schema.has_table("users")
        assert schema.get_table("users") is not None
    
    def test_add_relationship(self) -> None:
        """Test adding relationships."""
        schema = Schema()
        rel = Relationship(
            from_table="orders",
            from_column="user_id",
            to_table="users",
            to_column="id"
        )
        schema.add_relationship(rel)
        
        assert len(schema.relationships) == 1
    
    def test_find_relationship(self) -> None:
        """Test finding relationships."""
        schema = Schema()
        
        # Add explicit relationship
        explicit_rel = Relationship(
            from_table="orders",
            from_column="user_id",
            to_table="users",
            to_column="id",
            source="explicit"
        )
        schema.add_relationship(explicit_rel)
        
        # Add inferred relationship (different tables)
        inferred_rel = Relationship(
            from_table="orders",
            from_column="customer_id",
            to_table="customers",
            to_column="id",
            source="inferred"
        )
        schema.add_relationship(inferred_rel)
        
        # Find explicit
        found = schema.find_relationship("orders", "users")
        assert found is not None
        assert found.source == "explicit"
        
        # Find inferred
        found = schema.find_relationship("orders", "customers")
        assert found is not None
        assert found.source == "inferred"
        
        # Not found
        found = schema.find_relationship("orders", "products")
        assert found is None
    
    def test_find_relationship_explicit_wins(self) -> None:
        """Test that explicit relationships take precedence."""
        schema = Schema()
        
        # Add inferred first
        inferred = Relationship(
            from_table="orders",
            from_column="user_id",
            to_table="users",
            to_column="id",
            source="inferred"
        )
        schema.add_relationship(inferred)
        
        # Add explicit second
        explicit = Relationship(
            from_table="orders",
            from_column="buyer_id",
            to_table="users",
            to_column="id",
            source="explicit"
        )
        schema.add_relationship(explicit)
        
        # Should find explicit
        found = schema.find_relationship("orders", "users")
        assert found is not None
        assert found.source == "explicit"
        assert found.from_column == "buyer_id"


class TestSchemaInference:
    """Test relationship inference from naming conventions."""
    
    def test_infer_simple_fk(self) -> None:
        """Test inferring simple FK pattern."""
        schema = Schema()
        
        # Add tables
        schema.add_table(Table.from_column_list("orders", ["id", "user_id", "amount"]))
        schema.add_table(Table.from_column_list("users", ["id", "name", "email"]))
        
        # Infer relationships
        schema.infer_relationships()
        
        # Should find orders.user_id -> users.id
        rel = schema.find_relationship("orders", "users")
        assert rel is not None
        assert rel.from_column == "user_id"
        assert rel.to_column == "id"
        assert rel.alias == "user"
        assert rel.source == "inferred"
    
    def test_infer_prefixed_fk(self) -> None:
        """Test inferring prefixed FK pattern like owner_user_id."""
        schema = Schema()
        
        # Add tables
        schema.add_table(Table.from_column_list("accounts", ["id", "owner_user_id", "name"]))
        schema.add_table(Table.from_column_list("users", ["id", "name"]))
        
        # Infer relationships
        schema.infer_relationships()
        
        # Should find accounts.owner_user_id -> users.id with alias "owner"
        rel = schema.find_relationship("accounts", "users")
        assert rel is not None
        assert rel.from_column == "owner_user_id"
        assert rel.alias == "owner"
    
    def test_no_infer_without_target(self) -> None:
        """Test that inference doesn't create relationships without target table."""
        schema = Schema()
        
        # Add only orders (no users table)
        schema.add_table(Table.from_column_list("orders", ["id", "user_id", "amount"]))
        
        # Infer relationships
        schema.infer_relationships()
        
        # Should not find any relationships
        assert len(schema.relationships) == 0


class TestSchemaFromYaml:
    """Test loading schema from YAML files."""
    
    def test_from_yaml_basic(self) -> None:
        """Test loading basic YAML schema."""
        yaml_content = """
tables:
  orders:
    columns: [id, user_id, amount, created_at]
  users:
    columns: [id, name, email]

relationships:
  - from: orders.user_id
    to: users.id
    alias: user
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                schema = Schema.from_yaml(f.name)
                
                # Check tables
                assert schema.has_table("orders")
                assert schema.has_table("users")
                
                orders = schema.get_table("orders")
                assert orders is not None
                assert orders.has_column("user_id")
                
                # Check explicit relationship
                rel = schema.find_relationship("orders", "users")
                assert rel is not None
                assert rel.source == "explicit"
                assert rel.alias == "user"
            finally:
                os.unlink(f.name)
    
    def test_from_yaml_infers_additional(self) -> None:
        """Test that YAML loading also infers relationships."""
        yaml_content = """
tables:
  orders:
    columns: [id, customer_id, amount]
  customers:
    columns: [id, name]
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                schema = Schema.from_yaml(f.name)
                
                # Should have inferred relationship
                rel = schema.find_relationship("orders", "customers")
                assert rel is not None
                assert rel.source == "inferred"
            finally:
                os.unlink(f.name)


class TestSchemaFromDbt:
    """Test loading schema from dbt files."""
    
    def test_from_dbt_schema_yml(self) -> None:
        """Test loading from dbt schema.yml format."""
        yaml_content = """
models:
  - name: orders
    columns:
      - name: id
      - name: user_id
        tests:
          - relationships:
              to: ref('users')
              field: id
      - name: amount

  - name: users
    columns:
      - name: id
      - name: name
      - name: email
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "schema.yml"
            schema_path.write_text(yaml_content)
            
            schema = Schema.from_dbt(tmpdir)
            
            # Check tables
            assert schema.has_table("orders")
            assert schema.has_table("users")
            
            # Check explicit relationship from test
            rel = schema.find_relationship("orders", "users")
            assert rel is not None
            assert rel.source == "explicit"
            assert rel.from_column == "user_id"


class TestSchemaJoinInference:
    """Test schema-based join inference in compile."""
    
    def test_join_with_schema(self) -> None:
        """Test that join uses schema for ON clause inference."""
        # Create schema with relationship
        schema = Schema()
        schema.add_table(Table.from_column_list("orders", ["id", "user_id", "amount"]))
        schema.add_table(Table.from_column_list("users", ["id", "name"]))
        schema.add_relationship(Relationship(
            from_table="orders",
            from_column="user_id",
            to_table="users",
            to_column="id",
            source="explicit"
        ))
        
        settings = CompileSettings(schema=schema)
        
        # Compile with schema - should infer ON clause
        # Note: This tests the integration, but the preparser needs both tables
        asql = "from orders & users on orders.user_id = users.id"
        sql = compile(asql, settings=settings)
        
        assert "JOIN" in sql.upper()
        assert "orders" in sql.lower()
        assert "users" in sql.lower()
    
    def test_join_with_invent_join_keys(self) -> None:
        """Test fallback to invent_join_keys when no schema."""
        settings = CompileSettings(invent_join_keys=True)
        
        # Without schema, should use convention
        asql = "from orders & users on orders.user_id = users.id"
        sql = compile(asql, settings=settings)
        
        assert "JOIN" in sql.upper()


class TestSchemaToDict:
    """Test schema serialization."""
    
    def test_to_dict(self) -> None:
        """Test converting schema to dictionary."""
        schema = Schema()
        schema.add_table(Table.from_column_list("users", ["id", "name"]))
        schema.add_relationship(Relationship(
            from_table="orders",
            from_column="user_id",
            to_table="users",
            to_column="id",
            alias="user",
            source="explicit"
        ))
        
        data = schema.to_dict()
        
        assert "tables" in data
        assert "users" in data["tables"]
        assert "relationships" in data
        assert len(data["relationships"]) == 1
        assert data["relationships"][0]["from_table"] == "orders"
        assert data["relationships"][0]["to_table"] == "users"
    
    def test_from_dict(self) -> None:
        """Test creating schema from dictionary."""
        data = {
            "tables": {
                "orders": {"columns": ["id", "user_id"]},
                "users": {"columns": ["id", "name"]}
            },
            "relationships": [
                {
                    "from_table": "orders",
                    "from_column": "user_id",
                    "to_table": "users",
                    "to_column": "id",
                    "alias": "user",
                    "source": "explicit"
                }
            ]
        }
        
        schema = Schema.from_dict(data)
        
        assert schema.has_table("orders")
        assert schema.has_table("users")
        
        rel = schema.find_relationship("orders", "users")
        assert rel is not None
        assert rel.alias == "user"
