"""
Playwright E2E tests for the Yahoo Pipes-style visual mode in the ASQL Playground.
Tests the new 'pipes' style toggle and node-based visualization with CTEs.
"""
import re
import pytest
from playwright.sync_api import Page, expect


# Example queries with CTEs for testing
CTE_EXAMPLES = {
    "bigquery_cte": {
        "dialect": "bigquery",
        "query": """WITH active_users AS (
  SELECT user_id, country, signup_date
  FROM users
  WHERE status = 'active' AND signup_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),
user_orders AS (
  SELECT au.user_id, au.country,
    COUNT(o.order_id) AS order_count,
    SUM(o.amount) AS total_spent
  FROM active_users au
  LEFT JOIN orders o ON au.user_id = o.user_id
  GROUP BY au.user_id, au.country
)
SELECT country,
  COUNT(*) AS user_count,
  AVG(order_count) AS avg_orders,
  SUM(total_spent) AS total_revenue
FROM user_orders
GROUP BY country
ORDER BY total_revenue DESC
LIMIT 10""",
        "expected_ctes": ["active_users", "user_orders"],
    },
    "simple_cte": {
        "dialect": "postgres",
        "query": """WITH filtered AS (
  SELECT * FROM orders WHERE status = 'completed'
)
SELECT customer_id, SUM(total) as total_spent
FROM filtered
GROUP BY customer_id""",
        "expected_ctes": ["filtered"],
    },
    "multi_cte": {
        "dialect": "snowflake",
        "query": """WITH
  step1 AS (
    SELECT id, name FROM users WHERE active = true
  ),
  step2 AS (
    SELECT user_id, SUM(amount) as total FROM orders GROUP BY user_id
  ),
  step3 AS (
    SELECT s1.name, s2.total
    FROM step1 s1
    JOIN step2 s2 ON s1.id = s2.user_id
  )
SELECT * FROM step3 ORDER BY total DESC""",
        "expected_ctes": ["step1", "step2", "step3"],
    },
}


@pytest.fixture
def playground_page(page: Page, server_url: str):
    """Navigate to the playground and wait for it to load."""
    page.goto(server_url)
    # Wait for the playground to initialize
    page.wait_for_selector("#from-dialect", timeout=10000)
    return page


class TestPipesStyleToggle:
    """Tests for the pipes style toggle button functionality."""

    def test_pipes_button_exists_in_input_panel(self, playground_page: Page):
        """Verify the pipes style toggle button exists in the input panel."""
        pipes_btn = playground_page.locator("#pipes-style-btn")
        expect(pipes_btn).to_be_attached()
        expect(pipes_btn).to_have_attribute("title", "Yahoo Pipes Style")

    def test_pipes_button_exists_in_output_panel(self, playground_page: Page):
        """Verify the pipes style toggle button exists in the output panel."""
        pipes_btn = playground_page.locator("#output-pipes-style-btn")
        expect(pipes_btn).to_be_attached()
        expect(pipes_btn).to_have_attribute("title", "Yahoo Pipes Style")

    def test_toggle_to_pipes_style(self, playground_page: Page):
        """Test switching to pipes style activates the button."""
        # First need to switch to visual-asql mode to see style toggles
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(500)

        # Show the output visual toggle
        visual_toggle = playground_page.locator("#output-visual-style-toggle")
        expect(visual_toggle).to_be_visible()

        # Click on pipes style button
        pipes_btn = playground_page.locator("#output-pipes-style-btn")
        pipes_btn.click()

        # Verify it becomes active
        expect(pipes_btn).to_have_class(re.compile(r"active"))

    def test_pipes_style_persists_in_localstorage(self, playground_page: Page):
        """Test that pipes style preference is saved to localStorage."""
        # Switch to visual-asql to enable style toggles
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(500)

        # Click pipes style
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.wait_for_timeout(200)

        # Check localStorage
        style_pref = playground_page.evaluate("localStorage.getItem('asql_visual_style')")
        assert style_pref == "pipes"


