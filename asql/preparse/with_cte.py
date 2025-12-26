"""Pre-parser transforms: with name = from CTE syntax."""

from __future__ import annotations

import re
from typing import List, Tuple


class WithCTEMixin:
    """Mixin for transforming 'with name = from ...' CTE syntax."""

    def _transform_with_cte_syntax(self, text: str) -> str:
        """
        Transform 'with name = from ...' CTE definitions.
        
        Example:
            with customer_stats = from customers
              group by customer_id (sum(amount) as total)
            
            from customer_stats
              where total > 100
        
        Extracts CTEs and returns the main query for further processing.
        """
        result = text.strip()
        extracted_ctes: List[Tuple[str, str]] = []
        first_leading_comments = ""
        
        # Keep extracting 'with name = from ...' blocks until none remain
        while True:
            # Check if we start with 'with <name> =' (possibly after comment markers)
            # Comment markers look like __COMMENT_N__
            with_match = re.match(r'^(\s*(?:__COMMENT_\d+__\s*)*)\s*with\s+(\w+)\s*=\s*', result, re.IGNORECASE)
            if not with_match:
                break
            
            # Preserve any leading comment markers (only for first CTE)
            if not extracted_ctes:
                first_leading_comments = with_match.group(1)
            
            cte_name = with_match.group(2)
            after_equals = result[with_match.end():]
            
            # Find where this CTE definition ends
            cte_body, remaining = self._extract_cte_body(after_equals)
            
            if not cte_body:
                break
            
            # Store the raw CTE body - we'll preparse each one at the end
            extracted_ctes.append((cte_name, cte_body.strip()))
            
            # Continue with remaining text
            result = remaining.strip()
        
        # Now preparse each CTE body and add to self.ctes
        for cte_name, cte_body in extracted_ctes:
            from asql.preparse.preparser import ASQLPreParser
            sub_parser = ASQLPreParser(cte_body, self.settings, self.dialect)
            parsed_cte = sub_parser.preparse()
            
            # If the sub-parser generated CTEs (nested), we need to merge them
            # but the parsed_cte will already include WITH ... so we need to handle this
            if sub_parser.ctes:
                # The sub-parser has nested CTEs - merge them first
                for nested_name, nested_query in sub_parser.ctes:
                    self.ctes.append((nested_name, nested_query))
                # parsed_cte already has WITH prefix - strip it and get just the main query
                # This is tricky - let's extract just the last SELECT
                with_match = re.match(r'^WITH\s+.+?\)\s*(.+)$', parsed_cte, re.IGNORECASE | re.DOTALL)
                if with_match:
                    parsed_cte = with_match.group(1).strip()
            
            self.ctes.append((cte_name, parsed_cte))
        
        # If result is empty after extracting CTEs, default to SELECT * from last CTE
        if not result.strip() and self.ctes:
            last_cte_name = self.ctes[-1][0]
            result = f"from {last_cte_name}"
        
        # Preserve leading comments (they were removed during extraction but should stay in main query)
        if extracted_ctes and first_leading_comments.strip():
            result = first_leading_comments + result
        
        return result

    def _extract_cte_body(self, text: str) -> Tuple[str, str]:
        """
        Extract the CTE body from text that starts right after 'with name = '.
        
        Returns:
            (cte_body, remaining_text)
        """
        lines = text.split('\n')
        cte_lines: List[str] = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check if this is an empty line (blank line boundary)
            if not stripped:
                # Look ahead for the next non-empty line
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                
                if j < len(lines):
                    next_line = lines[j].strip().lower()
                    # Check if next non-empty line starts a new statement
                    if (next_line.startswith('from ') or 
                        next_line.startswith('select ') or
                        re.match(r'^with\s+\w+\s*=', next_line)):
                        # This blank line is the boundary
                        remaining = '\n'.join(lines[j:])
                        return '\n'.join(cte_lines), remaining
                
                # Include the blank line in CTE and continue
                cte_lines.append(line)
                i += 1
                continue
            
            # Check if this line starts a new 'with name =' (not the first line)
            if cte_lines and re.match(r'^with\s+\w+\s*=', stripped, re.IGNORECASE):
                remaining = '\n'.join(lines[i:])
                return '\n'.join(cte_lines), remaining
            
            cte_lines.append(line)
            i += 1
        
        # No boundary found - entire text is CTE body
        return '\n'.join(cte_lines), ''
