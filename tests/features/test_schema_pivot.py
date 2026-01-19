"""Tests for schema-aware features in ASQL.

These tests verify that schema metadata (like distinct_values) is properly loaded.
Note: The PIVOT fallback transform was removed - SQLGlot handles PIVOT natively.
"""

from tests.validator import ASQLValidator
from asql.schema import Schema


class TestSchemaDistinctValues(ASQLValidator):
    """Test that schema properly stores distinct_values metadata."""
    
    def test_schema_distinct_values_in_column_class(self) -> None:
        """Column class properly stores distinct_values."""
        from asql.schema import Column
        
        col = Column(name="status", distinct_values=["active", "inactive", "pending"])
        assert col.distinct_values == ["active", "inactive", "pending"]
        assert col.name == "status"
    
    def test_schema_from_dict_with_distinct_values(self) -> None:
        """Schema.from_dict properly loads distinct_values."""
        schema = Schema.from_dict({
            "tables": {
                "orders": {
                    "columns": ["id", "status", "amount"],
                    "status": {"distinct_values": ["pending", "shipped", "delivered"]}
                }
            }
        })
        
        table = schema.get_table("orders")
        assert table is not None
        
        values = table.get_distinct_values("status")
        assert values == ["pending", "shipped", "delivered"]
