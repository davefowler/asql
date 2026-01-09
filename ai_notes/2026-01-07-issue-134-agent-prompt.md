# Agent Prompt: Issue #134 - ASQL Parser Rewrite

**Copy this to kick off a Cursor agent:**

---

@cursor-opus-4-5 

## Task: Rewrite ASQL Parser Using SQLGlot's TRANSFORM_PARSERS Pattern

**Issue:** #134  
**PR Title:** asql: rewrite parser using TRANSFORM_PARSERS pattern (#134)  
**Branch:** issue-134-transform-parsers-rewrite  
**Commits must use:** `Fixes #134`

## Critical Constraints

1. **NO SYNTAX CHANGES** - ASQL syntax must remain exactly as specified in `docs/spec.md`. We're changing the implementation, not the language.

2. **GREENFIELD REWRITE** - Do NOT try to preserve or integrate with the existing preparser code (`asql/preparse/`). Think fresh. The goal is ~200 LOC like PRQL, not 6,477 LOC.

3. **IMPLEMENT AS A PROPER SQLGLOT DIALECT** - Write this as if you were the SQLGlot creator adding ASQL as a first-class dialect. Study `sqlglot/dialects/prql.py` as your template.

## Implementation Guide

### Step 1: Study PRQL's Implementation

```bash
# Read PRQL dialect (your template)
cat venv/lib/python*/site-packages/sqlglot/dialects/prql.py
```

PRQL is ~200 lines. ASQL should be similar.

### Step 2: Create ASQL Dialect Structure

```python
# asql/dialect.py (rewrite from scratch)

class ASQL(Dialect):
    DPIPE_IS_STRING_CONCAT = True  # || is concat, not OR
    
    class Tokenizer(tokens.Tokenizer):
        SINGLE_TOKENS = {
            **tokens.Tokenizer.SINGLE_TOKENS,
            "|": TokenType.PIPE_GT,  # Map | to |> to reuse pipe infra
            "#": TokenType.HASH,     # For COUNT(*) shorthand
        }
    
    class Parser(parser.Parser):
        # Copy PRQL's patterns for:
        # - CONJUNCTION with DAMP (&&)
        # - _parse_equality() for NULL handling
        # - _parse_ordered() for -column DESC
        
        TRANSFORM_PARSERS = {
            "WHERE": lambda self, q: q.where(self._parse_where()),
            "LIMIT": lambda self, q: q.limit(self._parse_number()),
            "ORDER": lambda self, q: self._parse_order_by(q),
            "SELECT": lambda self, q: self._parse_select(q),
            "GROUP": lambda self, q: self._parse_group_by(q),
            "EXTEND": lambda self, q: self._parse_extend(q),
        }
        
        FUNCTIONS = {
            **parser.Parser.FUNCTIONS,
            "TOTAL": exp.Sum.from_arg_list,
            "AVERAGE": exp.Avg.from_arg_list,
            "MAXIMUM": exp.Max.from_arg_list,
            "MINIMUM": exp.Min.from_arg_list,
            "PRIOR": lambda args: exp.Lag(this=seq_get(args, 0)),
            "NEXT": lambda args: exp.Lead(this=seq_get(args, 0)),
        }
        
        def _parse_query(self):
            query = self._parse_from()
            while self._match_texts(self.TRANSFORM_PARSERS):
                query = self.TRANSFORM_PARSERS[self._prev.text.upper()](self, query)
            return self._parse_pipe_syntax_query(query)  # Handle |> chains
    
    class Generator(generator.Generator):
        pass  # For reverse compilation later
```

### Step 3: Key SQLGlot Infrastructure to Use

1. **`_parse_pipe_syntax_query()`** - Built-in pipe handling
2. **`_build_pipe_cte()`** - Auto-wraps queries in CTEs when needed
3. **`PIPE_SYNTAX_TRANSFORM_PARSERS`** - For `|>` handling
4. **`exp.*`** - Expression builders (never build SQL strings!)

### Step 4: What to DELETE

Once the new parser works, these preparser files become obsolete:
- `asql/preparse/pipeline.py` (68 lines → 0)
- `asql/preparse/order.py` (79 lines → 0)  
- `asql/preparse/aggregates.py` (225 lines → mostly 0)
- `asql/preparse/clauses.py` (974 lines → mostly 0)
- Eventually most of the 6,477 lines

### Step 5: Test Strategy

1. All existing tests in `tests/` must pass
2. Add tests for proper pipeline semantics:
   ```python
   def test_group_then_where_uses_cte():
       # This was BROKEN before, should produce CTE now
       sql = compile("from users group by country (count(*)) where count > 10")
       assert "WITH" in sql or "HAVING" in sql
   ```

## Reference Materials

- **ASQL Syntax Spec:** `docs/spec.md` (source of truth - don't change!)
- **PRQL Dialect:** `venv/lib/python*/site-packages/sqlglot/dialects/prql.py`
- **BigQuery Pipe Syntax:** Look at `PIPE_SYNTAX_TRANSFORM_PARSERS` in base Parser
- **Issue Details:** https://github.com/davefowler/asql/issues/134

## Success Criteria

1. ✅ All existing tests pass
2. ✅ ASQL syntax unchanged (verify against `docs/spec.md`)
3. ✅ Parser is ~200-300 LOC (like PRQL)
4. ✅ Pipeline semantics correct (group → where uses CTEs)
5. ✅ Uses SQLGlot infrastructure (no string manipulation)
6. ✅ Preparser LOC significantly reduced

## Commands

```bash
# Setup
git checkout main
git pull
git checkout -b issue-134-transform-parsers-rewrite

# Test
./venv/bin/pytest tests/ -x -v

# Commit
git commit -m "Fixes #134 - rewrite parser using TRANSFORM_PARSERS"
```

---

**Remember:** This is a REWRITE, not a refactor. Start fresh. Think like you're the SQLGlot maintainer adding a new dialect. Target ~200 LOC. The old preparser code is legacy - don't try to preserve it.

