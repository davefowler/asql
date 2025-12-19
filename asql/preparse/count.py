"""Pre-parser transforms: count."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from asql.preparse.registry import FUNCTION_REGISTRY

class CountMixin:

    def _infer_primary_key_column(self, table_name: str) -> str:
        """
        Infer the primary key column name from a table name.
        
        Uses convention: plural table name → singular + '_id'
        Examples:
        - users → user_id
        - orders → order_id
        - user → user_id (already singular)
        
        Args:
            table_name: Table name (can be plural or singular)
            
        Returns:
            Primary key column name (e.g., 'user_id')
        """
        # Convert to lowercase for processing
        table_lower = table_name.lower()
        
        # Simple pluralization: remove trailing 's' if present
        # This handles most common cases: users → user, orders → order
        if table_lower.endswith('s') and len(table_lower) > 1:
            singular = table_lower[:-1]
        else:
            singular = table_lower
        
        # Generate primary key column name: {singular}_id
        return f"{singular}_id"

    def _transform_count_shorthand(self, text: str) -> str:
        """
        Transform # count shorthand to COUNT(*) or COUNT(DISTINCT {table}_id).
        
        # → COUNT(*)
        # * → COUNT(*) (explicit)
        #(col) → COUNT(col)
        # users → COUNT(DISTINCT user_id)
        # of users → COUNT(DISTINCT user_id)
        """
        result = text
        
        # SQL keywords that should NOT be treated as table names
        sql_keywords = {
            'as', 'from', 'where', 'group', 'by', 'order', 'limit', 'having',
            'select', 'join', 'on', 'and', 'or', 'not', 'in', 'is', 'null',
            'true', 'false', 'union', 'except', 'intersect', 'with', 'stash'
        }
        
        # Pattern: # at word boundary (not inside identifier)
        # Transform standalone # to COUNT(*)
        # But be careful not to transform inside strings or comments
        
        # #(col) → COUNT(col) (explicit column reference)
        result = re.sub(r'#\s*\(\s*([^)]+)\s*\)', r'COUNT(\1)', result)
        
        # # * → COUNT(*) (explicit row count)
        result = re.sub(r'#\s+\*', 'COUNT(*)', result)
        
        # # followed by SQL keyword → COUNT(*) (standalone # with keyword like "as", "from", etc.)
        keyword_pattern = '|'.join(sql_keywords)
        result = re.sub(rf'(?<![a-zA-Z0-9_])#\s+(?:{keyword_pattern})\b', 'COUNT(*)', result, flags=re.IGNORECASE)
        
        # # of <table_name> → COUNT(DISTINCT {table}_id)
        def replace_hash_of_table(match: re.Match) -> str:
            table_name = match.group(1)
            # SQL keywords should have been handled above - if we get here, it's a bug
            if table_name.lower() in sql_keywords:
                raise ValueError(
                    f"Unexpected: SQL keyword '{table_name}' matched as table name in '# of {table_name}'. "
                    f"This indicates a bug in the regex pattern ordering."
                )
            pk_column = self._infer_primary_key_column(table_name)
            return f'COUNT(DISTINCT {pk_column})'
        
        result = re.sub(r'#\s+of\s+([a-zA-Z_][a-zA-Z0-9_]*)', replace_hash_of_table, result)
        
        # # <table_name> → COUNT(DISTINCT {table}_id)
        # This matches # followed by a table name (identifier)
        # But NOT if it's followed by * (already handled) or ( (already handled) or 'of' (already handled)
        # And NOT if it's a SQL keyword (already handled above)
        def replace_hash_table(match: re.Match) -> str:
            table_name = match.group(1)
            # SQL keywords should have been handled above - if we get here, it's a bug
            if table_name.lower() in sql_keywords:
                raise ValueError(
                    f"Unexpected: SQL keyword '{table_name}' matched as table name in '# {table_name}'. "
                    f"This indicates a bug in the regex pattern ordering."
                )
            pk_column = self._infer_primary_key_column(table_name)
            return f'COUNT(DISTINCT {pk_column})'
        
        result = re.sub(r'(?<![a-zA-Z0-9_])#\s+([a-zA-Z_][a-zA-Z0-9_]*)(?!\s*\(|\s*\*|\s*of\s)', replace_hash_table, result)
        
        # Standalone # (not followed by identifier, *, opening paren, or 'of')
        # → COUNT(*)
        result = re.sub(r'(?<![a-zA-Z0-9_])#(?!\s*\(|\s*\*|\s*of\s|\s+[a-zA-Z_])', 'COUNT(*)', result)
        
        return result
