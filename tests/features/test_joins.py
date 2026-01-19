"""Tests for JOIN syntax in ASQL.

Join operators:
- & → INNER JOIN
- &? → LEFT JOIN
- ?& → RIGHT JOIN
- ?&? → FULL OUTER JOIN
- * → CROSS JOIN

Also supports traditional JOIN keywords.
"""

from tests.validator import ASQLValidator


class TestJoinOperators(ASQLValidator):
    """Test new ASQL join operator syntax."""
    
    def test_inner_join_operator(self) -> None:
        """& operator for INNER JOIN."""
        # JOIN may generate table-qualified SELECT (users.*, orders.*)
        for dialect in ["duckdb", "postgres", "mysql"]:
            self.validate_contains(
                "from users & orders on users.id = orders.user_id",
                "JOIN", "users", "orders", "ON", "users.id", "orders.user_id",
                dialect=dialect
            )
    
    def test_left_join_operator(self) -> None:
        """&? operator for LEFT JOIN."""
        self.validate_contains(
            "from users &? orders on users.id = orders.user_id",
            "LEFT", "JOIN", "users", "orders", "ON"
        )
    
    def test_right_join_operator(self) -> None:
        """?& operator for RIGHT JOIN."""
        self.validate_contains(
            "from users ?& orders on users.id = orders.user_id",
            "RIGHT", "JOIN"
        )
    
    def test_full_outer_join_operator(self) -> None:
        """?&? operator for FULL OUTER JOIN."""
        self.validate_contains(
            "from users ?&? orders on users.id = orders.user_id",
            "FULL"
        )
    
    def test_cross_join_operator(self) -> None:
        """* operator for CROSS JOIN."""
        self.validate_contains(
            "from users * roles",
            "CROSS JOIN", "users", "roles"
        )


class TestJoinWithAlias(ASQLValidator):
    """Test joins with table aliases."""
    
    def test_left_join_with_alias(self) -> None:
        """LEFT JOIN with AS alias."""
        self.validate_contains(
            "from accounts &? users as owner on accounts.owner_id = owner.id",
            "LEFT", "JOIN", "users", "AS", "owner"
        )
    
    def test_self_join_with_aliases(self) -> None:
        """Self-join with different aliases."""
        self.validate_contains(
            "from employees as e1 &? employees as e2 on e1.manager_id = e2.id",
            "LEFT", "JOIN", "employees"
        )


class TestChainedJoins(ASQLValidator):
    """Test multiple joins in a single query."""
    
    def test_chained_inner_joins(self) -> None:
        """Multiple INNER JOINs."""
        self.validate_contains(
            "from orders & customers on orders.customer_id = customers.id & order_items on orders.id = order_items.order_id",
            "JOIN", "customers", "order_items"
        )
    
    def test_mixed_join_types(self) -> None:
        """Mix of INNER and LEFT joins."""
        self.validate_contains(
            "from orders & customers on orders.customer_id = customers.id &? shipping on orders.id = shipping.order_id",
            "JOIN", "LEFT", "JOIN"
        )


class TestJoinWithClauses(ASQLValidator):
    """Test joins combined with other clauses."""
    
    def test_join_with_where(self) -> None:
        """JOIN with WHERE clause."""
        self.validate_contains(
            'from users &? orders on users.id = orders.user_id where orders.status = "active"',
            "LEFT", "JOIN", "WHERE", "status"
        )
    
    def test_join_with_group_by(self) -> None:
        """JOIN with GROUP BY."""
        self.validate_contains(
            "from users &? orders on users.id = orders.user_id group by users.country (sum(orders.amount) as total)",
            "LEFT", "JOIN", "GROUP BY", "SUM"
        )


