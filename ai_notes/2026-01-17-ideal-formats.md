# Ideal Formats: Parser vs Schema

Three examples showing what each dict ideally looks like for its use case.

---

## 1. TRANSFORM_PARSERS (Transforms like WHERE, SELECT, GROUP BY)

### Ideal for Parser (dialect.py)

The parser needs to:
- Match keywords to trigger transforms
- Call a function to do the parsing

```python
TRANSFORM_PARSERS = {
    "WHERE": lambda self, query: query.where(self._parse_assignment(), copy=False),
    "SELECT": lambda self, query: self._parse_asql_select(query),
    "GROUP BY": lambda self, query: self._parse_asql_group_by(query),
    "JOIN": lambda self, query: self._parse_asql_join(query, kind="INNER"),
    "LEFT": lambda self, query: self._parse_join_kind(query, "LEFT", ("JOIN",)),
    "PER": lambda self, query: self._parse_asql_per(query),
    "STASH": lambda self, query: self._parse_asql_stash(query),
    "EXTEND": lambda self, query: self._parse_asql_extend(query),
    # ...
}

# Parser also needs to know alternate keywords that trigger same transform
# (e.g., "FILTER" triggers WHERE, "PROJECT" triggers SELECT)
# Could be separate dict or embedded:
KEYWORD_ALIASES = {
    "FILTER": "WHERE",
    "IF": "WHERE",
    "PROJECT": "SELECT",
}
```

### Ideal for Schema (dialect_schema.py)

The schema needs to:
- List all transforms with human-readable metadata
- Provide icons, labels, descriptions for UI
- Document what keywords trigger each transform
- Define parameters for visual editor forms

```python
TRANSFORMS = {
    "where": {
        "keywords": ["WHERE", "FILTER", "IF"],
        "label": "Filter",
        "icon": "🔍",
        "category": "filter",
        "description": "Filter rows by a condition",
        "parameters": [
            {"name": "condition", "type": "expression", "required": True}
        ],
    },
    "select": {
        "keywords": ["SELECT", "PROJECT"],
        "label": "Select",
        "icon": "📋",
        "category": "projection",
        "description": "Choose which columns to return",
        "parameters": [
            {"name": "columns", "type": "column_list", "required": True}
        ],
    },
    "group_by": {
        "keywords": ["GROUP BY"],
        "label": "Group By",
        "icon": "📊",
        "category": "aggregation",
        "description": "Group rows and compute aggregates",
        "parameters": [
            {"name": "columns", "type": "column_list", "required": True},
            {"name": "aggregates", "type": "aggregate_list", "required": False},
        ],
    },
    "join": {
        "keywords": ["JOIN", "&"],
        "label": "Join",
        "icon": "🔗",
        "category": "join",
        "description": "Combine rows from two tables",
        "parameters": [
            {"name": "table", "type": "table", "required": True},
            {"name": "condition", "type": "expression", "required": False},
            {"name": "type", "type": "join_type", "required": False, "default": "inner"},
        ],
    },
    # ...
}
```

---

## 2. COMPARISON_OPS (Operators like >, <, >=, =)

### Ideal for Parser (dialect.py)

The parser needs to:
- Map TokenType to expression class
- Build AST nodes from matched operators

```python
COMPARISON_OPS = {
    TokenType.GT: exp.GT,
    TokenType.GTE: exp.GTE,
    TokenType.LT: exp.LT,
    TokenType.LTE: exp.LTE,
    TokenType.EQ: exp.EQ,
    TokenType.NEQ: exp.NEQ,
}

# Usage in parser:
def _build_comparison(self, left, op_token, right):
    expr_class = self.COMPARISON_OPS.get(op_token, exp.EQ)
    return expr_class(this=left, expression=right)
```

### Ideal for Schema (dialect_schema.py)

The schema needs to:
- List operators with human-readable symbols
- Provide labels and descriptions for UI dropdowns

