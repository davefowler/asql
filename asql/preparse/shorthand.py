"""Pre-parser transforms: shorthand natural language queries without 'from' clause.

Supports queries like:
- # of Users by country
- Sum of revenue by region  
- Avg Users.age by country
"""

from __future__ import annotations

import re
from typing import Optional, Tuple


class ShorthandMixin:
    """Mixin for handling shorthand natural language queries."""

    def _infer_table_from_aggregation(self, text: str) -> Optional[str]:
        """
        Infer table name from aggregation expression.
        
        Patterns:
        - # of Users → Users
        - # users → users
        - Sum of revenue → sales (inferred from common column-to-table mapping)
        - Avg Users.age → Users
        - Sum revenue → sales (inferred from common column-to-table mapping)
        
        Returns:
            Table name if inferrable, None otherwise
        """
        # Pattern 1: # of <table> or # <table>
        match = re.search(r'#\s+(?:of\s+)?([A-Za-z_][A-Za-z0-9_]*)', text, re.IGNORECASE)
        if match:
            table_name = match.group(1)
            # Don't treat SQL keywords as table names
            sql_keywords = {
                'as', 'from', 'where', 'group', 'by', 'order', 'limit', 'having',
                'select', 'join', 'on', 'and', 'or', 'not', 'in', 'is', 'null',
                'true', 'false', 'union', 'except', 'intersect', 'with', 'stash'
            }
            if table_name.lower() not in sql_keywords:
                return table_name
        
        # Pattern 2: <Table>.<column> (e.g., Users.age)
        match = re.search(r'([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)', text)
        if match:
            table_name = match.group(1)
            # Capitalized names are likely table names
            if table_name[0].isupper() or table_name.lower().endswith('s'):
                return table_name
        
        # Pattern 3: Just a column name - try to infer table from common conventions
        # Common column-to-table mappings (e.g., revenue → sales)
        # Note: This is limited - explicit table references (Table.column) are preferred
        column_to_table = {
            'revenue': 'sales',
            'amount': 'sales',
            'price': 'products',
            'cost': 'products',
        }
        
        # Check if text matches a known column name
        column_lower = text.lower().strip()
        if column_lower in column_to_table:
            return column_to_table[column_lower]
        
        return None

    def _transform_shorthand_queries(self, text: str) -> str:
        """
        Transform shorthand natural language queries to full FROM ... GROUP BY syntax.
        
        Examples:
        - # of Users by country → from Users group by country ( COUNT(DISTINCT user_id) )
        - Sum of revenue by region → from <inferred_table> group by region ( SUM(revenue) )
        - Avg Users.age by country → from Users group by country ( AVG(Users.age) )
        
        This transformation runs early, before _transform_from_first, so we can add
        the FROM clause before other transformations.
        """
        result = text.strip()
        
        # Skip if query already starts with FROM, SELECT, WITH, etc.
        if re.match(r'^\s*(from|select|with|insert|update|delete|create|alter|drop)\b', result, re.IGNORECASE):
            return result
        
        # Pattern: aggregation "by" columns
        # Match patterns like:
        # - # of Users by country
        # - Sum of revenue by region
        # - Avg Users.age by country
        # - # users by country, region
        
        # First, try to match aggregation expressions followed by "by"
        # This is a simplified pattern - we'll match common aggregation patterns
        
        # Pattern 1: # of <table> by <columns> [optional trailing clauses]
        # Match: # of Users by country
        # Match: # users by country, region
        # Match: # users by country order by -total_users
        pattern1 = r'^#\s+(?:of\s+)?([A-Za-z_][A-Za-z0-9_]*)\s+by\s+(.+)$'
        match1 = re.match(pattern1, result, re.IGNORECASE | re.DOTALL)
        if match1:
            table_name = match1.group(1)
            group_cols = match1.group(2).strip()
            
            # Check if table_name is a SQL keyword (shouldn't happen, but safety check)
            sql_keywords = {
                'as', 'from', 'where', 'group', 'by', 'order', 'limit', 'having',
                'select', 'join', 'on', 'and', 'or', 'not', 'in', 'is', 'null',
                'true', 'false', 'union', 'except', 'intersect', 'with', 'stash'
            }
            if table_name.lower() in sql_keywords:
                return result
            
            # Infer primary key (method from CountMixin)
            # Convert table name to singular and add _id
            table_lower = table_name.lower()
            if table_lower.endswith('s') and len(table_lower) > 1:
                singular = table_lower[:-1]
            else:
                singular = table_lower
            pk_column = f"{singular}_id"
            
            # Split group columns from trailing clauses (order by, limit, where)
            # Look for keywords that indicate end of group by clause
            group_by_end_pattern = r'\s+(order\s+by|limit|where)\s+'
            end_match = re.search(group_by_end_pattern, group_cols, re.IGNORECASE)
            
            if end_match:
                actual_group_cols = group_cols[:end_match.start()].strip()
                rest = group_cols[end_match.start():].strip()
            else:
                actual_group_cols = group_cols.strip()
                rest = ""
            
            # Build aggregation: COUNT(DISTINCT pk)
            agg_expr = f"COUNT(DISTINCT {pk_column})"
            
            # Transform to: from <table> group by <cols> ( <agg> )
            transformed = f"from {table_name} group by {actual_group_cols} ( {agg_expr} )"
            if rest:
                transformed += " " + rest
            
            return transformed
        
        # Pattern 2: Aggregation function of column by columns
        # Examples: Sum of revenue by region, Avg Users.age by country
        # Match: <func> of <expr> by <cols> [optional trailing clauses]
        pattern2 = r'^(sum|avg|average|count|min|max|total)\s+(?:of\s+)?([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s+by\s+(.+)$'
        match2 = re.match(pattern2, result, re.IGNORECASE | re.DOTALL)
        if match2:
            func_name = match2.group(1).lower()
            agg_expr = match2.group(2).strip()
            group_cols_raw = match2.group(3).strip()
            
            # Split group columns from trailing clauses
            group_by_end_pattern = r'\s+(order\s+by|limit|where)\s+'
            end_match = re.search(group_by_end_pattern, group_cols_raw, re.IGNORECASE)
            
            if end_match:
                group_cols = group_cols_raw[:end_match.start()].strip()
                rest = group_cols_raw[end_match.start():].strip()
            else:
                group_cols = group_cols_raw.strip()
                rest = ""
            
            # Try to infer table from aggregation expression
            table_name = self._infer_table_from_aggregation(agg_expr)
            
            if not table_name:
                # Can't infer table - this pattern requires explicit table reference
                # For now, we'll skip transformation and let it error
                # In the future, we could use schema metadata to infer from column names
                return result
            
            # Normalize function name
            if func_name == 'average':
                func_name = 'avg'
            elif func_name == 'total':
                func_name = 'sum'
            
            # Build aggregation expression
            # If agg_expr already has table prefix (Users.age), keep it
            # Otherwise, add table prefix
            if '.' not in agg_expr:
                agg_expr_with_table = f"{table_name}.{agg_expr}"
            else:
                agg_expr_with_table = agg_expr
            
            agg_func = f"{func_name.upper()}({agg_expr_with_table})"
            
            # Transform to: from <table> group by <cols> ( <agg> )
            transformed = f"from {table_name} group by {group_cols} ( {agg_func} )"
            if rest:
                transformed += " " + rest
            
            return transformed
        
        # Pattern 3: Aggregation function column by columns (without "of")
        # Examples: Sum revenue by region (less common, but possible)
        pattern3 = r'^(sum|avg|average|count|min|max|total)\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s+by\s+(.+)$'
        match3 = re.match(pattern3, result, re.IGNORECASE | re.DOTALL)
        if match3:
            func_name = match3.group(1).lower()
            agg_expr = match3.group(2).strip()
            group_cols_raw = match3.group(3).strip()
            
            # Split group columns from trailing clauses
            group_by_end_pattern = r'\s+(order\s+by|limit|where)\s+'
            end_match = re.search(group_by_end_pattern, group_cols_raw, re.IGNORECASE)
            
            if end_match:
                group_cols = group_cols_raw[:end_match.start()].strip()
                rest = group_cols_raw[end_match.start():].strip()
            else:
                group_cols = group_cols_raw.strip()
                rest = ""
            
            # Try to infer table from aggregation expression
            table_name = self._infer_table_from_aggregation(agg_expr)
            
            if not table_name:
                # Can't infer table
                return result
            
            # Normalize function name
            if func_name == 'average':
                func_name = 'avg'
            elif func_name == 'total':
                func_name = 'sum'
            
            # Build aggregation expression
            if '.' not in agg_expr:
                agg_expr_with_table = f"{table_name}.{agg_expr}"
            else:
                agg_expr_with_table = agg_expr
            
            agg_func = f"{func_name.upper()}({agg_expr_with_table})"
            
            # Transform to: from <table> group by <cols> ( <agg> )
            transformed = f"from {table_name} group by {group_cols} ( {agg_func} )"
            if rest:
                transformed += " " + rest
            
            return transformed
        
        return result
