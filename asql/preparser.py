"""ASQL Pre-Parser - Transforms ASQL structure to SQL-like structure before SQLGlot parsing.

This module handles structural transformations that fundamentally differ from SQL:
1. FROM-first → SELECT-FROM transformation
2. Pipeline operators (|) removal
3. Aggregate blocks (group by x (...)) transformation
4. Stash as (CTEs) transformation
5. Natural aggregates (sum amount → sum(amount))
6. Underscore/space normalization for function calls
7. Window utilities (per command)
8. Date expressions (N days ago, date + N days, etc.)
9. Count shorthand (# → COUNT(*))
10. Order by -col (DESC indicator)
"""

import re
from typing import List, Optional, Tuple, Dict, Set
from dataclasses import dataclass


# Function registry for underscore/space normalization
FUNCTION_REGISTRY: Set[str] = {
    # Single-word aggregate functions
    'sum', 'avg', 'average', 'total', 'count', 'min', 'max',
    
    # Date truncation functions
    'year', 'month', 'week', 'day', 'hour', 'minute', 'second', 'quarter',
    
    # Multi-word date functions
    'day_of_week', 'day_of_month', 'day_of_year',
    'week_of_year', 'month_of_year', 'quarter_of_year',
    'week_monday', 'week_sunday',
    
    # Date difference functions
    'days', 'weeks', 'months', 'years', 'hours', 'minutes', 'seconds',
    'days_between', 'weeks_between', 'months_between', 'years_between',
    
    # String functions
    'upper', 'lower', 'length', 'trim', 'ltrim', 'rtrim',
    'concat', 'substring', 'replace', 'split', 'string_agg',
    
    # Math functions
    'abs', 'round', 'floor', 'ceil', 'ceiling', 'sqrt', 'power',
    
    # Other common functions
    'coalesce', 'nullif', 'cast',
    'date_trunc', 'date_add', 'date_diff', 'date_format',
    
    # Window functions
    'row_number', 'rank', 'dense_rank',
    'lag', 'lead', 'first_value', 'last_value',
    'running_sum', 'running_avg', 'running_count',
    'rolling_sum', 'rolling_avg',
    'prior', 'next',
    
    # Ordered aggregates
    'first', 'last', 'arg_max', 'arg_min',
}

# Function aliases
FUNCTION_ALIASES: Dict[str, str] = {
    'total': 'sum',
    'average': 'avg',
    'maximum': 'max',
    'minimum': 'min',
}

# Date units for arithmetic and relative dates
DATE_UNITS: Set[str] = {
    'day', 'days',
    'week', 'weeks', 
    'month', 'months',
    'year', 'years',
    'hour', 'hours',
    'minute', 'minutes',
    'second', 'seconds',
}


@dataclass
class PreParseResult:
    """Result of pre-parsing ASQL."""
    sql_like: str
    original: str
    ctes: List[Tuple[str, str]]  # (name, query) pairs for CTEs


