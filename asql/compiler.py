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
        asql_query: ASQL query string
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
        
        # Check if this is a SET/CTE statement by checking the query text
        query_stripped = asql_query.strip()
        is_set_statement = query_stripped.lower().startswith("set ")
        
        # Parse ASQL to SQLGlot AST
        parser = ASQLParser(asql_query)
        select_expr = parser.parse()
        
        # If this was a SET statement, extract the CTE name and create WITH clause
        if is_set_statement:
            # Extract variable name from "set var_name = ..."
            parts = query_stripped.split("=", 1)
            if len(parts) == 2:
                var_part = parts[0].strip()
                # Remove "set" keyword
                if var_part.lower().startswith("set "):
                    cte_name = var_part[4:].strip()
                    
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
                        select_from_cte.set("from_", exp.From(this=exp.Table(this=exp.Identifier(this=cte_name))))
                        # Set WITH clause on the SELECT (SQLGlot uses 'with_' not 'with')
                        select_from_cte.set("with_", exp.With(expressions=[cte]))
                        
                        sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
                        sql = select_from_cte.sql(dialect=sql_dialect, pretty=pretty)
                        return sql
        
        # Generate SQL
        sql_dialect = Dialect.get_or_raise(dialect) if dialect else None
        sql = select_expr.sql(dialect=sql_dialect, pretty=pretty)
        
        return sql
        
    except ASQLSyntaxError:
        raise
    except sqlglot.errors.ParseError as e:
        raise ASQLSyntaxError(f"ASQL syntax error: {e}") from e
    except Exception as e:
        raise ASQLCompilationError(f"Compilation error: {e}") from e

