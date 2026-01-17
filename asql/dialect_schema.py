"""
ASQL Dialect Schema - Single source of truth using dataclasses

This is the canonical definition of ASQL's syntax, operators, and semantics.
Used by:
- Parser (dialect.py) - for parsing ASQL
- Visual Editor (ui_schema.py) - for generating UI
- LSP/Autocomplete - for code intelligence
- Documentation - for generating reference docs

Everything about ASQL's syntax is defined here using type-safe dataclasses.
No magic strings, full IDE autocomplete support.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from sqlglot import exp, TokenType


# =============================================================================
# DATACLASS DEFINITIONS
# =============================================================================


@dataclass(frozen=True)
class Operator:
    """Definition of a comparison/equality operator"""

    token: TokenType
    expr_class: type  # SQLGlot expression class (exp.GT, exp.LT, etc.)
    symbol: str
    label: str
    description: str


@dataclass(frozen=True)
class StringOperator:
    """Definition of an ASQL string matching operator"""

    tokens: tuple  # Token sequence to match, e.g., ("STARTS", "WITH")
    wrap_pattern: tuple  # Left/right wrap patterns for LIKE, e.g., ("", "%")
    case_sensitive: bool
    label: str
    description: str


@dataclass(frozen=True)
class JoinType:
    """Definition of a join operation type"""

    kind: str  # SQL join kind: "INNER", "LEFT", "RIGHT", "FULL OUTER", "CROSS"
    symbols: List[str]  # ASQL symbols: ["&"], ["&?"], etc.
    keywords: List[str]  # SQL keywords: ["JOIN", "INNER JOIN"]
    label: str  # UI label: "inner (&)"
    description: str
    default: bool = False


@dataclass(frozen=True)
class Aggregate:
    """Definition of an aggregate function"""

    expr_class: type  # SQLGlot aggregate class (exp.Count, exp.Sum, etc.)
    label: str
    description: str
    allows_distinct: bool = False
    category: str = "basic"


@dataclass(frozen=True)
class Parameter:
    """Definition of a transform parameter"""

    name: str
    type: str  # "expression", "table", "column", "integer", etc.
    required: bool
    label: str
    widget: str  # "text", "dropdown", "expression", "list", etc.
    description: str = ""
    placeholder: str = ""
    help: str = ""

    # Population logic for dropdowns
    populate_query: Optional[str] = None  # ASQL query to fetch options
    populate_depends_on: Optional[str] = None  # Parameter this depends on

    # Widget-specific config
    operators: Optional[List[str]] = None  # For expression widgets
    options: Optional[str] = None  # Reference to class (e.g., "JOIN_TYPES")
    min_value: Optional[int] = None  # For integer widgets
    max_value: Optional[int] = None


@dataclass(frozen=True)
class Transform:
    """Definition of a pipeline transform operation"""

    keywords: List[str]  # Keywords that trigger this transform
    label: str
    category: str  # Optional grouping: "filter", "join", "aggregate", etc.
    description: str
    parameters: Dict[str, Parameter]  # Parameter name -> Parameter
    symbols: List[str] = field(default_factory=list)  # Optional symbols (for joins)
    parser_method: Optional[str] = None  # Reference to parser method name


# =============================================================================
# OPERATORS
# =============================================================================


class OPERATORS:
    """Comparison, equality, string, and logical operators"""

    # Standard comparison operators
    class COMPARISON:
        GT = Operator(
            token=TokenType.GT,
            expr_class=exp.GT,
            symbol=">",
            label=">",
            description="Greater than",
        )
        GTE = Operator(
            token=TokenType.GTE,
            expr_class=exp.GTE,
            symbol=">=",
            label=">=",
            description="Greater than or equal",
        )
        LT = Operator(
            token=TokenType.LT,
            expr_class=exp.LT,
            symbol="<",
            label="<",
            description="Less than",
        )
        LTE = Operator(
            token=TokenType.LTE,
            expr_class=exp.LTE,
            symbol="<=",
            label="<=",
            description="Less than or equal",
        )

    # Equality operators
    class EQUALITY:
        EQ = Operator(
            token=TokenType.EQ,
            expr_class=exp.EQ,
            symbol="=",
            label="=",
            description="Equal to (use == in ASQL syntax)",
        )
        NEQ = Operator(
            token=TokenType.NEQ,
            expr_class=exp.NEQ,
            symbol="!=",
            label="!=",
            description="Not equal",
        )
        NULLSAFE_EQ = Operator(
            token=TokenType.NULLSAFE_EQ,
            expr_class=exp.NullSafeEQ,
            symbol="<=>",
            label="<=>",
            description="Null-safe equality (MySQL style)",
        )

    # ASQL-specific string operators
    class STRING:
        CONTAINS = StringOperator(
            tokens=("CONTAINS",),
            wrap_pattern=("%", "%"),
            case_sensitive=True,
            label="contains",
            description="String contains (case-sensitive)",
        )
        ICONTAINS = StringOperator(
            tokens=("ICONTAINS",),
            wrap_pattern=("%", "%"),
            case_sensitive=False,
            label="icontains",
            description="String contains (case-insensitive)",
        )
        STARTS_WITH = StringOperator(
            tokens=("STARTS", "WITH"),
            wrap_pattern=("", "%"),
            case_sensitive=True,
            label="starts with",
            description="String starts with (case-sensitive)",
        )
        ISTARTS_WITH = StringOperator(
            tokens=("ISTARTS", "WITH"),
            wrap_pattern=("", "%"),
            case_sensitive=False,
            label="istarts with",
            description="String starts with (case-insensitive)",
        )
        ENDS_WITH = StringOperator(
            tokens=("ENDS", "WITH"),
            wrap_pattern=("%", ""),
            case_sensitive=True,
            label="ends with",
            description="String ends with (case-sensitive)",
        )
        IENDS_WITH = StringOperator(
            tokens=("IENDS", "WITH"),
            wrap_pattern=("%", ""),
            case_sensitive=False,
            label="iends with",
            description="String ends with (case-insensitive)",
        )
        MATCHES = StringOperator(
            tokens=("MATCHES",),
            wrap_pattern=("", ""),
            case_sensitive=True,
            label="matches",
            description="Regex pattern match",
        )


# =============================================================================
# JOIN TYPES
# =============================================================================


class JOIN_TYPES:
    """Join operation types with symbols and keywords"""

    INNER = JoinType(
        kind="INNER",
        symbols=["&"],
        keywords=["JOIN", "INNER JOIN"],
        label="inner (&)",
        description="Inner join - only matching rows",
        default=True,
    )

    LEFT = JoinType(
        kind="LEFT",
        symbols=["&?"],
        keywords=["LEFT JOIN", "LEFT OUTER JOIN"],
        label="left (&?)",
        description="Left outer join - all left rows + matches",
    )

    RIGHT = JoinType(
        kind="RIGHT",
        symbols=["?&"],
        keywords=["RIGHT JOIN", "RIGHT OUTER JOIN"],
        label="right (?&)",
        description="Right outer join - all right rows + matches",
    )

    FULL = JoinType(
        kind="FULL OUTER",
        symbols=["?&?"],
        keywords=["FULL JOIN", "FULL OUTER JOIN"],
        label="full (?&?)",
        description="Full outer join - all rows from both sides",
    )

    CROSS = JoinType(
        kind="CROSS",
        symbols=["*"],
        keywords=["CROSS JOIN"],
        label="cross (*)",
        description="Cross join - cartesian product",
    )


# =============================================================================
# AGGREGATES
# =============================================================================


class AGGREGATES:
    """Aggregate functions"""

    COUNT = Aggregate(
        expr_class=exp.Count,
        label="count",
        description="Count number of rows",
        allows_distinct=True,
        category="basic",
    )

    SUM = Aggregate(
        expr_class=exp.Sum,
        label="sum",
        description="Sum of values",
        allows_distinct=True,
        category="basic",
    )

    AVG = Aggregate(
        expr_class=exp.Avg,
        label="avg",
        description="Average of values",
        allows_distinct=True,
        category="basic",
    )

    MIN = Aggregate(
        expr_class=exp.Min,
        label="min",
        description="Minimum value",
        allows_distinct=False,
        category="basic",
    )

    MAX = Aggregate(
        expr_class=exp.Max,
        label="max",
        description="Maximum value",
        allows_distinct=False,
        category="basic",
    )

    COUNT_DISTINCT = Aggregate(
        expr_class=exp.Count,
        label="count distinct",
        description="Count unique values",
        allows_distinct=True,
        category="basic",
    )


# =============================================================================
# TRANSFORMS
# =============================================================================


class TRANSFORMS:
    """Pipeline operations (where, select, join, etc.)"""

    WHERE = Transform(
        keywords=["WHERE", "FILTER", "IF"],
        label="where",
        category="filter",
        description="Filter rows by condition",
        parser_method="_parse_asql_where",
        parameters={
            "condition": Parameter(
                name="condition",
                type="expression",
                required=True,
                label="condition",
                widget="expression",
                description="Boolean expression to filter rows",
                operators=["=", "!=", "<", ">", "<=", ">=", "contains", "starts with"],
            ),
        },
    )

    SELECT = Transform(
        keywords=["SELECT", "PROJECT"],
        label="select",
        category="select",
        description="Choose which columns to return",
        parser_method="_parse_asql_select",
        parameters={
            "columns": Parameter(
                name="columns",
                type="list[column]",
                required=True,
                label="columns",
                widget="list",
                description="List of columns or expressions to select",
                placeholder="column_name",
                populate_depends_on="table",
                populate_query="""
                    from information_schema.columns
                    where table_name = $table
                    select column_name, data_type
                """,
            ),
        },
    )

    JOIN = Transform(
        keywords=["JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS"],
        symbols=["&", "&?", "?&", "?&?", "*"],
        label="join",
        category="join",
        description="Join with another table",
        parser_method="_parse_asql_join",
        parameters={
            "join_type": Parameter(
                name="join_type",
                type="enum",
                required=True,
                label="join type",
                widget="dropdown",
                description="Type of join operation",
                options="JOIN_TYPES",  # Reference to JOIN_TYPES class
            ),
            "table": Parameter(
                name="table",
                type="table",
                required=True,
                label="table",
                widget="dropdown",
                description="Table to join with",
                placeholder="table_name",
                populate_query="""
                    from information_schema.tables
                    where table_schema = current_schema()
                    select table_name
                """,
            ),
            "condition": Parameter(
                name="condition",
                type="expression",
                required=False,
                label="on",
                widget="expression",
                description="Join condition",
                help="Leave empty to infer from schema",
                operators=["=", "!="],
            ),
        },
    )

    GROUP_BY = Transform(
        keywords=["GROUP BY"],
        label="group by",
        category="aggregate",
        description="Group rows and compute aggregates",
        parser_method="_parse_asql_group_by",
        parameters={
            "dimensions": Parameter(
                name="dimensions",
                type="list[column]",
                required=True,
                label="group by",
                widget="list",
                description="Columns to group by",
                placeholder="column_name",
            ),
            "aggregates": Parameter(
                name="aggregates",
                type="list[aggregate]",
                required=False,
                label="aggregations",
                widget="aggregate_list",
                description="Aggregate functions to compute",
                options="AGGREGATES",  # Reference to AGGREGATES class
            ),
        },
    )

    ORDER_BY = Transform(
        keywords=["ORDER BY"],
        label="order by",
        category="sort",
        description="Sort results",
        parser_method="_parse_asql_order_by",
        parameters={
            "expressions": Parameter(
                name="expressions",
                type="list[order_expression]",
                required=True,
                label="order by",
                widget="order_list",
                description="Columns to sort by with direction",
            ),
        },
    )

    LIMIT = Transform(
        keywords=["LIMIT"],
        label="limit",
        category="utility",
        description="Limit number of results",
        parser_method="query.limit",
        parameters={
            "count": Parameter(
                name="count",
                type="integer",
                required=True,
                label="count",
                widget="number",
                description="Maximum number of rows to return",
                min_value=1,
            ),
        },
    )

    EXTEND = Transform(
        keywords=["EXTEND"],
        label="extend",
        category="transform",
        description="Add computed columns",
        parser_method="_parse_asql_extend",
        parameters={
            "columns": Parameter(
                name="columns",
                type="list[aliased_expression]",
                required=True,
                label="columns",
                widget="list",
                description="New columns with expressions",
                placeholder="new_col = expression",
            ),
        },
    )

    STASH = Transform(
        keywords=["STASH"],
        label="stash",
        category="utility",
        description="Save as CTE for reuse",
        parser_method="_parse_asql_stash",
        parameters={
            "name": Parameter(
                name="name",
                type="identifier",
                required=True,
                label="as",
                widget="text",
                description="Name for the CTE",
                placeholder="cte_name",
            ),
        },
    )

    HAVING = Transform(
        keywords=["HAVING"],
        label="having",
        category="filter",
        description="Filter aggregated results",
        parser_method="query.having",
        parameters={
            "condition": Parameter(
                name="condition",
                type="expression",
                required=True,
                label="condition",
                widget="expression",
                description="Boolean expression to filter aggregated rows",
                operators=["=", "!=", "<", ">", "<=", ">="],
            ),
        },
    )

    QUALIFY = Transform(
        keywords=["QUALIFY"],
        label="qualify",
        category="filter",
        description="Filter window function results",
        parser_method="query.qualify",
        parameters={
            "condition": Parameter(
                name="condition",
                type="expression",
                required=True,
                label="condition",
                widget="expression",
                description="Boolean expression with window functions",
                operators=["=", "!=", "<", ">", "<=", ">="],
            ),
        },
    )

    EXPLODE = Transform(
        keywords=["EXPLODE"],
        label="explode",
        category="transform",
        description="Unnest array column into multiple rows",
        parser_method="_parse_asql_explode",
        parameters={
            "column": Parameter(
                name="column",
                type="column",
                required=True,
                label="column",
                widget="text",
                description="Array column to unnest",
                placeholder="array_column",
            ),
        },
    )

    DISTINCT = Transform(
        keywords=["DISTINCT"],
        label="distinct",
        category="utility",
        description="Remove duplicate rows",
        parser_method="_parse_asql_distinct",
        parameters={},
    )

    EXCEPT = Transform(
        keywords=["EXCEPT"],
        label="except",
        category="select",
        description="Remove specified columns from selection",
        parser_method="_parse_asql_except",
        parameters={
            "columns": Parameter(
                name="columns",
                type="list[column]",
                required=True,
                label="columns",
                widget="list",
                description="Columns to exclude",
                placeholder="column_name",
            ),
        },
    )

    RENAME = Transform(
        keywords=["RENAME"],
        label="rename",
        category="transform",
        description="Rename columns",
        parser_method="_parse_asql_rename",
        parameters={
            "mappings": Parameter(
                name="mappings",
                type="list[rename_mapping]",
                required=True,
                label="renames",
                widget="list",
                description="Column rename mappings",
                placeholder="old_name = new_name",
            ),
        },
    )

    REPLACE = Transform(
        keywords=["REPLACE"],
        label="replace",
        category="transform",
        description="Replace column definitions",
        parser_method="_parse_asql_replace",
        parameters={
            "columns": Parameter(
                name="columns",
                type="list[aliased_expression]",
                required=True,
                label="columns",
                widget="list",
                description="Column replacements",
                placeholder="col = new_expression",
            ),
        },
    )

    SAMPLE = Transform(
        keywords=["SAMPLE"],
        label="sample",
        category="utility",
        description="Sample rows from result set",
        parser_method="_parse_asql_sample",
        parameters={
            "size": Parameter(
                name="size",
                type="number",
                required=True,
                label="size",
                widget="number",
                description="Sample size (number or percentage)",
                min_value=1,
            ),
        },
    )

    PER = Transform(
        keywords=["PER"],
        label="per",
        category="window",
        description="Define window partitioning for subsequent operations",
        parser_method="_parse_asql_per",
        parameters={
            "columns": Parameter(
                name="columns",
                type="list[column]",
                required=True,
                label="partition by",
                widget="list",
                description="Columns to partition by",
                placeholder="column_name",
            ),
        },
    )

    NUMBER = Transform(
        keywords=["NUMBER"],
        label="number",
        category="window",
        description="Add row number column",
        parser_method="_parse_asql_standalone_rank",
        parameters={
            "alias": Parameter(
                name="alias",
                type="identifier",
                required=False,
                label="as",
                widget="text",
                description="Alias for row number column",
                placeholder="row_num",
            ),
        },
    )

    RANK = Transform(
        keywords=["RANK"],
        label="rank",
        category="window",
        description="Add rank column (with gaps)",
        parser_method="_parse_asql_standalone_rank",
        parameters={
            "alias": Parameter(
                name="alias",
                type="identifier",
                required=False,
                label="as",
                widget="text",
                description="Alias for rank column",
                placeholder="rank",
            ),
        },
    )

    DENSE = Transform(
        keywords=["DENSE"],
        label="dense",
        category="window",
        description="Add dense rank column (without gaps)",
        parser_method="_parse_asql_dense_rank_standalone",
        parameters={
            "alias": Parameter(
                name="alias",
                type="identifier",
                required=False,
                label="as",
                widget="text",
                description="Alias for dense rank column",
                placeholder="dense_rank",
            ),
        },
    )

    DEDUPLICATE = Transform(
        keywords=["DEDUPLICATE"],
        label="deduplicate",
        category="utility",
        description="Remove duplicate rows keeping first occurrence",
        parser_method="_parse_asql_deduplicate",
        parameters={
            "columns": Parameter(
                name="columns",
                type="list[column]",
                required=False,
                label="by columns",
                widget="list",
                description="Columns to determine duplicates (empty = all columns)",
                placeholder="column_name",
            ),
        },
    )

    COHORT = Transform(
        keywords=["COHORT"],
        label="cohort",
        category="analytics",
        description="Create cohort analysis with retention calculations",
        parser_method="_parse_asql_cohort",
        parameters={
            "entity": Parameter(
                name="entity",
                type="column",
                required=True,
                label="entity",
                widget="text",
                description="Entity column (e.g., user_id)",
                placeholder="user_id",
            ),
            "cohort_date": Parameter(
                name="cohort_date",
                type="column",
                required=True,
                label="cohort date",
                widget="text",
                description="Date column for cohort grouping",
                placeholder="signup_date",
            ),
            "event_date": Parameter(
                name="event_date",
                type="column",
                required=True,
                label="event date",
                widget="text",
                description="Date column for event tracking",
                placeholder="activity_date",
            ),
        },
    )

    RECURSE = Transform(
        keywords=["RECURSE"],
        label="recurse",
        category="advanced",
        description="Create recursive CTE for hierarchical data",
        parser_method="_parse_asql_recurse",
        parameters={
            "max_depth": Parameter(
                name="max_depth",
                type="integer",
                required=False,
                label="max depth",
                widget="number",
                description="Maximum recursion depth",
                min_value=1,
            ),
        },
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_all_operators() -> List[Operator]:
    """Get all comparison and equality operators flattened into a list."""
    ops = []
    for cls in [OPERATORS.COMPARISON, OPERATORS.EQUALITY]:
        for name in dir(cls):
            if not name.startswith("_"):
                op = getattr(cls, name)
                if isinstance(op, Operator):
                    ops.append(op)
    return ops


def get_all_string_operators() -> List[StringOperator]:
    """Get all string matching operators."""
    ops = []
    for name in dir(OPERATORS.STRING):
        if not name.startswith("_"):
            op = getattr(OPERATORS.STRING, name)
            if isinstance(op, StringOperator):
                ops.append(op)
    return ops


def get_join_options() -> List[Dict[str, str]]:
    """Get join type options formatted for UI dropdown."""
    options = []
    for name in dir(JOIN_TYPES):
        if not name.startswith("_"):
            join = getattr(JOIN_TYPES, name)
            if isinstance(join, JoinType):
                options.append(
                    {"value": name, "label": join.label, "description": join.description}
                )
    return options


def get_aggregate_options() -> List[Dict[str, str]]:
    """Get aggregate function options formatted for UI dropdown."""
    options = []
    for name in dir(AGGREGATES):
        if not name.startswith("_"):
            agg = getattr(AGGREGATES, name)
            if isinstance(agg, Aggregate):
                options.append({"value": name, "label": agg.label, "description": agg.description})
    return options


def get_transform_by_keyword(keyword: str) -> Optional[Transform]:
    """Get transform definition by keyword (e.g., 'WHERE' -> TRANSFORMS.WHERE)"""
    keyword_upper = keyword.upper()
    for name in dir(TRANSFORMS):
        if not name.startswith("_"):
            transform = getattr(TRANSFORMS, name)
            if isinstance(transform, Transform) and keyword_upper in transform.keywords:
                return transform
    return None


def get_all_transforms() -> List[Transform]:
    """Get list of all available transforms."""
    transforms = []
    for name in dir(TRANSFORMS):
        if not name.startswith("_"):
            transform = getattr(TRANSFORMS, name)
            if isinstance(transform, Transform):
                transforms.append(transform)
    return transforms
