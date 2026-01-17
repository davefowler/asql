"""
ASQL Dialect Schema - Declarative single source of truth for ASQL syntax

This is the canonical definition of ASQL's syntax, operators, and semantics.
Used by:
- Parser (dialect.py) - for parsing ASQL
- Visual Editor (ui_schema.py) - for generating UI
- LSP/Autocomplete - for code intelligence
- Documentation - for generating reference docs

Everything about ASQL's syntax should be defined here declaratively.
"""

from sqlglot import exp, TokenType

# =============================================================================
# OPERATORS
# =============================================================================

OPERATORS = {
    # Standard comparison operators (from SQLGlot)
    "comparison": {
        ">": {
            "token": TokenType.GT,
            "expr_class": exp.GT,
            "label": ">",
            "description": "Greater than",
        },
        ">=": {
            "token": TokenType.GTE,
            "expr_class": exp.GTE,
            "label": ">=",
            "description": "Greater than or equal",
        },
        "<": {
            "token": TokenType.LT,
            "expr_class": exp.LT,
            "label": "<",
            "description": "Less than",
        },
        "<=": {
            "token": TokenType.LTE,
            "expr_class": exp.LTE,
            "label": "<=",
            "description": "Less than or equal",
        },
    },

    # Equality operators
    "equality": {
        "=": {
            "token": TokenType.EQ,
            "expr_class": exp.EQ,
            "label": "=",
            "description": "Equal to (== in ASQL syntax)",
        },
        "!=": {
            "token": TokenType.NEQ,
            "expr_class": exp.NEQ,
            "label": "!=",
            "description": "Not equal",
        },
    },

    # ASQL-specific string operators
    "string": {
        "contains": {
            "tokens": ("CONTAINS",),
            "wrap_pattern": ("%", "%"),
            "case_sensitive": True,
            "label": "contains",
            "description": "String contains (case-sensitive)",
        },
        "icontains": {
            "tokens": ("ICONTAINS",),
            "wrap_pattern": ("%", "%"),
            "case_sensitive": False,
            "label": "icontains",
            "description": "String contains (case-insensitive)",
        },
        "starts with": {
            "tokens": ("STARTS", "WITH"),
            "wrap_pattern": ("", "%"),
            "case_sensitive": True,
            "label": "starts with",
            "description": "String starts with (case-sensitive)",
        },
        "istarts with": {
            "tokens": ("ISTARTS", "WITH"),
            "wrap_pattern": ("", "%"),
            "case_sensitive": False,
            "label": "istarts with",
            "description": "String starts with (case-insensitive)",
        },
        "ends with": {
            "tokens": ("ENDS", "WITH"),
            "wrap_pattern": ("%", ""),
            "case_sensitive": True,
            "label": "ends with",
            "description": "String ends with (case-sensitive)",
        },
        "iends with": {
            "tokens": ("IENDS", "WITH"),
            "wrap_pattern": ("%", ""),
            "case_sensitive": False,
            "label": "iends with",
            "description": "String ends with (case-insensitive)",
        },
        "matches": {
            "tokens": ("MATCHES",),
            "wrap_pattern": ("", ""),
            "case_sensitive": True,
            "label": "matches",
            "description": "Regex pattern match",
        },
    },

    # Logical operators
    "logical": {
        "and": {
            "token": TokenType.AND,
            "expr_class": exp.And,
            "label": "and",
            "description": "Logical AND",
        },
        "or": {
            "token": TokenType.OR,
            "expr_class": exp.Or,
            "label": "or",
            "description": "Logical OR",
        },
    },
}

# =============================================================================
# JOIN TYPES
# =============================================================================

JOIN_TYPES = {
    "inner": {
        "symbols": ["&", "join"],
        "keywords": ["JOIN", "INNER JOIN"],
        "kind": "INNER",
        "label": "inner (&)",
        "description": "Inner join - only matching rows",
        "default": True,
    },
    "left": {
        "symbols": ["&?"],
        "keywords": ["LEFT JOIN", "LEFT OUTER JOIN"],
        "kind": "LEFT",
        "label": "left (&?)",
        "description": "Left outer join - all left rows + matches",
    },
    "right": {
        "symbols": ["?&"],
        "keywords": ["RIGHT JOIN", "RIGHT OUTER JOIN"],
        "kind": "RIGHT",
        "label": "right (?&)",
        "description": "Right outer join - all right rows + matches",
    },
    "full": {
        "symbols": ["?&?"],
        "keywords": ["FULL JOIN", "FULL OUTER JOIN"],
        "kind": "FULL OUTER",
        "label": "full (?&?)",
        "description": "Full outer join - all rows from both sides",
    },
    "cross": {
        "symbols": ["*"],
        "keywords": ["CROSS JOIN"],
        "kind": "CROSS",
        "label": "cross (*)",
        "description": "Cross join - cartesian product",
    },
}

# =============================================================================
# AGGREGATE FUNCTIONS
# =============================================================================

