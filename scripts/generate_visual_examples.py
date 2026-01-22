#!/usr/bin/env python3
"""Generate visual ASQL examples from ASQL source queries.

This is the SOURCE OF TRUTH for visual ASQL examples. Edit the EXAMPLES list
below and run this script to regenerate playground/examples/visual_asql.json.

The frontend is a DUMB RENDERER - it just displays what this script produces.
All column tracking, transform parsing, etc. happens here via the transpiler.

Usage:
    just gen-visual-examples
"""

import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import asql
from asql.schema import Schema
from playground.schema import PLAYGROUND_SCHEMA

# Convert PLAYGROUND_SCHEMA (SQLGlot format) to ASQL Schema format
# PLAYGROUND_SCHEMA is: {"table": {"col": "type", ...}}
# Schema.from_dict expects: {"tables": {"table": {"columns": {"col": "type"}}}}
SCHEMA = Schema.from_dict({
    "tables": {
        table_name: {"columns": columns}
        for table_name, columns in PLAYGROUND_SCHEMA.items()
    }
})

# =============================================================================
# VISUAL ASQL EXAMPLES - Edit these to update the playground examples
# =============================================================================

EXAMPLES = [
    {
        "title": "Simple Filter",
        "desc": "Filter users by status",
        "query": """
            from users
            where status = 'active'
        """,
    },
    {
        "title": "Select Columns",
        "desc": "Pick specific columns from a table",
        "query": """
            from users
            select name, email, country
        """,
    },
    {
        "title": "Group and Count",
        "desc": "Count users by country",
        "query": """
            from users
            group by country (count(*) as total)
        """,
    },
    {
        "title": "Sort and Limit",
        "desc": "Get top 10 users alphabetically",
        "query": """
            from users
            select name, email
            order by name
            limit 10
        """,
    },
    {
        "title": "Sales by Region",
        "desc": "Aggregate sales metrics per region",
        "query": """
            from sales
            group by region (
                sum(amount) as total_sales,
                count(*) as orders,
                avg(amount) as avg_order
            )
            order by total_sales desc
        """,
    },
    {
        "title": "Filter and Aggregate",
        "desc": "Filter completed orders, then sum by customer",
        "query": """
            from orders
            where status = 'completed'
            group by customer_id (
                sum(total) as lifetime_value,
                count(*) as order_count
            )
            order by lifetime_value desc
            limit 20
        """,
    },
    {
        "title": "Customer Orders Report",
        "desc": "Join customers with orders, aggregate and filter high-value customers",
        "query": """
            from customers
            left join orders on customers.id = orders.customer_id
            where orders.created_at >= '2024-01-01'
            group by customers.id, customers.name, customers.email (
                count(*) as order_count,
                sum(orders.total) as total_spent,
                avg(orders.total) as avg_order,
                max(orders.created_at) as last_order
            )
            where total_spent > 1000
            order by total_spent desc
            limit 50
        """,
    },
    {
        "title": "Complete Analytics Dashboard",
        "desc": "Showcases all visual editor features: joins, filters, functions, aggregates, grouping, sorting",
        "query": """
            from orders
            join customers on orders.customer_id = customers.id
            left join products on orders.product_id = products.id
            where orders.status = 'completed' and orders.total > 50
            extend 
                year(orders.created_at) as order_year,
                month(orders.created_at) as order_month,
                upper(customers.country) as country_code
            group by order_year, order_month, country_code, products.category (
                count(*) as total_orders,
                sum(orders.total) as revenue,
                avg(orders.total) as avg_order_value,
                min(orders.total) as smallest_order,
                max(orders.total) as largest_order,
                count(distinct customers.id) as unique_customers
            )
            where total_orders >= 5 and revenue > 1000
            order by order_year desc, order_month desc, revenue desc
            limit 100
        """,
    },
    {
        "title": "Monthly Revenue by Channel",
        "desc": "Time-series aggregation with multiple dimensions and metrics",
        "query": """
            from orders
            join customers on orders.customer_id = customers.id
            where orders.status in ('completed', 'shipped')
            group by month(orders.created_at), customers.country (
                sum(orders.total) as revenue,
                count(*) as order_count,
                count(distinct orders.customer_id) as unique_customers,
                avg(orders.total) as avg_order_value
            )
            where order_count >= 10
            order by month(orders.created_at), revenue desc
        """,
    },
    {
        "title": "Product Category Analysis",
        "desc": "Multi-join analysis of products and sales",
        "query": """
            from products
            left join sales on products.id = sales.product_id
            where sales.status = 'completed' or sales.id is null
            group by products.category, products.name, products.price (
                count(sales.id) as times_sold,
                sum(sales.quantity) as total_units,
                sum(sales.amount) as revenue,
                avg(sales.quantity) as avg_qty_per_sale
            )
            order by products.category, revenue desc
        """,
    },
    {
        "title": "Lead Conversion Funnel",
        "desc": "Analyze leads by source and status",
        "query": """
            from leads
            group by source, status (
                count(*) as lead_count,
                avg(score) as avg_score
            )
            order by source, lead_count desc
        """,
    },
]


def generate_visual_json(query: str) -> list[dict]:
    """Transpile an ASQL query to visual JSON format."""
    result = asql.transpile(
        query.strip(),
        read="asql",
        write="visual_asql",
        schema=SCHEMA,
    )
    # The visual dialect returns JSON as a string
    if result and result[0]:
        return json.loads(result[0])
    return []


def main() -> None:
    """Generate visual_asql.json from ASQL examples."""
    output_path = Path(__file__).parent.parent / "playground" / "examples" / "visual_asql.json"
    
    print("Generating visual ASQL examples...")
    print(f"Schema tables: {list(SCHEMA.tables.keys())}")
    
    visual_examples = []
    
    for i, example in enumerate(EXAMPLES):
        title = example["title"]
        print(f"  [{i+1}/{len(EXAMPLES)}] {title}...")
        
        try:
            visual_json = generate_visual_json(example["query"])
            
            visual_examples.append({
                "title": title,
                "desc": example["desc"],
                "dialect": "visual-asql",
                "query": visual_json,
            })
            
        except Exception as e:
            print(f"    ERROR: {e}")
            # Include failed example with error message
            visual_examples.append({
                "title": title,
                "desc": example["desc"],
                "dialect": "visual-asql",
                "query": [],
                "error": str(e),
            })
    
    print(f"\nWriting {output_path}")
    with open(output_path, "w") as f:
        json.dump(visual_examples, f, indent=2)
    
    print(f"Done! Generated {len(visual_examples)} examples.")


if __name__ == "__main__":
    main()
