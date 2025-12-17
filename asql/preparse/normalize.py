"""Pre-parser transforms: normalize."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from asql.preparse.registry import DATE_UNITS, FUNCTION_ALIASES, FUNCTION_REGISTRY

class NormalizeMixin:

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
