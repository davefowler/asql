"""Test ASQL with example datasets and real-world scenarios."""

import pytest
from asql import compile


# Example dataset descriptions (for documentation/testing)
EXAMPLE_DATASETS = {
    "users": {
        "description": "User accounts table",
        "columns": ["id", "name", "email", "status", "age", "country", "created_at", "updated_at"],
        "sample_queries": [
            "from users",
            'from users where status == "active"',
            "from users where age >= 18",
            "from users group by country ( # as total_users )",
        ]
    },
    "sales": {
        "description": "Sales transactions",
        "columns": ["id", "user_id", "amount", "region", "month", "year", "status", "product_category", "created_at"],
        "sample_queries": [
            "from sales",
            'from sales where status == "completed"',
            "from sales group by region ( sum(amount) as revenue )",
            "from sales group by region, month ( sum(amount) as revenue, # as orders )",
        ]
    },
    "orders": {
        "description": "Customer orders",
        "columns": ["id", "user_id", "total", "status", "created_at"],
        "sample_queries": [
            "from orders",
            'from orders where status == "pending"',
            "from orders group by status ( sum(total) as total_revenue )",
        ]
    },
}


class TestExampleDatasets:
    """Test queries against example datasets."""
    
    def test_users_dataset_queries(self) -> None:
        """Test common queries on users dataset."""
        queries = EXAMPLE_DATASETS["users"]["sample_queries"]
        for asql in queries:
            sql = compile(asql)
            assert sql is not None
            assert "users" in sql.lower()
            assert "SELECT" in sql.upper()
    
    def test_sales_dataset_queries(self) -> None:
        """Test common queries on sales dataset."""
        queries = EXAMPLE_DATASETS["sales"]["sample_queries"]
        for asql in queries:
            sql = compile(asql)
            assert sql is not None
            assert "sales" in sql.lower()
            assert "SELECT" in sql.upper()
    
    def test_orders_dataset_queries(self) -> None:
        """Test common queries on orders dataset."""
        queries = EXAMPLE_DATASETS["orders"]["sample_queries"]
        for asql in queries:
            sql = compile(asql)
            assert sql is not None
            assert "orders" in sql.lower()
            assert "SELECT" in sql.upper()


class TestRealWorldScenarios:
    """Test real-world query scenarios."""
    
    def test_user_segmentation(self) -> None:
        """Test user segmentation query."""
        asql = """
from users
where status == "active" and age >= 18
group by country ( # as total_users, avg(age) as avg_age )
order by -total_users
take 20
"""
        sql = compile(asql)
        assert "SELECT" in sql.upper()
        assert "WHERE" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()
    
    def test_sales_analytics(self) -> None:
        """Test sales analytics query."""
        asql = """
from sales
where status == "completed" and amount > 100
group by region, month ( sum(amount) as revenue, # as orders )
order by -revenue
take 10
"""
        sql = compile(asql)
        assert "SELECT" in sql.upper()
        assert "WHERE" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "SUM" in sql.upper()
        assert "COUNT" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()
    
    def test_user_filtering(self) -> None:
        """Test complex user filtering."""
        asql = """
from users
where status in ("active", "pending", "verified")
    and age >= 18
    and age <= 65
    and email is not null
    and country not in ("banned_country1", "banned_country2")
"""
        sql = compile(asql)
        assert "WHERE" in sql.upper()
        assert "IN" in sql.upper()
        assert "NOT" in sql.upper()
        assert "AND" in sql.upper()
    
    def test_time_based_analysis(self) -> None:
        """Test time-based analysis query."""
        # Note: GROUP BY with function calls requires aggregation
        # Use single-line format (multi-line not fully supported yet)
        asql = "from users group by month(created_at) ( # as signups ) order by -signups"
        sql = compile(asql)
        assert "GROUP BY" in sql.upper()
        assert "MONTH" in sql.upper() or "month" in sql.lower()
        assert "ORDER BY" in sql.upper()
    
    def test_top_performers(self) -> None:
        """Test top performers query."""
        asql = """
from sales
where status == "completed"
group by user_id ( sum(amount) as total_spent )
order by -total_spent
take 100
"""
        sql = compile(asql)
        assert "GROUP BY" in sql.upper()
        assert "SUM" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "DESC" in sql.upper()
        assert "LIMIT" in sql.upper()
        assert "100" in sql
    
    def test_status_distribution(self) -> None:
        """Test status distribution query."""
        asql = """
from users
group by status ( # as count )
order by -count
"""
        sql = compile(asql)
        assert "GROUP BY" in sql.upper()
        assert "COUNT" in sql.upper()
        assert "ORDER BY" in sql.upper()
    
    def test_region_comparison(self) -> None:
        """Test region comparison query."""
        asql = """
from sales
where year == 2024
group by region (
    sum(amount) as revenue,
    avg(amount) as avg_order,
    # as order_count
)
order by -revenue
"""
        sql = compile(asql)
        assert "WHERE" in sql.upper()
        assert "GROUP BY" in sql.upper()
        assert "SUM" in sql.upper()
        assert "AVG" in sql.upper()
        assert "COUNT" in sql.upper()
        assert "ORDER BY" in sql.upper()
