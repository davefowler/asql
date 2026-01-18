# Factory Pattern Opportunities in ASQL Dialect

**Date**: 2026-01-07  
**Context**: Porting window.py to dialect, analyzing DRY opportunities

## Current State

### ✅ Already Using Factories Well

**`functions.py` - `_build_date_diff`**:
```python
def _build_date_diff(unit: str, from_col: bool = True) -> callable:
    """Factory for date difference functions."""
    def builder(args):
        col = seq_get(args, 0) if isinstance(args, list) else args
        if from_col:
            return exp.DateDiff(this=exp.CurrentTimestamp(), expression=col, unit=exp.Literal.string(unit))
        else:
            return exp.DateDiff(this=col, expression=exp.CurrentTimestamp(), unit=exp.Literal.string(unit))
    return builder

# Usage - generates 28 function variants from 1 factory!
ASQL_FUNCTION_REGISTRY = {
    'DAYS_SINCE': _build_date_diff('day', from_col=True),
    'DAYS_UNTIL': _build_date_diff('day', from_col=False),
    'WEEKS_SINCE': _build_date_diff('week', from_col=True),
    # ... etc
}
```

This is the **gold standard** for ASQL - follows SQLGlot's `build_*` pattern exactly.

---

## ✅ Implemented Opportunities

### 1. Window Functions - **COMPLETED**

**Current preparser**: ~400 LOC of regex transforms  
**With factories**: ~80 LOC

```python
# Factory for running aggregates
def build_running_agg(agg_class: t.Type[exp.AggFunc]) -> t.Callable:
    """Factory for running aggregate window functions (cumulative from start)."""
    def _builder(args: t.List) -> exp.Window:
        col = seq_get(args, 0)
        spec = exp.WindowSpec(kind="ROWS", start="UNBOUNDED", start_side="PRECEDING")
        return exp.Window(this=agg_class(this=col), spec=spec)
    return _builder

# Factory for rolling aggregates
def build_rolling_agg(agg_class: t.Type[exp.AggFunc]) -> t.Callable:
    """Factory for rolling window aggregate functions (sliding window)."""
    def _builder(args: t.List) -> exp.Window:
        col = seq_get(args, 0)
        window_size = seq_get(args, 1)
        start = str(int(window_size.this) - 1) if window_size else "UNBOUNDED"
        spec = exp.WindowSpec(kind="ROWS", start=start, start_side="PRECEDING",
                              end="CURRENT ROW", end_side="")
        return exp.Window(this=agg_class(this=col), spec=spec)
    return _builder

# Usage in FUNCTIONS dict
FUNCTIONS = {
    "RUNNING_SUM": build_running_agg(exp.Sum),
    "RUNNING_AVG": build_running_agg(exp.Avg),
    "RUNNING_COUNT": build_running_agg(exp.Count),
    "ROLLING_SUM": build_rolling_agg(exp.Sum),
    "ROLLING_AVG": build_rolling_agg(exp.Avg),
}
```

**Savings**: ~300 LOC, eliminates ORDER BY extraction heuristics

---

### 2. Natural Aggregate Functions - **COMPLETED**

**Current** (`functions.py` lines 106-128):
```python
NATURAL_AGGREGATE_FUNCS = {
    'SUM': lambda args: exp.Sum(this=seq_get(args, 0) if isinstance(args, list) else args),
    'AVG': lambda args: exp.Avg(this=seq_get(args, 0) if isinstance(args, list) else args),
    'COUNT': lambda args: exp.Count(this=seq_get(args, 0) if isinstance(args, list) else args),
    # ... repeated 12 more times
}
```

**With factory**:
```python
def build_natural_agg(agg_class: t.Type[exp.Expression]) -> t.Callable:
    """Factory for natural aggregate functions (sum amount → SUM(amount))."""
    def _builder(args):
        col = seq_get(args, 0) if isinstance(args, list) else args
        return agg_class(this=col)
    return _builder

NATURAL_AGGREGATE_FUNCS = {
    'SUM': build_natural_agg(exp.Sum),
    'AVG': build_natural_agg(exp.Avg),
    'COUNT': build_natural_agg(exp.Count),
    'MIN': build_natural_agg(exp.Min),
    'MAX': build_natural_agg(exp.Max),
    # Aliases
    'TOTAL': build_natural_agg(exp.Sum),
    'AVERAGE': build_natural_agg(exp.Avg),
}
```

**Savings**: ~15 LOC, cleaner code

---

### 3. Fill Functions - **COMPLETED**

**Current preparser**: Regex replacement with IGNORE NULLS logic

**With factory**:
```python
def build_fill_function(direction: str) -> t.Callable:
    """Factory for fill_forward/fill_backward."""
    def _builder(args: t.List) -> exp.Window:
        col = seq_get(args, 0)
        if direction == "forward":
            func = exp.LastValue
            start, start_side = "UNBOUNDED", "PRECEDING"
            end, end_side = "CURRENT ROW", ""
        else:  # backward
            func = exp.FirstValue
            start, start_side = "CURRENT ROW", ""
            end, end_side = "UNBOUNDED", "FOLLOWING"
        
        spec = exp.WindowSpec(kind="ROWS", start=start, start_side=start_side,
                              end=end, end_side=end_side)
        return exp.Window(this=func(this=col, ignore_nulls=True), spec=spec)
    return _builder

FUNCTIONS = {
    "FILL_FORWARD": build_fill_function("forward"),
    "FILL_BACKWARD": build_fill_function("backward"),
}
```

---

## 📋 Future Opportunities (When Porting)

### 4. Join Operators (joins.py) - **FUTURE**

When porting `&`, `<&`, `&>` operators, could use:
```python
def build_join_operator(join_type: str) -> t.Callable:
    """Factory for ASQL join operators."""
    # &  → INNER JOIN
    # <& → LEFT JOIN  
    # &> → RIGHT JOIN
    ...
```

### 5. Per Commands (window.py) - **FUTURE**

`per col first/last/number/rank by order` transforms could use:
```python
def build_per_ranking(window_func: t.Type[exp.Expression], filter_to_first: bool = False):
    """Factory for PER ranking transforms."""
    ...
```

---

## ❌ Not Good Candidates for Factories

### TRANSFORM_PARSERS
Each transform has unique parsing logic - lambdas are appropriate:
```python
TRANSFORM_PARSERS = {
    "WHERE": lambda self, query: self._parse_asql_where(query),
    "GROUP BY": lambda self, query: self._parse_asql_group_by(query),
    # Each has different behavior - no shared pattern
}
```

### FUNCTION_PARSERS  
Custom parsing (like `bucket()` with kwargs) needs method overrides, not factories.

---

## Summary

| Opportunity | Current LOC | With Factory | Savings | Status |
|-------------|-------------|--------------|---------|--------|
| Window functions | ~400 | ~80 | ~320 | ✅ DONE |
| Natural aggregates | ~25 | ~15 | ~10 | ✅ DONE |
| Fill functions | ~50 | ~15 | ~35 | ✅ DONE |
| Join operators | ~100 | ~40 | ~60 | FUTURE |
| Per commands | ~150 | ~60 | ~90 | FUTURE |

**Implemented savings**: ~365 LOC with cleaner, more SQLGlot-idiomatic code.  
**Remaining potential**: ~150 LOC (join operators + per commands)

---

## Implementation Principle

Follow SQLGlot's pattern:
1. **Module-level `build_*` functions** that return callables
2. **Factory takes the varying part** (agg class, direction, unit)
3. **Returns a builder function** that takes `args` list
4. **Explicit mapping in FUNCTIONS dict** - no magic

