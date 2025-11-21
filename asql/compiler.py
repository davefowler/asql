"""ASQL compiler - transforms ASQL to SQL."""

from typing import Optional
import sqlglot
from sqlglot import exp
from sqlglot.dialects import Dialect

from asql.errors import ASQLCompilationError, ASQLSyntaxError
from asql.parser import ASQLParser


def compile(
    asql_query: str,
    dialect: Optional[str] = None,
    pretty: bool = False,
) -> str:
    """
    Compile ASQL query to SQL.
    
    Args:
        asql_query: ASQL query string (can contain multiple queries separated by semicolons)
        dialect: Target SQL dialect (e.g., 'postgres', 'mysql', 'bigquery')
        pretty: Whether to format SQL output
    
    Returns:
        SQL query string
    
    Raises:
        ASQLSyntaxError: If ASQL syntax is invalid
        ASQLCompilationError: If compilation fails
    """
    try:
        if not asql_query.strip():
            raise ASQLSyntaxError("Empty ASQL query")
        
        # Split by semicolons to handle multiple queries
        query_parts = [q.strip() for q in asql_query.split(';') if q.strip()]
        
        if not query_parts:
            raise ASQLSyntaxError("No valid queries found")
        
        # If only one query, handle it normally
        if len(query_parts) == 1:
            return _compile_single_query(query_parts[0], dialect, pretty)
        
        # Multiple queries: collect all CTEs and combine them
        all_ctes = {}  # Map of CTE name to CTE expression
        final_queries = []
        
        for query_part in query_parts:
            # Check if this is a WITH/CTE statement
            query_stripped = query_part.strip()
            is_with_statement = query_stripped.lower().startswith("with ")
            
            if is_with_statement:
                # Handle WITH statement
                parser = ASQLParser(query_part)
                select_expr = parser.parse()
                
                if hasattr(select_expr, "meta") and select_expr.meta.get("_is_cte"):
                    cte_name = select_expr.meta.get("_cte_name")
                    if cte_name:
                        # Store CTE for later use
                        clean_select = exp.Select()
                        for key, value in select_expr.args.items():
                            if key not in ["_is_cte", "_cte_name"]:
                                clean_select.set(key, value)
                        
                        cte = exp.CTE(
                            this=clean_select,
                            alias=exp.TableAlias(this=exp.Identifier(this=cte_name))
                        )
                        all_ctes[cte_name] = cte
                        # Create a SELECT that uses the CTE
                        select_from_cte = exp.Select()
                        select_from_cte.set("expressions", [exp.Star()])
                        # SQLGlot uses 'from' as the key, but it's a Python keyword, so we use args dict directly
                        select_from_cte.args["from"] = exp.From(this=exp.Table(this=exp.Identifier(this=cte_name)))
                        final_queries.append(select_from_cte)
            else:
                # Regular pipeline query
                parser = ASQLParser(query_part)
                select_expr = parser.parse()
                
                # Extract CTEs from this query if it has a WITH clause
                with_clause = select_expr.args.get("with_")
                if with_clause and isinstance(with_clause, exp.With):
                    for cte_expr in with_clause.expressions:
                        if isinstance(cte_expr, exp.CTE):
                            # Extract CTE name from alias
                            cte_name = None
                            if cte_expr.alias:
                                if isinstance(cte_expr.alias, exp.TableAlias):
                                    if isinstance(cte_expr.alias.this, exp.Identifier):
                                        cte_name = cte_expr.alias.this.name
                                elif isinstance(cte_expr.alias, str):
                                    cte_name = cte_expr.alias
                            if cte_name:
                                all_ctes[cte_name] = cte_expr
                
                final_queries.append(select_expr)
        
        # Combine all CTEs into the final query
        if all_ctes and final_queries:
            # Use the last query as the final SELECT
            final_select = final_queries[-1]
            
            # Merge all CTEs
            existing_ctes = []
            with_clause = final_select.args.get("with_")
            if with_clause and isinstance(with_clause, exp.With):
                existing_ctes = list(with_clause.expressions)
            
            # Add all stored CTEs
            for cte_name, cte_expr in all_ctes.items():
                # Check if CTE already exists
                cte_exists = False
                for cte in existing_ctes:
                    if isinstance(cte, exp.CTE):
                        existing_name = None
                        if cte.alias:
                            if isinstance(cte.alias, exp.TableAlias):
                                if isinstance(cte.alias.this, exp.Identifier):
                                    existing_name = cte.alias.this.name
                            elif isinstance(cte.alias, str):
                                existing_name = cte.alias
                        if existing_name == cte_name:
                            cte_exists = True
                            break
                if not cte_exists:
                    existing_ctes.append(cte_expr)
            
            if existing_ctes:
                # SQLGlot uses 'with' as the key, but it's a Python keyword, so we use args dict directly
                final_select.args["with"] = exp.With(expressions=existing_ctes)
            
            sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
            return final_select.sql(dialect=sql_dialect, pretty=pretty)
        
        # Fallback: compile queries separately
        sql_parts = []
        for query_part in query_parts:
            sql_parts.append(_compile_single_query(query_part, dialect, pretty))
        return ";\n\n".join(sql_parts)
        
    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e


def _compile_single_query(
    asql_query: str,
    dialect: Optional[str] = None,
    pretty: bool = False,
) -> str:
    """Compile a single ASQL query to SQL."""
    # Check if this is a WITH/CTE statement by checking the query text
    query_stripped = asql_query.strip()
    is_with_statement = query_stripped.lower().startswith("with ")
    
    # Parse ASQL to SQLGlot AST
    parser = ASQLParser(asql_query)
    select_expr = parser.parse()
    
    # If this was a WITH statement, extract the CTE name from parser metadata
    if is_with_statement and hasattr(select_expr, "meta") and select_expr.meta.get("_is_cte"):
        cte_name = select_expr.meta.get("_cte_name")
        
        if cte_name:
            # Create a clean copy of the SELECT (without CTE metadata)
            clean_select = exp.Select()
            for key, value in select_expr.args.items():
                if key not in ["_is_cte", "_cte_name"]:
                    clean_select.set(key, value)
            
            # Create WITH clause
            cte = exp.CTE(
                this=clean_select,
                alias=exp.TableAlias(this=exp.Identifier(this=cte_name))
            )
            # Create a SELECT that uses the CTE
            select_from_cte = exp.Select()
            select_from_cte.set("expressions", [exp.Star()])
            # SQLGlot uses 'from' and 'with' as keys, but they're Python keywords, so we use args dict directly
            select_from_cte.args["from"] = exp.From(this=exp.Table(this=exp.Identifier(this=cte_name)))
            select_from_cte.args["with"] = exp.With(expressions=[cte])
            
            sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
            sql = select_from_cte.sql(dialect=sql_dialect, pretty=pretty)
            return sql
    
    # Generate SQL
    sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
    sql = select_expr.sql(dialect=sql_dialect, pretty=pretty)
    
    return sql

