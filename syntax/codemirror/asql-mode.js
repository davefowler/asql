/**
 * ASQL Syntax Highlighting Mode for CodeMirror
 * 
 * This file provides syntax highlighting for ASQL (Analytic SQL) queries
 * in CodeMirror-based editors. It can be included in any web application
 * that uses CodeMirror.
 * 
 * Usage:
 *   1. Include CodeMirror library
 *   2. Include this file after CodeMirror
 *   3. Use mode: 'text/x-asql' or mode: 'asql' in CodeMirror options
 * 
 * Example:
 *   <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.js"></script>
 *   <script src="syntax/codemirror/asql-mode.js"></script>
 *   <script>
 *     const editor = CodeMirror(document.getElementById('editor'), {
 *       mode: 'text/x-asql',
 *       lineNumbers: true
 *     });
 *   </script>
 * 
 * Features:
 *   - Keywords: from, where, select, group by, order by, take, join, with, stash, etc.
 *   - Functions: sum, avg, count, min, max, date functions, string functions
 *   - Operators: ==, !=, <=, >=, <, >, +, -, *, /, %, || (null coalescing), :: (type casting)
 *   - Strings: Single and double quoted strings
 *   - Numbers: Integers and floats
 *   - Comments: -- to end of line (SQL-style)
 *   - Special ASQL syntax: # (count shorthand), -column (descending order), col::TYPE (type casting)
 *   - Multi-word keywords: group by, not in, is null, is not null, stash as
 * 
 * @version 1.1.0
 * @license MIT
 */

