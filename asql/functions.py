"""ASQL Function Registry - Single source of truth for all ASQL functions.

This registry is used by:
1. Parser - for function call syntax: days_since(col)
2. Parser - for space notation: days since col  
3. Optimizer - for underscore aliases: days_since_col (schema-aware)

Each function is defined as a lambda that takes a single column expression
and returns an AST expression.

Factory Pattern:
- Use module-level `build_*` functions that return callables
- Factory takes the varying part (agg class, direction, unit)
- Returns a builder function that takes `args` list
- Follows SQLGlot's `build_extract_json_with_path` pattern
"""

from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.helper import seq_get


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================
# These create function builders for families of similar functions.
# Pattern: build_*(parameterized_part) -> callable(args) -> Expression
# =============================================================================


def _build_date_diff(unit: str, from_col: bool = True) -> t.Callable:
    """Build a date difference function.
    
    Args:
        unit: The time unit ('day', 'week', 'month', 'year', etc.)
        from_col: If True, calculates time SINCE col (col to now)
                  If False, calculates time UNTIL col (now to col)
    """
    def builder(args: t.List) -> exp.DateDiff:
        col = seq_get(args, 0) if isinstance(args, list) else args
        if from_col:
            # Time since: DATEDIFF(unit, col, CURRENT_TIMESTAMP)
            return exp.DateDiff(
                this=exp.CurrentTimestamp(),
                expression=col,
                unit=exp.Literal.string(unit),
            )
        else:
            # Time until: DATEDIFF(unit, CURRENT_TIMESTAMP, col)
            return exp.DateDiff(
                this=col,
                expression=exp.CurrentTimestamp(),
                unit=exp.Literal.string(unit),
            )
    return builder


def build_running_agg(agg_class: t.Type[exp.AggFunc], safe: bool = False) -> t.Callable:
    """Factory for running aggregate window functions (cumulative from start).
    
    running_sum(col) → SUM(col) OVER (ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    running_sum_safe(col) → COALESCE(SUM(col) OVER (...), 0)
    
    Args:
        agg_class: The aggregate function class (exp.Sum, exp.Avg, etc.)
        safe: If True, wrap in COALESCE(..., 0) to return 0 instead of NULL
    
    Note: ORDER BY is inherited from the query context or must be specified via OVER clause.
    """
    def _builder(args: t.List) -> exp.Expression:
        col = seq_get(args, 0)
        if not col:
            return None
        spec = exp.WindowSpec(kind="ROWS", start="UNBOUNDED", start_side="PRECEDING")
        window = exp.Window(this=agg_class(this=col), spec=spec)
        if safe:
            return exp.Coalesce(this=window, expressions=[exp.Literal.number(0)])
        return window
    return _builder


def build_rolling_agg(agg_class: t.Type[exp.AggFunc], safe: bool = False) -> t.Callable:
    """Factory for rolling window aggregate functions (sliding window).
    
    rolling_avg(col, 7) → AVG(col) OVER (ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
    rolling_sum_safe(col, 7) → COALESCE(SUM(col) OVER (...), 0)
    
    Args:
        agg_class: The aggregate function class (exp.Sum, exp.Avg, etc.)
        safe: If True, wrap in COALESCE(..., 0) to return 0 instead of NULL
    
    The window size is the number of rows to include (current + preceding).
    """
    def _builder(args: t.List) -> exp.Expression:
        col = seq_get(args, 0)
        window_size = seq_get(args, 1)
        if not col:
            return None
        
        # Calculate preceding rows: window_size - 1 (since current row is included)
        if window_size and isinstance(window_size, exp.Literal):
            try:
                start = str(int(window_size.this) - 1)
            except (ValueError, TypeError):
                start = "UNBOUNDED"
        else:
            start = "UNBOUNDED"
        
        spec = exp.WindowSpec(
            kind="ROWS",
            start=start,
            start_side="PRECEDING",
            end="CURRENT ROW",
            end_side="",
        )
        window = exp.Window(this=agg_class(this=col), spec=spec)
        if safe:
            return exp.Coalesce(this=window, expressions=[exp.Literal.number(0)])
        return window
    return _builder


