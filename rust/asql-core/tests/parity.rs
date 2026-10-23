//! Python asql is the oracle. `fixtures/parity.json` holds its output per
//! dialect (regenerate with `fixtures/gen_parity.py`); both sides are
//! canonicalized through polyglot (parse in the dialect, generate again) so
//! the comparison is by AST, not spelling.

use std::str::FromStr;

use polyglot_sql::DialectType;
use serde::Deserialize;
use std::collections::BTreeMap;

#[derive(Deserialize)]
struct Row {
    asql: String,
    sql: BTreeMap<String, String>,
}

fn canonical(sql: &str, dialect: DialectType) -> String {
    let ast = polyglot_sql::parse_one(sql, dialect).expect("oracle SQL parses");
    polyglot_sql::generate(&ast, dialect).expect("oracle SQL generates")
}

#[test]
fn matches_python_asql() {
    let rows: Vec<Row> =
        serde_json::from_str(include_str!("fixtures/parity.json")).expect("fixture");
    let mut failures = Vec::new();
    for row in &rows {
        for (name, expected) in &row.sql {
            let dialect = DialectType::from_str(name).expect("dialect name");
            match asql_core::transpile(&row.asql, dialect) {
                Ok(got) if got == canonical(expected, dialect) => {}
                Ok(got) => failures.push(format!(
                    "{name}: {}\n  python: {expected}\n  rust:   {got}",
                    row.asql
                )),
                Err(e) => failures.push(format!("{name}: {}\n  error: {e}", row.asql)),
            }
        }
    }
    assert!(failures.is_empty(), "\n{}", failures.join("\n\n"));
}
