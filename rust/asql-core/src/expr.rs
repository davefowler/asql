//! Layer 3: expressions inside a pipeline step.
//!
//! ASQL's expression grammar is SQL's plus sugar. The sugar is handled here at
//! the token level; the SQL is handed to polyglot-sql's parser through its
//! public entry points, one token slice at a time. Nothing in polyglot's
//! private parser internals is needed for that.

use polyglot_sql::expressions::{Alias, CountFunc, Identifier, Ordered};
use polyglot_sql::parser::{Parser, ParserConfig};
use polyglot_sql::{DialectType, Expression, Token, TokenType};

use crate::{Error, Result};

fn parser(tokens: &[Token]) -> Parser {
    let config = ParserConfig {
        dialect: Some(DialectType::PostgreSQL),
        ..ParserConfig::default()
    };
    Parser::with_config(tokens.to_vec(), config)
}

fn text(tokens: &[Token]) -> String {
    tokens
        .iter()
        .map(|t| t.text.as_str())
        .collect::<Vec<_>>()
        .join(" ")
}

/// Split a slice at depth-0 commas.
pub fn split_csv(tokens: &[Token]) -> Vec<&[Token]> {
    let mut parts = Vec::new();
    let mut depth = 0i32;
    let mut start = 0;
    for (i, t) in tokens.iter().enumerate() {
        match t.token_type {
            TokenType::LParen => depth += 1,
            TokenType::RParen => depth -= 1,
            TokenType::Comma if depth == 0 => {
                parts.push(&tokens[start..i]);
                start = i + 1;
            }
            _ => {}
        }
    }
    if start < tokens.len() {
        parts.push(&tokens[start..]);
    }
    parts
}

/// `#` → `COUNT(*)`; otherwise polyglot's `parse_assignment` (the entry point
/// sqlglot's `_parse_expression` uses before alias handling).
pub fn parse_bare(tokens: &[Token]) -> Result<Expression> {
    if tokens.len() == 1 && tokens[0].token_type == TokenType::Hash {
        return Ok(Expression::Count(Box::new(CountFunc {
            this: None,
            star: true,
            distinct: false,
            filter: None,
            ignore_nulls: None,
            original_name: None,
            inferred_type: None,
        })));
    }
    let mut p = parser(tokens);
    p.parse_assignment()?
        .ok_or_else(|| Error(format!("expected an expression at `{}`", text(tokens))))
}

/// An expression with an optional `as alias` (or implicit alias).
pub fn parse_aliased(tokens: &[Token]) -> Result<Expression> {
    if tokens.is_empty() {
        return Err(Error("expected an expression, found nothing".into()));
    }
    // `# as n` / `#` : alias handling is ours because `#` is ours.
    if tokens[0].token_type == TokenType::Hash {
        let count = parse_bare(&tokens[..1])?;
        return match &tokens[1..] {
            [] => Ok(count),
            [as_kw, name] if matches!(as_kw.token_type, TokenType::As | TokenType::Alias) => {
                Ok(Expression::Alias(Box::new(Alias::new(
                    count,
                    Identifier::new(name.text.clone()),
                ))))
            }
            rest => Err(Error(format!("unexpected `{}` after #", text(rest)))),
        };
    }
    let mut p = parser(tokens);
    let this = p
        .parse_assignment()?
        .ok_or_else(|| Error(format!("expected an expression at `{}`", text(tokens))))?;
    p.parse_alias_with_expr(Some(this))?
        .ok_or_else(|| Error(format!("expected an expression at `{}`", text(tokens))))
}

/// A condition (`where`, `having`): no alias.
pub fn parse_condition(tokens: &[Token]) -> Result<Expression> {
    parse_bare(tokens)
}

/// An `order by` term: `-col` is descending. Null placement follows the
/// Python package: explicit `NULLS LAST` when descending, `NULLS FIRST`
/// otherwise, so every dialect sorts the same way.
pub fn parse_ordered(tokens: &[Token]) -> Result<Expression> {
    let (desc, rest) = match tokens {
        [first, rest @ ..] if first.token_type == TokenType::Dash => (true, rest),
        _ => (false, tokens),
    };
    let this = parse_bare(rest)?;
    Ok(Expression::Ordered(Box::new(Ordered {
        this,
        desc,
        nulls_first: Some(!desc),
        explicit_asc: false,
        nulls_auto: false,
        with_fill: None,
    })))
}

/// A `from` source: a (dotted) table name, via polyglot. Aliases, subqueries
/// and samples are the next slice. (polyglot's public `parse_table` is a stub
/// in 0.13.3; `parse_table_parts` is the working entry point.)
pub fn parse_table(tokens: &[Token]) -> Result<Expression> {
    let mut p = parser(tokens);
    let table = p
        .parse_table_parts()?
        .ok_or_else(|| Error(format!("expected a table at `{}`", text(tokens))))?;
    Ok(table)
}