def build_fill_function(direction: str) -> t.Callable:
    """Factory for fill_forward/fill_backward functions.
    
    fill_forward(col) → LAST_VALUE(col) IGNORE NULLS OVER (ROWS UNBOUNDED PRECEDING)
    fill_backward(col) → FIRST_VALUE(col) IGNORE NULLS OVER (ROWS CURRENT ROW TO UNBOUNDED FOLLOWING)
    
    These propagate the last/next non-null value to fill gaps.
    Note: SQLGlot uses exp.IgnoreNulls wrapper around the function.
    """
    def _builder(args: t.List) -> exp.Window:
        col = seq_get(args, 0)
        if not col:
            return None
        
        if direction == "forward":
            # Look backwards for last non-null value
            func = exp.IgnoreNulls(this=exp.LastValue(this=col))
            spec = exp.WindowSpec(kind="ROWS", start="UNBOUNDED", start_side="PRECEDING")
        else:  # backward
            # Look forwards for next non-null value
            func = exp.IgnoreNulls(this=exp.FirstValue(this=col))
            spec = exp.WindowSpec(
                kind="ROWS",
                start="CURRENT ROW",
                start_side="",
                end="UNBOUNDED",
                end_side="FOLLOWING",
            )
        
        return exp.Window(this=func, spec=spec)
    return _builder


def build_natural_agg(agg_class: t.Type[exp.Expression]) -> t.Callable:
    """Factory for natural aggregate functions (sum amount → SUM(amount)).
    
    Used for space notation parsing where function name precedes column.
    """
    def _builder(args: t.List) -> exp.Expression:
        col = seq_get(args, 0) if isinstance(args, list) else args
        return agg_class(this=col)
    return _builder


# =============================================================================
# ASQL FUNCTION REGISTRY
# =============================================================================
# All functions that support natural language syntax variants.
# Format: 'FUNCTION_NAME': lambda that builds the expression
#
# This enables:
#   - Function call: days_since(created_at)
#   - Space notation: days since created_at
#   - Underscore alias: days_since_created_at (via optimizer with schema)
# =============================================================================

