"""Pre-parser transforms: comments."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

class CommentsMixin:

    def _extract_comments(self, text: str) -> Tuple[str, List[Tuple[int, str]]]:
        """Extract comments and return text with placeholders."""
        comments: List[Tuple[int, str]] = []
        result = text
        
        # Extract single-line comments
        pattern = r'--[^\n]*'
        offset = 0
        for match in re.finditer(pattern, text):
            idx = len(comments)
            comment = match.group(0)
            placeholder = f"__COMMENT_{idx}__"
            comments.append((idx, comment))
            start = match.start() - offset
            end = match.end() - offset
            result = result[:start] + placeholder + result[end:]
            offset += len(comment) - len(placeholder)
        
        # Extract multi-line comments
        pattern = r'/\*[\s\S]*?\*/'
        offset = 0
        for match in re.finditer(pattern, result):
            idx = len(comments)
            comment = match.group(0)
            placeholder = f"__COMMENT_{idx}__"
            comments.append((idx, comment))
            start = match.start() - offset
            end = match.end() - offset
            result = result[:start] + placeholder + result[end:]
            offset += len(comment) - len(placeholder)
        
        return result, comments

    def _restore_comments(self, text: str, comments: List[Tuple[int, str]]) -> str:
        """Restore comments from placeholders.
        
        Respects the passthrough_comments setting if available.
        """
        # Check if passthrough_comments is disabled
        if hasattr(self, 'settings') and self.settings is not None:
            if not getattr(self.settings, 'passthrough_comments', True):
                # Remove all comment placeholders instead of restoring
                result = text
                for idx, _ in comments:
                    placeholder = f"__COMMENT_{idx}__"
                    result = result.replace(placeholder, '')
                return result
        
        # Default: restore comments
        result = text
        for idx, comment in comments:
            placeholder = f"__COMMENT_{idx}__"
            result = result.replace(placeholder, comment)
        return result
