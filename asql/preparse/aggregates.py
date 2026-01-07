"""Pre-parser transforms: aggregates."""

from __future__ import annotations

import re

from asql.preparse.registry import FUNCTION_ALIASES

class AggregatesMixin:

    def _convert_inline_comments_to_block(self, text: str) -> str:
        """Convert -- inline comments to /* */ block comments.
        
        This prevents inline comments from eating subsequent SQL when
        the query is reassembled onto fewer lines.
        
        Example:
            "sum(x) as total, -- comment\ncount(*)"
            → "sum(x) as total, /* comment */\ncount(*)"
        """
        # Pattern: -- followed by text until end of line (but not inside strings)
        # Simple approach: replace -- ... \n with /* ... */\n
        # and -- ... $ (end of string) with /* ... */
        
        result = []
        i = 0
        in_string = None
        
        while i < len(text):
            char = text[i]
            
            # Track string boundaries
            if char in ('"', "'") and (i == 0 or text[i-1] != '\\'):
                if in_string == char:
                    in_string = None
                elif in_string is None:
                    in_string = char
                result.append(char)
                i += 1
                continue
            
            # Check for -- comment start (outside strings)
            if in_string is None and i + 1 < len(text) and text[i:i+2] == '--':
                # Find end of comment (newline or end of string)
                comment_start = i + 2
                j = comment_start
                while j < len(text) and text[j] != '\n':
                    j += 1
                
                # Extract comment content and convert to block style
                comment_content = text[comment_start:j].strip()
                if comment_content:
                    result.append(f'/* {comment_content} */')
                
                # Skip past the comment (but keep the newline if present)
                if j < len(text) and text[j] == '\n':
                    result.append('\n')
                    i = j + 1
                else:
                    i = j
                continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)

    def _transform_natural_aggregates(self, text: str) -> str:
        """
        Transform natural language function calls to explicit function calls.
        
        Supports both aggregates and date functions:
        - sum amount → sum(amount)
        - sum of amount → sum(amount)
        - year created_at → year(created_at)
        - month created_at → month(created_at)
        """
        result = text
        
        # Aggregate functions (plus natural-language aliases like total/average).
        funcs = [
            'sum', 'avg', 'average', 'total', 'count', 'min', 'max', 'maximum', 'minimum',
        ]
        
        # Pattern: func <column> or func of <column> (not followed by opening paren)
        for func in funcs:
            def normalize_fn(raw_fn: str) -> str:
                lowered = raw_fn.lower()
                return FUNCTION_ALIASES.get(lowered, lowered)

            # func of column → func(column)
            pattern = rf'\b({func})\s+of\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'

            def replace_of(match: re.Match) -> str:
                fn = normalize_fn(match.group(1))
                arg = match.group(2)
                return f"{fn}({arg})"

            result = re.sub(pattern, replace_of, result, flags=re.IGNORECASE)

            # func column → func(column) (but not func() or func(...)
            # Only if not already followed by (
            pattern = rf'\b({func})\s+([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\s*\()'

            def replace_if_not_keyword(m: re.Match) -> str:
                fn_raw = m.group(1)
                fn = normalize_fn(fn_raw)
                arg = m.group(2)
                # Check if arg is a keyword
                keywords = {'as', 'from', 'where', 'group', 'by', 'order', 'limit', 'join', 'on', 'and', 'or', 'not', 'in', 'is', 'null', 'true', 'false'}
                if arg.lower() in keywords:
                    return m.group(0)
                return f'{fn}({arg})'

            result = re.sub(pattern, replace_if_not_keyword, result, flags=re.IGNORECASE)
        
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
        
        # Convert inline -- comments to /* */ style to prevent them from
        # eating the FROM/GROUP BY clauses when we reassemble the query.
        # Pattern: -- comment text (to end of line or end of string)
        aggs_text = self._convert_inline_comments_to_block(aggs_text)
        
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
        
        # Extract comment placeholders from before_group to preserve them at the start
        comment_prefix_pattern = r'^(\s*(?:__COMMENT_\d+__\s*)*)'
        comment_match = re.match(comment_prefix_pattern, before_group)
        comment_prefix = comment_match.group(1) if comment_match else ''
        before_group_no_comments = before_group[len(comment_prefix):].strip() if comment_prefix else before_group
        
        # Build SELECT clause
        select_clause = f"SELECT {group_cols}, {aggs_text}"
        
        # Build GROUP BY clause
        group_clause = f"GROUP BY {group_cols}"
        
        # Combine: [comments] SELECT ... FROM ... GROUP BY ... [remaining clauses]
        result = f"{comment_prefix}{select_clause} {before_group_no_comments} {group_clause} {after_block}"
        
        return result
