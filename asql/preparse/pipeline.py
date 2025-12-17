"""Pre-parser transforms: pipeline."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

class PipelineMixin:

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
