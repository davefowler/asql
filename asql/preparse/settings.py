"""Pre-parser transforms: settings."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

class SettingsMixin:

    def _transform_set_statements(self, text: str) -> str:
        """
        Handle SET statements for compile settings only.
        
        Compile settings (preserved for SQLGlot):
            SET auto_spine = true
            SET dialect = 'postgres'
            → preserved as-is (SQLGlot will parse them)
        
        NOTE: CTEs are ONLY created via "stash as" syntax, NOT via "set X = query"
        or "with X = query". This function only handles compile settings.
        """
        result = text.strip()
        preserved_sets: List[str] = []
        
        # Pattern: SET <setting_name> = <value>
        # Only matches known compile settings, not arbitrary identifiers
        known_settings = {'auto_spine', 'dialect', 'week_start', 'relative_date_type'}
        pattern = r'^\s*set\s+(\w+)\s*=\s*([^;]+?)(?:;|(?=\s*(?:set|from|select)\s)|\s*$)'
        
        while True:
            match = re.match(pattern, result, re.IGNORECASE)
            if not match:
                break
            
            name = match.group(1).lower()
            value = match.group(2).strip()
            
            # Only process known compile settings
            if name in known_settings:
                preserved_sets.append(f"SET {name} = {value}")
                result = result[match.end():].strip()
            else:
                # Unknown setting - stop processing (don't treat as CTE)
                break
        
        # Prepend preserved SET statements
        if preserved_sets:
            result = "; ".join(preserved_sets) + "; " + result
        
        return result