class ASQLPreParser:
    """
    Pre-parse ASQL to SQLGlot-compatible syntax.
    
    Handles structural transformations that can't be done in SQLGlot's
    dialect extension model.
    """
    
    def __init__(self, text: str):
        self.text = text.strip()
        self.original = text
        self.pos = 0
        self.ctes: List[Tuple[str, str]] = []
    
    def preparse(self) -> str:
        """Apply all transformations and return SQL-like text."""
        result = self.text
        
        # Handle comments first - preserve them during transformation
        result, comments = self._extract_comments(result)
        
        # Apply transformations in order
        result = self._transform_set_statements(result)
        result = self._transform_pipeline(result)
        result = self._transform_stash_as(result)  # Early: split query at stash points before other transforms
        result = self._transform_count_shorthand(result)
        result = self._transform_order_desc_prefix(result)
        result = self._transform_natural_aggregates(result)
        result = self._transform_date_literals(result)
        result = self._transform_relative_dates(result)
        result = self._transform_date_arithmetic(result)
        result = self._transform_since_until_patterns(result)
        result = self._transform_per_commands(result)
        result = self._transform_aggregate_blocks(result)
        result = self._transform_multiple_where(result)  # Combine multiple WHERE clauses
        result = self._transform_from_first(result)
        result = self._transform_distinct_on(result)  # Move DISTINCT ON to after SELECT
        result = self._transform_window_functions(result)  # prior, next, running_*, rolling_*
        result = self._transform_qualify_clause(result)  # qualify rn == 1
        result = self._transform_coalesce_operator(result)  # After FROM-first for proper structure
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
    
    def _extract_comments(self, text: str) -> Tuple[str, List[Tuple[int, str]]]:
        """Extract comments and return text with placeholders."""
        comments: List[Tuple[int, str]] = []
        result = text
        
        # Extract single-line comments
        pattern = r'--[^\n]*'
        offset = 0
        for match in re.finditer(pattern, text):
            idx = len(comments)
            comment = match.group(0)
            placeholder = f"__COMMENT_{idx}__"
            comments.append((idx, comment))
            start = match.start() - offset
            end = match.end() - offset
            result = result[:start] + placeholder + result[end:]
            offset += len(comment) - len(placeholder)
        
        # Extract multi-line comments
        pattern = r'/\*[\s\S]*?\*/'
        offset = 0
        for match in re.finditer(pattern, result):
            idx = len(comments)
            comment = match.group(0)
            placeholder = f"__COMMENT_{idx}__"
            comments.append((idx, comment))
            start = match.start() - offset
            end = match.end() - offset
            result = result[:start] + placeholder + result[end:]
            offset += len(comment) - len(placeholder)
        
        return result, comments
    
    def _restore_comments(self, text: str, comments: List[Tuple[int, str]]) -> str:
        """Restore comments from placeholders."""
        result = text
        for idx, comment in comments:
            placeholder = f"__COMMENT_{idx}__"
            result = result.replace(placeholder, comment)
        return result
    
    def _transform_set_statements(self, text: str) -> str:
        """
        Handle SET statements for compile settings only.
        
        Compile settings (preserved for SQLGlot):
            SET auto_spine = true
            SET dialect = 'postgres'
            → preserved as-is (SQLGlot will parse them)
        
        NOTE: CTEs are ONLY created via "stash as" syntax, NOT via "set X = query"
        or "with X = query". This function only handles compile settings.
        """
        result = text.strip()
        preserved_sets: List[str] = []
        
        # Pattern: SET <setting_name> = <value>
        # Only matches known compile settings, not arbitrary identifiers
        known_settings = {'auto_spine', 'dialect', 'week_start', 'relative_date_type'}
        pattern = r'^\s*set\s+(\w+)\s*=\s*([^;]+?)(?:;|(?=\s*(?:set|from|select)\s)|\s*$)'
        
        while True:
            match = re.match(pattern, result, re.IGNORECASE)
            if not match:
                break
            
            name = match.group(1).lower()
            value = match.group(2).strip()
            
            # Only process known compile settings
            if name in known_settings:
                preserved_sets.append(f"SET {name} = {value}")
                result = result[match.end():].strip()
            else:
                # Unknown setting - stop processing (don't treat as CTE)
                break
        
        # Prepend preserved SET statements
        if preserved_sets:
            result = "; ".join(preserved_sets) + "; " + result
        
        return result
    
    def _transform_pipeline(self, text: str) -> str:
        """
        Remove pipeline operators, normalize to SQL clause order.
        
        from users | where active | order by -created_at | limit 10
        → from users where active order by created_at DESC limit 10
        """
        # Split on | (respecting strings and parentheses)
        segments = self._split_pipeline(text)
        if len(segments) == 1:
            return text
        
        # Reconstruct without |
        return " ".join(seg.strip() for seg in segments if seg.strip())
    
    def _split_pipeline(self, text: str) -> List[str]:
        """Split on | respecting strings and parentheses."""
        segments: List[str] = []
        current: List[str] = []
        depth = 0
        in_string: Optional[str] = None
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # String handling
            if char in ('"', "'") and (i == 0 or text[i-1] != '\\'):
                if in_string == char:
                    in_string = None
                elif in_string is None:
                    in_string = char
            
            # Parentheses
            if in_string is None:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                elif char == '|' and depth == 0:
                    segments.append(''.join(current))
                    current = []
                    i += 1
                    continue
            
            current.append(char)
            i += 1
        
        if current:
            segments.append(''.join(current))
        
        return segments
    
    def _transform_count_shorthand(self, text: str) -> str:
        """
        Transform # count shorthand to COUNT(*).
        
        # → COUNT(*)
        #(col) → COUNT(col)
        # of users → COUNT(*)
        """
        result = text
        
        # Pattern: # at word boundary (not inside identifier)
        # Transform standalone # to COUNT(*)
        # But be careful not to transform inside strings or comments
        
        # #(col) → COUNT(col)
        result = re.sub(r'#\s*\(\s*([^)]+)\s*\)', r'COUNT(\1)', result)
        
        # # of <identifier> → COUNT(*)
        result = re.sub(r'#\s+of\s+\w+', 'COUNT(*)', result)
        
        # Standalone # (not followed by identifier or opening paren that we already handled)
        # Must be careful with word boundaries
        result = re.sub(r'(?<![a-zA-Z0-9_])#(?!\s*\(|\s*of\s)', 'COUNT(*)', result)
        
        return result
    
    def _transform_coalesce_operator(self, text: str) -> str:
        """
        Transform ?? coalesce operator to COALESCE function.
        
        a ?? b → COALESCE(a, b)
        a ?? b ?? c → COALESCE(a, b, c)
        """
        result = text
        
        # Process ?? chains from right to left to handle nesting correctly
        # Pattern: simple_expr ?? simple_expr (where simple_expr is identifier, string, number, or function call)
        # Note: function calls can have nested parens, so we need to handle those
        
        # First, find all ?? occurrences and process them
        while '??' in result:
            # Find the rightmost ?? first (so inner coalesces are built first)
            pos = result.rfind('??')
            if pos == -1:
                break
            
            # Find the left expression
            # Go backward from ?? to find the start of the left operand
            left_end = pos
            while left_end > 0 and result[left_end - 1] in ' \t':
                left_end -= 1
            
            left_start = left_end - 1
            if left_start >= 0:
                # Handle parenthesized expressions
                if result[left_start] == ')':
                    # Find matching open paren
                    paren_depth = 1
                    left_start -= 1
                    while left_start >= 0 and paren_depth > 0:
                        if result[left_start] == ')':
                            paren_depth += 1
                        elif result[left_start] == '(':
                            paren_depth -= 1
                        left_start -= 1
                    left_start += 1
                    # Check for function name before the paren
                    if left_start > 0:
                        func_start = left_start - 1
                        while func_start >= 0 and result[func_start] in ' \t':
                            func_start -= 1
                        while func_start >= 0 and (result[func_start].isalnum() or result[func_start] == '_'):
                            func_start -= 1
                        if func_start >= 0:
                            left_start = func_start + 1
                # Handle string literals
                elif result[left_start] in '"\'':
                    quote = result[left_start]
                    left_start -= 1
                    while left_start >= 0 and result[left_start] != quote:
                        left_start -= 1
                # Handle identifiers and numbers
                else:
                    while left_start >= 0 and (result[left_start].isalnum() or result[left_start] in '_.:'):
                        left_start -= 1
                    left_start += 1
            else:
                left_start = 0
            
            left_expr = result[left_start:left_end].strip()
            
            # Find the right expression
            right_start = pos + 2
            while right_start < len(result) and result[right_start] in ' \t':
                right_start += 1
            
            right_end = right_start
            if right_end < len(result):
                # Handle string literals
                if result[right_end] in '"\'':
                    quote = result[right_end]
                    right_end += 1
                    while right_end < len(result) and result[right_end] != quote:
                        right_end += 1
                    if right_end < len(result):
                        right_end += 1
                # Handle identifiers, numbers, and function calls
                else:
                    while right_end < len(result) and (result[right_end].isalnum() or result[right_end] in '_.:'):
                        right_end += 1
                    # Check for function call
                    if right_end < len(result) and result[right_end] == '(':
                        paren_depth = 1
                        right_end += 1
                        while right_end < len(result) and paren_depth > 0:
                            if result[right_end] == '(':
                                paren_depth += 1
                            elif result[right_end] == ')':
                                paren_depth -= 1
                            right_end += 1
            
            right_expr = result[right_start:right_end].strip()
            
            if left_expr and right_expr:
                # Build COALESCE expression
                coalesce_expr = f"COALESCE({left_expr}, {right_expr})"
                
                # Replace in result
                result = result[:left_start] + coalesce_expr + result[right_end:]
            else:
                # Can't parse - break to avoid infinite loop
                break
        
        return result
    
    def _transform_order_desc_prefix(self, text: str) -> str:
        """
        Transform -column in ORDER BY to column DESC.
        
        order by -created_at → order by created_at DESC
        order by -amount, name → order by amount DESC, name
        
        Note: Only transforms ORDER BY clauses that are NOT inside parentheses
        (to avoid transforming ORDER BY inside OVER clauses).
        """
        result = text
        
        # Find all ORDER BY clauses and check if they're inside parentheses
        pattern = r'\border\s+by\s+'
        
        # Track parenthesis depth at each position
        paren_depth = 0
        paren_depths = []
        for char in result:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            paren_depths.append(paren_depth)
        
        # Find ORDER BY that is NOT inside parentheses
        for match in re.finditer(pattern, result, re.IGNORECASE):
            # Check if this ORDER BY is inside parentheses
            if paren_depths[match.start()] > 0:
                # Inside parens (e.g., OVER clause) - transform the -col there too
                # but only within the parenthesis
                continue
            
            start = match.end()
            
            # Find end of ORDER BY clause (before LIMIT, another clause, or end)
            remaining = result[start:]
            clause_end = len(remaining)
            for kw in ['limit', 'offset', 'having', 'union', 'except', 'intersect', 'qualify']:
                kw_match = re.search(rf'\b{kw}\b', remaining, re.IGNORECASE)
                if kw_match and kw_match.start() < clause_end:
                    clause_end = kw_match.start()
            
            order_clause = remaining[:clause_end]
            
            # Transform -col to col DESC
            def transform_col(col_match: re.Match) -> str:
                col = col_match.group(1)
                return f"{col} DESC"
            
            transformed = re.sub(r'-\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\s*\([^)]*\))?)', transform_col, order_clause)
            
            # Rebuild result
            result = result[:match.start()] + match.group(0) + transformed + remaining[clause_end:]
            
            # Only process one ORDER BY at the top level
            break
        
        # Now handle ORDER BY inside OVER clauses - transform -col to col DESC
        # Pattern: OVER (...ORDER BY -col...)
        def transform_over_order(match: re.Match) -> str:
            over_content = match.group(1)
            # Transform -col to col DESC inside the OVER clause
            transformed = re.sub(r'-\s*([a-zA-Z_][a-zA-Z0-9_]*)', r'\1 DESC', over_content)
            return f"OVER ({transformed})"
        
        result = re.sub(r'\bover\s*\(([^)]+)\)', transform_over_order, result, flags=re.IGNORECASE)
        
        return result
    
    def _transform_natural_aggregates(self, text: str) -> str:
        """
        Transform natural language aggregates to function calls.
        
        sum amount → sum(amount)
        sum of amount → sum(amount)
        avg of price → avg(price)
        """
        result = text
        
        # Pattern: func <column> or func of <column> (not followed by opening paren)
        for func in ['sum', 'avg', 'average', 'total', 'count', 'min', 'max']:
            # func of column → func(column)
            pattern = rf'\b({func})\s+of\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'
            result = re.sub(pattern, r'\1(\2)', result, flags=re.IGNORECASE)
            
            # func column → func(column) (but not func() or func(...)
            # Only if not already followed by (
            pattern = rf'\b({func})\s+([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\s*\()'
            
            def replace_if_not_keyword(m: re.Match) -> str:
                fn = m.group(1)
                arg = m.group(2)
                # Check if arg is a keyword
                keywords = {'as', 'from', 'where', 'group', 'by', 'order', 'limit', 'join', 'on', 'and', 'or', 'not', 'in', 'is', 'null', 'true', 'false'}
                if arg.lower() in keywords:
                    return m.group(0)
                return f'{fn}({arg})'
            
            result = re.sub(pattern, replace_if_not_keyword, result, flags=re.IGNORECASE)
        
        return result
    
    def _transform_date_literals(self, text: str) -> str:
        """
        Transform @YYYY-MM-DD date literals to SQL DATE literals.
        
        @2024-01-15 → DATE '2024-01-15'
        @2024-01-15T10:30:00 → TIMESTAMP '2024-01-15 10:30:00'
        """
        result = text
        
        # Date with time: @YYYY-MM-DDTHH:MM:SS → TIMESTAMP '...'
        pattern = r'@(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})'
        result = re.sub(pattern, r"TIMESTAMP '\1 \2'", result)
        
        # Date only: @YYYY-MM-DD → DATE '...'
        pattern = r'@(\d{4}-\d{2}-\d{2})'
        result = re.sub(pattern, r"DATE '\1'", result)
        
        return result
    
    def _transform_relative_dates(self, text: str) -> str:
        """
        Transform relative date expressions.
        
        7 days ago → CURRENT_DATE - INTERVAL '7 days'
        1 month ago → CURRENT_DATE - INTERVAL '1 month'
        3 days from now → CURRENT_DATE + INTERVAL '3 days'
        """
        result = text
        
        # N unit ago → CURRENT_DATE - INTERVAL 'N unit'
        pattern = r'\b(\d+)\s+(day|days|week|weeks|month|months|year|years|hour|hours|minute|minutes|second|seconds)\s+ago\b'
        result = re.sub(pattern, r"CURRENT_TIMESTAMP - INTERVAL '\1 \2'", result, flags=re.IGNORECASE)
        
        # N unit from now → CURRENT_DATE + INTERVAL 'N unit'
        pattern = r'\b(\d+)\s+(day|days|week|weeks|month|months|year|years|hour|hours|minute|minutes|second|seconds)\s+from\s+now\b'
        result = re.sub(pattern, r"CURRENT_TIMESTAMP + INTERVAL '\1 \2'", result, flags=re.IGNORECASE)
        
        return result
    
    def _transform_date_arithmetic(self, text: str) -> str:
        """
        Transform inline date arithmetic.
        
        order_date + 7 days → order_date + INTERVAL '7 days'
        created_at - 1 month → created_at - INTERVAL '1 month'
        """
        result = text
        
        # col + N unit → col + INTERVAL 'N unit'
        # col - N unit → col - INTERVAL 'N unit'
        # Be careful not to match "N days ago" which is handled separately
        pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*([+-])\s*(\d+)\s+(day|days|week|weeks|month|months|year|years|hour|hours|minute|minutes|second|seconds)\b(?!\s+(?:ago|from))'
        result = re.sub(pattern, r"\1 \2 INTERVAL '\3 \4'", result, flags=re.IGNORECASE)
        
        return result
    
    def _transform_since_until_patterns(self, text: str) -> str:
        """
        Transform *_since_* and *_until_* patterns.
        
        days_since_created_at → EXTRACT(DAY FROM CURRENT_TIMESTAMP - created_at)
        days_until_due_date → EXTRACT(DAY FROM due_date - CURRENT_TIMESTAMP)
        """
        result = text
        
        # days_since_col → (CURRENT_TIMESTAMP - col) (simplified, actual diff depends on dialect)
        units = ['days', 'weeks', 'months', 'years', 'hours', 'minutes', 'seconds']
        for unit in units:
            # Singular form too
            singular = unit[:-1] if unit.endswith('s') else unit
            
            # unit_since_col pattern
            pattern = rf'\b{unit}_since_([a-zA-Z_][a-zA-Z0-9_]*)\b'
            result = re.sub(pattern, rf"DATEDIFF('{singular}', \1, CURRENT_TIMESTAMP)", result, flags=re.IGNORECASE)
            
            pattern = rf'\b{singular}_since_([a-zA-Z_][a-zA-Z0-9_]*)\b'
            result = re.sub(pattern, rf"DATEDIFF('{singular}', \1, CURRENT_TIMESTAMP)", result, flags=re.IGNORECASE)
            
            # unit_until_col pattern
            pattern = rf'\b{unit}_until_([a-zA-Z_][a-zA-Z0-9_]*)\b'
            result = re.sub(pattern, rf"DATEDIFF('{singular}', CURRENT_TIMESTAMP, \1)", result, flags=re.IGNORECASE)
            
            pattern = rf'\b{singular}_until_([a-zA-Z_][a-zA-Z0-9_]*)\b'
            result = re.sub(pattern, rf"DATEDIFF('{singular}', CURRENT_TIMESTAMP, \1)", result, flags=re.IGNORECASE)
        
        return result
    
    def _transform_per_commands(self, text: str) -> str:
        """
        Transform PER command to window function syntax.
        
        per customer_id first by -order_date →
            ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) = 1
            (wrapped in subquery with QUALIFY or WHERE filter)
        
        per department number by -salary as rank_num →
            ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS rank_num
        """
        result = text
        
        # Pattern: per <partition_cols> <op> by <order_cols> [as <alias>]
        # Operations: first, last, number, rank, dense rank / dense_rank
        
        # For now, handle the most common case: per ... first/last by ...
        # This requires wrapping in a subquery which is complex
        # We'll transform to a simpler representation that the dialect parser can handle
        
        # per col first by -order → with window function and filter
        pattern = r'\bper\s+([a-zA-Z_][a-zA-Z0-9_,\s]*)\s+(first|last)\s+by\s+(-?)([a-zA-Z_][a-zA-Z0-9_]*)'
        
        def transform_per_first_last(match: re.Match) -> str:
            partition = match.group(1).strip()
            op = match.group(2).lower()
            desc_prefix = match.group(3)
            order_col = match.group(4)
            
            # Determine order direction
            order_dir = "DESC" if desc_prefix else "ASC"
            if op == "last":
                # Reverse order for last
                order_dir = "ASC" if desc_prefix else "DESC"
            
            # Generate window function with qualify
            # This will be: QUALIFY ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...) = 1
            return f"QUALIFY ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {order_col} {order_dir}) = 1"
        
        result = re.sub(pattern, transform_per_first_last, result, flags=re.IGNORECASE)
        
        # per col dense rank by ... [as alias] → DENSE_RANK() - check for "dense rank" FIRST
        pattern = r'\bper\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)*)\s+dense\s+rank\s+by\s+(-?)([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*))?'
        
        def transform_per_dense_rank(match: re.Match) -> str:
            partition = match.group(1).strip()
            desc_prefix = match.group(2)
            order_col = match.group(3)
            alias = match.group(4) or 'dense_rank'
            
            order_dir = "DESC" if desc_prefix else "ASC"
            return f", DENSE_RANK() OVER (PARTITION BY {partition} ORDER BY {order_col} {order_dir}) AS {alias}"
        
        result = re.sub(pattern, transform_per_dense_rank, result, flags=re.IGNORECASE)
        
        # per col number/rank by ... [as alias] → adds window function column
        pattern = r'\bper\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)*)\s+(number|rank|dense_rank)\s+by\s+(-?)([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*))?'
        
        def transform_per_number(match: re.Match) -> str:
            partition = match.group(1).strip()
            op = match.group(2).lower().replace(' ', '_')
            desc_prefix = match.group(3)
            order_col = match.group(4)
            alias = match.group(5)
            
            order_dir = "DESC" if desc_prefix else "ASC"
            
            # Map operation to window function
            func_map = {
                'number': 'ROW_NUMBER',
                'rank': 'RANK',
                'dense_rank': 'DENSE_RANK',
            }
            func = func_map.get(op, 'ROW_NUMBER')
            
            # Default alias
            if not alias:
                alias = 'row_num' if op == 'number' else op
            
            return f", {func}() OVER (PARTITION BY {partition} ORDER BY {order_col} {order_dir}) AS {alias}"
        
        result = re.sub(pattern, transform_per_number, result, flags=re.IGNORECASE)
        
        # Standalone: number by ... [as alias] (no partition)
        pattern = r'\bnumber\s+by\s+(-?)([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*))?'
        
        def transform_standalone_number(match: re.Match) -> str:
            desc_prefix = match.group(1)
            order_col = match.group(2)
            alias = match.group(3) or 'row_num'
            
            order_dir = "DESC" if desc_prefix else "ASC"
            return f", ROW_NUMBER() OVER (ORDER BY {order_col} {order_dir}) AS {alias}"
        
        result = re.sub(pattern, transform_standalone_number, result, flags=re.IGNORECASE)
        
        # Standalone: dense rank by ... [as alias] (no partition) - MUST COME BEFORE "rank by"
        pattern = r'\bdense\s+rank\s+by\s+(-?)([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*))?'
        
        def transform_standalone_dense_rank(match: re.Match) -> str:
            desc_prefix = match.group(1)
            order_col = match.group(2)
            alias = match.group(3) or 'dense_rank'
            
            order_dir = "DESC" if desc_prefix else "ASC"
            return f", DENSE_RANK() OVER (ORDER BY {order_col} {order_dir}) AS {alias}"
        
        result = re.sub(pattern, transform_standalone_dense_rank, result, flags=re.IGNORECASE)
        
        # Standalone: rank by ... [as alias] (no partition) - AFTER dense rank
        pattern = r'\brank\s+by\s+(-?)([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*))?'
        
        def transform_standalone_rank(match: re.Match) -> str:
            desc_prefix = match.group(1)
            order_col = match.group(2)
            alias = match.group(3) or 'rank'
            
            order_dir = "DESC" if desc_prefix else "ASC"
            return f", RANK() OVER (ORDER BY {order_col} {order_dir}) AS {alias}"
        
        result = re.sub(pattern, transform_standalone_rank, result, flags=re.IGNORECASE)
        
        # first(col order by expr) → FIRST_VALUE(col) OVER (ORDER BY expr ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
        pattern = r'\bfirst\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+order\s+by\s+(-?)([a-zA-Z_][a-zA-Z0-9_]*)\s*\)'
        
        def transform_first(match: re.Match) -> str:
            col = match.group(1)
            desc_prefix = match.group(2)
            order_col = match.group(3)
            order_dir = "DESC" if desc_prefix else "ASC"
            return f"FIRST_VALUE({col}) OVER (ORDER BY {order_col} {order_dir} ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)"
        
        result = re.sub(pattern, transform_first, result, flags=re.IGNORECASE)
        
        # last(col order by expr) → FIRST_VALUE(col) OVER (ORDER BY expr DESC/ASC ROWS ...)
        pattern = r'\blast\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+order\s+by\s+(-?)([a-zA-Z_][a-zA-Z0-9_]*)\s*\)'
        
        def transform_last(match: re.Match) -> str:
            col = match.group(1)
            desc_prefix = match.group(2)
            order_col = match.group(3)
            # Reverse the order for last
            order_dir = "ASC" if desc_prefix else "DESC"
            return f"FIRST_VALUE({col}) OVER (ORDER BY {order_col} {order_dir} ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)"
        
        result = re.sub(pattern, transform_last, result, flags=re.IGNORECASE)
        
        # arg_max(return_col, value_col) → value at max - complex window function
        # Simplified: becomes FIRST_VALUE with ORDER BY value_col DESC
        pattern = r'\barg_max\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*,\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)'
        
        def transform_arg_max(match: re.Match) -> str:
            return_col = match.group(1)
            value_col = match.group(2)
            return f"FIRST_VALUE({return_col}) OVER (ORDER BY {value_col} DESC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)"
        
        result = re.sub(pattern, transform_arg_max, result, flags=re.IGNORECASE)
        
        # arg_min(return_col, value_col) → value at min
        pattern = r'\barg_min\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*,\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)'
        
        def transform_arg_min(match: re.Match) -> str:
            return_col = match.group(1)
            value_col = match.group(2)
            return f"FIRST_VALUE({return_col}) OVER (ORDER BY {value_col} ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)"
        
        result = re.sub(pattern, transform_arg_min, result, flags=re.IGNORECASE)
        
        return result
    
    def _transform_aggregate_blocks(self, text: str) -> str:
        """
        Transform ASQL aggregate blocks to SQL SELECT + GROUP BY.
        
        from sales group by region (sum(amount) as revenue, count(*) as cnt)
        →
        SELECT region, SUM(amount) AS revenue, COUNT(*) AS cnt FROM sales GROUP BY region
        """
        result = text
        
        # Find "group by" followed by columns and then an aggregate block in parens
        # Need to handle nested parentheses in aggregate functions
        pattern = r'\bgroup\s+by\s+'
        match = re.search(pattern, result, re.IGNORECASE)
        
        if not match:
            return result
        
        start = match.end()
        
        # Find the opening paren of the aggregate block
        # Need to skip over any function calls in the group by expression
        # Function call pattern: identifier(...) - NO space between identifier and paren
        paren_pos = -1
        i = start
        while i < len(result):
            if result[i] == '(':
                # Check if this is a function call or the aggregate block
                # A function call has an identifier DIRECTLY before it (no space)
                j = i - 1
                if j >= start and (result[j].isalnum() or result[j] == '_'):
                    # This is a function call (no space before paren) - skip its content
                    depth = 1
                    i += 1
                    while i < len(result) and depth > 0:
                        if result[i] == '(':
                            depth += 1
                        elif result[i] == ')':
                            depth -= 1
                        i += 1
                    continue
                else:
                    # This is the aggregate block (space before paren or other char)
                    paren_pos = i
                    break
            elif result[i] in '\n;':
                # No aggregate block on this line
                return result
            i += 1
        
        if paren_pos == -1:
            return result
        
        # Extract group columns (between "group by" and the paren)
        group_cols = result[start:paren_pos].strip()
        
        # Find matching closing paren (handling nested parens)
        depth = 1
        i = paren_pos + 1
        while i < len(result) and depth > 0:
            if result[i] == '(':
                depth += 1
            elif result[i] == ')':
                depth -= 1
            i += 1
        
        if depth != 0:
            return result  # Unmatched parens
        
        # Extract aggregate block content (between outer parens)
        aggs_text = result[paren_pos + 1:i - 1].strip()
        
        # Find what comes after the aggregate block
        after_block = result[i:].strip()
        
        # If there's a 'select' clause after the aggregate block, remove it
        # (the aggregate block already specifies what to SELECT)
        select_after_pattern = r'^\s*select\s+[^(]+?(?=\s+(?:stash|order|limit|$)|\s*$)'
        after_match = re.match(select_after_pattern, after_block, re.IGNORECASE)
        if after_match:
            after_block = after_block[after_match.end():].strip()
        
        # Build the transformed query
        # Format: SELECT group_cols, aggs FROM ... GROUP BY group_cols [ORDER BY ...]
        before_group = result[:match.start()].strip()
        
        # Build SELECT clause
        select_clause = f"SELECT {group_cols}, {aggs_text}"
        
        # Build GROUP BY clause
        group_clause = f"GROUP BY {group_cols}"
        
        # Combine: SELECT ... FROM ... GROUP BY ... [remaining clauses]
        result = f"{select_clause} {before_group} {group_clause} {after_block}"
        
        return result
    
    def _transform_stash_as(self, text: str) -> str:
        """
        Transform stash as <name> to CTE.
        
        from users where active stash as active_users
        →
        WITH active_users AS (SELECT * FROM users WHERE active) SELECT * FROM active_users
        
        Also handles stash as in the middle of a query:
        from users where active stash as active_users group by country
        →
        WITH active_users AS (SELECT * FROM users WHERE active) 
        SELECT * FROM active_users GROUP BY country
        """
        result = text
        
        # Pattern: ... stash as <name> [continuation]
        # The continuation can be more query operations
        pattern = r'(.+?)\s+stash\s+as\s+(\w+)(?:\s+(.+?))?$'
        match = re.match(pattern, result.strip(), re.IGNORECASE | re.DOTALL)
        
        if match:
            query_part = match.group(1).strip()
            cte_name = match.group(2)
            continuation = match.group(3).strip() if match.group(3) else None
            
            # Recursively preparse the query part
            sub_parser = ASQLPreParser(query_part)
            parsed_query = sub_parser.preparse()
            
            # Add to CTEs
            self.ctes.append((cte_name, parsed_query))
            
            if continuation:
                # There's more query after the stash - run it on the CTE
                continuation_query = f"from {cte_name} {continuation}"
                # Recursively preparse the continuation
                cont_parser = ASQLPreParser(continuation_query)
                result = cont_parser.preparse()
                # Merge CTEs from continuation
                self.ctes.extend(cont_parser.ctes)
            else:
                # No continuation - just select from the CTE
                result = f"SELECT * FROM {cte_name}"
        
        return result
    
    def _transform_multiple_where(self, text: str) -> str:
        """
        Combine multiple WHERE clauses into a single WHERE with AND.
        
        from users where status == "active" where age >= 18
        → from users where status == "active" AND age >= 18
        """
        result = text
        
        # Find all WHERE clauses and combine them
        # Pattern: where <condition1> where <condition2>
        while True:
            # Find two consecutive WHERE clauses
            pattern = r'\bwhere\s+(.+?)\s+where\s+'
            match = re.search(pattern, result, re.IGNORECASE)
            if not match:
                break
            
            first_condition = match.group(1).strip()
            # Replace "where X where Y" with "where X AND Y"
            result = result[:match.start()] + f"where {first_condition} AND " + result[match.end():]
        
        return result
    
    def _transform_from_first(self, text: str) -> str:
        """
        Add SELECT * if needed for FROM-first queries.
        
        from users where active limit 10
        → SELECT * FROM users WHERE active LIMIT 10
        """
        result = text.strip()
        
        # Check if query starts with FROM (not SELECT, WITH, etc.)
        if not re.match(r'^\s*(select|with|insert|update|delete|create|alter|drop)\b', result, re.IGNORECASE):
            if re.match(r'^\s*from\b', result, re.IGNORECASE):
                # Check if SELECT appears later (for "from x select y" syntax)
                select_match = re.search(r'\bselect\s+', result, re.IGNORECASE)
                if select_match:
                    # Find the extent of the SELECT clause
                    # We need to find where the SELECT clause ends, which is at
                    # a keyword like WHERE, GROUP BY, LIMIT, QUALIFY, etc.
                    # But we need to skip keywords inside parentheses (like in OVER clauses)
                    select_start = select_match.end()
                    select_end = len(result)
                    
                    paren_depth = 0
                    i = select_start
                    while i < len(result):
                        char = result[i]
                        if char == '(':
                            paren_depth += 1
                        elif char == ')':
                            paren_depth -= 1
                        elif paren_depth == 0:
                            # Check for clause keywords at this position
                            remaining = result[i:].lower()
                            for kw in ['where ', 'group by ', 'order by ', 'limit ', 'having ', 'qualify ']:
                                if remaining.startswith(kw):
                                    select_end = i
                                    break
                            if select_end != len(result):
                                break
                        i += 1
                    
                    select_clause = result[select_start:select_end].strip()
                    before_select = result[:select_match.start()]
                    after_select = result[select_end:]
                    result = f"SELECT {select_clause} {before_select}{after_select}"
                else:
                    # Add SELECT * at front
                    result = "SELECT * " + result
        
        return result
    
    def _transform_distinct_on(self, text: str) -> str:
        """
        Transform ASQL distinct on (cols) to SQL DISTINCT ON.
        
        The distinct on clause should be moved to after SELECT.
        """
        result = text
        
        # Pattern: distinct on (cols) anywhere in query
        pattern = r'\bdistinct\s+on\s*\(([^)]+)\)'
        match = re.search(pattern, result, re.IGNORECASE)
        
        if match:
            cols = match.group(1).strip()
            # Remove distinct on from its current position
            before = result[:match.start()]
            after = result[match.end():]
            result = before.strip() + " " + after.strip()
            
            # Add DISTINCT ON after SELECT
            result = re.sub(r'\bSELECT\s+', f'SELECT DISTINCT ON ({cols}) ', result, count=1, flags=re.IGNORECASE)
        
        return result
    
    def _transform_window_functions(self, text: str) -> str:
        """
        Transform ASQL window functions to SQL window functions.
        
        prior(col) → LAG(col, 1) OVER (ORDER BY ...)
        prior(col, n) → LAG(col, n) OVER (ORDER BY ...)
        next(col) → LEAD(col, 1) OVER (ORDER BY ...)
        next(col, n) → LEAD(col, n) OVER (ORDER BY ...)
        running_sum(col) → SUM(col) OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)
        running_avg(col) → AVG(col) OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)
        running_count(*) → COUNT(*) OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)
        rolling_avg(col, n) → AVG(col) OVER (ORDER BY ... ROWS BETWEEN n-1 PRECEDING AND CURRENT ROW)
        rolling_sum(col, n) → SUM(col) OVER (ORDER BY ... ROWS BETWEEN n-1 PRECEDING AND CURRENT ROW)
        """
        result = text
        
        # Extract ORDER BY clause for window frame
        order_match = re.search(r'\bORDER\s+BY\s+([^,\s]+(?:\s+(?:ASC|DESC))?)', result, re.IGNORECASE)
        order_clause = order_match.group(0) if order_match else 'ORDER BY 1'
        
        # Transform prior(col) and prior(col, n) to LAG
        def replace_prior(match: re.Match) -> str:
            args = match.group(1).strip()
            if ',' in args:
                col, offset = [a.strip() for a in args.split(',', 1)]
                return f"LAG({col}, {offset}) OVER ({order_clause})"
            else:
                return f"LAG({args}, 1) OVER ({order_clause})"
        
        result = re.sub(r'\bprior\s*\(\s*([^)]+)\s*\)', replace_prior, result, flags=re.IGNORECASE)
        
        # Transform next(col) and next(col, n) to LEAD
        def replace_next(match: re.Match) -> str:
            args = match.group(1).strip()
            if ',' in args:
                col, offset = [a.strip() for a in args.split(',', 1)]
                return f"LEAD({col}, {offset}) OVER ({order_clause})"
            else:
                return f"LEAD({args}, 1) OVER ({order_clause})"
        
        result = re.sub(r'\bnext\s*\(\s*([^)]+)\s*\)', replace_next, result, flags=re.IGNORECASE)
        
        # Transform running_sum(col) to SUM with window frame
        def replace_running_sum(match: re.Match) -> str:
            col = match.group(1).strip()
            return f"SUM({col}) OVER ({order_clause} ROWS UNBOUNDED PRECEDING)"
        
        result = re.sub(r'\brunning_sum\s*\(\s*([^)]+)\s*\)', replace_running_sum, result, flags=re.IGNORECASE)
        
        # Transform running_avg(col) to AVG with window frame
        def replace_running_avg(match: re.Match) -> str:
            col = match.group(1).strip()
            return f"AVG({col}) OVER ({order_clause} ROWS UNBOUNDED PRECEDING)"
        
        result = re.sub(r'\brunning_avg\s*\(\s*([^)]+)\s*\)', replace_running_avg, result, flags=re.IGNORECASE)
        
        # Transform running_count(*) to COUNT with window frame
        def replace_running_count(match: re.Match) -> str:
            col = match.group(1).strip()
            return f"COUNT({col}) OVER ({order_clause} ROWS UNBOUNDED PRECEDING)"
        
        result = re.sub(r'\brunning_count\s*\(\s*([^)]+)\s*\)', replace_running_count, result, flags=re.IGNORECASE)
        
        # Transform rolling_avg(col, n) to AVG with window frame
        def replace_rolling_avg(match: re.Match) -> str:
            args = match.group(1).strip()
            if ',' in args:
                col, window = [a.strip() for a in args.split(',', 1)]
                try:
                    window_size = int(window) - 1
                except ValueError:
                    window_size = f"{window} - 1"
                return f"AVG({col}) OVER ({order_clause} ROWS BETWEEN {window_size} PRECEDING AND CURRENT ROW)"
            else:
                return f"AVG({args}) OVER ({order_clause} ROWS UNBOUNDED PRECEDING)"
        
        result = re.sub(r'\brolling_avg\s*\(\s*([^)]+)\s*\)', replace_rolling_avg, result, flags=re.IGNORECASE)
        
        # Transform rolling_sum(col, n) to SUM with window frame
        def replace_rolling_sum(match: re.Match) -> str:
            args = match.group(1).strip()
            if ',' in args:
                col, window = [a.strip() for a in args.split(',', 1)]
                try:
                    window_size = int(window) - 1
                except ValueError:
                    window_size = f"{window} - 1"
                return f"SUM({col}) OVER ({order_clause} ROWS BETWEEN {window_size} PRECEDING AND CURRENT ROW)"
            else:
                return f"SUM({args}) OVER ({order_clause} ROWS UNBOUNDED PRECEDING)"
        
        result = re.sub(r'\brolling_sum\s*\(\s*([^)]+)\s*\)', replace_rolling_sum, result, flags=re.IGNORECASE)
        
        return result
    
    def _transform_qualify_clause(self, text: str) -> str:
        """
        Transform ASQL qualify clause to SQL QUALIFY or subquery.
        
        qualify rn == 1 → QUALIFY rn = 1
        """
        result = text
        
        # Transform qualify keyword to QUALIFY (SQL standard for some dialects)
        # Just uppercase it and fix the equality operator
        result = re.sub(r'\bqualify\s+', 'QUALIFY ', result, flags=re.IGNORECASE)
        
        return result
    
    def _normalize_function_spaces(self, text: str) -> str:
        """
        Normalize function names with spaces to underscores.
        
        day of week created_at → day_of_week(created_at)
        row number() → row_number()
        """
        result = text
        
        # Multi-word function patterns
        multi_word_funcs = [
            ('day of week', 'day_of_week'),
            ('day of month', 'day_of_month'),
            ('day of year', 'day_of_year'),
            ('week of year', 'week_of_year'),
            ('month of year', 'month_of_year'),
            ('quarter of year', 'quarter_of_year'),
            ('row number', 'row_number'),
            ('dense rank', 'dense_rank'),
            ('running sum', 'running_sum'),
            ('running avg', 'running_avg'),
            ('running count', 'running_count'),
            ('rolling sum', 'rolling_sum'),
            ('rolling avg', 'rolling_avg'),
            ('arg max', 'arg_max'),
            ('arg min', 'arg_min'),
            ('first value', 'first_value'),
            ('last value', 'last_value'),
            ('date trunc', 'date_trunc'),
            ('date add', 'date_add'),
            ('date diff', 'date_diff'),
            ('string agg', 'string_agg'),
            ('array agg', 'array_agg'),
        ]
        
        for spaced, underscored in multi_word_funcs:
            # Replace "func name(..." with "func_name(..."
            pattern = rf'\b{spaced}\s*\('
            result = re.sub(pattern, f'{underscored}(', result, flags=re.IGNORECASE)
            
            # Replace "func name column" with "func_name(column)" (shorthand)
            pattern = rf'\b{spaced}\s+([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\s*\()'
            result = re.sub(pattern, rf'{underscored}(\1)', result, flags=re.IGNORECASE)
        
        return result
    
    def _transform_equality_operators(self, text: str) -> str:
        """
        Transform == to = for SQL compatibility.
        
        ASQL accepts both = and == for equality, but SQL only uses =.
        """
        result = text
        
        # Replace == with = (but not !== or ===)
        result = re.sub(r'(?<![=!])={2}(?!=)', '=', result)
        
        return result


def preparse_asql(text: str) -> str:
    """
    Pre-parse ASQL text to SQL-like text for SQLGlot parsing.
    
    This is the main entry point for the pre-parser.
    
    Args:
        text: ASQL query string
        
    Returns:
        SQL-like string ready for SQLGlot parsing
    """
    parser = ASQLPreParser(text)
    return parser.preparse()