ASQL_FUNCTION_REGISTRY = {
    # -------------------------------------------------------------------------
    # Date Difference - Time SINCE (past to now)
    # Plural is primary, singular is alias (days_since, day_since)
    # -------------------------------------------------------------------------
    'DAYS_SINCE': _build_date_diff('day', from_col=True),
    'DAY_SINCE': _build_date_diff('day', from_col=True),
    'WEEKS_SINCE': _build_date_diff('week', from_col=True),
    'WEEK_SINCE': _build_date_diff('week', from_col=True),
    'MONTHS_SINCE': _build_date_diff('month', from_col=True),
    'MONTH_SINCE': _build_date_diff('month', from_col=True),
    'YEARS_SINCE': _build_date_diff('year', from_col=True),
    'YEAR_SINCE': _build_date_diff('year', from_col=True),
    'HOURS_SINCE': _build_date_diff('hour', from_col=True),
    'HOUR_SINCE': _build_date_diff('hour', from_col=True),
    'MINUTES_SINCE': _build_date_diff('minute', from_col=True),
    'MINUTE_SINCE': _build_date_diff('minute', from_col=True),
    'SECONDS_SINCE': _build_date_diff('second', from_col=True),
    'SECOND_SINCE': _build_date_diff('second', from_col=True),
    
    # -------------------------------------------------------------------------
    # Date Difference - Time UNTIL (now to future)
    # -------------------------------------------------------------------------
    'DAYS_UNTIL': _build_date_diff('day', from_col=False),
    'DAY_UNTIL': _build_date_diff('day', from_col=False),
    'WEEKS_UNTIL': _build_date_diff('week', from_col=False),
    'WEEK_UNTIL': _build_date_diff('week', from_col=False),
    'MONTHS_UNTIL': _build_date_diff('month', from_col=False),
    'MONTH_UNTIL': _build_date_diff('month', from_col=False),
    'YEARS_UNTIL': _build_date_diff('year', from_col=False),
    'YEAR_UNTIL': _build_date_diff('year', from_col=False),
    'HOURS_UNTIL': _build_date_diff('hour', from_col=False),
    'HOUR_UNTIL': _build_date_diff('hour', from_col=False),
    'MINUTES_UNTIL': _build_date_diff('minute', from_col=False),
    'MINUTE_UNTIL': _build_date_diff('minute', from_col=False),
    'SECONDS_UNTIL': _build_date_diff('second', from_col=False),
    'SECOND_UNTIL': _build_date_diff('second', from_col=False),
    
    # -------------------------------------------------------------------------
    # Running Aggregates (cumulative from start of window)
    # SUM/TOTAL use safe=True (COALESCE to 0) - sum of nothing = 0 is intuitive
    # AVG/MIN/MAX return NULL for empty windows - use ?? 0 if you want 0
    # -------------------------------------------------------------------------
    'RUNNING_SUM': build_running_agg(exp.Sum, safe=True),
    'RUNNING_TOTAL': build_running_agg(exp.Sum, safe=True),  # alias
    'RUNNING_AVG': build_running_agg(exp.Avg),
    'RUNNING_AVERAGE': build_running_agg(exp.Avg),  # alias
    'RUNNING_COUNT': build_running_agg(exp.Count),
    'RUNNING_MIN': build_running_agg(exp.Min),
    'RUNNING_MINIMUM': build_running_agg(exp.Min),  # alias
    'RUNNING_MAX': build_running_agg(exp.Max),
    'RUNNING_MAXIMUM': build_running_agg(exp.Max),  # alias
    
    # -------------------------------------------------------------------------
    # Rolling Aggregates (sliding window of N rows)
    # SUM/TOTAL use safe=True (COALESCE to 0) - sum of nothing = 0 is intuitive
    # AVG/MIN/MAX return NULL for empty windows - use ?? 0 if you want 0
    # -------------------------------------------------------------------------
    'ROLLING_SUM': build_rolling_agg(exp.Sum, safe=True),
    'ROLLING_TOTAL': build_rolling_agg(exp.Sum, safe=True),  # alias
    'ROLLING_AVG': build_rolling_agg(exp.Avg),
    'ROLLING_AVERAGE': build_rolling_agg(exp.Avg),  # alias
    'ROLLING_COUNT': build_rolling_agg(exp.Count),
    'ROLLING_MIN': build_rolling_agg(exp.Min),
    'ROLLING_MINIMUM': build_rolling_agg(exp.Min),  # alias
    'ROLLING_MAX': build_rolling_agg(exp.Max),
    'ROLLING_MAXIMUM': build_rolling_agg(exp.Max),  # alias
    
    # -------------------------------------------------------------------------
    # Fill Functions (propagate non-null values)
    # -------------------------------------------------------------------------
    'FILL_FORWARD': build_fill_function('forward'),
    'FILL_BACKWARD': build_fill_function('backward'),
    
    # -------------------------------------------------------------------------
    # ArgMax/ArgMin (value at max/min of another column)
    # SQLGlot has native exp.ArgMax/ArgMin
    # Using dict.fromkeys() for multiple aliases (SQLGlot idiom)
    # -------------------------------------------------------------------------
    'ARG_MAX': exp.ArgMax.from_arg_list,
    'ARGMAX': exp.ArgMax.from_arg_list,  # alias (no underscore)
    'ARG_MIN': exp.ArgMin.from_arg_list,
    'ARGMIN': exp.ArgMin.from_arg_list,  # alias (no underscore)
}


# =============================================================================
# NATURAL SYNTAX: AGGREGATES
# =============================================================================
# These enable natural language syntax like "sum amount" → "SUM(amount)"
# Uses build_natural_agg factory for cleaner, DRY code.
#
# Natural syntax = paren-free function calls where func precedes its argument.
# =============================================================================

NATURAL_AGG_FUNCS = {
    # Aggregates with natural language aliases
    'SUM': build_natural_agg(exp.Sum),
    'TOTAL': build_natural_agg(exp.Sum),  # alias
    'AVG': build_natural_agg(exp.Avg),
    'AVERAGE': build_natural_agg(exp.Avg),  # alias
    'COUNT': build_natural_agg(exp.Count),
    'MIN': build_natural_agg(exp.Min),
    'MINIMUM': build_natural_agg(exp.Min),  # alias
    'MAX': build_natural_agg(exp.Max),
    'MAXIMUM': build_natural_agg(exp.Max),  # alias
    
    # Date parts
    'YEAR': build_natural_agg(exp.Year),
    'MONTH': build_natural_agg(exp.Month),
    'DAY': build_natural_agg(exp.Day),
    'WEEK': build_natural_agg(exp.Week),
    'QUARTER': build_natural_agg(exp.Quarter),
    # HOUR/MINUTE/SECOND need Extract - keep as lambdas for custom structure
    'HOUR': lambda args: exp.Extract(this=exp.Literal.string('HOUR'), expression=seq_get(args, 0) if isinstance(args, list) else args),
    'MINUTE': lambda args: exp.Extract(this=exp.Literal.string('MINUTE'), expression=seq_get(args, 0) if isinstance(args, list) else args),
    'SECOND': lambda args: exp.Extract(this=exp.Literal.string('SECOND'), expression=seq_get(args, 0) if isinstance(args, list) else args),
}


