"""ASQL pre-parser orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, TYPE_CHECKING

from asql.preparse.comments import CommentsMixin
from asql.preparse.settings import SettingsMixin
from asql.preparse.pipeline import PipelineMixin
from asql.preparse.joins import JoinsMixin
from asql.preparse.count import CountMixin
from asql.preparse.coalesce import CoalesceMixin
from asql.preparse.order import OrderMixin
from asql.preparse.aggregates import AggregatesMixin
from asql.preparse.dates import DatesMixin
from asql.preparse.stash import StashMixin
from asql.preparse.clauses import ClausesMixin
from asql.preparse.pivot import PivotMixin
from asql.preparse.window import WindowMixin
from asql.preparse.normalize import NormalizeMixin
from asql.preparse.cohort import CohortMixin
from asql.preparse.key import KeyMixin
from asql.preparse.when import WhenMixin
from asql.preparse.ternary import TernaryMixin
from asql.preparse.list_comprehension import ListComprehensionMixin
from asql.preparse.bucket import BucketMixin

if TYPE_CHECKING:
    from asql.config import CompileSettings

@dataclass
class PreParseResult:
    """Result of pre-parsing ASQL."""
    sql_like: str
    original: str
    ctes: List[Tuple[str, str]]  # (name, query) pairs for CTEs

class ASQLPreParser(
    CommentsMixin,
    SettingsMixin,
    PipelineMixin,
    JoinsMixin,
    CountMixin,
    CoalesceMixin,
    OrderMixin,
    AggregatesMixin,
    DatesMixin,
    StashMixin,
    ClausesMixin,
    PivotMixin,
    WindowMixin,
    NormalizeMixin,
    CohortMixin,
    TernaryMixin,
    WhenMixin,
    KeyMixin,
    ListComprehensionMixin,
    BucketMixin,
):
    def __init__(
        self,
        text: str,
        settings: Optional["CompileSettings"] = None,
        dialect: Optional[str] = None,
    ):
        self.text = text.strip()
        self.original = text
        self.pos = 0
        self.ctes: List[Tuple[str, str]] = []
        self.settings = settings  # Compile settings with schema for join inference
        self.dialect = dialect  # Target SQL dialect for dialect-specific transformations

    def preparse(self) -> str:
        """Apply all transformations and return SQL-like text."""
        result = self.text
        
        # Handle comments first - preserve them during transformation
        result, comments = self._extract_comments(result)
        
        # Apply transformations in order
        result = self._transform_set_statements(result)
        result = self._transform_pipeline(result)
        result = self._transform_join_operators(result)  # Early: transform join operators before other processing
        result = self._normalize_where_before_joins(result)  # Ensure WHEREs move after JOINs (pipeline semantics)
        result = self._transform_stash_as(result)  # Early: split query at stash points before other transforms
        result = self._transform_count_shorthand(result)
        result = self._transform_deduplicate_by(result)  # Transform deduplicate by to per ... first by
        result = self._transform_order_desc_prefix(result)
        result = self._transform_natural_aggregates(result)
        result = self._transform_date_literals(result)
        result = self._transform_relative_dates(result)
        result = self._transform_date_arithmetic(result)
        result = self._transform_since_until_patterns(result)
        result = self._transform_per_commands(result)
        result = self._transform_implicit_function_aliases(result)  # sum_amount → sum(amount) as sum_amount (SELECT and GROUP BY)
        result = self._transform_aggregate_blocks(result)
        result = self._transform_column_operators(result)  # except, rename, replace - before from_first
        result = self._transform_multiple_where(result)  # Combine multiple WHERE clauses
        result = self._transform_string_matching_operators(result)  # contains, icontains, starts with, etc.
        result = self._transform_explode(result)  # explode array as alias
        result = self._transform_unpivot(result)  # unpivot cols into name, value
        result = self._transform_pivot(result)  # pivot value by key - creates __PIVOT_COLS__ marker
        result = self._transform_from_first(result)
        result = self._transform_pivot_marker(result)  # Expand __PIVOT_COLS__ markers after from_first
        result = self._transform_distinct_on(result)  # Move DISTINCT ON to after SELECT
        result = self._transform_star_column_override(result)  # select *, col as name → select * EXCEPT(name), col as name
        result = self._transform_cohort_by(result)  # cohort by - transforms to CTEs and joins (after FROM-first)
        result = self._transform_window_functions(result)  # prior, next, running_*, rolling_*
        result = self._transform_qualify_clause(result)  # qualify rn == 1
        result = self._transform_coalesce_operator(result)  # After FROM-first for proper structure
        result = self._transform_ternary_expressions(result)  # ternary ? : expressions to CASE WHEN
        result = self._transform_when_expressions(result)  # when expressions to CASE WHEN
        result = self._transform_bucket_function(result)  # bucket() function to CASE WHEN
        result = self._transform_list_comprehensions(result)  # [expr for var in arr] to ARRAY(SELECT ...)
        result = self._transform_key_function(result)  # key(col1, col2, ...) surrogate key generation
        result = self._transform_sample_clause(result)  # sample N, sample N%, sample N per col
        result = self._normalize_function_spaces(result)
        result = self._transform_equality_operators(result)
        
        # Restore comments
        result = self._restore_comments(result, comments)
        
        # Wrap with CTEs if any
        if self.ctes:
            cte_parts = []
            for name, query in self.ctes:
                cte_parts.append(f"{name} AS ({query})")
            result = "WITH " + ", ".join(cte_parts) + " " + result
        
        return result
