# Rust sqlglot spike

Measures [polyglot-sql](https://crates.io/crates/polyglot-sql), a Rust port of
sqlglot, against Python sqlglot on the SQL that asql emits. Findings and the
strategy are in `ai_notes/rust-sqlglot-spike-2026-10-23.md`. Not wired into
`just check`: the crate is 325k lines and takes ~15 minutes to build.

```sh
# 1. corpus: every playground example x six target dialects, plus sqlglot's
#    identity and cross-dialect transpile of each (the "answer key")
uv run --all-extras --locked python spike/rust-sqlglot/build_corpus.py spike/rust-sqlglot/corpus.json   # add --comments to keep asql's comment passthrough

# 2. same transpiles through polyglot-sql
cargo run --release --manifest-path spike/rust-sqlglot/Cargo.toml -- spike/rust-sqlglot/corpus.json spike/rust-sqlglot/results.json

# 3. compare: exact, AST-equal (both reparsed by sqlglot in the write dialect), mismatch, error
uv run --all-extras --locked python spike/rust-sqlglot/compare.py spike/rust-sqlglot/results.json
```
