# ASQL Configuration & Settings System

This document outlines the proposed configuration system for ASQL and how to expose style preferences in the playground.

---

## Current State: NO CONFIG SYSTEM EXISTS

As of now, ASQL has **no configuration or settings system**. The syntax choices in both directions are hardcoded:

- **`preparser.py`**: Hardcoded transformations (e.g., `==` → `=`, `#` → `COUNT(*)`)
- **`reverse_compiler.py`**: Hardcoded output style (e.g., uses `==`, `#`, `??`, `take`)

---

## Proposed: ASQLConfig System

### Core Idea

Create an `ASQLConfig` class that controls ASQL syntax style preferences. This config would be used in:

1. **`reverse_compile()`** (SQL → ASQL) - Output ASQL in user's preferred style
2. **NEW: `normalize_asql()`** (ASQL → ASQL) - Re-style existing ASQL with preferences

### The Magic: ASQL → ASQL Transpilation

```
User clicks example (written in parens style)
        ↓
    ASQL Input: "from users group by country ( sum(amount) as revenue )"
        ↓
    compile() → SQL: "SELECT country, SUM(amount) AS revenue FROM users GROUP BY country"
        ↓
    reverse_compile(config=user_prefs) → ASQL in user's style
        ↓
    ASQL Output: "from users group by country ( sum_amount as revenue )"
```

This allows examples to be written in ONE canonical style, but displayed to users in THEIR preferred style!

---

## Proposed Configuration Options

### 1. Function Call Style

How function calls should be written:

| Style | Example | Notes |
|-------|---------|-------|
| `parens` | `sum(amount)` | Standard function call syntax |
| `underscore` | `sum_amount` | Shorthand with underscore |
| `space` | `sum amount` | Natural language style |

**Config key**: `function_style: "parens" | "underscore" | "space"`

### 2. Equality Operator

| Style | Example | Notes |
|-------|---------|-------|
| `double` | `status == "active"` | Python/JavaScript style |
| `single` | `status = "active"` | SQL style |

**Config key**: `equality_style: "double" | "single"`

### 3. Count Shorthand

| Style | Example | Notes |
|-------|---------|-------|
| `hash` | `#` or `# as total` | ASQL shorthand |
| `function` | `count(*)` | Standard SQL function |

**Config key**: `count_style: "hash" | "function"`

### 4. Coalesce Style

| Style | Example | Notes |
|-------|---------|-------|
| `operator` | `name ?? "Unknown"` | JavaScript-style nullish coalescing |
| `function` | `coalesce(name, "Unknown")` | SQL function |

**Config key**: `coalesce_style: "operator" | "function"`

### 5. Pipeline Delimiter

| Style | Example | Notes |
|-------|---------|-------|
| `none` | `from users where active` | Clean, no delimiter |
| `pipe` | `from users \| where active` | Explicit pipeline |

**Config key**: `pipeline_style: "none" | "pipe"`

### 6. Limit Keyword

| Style | Example | Notes |
|-------|---------|-------|
| `take` | `take 10` | ASQL style |
| `limit` | `limit 10` | SQL style |

**Config key**: `limit_keyword: "take" | "limit"`

### 7. Descending Order

| Style | Example | Notes |
|-------|---------|-------|
| `prefix` | `order by -amount` | ASQL shorthand |
| `suffix` | `order by amount desc` | SQL style |

**Config key**: `desc_style: "prefix" | "suffix"`

### 8. Sort Keyword

| Style | Example | Notes |
|-------|---------|-------|
| `sort` | `sort -amount` | Shorter |
| `order_by` | `order by -amount` | SQL style |

**Config key**: `sort_keyword: "sort" | "order_by"`

### 9. Cast Syntax

| Style | Example | Notes |
|-------|---------|-------|
| `double_colon` | `value::INT` | PostgreSQL style |
| `cast_function` | `cast(value as INT)` | SQL standard |

**Config key**: `cast_style: "double_colon" | "cast_function"`

### 10. Date Literal Style

| Style | Example | Notes |
|-------|---------|-------|
| `at_prefix` | `@2024-01-15` | ASQL shorthand |
| `date_keyword` | `DATE '2024-01-15'` | SQL standard |

**Config key**: `date_literal_style: "at_prefix" | "date_keyword"`

### 11. Week Start Day

| Style | Example | Notes |
|-------|---------|-------|
| `monday` | ISO 8601 standard | International |
| `sunday` | US convention | United States |

**Config key**: `week_start: "monday" | "sunday"`

---

## Implementation

### ASQLConfig Class

