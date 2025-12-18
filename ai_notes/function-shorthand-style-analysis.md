# Function Shorthand Style Analysis: `sum(amount)` vs `sum_amount` vs `sum amount`

## Current State

**Current Default**: There is **no style config setting** for function shorthand format. All three are accepted on input, but `normalize()` doesn't currently standardize them (there's no preference setting).

**Current Documentation**: The style guide currently says explicit `sum(amount)` is preferred, but this isn't enforced by any config setting.

## The Three Options

### 1. `sum(amount)` - Explicit Function Call

**Pros**:
- ✅ **Crystal clear intent** - immediately obvious it's a function call
- ✅ **No ambiguity** - can't conflict with column names
- ✅ **Familiar** - matches SQL and most programming languages
- ✅ **Self-documenting** - easy for new users to understand
- ✅ **Works with complex expressions** - `sum(amount * quantity)` is natural
- ✅ **IDE-friendly** - syntax highlighting and autocomplete work well
- ✅ **Maintainable** - easier to read and modify later

**Cons**:
- ❌ **More verbose** - requires parentheses and explicit column name
- ❌ **Less "natural language"** - doesn't read as naturally as `sum amount`
- ❌ **More typing** - 11 characters vs 9 for `sum_amount` or `sum amount`

**Use cases**: Documentation, production code, when clarity matters most

---

### 2. `sum_amount` - Underscore Shorthand

**Pros**:
- ✅ **Declarative continuity** - What you write (`sum_amount`) is exactly what the output column will be named, enabling consistent reference throughout the query
- ✅ **Self-documenting** - Makes it immediately clear what column name will be created
- ✅ **Predictable** - No mismatch between input syntax and output column name
- ✅ **Column-like** - Looks like a column reference because it becomes one
- ✅ **Works seamlessly** - You can write `sum_amount` in GROUP BY, then reference `sum_amount` in ORDER BY, WHERE, etc.
- ✅ **Concise** - shorter than explicit call
- ✅ **No spaces** - works well in tight contexts (GROUP BY, ORDER BY)
- ✅ **Familiar** - matches common SQL naming conventions (`created_at`, `user_id`)

**Cons**:
- ❌ **Ambiguity risk** - if a column named `sum_amount` exists, it uses the column instead
- ❌ **Less obvious** - not immediately clear it's a function call (though the output column name makes it clear)
- ❌ **Requires knowledge** - users need to know the shorthand pattern
- ❌ **Can't express complex expressions** - `sum_amount * quantity` is ambiguous (is it `sum(amount * quantity)` or `sum(amount) * quantity`?)
- ❌ **Can't express multiple arguments** - `max_price, cost` doesn't work (needs `max(price, cost)`)
- ❌ **Less natural language** - reads like code, not English

**Use cases**: When you'll reference the column later (ORDER BY, WHERE, etc.) - declarative and matches output. Also good for quick queries when brevity matters. **Only works with single column arguments** - multiple arguments or complex expressions require parens form.

---

### 3. `sum amount` - Space Shorthand

**Pros**:
- ✅ **Most natural language** - reads like English: "sum amount"
- ✅ **Analyst-friendly** - feels more accessible to non-programmers
- ✅ **Concise** - shorter than explicit call
- ✅ **Matches ASQL philosophy** - aligns with "natural language" goals
- ✅ **Works with "of"** - `sum of amount` reads even more naturally
- ✅ **Flexible** - `sum amount`, `sum of amount`, `total amount` all work

**Cons**:
- ❌ **Spaces in identifiers** - can be confusing in some contexts
- ❌ **Less familiar** - unusual for programmers coming from SQL/other languages
- ❌ **Ambiguity risk** - same as underscore version
- ❌ **Can't express complex expressions** - `sum amount * quantity` is ambiguous (is it `sum(amount * quantity)` or `sum(amount) * quantity`?)
- ❌ **Can't express multiple arguments** - `max price, cost` doesn't work (needs `max(price, cost)`)
- ❌ **Parsing complexity** - requires more sophisticated parsing
- ❌ **IDE challenges** - syntax highlighting might struggle

**Use cases**: Exploratory queries, when natural language feel matters, for analysts less familiar with programming. **Only works with single column arguments** - multiple arguments or complex expressions require parens form.

---

## Comparison Table

