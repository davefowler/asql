"""Playground schema for ASQL examples.

This schema provides table and column definitions for all playground examples.
It's used by:
- The playground frontend for autocomplete and type information
- The visual editor for column tracking through pipeline stages
- Tests to verify examples compile correctly with schema

The schema is intentionally comprehensive - it includes all columns used in examples
plus realistic additional columns that such tables would typically have.
"""

from typing import Any

# SQLGlot MappingSchema format: {table: {column: type}}
# Types are SQLGlot type strings: VARCHAR, INT, BIGINT, FLOAT, DOUBLE, BOOLEAN, 
# DATE, TIMESTAMP, ARRAY<T>, etc.

PLAYGROUND_SCHEMA: dict[str, dict[str, str]] = {
    # ==========================================================================
    # CORE USER/CUSTOMER TABLES
    # ==========================================================================
    
    "users": {
        # Primary key
        "id": "BIGINT",
        "user_id": "BIGINT",  # Alias used in some examples
        
        # Profile information
        "name": "VARCHAR",
        "email": "VARCHAR",
        "phone": "VARCHAR",
        "domain": "VARCHAR",  # User's website domain
        
        # Geographic
        "country": "VARCHAR",
        "region": "VARCHAR",
        "city": "VARCHAR",
        "timezone": "VARCHAR",
        
        # Account status
        "status": "VARCHAR",  # active, inactive, pending, banned
        "is_active": "BOOLEAN",
        
        # Demographics
        "age": "INT",
        "gender": "VARCHAR",
        
        # Acquisition
        "channel": "VARCHAR",  # signup source: website, referral, ad, etc.
        "source": "VARCHAR",
        "campaign": "VARCHAR",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
        "signup_date": "DATE",
        "last_login": "TIMESTAMP",
        "deleted_at": "TIMESTAMP",
        
        # Sensitive (for testing except/column ops)
        "password_hash": "VARCHAR",
        "internal_notes": "VARCHAR",
    },
    
    "customers": {
        # Primary key
        "id": "BIGINT",
        "customer_id": "BIGINT",
        
        # Profile
        "name": "VARCHAR",
        "email": "VARCHAR",
        "phone": "VARCHAR",
        "company": "VARCHAR",
        
        # Geographic
        "country": "VARCHAR",
        "region": "VARCHAR",
        "city": "VARCHAR",
        "address": "VARCHAR",
        
        # Status
        "status": "VARCHAR",
        "is_active": "BOOLEAN",
        "tier": "VARCHAR",  # bronze, silver, gold, platinum
        
        # Business metrics
        "lifetime_value": "DOUBLE",
        "total_orders": "INT",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
        "signup_date": "DATE",
        "first_order_date": "DATE",
        "last_order_date": "DATE",
        
        # Internal
        "internal_id": "VARCHAR",
    },
    
    # ==========================================================================
    # ORDER/TRANSACTION TABLES
    # ==========================================================================
    
    "orders": {
        # Primary key
        "id": "BIGINT",
        "order_id": "BIGINT",
        
        # Foreign keys
        "user_id": "BIGINT",
        "customer_id": "BIGINT",
        "product_id": "BIGINT",
        
        # Order details
        "status": "VARCHAR",  # pending, shipped, delivered, completed, cancelled
        "amount": "DOUBLE",
        "total": "DOUBLE",
        "subtotal": "DOUBLE",
        "tax": "DOUBLE",
        "discount": "DOUBLE",
        "shipping": "DOUBLE",
        
        # Geographic
        "region": "VARCHAR",
        "country": "VARCHAR",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
        "order_date": "DATE",
        "shipped_date": "DATE",
        "delivered_date": "DATE",
        "estimated_delivery": "DATE",
        
        # Payment
        "payment_method": "VARCHAR",
        "payment_status": "VARCHAR",
    },
    
    "order_items": {
        # Primary key
        "id": "BIGINT",
        "item_id": "BIGINT",
        
        # Foreign keys
        "order_id": "BIGINT",
        "product_id": "BIGINT",
        
        # Item details
        "quantity": "INT",
        "price": "DOUBLE",
        "unit_price": "DOUBLE",
        "total": "DOUBLE",
        "discount": "DOUBLE",
        
        # Product info (denormalized)
        "category": "VARCHAR",
        "sku": "VARCHAR",
        
        # Timestamps
        "created_at": "TIMESTAMP",
    },
    
    "transactions": {
        # Primary key
        "id": "BIGINT",
        "transaction_id": "BIGINT",
        
        # Foreign keys
        "user_id": "BIGINT",
        "order_id": "BIGINT",
        "account_id": "BIGINT",
        
        # Transaction details
        "amount": "DOUBLE",
        "currency": "VARCHAR",
        "type": "VARCHAR",  # credit, debit, refund
        "status": "VARCHAR",  # pending, completed, failed
        
        # Geographic
        "region": "VARCHAR",
        "country": "VARCHAR",
        
        # Timestamps
        "transaction_date": "DATE",
        "created_at": "TIMESTAMP",
        "processed_at": "TIMESTAMP",
        
        # Payment details
        "payment_method": "VARCHAR",
        "reference": "VARCHAR",
    },
    
    # ==========================================================================
    # PRODUCT TABLES
    # ==========================================================================
    
    "products": {
        # Primary key
        "id": "BIGINT",
        "product_id": "BIGINT",
        
        # Product info
        "name": "VARCHAR",
        "description": "VARCHAR",
        "sku": "VARCHAR",
        
        # Categorization
        "category": "VARCHAR",
        "subcategory": "VARCHAR",
        "brand": "VARCHAR",
        
        # Pricing
        "price": "DOUBLE",
        "cost": "DOUBLE",
        "sale_price": "DOUBLE",
        "msrp": "DOUBLE",
        
        # Inventory
        "stock_quantity": "INT",
        "is_available": "BOOLEAN",
        
        # Status
        "status": "VARCHAR",
        "is_active": "BOOLEAN",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
    },
    
    # ==========================================================================
    # SALES/REVENUE TABLES
    # ==========================================================================
    
    "sales": {
        # Primary key
        "id": "BIGINT",
        "sale_id": "BIGINT",
        
        # Foreign keys
        "product_id": "BIGINT",
        "customer_id": "BIGINT",
        "order_id": "BIGINT",
        
        # Sale details
        "amount": "DOUBLE",
        "quantity": "INT",
        "price": "DOUBLE",
        "revenue": "DOUBLE",
        "profit": "DOUBLE",
        
        # Status
        "status": "VARCHAR",  # completed, pending, refunded
        
        # Categorization
        "category": "VARCHAR",
        "channel": "VARCHAR",
        
        # Geographic
        "region": "VARCHAR",
        "country": "VARCHAR",
        
        # Timestamps
        "sale_date": "DATE",
        "created_at": "TIMESTAMP",
    },
    
    # ==========================================================================
    # CRM/LEADS TABLES
    # ==========================================================================
    
    "leads": {
        # Primary key
        "id": "BIGINT",
        "lead_id": "BIGINT",
        
        # Lead info
        "name": "VARCHAR",
        "email": "VARCHAR",
        "phone": "VARCHAR",
        "company": "VARCHAR",
        
        # Status
        "status": "VARCHAR",  # new, contacted, qualified, converted, lost
        "score": "INT",
        
        # Acquisition
        "source": "VARCHAR",  # website, referral, ad, event
        "campaign": "VARCHAR",
        "channel": "VARCHAR",
        
        # Assignment
        "owner_id": "BIGINT",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
        "converted_at": "TIMESTAMP",
    },
    
    "opportunities": {
        # Primary key
        "id": "BIGINT",
        "opportunity_id": "BIGINT",
        
        # Foreign keys
        "lead_id": "BIGINT",
        "account_id": "BIGINT",
        "owner_id": "BIGINT",
        
        # Opportunity details
        "name": "VARCHAR",
        "amount": "DOUBLE",
        "probability": "DOUBLE",
        "stage": "VARCHAR",  # prospecting, qualification, proposal, closed_won, closed_lost
        "status": "VARCHAR",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
        "close_date": "DATE",
    },
    
    "deals": {
        # Primary key
        "id": "BIGINT",
        "deal_id": "BIGINT",
        
        # Foreign keys
        "opportunity_id": "BIGINT",
        "customer_id": "BIGINT",
        "owner_id": "BIGINT",
        
        # Deal details
        "name": "VARCHAR",
        "amount": "DOUBLE",
        "value": "DOUBLE",
        "stage": "VARCHAR",
        "status": "VARCHAR",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "closed_at": "TIMESTAMP",
    },
    
    # ==========================================================================
    # CONTENT/ENGAGEMENT TABLES
    # ==========================================================================
    
    "posts": {
        # Primary key
        "id": "BIGINT",
        "post_id": "BIGINT",
        
        # Foreign keys
        "author_id": "BIGINT",
        "user_id": "BIGINT",
        
        # Content
        "title": "VARCHAR",
        "body": "VARCHAR",
        "slug": "VARCHAR",
        
        # Metadata
        "tags": "ARRAY<VARCHAR>",
        "category": "VARCHAR",
        "status": "VARCHAR",  # draft, published, archived
        
        # Engagement
        "view_count": "INT",
        "like_count": "INT",
        "comment_count": "INT",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
        "published_at": "TIMESTAMP",
    },
    
    "events": {
        # Primary key
        "id": "BIGINT",
        "event_id": "BIGINT",
        
        # Foreign keys
        "user_id": "BIGINT",
        "session_id": "VARCHAR",
        
        # Event details
        "event_name": "VARCHAR",
        "event_type": "VARCHAR",
        "event_date": "DATE",
        
        # Context
        "page": "VARCHAR",
        "referrer": "VARCHAR",
        "device": "VARCHAR",
        "platform": "VARCHAR",
        
        # Properties (JSON stored as string for compatibility)
        "properties": "VARCHAR",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "timestamp": "TIMESTAMP",
    },
    
    # ==========================================================================
    # METRICS/ANALYTICS TABLES
    # ==========================================================================
    
    "quarterly_metrics": {
        # Primary key
        "id": "BIGINT",
        
        # Dimensions
        "metric_name": "VARCHAR",
        "category": "VARCHAR",
        "region": "VARCHAR",
        "year": "INT",
        
        # Quarterly values (for unpivot examples)
        "q1": "DOUBLE",
        "q2": "DOUBLE",
        "q3": "DOUBLE",
        "q4": "DOUBLE",
        
        # Timestamps
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
    },
}


