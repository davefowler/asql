//! Layer 6: SQL generation. Entirely polyglot-sql's; the ASQL output dialect
//! (SQL → ASQL, `asql/dialect/generator.py`) is layer 7 and not started.

use polyglot_sql::{DialectType, Expression};

use crate::Result;

pub fn generate(query: &Expression, write: DialectType) -> Result<String> {
    Ok(polyglot_sql::generate(query, write)?)
}