class TestFKColumnShorthand(ASQLValidator):
    """Test FK column shorthand syntax.
    
    Note: Without schema, FK shorthand just preserves the column reference.
    Full expansion (e.g., owner_id → accounts.owner_id = users.id) requires schema.
    See TestSchemaAwareFKShorthand for schema-aware tests.
    """
    
    def test_explicit_fk_column_without_schema(self) -> None:
        """FK column shorthand without schema just keeps the column reference."""
        # Without schema, we can't expand the FK shorthand
        self.validate_contains(
            "from accounts & users on owner_id",
            "ON", "owner_id"
        )
    
    def test_fk_shorthand_with_alias(self) -> None:
        """FK shorthand with table alias (without schema)."""
        self.validate_contains(
            "from accounts &? users as u on owner_id",
            "ON", "owner_id"
        )


class TestTraditionalJoinSyntax(ASQLValidator):
    """Test backward compatibility with traditional JOIN keywords."""
    
    def test_traditional_join(self) -> None:
        """Traditional JOIN keyword."""
        self.validate_contains(
            "from users join orders on users.id = orders.user_id",
            "JOIN", "users", "orders"
        )
    
    def test_traditional_left_join(self) -> None:
        """Traditional LEFT JOIN keyword."""
        self.validate_contains(
            "from users left join orders on users.id = orders.user_id",
            "LEFT", "JOIN"
        )


class TestSchemaAwareFKShorthand(ASQLValidator):
    """Test schema-aware FK column expansion in JOIN conditions."""
    
    def test_fk_uses_schema_pk_not_id(self) -> None:
        """FK shorthand uses actual primary key from schema, not just 'id'."""
        from tests.fixtures import transpile
        from asql.schema import Schema, Table, Column
        from asql.config import CompileSettings
        
        # Create schema where users has user_id as PK (not 'id')
        schema = Schema()
        users = Table(name="users")
        users.add_column(Column(name="user_id", primary_key=True))
        users.add_column(Column(name="name"))
        schema.add_table(users)
        
        orders = Table(name="orders")
        orders.add_column(Column(name="id"))
        orders.add_column(Column(name="user_id"))  # FK to users
        schema.add_table(orders)
        
        settings = CompileSettings(schema=schema)
        sql = transpile("from orders & users on user_id", settings=settings)
        
        # Should use user_id (the actual PK) not assume 'id'
        assert "users.user_id" in sql.lower(), f"Expected users.user_id in: {sql}"
        assert "orders.user_id" in sql.lower(), f"Expected orders.user_id in: {sql}"
    
    def test_fk_detects_column_on_right_table(self) -> None:
        """Schema helps detect when FK is on the right table, not left."""
        from tests.fixtures import transpile
        from asql.schema import Schema, Table, Column
        from asql.config import CompileSettings
        
        schema = Schema()
        users = Table(name="users")
        users.add_column(Column(name="id", primary_key=True))
        users.add_column(Column(name="name"))
        schema.add_table(users)
        
        customers = Table(name="customers")
        customers.add_column(Column(name="id", primary_key=True))
        customers.add_column(Column(name="user_id"))  # FK to users - on the RIGHT table
        schema.add_table(customers)
        
        settings = CompileSettings(schema=schema)
        sql = transpile("from users & customers on user_id", settings=settings)
        
        # Schema should detect that user_id is on customers (right), not users (left)
        assert "customers.user_id" in sql.lower(), f"Expected customers.user_id in: {sql}"
        assert "users.id" in sql.lower(), f"Expected users.id in: {sql}"
    
    def test_fk_without_schema_preserves_column(self) -> None:
        """Without schema, FK shorthand preserves the column reference."""
        from tests.fixtures import transpile
        from asql.config import CompileSettings
        
        settings = CompileSettings()  # No schema
        sql = transpile("from orders & users on user_id", settings=settings)
        
        # Without schema, FK shorthand can't be expanded - just preserves the column
        assert "user_id" in sql.lower(), f"Expected user_id in: {sql}"
        # Note: The output keeps the ON condition as-is without expansion
    
    def test_fk_schema_with_custom_pk_name(self) -> None:
        """FK shorthand with non-standard primary key name."""
        from tests.fixtures import transpile
        from asql.schema import Schema, Table, Column
        from asql.config import CompileSettings
        
        schema = Schema()
        products = Table(name="products")
        products.add_column(Column(name="pk", primary_key=True))
        products.add_column(Column(name="name"))
        schema.add_table(products)
        
        order_items = Table(name="order_items")
        order_items.add_column(Column(name="id", primary_key=True))
        order_items.add_column(Column(name="product_pk"))  # FK uses pk naming
        schema.add_table(order_items)
        
        settings = CompileSettings(schema=schema)
        sql = transpile("from order_items & products on product_pk", settings=settings)
        
        # Should use 'pk' as the primary key, not 'id'
        assert "products.pk" in sql.lower(), f"Expected products.pk in: {sql}"
        assert "order_items.product_pk" in sql.lower(), f"Expected order_items.product_pk in: {sql}"