def get_playground_schema() -> dict[str, dict[str, str]]:
    """Get the playground schema."""
    return PLAYGROUND_SCHEMA


def get_schema_for_sqlglot() -> dict[str, Any]:
    """Get schema in format suitable for sqlglot.MappingSchema."""
    return PLAYGROUND_SCHEMA


def get_table_names() -> list[str]:
    """Get list of all table names."""
    return list(PLAYGROUND_SCHEMA.keys())


def get_columns_for_table(table: str) -> dict[str, str]:
    """Get column definitions for a specific table."""
    return PLAYGROUND_SCHEMA.get(table, {})


def get_column_names_for_table(table: str) -> list[str]:
    """Get list of column names for a specific table."""
    return list(PLAYGROUND_SCHEMA.get(table, {}).keys())


# Schema metadata for UI display
SCHEMA_METADATA = {
    "users": {
        "description": "User accounts and profiles",
        "primary_key": "id",
        "category": "core",
    },
    "customers": {
        "description": "Customer records (B2B focus)",
        "primary_key": "id",
        "category": "core",
    },
    "orders": {
        "description": "Purchase orders",
        "primary_key": "id",
        "category": "transactions",
    },
    "order_items": {
        "description": "Line items within orders",
        "primary_key": "id",
        "category": "transactions",
    },
    "transactions": {
        "description": "Financial transactions",
        "primary_key": "id",
        "category": "transactions",
    },
    "products": {
        "description": "Product catalog",
        "primary_key": "id",
        "category": "catalog",
    },
    "sales": {
        "description": "Sales records",
        "primary_key": "id",
        "category": "transactions",
    },
    "leads": {
        "description": "Sales leads",
        "primary_key": "id",
        "category": "crm",
    },
    "opportunities": {
        "description": "Sales opportunities",
        "primary_key": "id",
        "category": "crm",
    },
    "deals": {
        "description": "Closed deals",
        "primary_key": "id",
        "category": "crm",
    },
    "posts": {
        "description": "Content posts",
        "primary_key": "id",
        "category": "content",
    },
    "events": {
        "description": "User activity events",
        "primary_key": "id",
        "category": "analytics",
    },
    "quarterly_metrics": {
        "description": "Quarterly business metrics",
        "primary_key": "id",
        "category": "analytics",
    },
}


def get_schema_with_metadata() -> dict[str, Any]:
    """Get schema with metadata for UI display."""
    result = {}
    for table, columns in PLAYGROUND_SCHEMA.items():
        result[table] = {
            "columns": columns,
            "metadata": SCHEMA_METADATA.get(table, {
                "description": f"{table} table",
                "primary_key": "id",
                "category": "other",
            }),
        }
    return result
