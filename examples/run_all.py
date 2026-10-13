"""Run all ASQL examples."""

from examples import aggregations, basic_queries, complex_queries, sorting_and_limiting


def run_all_examples():
    """Run all example modules."""
    print("=" * 80)
    print("ASQL Examples Library")
    print("=" * 80)

    modules = [
        ("Basic Queries", basic_queries),
        ("Aggregations", aggregations),
        ("Sorting and Limiting", sorting_and_limiting),
        ("Complex Queries", complex_queries),
    ]

    for title, module in modules:
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print("=" * 80)

        # Run all functions in the module
        for name in dir(module):
            if name.startswith("example_") and callable(getattr(module, name)):
                func = getattr(module, name)
                try:
                    func()
                    print()
                except Exception as e:  # noqa: BLE001
                    print(f"Error in {name}: {e}")
                    print()


if __name__ == "__main__":
    run_all_examples()
