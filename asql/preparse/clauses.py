"""Pre-parser transforms: clauses."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from asql.preparse.registry import FUNCTION_ALIASES, FUNCTION_REGISTRY

class ClausesMixin:

    def _normalize_where_before_joins(self, text: str) -> str:
        """
        Ensure WHERE appears after JOINs.

        ASQL pipeline semantics allow:
          from t
            where ...
            & u
            where ...

        But SQL requires JOINs to appear before WHERE. This transform moves any WHERE
        that appears between FROM and the first JOIN to after the JOIN section,
        combining it with an existing post-join WHERE using AND.
        """
        result = text

        from_match = re.search(r'\bfrom\b', result, re.IGNORECASE)
        if not from_match:
            return result

        # Find the first JOIN after FROM (include optional join-type keyword so we don't
        # accidentally treat "LEFT" as part of a preceding WHERE condition).
        join_match = re.search(
            r'\b(?:left|right|inner|cross|full(?:\s+outer)?)\s+join\b|\bjoin\b',
            result[from_match.end():],
            re.IGNORECASE,
        )
        if not join_match:
            return result
        join_pos = from_match.end() + join_match.start()

        # Find the first WHERE after FROM
        where_match = re.search(r'\bwhere\b', result[from_match.end():], re.IGNORECASE)
        if not where_match:
            return result
        where_pos = from_match.end() + where_match.start()

        # Only fix the case where a WHERE appears before the first JOIN
        if where_pos > join_pos:
            return result

        # Extract the pre-join WHERE condition (up to the JOIN)
        cond_start = where_pos + len(where_match.group(0))
        cond_end = join_pos
        cond = result[cond_start:cond_end].strip()
        if not cond:
            return result

        # Remove the pre-join WHERE clause
        result = (result[:where_pos].rstrip() + " " + result[cond_end:].lstrip()).strip()

        # If there's already a WHERE after joins, combine with AND
        from_match2 = re.search(r'\bfrom\b', result, re.IGNORECASE)
        if not from_match2:
            return result

        where_after = re.search(r'\bwhere\b', result[from_match2.end():], re.IGNORECASE)
        if where_after:
            insert_at = from_match2.end() + where_after.start() + len(where_after.group(0))
            return result[:insert_at] + f" ({cond}) AND" + result[insert_at:]

        # Otherwise insert a new WHERE after the join section (before next clause)
        tail = result[from_match2.end():]
        clause_match = re.search(r'\b(group\s+by|order\s+by|limit|having|qualify)\b', tail, re.IGNORECASE)
        if clause_match:
            insert_at = from_match2.end() + clause_match.start()
        else:
            insert_at = len(result)

        return (result[:insert_at].rstrip() + f" WHERE {cond} " + result[insert_at:].lstrip()).strip()

    def _transform_implicit_function_aliases(self, text: str) -> str:
        """
        Expand implicit function aliases in SELECT projections and GROUP BY aggregate blocks.

        This supports the "auto-alias" convention where a single-arg function call's
        natural alias is `func_col`, and ASQL lets you write that alias directly:

        - select sum_amount  → select sum(amount) as sum_amount
        - select year_created_at → select year(created_at) as year_created_at
        - group by region ( sum_amount ) → group by region ( sum(amount) as sum_amount )

        Notes / constraints:
        - Applied to SELECT projection items and GROUP BY aggregate blocks.
        - Only expands *plain identifiers* (no dots, no parens, no quotes).
        - Only for a conservative set of single-arg functions (and their aliases).
        """
        result = text

        # Conservative allowlist: single-arg functions that follow func_col aliasing.
        single_arg_funcs: Set[str] = {
            # Aggregates
            'sum', 'avg', 'count', 'min', 'max',
            # Date parts / truncs
            'year', 'quarter', 'month', 'week', 'day', 'hour', 'minute', 'second',
            'day_of_week', 'day_of_month', 'day_of_year',
            'week_of_year', 'month_of_year', 'quarter_of_year',
            # Window-ish single-arg helpers
            'running_sum', 'running_avg', 'running_count',
            'rolling_sum', 'rolling_avg',
        }

        # Include aliases (total/average/etc) as valid shorthand prefixes, but expand to canonical fn.
        alias_prefixes: Set[str] = set(FUNCTION_ALIASES.keys())

        # Include any registered function that is in our allowlist
        allowed_prefixes: List[str] = sorted(
            {fn for fn in FUNCTION_REGISTRY if fn in single_arg_funcs}.union(alias_prefixes),
            key=len,
            reverse=True,
        )

        identifier_pattern = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

        def split_csv(exprs: str) -> List[str]:
            items: List[str] = []
            current: List[str] = []
            depth = 0
            in_single = False
            in_double = False
            idx = 0
            while idx < len(exprs):
                ch = exprs[idx]
                if ch == "'" and not in_double:
                    in_single = not in_single
                elif ch == '"' and not in_single:
                    in_double = not in_double
                elif not in_single and not in_double:
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth = max(0, depth - 1)
                    elif ch == ',' and depth == 0:
                        items.append(''.join(current).strip())
                        current = []
                        idx += 1
                        continue
                current.append(ch)
                idx += 1
            tail = ''.join(current).strip()
            if tail:
                items.append(tail)
            return items

        def expand_token(token: str, add_alias: bool = True) -> str:
            """
            Expand a token if it matches a function pattern.
            
            Args:
                token: The token to expand
                add_alias: If True, add 'as func_col' alias (for SELECT/GROUP BY).
            """
            trimmed = token.strip()
            if not trimmed:
                return token
            # Don't touch anything that's clearly not a bare identifier
            if not identifier_pattern.match(trimmed):
                return token
            if '.' in trimmed:
                return token

            lowered = trimmed.lower()
            for prefix in allowed_prefixes:
                prefix_lower = prefix.lower()
                needle = f"{prefix_lower}_"
                if not lowered.startswith(needle):
                    continue
                arg = trimmed[len(prefix) + 1:]
                if not identifier_pattern.match(arg):
                    return token
                fn = FUNCTION_ALIASES.get(prefix_lower, prefix_lower)
                if add_alias:
                    return f"{fn}({arg}) as {trimmed}"
                else:
                    return f"{fn}({arg})"
            return token
        
        # Process SELECT clause
        select_match = re.search(r'\bselect\s+', result, re.IGNORECASE)
        if select_match:
            select_start = select_match.end()
            select_end = len(result)

            paren_depth = 0
            i = select_start
            while i < len(result):
                char = result[i]
                if char == '(':
                    paren_depth += 1
                elif char == ')':
                    paren_depth = max(0, paren_depth - 1)
                elif paren_depth == 0:
                    remaining = result[i:].lower()
                    for kw in [' from ', '\nfrom ', '\tfrom ', ' where ', ' group by ', ' order by ', ' limit ', ' having ', ' qualify ']:
                        if remaining.startswith(kw):
                            select_end = i
                            i = len(result)
                            break
                i += 1

            raw_clause = result[select_start:select_end]
            items = split_csv(raw_clause)
            if items:
                expanded_items = [expand_token(item, add_alias=True) for item in items]
                new_clause = ", ".join(expanded_items)
                result = result[:select_start] + new_clause + result[select_end:]

        # Process GROUP BY aggregate blocks: group by <keys> ( agg1, agg2 )
        #
        # IMPORTANT: group-by keys can include function calls like month(created_at).
        # So we can't use a naive regex that stops at the first "(".
        def expand_group_by_aggregate_blocks(text: str) -> str:
            out_text = text
            search_pos = 0

            while True:
                gb_match = re.search(r'\bgroup\s+by\s+', out_text[search_pos:], re.IGNORECASE)
                if not gb_match:
                    return out_text

                gb_start = search_pos + gb_match.start()
                keys_start = search_pos + gb_match.end()

                # Find the opening paren of the aggregate list, skipping function-call parens in keys.
                paren_pos = -1
                i = keys_start
                while i < len(out_text):
                    ch = out_text[i]
                    if ch == '(':
                        j = i - 1
                        # function call: identifier directly before "("
                        if j >= keys_start and (out_text[j].isalnum() or out_text[j] == '_'):
                            depth = 1
                            i += 1
                            while i < len(out_text) and depth > 0:
                                if out_text[i] == '(':
                                    depth += 1
                                elif out_text[i] == ')':
                                    depth -= 1
                                i += 1
                            continue
                        # otherwise: this is the aggregate list paren
                        paren_pos = i
                        break
                    # stop if we hit another clause keyword before an aggregate list
                    if ch == '\n' or ch == ';':
                        break
                    i += 1

                if paren_pos == -1:
                    search_pos = keys_start
                    continue

                group_cols = out_text[keys_start:paren_pos].strip()

                # Find the matching closing paren for the aggregate list
                depth = 1
                i = paren_pos + 1
                while i < len(out_text) and depth > 0:
                    if out_text[i] == '(':
                        depth += 1
                    elif out_text[i] == ')':
                        depth -= 1
                    i += 1

                if depth != 0:
                    # Unmatched parens; give up on this one
                    search_pos = paren_pos + 1
                    continue

                aggs_inner_start = paren_pos + 1
                aggs_inner_end = i - 1
                aggs_text = out_text[aggs_inner_start:aggs_inner_end].strip()

                items = split_csv(aggs_text)
                if items:
                    expanded_items = [expand_token(item, add_alias=True) for item in items]
                    new_aggs = ", ".join(expanded_items)
                    replacement = f"group by {group_cols} ( {new_aggs} )"

                    # Replace from "group by" up through closing paren
                    out_text = out_text[:gb_start] + replacement + out_text[i:]
                    search_pos = gb_start + len(replacement)
                else:
                    search_pos = i

        result = expand_group_by_aggregate_blocks(result)

        return result

    def _transform_column_operators(self, text: str) -> str:
        """
        Transform column operators: except, rename, replace.
        
        except col1, col2 → adds EXCEPT(col1, col2) to SELECT *
        rename old as new → transforms to: old AS new in SELECT
        replace col with expr → adds expr AS col and EXCEPT(col)
        
        These must run before _transform_from_first.
        """
        result = text
        
        # Track columns to except and expressions to add
        except_cols: List[str] = []
        rename_mappings: List[Tuple[str, str]] = []  # (old, new)
        replace_exprs: List[Tuple[str, str]] = []  # (col, expr)
        
        # Process 'except col1, col2, ...'
        except_pattern = r'\bexcept\s+([a-zA-Z_][\w.,\s]*?)(?=\s+(?:from|where|group|order|limit|join|left|right|inner|outer|rename|replace|select|$)|\s*$)'
        except_match = re.search(except_pattern, result, re.IGNORECASE)
        if except_match:
            cols_str = except_match.group(1).strip()
            # Split by comma and clean
            cols = [c.strip() for c in cols_str.split(',') if c.strip()]
            except_cols.extend(cols)
            # Remove the except clause from result
            result = result[:except_match.start()] + result[except_match.end():]
        
        # Process 'rename old as new, old2 as new2, ...'
        rename_pattern = r'\brename\s+(.+?)(?=\s+(?:from|where|group|order|limit|join|left|right|inner|outer|except|replace|select|$)|\s*$)'
        rename_match = re.search(rename_pattern, result, re.IGNORECASE)
        if rename_match:
            mappings_str = rename_match.group(1).strip()
            # Split by comma (but not inside parens)
            # Simple approach: split by comma, then parse each "old as new"
            mapping_pattern = r'(\w+)\s+as\s+(\w+)'
            for m in re.finditer(mapping_pattern, mappings_str, re.IGNORECASE):
                old_name = m.group(1)
                new_name = m.group(2)
                rename_mappings.append((old_name, new_name))
            # Remove the rename clause from result
            result = result[:rename_match.start()] + result[rename_match.end():]
        
        # Process 'replace col with expr' - supports chaining:
        # replace name with upper(name), price with round(price, 2)
        # Also supports multiple replace statements
        while True:
            replace_clause_pattern = r'\breplace\s+(.+?)(?=\s+(?:from|where|group|order|limit|join|left|right|inner|outer|except|rename|replace|select|$)|\s*$)'
            replace_clause_match = re.search(replace_clause_pattern, result, re.IGNORECASE)
            if not replace_clause_match:
                break
            
            replace_content = replace_clause_match.group(1).strip()
            # Parse individual "col with expr" pairs
            # Pattern: word "with" expression, where expression ends at ", word with" or end
            # Handle nested parens in expressions
            individual_pattern = r'(\w+)\s+with\s+'
            pairs = []
            for m in re.finditer(individual_pattern, replace_content, re.IGNORECASE):
                col_name = m.group(1)
                expr_start = m.end()
                # Find where this expression ends (next "col with" or end)
                next_match = re.search(r',\s*(\w+)\s+with\s+', replace_content[expr_start:], re.IGNORECASE)
                if next_match:
                    expr_end = expr_start + next_match.start()
                else:
                    expr_end = len(replace_content)
                expr = replace_content[expr_start:expr_end].strip().rstrip(',')
                pairs.append((col_name, expr))
            
            for col_name, expr in pairs:
                replace_exprs.append((col_name, expr))
                except_cols.append(col_name)
            
            # Remove the replace clause from result
            result = result[:replace_clause_match.start()] + result[replace_clause_match.end():]
        
        # Now apply transformations to the query
        # If we have any column operators, we need to modify the SELECT clause
        
        if not except_cols and not rename_mappings and not replace_exprs:
            return result
        
        # Check if there's already a SELECT clause
        select_match = re.search(r'\bselect\s+', result, re.IGNORECASE)
        
        if select_match:
            # There's already a SELECT - need to modify it
            # For now, add EXCEPT and expressions after the select columns
            select_pos = select_match.end()
            
            # Find what follows SELECT until FROM or other clause
            rest = result[select_pos:]
            from_match = re.search(r'\bfrom\b', rest, re.IGNORECASE)
            if from_match:
                select_clause = rest[:from_match.start()].strip()
                after_select = rest[from_match.start():]
            else:
                select_clause = rest.strip()
                after_select = ""
            
            # Build new select clause
            new_parts = []
            
            # Handle star with EXCEPT
            if '*' in select_clause and except_cols:
                # Replace * with * EXCEPT(...)
                except_str = ', '.join(except_cols)
                select_clause = re.sub(r'\*', f'* EXCEPT({except_str})', select_clause, count=1)
            elif except_cols and '*' not in select_clause:
                # No star but have except - need to add * EXCEPT
                except_str = ', '.join(except_cols)
                select_clause = f"* EXCEPT({except_str}), {select_clause}"
            
            new_parts.append(select_clause)
            
            # Add rename mappings (old AS new)
            for old, new in rename_mappings:
                new_parts.append(f"{old} AS {new}")
            
            # Add replace expressions (expr AS col)
            for col, expr in replace_exprs:
                new_parts.append(f"{expr} AS {col}")
            
            new_select_clause = ', '.join(p for p in new_parts if p)
            result = result[:select_match.start()] + f"SELECT {new_select_clause} " + after_select
        else:
            # No SELECT yet - we're in from-first mode
            # Build select parts that will be used after from-first transform
            select_parts = []
            
            if except_cols:
                except_str = ', '.join(except_cols)
                select_parts.append(f"* EXCEPT({except_str})")
            else:
                select_parts.append("*")
            
            for old, new in rename_mappings:
                select_parts.append(f"{old} AS {new}")
                # If we have renames but no except, we need to except the original
                if old not in except_cols:
                    # Update the first part to include this in EXCEPT
                    if "EXCEPT" in select_parts[0]:
                        select_parts[0] = select_parts[0].replace(")", f", {old})")
                    else:
                        select_parts[0] = f"* EXCEPT({old})"
            
            for col, expr in replace_exprs:
                select_parts.append(f"{expr} AS {col}")
            
            # Insert SELECT clause before FROM
            from_match = re.search(r'\bfrom\b', result, re.IGNORECASE)
            if from_match:
                select_clause = ', '.join(select_parts)
                result = f"SELECT {select_clause} " + result[from_match.start():]
        
        return result

    def _transform_multiple_where(self, text: str) -> str:
        """
        Combine multiple WHERE clauses into a single WHERE with AND.
        
        from users where status == "active" where age >= 18
        → from users where status == "active" AND age >= 18
        """
        result = text
        
        # Find all WHERE clauses and combine them
        # Pattern: where <condition1> where <condition2>
        while True:
            # Find two consecutive WHERE clauses
            pattern = r'\bwhere\s+(.+?)\s+where\s+'
            match = re.search(pattern, result, re.IGNORECASE)
            if not match:
                break
            
            first_condition = match.group(1).strip()
            # Replace "where X where Y" with "where X AND Y"
            result = result[:match.start()] + f"where {first_condition} AND " + result[match.end():]
        
        return result

    def _transform_from_first(self, text: str) -> str:
        """
        Add SELECT * if needed for FROM-first queries.
        
        from users where active limit 10
        → SELECT * FROM users WHERE active LIMIT 10
        """
        result = text.strip()
        
        # Skip over comment placeholders at the start to find actual query start
        # Comment placeholders look like: __COMMENT_N__
        query_start_pattern = r'^(\s*(?:__COMMENT_\d+__\s*)*)'
        query_start_match = re.match(query_start_pattern, result)
        prefix = query_start_match.group(1) if query_start_match else ''
        query_without_prefix = result[len(prefix):].strip() if prefix else result
        
        # Check if query starts with FROM (not SELECT, WITH, etc.)
        if not re.match(r'^\s*(select|with|insert|update|delete|create|alter|drop)\b', query_without_prefix, re.IGNORECASE):
            if re.match(r'^\s*from\b', query_without_prefix, re.IGNORECASE):
                # Check if SELECT appears later (for "from x select y" syntax)
                # Search in the query without prefix to avoid matching select in comments
                select_match = re.search(r'\bselect\s+', query_without_prefix, re.IGNORECASE)
                if select_match:
                    # Find the extent of the SELECT clause
                    # We need to find where the SELECT clause ends, which is at
                    # a keyword like WHERE, GROUP BY, LIMIT, QUALIFY, etc.
                    # But we need to skip keywords inside parentheses (like in OVER clauses)
                    select_start = select_match.end()
                    select_end = len(query_without_prefix)
                    
                    paren_depth = 0
                    i = select_start
                    while i < len(query_without_prefix):
                        char = query_without_prefix[i]
                        if char == '(':
                            paren_depth += 1
                        elif char == ')':
                            paren_depth -= 1
                        elif paren_depth == 0:
                            # Check for clause keywords at this position
                            remaining = query_without_prefix[i:].lower()
                            for kw in ['where ', 'group by ', 'order by ', 'limit ', 'having ', 'qualify ']:
                                if remaining.startswith(kw):
                                    select_end = i
                                    break
                            if select_end != len(query_without_prefix):
                                break
                        i += 1
                    
                    select_clause = query_without_prefix[select_start:select_end].strip()
                    before_select = query_without_prefix[:select_match.start()]
                    after_select = query_without_prefix[select_end:]
                    # Keep prefix (comments) at the front
                    result = f"{prefix}SELECT {select_clause} {before_select}{after_select}"
                else:
                    # Add SELECT * at front, keeping prefix
                    result = f"{prefix}SELECT * {query_without_prefix}"
        
        return result

    def _transform_distinct_on(self, text: str) -> str:
        """
        Transform ASQL distinct on (cols) to SQL DISTINCT ON.
        
        The distinct on clause should be moved to after SELECT.
        """
        result = text
        
        # Pattern: distinct on (cols) anywhere in query
        pattern = r'\bdistinct\s+on\s*\(([^)]+)\)'
        match = re.search(pattern, result, re.IGNORECASE)
        
        if match:
            cols = match.group(1).strip()
            # Remove distinct on from its current position
            before = result[:match.start()]
            after = result[match.end():]
            result = before.strip() + " " + after.strip()
            
            # Add DISTINCT ON after SELECT
            result = re.sub(r'\bSELECT\s+', f'SELECT DISTINCT ON ({cols}) ', result, count=1, flags=re.IGNORECASE)
        
        return result

    def _transform_star_column_override(self, text: str) -> str:
        """
        Transform SELECT *, expr AS col to SELECT * EXCEPT(col), expr AS col.
        
        This allows columns to be "overwritten" by explicit definitions.
        When you write `select *, upper(name) as name`, the explicit `name`
        definition should replace the original column, not create a duplicate.
        
        This uses SQL's EXCEPT/EXCLUDE syntax which is supported by:
        - BigQuery: * EXCEPT(col)
        - Snowflake: * EXCLUDE(col)  
        - DuckDB: * EXCLUDE(col)
        
        SQLGlot handles dialect translation automatically.
        
        Note: For dialects without EXCEPT support (PostgreSQL, MySQL, SQLite),
        the generated SQL will error at runtime - users need to list columns explicitly.
        """
        result = text
        
        # Find SELECT ... FROM pattern
        select_pattern = r'\bSELECT\s+(.*?)\s+FROM\b'
        select_match = re.search(select_pattern, result, re.IGNORECASE | re.DOTALL)
        
        if not select_match:
            return result
            
        select_clause = select_match.group(1)
        
        # Check if there's a bare * or table.* in the select
        star_pattern = r'(?:^|,\s*)(\*|[\w]+\.\*)(?:\s*,|\s*$)'
        star_match = re.search(star_pattern, select_clause)
        
        if not star_match:
            return result
            
        star_expr = star_match.group(1)  # Either "*" or "table.*"
        
        # Find all explicit aliases: "expr AS alias" patterns
        # Be careful to handle nested parens and complex expressions
        alias_pattern = r'\bAS\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:,|$)'
        aliases = re.findall(alias_pattern, select_clause, re.IGNORECASE)
        
        if not aliases:
            return result
            
        # Build EXCEPT clause
        except_cols = ', '.join(aliases)
        new_star = f'{star_expr} EXCEPT({except_cols})'
        
        # Replace the star in the select clause
        new_select_clause = re.sub(
            r'(?:^|(?<=,\s))(\*|[\w]+\.\*)(?=\s*,|\s*$)',
            new_star,
            select_clause,
            count=1
        )
        
        # Only apply if we actually made a change
        if new_select_clause != select_clause:
            result = result[:select_match.start(1)] + new_select_clause + result[select_match.end(1):]
        
        return result

    def _transform_sample_clause(self, text: str) -> str:
        """
        Transform ASQL sample clause to SQL.
        
        sample N → ORDER BY RANDOM() LIMIT N (or TABLESAMPLE for dialects that support it)
        sample N% → TABLESAMPLE SYSTEM(N) or ORDER BY RANDOM() LIMIT (N% of count)
        sample N per col → stratified sampling via window functions
        
        The transformation creates portable SQL that works across dialects:
        - For fixed N: ORDER BY RANDOM() LIMIT N (universally supported)
        - For percentage: Uses TABLESAMPLE where available, otherwise approximates
        - For stratified: Uses window functions with QUALIFY or subquery
        """
        result = text
        
        # Pattern 1: sample N per column (stratified sampling)
        # sample 100 per category → get N random rows per group value
        pattern_per = r'\bsample\s+(\d+)\s+per\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'
        match_per = re.search(pattern_per, result, re.IGNORECASE)
        if match_per:
            n = match_per.group(1)
            partition_col = match_per.group(2)
            # Transform to window function with QUALIFY
            # This selects N random rows per partition
            stratified_sql = (
                f"QUALIFY ROW_NUMBER() OVER (PARTITION BY {partition_col} ORDER BY RANDOM()) <= {n}"
            )
            result = result[:match_per.start()] + stratified_sql + result[match_per.end():]
            return result
        
        # Pattern 2: sample N% (percentage sampling)
        # sample 10% → random 10% of rows
        pattern_pct = r'\bsample\s+(\d+(?:\.\d+)?)\s*%'
        match_pct = re.search(pattern_pct, result, re.IGNORECASE)
        if match_pct:
            pct = match_pct.group(1)
            # Use TABLESAMPLE for efficiency where supported
            # Falls back to RANDOM() filter for dialects without TABLESAMPLE
            # TABLESAMPLE BERNOULLI(pct) is SQL standard
            sample_sql = f"TABLESAMPLE BERNOULLI({pct})"
            result = result[:match_pct.start()] + sample_sql + result[match_pct.end():]
            return result
        
        # Pattern 3: sample N (fixed number of rows)
        # sample 100 → random 100 rows
        pattern_n = r'\bsample\s+(\d+)\b(?!\s*%|\s+per\b)'
        match_n = re.search(pattern_n, result, re.IGNORECASE)
        if match_n:
            n = match_n.group(1)
            # Use ORDER BY RANDOM() LIMIT N for portability
            # This is slower than TABLESAMPLE but universally supported
            sample_sql = f"ORDER BY RANDOM() LIMIT {n}"
            result = result[:match_n.start()] + sample_sql + result[match_n.end():]
            return result
        
        return result

    def _transform_string_matching_operators(self, text: str) -> str:
        """
        Transform string matching operators to SQL LIKE/ILIKE.
        
        contains "pattern" → LIKE '%pattern%'
        icontains "pattern" → ILIKE '%pattern%' (or LOWER(column) LIKE LOWER('%pattern%'))
        starts with "pattern" → LIKE 'pattern%'
        istarts with "pattern" → case-insensitive version
        ends with "pattern" → LIKE '%pattern'
        iends with "pattern" → case-insensitive version
        matches "pattern" → LIKE pattern (with pattern as-is)
        
        Handles:
        - Simple columns: email contains "gmail"
        - Dotted columns: users.email contains "gmail"
        - Function calls: upper(name) contains "JOHN"
        - Complex expressions: coalesce(email, '') contains "gmail"
        """
        result = text
        
        # Pattern to match string literals (single or double quotes, handling escaped quotes)
        string_pattern = r'(?:"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
        
        # Transform each operator type
        operators = [
            ('icontains', 'ILIKE', '%{}%'),
            ('contains', 'LIKE', '%{}%'),
            ('istarts with', 'ILIKE', '{}%'),
            ('starts with', 'LIKE', '{}%'),
            ('iends with', 'ILIKE', '%{}'),
            ('ends with', 'LIKE', '%{}'),
            ('matches', 'LIKE', '{}'),
        ]
        
        for asql_op, sql_op, pattern_template in operators:
            # Pattern: <expression> <operator> <string_literal>
            # We need to find the operator, then work backwards for the expression
            # and forwards for the string literal
            # Handle multi-word operators by replacing spaces with \s+
            op_pattern = asql_op.replace(' ', r'\s+')
            pattern = rf'\b{op_pattern}\s+({string_pattern})'
            
            while True:
                match = re.search(pattern, result, re.IGNORECASE)
                if not match:
                    break
                
                op_start = match.start()
                op_end = match.end()
                
                # Find the start of the left-hand expression
                # Work backwards from operator, skipping whitespace
                expr_end = op_start
                expr_start = expr_end
                
                # Find where the expression starts (work backwards)
                i = expr_end - 1
                paren_depth = 0
                in_string = False
                string_char = None
                
                while i >= 0:
                    char = result[i]
                    
                    # Track string literals
                    if char in ('"', "'") and (i == len(result) - 1 or result[i+1] != '\\'):
                        if not in_string:
                            in_string = True
                            string_char = char
                        elif char == string_char:
                            in_string = False
                            string_char = None
                    
                    if not in_string:
                        if char == ')':
                            paren_depth += 1
                        elif char == '(':
                            paren_depth -= 1
                        elif paren_depth == 0:
                            # Stop at logical operators, comparison operators, or clause keywords
                            if char in (' ', '\t', '\n'):
                                # Check if preceding word is a keyword
                                remaining = result[:i+1]
                                if re.search(r'\b(and|or|not|where|group|order|limit|having|qualify)\s*$', remaining, re.IGNORECASE):
                                    expr_start = i + 1
                                    break
                            elif char in ('(', ',', '='):
                                # Stop before these characters
                                expr_start = i + 1
                                break
                    
                    i -= 1
                
                if i < 0:
                    expr_start = 0
                
                # Extract expression and string literal
                expr = result[expr_start:expr_end].strip()
                string_literal = match.group(1)  # The matched string literal
                
                # Remove quotes and escape SQL special characters
                quote_char = string_literal[0]
                pattern_value = string_literal[1:-1]  # Remove quotes
                # Escape single quotes for SQL (double them)
                pattern_value = pattern_value.replace("'", "''")
                # Escape backslashes
                pattern_value = pattern_value.replace('\\', '\\\\')
                
                # Apply pattern template (wrapping with % for contains/starts/ends)
                sql_pattern = pattern_template.format(pattern_value)
                
                # Build SQL expression
                # For case-insensitive operators, use ILIKE (PostgreSQL) or LOWER() LIKE LOWER() (others)
                if sql_op == 'ILIKE':
                    # Use ILIKE directly - SQLGlot will handle dialect translation
                    sql_expr = f"{expr} ILIKE '{sql_pattern}'"
                else:
                    sql_expr = f"{expr} LIKE '{sql_pattern}'"
                
                # Replace in result
                result = result[:expr_start] + sql_expr + result[op_end:]
        
        return result