| Aspect | `sum(amount)` | `sum_amount` | `sum amount` |
|--------|---------------|--------------|--------------|
| **Clarity** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Brevity** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Natural Language** | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Familiarity** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **Ambiguity Risk** | ⭐⭐⭐⭐⭐ (none) | ⭐⭐ | ⭐⭐ |
| **Complex Expressions** | ⭐⭐⭐⭐⭐ | ❌ | ❌ |
| **Documentation** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

---

## Recommendation

### For Style Guide / Default Preference

**Recommendation: `sum_amount` (underscore shorthand) as the preferred default**

**Rationale**:
1. **Declarative continuity** - The key insight: `sum_amount` is **declarative** - you're declaring what the output column will be named, and then you can reference it consistently. This makes queries more predictable and self-documenting.
2. **No mismatch** - When you write `sum_amount`, the output column is `sum_amount`. When you write `sum amount`, the output column is `sum_amount` (mismatch). When you write `sum(amount)`, the output column is `sum_amount` (mismatch). Only underscore matches exactly.
3. **Self-documenting** - Makes it immediately clear what column name will be created, which you can then reference in ORDER BY, WHERE, etc.
4. **Works seamlessly** - You can write `sum_amount` in GROUP BY, then reference `sum_amount` in ORDER BY without any mental translation.
5. **Column-like** - Looks like a column reference because it becomes one - this is actually a feature, not a bug.

**But with important caveats**:
- **When using `as` to rename**: The declarative continuity benefit doesn't apply. Use `sum amount` or `sum(amount)` instead:
  ```asql
  -- ✅ Preferred when aliasing
  group by region ( sum amount as revenue )
  group by region ( sum(amount) as revenue )
  
  -- ❌ Not preferred when aliasing (underscore benefit doesn't apply)
  group by region ( sum_amount as revenue )
  ```

- **When there are multiple arguments**: Shorthand forms can't express this clearly. **Parens form is required**:
  ```asql
  -- ✅ Required for multiple arguments
  select max(price, cost) as max_value
  
  -- ❌ Ambiguous/confusing with shorthand
  select max_price, cost  -- Doesn't work - is this max(price, cost) or max(price), cost?
  ```

- **When there are complex expressions**: Shorthand forms are ambiguous. **Parens form is required**:
  ```asql
  -- ✅ Required for complex expressions
  select sum(amount * quantity) as total_revenue
  
  -- ❌ Ambiguous with shorthand
  select sum_amount * quantity  -- Is this sum(amount * quantity) or sum(amount) * quantity?
  ```

- **Space form `sum amount` is also preferred** for:
  - When using `as` to rename (underscore benefit doesn't apply, single column only)
  - Natural language feel when you won't reference the column later (single column only)
  - Exploratory queries where readability matters more than continuity (single column only)
  - When the "English-like" feel aligns with ASQL's philosophy (single column only)

- **Parens form `sum(amount)` is required for**:
  - **Multiple arguments**: `max(price, cost)` - shorthand forms can't express this
  - **Complex expressions**: `sum(amount * quantity)` - shorthand forms are ambiguous
  - When using `as` to rename (underscore benefit doesn't apply)
  - Documentation examples (for maximum clarity)
  - When ambiguity is a concern
  - Production code where maintainability matters most

**Key insight**: The underscore form is **declarative** - it's self-documenting about what the output will be, making queries more predictable and enabling seamless column reuse. However, this benefit only applies when you're NOT using `as` to rename the column AND when there's a single column argument. When aliasing OR when there are multiple arguments/complex expressions, use parens form instead.

### For Style Config Setting

**Recommendation**: Add a new `StyleConfig` setting:

```python
function_shorthand: Literal["underscore", "space", "parens"] = "underscore"
```

- `"underscore"` → Prefer `sum_amount` when possible (default, for declarative continuity)
- `"space"` → Prefer `sum amount` when possible
- `"parens"` → Always use `sum(amount)`

**Note**: When using `as` to rename OR when there are multiple arguments/complex expressions, the underscore benefit doesn't apply, so parens form should be used regardless of config setting.

This gives users choice while establishing a default that matches ASQL's philosophy.

---

## Implementation Notes

- `normalize()` should convert all three forms to the configured preference
- Documentation should show `sum amount` as the preferred form
- Explicit `sum(amount)` should always be acceptable and preferred for complex expressions
- The style guide should explain when to use each form

