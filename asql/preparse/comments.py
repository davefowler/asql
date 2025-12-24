"""Pre-parser transforms: comments."""

from __future__ import annotations

import re
from typing import List, Tuple

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
        If a -- comment would end up NOT at the end of a line (i.e., there's
        SQL code after it on the same line), convert it to /* */ style to
        prevent it from eating the subsequent code.
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
            
            # Find where the placeholder is in the current result
            pos = result.find(placeholder)
            if pos == -1:
                continue
            
            # Check if this is a -- comment that needs conversion
            if comment.startswith('--'):
                # Find what comes after the placeholder on the same line
                after_placeholder = pos + len(placeholder)
                next_newline = result.find('\n', after_placeholder)
                if next_newline == -1:
                    after_text = result[after_placeholder:]
                else:
                    after_text = result[after_placeholder:next_newline]
                
                # If there's non-whitespace content after the placeholder on
                # the same line, convert -- to /* */ to prevent eating it
                if after_text.strip():
                    # Convert: "-- comment text" → "/* comment text */"
                    comment_content = comment[2:].strip()  # Remove -- prefix
                    if comment_content:
                        comment = f"/* {comment_content} */"
                    else:
                        comment = ""  # Empty comment, just remove it
            
            result = result.replace(placeholder, comment, 1)
        
        return result
