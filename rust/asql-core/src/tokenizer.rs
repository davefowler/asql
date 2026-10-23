//! Layer 1: the ASQL tokenizer as a polyglot-sql custom dialect.
//!
//! Mirrors `asql/dialect/tokenizer.py`: `|` is the pipe step separator, `#` is
//! the `COUNT(*)` shorthand, `==` is equality, double quotes are strings and
//! backticks are identifiers. Registered once, under the name `asql`, on top of
//! polyglot's PostgreSQL tokenizer config.

use std::sync::OnceLock;

use polyglot_sql::dialects::{CustomDialectBuilder, Dialect, DialectType};
use polyglot_sql::{Token, TokenType};

use crate::{Error, Result};

const NAME: &str = "asql";

fn dialect() -> &'static Dialect {
    static DIALECT: OnceLock<Dialect> = OnceLock::new();
    DIALECT.get_or_init(|| {
        CustomDialectBuilder::new(NAME)
            .based_on(DialectType::PostgreSQL)
            .tokenizer_config_modifier(|tc| {
                tc.single_tokens.insert('|', TokenType::PipeGt);
                tc.single_tokens.insert('#', TokenType::Hash);
                tc.keywords.insert("==".to_string(), TokenType::Eq);
                tc.keywords.insert("OTHERWISE".to_string(), TokenType::Else);
                for kw in ["STASH", "PER", "EXTEND", "RECURSE", "SPINE"] {
                    tc.keywords.insert(kw.to_string(), TokenType::Var);
                }
                // Strings may use either quote; identifiers use backticks only.
                tc.quotes.insert("\"".to_string(), "\"".to_string());
                tc.identifiers.clear();
                tc.identifiers.insert('`', '`');
            })
            .register()
            .expect("asql dialect registers once");
        Dialect::get_by_name(NAME).expect("asql dialect registered")
    })
}

/// Tokenize ASQL text.
pub fn tokenize(asql: &str) -> Result<Vec<Token>> {
    dialect()
        .tokenize(asql)
        .map_err(|e| Error(format!("tokenizer: {e}")))
}
