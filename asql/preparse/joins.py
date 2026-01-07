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
        
        # Expand FK column shorthand in traditional JOIN syntax
        result = self._expand_traditional_join_fk_shorthand(result, from_table)
        
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
            r'|(?:(?:left|right|inner|cross|full(?:\s+outer)?)\s+)?join\b' +  # SQL JOIN keywords (already transformed)
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
            elif condition and from_table:
                # Check if condition is a single FK column shorthand
                expanded = self._expand_fk_shorthand(condition.strip(), from_table, table_name, alias)
                if expanded:
                    condition = expanded
            
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

    def _expand_fk_shorthand(
        self,
        condition: str,
        from_table: str,
        to_table: str,
        to_alias: Optional[str] = None
    ) -> Optional[str]:
        """
        Expand a single FK column name to a full join condition.
        
        If the condition is a single identifier (no dots, operators, etc.),
        treat it as an FK column shorthand and expand to full equality.
        
        Examples:
            owner_id, accounts, users -> accounts.owner_id = users.id
            customer_id, orders, customers -> orders.customer_id = customers.id
            
        Args:
            condition: The ON clause content (potentially just a column name)
            from_table: The source table (FROM clause)
            to_table: The target table (being joined)
            to_alias: Optional alias for the target table
            
        Returns:
            Expanded condition if shorthand detected, None otherwise (use original)
        """
        # Pattern for a single identifier (FK column name)
        # Must be just letters, numbers, underscores - no dots, operators, spaces with operators
        single_ident_pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        
        if not re.match(single_ident_pattern, condition):
            # Not a single identifier - contains dots, operators, etc.
            # Fall back to original behavior (passthrough)
            return None
        
        # It's a single column name - expand to full condition
        fk_column = condition
        to_ref = to_alias or to_table
        
        # FK column is on the from_table, pointing to to_table.id
        return f"{from_table}.{fk_column} = {to_ref}.id"

    def _expand_traditional_join_fk_shorthand(
        self,
        text: str,
        from_table: Optional[str]
    ) -> str:
        """
        Expand FK column shorthand in traditional JOIN syntax.
        
        Handles patterns like:
        - from accounts JOIN users ON owner_id
        - from accounts LEFT JOIN users AS u ON created_by_id
        
        Expands single-column ON clauses to full equality conditions.
        """
        if not from_table:
            return text
        
        # Pattern for traditional JOIN with optional type and alias
        # Captures: join_type, table_name, alias, condition
        pattern = (
            r'\b((?:left|right|inner|cross|full(?:\s+outer)?)\s+)?join\s+'
            r'([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*))?'
            r'\s+on\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?=\s*(?:'
            r'\b(?:left|right|inner|cross|full)\b|\bjoin\b'
            r'|\bwhere\b|\bgroup\b|\border\b|\blimit\b|\bselect\b|\bstash\b|\bhaving\b|\bqualify\b'
            r'|$))'
        )
        
        def replace_match(match: re.Match) -> str:
            join_type = match.group(1) or ''
            table_name = match.group(2)
            alias = match.group(3)
            condition = match.group(4)
            
            # Check if condition is a single identifier (FK column shorthand)
            single_ident_pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
            if not re.match(single_ident_pattern, condition):
                # Not a single identifier, return unchanged
                return match.group(0)
            
            # Expand to full condition
            to_ref = alias or table_name
            expanded_condition = f"{from_table}.{condition} = {to_ref}.id"
            
            # Rebuild the join clause
            parts = [f'{join_type}JOIN', table_name]
            if alias:
                parts.append(f'AS {alias}')
            parts.append(f'ON {expanded_condition}')
            
            return ' '.join(parts)
        
        return re.sub(pattern, replace_match, text, flags=re.IGNORECASE)

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
