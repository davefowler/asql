use std::str::FromStr;
use polyglot_sql::DialectType;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Deserialize)]
struct Row { id: String, dialect: String, sql: String, identity: Option<String>, cross: BTreeMap<String, Option<String>> }

#[derive(Serialize)]
struct Out { id: String, dialect: String, sql: String, identity_py: Option<String>, identity_rs: Result<String, String>, cross: BTreeMap<String, (Option<String>, Result<String, String>)> }

fn tp(sql: &str, r: &str, w: &str) -> Result<String, String> {
    let rd = DialectType::from_str(r).map_err(|e| format!("dialect {r}: {e}"))?;
    let wd = DialectType::from_str(w).map_err(|e| format!("dialect {w}: {e}"))?;
    let out = std::panic::catch_unwind(|| polyglot_sql::transpile(sql, rd, wd)).map_err(|_| "PANIC".to_string())?;
    out.map(|v| v.join("; ")).map_err(|e| e.to_string())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let rows: Vec<Row> = serde_json::from_str(&std::fs::read_to_string(&args[1]).unwrap()).unwrap();
    let mut outs = vec![];
    for r in rows {
        let identity_rs = tp(&r.sql, &r.dialect, &r.dialect);
        let mut cross = BTreeMap::new();
        for (w, py) in &r.cross { cross.insert(w.clone(), (py.clone(), tp(&r.sql, &r.dialect, w))); }
        outs.push(Out { id: r.id, dialect: r.dialect, sql: r.sql, identity_py: r.identity, identity_rs, cross });
    }
    std::fs::write(&args[2], serde_json::to_string_pretty(&outs).unwrap()).unwrap();
}
