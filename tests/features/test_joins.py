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
    """Test FK column shorthand syntax."""
    
    def test_explicit_fk_column(self) -> None:
        """FK column shorthand: on fk_column → on table.fk_column = other.id."""
        self.validate_contains(
            "from accounts & users on owner_id",
            "accounts.owner_id", "users.id"
        )
    
    def test_fk_shorthand_with_alias(self) -> None:
        """FK shorthand with table alias."""
        self.validate_contains(
            "from accounts &? users as u on owner_id",
            "accounts.owner_id", "u.id"
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
