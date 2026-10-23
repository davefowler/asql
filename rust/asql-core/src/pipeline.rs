//! Layer 2: the FROM-first pipeline.
//!
//! This is the grammar asql owns (`asql/dialect/parser.py`'s
//! `TRANSFORM_PARSERS`). The token stream is cut into steps at step keywords
//! (depth 0), each step's tokens go to [`crate::expr`], and the result is one
//! polyglot `Select`. Steps that need a CTE boundary (a `where` after an
//! aggregate block, `stash`, joins, `spine by`, ...) are the next slice of
//! work; this driver covers the straight-line case.

use polyglot_sql::expressions::{From, GroupBy, Limit, Literal, OrderBy, Select, Star, Where};
use polyglot_sql::{Expression, Token, TokenType};

use crate::expr;
use crate::{Error, Result};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Step {
    From,
    Where,
    Select,
    GroupBy,
    OrderBy,
    Limit,
}

/// The step keyword starting at `tokens[i]`, and how many tokens it spans.
/// polyglot tokenizes `GROUP BY` as two tokens (sqlglot makes it one).
fn step_keyword(tokens: &[Token], i: usize) -> Option<(Step, usize)> {
    let next_is_by = tokens.get(i + 1).map(|t| t.token_type) == Some(TokenType::By);
    match tokens[i].token_type {
        TokenType::From => Some((Step::From, 1)),
        TokenType::Where => Some((Step::Where, 1)),
        TokenType::Select => Some((Step::Select, 1)),
        TokenType::GroupBy => Some((Step::GroupBy, 1)),
        TokenType::OrderBy => Some((Step::OrderBy, 1)),
        TokenType::Group if next_is_by => Some((Step::GroupBy, 2)),
        TokenType::Order if next_is_by => Some((Step::OrderBy, 2)),
        TokenType::Limit => Some((Step::Limit, 1)),
        _ => None,
    }
}

/// Cut the stream into `(step, tokens)` pairs at depth-0 step keywords;
/// `|` separators are dropped.
fn split_steps(tokens: &[Token]) -> Result<Vec<(Step, &[Token])>> {
    let mut steps: Vec<(Step, usize, usize)> = Vec::new();
    let mut depth = 0i32;
    for (i, t) in tokens.iter().enumerate() {
        match t.token_type {
            TokenType::LParen => depth += 1,
            TokenType::RParen => depth -= 1,
            _ => {}
        }
        if depth == 0 {
            if let Some((step, width)) = step_keyword(tokens, i) {
                if let Some(last) = steps.last_mut() {
                    last.2 = i;
                }
                steps.push((step, i + width, tokens.len()));
            }
        }
    }
    match steps.first() {
        Some((Step::From, _, _)) => {}
        _ => return Err(Error("an ASQL query starts with `from`".into())),
    }
    Ok(steps
        .into_iter()
        .map(|(s, a, b)| {
            let slice = &tokens[a..b];
            let slice = match slice.last() {
                Some(t) if t.token_type == TokenType::PipeGt => &slice[..slice.len() - 1],
                _ => slice,
            };
            (s, slice)
        })
        .collect())
}

