"""Parser-stage transforms for ASQL.

These transforms are applied during parsing (in ASQLParser._apply_asql_transforms)
and do NOT require knowledge of the output dialect.

For dialect-aware transforms (spine, alias_reuse, column_operators, list_comprehension),
see asql/compiler/ - these are applied in asql.transpile().
"""

from asql.dialect.transforms.underscore_shorthands import (
    apply_since_until_underscore_shorthands,
    apply_implicit_function_aliases,
)

from asql.dialect.transforms.auto_alias import (
    apply_auto_aliasing,
)

from asql.dialect.transforms.auto_qualify import (
    auto_qualify_columns,
)

from asql.dialect.transforms.join_fk_shorthand import (
    transform_fk_shorthand,
)

from asql.dialect.transforms.join_inference import (
    resolve_join_condition,
    JoinCondition,
)

__all__ = [
    # Underscore shorthands
    "apply_since_until_underscore_shorthands",
    "apply_implicit_function_aliases",
    # Auto-aliasing
    "apply_auto_aliasing",
    # Auto-qualify
    "auto_qualify_columns",
    # FK shorthand
    "transform_fk_shorthand",
    # Join inference
    "resolve_join_condition",
    "JoinCondition",
]
