# Expression Parsing Anti-Pattern Analysis

**Date**: 2026-01-18  
**Issue**: Custom keyword lists that should just be parsed as regular expressions

## The Anti-Pattern

We were creating custom lists of "allowed" keywords/options when we should just parse a regular expression and extract the information from the AST.

### Example: Cohort Granularity

**Before (wrong):**
```python
_COHORT_GRANULARITIES = {"MONTH": "month", "WEEK": "week", "DAY": "day"}

# Manual keyword matching
for token, value in self._COHORT_GRANULARITIES.items():
    if self._match_text_seq(token):
        granularity = value
        break
```

**After (correct):**
```python
# Parse as regular function call: month(date_col)
expr = self._parse_expression()

# Extract granularity from the parsed AST
if isinstance(expr, exp.Month):
    granularity = "month"
# etc.
```

**Why better:**
1. No hardcoded list to maintain
2. Supports ANY date function SQLGlot knows about
3. Follows "parse once, extract from AST" pattern

## Audit Results

### ✅ Already Correct

| Area | Notes |
|------|-------|
| String operators | Uses dict for LIKE patterns, but the dict is for AST building, not keyword matching |
| TIME_UNITS | Legitimate domain list for relative dates ("7 days ago") |
| NATURAL_AGG_FUNCS | Legitimate registry of paren-free syntax functions |
| Date function type checks | Uses `isinstance(expr, exp.Month)` after parsing - correct pattern |

### ⚠️ Potential Issues Found

1. **`_extract_granularity_and_column`** (lines 2491-2514)
   - Has explicit `isinstance` checks for Month, Week, Day, Year, Quarter
   - Could use a dict mapping `{exp.Month: "month", ...}` for cleaner code
   - But this is after parsing, so it's the correct pattern - just verbose

## Key Insight

The anti-pattern is: **Manual token matching for things that are standard expressions**

The fix is: **Parse as expression, then inspect the AST**

### Signs of the Anti-Pattern:
- `_match_text_seq("KEYWORD")` followed by manual AST building
- Custom `_ALLOWED_*` frozensets for things that are just function/expression names
- `if text.upper() == "SOMETHING":` checks for things that could be parsed

### Signs of the Correct Pattern:
- `self._parse_expression()` or `self._parse_column()` 
- `isinstance(expr, exp.SomeType)` checks on the parsed result
- Extracting `expr.name` or `expr.this` from parsed AST

## Recommendations

1. When adding new syntax, ask: "Is this just a standard expression in disguise?"
2. If yes: parse it as an expression and extract info from AST
3. If no (truly custom syntax): use the keyword matching approach

## Example Refactor for Date Granularity Checks

The explicit isinstance chain could become:

```python
DATE_GRANULARITY_TYPES: dict[type[exp.Expression], str] = {
    exp.Month: "month",
    exp.Week: "week", 
    exp.Day: "day",
    exp.Year: "year",
    exp.Quarter: "quarter",
    exp.Hour: "hour",
}

def _extract_granularity_and_column(self, expr):
    for exp_type, name in self.DATE_GRANULARITY_TYPES.items():
        if isinstance(expr, exp_type):
            return (name, expr.this)
    
    # Fall back to function name extraction
    if isinstance(expr, exp.Func):
        return (type(expr).__name__.lower(), expr.this)
    
    return (None, None)
```

This is a minor improvement (same behavior, cleaner code) but demonstrates the dict-based pattern.