class TestPipesVisualization:
    """Tests for the pipes-style node visualization."""

    def test_pipes_container_created(self, playground_page: Page):
        """Test that pipes container is created when in pipes mode."""
        # Set up: enter a simple query and switch to visual output with pipes mode
        playground_page.select_option("#from-dialect", "postgres")
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        # Enter a simple query in input
        input_editor = playground_page.locator("#input-editor .CodeMirror")
        input_editor.click()
        playground_page.keyboard.press("Control+A")
        playground_page.keyboard.type("SELECT * FROM users WHERE status = 'active'")
        playground_page.wait_for_timeout(1000)

        # Switch to pipes style
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.wait_for_timeout(500)

        # Switch to visual view in output
        playground_page.locator("#output-visual-view-btn").click()
        playground_page.wait_for_timeout(500)

        # Check for pipes container
        pipes_container = playground_page.locator(".pipes-nodes-container")
        expect(pipes_container).to_be_visible()

    def test_pipe_node_rendered(self, playground_page: Page):
        """Test that pipe nodes are rendered for queries."""
        playground_page.select_option("#from-dialect", "postgres")
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        # Enter query
        input_editor = playground_page.locator("#input-editor .CodeMirror")
        input_editor.click()
        playground_page.keyboard.press("Control+A")
        playground_page.keyboard.type("SELECT name, email FROM users WHERE active = true")
        playground_page.wait_for_timeout(1000)

        # Switch to pipes mode and visual view
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.locator("#output-visual-view-btn").click()
        playground_page.wait_for_timeout(500)

        # Check for pipe node
        pipe_node = playground_page.locator(".pipe-node")
        expect(pipe_node).to_be_visible()

        # Check for node header
        node_header = playground_page.locator(".pipe-node-header")
        expect(node_header).to_be_visible()

    def test_transform_steps_shown_in_node(self, playground_page: Page):
        """Test that transform steps are displayed within nodes."""
        playground_page.select_option("#from-dialect", "postgres")
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        # Enter query with multiple transforms
        input_editor = playground_page.locator("#input-editor .CodeMirror")
        input_editor.click()
        playground_page.keyboard.press("Control+A")
        playground_page.keyboard.type("""SELECT country, COUNT(*) as cnt
FROM users
WHERE active = true
GROUP BY country
ORDER BY cnt DESC
LIMIT 10""")
        playground_page.wait_for_timeout(1000)

        # Switch to pipes mode and visual view
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.locator("#output-visual-view-btn").click()
        playground_page.wait_for_timeout(500)

        # Check for pipe steps within the node
        pipe_steps = playground_page.locator(".pipe-step")
        expect(pipe_steps.first).to_be_visible()

        # Check for step type badges
        step_types = playground_page.locator(".pipe-step-type")
        expect(step_types.first).to_be_visible()


class TestPipesWithCTEs:
    """Tests for pipes visualization with CTE queries."""

    @pytest.mark.parametrize("example_key", ["simple_cte", "multi_cte"])
    def test_cte_nodes_created(self, playground_page: Page, example_key: str):
        """Test that each CTE is rendered as a separate node."""
        example = CTE_EXAMPLES[example_key]

        # Set up dialects
        playground_page.select_option("#from-dialect", example["dialect"])
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        # Enter CTE query
        input_editor = playground_page.locator("#input-editor .CodeMirror")
        input_editor.click()
        playground_page.keyboard.press("Control+A")
        playground_page.keyboard.type(example["query"])
        playground_page.wait_for_timeout(1500)

        # Switch to pipes mode and visual view
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.locator("#output-visual-view-btn").click()
        playground_page.wait_for_timeout(500)

        # Count nodes - should have at least one per CTE plus the final query
        nodes = playground_page.locator(".pipe-node")
        node_count = nodes.count()

        # We expect at least len(expected_ctes) nodes
        expected_min = len(example["expected_ctes"])
        assert node_count >= expected_min, f"Expected at least {expected_min} nodes, got {node_count}"

    def test_cte_node_shows_name(self, playground_page: Page):
        """Test that CTE nodes display their names."""
        example = CTE_EXAMPLES["simple_cte"]

        playground_page.select_option("#from-dialect", example["dialect"])
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        input_editor = playground_page.locator("#input-editor .CodeMirror")
        input_editor.click()
        playground_page.keyboard.press("Control+A")
        playground_page.keyboard.type(example["query"])
        playground_page.wait_for_timeout(1500)

        # Switch to pipes mode
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.locator("#output-visual-view-btn").click()
        playground_page.wait_for_timeout(500)

        # Look for the CTE name in a node title
        node_title = playground_page.locator(".pipe-node-title")
        first_title_text = node_title.first.inner_text()

        # Should contain one of the expected CTE names or the source table
        assert any(
            name in first_title_text.lower() or first_title_text.lower() in name
            for name in example["expected_ctes"] + ["orders", "filtered"]
        ), f"Expected CTE name in title, got: {first_title_text}"

    def test_cte_reference_badge_shown(self, playground_page: Page):
        """Test that nodes referencing other CTEs show a reference badge."""
        example = CTE_EXAMPLES["multi_cte"]

        playground_page.select_option("#from-dialect", example["dialect"])
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        input_editor = playground_page.locator("#input-editor .CodeMirror")
        input_editor.click()
        playground_page.keyboard.press("Control+A")
        playground_page.keyboard.type(example["query"])
        playground_page.wait_for_timeout(1500)

        # Switch to pipes mode
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.locator("#output-visual-view-btn").click()
        playground_page.wait_for_timeout(500)

        # At least one node should show a reference badge
        ref_badges = playground_page.locator(".pipe-ref-badge")
        # The step3 CTE references step1 and step2, so there should be a ref badge
        expect(ref_badges.first).to_be_visible()


