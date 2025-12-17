"""Pre-parser transforms: dates."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from asql.preparse.registry import DATE_UNITS, FUNCTION_ALIASES, FUNCTION_REGISTRY

class DatesMixin:

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
