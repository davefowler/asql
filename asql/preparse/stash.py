"""Pre-parser transforms: stash."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

class StashMixin:

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
            # Local import to avoid circular import (preparser imports this mixin)
            from asql.preparse.preparser import ASQLPreParser

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
