# ASQL Language Configuration System

Design document for ASQL's configuration system.

---

## Philosophy: Should ASQL Even Have Config?

### The Spectrum of Configurability

| Tool | Philosophy | Config Level |
|------|------------|--------------|
| **Black** | "Uncompromising" - almost zero options | Minimal |
| **Prettier** | Opinionated - few options, strong defaults | Low |
| **Rustfmt** | Has options, but encourages defaults | Medium |
| **ESLint** | Highly configurable, rule-by-rule | High |

### Recommendation for ASQL

**ASQL should be Prettier-style: opinionated with limited, meaningful options.**

---

## Core Design Principle

```
┌─────────────────────────────────────────────────────────────┐
│  PARSING (Input)     │  ALWAYS PERMISSIVE                  │
│  compile()           │  Accept ALL valid ASQL syntaxes     │
├──────────────────────┼──────────────────────────────────────┤
│  OUTPUT (Rendering)  │  CONFIGURABLE                       │
│  reverse_compile()   │  Output in configured style         │
│  normalize()         │                                     │
└──────────────────────┴──────────────────────────────────────┘
```

**Key insight**: Config affects HOW ASQL IS WRITTEN (output), not WHAT IS VALID (input).

ASQL will ALWAYS accept all valid syntaxes. Config only controls what the output looks like when:
- Converting SQL → ASQL (`reverse_compile`)
- Normalizing ASQL → ASQL (`normalize`)

---

## Configuration File

### File Format: YAML Only

```
asql.config.yaml      # Standard location
.asqlrc.yaml          # Hidden file alternative
```

**Why just YAML?**
- One format = simpler tooling, simpler docs
- YAML is human-readable and supports comments
- Programmatic use (libraries) can pass config as dict/object directly

### Basic Structure

```yaml
# asql.config.yaml

# Preset: "default" | "sql-compat" | "concise"
preset: default

# Target SQL dialect for compile()
dialect: snowflake

# Override individual style options (optional)
style:
  count: hash           # override specific options
```

---

## The Style/Lint Question

You asked a great question: **How do style and lint overlap?**

### Option A: Separate Style + Lint (Current Design)

```yaml
style:
  count: hash           # OUTPUT: write # in generated ASQL
  
lint:
  prefer-hash-count: warn   # LINT: warn if input uses count(*)
```

**Problem**: Redundant. If I set `count: hash`, I probably also want to lint for it.

### Option B: Array Syntax (Your Idea)

```yaml
count: [hash, function]    # First = preferred (for output), rest = also allowed
count: [hash]              # Only hash allowed, warn on function  
count: hash                # Shorthand for [hash] - strict
```

**How it works:**
- First item = OUTPUT style (what `normalize()` produces)
- All items = ALLOWED without warning
- Items NOT in list = would trigger lint warning

**Example:**
```yaml
# Permissive: both OK, prefer hash for output
count: [hash, function]

# Strict: only hash, warn on function  
count: [hash]
# or shorthand:
count: hash
```

**Problem**: No "error" level, only "allowed" vs "warn".

### Option C: Simplified - Just Style, No Lint

Like Prettier - no linting at all. Config only affects OUTPUT.

```yaml
style:
  count: hash    # normalize() outputs #, but count(*) input is always fine
```

**How it works:**
- `compile()` accepts EVERYTHING (no warnings ever)
- `normalize()` rewrites to preferred style
- No separate lint step

**Pros**: Simplest, no redundancy  
**Cons**: Can't warn about style in CI without normalizing

### Recommendation: Option C (No Lint, Just Style)

ASQL should be like Prettier:
1. Accept all valid syntax on input
2. Output in ONE configured style
3. To "lint", just run `normalize()` and diff

```bash
# "Lint" by checking if normalization changes anything
asql normalize --check query.asql
# Exit 1 if file would change, exit 0 if already normalized
```

This is exactly how `prettier --check` and `black --check` work.

---

## Simplified Configuration

### Presets

```yaml
preset: default      # or: sql-compat, concise
```

| Preset | Description | Key Choices |
|--------|-------------|-------------|
| `default` | Balanced ASQL style | `==`, `#`, `??`, `take`, `-col` |
| `sql-compat` | Familiar to SQL users | `=`, `count(*)`, `coalesce()`, `limit`, `col DESC` |
| `concise` | Maximum brevity | `==`, `#`, `??`, `take`, `-col`, underscore functions |

### Style Options

Each option controls OUTPUT style only. Input always accepts all variants.

```yaml
style:
  # Equality operator
  equality: double          # == (default) | single (=)
  
  # Count notation  
  count: hash               # hash (#) (default) | function (count(*))
  
  # Null coalescing
  coalesce: operator        # operator (??) (default) | function (coalesce())
  
  # Row limiting
  limit: take               # take (default) | limit
  
  # Descending order
  descending: prefix        # prefix (-col) (default) | suffix (col DESC)
  
  # Type casting
  cast: double_colon        # double_colon (::) (default) | function (CAST)
  
  # String quotes
  quotes: double            # double (") (default) | single (')
  
  # Week start (semantic, affects week() function)
  week_start: monday        # monday (default) | sunday
```

### Full Preset Definitions

#### `default`
```yaml
style:
  equality: double          # status == "active"
  count: hash               # #
  coalesce: operator        # name ?? "Unknown"
  limit: take               # take 10
  descending: prefix        # order by -amount
  cast: double_colon        # value::INT
  quotes: double            # "active"
  week_start: monday
```

