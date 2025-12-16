"""Examples demonstrating ASQL's pipeline CTE functionality."""

from asql import compile


def example_simple_pipeline() -> None:
    """Example: Simple pipeline with single step."""
    print("=" * 60)
    print("Example: Simple Pipeline")
    print("=" * 60)
    
    asql = "from users"
    sql = compile(asql, pretty=True)
    
    print("ASQL:")
    print(asql)
    print("\nGenerated SQL:")
    print(sql)
    print()


def example_pipeline_with_where() -> None:
    """Example: Pipeline with WHERE clause."""
    print("=" * 60)
    print("Example: Pipeline with WHERE")
    print("=" * 60)
    
    asql = 'from users where status == "active"'
    sql = compile(asql, pretty=True)
    
    print("ASQL:")
    print(asql)
    print("\nGenerated SQL:")
    print(sql)
    print()


def example_pipeline_with_group_by() -> None:
    """Example: Pipeline with GROUP BY creates multiple CTEs."""
    print("=" * 60)
    print("Example: Pipeline with GROUP BY (Multiple CTEs)")
    print("=" * 60)
    
    asql = 'from users where status == "active" group by country ( # as total_users )'
    sql = compile(asql, pretty=True)
    
    print("ASQL:")
    print(asql)
    print("\nGenerated SQL:")
    print(sql)
    print("Note: Each pipeline step becomes a descriptive CTE!")
    print()


def example_complete_pipeline() -> None:
    """Example: Complete pipeline with multiple transformations."""
    print("=" * 60)
    print("Example: Complete Pipeline")
    print("=" * 60)
    
    asql = """
    from users
    where status == "active"
    group by country ( # as total_users )
    order by -total_users
    take 10
    """
    sql = compile(asql, pretty=True)
    
    print("ASQL:")
    print(asql.strip())
    print("\nGenerated SQL:")
    print(sql)
    print()


def example_pipeline_with_join() -> None:
    """Example: Pipeline with JOIN creates new step."""
    print("=" * 60)
    print("Example: Pipeline with JOIN")
    print("=" * 60)
    
    asql = "from users join orders on users.id == orders.user_id"
    sql = compile(asql, pretty=True)
    
    print("ASQL:")
    print(asql)
    print("\nGenerated SQL:")
    print(sql)
    print()


def example_pipeline_with_select() -> None:
    """Example: Pipeline with explicit SELECT."""
    print("=" * 60)
    print("Example: Pipeline with SELECT")
    print("=" * 60)
    
    asql = 'from users where status == "active" select name, email'
    sql = compile(asql, pretty=True)
    
    print("ASQL:")
    print(asql)
    print("\nGenerated SQL:")
    print(sql)
    print()


if __name__ == "__main__":
    example_simple_pipeline()
    example_pipeline_with_where()
    example_pipeline_with_group_by()
    example_complete_pipeline()
    example_pipeline_with_join()
    example_pipeline_with_select()