```python
# asql/config.py

from dataclasses import dataclass, field
from typing import Literal

@dataclass
class ASQLConfig:
    """Configuration for ASQL syntax style preferences."""
    
    # Function call style
    function_style: Literal["parens", "underscore", "space"] = "parens"
    
    # Equality operator
    equality_style: Literal["double", "single"] = "double"
    
    # Count shorthand
    count_style: Literal["hash", "function"] = "hash"
    
    # Coalesce style
    coalesce_style: Literal["operator", "function"] = "operator"
    
    # Pipeline delimiter
    pipeline_style: Literal["none", "pipe"] = "none"
    
    # Limit keyword
    limit_keyword: Literal["take", "limit"] = "take"
    
    # Descending order notation
    desc_style: Literal["prefix", "suffix"] = "prefix"
    
    # Sort keyword
    sort_keyword: Literal["sort", "order_by"] = "sort"
    
    # Cast syntax
    cast_style: Literal["double_colon", "cast_function"] = "double_colon"
    
    # Date literal style
    date_literal_style: Literal["at_prefix", "date_keyword"] = "at_prefix"
    
    # Week start day
    week_start: Literal["monday", "sunday"] = "monday"
    
    @classmethod
    def default(cls) -> "ASQLConfig":
        """Return default ASQL style (shorthand-heavy)."""
        return cls()
    
    @classmethod
    def sql_like(cls) -> "ASQLConfig":
        """Return SQL-like style (more familiar to SQL users)."""
        return cls(
            function_style="parens",
            equality_style="single",
            count_style="function",
            coalesce_style="function",
            pipeline_style="none",
            limit_keyword="limit",
            desc_style="suffix",
            sort_keyword="order_by",
            cast_style="cast_function",
            date_literal_style="date_keyword",
        )
    
    @classmethod
    def shorthand(cls) -> "ASQLConfig":
        """Return maximum shorthand style."""
        return cls(
            function_style="underscore",
            equality_style="double",
            count_style="hash",
            coalesce_style="operator",
            pipeline_style="none",
            limit_keyword="take",
            desc_style="prefix",
            sort_keyword="sort",
            cast_style="double_colon",
            date_literal_style="at_prefix",
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "function_style": self.function_style,
            "equality_style": self.equality_style,
            "count_style": self.count_style,
            "coalesce_style": self.coalesce_style,
            "pipeline_style": self.pipeline_style,
            "limit_keyword": self.limit_keyword,
            "desc_style": self.desc_style,
            "sort_keyword": self.sort_keyword,
            "cast_style": self.cast_style,
            "date_literal_style": self.date_literal_style,
            "week_start": self.week_start,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "ASQLConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
```

### Modified reverse_compile()

```python
# asql/reverse_compiler.py

def reverse_compile(
    sql_query: str,
    source_dialect: Optional[str] = None,
    config: Optional[ASQLConfig] = None,  # NEW PARAMETER
) -> str:
    """
    Compile SQL query to ASQL.
    
    Args:
        sql_query: SQL query string
        source_dialect: Source SQL dialect
        config: ASQL style configuration (defaults to ASQLConfig.default())
    """
    if config is None:
        config = ASQLConfig.default()
    
    # ... existing parsing code ...
    
    # Use config when generating ASQL output
    # e.g., _aggregation_to_asql(expr, config)
```

### NEW: normalize_asql() function

```python
# asql/normalizer.py

from asql.compiler import compile
from asql.reverse_compiler import reverse_compile
from asql.config import ASQLConfig

def normalize_asql(
    asql_query: str,
    config: Optional[ASQLConfig] = None,
    dialect: str = "snowflake",  # Intermediate SQL dialect
) -> str:
    """
    Normalize ASQL to a consistent style based on config.
    
    This is ASQL → SQL → ASQL transpilation that applies
    the user's style preferences.
    
    Args:
        asql_query: Input ASQL query (any style)
        config: Target style configuration
        dialect: Intermediate SQL dialect to use
    
    Returns:
        ASQL query in the configured style
    """
    if config is None:
        config = ASQLConfig.default()
    
    # Step 1: ASQL → SQL
    sql = compile(asql_query, dialect=dialect)
    
    # Step 2: SQL → ASQL (with config)
    normalized = reverse_compile(sql, source_dialect=dialect, config=config)
    
    return normalized
```

---

## Playground Integration

### User Flow

1. User opens playground
2. User sets preferences in settings panel (stored in localStorage)
3. User clicks an example
4. Example is normalized to user's preferred style via `normalize_asql()`
5. User sees ASQL in their preferred style

### API Endpoint

