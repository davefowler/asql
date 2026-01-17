# 2026-01-08 — Ported Features LOC + Simplification Review

This is an engineering note to quantify **what’s been ported out of the regex preparser**, how much **new LOC** we added in the dialect/compiler, and where we should **simplify** to better match SQLGlot maintainer-style implementations.

## Snapshot: biggest new chunks (measured)

Measured via AST `lineno/end_lineno` (so counts are real, not estimates):

| Area | Location | New LOC |
|------|----------|---------|
| **Pipeline parsing (transform chaining)** | `ASQLParser._parse_query` | **60** |
| **Transform keyword matching** | `ASQLParser._match_transform` | **42** |
| **Transform payload token boundaries** | `_find_transform_boundary_index` + expression/select payload helpers | **52** (18 + 15 + 19) |
| **Natural syntax parsing** (relative dates, space-notation, multi-word sugar, natural aggs, etc.) | `ASQLParser._parse_unary` | **127** |
| **Date arithmetic** (`col +/- NUMBER unit`) | `ASQLParser._parse_factor` | **50** |
| **Ternary `? :`** | `ASQLParser._parse_assignment` | **19** |
| **Set operation RHS FROM-first support** | `ASQLParser.parse_set_operation` | **77** |
| **PIVOT/UNPIVOT parsing wrapper** | `_parse_pivot` + ASQL pivot/unpivot syntax | **104** (41 + 34 + 29) |
| **Column operators in parser** (`except/rename/replace`) | `_parse_asql_except/_rename/_replace` | **114** (17 + 50 + 47) |
| **Column operator schema fallback rewrite** | `compiler/column_operators.py` | **153** |
| **Schema-aware underscore shorthands** (`*_since_*`, plus `func_col` projections) | `compiler/underscore_shorthands.py` | **147** (63 + 84) |
| **Compiler driver** | `compiler/api.py::compile` | **174** (note: this includes much more than ports) |

## Ported features (measured LOC, dialect/compiler)

This list is focused on the ports that introduced meaningful new code (not deletions). For “what got deleted”, see `ai_notes/dialect_port_status.md`.

| Feature | Where it lives now | New LOC (measured) |
|--------|---------------------|--------------------|
| `except/rename/replace` column operators | `asql/dialect.py` + `asql/compiler/column_operators.py` | **267** (114 + 153) |
| `*_since_*` / `*_until_*` shorthands | `asql/compiler/underscore_shorthands.py` | **63** |
| `func_col` projection shorthands | `asql/compiler/underscore_shorthands.py` | **84** |
| `? :` ternary | `ASQLParser._parse_assignment` | **19** |
| `col +/- NUMBER unit` | `ASQLParser._parse_factor` | **50** |
| Relative dates + natural syntax layer | `ASQLParser._parse_unary` | **127** |
| FROM-first pipeline parsing | `_parse_query` + helpers | **102** (60 + 42; boundary helpers are additional) |
| Set ops (FROM-first RHS) | `ASQLParser.parse_set_operation` | **77** |
| PIVOT/UNPIVOT wrapper syntax | `_parse_pivot` + ASQL variants | **104** |

## What this implies

- **The largest “new complexity” is not a single feature**; it’s the **pipeline parsing** and the **natural syntax layer** (`_parse_unary`), which is expected because those are ASQL’s primary value-adds over vanilla SQL.
- The **column operators** port is moderate in the parser (114 LOC) but more complex in the compiler (153 LOC) due to **schema-driven expansion across pipeline-generated CTEs**.

## Maintainer-style review: are we doing this “the SQLGlot way”?

### ✅ Strong alignment (keep)

- **Ternary** (`_parse_assignment`, ~19 LOC): matches the ClickHouse-style “hook at the right precedence level” pattern. This is exactly the kind of small override SQLGlot maintainers tend to like.
- **Relative dates / date arithmetic** (`_parse_unary/_parse_factor`): implemented using SQLGlot `exp.Interval` and normal arithmetic expressions, which is idiomatic and portable.
- **Set operation RHS parsing** (`parse_set_operation`): pragmatic and localized, avoiding a big global rewrite.
- **Column operators representation**: using SQLGlot’s native `Star(except_=...)` structure is correct and makes cross-dialect generation feasible.

