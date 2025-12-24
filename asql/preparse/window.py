"""Pre-parser transforms: window."""

from __future__ import annotations

import re
from typing import Optional

from asql.errors import ASQLSyntaxError

class WindowMixin:

    def _transform_deduplicate_by(self, text: str) -> str:
        """
        Transform deduplicate by to per ... first by syntax.
        
        deduplicate by user_id, event_type order by -created_at →
            per user_id, event_type first by -created_at
        
        deduplicate by user_id, event_type
          order by -created_at →
            per user_id, event_type first by -created_at
        
        This is syntax sugar for the per ... first by pattern.
        """
        # Use a line-oriented transform (much less brittle than complex regexes).
        lines = text.splitlines(keepends=True)

        i = 0
        while i < len(lines):
            line = lines[i]
            match = re.match(r"^(\s*)deduplicate\s+by\s+(.+?)\s*$", line, re.IGNORECASE)
            if not match:
                i += 1
                continue

            indent = match.group(1)
            rest = match.group(2).strip()

            partition_cols: str
            order_cols: Optional[str] = None

            # Inline: "deduplicate by <cols> order by <order>"
            split = re.split(r"\border\s+by\b", rest, maxsplit=1, flags=re.IGNORECASE)
            if len(split) == 2:
                partition_cols = split[0].strip().rstrip(",")
                order_cols = split[1].strip()
            else:
                partition_cols = rest.rstrip(",")
                # Next-line order by
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                if j < len(lines):
                    order_match = re.match(r"^\s*order\s+by\s+(.+?)\s*$", lines[j], re.IGNORECASE)
                    if order_match:
                        order_cols = order_match.group(1).strip()
                        lines[j] = ""  # remove the order by line

            if not order_cols:
                raise ASQLSyntaxError(
                    "deduplicate by requires an order by clause. "
                    f"Use: deduplicate by {partition_cols} order by <column>"
                )

            lines[i] = f"{indent}per {partition_cols} first by {order_cols}\n"
            i += 1

        return "".join(lines)

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