#### `sql-compat`
```yaml
style:
  equality: single          # status = 'active'
  count: function           # count(*)
  coalesce: function        # coalesce(name, 'Unknown')
  limit: limit              # limit 10
  descending: suffix        # order by amount DESC
  cast: function            # CAST(value AS INT)
  quotes: single            # 'active'
  week_start: monday
```

#### `concise`
```yaml
style:
  equality: double          # status == "active"
  count: hash               # #
  coalesce: operator        # ??
  limit: take               # take 10
  descending: prefix        # -amount
  cast: double_colon        # ::
  quotes: double            # "active"
  week_start: monday
  # Note: concise also enables underscore functions in output
  # sum(amount) → sum_amount (when unambiguous)
```

---

## What About Function Style?

You mentioned `function_call: parens | underscore | space`.

This is tricky because:
- `sum(amount)` - always unambiguous
- `sum_amount` - could be column named "sum_amount" or sum(amount)
- `sum amount` - only works in certain contexts

**Recommendation**: Don't make this configurable for output.

- INPUT: Accept all three (current behavior)
- OUTPUT: Always use `parens` style - it's unambiguous

The `concise` preset could output underscore style, but only when unambiguous (no column named `sum_amount` exists).

---

## Implementation

### Config Class

```python
# asql/config.py

from dataclasses import dataclass
from typing import Literal, Optional
import yaml
from pathlib import Path

@dataclass
class StyleConfig:
    equality: Literal["double", "single"] = "double"
    count: Literal["hash", "function"] = "hash"
    coalesce: Literal["operator", "function"] = "operator"
    limit: Literal["take", "limit"] = "take"
    descending: Literal["prefix", "suffix"] = "prefix"
    cast: Literal["double_colon", "function"] = "double_colon"
    quotes: Literal["double", "single"] = "double"
    week_start: Literal["monday", "sunday"] = "monday"


@dataclass
class ASQLConfig:
    preset: str = "default"
    dialect: str = "snowflake"
    style: StyleConfig = None
    
    def __post_init__(self):
        if self.style is None:
            self.style = self._style_for_preset(self.preset)
    
    @staticmethod
    def _style_for_preset(preset: str) -> StyleConfig:
        if preset == "sql-compat":
            return StyleConfig(
                equality="single",
                count="function",
                coalesce="function",
                limit="limit",
                descending="suffix",
                cast="function",
                quotes="single",
            )
        elif preset == "concise":
            return StyleConfig()  # Same as default for now
        else:  # default
            return StyleConfig()
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> "ASQLConfig":
        """Load from file or return defaults."""
        if path is None:
            path = cls._find_config()
        
        if path is None or not path.exists():
            return cls()
        
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def _find_config(cls) -> Optional[Path]:
        """Find config in current dir or parents."""
        for name in ["asql.config.yaml", ".asqlrc.yaml"]:
            for parent in [Path.cwd()] + list(Path.cwd().parents):
                p = parent / name
                if p.exists():
                    return p
        return None
    
    @classmethod
    def from_dict(cls, data: dict) -> "ASQLConfig":
        preset = data.get("preset", "default")
        dialect = data.get("dialect", "snowflake")
        
        config = cls(preset=preset, dialect=dialect)
        
        # Override style options if provided
        if "style" in data:
            for key, value in data["style"].items():
                if hasattr(config.style, key):
                    setattr(config.style, key, value)
        
        return config
```

### Using Config

```python
# In reverse_compiler.py

def reverse_compile(sql: str, config: ASQLConfig = None) -> str:
    if config is None:
        config = ASQLConfig.load()
    
    # Use config.style when generating ASQL
    # e.g., if config.style.count == "hash", output "#"
    # e.g., if config.style.count == "function", output "count(*)"


def normalize(asql: str, config: ASQLConfig = None) -> str:
    """Reformat ASQL to match configured style."""
    if config is None:
        config = ASQLConfig.load()
    
    sql = compile(asql, dialect=config.dialect)
    return reverse_compile(sql, config=config)
```

---

## CLI

```bash
# Compile ASQL to SQL (uses config if present)
asql compile query.asql

# Normalize ASQL to configured style
asql normalize query.asql

# Check if already normalized (for CI)
asql normalize --check query.asql

# Use specific preset
asql normalize --preset sql-compat query.asql

# Override dialect
asql compile --dialect bigquery query.asql
```

---

## Current Code Status

Checking what the code currently does:

| Feature | Input (preparser) | Output (reverse_compiler) |
|---------|-------------------|---------------------------|
| Equality | Accepts `=` and `==`, converts `==` → `=` | Outputs `==` |
| Count | Accepts `#` and `count(*)` | Outputs `#` |
| Limit | Accepts `take` and `limit` | Outputs `take` |
| Coalesce | Accepts `??` and `coalesce()` | Outputs `??` |
| Descending | Accepts `-col` and `col DESC` | Outputs `-col` |
| Cast | Accepts `::` and `CAST()` | Outputs `::` |

So currently, ASQL is hardcoded to the `default` style. Adding config would make the reverse_compiler style-aware.

---

## Summary

| Question | Answer |
|----------|--------|
| Config file format? | YAML only (`asql.config.yaml`) |
| Style affects output? | Yes - only affects `reverse_compile` and `normalize` |
| Style affects input? | No - input always accepts all valid syntaxes |
| Separate lint rules? | No - use `normalize --check` instead |
| Default equality? | `==` (double) |
| `take` still in code? | Yes, both `take` and `limit` work |
| Array syntax? | Not needed if we drop lint rules |

**Design principle**: Keep it simple. Style = output format. No lint rules. To check style, run `normalize --check`.