```python
COMPARISON_OPERATORS = [
    {"symbol": ">",  "label": "greater than",          "description": "Left is greater than right"},
    {"symbol": ">=", "label": "greater than or equal", "description": "Left is greater than or equal to right"},
    {"symbol": "<",  "label": "less than",             "description": "Left is less than right"},
    {"symbol": "<=", "label": "less than or equal",    "description": "Left is less than or equal to right"},
    {"symbol": "=",  "label": "equals",                "description": "Left equals right"},
    {"symbol": "!=", "label": "not equals",            "description": "Left does not equal right"},
]

# Or as dict keyed by symbol for lookup:
COMPARISON_OPERATORS = {
    ">":  {"label": "greater than",          "description": "..."},
    ">=": {"label": "greater than or equal", "description": "..."},
    "<":  {"label": "less than",             "description": "..."},
    "<=": {"label": "less than or equal",    "description": "..."},
    "=":  {"label": "equals",                "description": "..."},
    "!=": {"label": "not equals",            "description": "..."},
}
```

---

## 3. STRING_OPERATORS (Operators like CONTAINS, STARTS WITH)

### Ideal for Parser (dialect.py)

The parser needs to:
- Match text sequences (multi-word operators)
- Know how to wrap the pattern (prefix/suffix %)
- Know if case-insensitive

```python
STRING_OPS = {
    "CONTAINS":      {"wrap": ("%", "%"), "case_insensitive": False},
    "ICONTAINS":     {"wrap": ("%", "%"), "case_insensitive": True},
    "STARTS WITH":   {"wrap": ("", "%"),  "case_insensitive": False},
    "ISTARTS WITH":  {"wrap": ("", "%"),  "case_insensitive": True},
    "ENDS WITH":     {"wrap": ("%", ""),  "case_insensitive": False},
    "IENDS WITH":    {"wrap": ("%", ""),  "case_insensitive": True},
    "MATCHES":       {"wrap": ("", ""),   "case_insensitive": False, "is_regex": True},
}

# Usage in parser:
for op_name, spec in self.STRING_OPS.items():
    tokens = op_name.split()  # ["STARTS", "WITH"]
    if self._match_text_seq(*tokens):
        return self._build_like(left, right, **spec)
```

### Ideal for Schema (dialect_schema.py)

The schema needs to:
- List operators with syntax examples
- Provide labels and descriptions for docs/UI

```python
STRING_OPERATORS = [
    {
        "keyword": "contains",
        "label": "Contains",
        "description": "True if string contains substring",
        "example": "name contains 'smith'",
        "case_sensitive": True,
    },
    {
        "keyword": "icontains",
        "label": "Contains (case-insensitive)",
        "description": "True if string contains substring (ignoring case)",
        "example": "name icontains 'SMITH'",
        "case_sensitive": False,
    },
    {
        "keyword": "starts with",
        "label": "Starts With",
        "description": "True if string starts with prefix",
        "example": "name starts with 'Dr.'",
        "case_sensitive": True,
    },
    {
        "keyword": "istarts with",
        "label": "Starts With (case-insensitive)",
        "description": "True if string starts with prefix (ignoring case)",
        "example": "name istarts with 'DR.'",
        "case_sensitive": False,
    },
    {
        "keyword": "ends with",
        "label": "Ends With",
        "description": "True if string ends with suffix",
        "example": "email ends with '.com'",
        "case_sensitive": True,
    },
    {
        "keyword": "iends with",
        "label": "Ends With (case-insensitive)",
        "description": "True if string ends with suffix (ignoring case)",
        "example": "email iends with '.COM'",
        "case_sensitive": False,
    },
    {
        "keyword": "matches",
        "label": "Matches (regex)",
        "description": "True if string matches regular expression pattern",
        "example": "phone matches '^\\d{3}-\\d{4}$'",
        "is_regex": True,
    },
]
```

---

## Summary: Different Needs, Different Shapes

| Dict | Parser Needs | Schema Needs |
|------|--------------|--------------|
| Transforms | Keyword → function | Keyword → {label, icon, description, parameters} |
| Comparison ops | TokenType → exp class | Symbol → {label, description} |
| String ops | Keyword → {wrap pattern, case flag} | Keyword → {label, description, example} |

**Notice:**
- Parser keys are often TokenType or UPPERCASE keywords (machine-readable)
- Schema keys are often lowercase or symbols (human-readable)
- Parser values are code (functions, classes, tuples)
- Schema values are metadata (strings, lists of dicts)

They're fundamentally different structures optimized for different purposes.