### ⚠️ Medium alignment (works, but consider simplification)

#### 1) Pipeline parsing (`_parse_query` + boundary helpers)
**Why it’s complex:** we support indentation/newline “PRQL-ish” chaining without relying on literal `|>`, but SQLGlot’s built-in pipe syntax machinery is optimized for explicit pipe tokens.

**How SQLGlot dialects usually do it:**
- Lean on `PIPE_SYNTAX_TRANSFORM_PARSERS` / `TRANSFORM_PARSERS` (BigQuery style).
- Keep token boundary logic minimal; prefer tokenized keywords (e.g., `GROUP_BY` token).

**Recommendation (future):**
- If we can constrain the grammar slightly (e.g., require explicit `|` for single-line chaining), we can delete most of the boundary scanning logic.
- Otherwise, consider extracting boundary helpers into a small internal helper class/module to keep `dialect.py` more readable (SQLGlot dialects often keep overrides short and specific).

#### 2) Column-operator fallback (`compiler/column_operators.py`, ~153 LOC)
**Why it’s complex:** pipeline column operators generate CTEs; fallback must expand star operators **across CTE stages** while preserving renames/replacements.

**How other systems do it:**
- Many dialects simply *don’t support this* without native syntax, or they expand earlier (before wrapping).

**Recommendation (future):**
- If we’re willing to change semantics slightly, prefer **not introducing intermediate CTEs for column operators**; instead, keep them in a single SELECT projection stage. That would reduce the need for “track CTE columns” logic.
- If we keep current semantics, the implementation is reasonable; it’s inherently a compiler-level complexity, not dialect-level.

**Update (implemented):**
- We removed unnecessary **CTE wrapping** from the parser-side `except/rename/replace` transforms.
  - Now these transforms **mutate the query projection in-place** and return the same `exp.Query`.
  - This is closer to how SQLGlot dialects are typically written (avoid `_build_pipe_cte` unless semantics demand it).
  - Side benefit: `extend ... except ...` no longer drops the `extend`-added projection, since we no longer replace the projection with `SELECT * FROM __tmp`.

## Research cross-checks (what we matched / where we differ)

- **Star EXCEPT representation**: SQLGlot’s BigQuery-style AST uses `Star(except_=...)`, not `Star(except=...)`. We aligned our code with that, which also matches the generator behavior for dialects with native support.
- **Ternary parsing**: Aligns with the ClickHouse-style approach (override at assignment precedence and build `exp.If`).
- **Pipeline transforms**: Similar spirit to PRQL/BigQuery transform parsers, but we carry extra boundary logic to support indentation pipelines without explicit pipe tokens.

## Recommended simplifications (next)

If we want to reduce complexity further (while keeping behavior), the biggest wins are:

- **Refactor `_parse_unary` into small helpers** (readability + maintainability; minimal behavior risk).
- **Consolidate pipeline boundary scanning** into a small internal helper (or constrain grammar to reduce scanning needs).
- **Keep compiler transforms schema-scoped** and avoid dialect parser doing schema work (we’re mostly aligned here already).

### ❌ Likely too big / mixed concerns (candidate refactors)

#### `_parse_unary` is doing a lot (~127 LOC)
This is the most concentrated “feature soup” in the dialect. It works, but it’s a readability hotspot.

**How SQLGlot maintainers tend to structure this:**
- Keep `_parse_unary` overrides short, delegating to small helpers for each family of sugar.
- Prefer declarative registries (`FUNCTIONS`, `FUNCTION_PARSERS`, `NO_PAREN_FUNCTION_PARSERS`) over long `if/elif` ladders when feasible.

**Recommendation (future):**
- Split `_parse_unary` into helpers like:
  - `_parse_relative_interval_unary()` (e.g., `7 days ago`)
  - `_parse_natural_agg_unary()` (e.g., `sum amount`)
  - `_parse_multiword_unary()` (e.g., `day of week col`)
  - `_parse_list_comprehension_unary()` (if retained in parser)
- This won’t reduce LOC much, but it will reduce cognitive load and make future ports safer.

