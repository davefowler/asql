"""Pre-parser transforms: bucket function for binning/discretization."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple


class BucketMixin:
    """Mixin for transforming bucket() function calls to CASE WHEN expressions.
    
    The bucket() function simplifies binning/discretization of continuous values
    into categories, similar to pandas pd.cut() and pd.qcut().
    
    Supported forms:
    
    1. Explicit boundaries with labels:
       bucket(score, [0, 60, 70, 80, 90, 100], ['F', 'D', 'C', 'B', 'A'])
       
    2. Explicit boundaries without labels (auto-labeled as ranges):
       bucket(score, [0, 60, 70, 80, 90, 100])
       
    3. Fixed-width bins with start/end:
       bucket(value, start=0, end=100, width=10)
       
    All forms compile to CASE WHEN expressions.
    """

    def _transform_bucket_function(self, text: str) -> str:
        """Transform bucket() function calls to CASE WHEN expressions."""
        result = text
        
        # Pattern to find bucket() function calls
        # bucket(expr, [...], [...]) or bucket(expr, [...]) or bucket(expr, start=..., end=..., width=...)
        bucket_pattern = r'\bbucket\s*\('
        
        while True:
            match = re.search(bucket_pattern, result, re.IGNORECASE)
            if not match:
                break
            
            start_pos = match.start()
            
            # Skip if inside a string
            before = result[:start_pos]
            if (before.count("'") % 2 != 0) or (before.count('"') % 2 != 0):
                # Replace temporarily to avoid infinite loop
                result = result[:start_pos] + "__BUCKET_SKIP__" + result[start_pos + 6:]
                continue
            
            # Parse the bucket() call
            case_expr, end_pos = self._parse_bucket_call(result, start_pos)
            
            if case_expr:
                result = result[:start_pos] + case_expr + result[end_pos:]
            else:
                # Failed to parse, skip to avoid infinite loop
                result = result[:start_pos] + "__BUCKET_SKIP__" + result[start_pos + 6:]
        
        # Restore skipped bucket keywords
        result = result.replace("__BUCKET_SKIP__", "bucket")
        
        return result
    
    def _parse_bucket_call(self, text: str, start_pos: int) -> Tuple[Optional[str], int]:
        """Parse a bucket() function call and return the CASE WHEN expression.
        
        Returns:
            (case_expr, end_pos) or (None, start_pos) if parsing fails
        """
        # Find the opening parenthesis
        paren_start = text.find('(', start_pos)
        if paren_start == -1:
            return None, start_pos
        
        # Find the matching closing parenthesis
        paren_end = self._find_matching_paren(text, paren_start)
        if paren_end == -1:
            return None, start_pos
        
        # Extract the arguments
        args_text = text[paren_start + 1:paren_end]
        
        # Parse arguments
        args = self._parse_bucket_args(args_text)
        if not args:
            return None, start_pos
        
        # Determine which form of bucket() this is
        expr = args.get('expr')
        boundaries = args.get('boundaries')
        labels = args.get('labels')
        start = args.get('start')
        end = args.get('end')
        width = args.get('width')
        
        if not expr:
            return None, start_pos
        
        # Form 1 & 2: Explicit boundaries
        if boundaries:
            case_expr = self._build_case_from_boundaries(expr, boundaries, labels)
            return case_expr, paren_end + 1
        
        # Form 3: start/end/width
        if start is not None and end is not None and width is not None:
            # Generate boundaries from start, end, width
            try:
                start_val = float(start)
                end_val = float(end)
                width_val = float(width)
                
                if width_val <= 0:
                    return None, start_pos
                
                generated_boundaries: List[str] = []
                current = start_val
                while current <= end_val:
                    # Format nicely: integer if whole number, float otherwise
                    if current == int(current):
                        generated_boundaries.append(str(int(current)))
                    else:
                        generated_boundaries.append(str(current))
                    current += width_val
                
                # Ensure end is included
                end_str = str(int(end_val)) if end_val == int(end_val) else str(end_val)
                if generated_boundaries[-1] != end_str:
                    generated_boundaries.append(end_str)
                
                case_expr = self._build_case_from_boundaries(expr, generated_boundaries, None)
                return case_expr, paren_end + 1
            except (ValueError, TypeError):
                return None, start_pos
        
        return None, start_pos
    
    def _find_matching_paren(self, text: str, open_pos: int) -> int:
        """Find the position of the matching closing parenthesis."""
        depth = 1
        pos = open_pos + 1
        in_string: Optional[str] = None
        
        while pos < len(text) and depth > 0:
            char = text[pos]
            
            # Handle string literals
            if char in ('"', "'") and (pos == 0 or text[pos - 1] != '\\'):
                if in_string == char:
                    in_string = None
                elif in_string is None:
                    in_string = char
            
            if in_string is None:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
            
            pos += 1
        
        return pos - 1 if depth == 0 else -1
    
    def _parse_bucket_args(self, args_text: str) -> Optional[dict]:
        """Parse bucket() arguments into a dictionary.
        
        Handles:
        - bucket(expr, [boundaries], [labels])
        - bucket(expr, [boundaries])
        - bucket(expr, start=X, end=Y, width=Z)
        """
        result: dict = {
            'expr': None,
            'boundaries': None,
            'labels': None,
            'start': None,
            'end': None,
            'width': None,
        }
        
        # Split by commas at the top level (respecting brackets and parens)
        parts = self._split_args(args_text)
        if not parts:
            return None
        
        # First part is always the expression
        result['expr'] = parts[0].strip()
        
        if len(parts) < 2:
            return None
        
        # Check if we have keyword arguments
        has_kwargs = any('=' in p and not self._is_in_brackets(p) for p in parts[1:])
        
        if has_kwargs:
            # Parse keyword arguments
            for part in parts[1:]:
                part = part.strip()
                if '=' in part:
                    key, value = part.split('=', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if key in ('start', 'end', 'width', 'bins', 'quantiles'):
                        result[key] = value
        else:
            # Positional arguments: second is boundaries, third is labels
            second = parts[1].strip()
            if second.startswith('[') or second.startswith('('):
                result['boundaries'] = self._parse_list(second)
            
            if len(parts) >= 3:
                third = parts[2].strip()
                if third.startswith('[') or third.startswith('('):
                    result['labels'] = self._parse_list(third)
        
        return result
    
    def _is_in_brackets(self, text: str) -> bool:
        """Check if '=' appears inside brackets."""
        depth = 0
        for i, char in enumerate(text):
            if char in '[(':
                depth += 1
            elif char in '])':
                depth -= 1
            elif char == '=' and depth > 0:
                return True
        return False
    
    def _split_args(self, text: str) -> List[str]:
        """Split arguments by comma, respecting brackets and parentheses."""
        parts: List[str] = []
        current: List[str] = []
        depth = 0
        in_string: Optional[str] = None
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # Handle string literals
            if char in ('"', "'") and (i == 0 or text[i - 1] != '\\'):
                if in_string == char:
                    in_string = None
                elif in_string is None:
                    in_string = char
            
            if in_string is None:
                if char in '([':
                    depth += 1
                elif char in ')]':
                    depth -= 1
                elif char == ',' and depth == 0:
                    parts.append(''.join(current))
                    current = []
                    i += 1
                    continue
            
            current.append(char)
            i += 1
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    def _parse_list(self, text: str) -> List[str]:
        """Parse a list like [1, 2, 3] or ['a', 'b', 'c'] into individual elements."""
        # Remove outer brackets
        text = text.strip()
        if text.startswith('['):
            text = text[1:]
        if text.startswith('('):
            text = text[1:]
        if text.endswith(']'):
            text = text[:-1]
        if text.endswith(')'):
            text = text[:-1]
        
        # Split by comma
        elements = self._split_args(text)
        return [e.strip() for e in elements if e.strip()]
    
    def _build_case_from_boundaries(
        self, 
        expr: str, 
        boundaries: List[str], 
        labels: Optional[List[str]]
    ) -> str:
        """Build a CASE WHEN expression from boundaries.
        
        Boundaries define the edges: [0, 60, 70, 80, 90, 100] creates bins:
        - [0, 60)   -> label[0] or '0-60'
        - [60, 70)  -> label[1] or '60-70'
        - [70, 80)  -> label[2] or '70-80'
        - [80, 90)  -> label[3] or '80-90'
        - [90, 100] -> label[4] or '90-100'
        
        Left-inclusive by default: [lower, upper)
        Last bucket includes upper bound: [lower, upper]
        """
        if len(boundaries) < 2:
            return f"NULL /* bucket: need at least 2 boundaries, got {len(boundaries)} */"
        
        num_bins = len(boundaries) - 1
        
        # Generate labels if not provided
        if not labels:
            labels = []
            for i in range(num_bins):
                lower = boundaries[i]
                upper = boundaries[i + 1]
                labels.append(f"'{lower}-{upper}'")
        elif len(labels) != num_bins:
            # Wrong number of labels - use auto-generated
            labels = []
            for i in range(num_bins):
                lower = boundaries[i]
                upper = boundaries[i + 1]
                labels.append(f"'{lower}-{upper}'")
        
        # Build CASE WHEN
        case_parts = ["CASE"]
        
        for i in range(num_bins):
            lower = boundaries[i]
            upper = boundaries[i + 1]
            label = labels[i]
            
            # Ensure label is quoted if it's a string literal
            if not (label.startswith("'") or label.startswith('"')):
                # Check if it's a number
                try:
                    float(label)
                except ValueError:
                    label = f"'{label}'"
            
            if i == num_bins - 1:
                # Last bucket: include upper bound [lower, upper]
                case_parts.append(
                    f"WHEN {expr} >= {lower} AND {expr} <= {upper} THEN {label}"
                )
            else:
                # Other buckets: left-inclusive, right-exclusive [lower, upper)
                case_parts.append(
                    f"WHEN {expr} >= {lower} AND {expr} < {upper} THEN {label}"
                )
        
        case_parts.append("ELSE NULL END")
        
        return " ".join(case_parts)