/// Build one `Select` from the tokens of a whole query.
pub fn parse(tokens: Vec<Token>) -> Result<Expression> {
    let tokens: Vec<Token> = tokens
        .into_iter()
        .filter(|t| !matches!(t.token_type, TokenType::Eof | TokenType::Semicolon))
        .collect();
    let mut select = Select {
        expressions: vec![star()],
        ..Select::default()
    };
    for (step, slice) in split_steps(&tokens)? {
        match step {
            Step::From => {
                select.from = Some(From {
                    expressions: vec![expr::parse_table(slice)?],
                });
            }
            Step::Where => {
                let cond = expr::parse_condition(slice)?;
                select.where_clause = Some(Where { this: cond });
            }
            Step::Select => {
                select.expressions = expr::split_csv(slice)
                    .into_iter()
                    .map(expr::parse_aliased)
                    .collect::<Result<_>>()?;
            }
            Step::GroupBy => {
                // `group by k1, k2 (agg1, agg2)`: keys before the block, the
                // block is the projection together with the keys.
                let (keys, block) = split_aggregate_block(slice);
                let keys: Vec<Expression> = expr::split_csv(keys)
                    .into_iter()
                    .map(expr::parse_bare)
                    .collect::<Result<_>>()?;
                if let Some(block) = block {
                    let aggs: Vec<Expression> = expr::split_csv(block)
                        .into_iter()
                        .map(expr::parse_aliased)
                        .collect::<Result<_>>()?;
                    select.expressions = keys.iter().cloned().chain(aggs).collect();
                }
                select.group_by = Some(GroupBy {
                    expressions: keys,
                    all: None,
                    totals: false,
                    comments: vec![],
                });
            }
            Step::OrderBy => {
                let ordered = expr::split_csv(slice)
                    .into_iter()
                    .map(expr::parse_ordered)
                    .map(|e| match e? {
                        Expression::Ordered(o) => Ok(*o),
                        other => Err(Error(format!("not an order term: {other:?}"))),
                    })
                    .collect::<Result<_>>()?;
                select.order_by = Some(OrderBy {
                    expressions: ordered,
                    siblings: false,
                    comments: vec![],
                });
            }
            Step::Limit => {
                let n: u64 = match slice {
                    [t] if t.token_type == TokenType::Number => t
                        .text
                        .parse()
                        .map_err(|_| Error(format!("bad limit `{}`", t.text)))?,
                    _ => return Err(Error("`limit` takes one number".into())),
                };
                select.limit = Some(Limit {
                    this: Expression::Literal(Box::new(Literal::Number(n.to_string()))),
                    percent: false,
                    comments: vec![],
                });
            }
        }
    }
    Ok(Expression::Select(Box::new(select)))
}

fn star() -> Expression {
    Expression::Star(Star {
        table: None,
        except: None,
        replace: None,
        rename: None,
        trailing_comments: vec![],
        span: None,
    })
}

/// `k1, k2 (agg, ...)` → (`k1, k2`, Some(`agg, ...`)): the block is a trailing
/// depth-0 parenthesis group. After a bare name the group is ambiguous with a
/// function call (`month(created_at)` vs `region (sum(amount))`); the rule is
/// Python asql's `_looks_like_aggregate_block_at`: a block has an alias, a
/// comma or `#` at its top level, or follows a name that is not a known
/// key function.
fn split_aggregate_block(tokens: &[Token]) -> (&[Token], Option<&[Token]>) {
    if tokens.last().map(|t| t.token_type) != Some(TokenType::RParen) {
        return (tokens, None);
    }
    let mut depth = 0i32;
    let mut open = None;
    for i in (0..tokens.len()).rev() {
        match tokens[i].token_type {
            TokenType::RParen => depth += 1,
            TokenType::LParen => {
                depth -= 1;
                if depth == 0 {
                    open = Some(i);
                    break;
                }
            }
            _ => {}
        }
    }
    let Some(open) = open else {
        return (tokens, None);
    };
    let inner = &tokens[open + 1..tokens.len() - 1];
    let follows_name = open > 0
        && matches!(
            tokens[open - 1].token_type,
            TokenType::Var | TokenType::Identifier
        );
    if follows_name {
        let name = tokens[open - 1].text.to_ascii_uppercase();
        let known_key_function = KEY_FUNCTIONS.contains(&name.as_str());
        let mut d = 0i32;
        let mut looks_like_block = false;
        for t in inner {
            match t.token_type {
                TokenType::LParen => d += 1,
                TokenType::RParen => d -= 1,
                TokenType::As | TokenType::Alias | TokenType::Comma | TokenType::Hash if d == 0 => {
                    looks_like_block = true;
                }
                _ => {}
            }
        }
        if known_key_function && !looks_like_block {
            return (tokens, None);
        }
    }
    (&tokens[..open], Some(inner))
}

/// Functions that may appear as a `group by` key followed by `(`; a bare
/// `(...)` after any other name is an aggregate block.
const KEY_FUNCTIONS: &[&str] = &[
    "YEAR",
    "QUARTER",
    "MONTH",
    "WEEK",
    "DAY",
    "HOUR",
    "MINUTE",
    "SECOND",
    "DATE_TRUNC",
    "DATE",
    "BUCKET",
    "SLUGIFY",
    "LOWER",
    "UPPER",
    "COALESCE",
];
