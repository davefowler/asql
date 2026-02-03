/**
 * ASQL Language Definition for Highlight.js
 * 
 * Provides syntax highlighting for ASQL (Analytic SQL) queries
 * in highlight.js-based documentation.
 */

(function() {
  'use strict';
  
  function registerASQLLanguage() {
    const hljs = window.hljs;
    if (!hljs || !hljs.registerLanguage) {
      console.warn('Highlight.js not available. ASQL syntax highlighting will not work.');
      return false;
    }
    
    // Check if already registered
    if (hljs.getLanguage && hljs.getLanguage('asql')) {
      console.log('ASQL language already registered');
      return true;
    }

    // ASQL Keywords - comprehensive list from spec.md
    const ASQL_KEYWORDS = {
      keyword: [
        // Core pipeline operators
        'from', 'where', 'select', 'project', 'group', 'by', 'order', 'take', 'limit',
        // Joins
        'join', 'on', 'with',
        // Sorting
        'desc', 'asc', 'descending', 'ascending',
        // Logical operators
        'and', 'or', 'not', 'is', 'in', 'between', 'like', 'ilike',
        // Conditionals
        'if', 'when', 'then', 'else', 'otherwise',
        // CTEs and variables
        'stash', 'as', 'let', 'set', 'store',
        // Column operators
        'except', 'rename', 'replace',
        // Pivot/Unpivot
        'pivot', 'unpivot', 'explode', 'into', 'values',
        // Window functions
        'per', 'first', 'last', 'number', 'rank', 'dense',
        // Aggregation modifiers
        'distinct', 'of', 'total',
        // String matching
        'contains', 'icontains', 'starts', 'istarts', 'ends', 'iends', 'matches',
        // Cohort analysis
        'cohort',
        // Deduplication
        'deduplicate',
        // Sampling
        'sample'
      ].join(' '),
      literal: 'true false null',
      built_in: [
        // Aggregation functions
        'sum', 'avg', 'average', 'count', 'min', 'max',
        // Date/time functions
        'month', 'year', 'day', 'week', 'quarter', 'hour', 'date',
        'date_trunc', 'date_format', 'now',
        'day_of_week', 'day_of_month', 'day_of_year', 'week_of_year', 'month_of_year', 'quarter_of_year',
        // String functions
        'upper', 'lower', 'trim', 'concat', 'substring', 'length', 'replace', 'string_agg',
        // Window functions
        'prior', 'next', 'running_sum', 'running_avg', 'running_count',
        'rolling_avg', 'rolling_sum',
        'arg_max', 'arg_min', 'row_number',
        // Other
        'coalesce', 'nullif', 'greatest', 'least', 'key'
      ].join(' ')
    };

    const ASQL_OPERATORS = {
      className: 'operator',
      begin: /(==|!=|<=|>=|::|\?\?|&&|[<>]|[+\-*/%]|\|)/,
      relevance: 0
    };

    const ASQL_STRING = {
      className: 'string',
      variants: [
        {
          begin: /"/,
          end: /"/,
          contains: [{ begin: /\\\\./ }]
        },
        {
          begin: /'/,
          end: /'/,
          contains: [{ begin: /\\\\./ }]
        }
      ]
    };

    const ASQL_NUMBER = {
      className: 'number',
      begin: /-?\d+\.?\d*/,
      relevance: 0
    };

    // ASQL uses SQL-style comments (--), NOT # (which is count shorthand)
    const ASQL_COMMENT = {
      className: 'comment',
      begin: /--/,
      end: /$/
    };

    // # is the count shorthand in ASQL, NOT a comment
    // Matches: #, #col, ##col (distinct), #(col), etc.
    const ASQL_COUNT_SHORTHAND = {
      className: 'keyword',
      begin: /#/,
      relevance: 10
    };

    // Date literals with @ prefix: @2024-01-01
    const ASQL_DATE_LITERAL = {
      className: 'number',
      begin: /@\d{4}-\d{2}-\d{2}/,
      relevance: 10
    };

    // Multi-word keywords that need special handling
    const ASQL_MULTIWORD_KEYWORDS = {
      className: 'keyword',
      begin: /\b(group\s+by|order\s+by|not\s+in|is\s+not\s+null|is\s+null|is\s+not|stash\s+as|starts\s+with|ends\s+with|istarts\s+with|iends\s+with|dense\s+rank|from\s+now|days?\s+ago|weeks?\s+ago|months?\s+ago|years?\s+ago|hours?\s+ago|day\s+of\s+week|day\s+of\s+month|day\s+of\s+year|week\s+of\s+year|month\s+of\s+year|quarter\s+of\s+year)\b/i,
      relevance: 10
    };

    // Function calls - function name followed by (
    const ASQL_FUNCTION = {
      className: 'built_in',
      begin: /\b(sum|avg|average|count|min|max|month|year|day|week|quarter|hour|date|upper|lower|trim|concat|substring|length|date_trunc|date_format|now|coalesce|nullif|greatest|least|replace|string_agg|prior|next|running_sum|running_avg|running_count|rolling_avg|rolling_sum|arg_max|arg_min|row_number|key|day_of_week|day_of_month|day_of_year|week_of_year|month_of_year|quarter_of_year)\s*\(/i,
      relevance: 10
    };

    // Join operators: &, &?, ?&, ?&?, *
    const ASQL_JOIN_OPERATORS = {
      className: 'keyword',
      begin: /(\?&\?|&\?|\?&|&(?!\w)|\*(?=\s+\w))/,
      relevance: 5
    };

    try {
      hljs.registerLanguage('asql', function(hljs) {
        return {
          name: 'ASQL',
          aliases: ['asql'],
          case_insensitive: true,
          keywords: ASQL_KEYWORDS,
          contains: [
            ASQL_COMMENT,
            ASQL_STRING,
            ASQL_DATE_LITERAL,
            ASQL_NUMBER,
            ASQL_MULTIWORD_KEYWORDS,
            ASQL_COUNT_SHORTHAND,
            ASQL_FUNCTION,
            ASQL_JOIN_OPERATORS,
            ASQL_OPERATORS
            // Note: No ASQL_IDENTIFIER - let highlight.js handle keyword matching
          ]
        };
      });
      console.log('ASQL language registered successfully with highlight.js');
      return true;
    } catch (e) {
      console.error('Error registering ASQL language:', e);
      return false;
    }
  }
  
  // Try to register immediately if hljs is available
  if (window.hljs && window.hljs.registerLanguage) {
    registerASQLLanguage();
  } else {
    // Wait for hljs to load
    function waitForHljs() {
      if (window.hljs && window.hljs.registerLanguage) {
        registerASQLLanguage();
      } else {
        setTimeout(waitForHljs, 100);
      }
    }
    
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', waitForHljs);
    } else {
      waitForHljs();
    }
  }
  
  // Export registration function for manual calls if needed
  window.registerASQLLanguage = registerASQLLanguage;
})();

