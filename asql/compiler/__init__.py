"""ASQL dialect-aware transforms (transpile stage).

This package contains AST transforms that need to know the OUTPUT dialect.
These are applied in asql.transpile(), not during parsing.

Transform modules:
- spine: gap-filling spine for explicit spine() expressions
- spine_helpers: helper functions for spine generation
- alias_reuse: CTE chain for alias reuse on non-DuckDB
- column_operators: EXCEPT/RENAME/REPLACE expansion
- list_comprehension: DuckDB native [x FOR x] conversion

For parser-stage transforms (underscore_shorthands, auto_alias, auto_qualify,
join_fk_shorthand, cohort_transform), see asql/dialect/transforms/.
"""

# Re-export join_inference from its new location for backwards compatibility
from asql.dialect.transforms.join_inference import resolve_join_condition, JoinCondition

# Spine helpers (used by spine.py and tests)
from asql.compiler.spine_helpers import (
    _build_categorical_spine_sql,
    _build_date_spine_from_data_sql,
    _build_date_spine_sql,
    _build_distinct_values_spine_sql,
    _columns_match,
    _detect_rollup_cube,
    _extract_date_bounds_from_where,
    _find_date_trunc_in_group_by,
    _find_non_date_group_by_columns,
    _get_all_group_by_columns,
    _get_source_column_from_trunc,
    DATE_TRUNC_FUNCTIONS,
    TRUNC_TO_INTERVAL,
)

__all__ = [
    # Join inference (re-exported from dialect/transforms/)
    "resolve_join_condition",
    "JoinCondition",
    # Spine helpers
    "_build_categorical_spine_sql",
    "_build_date_spine_from_data_sql",
    "_build_date_spine_sql",
    "_build_distinct_values_spine_sql",
    "_columns_match",
    "_detect_rollup_cube",
    "_extract_date_bounds_from_where",
    "_find_date_trunc_in_group_by",
    "_find_non_date_group_by_columns",
    "_get_all_group_by_columns",
    "_get_source_column_from_trunc",
    "DATE_TRUNC_FUNCTIONS",
    "TRUNC_TO_INTERVAL",
]