# =============================================================================
# NATURAL SYNTAX: DATE FUNCTIONS
# =============================================================================
# Patterns for "days since col" / "months until col" syntax in the parser.
# Maps (unit, direction) → function name from ASQL_FUNCTION_REGISTRY.
#
# Natural syntax = paren-free function calls where func precedes its argument.
# =============================================================================

NATURAL_DATE_DIRECTIONS = frozenset({'since', 'until'})

NATURAL_DATE_UNITS = frozenset({
    'day', 'days', 'week', 'weeks', 'month', 'months',
    'year', 'years', 'hour', 'hours', 'minute', 'minutes',
    'second', 'seconds',
})


def get_natural_date_function(unit: str, direction: str) -> str | None:
    """Get the function name for natural date syntax like 'days since col'.
    
    Args:
        unit: Time unit ('day', 'days', 'week', etc.)
        direction: 'since' or 'until'
    
    Returns:
        Function name like 'DAYS_SINCE' or None if not valid
    """
    if direction.lower() not in NATURAL_DATE_DIRECTIONS:
        return None
    if unit.lower() not in NATURAL_DATE_UNITS:
        return None
    
    # Normalize to singular base
    unit_lower = unit.lower()
    if unit_lower.endswith('s') and unit_lower not in ('seconds',):
        # Remove trailing 's': days → day, months → month
        singular = unit_lower[:-1]
    else:
        singular = unit_lower
    
    # Handle 'seconds' specially
    if unit_lower == 'seconds':
        singular = 'second'
    
    # Build function name with plural: DAY → DAYS_SINCE, MONTH → MONTHS_UNTIL
    func_name = f"{singular.upper()}S_{direction.upper()}"
    
    if func_name in ASQL_FUNCTION_REGISTRY:
        return func_name
    
    return None


def get_natural_agg(func_name: str) -> callable | None:
    """Get the function builder for natural aggregate syntax.
    
    Supports: sum, avg, count, min, max, year, month, day, etc.
    
    Args:
        func_name: Function name like 'sum', 'avg', etc.
    
    Returns:
        Function builder or None if not a natural aggregate
    """
    return NATURAL_AGG_FUNCS.get(func_name.upper())


# =============================================================================
# BUCKET FUNCTION
# =============================================================================
# The bucket() function for binning/discretization of continuous values.
# Converts to CASE WHEN expressions for portability across all SQL dialects.
#
# Supported forms:
#   bucket(score, [0, 60, 70, 80, 90, 100], ['F', 'D', 'C', 'B', 'A'])
#   bucket(score, [0, 60, 70, 80, 90, 100])  -- auto-labeled as ranges
#   bucket(value, start=0, end=100, width=10)
# =============================================================================


def _extract_literal_value(node: exp.Expression) -> str | float | int | None:
    """Extract the literal value from an expression node."""
    if isinstance(node, exp.Literal):
        if node.is_string:
            return node.this
        else:
            # Try to convert to number
            try:
                val = float(node.this)
                if val == int(val):
                    return int(val)
                return val
            except (ValueError, TypeError):
                return node.this
    elif isinstance(node, exp.Neg):
        # Handle negative numbers like -40
        inner = _extract_literal_value(node.this)
        if isinstance(inner, (int, float)):
            return -inner
    return None


def _extract_array_values(arr: exp.Array) -> list[str | float | int]:
    """Extract values from an Array expression."""
    values = []
    for elem in arr.expressions:
        val = _extract_literal_value(elem)
        if val is not None:
            values.append(val)
    return values


