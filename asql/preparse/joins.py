"""Pre-parser transforms: joins."""

from __future__ import annotations

import re
from typing import Optional, TYPE_CHECKING

from asql.preparse.inference import infer_fk_column

if TYPE_CHECKING:
    from asql.schema import Schema

class JoinsMixin:

    def _transform_join_operators(self, text: str) -> str:
        """
        Transform ASQL join operators to SQL JOIN syntax.
        
        &   → INNER JOIN (both sides must match)
        &?  → LEFT JOIN (right side is optional)
        ?&  → RIGHT JOIN (left side is optional)
        ?&? → FULL OUTER JOIN (both sides are optional)
        *   → CROSS JOIN (cartesian product)
        
        Examples:
        from users &? orders on users.id = orders.user_id
        → FROM users LEFT JOIN orders ON users.id = orders.user_id
        
        from opportunities & owners
        → FROM opportunities INNER JOIN owners
        
        from users &? accounts as account on users.id = account.user_id
        → FROM users LEFT JOIN accounts AS account ON users.id = account.user_id
        
        Schema-based inference (when no ON clause):
        from orders & users
        → FROM orders JOIN users ON orders.user_id = users.id
        (if schema has relationship: orders.user_id -> users.id)
        """
        result = text
        
        # Extract the FROM table for join inference
        from_match = re.search(r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)', result, re.IGNORECASE)
        from_table = from_match.group(1) if from_match else None
        
        # Process join operators in a specific order to handle overlapping patterns
        # Order matters: ?&? before ?& and &? before &
        
        # Pattern components:
        # - Join operator: ?&?, &?, ?&, &, *
        # - Table name: identifier
        # - Optional alias: as <identifier>
        # - Optional condition: on <condition>
        
        # ?&? → FULL OUTER JOIN
        result = self._replace_join_operator(result, r'\?\s*&\s*\?', 'FULL OUTER JOIN', from_table)
        
        # &? → LEFT JOIN  
        result = self._replace_join_operator(result, r'&\s*\?', 'LEFT JOIN', from_table)
        
        # ?& → RIGHT JOIN
        result = self._replace_join_operator(result, r'\?\s*&', 'RIGHT JOIN', from_table)
        
        # & → INNER JOIN (but not &&, and not &? or ?&)
        # Use negative lookahead/lookbehind to avoid matching &? or ?& or &&
        result = self._replace_join_operator(result, r'(?<!\?)&(?!\?|&)', 'JOIN', from_table)
        
        # * → CROSS JOIN (but not ** or *=)
        # Must be careful to distinguish from multiplication
        # Cross join should have a table name after it
        result = self._replace_cross_join(result)
        
        return result

    def _replace_join_operator(
        self, 
        text: str, 
        operator_pattern: str, 
        join_type: str,
        from_table: Optional[str] = None
    ) -> str:
        """
        Replace a join operator with SQL JOIN syntax.
        
        Handles patterns like:
        - table1 &? table2
        - table1 &? table2 as alias
        - table1 &? table2 on condition
        - table1 &? table2 as alias on condition
        
        When no ON condition is provided, attempts to infer from schema.
        """
        result = text
        
        # Build the pattern:
        # <operator> <table_name> [as <alias>] [on <condition>]
        # The condition extends until the next join operator, clause keyword, or end
        
        # Pattern for table with optional alias
        table_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*))?'
        
        # Full pattern: operator table [as alias] [on condition]
        # Condition continues until next join op, clause keyword, or end of line/query
        full_pattern = (
            operator_pattern + 
            r'\s+' + 
            table_pattern +
            r'(?:\s+on\s+(.+?))?'
            r'(?=\s*(?:' +
            r'(?:\?\s*&\s*\?|\&\s*\?|\?\s*&|(?<!\?)&(?!\?|&)|\*)' +  # Next join operator
            r'|\bwhere\b|\bgroup\b|\border\b|\blimit\b|\bselect\b|\bstash\b|\bhaving\b|\bqualify\b' +  # Clause keywords
            r'|$))'  # End of string
        )
        
        def replace_match(match: re.Match) -> str:
            table_name = match.group(1)
            alias = match.group(2)
            condition = match.group(3)
            
            # Build the replacement
            parts = [join_type, table_name]
            
            if alias:
                parts.append(f'AS {alias}')
            
            # If no ON condition, try to infer from schema
            if not condition and from_table:
                inferred_condition = self._infer_join_condition(from_table, table_name, alias)
                if inferred_condition:
                    condition = inferred_condition
            
            if condition:
                parts.append(f'ON {condition.strip()}')
            
            return ' ' + ' '.join(parts)
        
        result = re.sub(full_pattern, replace_match, result, flags=re.IGNORECASE | re.DOTALL)
        
        return result
    
    def _infer_join_condition(
        self, 
        from_table: str, 
        to_table: str, 
        to_alias: Optional[str] = None
    ) -> Optional[str]:
        """
        Infer join condition from schema or naming conventions.
        
        Args:
            from_table: The source table (FROM clause)
            to_table: The target table (being joined)
            to_alias: Optional alias for the target table
            
        Returns:
            Join condition string, or None if can't infer
        """
        # Get settings and schema from the preparser instance
        settings = getattr(self, 'settings', None)
        schema: Optional["Schema"] = None
        invent_join_keys = False
        
        if settings:
            schema = getattr(settings, 'schema', None)
            invent_join_keys = getattr(settings, 'invent_join_keys', False)
        
        # Use alias or table name for the condition
        to_ref = to_alias or to_table
        
        # Try schema-based lookup first
        if schema:
            # Try from_table -> to_table
            rel = schema.find_relationship(from_table, to_table)
            if rel:
                return f"{from_table}.{rel.from_column} = {to_ref}.{rel.to_column}"
            
            # Try reverse direction: to_table -> from_table
            rel = schema.find_relationship(to_table, from_table)
            if rel:
                return f"{to_ref}.{rel.from_column} = {from_table}.{rel.to_column}"
        
        # Fall back to convention-based inference if enabled
        if invent_join_keys:
            return self._invent_join_condition(from_table, to_table, to_ref)
        
        return None
    
    def _invent_join_condition(
        self, 
        from_table: str, 
        to_table: str, 
        to_ref: str
    ) -> Optional[str]:
        """
        Invent join condition using naming conventions.
        
        Uses shared inference logic from asql.preparse.inference.
        Assumes {singular_table}_id -> {table}.id convention.
        
        Examples:
        - orders, users -> orders.user_id = users.id
        - users, orders -> users.id = orders.user_id (reverse)
        """
        # Use shared FK column inference
        fk_col = infer_fk_column(to_table)
        return f"{from_table}.{fk_col} = {to_ref}.id"

    def _replace_cross_join(self, text: str) -> str:
        """
        Replace * cross join operator with SQL CROSS JOIN syntax.
        
        Pattern: table1 * table2
        → FROM table1 CROSS JOIN table2
        
        Must be careful to distinguish from multiplication in expressions.
        Cross join * is only valid:
        - After FROM clause table name
        - After another join clause
        
        NOT valid:
        - Inside expressions (arithmetic)
        - Inside parentheses (could be subexpression)
        """
        result = text
        
        # Only look for * that appears in a "from" context
        # Pattern: after FROM table or after a previous join (ending with identifier or ))
        # We need to look for:
        # - "from <table> *" 
        # - "on <condition> *" (after a join condition)
        
        # The cross join must:
        # 1. Follow a table identifier (not inside parens for arithmetic)
        # 2. Precede a table identifier
        # 3. Not be inside a select expression context
        
        # Strategy: Only replace * when it's preceded by:
        # - "from <table>"
        # - Another JOIN clause pattern
        # And followed by a table name
        
        # This is a conservative pattern that only matches * after "from X" or after
        # a previous join's table/alias, NOT inside select expressions
        
        # Pattern: from <table> * <table2> OR from <table> as <alias> * <table2>
        pattern = r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+as\s+[a-zA-Z_][a-zA-Z0-9_]*)?\s+\*\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*))?'
        
        def replace_from_cross(match: re.Match) -> str:
            table1 = match.group(1)
            table2 = match.group(2)
            alias = match.group(3)
            
            parts = [f'from {table1} CROSS JOIN {table2}']
            if alias:
                parts[0] += f' AS {alias}'
            
            return parts[0]
        
        result = re.sub(pattern, replace_from_cross, result, flags=re.IGNORECASE)
        
        return result