AGGREGATES = {
    "count": {
        "expr_class": exp.Count,
        "label": "count",
        "description": "Count number of rows",
        "allows_distinct": True,
        "category": "basic",
    },
    "sum": {
        "expr_class": exp.Sum,
        "label": "sum",
        "description": "Sum of values",
        "allows_distinct": True,
        "category": "basic",
    },
    "avg": {
        "expr_class": exp.Avg,
        "label": "avg",
        "description": "Average of values",
        "allows_distinct": True,
        "category": "basic",
    },
    "min": {
        "expr_class": exp.Min,
        "label": "min",
        "description": "Minimum value",
        "allows_distinct": False,
        "category": "basic",
    },
    "max": {
        "expr_class": exp.Max,
        "label": "max",
        "description": "Maximum value",
        "allows_distinct": False,
        "category": "basic",
    },
    "count_distinct": {
        "expr_class": exp.Count,
        "label": "count distinct",
        "description": "Count unique values",
        "distinct": True,
        "category": "basic",
    },
}

# =============================================================================
# TRANSFORMS (Pipeline Operations)
# =============================================================================

TRANSFORMS = {
    "where": {
        "keywords": ["WHERE", "FILTER", "IF"],
        "label": "where",
        "icon": "🔍",
        "category": "filter",
        "description": "Filter rows by condition",
        "parameters": {
            "condition": {
                "type": "expression",
                "required": True,
                "label": "condition",
                "description": "Boolean expression to filter rows",
            },
        },
    },

    "select": {
        "keywords": ["SELECT", "PROJECT"],
        "label": "select",
        "icon": "📋",
        "category": "select",
        "description": "Choose which columns to return",
        "parameters": {
            "columns": {
                "type": "list[column]",
                "required": True,
                "label": "columns",
                "description": "List of columns or expressions to select",
            },
        },
    },

    "join": {
        "keywords": ["JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS"],
        "symbols": ["&", "&?", "?&", "?&?", "*"],
        "label": "join",
        "icon": "🔗",
        "category": "join",
        "description": "Join with another table",
        "parameters": {
            "join_type": {
                "type": "enum",
                "required": True,
                "default": "inner",
                "label": "join type",
                "description": "Type of join operation",
                "options": JOIN_TYPES,  # Reference to JOIN_TYPES above
            },
            "table": {
                "type": "table",
                "required": True,
                "label": "table",
                "description": "Table to join with",
            },
            "condition": {
                "type": "expression",
                "required": False,
                "label": "on",
                "description": "Join condition (leave empty to infer from schema)",
            },
        },
    },

    "group_by": {
        "keywords": ["GROUP BY"],
        "label": "group by",
        "icon": "📊",
        "category": "aggregate",
        "description": "Group rows and compute aggregates",
        "parameters": {
            "dimensions": {
                "type": "list[column]",
                "required": True,
                "label": "group by",
                "description": "Columns to group by",
            },
            "aggregates": {
                "type": "list[aggregate]",
                "required": False,
                "label": "aggregations",
                "description": "Aggregate functions to compute",
                "options": AGGREGATES,  # Reference to AGGREGATES above
            },
        },
    },

    "order_by": {
        "keywords": ["ORDER BY"],
        "label": "order by",
        "icon": "⬆️",
        "category": "sort",
        "description": "Sort results",
        "parameters": {
            "expressions": {
                "type": "list[order_expression]",
                "required": True,
                "label": "order by",
                "description": "Columns to sort by with direction",
            },
        },
    },

    "limit": {
        "keywords": ["LIMIT"],
        "label": "limit",
        "icon": "🔢",
        "category": "utility",
        "description": "Limit number of results",
        "parameters": {
            "count": {
                "type": "integer",
                "required": True,
                "label": "count",
                "description": "Maximum number of rows to return",
                "min": 1,
            },
        },
    },

    "extend": {
        "keywords": ["EXTEND"],
        "label": "extend",
        "icon": "➕",
        "category": "transform",
        "description": "Add computed columns",
        "parameters": {
            "columns": {
                "type": "list[aliased_expression]",
                "required": True,
                "label": "columns",
                "description": "New columns with expressions",
            },
        },
    },

    "stash": {
        "keywords": ["STASH"],
        "label": "stash",
        "icon": "💾",
        "category": "utility",
        "description": "Save as CTE for reuse",
        "parameters": {
            "name": {
                "type": "identifier",
                "required": True,
                "label": "as",
                "description": "Name for the CTE",
            },
        },
    },
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_operators():
    """Get all operators flattened into a single list."""
    ops = []
    for category, operators in OPERATORS.items():
        for op_name, op_spec in operators.items():
            ops.append({
                "name": op_name,
                "category": category,
                **op_spec
            })
    return ops

def get_operators_for_widget(widget_type="expression"):
    """Get operators suitable for a specific widget type."""
    if widget_type == "expression":
        # For where/having expressions, include comparison + equality + string
        ops = []
        for cat in ["comparison", "equality", "string"]:
            if cat in OPERATORS:
                ops.extend(OPERATORS[cat].keys())
        return ops
    return []

def get_join_options():
    """Get join type options formatted for UI dropdown."""
    return [
        {
            "value": join_id,
            "label": join_spec["label"],
            "description": join_spec["description"]
        }
        for join_id, join_spec in JOIN_TYPES.items()
    ]

def get_aggregate_options():
    """Get aggregate function options formatted for UI dropdown."""
    return [
        {
            "value": agg_id,
            "label": agg_spec["label"],
            "description": agg_spec["description"]
        }
        for agg_id, agg_spec in AGGREGATES.items()
    ]

def get_transform_schema(transform_name):
    """Get full schema for a transform operation."""
    return TRANSFORMS.get(transform_name)

def get_all_transforms():
    """Get list of all available transforms."""
    return list(TRANSFORMS.keys())
