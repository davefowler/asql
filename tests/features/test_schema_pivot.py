"""Tests for schema-aware pivot behavior in ASQL.

When a schema provides distinct_values for a column,
dynamic pivot can use those values for non-native dialect fallback.
"""

from tests.validator import ASQLValidator
from asql.config import CompileSettings
from asql.schema import Schema


class TestSchemaAwarePivot(ASQLValidator):
    """Test schema-aware dynamic pivot."""
    
    def test_dynamic_pivot_with_schema_postgres(self) -> None:
        """PostgreSQL dynamic pivot works when schema provides distinct_values."""
        schema = Schema.from_dict({
            "tables": {
                "sales": {
                    "columns": ["id", "amount", "category"],
                    "category": {"distinct_values": ["A", "B", "C"]}
                }
            }
        })
        settings = CompileSettings(schema=schema, auto_spine=False)
        
        result = self.validate_contains(
            "from sales pivot sum(amount) by category",
            "CASE WHEN",
            dialect="postgres",
            settings=settings
        )
        
        # Should use CASE/WHEN fallback with schema values
        assert "CASE WHEN" in result.upper()
        assert "category" in result.lower()
        # Values from schema should be used
        assert "= 'A'" in result or "= 'a'" in result.lower()
        assert "= 'B'" in result or "= 'b'" in result.lower()
        assert "= 'C'" in result or "= 'c'" in result.lower()
    
    def test_dynamic_pivot_with_schema_mysql(self) -> None:
        """MySQL dynamic pivot works when schema provides distinct_values."""
        schema = Schema.from_dict({
            "tables": {
                "sales": {
                    "columns": ["id", "amount", "category"],
                    "category": {"distinct_values": ["X", "Y"]}
                }
            }
        })
        settings = CompileSettings(schema=schema, auto_spine=False)
        
        result = self.validate_contains(
            "from sales pivot sum(amount) by category",
            "CASE WHEN",
            dialect="mysql",
            settings=settings
        )
        
        assert "CASE WHEN" in result.upper()
        assert "= 'X'" in result or "= 'x'" in result.lower()
        assert "= 'Y'" in result or "= 'y'" in result.lower()
    
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