class TestAutoJoin(ASQLValidator):
    """Test automatic join condition inference."""
    
    def test_auto_join_with_infer_join_keys(self) -> None:
        """Auto-infer join requires schema to know column names.
        
        Without schema, infer_join_keys alone cannot infer conditions because
        we don't know what columns exist on each table.
        """
        from tests.fixtures import transpile
        from asql.config import CompileSettings
        
        settings = CompileSettings(infer_join_keys=True)
        sql = transpile("from orders & users", settings=settings)
        
        # Without schema, no inference is possible - both tables referenced
        assert "orders" in sql.lower()
        assert "users" in sql.lower()
    
    def test_auto_join_with_schema_relationship(self) -> None:
        """Auto-infer join condition from schema relationship."""
        from tests.fixtures import transpile
        from asql.config import CompileSettings
        from asql.schema import Schema, Table, Relationship
        
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
        
        settings = CompileSettings(schema=schema)
        sql = transpile("from orders & customers", settings=settings)
        
        # Should use explicit relationship
        assert "JOIN" in sql.upper()
        assert "orders.customer_id" in sql.lower()
        assert "customers.id" in sql.lower()
    
    def test_auto_join_with_inferred_relationship(self) -> None:
        """Auto-infer join from inferred schema relationship."""
        from tests.fixtures import transpile
        from asql.config import CompileSettings
        from asql.schema import Schema, Table
        
        schema = Schema()
        schema.add_table(Table.from_column_list("orders", ["id", "user_id"]))
        schema.add_table(Table.from_column_list("users", ["id", "name"]))
        schema.infer_relationships()
        
        settings = CompileSettings(schema=schema)
        sql = transpile("from orders & users", settings=settings)
        
        # Should use inferred relationship
        assert "JOIN" in sql.upper()
        assert "orders.user_id" in sql.lower()
        assert "users.id" in sql.lower()
    
    def test_auto_join_without_setting_or_schema(self) -> None:
        """Without infer_join_keys or schema, join has no ON condition."""
        from tests.fixtures import transpile
        
        # No settings - should produce join without condition (becomes comma join)
        sql = transpile("from orders & users")
        
        # Should have users table referenced
        assert "users" in sql.lower()
        # The join should exist but without an ON condition (no auto-inference without settings)
        assert " on " not in sql.lower(), f"Join should not have ON clause without settings: {sql}"
    
    def test_cross_join_no_auto_condition(self) -> None:
        """CROSS JOIN should not get auto-inferred condition."""
        from tests.fixtures import transpile
        from asql.config import CompileSettings
        
        settings = CompileSettings(infer_join_keys=True)
        sql = transpile("from orders * users", settings=settings)
        
        # Cross join shouldn't have ON condition
        assert "CROSS JOIN" in sql.upper()
        # Should NOT have an ON clause inferred - check both conditions
        assert " on " not in sql.lower(), f"CROSS JOIN should not have ON clause: {sql}"
    
    def test_chained_auto_joins(self) -> None:
        """Chained joins without schema just reference all tables.
        
        Without schema, we can't infer join conditions.
        """
        from tests.fixtures import transpile
        from asql.config import CompileSettings
        
        settings = CompileSettings(infer_join_keys=True)
        sql = transpile("from orders & users & products", settings=settings)
        
        # All tables should be referenced
        assert "orders" in sql.lower()
        assert "users" in sql.lower()
        assert "products" in sql.lower()