// Works with CodeMirror loaded via script tag or module system
(function(mod) {
  if (typeof exports == "object" && typeof module == "object") // CommonJS
    mod(require("codemirror"));
  else if (typeof define == "function" && define.amd) // AMD
    define(["codemirror"], mod);
  else {
    // Plain browser env - try immediately, then wait if needed
    if (typeof CodeMirror !== "undefined" && CodeMirror.defineMode) {
      // CodeMirror is ready, register immediately
      mod(CodeMirror);
    } else {
      // CodeMirror not ready yet, wait for it
      let attempts = 0;
      const maxAttempts = 40; // Max 2 seconds
      function waitForCodeMirror() {
        attempts++;
        if (typeof CodeMirror !== "undefined" && CodeMirror.defineMode) {
          mod(CodeMirror);
        } else if (attempts < maxAttempts) {
          setTimeout(waitForCodeMirror, 50);
        } else {
          console.error("CodeMirror not available after waiting. ASQL mode not registered.");
        }
      }
      waitForCodeMirror();
    }
  }
})(function(CodeMirror) {
  if (!CodeMirror) {
    console.error("CodeMirror is not defined");
    return;
  }
  
  if (!CodeMirror.defineMode) {
    console.error("CodeMirror.defineMode is not available. CodeMirror version:", CodeMirror.version);
    return;
  }

  try {
    CodeMirror.defineMode("asql", function(config, parserConfig) {
    // Keywords - comprehensive list from spec.md
    const keywords = {
        // Core pipeline operators
        "from": true, "where": true, "select": true, "project": true,
        "group": true, "by": true, "order": true,
        "take": true, "limit": true, "join": true, "with": true,
        // Sorting
        "desc": true, "asc": true, "descending": true, "ascending": true,
        // Logical operators
        "and": true, "or": true, "not": true, "is": true, "in": true,
        "between": true, "like": true, "ilike": true,
        // Conditionals
        "if": true, "when": true, "then": true, "else": true, "otherwise": true,
        // CTEs and variables
        "stash": true, "as": true, "let": true, "set": true, "store": true,
        // Column operators
        "except": true, "rename": true, "replace": true,
        // Pivot/Unpivot
        "pivot": true, "unpivot": true, "explode": true, "into": true, "values": true,
        // Window functions
        "per": true, "first": true, "last": true, "number": true, "rank": true, "dense": true,
        // Aggregation modifiers
        "distinct": true, "of": true, "total": true,
        // String matching
        "contains": true, "icontains": true, "starts": true, "istarts": true,
        "ends": true, "iends": true, "matches": true,
        // Cohort analysis
        "cohort": true,
        // Deduplication
        "deduplicate": true,
        // Sampling
        "sample": true
    };
    
    // Functions
    const functions = {
        // Aggregation functions
        "sum": true, "avg": true, "average": true, "count": true,
        "min": true, "max": true,
        // Date/time functions
        "month": true, "year": true, "day": true, "week": true, "quarter": true, "hour": true,
        "date": true, "date_trunc": true, "date_format": true, "now": true,
        "day_of_week": true, "day_of_month": true, "day_of_year": true,
        "week_of_year": true, "month_of_year": true, "quarter_of_year": true,
        // String functions
        "upper": true, "lower": true, "trim": true, "concat": true,
        "substring": true, "length": true, "string_agg": true,
        // Window functions
        "prior": true, "next": true, "running_sum": true, "running_avg": true, "running_count": true,
        "rolling_avg": true, "rolling_sum": true, "arg_max": true, "arg_min": true, "row_number": true,
        // Other
        "coalesce": true, "nullif": true, "greatest": true, "least": true, "key": true
    };
    
    // Booleans and null
    const booleans = {
        "true": true, "false": true, "null": true
    };
    
    function tokenBase(stream, state) {
        // Handle whitespace
        if (stream.eatSpace()) return null;
        
        // Handle comments (-- to end of line, SQL-style)
        if (stream.match(/^--/)) {
            stream.skipToEnd();
            return "comment";
        }
        
        // Handle count shorthand (#) - must be before other operators
        // # alone = COUNT(*), # col = COUNT(col), # distinct col = COUNT(DISTINCT col)
        if (stream.match(/^#/)) {
            return "keyword";
        }
        
        // Handle strings (double quotes)
        if (stream.match(/^"/)) {
            state.tokenize = tokenString('"');
            return state.tokenize(stream, state);
        }
        
        // Handle strings (single quotes)
        if (stream.match(/^'/)) {
            state.tokenize = tokenString("'");
            return state.tokenize(stream, state);
        }
        
        // Handle numbers (integers and floats, including negative)
        if (stream.match(/^-?\d+\.?\d*/)) {
            return "number";
        }
        
        // Handle comparison operators (==, !=, <=, >=, <, >)
        if (stream.match(/^(==|!=|<=|>=|[<>])/)) {
            return "operator";
        }
        
        // Handle null coalescing operator (??)
        if (stream.match(/^\?\?/)) {
            return "operator";
        }
        
        // Handle type casting operator (::)
        if (stream.match(/^::/)) {
            return "operator";
        }
        
        // Handle date literals (@2024-01-01)
        if (stream.match(/^@\d{4}-\d{2}-\d{2}/)) {
            return "number";
        }
        
        // Handle arithmetic operators
        if (stream.match(/^[+\-*/%]/)) {
            return "operator";
        }
        
        // Handle single pipeline operator (|)
        if (stream.match(/^\|/)) {
            return "operator";
        }
        
        // Handle descending order prefix (-identifier)
        if (stream.match(/^-\s*[a-zA-Z_][a-zA-Z0-9_]*/)) {
            return "variable";
        }
        
        // Handle "not in" as a single operator
        if (stream.match(/^not\s+in/i)) {
            return "keyword";
        }
        
        // Handle "is null" and "is not null"
        if (stream.match(/^is\s+(not\s+)?null/i)) {
            return "keyword";
        }
        
        // Handle "group by" as a single keyword
        if (stream.match(/^group\s+by/i)) {
            return "keyword";
        }
        
        // Handle "stash as" as a single keyword
        if (stream.match(/^stash\s+as/i)) {
            return "keyword";
        }
        
        // Handle "from now" in relative date expressions (before "from" matches as keyword)
        if (stream.match(/^from\s+now/i)) {
            return "number";
        }
        
        // Handle identifiers and keywords
        if (stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/)) {
            const word = stream.current().toLowerCase();
            
            if (keywords[word]) {
                return "keyword";
            }
            
            if (functions[word]) {
                // Check if followed by opening parenthesis
                if (stream.peek() === '(') {
                    return "def";
                }
                return "variable";
            }
            
            if (booleans[word]) {
                return "atom";
            }
            
            return "variable";
        }
        
        // Handle any other character
        stream.next();
        return null;
    }
    
    function tokenString(quote) {
        return function(stream, state) {
            let escaped = false;
            while (!stream.eol()) {
                if (!escaped && stream.peek() === quote) {
                    stream.next();
                    state.tokenize = tokenBase;
                    return "string";
                }
                escaped = stream.next() === "\\" && !escaped;
            }
            state.tokenize = tokenString(quote);
            return "string";
        };
    }
    
    return {
        startState: function() {
            return {
                tokenize: tokenBase
            };
        },
        
        token: function(stream, state) {
            if (stream.eol()) state.tokenize = tokenBase;
            return state.tokenize(stream, state);
        },
        
        lineComment: "--",
        fold: "indent"
    };
});

// Register the mode with MIME type
    CodeMirror.defineMIME("text/x-asql", "asql");

    console.log("ASQL mode registered successfully");
  } catch (error) {
    console.error("Error registering ASQL mode:", error);
  }
});