```python
@app.route('/api/normalize', methods=['POST'])
def api_normalize():
    """Normalize ASQL to user's preferred style."""
    data = request.get_json()
    asql_query = data.get('asql', '')
    config_dict = data.get('config', {})
    
    config = ASQLConfig.from_dict(config_dict)
    normalized = normalize_asql(asql_query, config=config)
    
    return jsonify({'asql': normalized})
```

### JavaScript Integration

```javascript
// Settings stored in localStorage
let asqlConfig = {
    function_style: "parens",
    equality_style: "double",
    count_style: "hash",
    // ... etc
};

// When user clicks an example
async function loadExample(exampleQuery) {
    // Normalize to user's preferred style
    const response = await fetch('/api/normalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            asql: exampleQuery,
            config: asqlConfig,
        })
    });
    
    const data = await response.json();
    inputEditor.setValue(data.asql);
    translateQuery();  // Also show SQL output
}
```

---

## Playground Settings UI

```html
<div class="settings-panel">
    <h3>⚙️ ASQL Style Preferences</h3>
    
    <div class="setting-group">
        <label>Function calls:</label>
        <select id="setting-function-style">
            <option value="parens">sum(amount)</option>
            <option value="underscore">sum_amount</option>
            <option value="space">sum amount</option>
        </select>
    </div>
    
    <div class="setting-group">
        <label>Equality:</label>
        <select id="setting-equality-style">
            <option value="double">== (Python style)</option>
            <option value="single">= (SQL style)</option>
        </select>
    </div>
    
    <div class="setting-group">
        <label>Count:</label>
        <select id="setting-count-style">
            <option value="hash"># (shorthand)</option>
            <option value="function">count(*)</option>
        </select>
    </div>
    
    <div class="setting-group">
        <label>Null coalescing:</label>
        <select id="setting-coalesce-style">
            <option value="operator">?? (operator)</option>
            <option value="function">coalesce()</option>
        </select>
    </div>
    
    <div class="setting-group">
        <label>Limit rows:</label>
        <select id="setting-limit-keyword">
            <option value="take">take 10</option>
            <option value="limit">limit 10</option>
        </select>
    </div>
    
    <div class="setting-group">
        <label>Descending sort:</label>
        <select id="setting-desc-style">
            <option value="prefix">-amount (prefix)</option>
            <option value="suffix">amount desc (suffix)</option>
        </select>
    </div>
    
    <div class="setting-group">
        <label>Week starts on:</label>
        <select id="setting-week-start">
            <option value="monday">Monday (ISO)</option>
            <option value="sunday">Sunday (US)</option>
        </select>
    </div>
    
    <div class="setting-presets">
        <button onclick="applyPreset('default')">ASQL Default</button>
        <button onclick="applyPreset('shorthand')">Max Shorthand</button>
        <button onclick="applyPreset('sql_like')">SQL-like</button>
    </div>
</div>
```

---

## Example Transformations

### Input (canonical style in examples)
```asql
from users
where status == "active"
group by country ( 
    # as total_users,
    sum(amount) as revenue 
)
order by -revenue
take 10
```

### Output with `ASQLConfig.sql_like()`
```asql
from users
where status = 'active'
group by country ( 
    count(*) as total_users,
    sum(amount) as revenue 
)
order by revenue desc
limit 10
```

### Output with `ASQLConfig.shorthand()`
```asql
from users
where status == "active"
group by country ( 
    # as total_users,
    sum_amount as revenue 
)
order by -revenue
take 10
```

---

## Implementation Priority

### Phase 1: Core Config System
1. Create `asql/config.py` with `ASQLConfig` class
2. Modify `reverse_compiler.py` to accept config
3. Create `normalize_asql()` function

### Phase 2: Playground Integration
4. Add `/api/normalize` endpoint
5. Add settings UI to playground
6. Store preferences in localStorage
7. Apply normalization when loading examples

### Phase 3: Advanced Features
8. URL parameter support for sharing configs
9. Preset buttons (Default, SQL-like, Shorthand)
10. Per-option documentation/tooltips

---

## Summary

**Current state**: ASQL has no config system. Output style is hardcoded.

**Proposed solution**: 
1. Create `ASQLConfig` dataclass with style preferences
2. Use config in `reverse_compile()` for SQL→ASQL
3. Create `normalize_asql()` for ASQL→ASQL style transformation
4. Playground normalizes examples to user's preferred style

**Key insight**: Examples are written ONCE in a canonical style. When displayed, they're re-transpiled through ASQL→SQL→ASQL to match user preferences. This means examples always feel native to the user's chosen style!
