//! ASQL on polyglot-sql: the Rust cutover, layer by layer.
//!
//! The Python package uses sqlglot for everything below the ASQL grammar. This
//! crate keeps that split and swaps sqlglot for polyglot-sql (its Rust port).
//! Each module below is one layer of the cutover and says which Python module
//! it replaces and what polyglot-sql supplies for it.
//!
//! | Layer | Python today | Rust (this crate) | polyglot-sql supplies |
//! |---|---|---|---|
//! | 1. Tokenizer | `asql/dialect/tokenizer.py` subclasses `sqlglot.Tokenizer` | [`tokenizer`]: the `asql` custom dialect | `CustomDialectBuilder`, `TokenizerConfig`, `Tokenizer` |
//! | 2. Pipeline parser | `asql/dialect/parser.py` subclasses `sqlglot.Parser` (FROM-first steps, `TRANSFORM_PARSERS`) | [`pipeline`]: owns the step grammar, builds `Select` | `Expression` AST, `builder` |
//! | 3. Expression grammar | inherited from `sqlglot.Parser` with ~80 overrides | [`expr`]: ASQL sugar (`==`, `-col`, `#`) then polyglot for the SQL inside | `Parser::with_config` + public `parse_assignment`, `parse_alias_with_expr`, `parse_ordered`, `parse_table_parts` |
//! | 4. Parser-stage transforms | `asql/dialect/transforms/*` (auto alias, auto qualify, count entity, join inference, ...) | [`transforms`] | AST walkers (`traversal`, `ast_transforms`) |
//! | 5. Compiler passes | `asql/compiler/*` (spine, fanout, alias reuse, metrics) and `asql/transpile.py` | [`compiler`] | `optimizer::qualify_columns`, `annotate_types`, `scope` |
//! | 6. SQL generation | `ast.sql(dialect=write)` | [`generator`] | `generate`, `Generator`, 38 dialect generators |
//! | 7. SQL → ASQL | `asql/dialect/generator.py` (sqlglot `Generator` subclass) | not started; needs polyglot generator hooks or our own ASQL generator | `parse` of any dialect |
//! | 8. Visual ASQL JSON | `asql/visual_dialect`, `asql/json_schema.py` | not started | `ast_json` (serde round trip of the AST) |
//! | 9. Bindings | FastAPI playground, Python package | not started | WASM (`polyglot-sql-wasm`), PyO3 |
//!
//! Status: layers 1, 2, 3 and 6 work for the slice in `tests/parity.rs`
//! (`from`, `where`, `select`, `group by` with an aggregate block, `order by`
//! with `-col`, `limit`); layer 4 has auto alias; layer 5 is a pass-through.
//! Python asql remains the oracle: `tests/fixtures/parity.json` is generated
//! from it and the test compares ASTs per dialect.

pub mod compiler;
pub mod expr;
pub mod generator;
pub mod pipeline;
pub mod tokenizer;
pub mod transforms;

pub use polyglot_sql::{DialectType, Expression};

/// A failure in any layer; the message says which.
#[derive(Debug)]
pub struct Error(pub String);

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for Error {}

impl From<polyglot_sql::Error> for Error {
    fn from(e: polyglot_sql::Error) -> Self {
        Error(format!("polyglot-sql: {e}"))
    }
}

pub type Result<T> = std::result::Result<T, Error>;

/// Compile one ASQL query to SQL in `write`, through every layer in order.
pub fn transpile(asql: &str, write: DialectType) -> Result<String> {
    let tokens = tokenizer::tokenize(asql)?;
    let query = pipeline::parse(tokens)?;
    let query = transforms::apply(query)?;
    let query = compiler::compile(query, write)?;
    generator::generate(&query, write)
}
