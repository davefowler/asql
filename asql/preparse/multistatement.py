"""Pre-parser transforms: multi-statement query handling."""

from __future__ import annotations

import re
from typing import List


class MultiStatementMixin:
    """Mixin for handling multi-statement ASQL queries (stash-based CTEs)."""

    def _transform_multi_statements(self, text: str) -> str:
        """
        Handle multi-statement queries where earlier statements define CTEs
        via 'stash as' and later statements reference them.
        
        Example:
            from users where status = 'active' stash as active_users
            
            from orders where status = 'completed' stash as user_orders
            
            from active_users
              &? user_orders on active_users.id = user_orders.user_id
        
        Becomes:
            WITH active_users AS (...), user_orders AS (...)
            SELECT * FROM active_users LEFT JOIN user_orders ...
        """
        # Split text into statements separated by blank lines followed by 'from'
        # But only when there's a 'stash as' in the first part
        
        statements = self._split_statements(text)
        
        if len(statements) <= 1:
            return text
        
        # Check if we have stash-based multi-statement pattern
        stash_pattern = r'\bstash\s+as\s+\w+\s*$'
        has_stash_statements = False
        
        for stmt in statements[:-1]:  # All but the last statement
            if re.search(stash_pattern, stmt.strip(), re.IGNORECASE):
                has_stash_statements = True
                break
        
        if not has_stash_statements:
            return text
        
        # Process each statement that ends with 'stash as', collect CTEs
        collected_ctes = []
        
        for stmt in statements[:-1]:
            if re.search(stash_pattern, stmt.strip(), re.IGNORECASE):
                # Strip any comment markers from the statement before processing
                clean_stmt = re.sub(r'__COMMENT_\d+__\s*', '', stmt.strip())
                
                # Extract CTE name and query from "... stash as name"
                stash_match = re.search(r'(.+?)\s+stash\s+as\s+(\w+)\s*$', clean_stmt, re.IGNORECASE | re.DOTALL)
                if stash_match:
                    query_part = stash_match.group(1).strip()
                    cte_name = stash_match.group(2)
                    
                    # Process the query part (but not the stash)
                    from asql.preparse.preparser import ASQLPreParser
                    sub_parser = ASQLPreParser(query_part, self.settings, self.dialect)
                    parsed_query = sub_parser.preparse()
                    
                    # If sub-parser generated nested CTEs, merge them first
                    if sub_parser.ctes:
                        for nested_name, nested_query in sub_parser.ctes:
                            collected_ctes.append((nested_name, nested_query))
                        # Strip the WITH wrapper from parsed_query if present
                        with_match = re.match(r'^WITH\s+.+?\)\s*(.+)$', parsed_query, re.IGNORECASE | re.DOTALL)
                        if with_match:
                            parsed_query = with_match.group(1).strip()
                    
                    collected_ctes.append((cte_name, parsed_query))
        
        # Add collected CTEs to our CTE list
        for cte in collected_ctes:
            self.ctes.append(cte)
        
        # Return just the final statement (which references the CTEs)
        return statements[-1]

    def _split_statements(self, text: str) -> List[str]:
        """
        Split text into statements separated by blank lines followed by 'from'.
        
        Returns list of statements.
        """
        # Pattern: one or more blank lines followed by 'from' (at start of line)
        # Split on blank lines where next non-empty line starts with 'from'
        
        lines = text.split('\n')
        statements: List[str] = []
        current_lines: List[str] = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check if this is a blank line
            if not line.strip():
                # Look ahead to find next non-blank line
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                
                if j < len(lines):
                    next_line = lines[j].strip().lower()
                    # If next non-blank starts with 'from', this is a statement boundary
                    if next_line.startswith('from ') or next_line == 'from':
                        if current_lines:
                            statements.append('\n'.join(current_lines))
                            current_lines = []
                        i = j
                        continue
            
            current_lines.append(line)
            i += 1
        
        if current_lines:
            statements.append('\n'.join(current_lines))
        
        return statements