class TestPipesStyleModes:
    """Tests for switching between style modes."""

    def test_switch_between_all_styles(self, playground_page: Page):
        """Test switching between text, blocky, and pipes styles."""
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        # Get all style buttons
        text_btn = playground_page.locator("#output-text-style-btn")
        blocky_btn = playground_page.locator("#output-blocky-style-btn")
        pipes_btn = playground_page.locator("#output-pipes-style-btn")

        # Test text style
        text_btn.click()
        playground_page.wait_for_timeout(200)
        expect(text_btn).to_have_class(re.compile(r"active"))
        expect(blocky_btn).not_to_have_class(re.compile(r"active"))
        expect(pipes_btn).not_to_have_class(re.compile(r"active"))

        # Test blocky style
        blocky_btn.click()
        playground_page.wait_for_timeout(200)
        expect(blocky_btn).to_have_class(re.compile(r"active"))
        expect(text_btn).not_to_have_class(re.compile(r"active"))
        expect(pipes_btn).not_to_have_class(re.compile(r"active"))

        # Test pipes style
        pipes_btn.click()
        playground_page.wait_for_timeout(200)
        expect(pipes_btn).to_have_class(re.compile(r"active"))
        expect(text_btn).not_to_have_class(re.compile(r"active"))
        expect(blocky_btn).not_to_have_class(re.compile(r"active"))

    def test_pipes_style_adds_correct_class(self, playground_page: Page):
        """Test that pipes style applies the correct CSS class."""
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        # Switch to pipes
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.wait_for_timeout(200)

        # Check container class
        container = playground_page.locator("#output-visual-editor-container")
        expect(container).to_have_class(re.compile(r"visual-style-pipes"))

    def test_style_switch_preserves_content(self, playground_page: Page):
        """Test that switching styles preserves the query content."""
        playground_page.select_option("#from-dialect", "postgres")
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        # Enter a query
        test_query = "SELECT * FROM users"
        input_editor = playground_page.locator("#input-editor .CodeMirror")
        input_editor.click()
        playground_page.keyboard.press("Control+A")
        playground_page.keyboard.type(test_query)
        playground_page.wait_for_timeout(1000)

        # Get the output JSON before switching
        playground_page.locator("#output-json-view-btn").click()
        playground_page.wait_for_timeout(200)
        output_before = playground_page.locator("#output-editor .CodeMirror").inner_text()

        # Switch to pipes and back to JSON
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.wait_for_timeout(200)
        playground_page.locator("#output-text-style-btn").click()
        playground_page.wait_for_timeout(200)

        # Output should be the same
        output_after = playground_page.locator("#output-editor .CodeMirror").inner_text()
        assert output_before == output_after


class TestPipesNodeInteraction:
    """Tests for user interaction with pipe nodes."""

    def test_node_hover_effect(self, playground_page: Page):
        """Test that hovering over a node shows visual feedback."""
        playground_page.select_option("#from-dialect", "postgres")
        playground_page.select_option("#to-dialect", "visual-asql")
        playground_page.wait_for_timeout(300)

        input_editor = playground_page.locator("#input-editor .CodeMirror")
        input_editor.click()
        playground_page.keyboard.press("Control+A")
        playground_page.keyboard.type("SELECT * FROM users")
        playground_page.wait_for_timeout(1000)

        # Switch to pipes mode and visual view
        playground_page.locator("#output-pipes-style-btn").click()
        playground_page.locator("#output-visual-view-btn").click()
        playground_page.wait_for_timeout(500)

        # Hover over the node
        node = playground_page.locator(".pipe-node").first
        node.hover()
        playground_page.wait_for_timeout(100)

        # The node should still be visible and have hover styles applied via CSS
        expect(node).to_be_visible()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