def _build_bucket_case(
    input_expr: exp.Expression,
    boundaries: list[float | int | str],
    labels: list[str] | None = None,
) -> exp.Case:
    """Build a CASE WHEN expression from boundaries.
    
    Boundaries define the edges: [0, 60, 70, 80, 90, 100] creates bins:
    - [0, 60)   -> label[0] or '0-60'
    - [60, 70)  -> label[1] or '60-70'
    - [70, 80)  -> label[2] or '70-80'
    - [80, 90)  -> label[3] or '80-90'
    - [90, 100] -> label[4] or '90-100'
    
    Left-inclusive by default: [lower, upper)
    Last bucket includes upper bound: [lower, upper]
    """
    if len(boundaries) < 2:
        # Return NULL for invalid boundaries
        return exp.Null()
    
    num_bins = len(boundaries) - 1
    
    # Generate labels if not provided
    if not labels or len(labels) != num_bins:
        labels = []
        for i in range(num_bins):
            lower = boundaries[i]
            upper = boundaries[i + 1]
            labels.append(f"{lower}-{upper}")
    
    # Build CASE WHEN ifs
    ifs = []
    for i in range(num_bins):
        lower = boundaries[i]
        upper = boundaries[i + 1]
        label = labels[i]
        
        # Build condition: expr >= lower AND expr < upper (or <= for last bucket)
        lower_cond = exp.GTE(this=input_expr.copy(), expression=exp.Literal.number(lower))
        
        if i == num_bins - 1:
            # Last bucket: include upper bound [lower, upper]
            upper_cond = exp.LTE(this=input_expr.copy(), expression=exp.Literal.number(upper))
        else:
            # Other buckets: left-inclusive, right-exclusive [lower, upper)
            upper_cond = exp.LT(this=input_expr.copy(), expression=exp.Literal.number(upper))
        
        condition = exp.And(this=lower_cond, expression=upper_cond)
        
        # Create the If expression (WHEN condition THEN label)
        if_expr = exp.If(this=condition, true=exp.Literal.string(label))
        ifs.append(if_expr)
    
    # Build CASE with all IFs
    case = exp.Case(ifs=ifs, default=exp.Null())
    return case


def _build_bucket(args: list[exp.Expression]) -> exp.Expression:
    """Build a bucket CASE expression from function arguments.
    
    Handles:
    - bucket(expr, [boundaries], [labels])
    - bucket(expr, [boundaries])
    - bucket(expr, start=X, end=Y, width=Z)
    """
    if len(args) < 2:
        # Invalid: need at least expr and boundaries/kwargs
        return exp.Anonymous(this="bucket", expressions=args)
    
    input_expr = args[0]
    
    # Check for keyword arguments (EQ expressions)
    kwargs: dict[str, float] = {}
    positional_args: list[exp.Expression] = []
    
    for arg in args[1:]:
        if isinstance(arg, exp.EQ):
            # Keyword argument: start=0, end=100, width=10
            key = arg.this.name.lower() if hasattr(arg.this, 'name') else str(arg.this)
            val = _extract_literal_value(arg.expression)
            if key in ('start', 'end', 'width') and val is not None:
                kwargs[key] = float(val)
        else:
            positional_args.append(arg)
    
    # Handle width-based form: bucket(expr, start=X, end=Y, width=Z)
    if 'start' in kwargs and 'end' in kwargs and 'width' in kwargs:
        start_val = kwargs['start']
        end_val = kwargs['end']
        width_val = kwargs['width']
        
        if width_val <= 0:
            return exp.Anonymous(this="bucket", expressions=args)
        
        # Generate boundaries from start, end, width
        boundaries: list[float | int] = []
        current = start_val
        while current <= end_val:
            # Format nicely: integer if whole number
            if current == int(current):
                boundaries.append(int(current))
            else:
                boundaries.append(current)
            current += width_val
        
        # Ensure end is included
        end_int = int(end_val) if end_val == int(end_val) else end_val
        if boundaries[-1] != end_int:
            boundaries.append(end_int)
        
        return _build_bucket_case(input_expr, boundaries, None)
    
    # Handle boundary-based forms
    if not positional_args:
        return exp.Anonymous(this="bucket", expressions=args)
    
    # First positional should be boundaries array
    boundaries_arg = positional_args[0]
    if not isinstance(boundaries_arg, exp.Array):
        return exp.Anonymous(this="bucket", expressions=args)
    
    boundaries = _extract_array_values(boundaries_arg)
    if len(boundaries) < 2:
        return exp.Anonymous(this="bucket", expressions=args)
    
    # Check for labels array (second positional)
    labels: list[str] | None = None
    if len(positional_args) >= 2:
        labels_arg = positional_args[1]
        if isinstance(labels_arg, exp.Array):
            labels = [str(v) for v in _extract_array_values(labels_arg)]
    
    return _build_bucket_case(input_expr, boundaries, labels)

