//! Layer 5: dialect-aware compiler passes (`asql/compiler/`, `asql/transpile.py`).
//!
//! Spine (gap-filling date series), fanout protection, alias reuse, metrics
//! and column operators all run here on the polyglot AST, with
//! `polyglot_sql::optimizer::{qualify_columns, annotate_types}` and `scope`
//! in place of `sqlglot.optimizer`. Pass-through until those are ported.

use polyglot_sql::{DialectType, Expression};

use crate::Result;

/// How a dialect orders NULLs by default (sqlglot's `NULL_ORDERING`), which
/// decides whether an `ORDER BY` term needs an explicit `NULLS FIRST/LAST`.
#[derive(Clone, Copy, PartialEq, Eq)]
enum NullOrdering {
    /// NULLs sort as the largest value: last in ASC, first in DESC (postgres, snowflake).
    Large,
    /// NULLs always sort last (duckdb).
    Last,
    /// No `NULLS FIRST/LAST` syntax at all (bigquery).
    Unsupported,
}

fn null_ordering(dialect: DialectType) -> NullOrdering {
    match dialect {
        DialectType::BigQuery => NullOrdering::Unsupported,
        DialectType::DuckDB => NullOrdering::Last,
        _ => NullOrdering::Large,
    }
}

/// Drop a `nulls_first` that is already the dialect's default, as sqlglot's
/// `ordered_sql` does, so the output carries only the placements that matter.
fn trim_null_ordering(query: Expression, write: DialectType) -> Expression {
    let Expression::Select(mut select) = query else {
        return query;
    };
    if let Some(order_by) = &mut select.order_by {
        for o in &mut order_by.expressions {
            let Some(nulls_first) = o.nulls_first else {
                continue;
            };
            let is_default = match null_ordering(write) {
                NullOrdering::Unsupported => true,
                NullOrdering::Last => !nulls_first,
                NullOrdering::Large => nulls_first == o.desc,
            };
            if is_default {
                o.nulls_first = None;
            }
        }
    }
    Expression::Select(select)
}

pub fn compile(query: Expression, write: DialectType) -> Result<Expression> {
    Ok(trim_null_ordering(query, write))
}
