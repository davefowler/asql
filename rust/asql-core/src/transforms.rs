//! Layer 4: parser-stage transforms (`asql/dialect/transforms/`).
//!
//! Only auto alias is here so far: an unaliased aggregate in a projection
//! gets `<func>_<column>` (`sum(amount)` → `sum_amount`, `count(*)` → `num`),
//! the convention `asql/dialect/transforms/auto_alias.py` implements. Auto
//! qualify, count entity, join inference, date units, underscore shorthands
//! and pivot group-by are the rest of this layer.

use polyglot_sql::expressions::{Alias, Identifier};
use polyglot_sql::traversal::transform_all;
use polyglot_sql::Expression;

use crate::Result;

fn implicit_alias(e: &Expression) -> Option<String> {
    match e {
        Expression::Count(c) if c.star => Some("num".into()),
        Expression::Function(f) => {
            let mut parts = vec![f.name.to_ascii_lowercase()];
            for a in &f.args {
                match a {
                    Expression::Column(c) => parts.push(c.name.name.to_ascii_lowercase()),
                    _ => return None,
                }
            }
            Some(parts.join("_"))
        }
        // polyglot has typed nodes for common aggregates; name them the same way.
        Expression::Sum(a) | Expression::Avg(a) | Expression::Min(a) | Expression::Max(a) => {
            let name = match e {
                Expression::Sum(_) => "sum",
                Expression::Avg(_) => "avg",
                Expression::Min(_) => "min",
                _ => "max",
            };
            match &a.this {
                Expression::Column(c) => {
                    Some(format!("{name}_{}", c.name.name.to_ascii_lowercase()))
                }
                _ => None,
            }
        }
        _ => None,
    }
}

/// sqlglot upper-cases function names on output (`normalize_functions="upper"`);
/// polyglot keeps the written case for functions it did not type, so do it
/// on the AST instead, once, for every dialect.
fn uppercase_functions(query: Expression) -> Result<Expression> {
    Ok(transform_all(query, &|e| {
        Ok(match e {
            Expression::Function(mut f) => {
                f.name = f.name.to_ascii_uppercase();
                Expression::Function(f)
            }
            // Typed aggregates remember the written name; BigQuery prints it as is.
            Expression::Sum(mut a) => {
                a.name = a.name.map(|n| n.to_ascii_uppercase());
                Expression::Sum(a)
            }
            Expression::Avg(mut a) => {
                a.name = a.name.map(|n| n.to_ascii_uppercase());
                Expression::Avg(a)
            }
            Expression::Min(mut a) => {
                a.name = a.name.map(|n| n.to_ascii_uppercase());
                Expression::Min(a)
            }
            Expression::Max(mut a) => {
                a.name = a.name.map(|n| n.to_ascii_uppercase());
                Expression::Max(a)
            }
            other => other,
        })
    })?)
}

/// Alias unaliased aggregates in the projection; normalize function names.
pub fn apply(query: Expression) -> Result<Expression> {
    let query = uppercase_functions(query)?;
    let Expression::Select(mut select) = query else {
        return Ok(query);
    };
    select.expressions = select
        .expressions
        .into_iter()
        .map(|e| match implicit_alias(&e) {
            Some(name) => Expression::Alias(Box::new(Alias::new(e, Identifier::new(name)))),
            None => e,
        })
        .collect();
    Ok(Expression::Select(select))
}
