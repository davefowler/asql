"""ASQL compiler package.

This package contains the ASQL→SQL compilation pipeline and related utilities.

Public API:
- compile
- compile_to_ast
- get_settings_from_query

Implementation submodules:
- auto_spine: gap-filling spine transformations
- inline_settings: inline SET parsing
- explode_fallback: dialect-specific explode rewriting (Snowflake FLATTEN)
- pivot_fallback: PIVOT to CASE/WHEN for non-native dialects
"""

from asql.compiler.api import compile, compile_to_ast, get_settings_from_query
from asql.compiler.inline_settings import extract_inline_settings, extract_dialect_from_comment
from asql.compiler.explode_fallback import transform_explode_for_dialect
from asql.compiler.pivot_fallback import transform_pivot_for_dialect
from asql.compiler.join_inference import resolve_join_condition, JoinCondition
from asql.compiler.auto_spine import (
    _apply_auto_spine,
    _build_categorical_spine_sql,
    _build_date_spine_from_data_sql,
    _build_date_spine_sql,
    _columns_match,
    _detect_rollup_cube,
    _extract_date_bounds_from_where,
    _find_date_trunc_in_group_by,
    _find_guarantee_in_group_by,
    _find_non_date_group_by_columns,
    _get_all_group_by_columns,
    _get_source_column_from_trunc,
    _is_guarantee_wrapped,
    _remove_guarantee_wrappers,
    _unwrap_guarantee,
    DATE_TRUNC_FUNCTIONS,
    TRUNC_TO_INTERVAL,
)

__all__ = [
    "compile",
    "compile_to_ast",
    "get_settings_from_query",
    "extract_inline_settings",
    "extract_dialect_from_comment",
    "transform_explode_for_dialect",
    "transform_pivot_for_dialect",
    # Join inference
    "resolve_join_condition",
    "JoinCondition",
    # Auto-spine (semi-private; used by tests and power users)
    "_apply_auto_spine",
    "_build_categorical_spine_sql",
    "_build_date_spine_from_data_sql",
    "_build_date_spine_sql",
    "_columns_match",
    "_detect_rollup_cube",
    "_extract_date_bounds_from_where",
    "_find_date_trunc_in_group_by",
    "_find_guarantee_in_group_by",
    "_find_non_date_group_by_columns",
    "_get_all_group_by_columns",
    "_get_source_column_from_trunc",
    "_is_guarantee_wrapped",
    "_remove_guarantee_wrappers",
    "_unwrap_guarantee",
    "DATE_TRUNC_FUNCTIONS",
    "TRUNC_TO_INTERVAL",
]
