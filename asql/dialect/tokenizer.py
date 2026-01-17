"""ASQL Tokenizer.

Handles ASQL-specific token mappings for the lexer.
"""

from sqlglot.tokens import Tokenizer, TokenType


class ASQLTokenizer(Tokenizer):
    """Tokenizer for ASQL syntax.
    
    Key mappings:
    - `|` → PIPE_GT to reuse SQLGlot's pipe syntax infrastructure
    - `#` → HASH for COUNT() shorthand
    - `&` → AMP for INNER JOIN
    - `&?` → QMARK_AMP for LEFT JOIN
    - `?&` → QMARK_AMP for RIGHT JOIN (differentiated by text)
    - `?&?` → uses PLACEHOLDER token (differentiated by text)
    - `*` → STAR for CROSS JOIN (context-dependent)
    
    String handling:
    - Single quotes (') are string literals (SQL standard)
    - Double quotes (") are string literals (ASQL accepts both)
    - Backticks (`) are identifiers (for column/table names with special chars)
    """
    
    IDENTIFIERS = ["`"]  # Only backticks for identifiers
    QUOTES = ["'", '"']  # Both ' and " for strings
    
    SINGLE_TOKENS = {
        **Tokenizer.SINGLE_TOKENS,
        "|": TokenType.PIPE_GT,  # Map | to |> to reuse BigQuery's pipe infrastructure
        "#": TokenType.HASH,     # For COUNT(*) shorthand
    }
    
    KEYWORDS = {
        **Tokenizer.KEYWORDS,
        # ASQL-specific keywords
        "STASH": TokenType.VAR,
        "PER": TokenType.VAR,
        "EXTEND": TokenType.VAR,
        "RECURSE": TokenType.VAR,  # For recursive CTEs
        
        # Natural language alternatives
        "OTHERWISE": TokenType.ELSE,  # Alias for ELSE in when expressions
        
        # Join operators (multi-char tokens)
        "?&?": TokenType.PLACEHOLDER,  # FULL OUTER JOIN
        "&?": TokenType.QMARK_AMP,     # LEFT JOIN
        "?&": TokenType.QMARK_AMP,     # RIGHT JOIN
    }
