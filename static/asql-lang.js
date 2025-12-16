/**
 * ASQL Language Definition for Highlight.js
 * 
 * Provides syntax highlighting for ASQL (Analytic SQL) queries
 * in highlight.js-based documentation.
 */

(function() {
  'use strict';
  
  // Get hljs from global scope (loaded via script tag)
  const hljs = window.hljs;
  
  if (!hljs || !hljs.registerLanguage) {
    // If hljs isn't loaded yet, wait for it
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function() {
        setTimeout(registerASQLLanguage, 100);
      });
    } else {
      setTimeout(registerASQLLanguage, 100);
    }
    return;
  }
  
  registerASQLLanguage();
  
  function registerASQLLanguage() {
    const hljs = window.hljs;
    if (!hljs || !hljs.registerLanguage) {
      console.warn('Highlight.js not available. ASQL syntax highlighting will not work.');
      return;
    }

    const ASQL_KEYWORDS = {
      keyword: [
        // Core query structure
        'from', 'where', 'select', 'group', 'by', 'order', 'take', 'limit', 'offset',
        'join', 'left', 'right', 'inner', 'outer', 'cross', 'full', 'on',
        'with', 'set', 'as', 'stash',
        // Logical operators
        'and', 'or', 'not', 'is', 'in', 'like', 'between', 'exists',
        // Set operations
        'union', 'except', 'intersect', 'all',
        // Column operations
        'rename', 'prefix', 'distinct',
        // Pivot/Unpivot
        'pivot', 'unpivot', 'fill',
        // Window operations
        'per', 'first', 'last', 'number', 'rank', 'over', 'partition', 'rows', 'range',
        'preceding', 'following', 'unbounded', 'current', 'row',
        // Conditional
        'if', 'then', 'else', 'end', 'case', 'when', 'qualify',
        // Misc
        'having', 'asc', 'desc', 'ascending', 'descending', 'nulls'
      ].join(' '),
      literal: 'true false null',
      built_in: [
        // Aggregate functions
        'sum', 'avg', 'average', 'total', 'count', 'min', 'max',
        // Date truncation
        'year', 'month', 'week', 'day', 'hour', 'minute', 'second', 'quarter',
        'day_of_week', 'day_of_month', 'day_of_year', 'week_of_year', 'month_of_year',
        // Date functions
        'date_trunc', 'date_add', 'date_diff', 'date_format', 'datediff',
        'days', 'weeks', 'months', 'years', 'hours', 'minutes', 'seconds',
        'days_since', 'days_until', 'today', 'now', 'current_date', 'current_timestamp',
        // String functions
        'upper', 'lower', 'trim', 'ltrim', 'rtrim', 'concat', 'substring', 'length', 'replace', 'split',
        // Math functions
        'abs', 'round', 'floor', 'ceil', 'ceiling', 'sqrt', 'power',
        // Window functions
        'row_number', 'dense_rank', 'lag', 'lead', 'first_value', 'last_value', 'nth_value',
        'prior', 'next', 'running_sum', 'running_avg', 'running_count',
        'rolling_sum', 'rolling_avg', 'arg_max', 'arg_min',
        // Other functions
        'coalesce', 'nullif', 'cast', 'key', 'string_agg', 'array_agg',
        'date_spine', 'series'
      ].join(' ')
    };

    const ASQL_COMMENT = {
      className: 'comment',
      variants: [
        // Single line comment with --
        {
          begin: '--',
          end: '$'
        },
        // Multi-line comment
        {
          begin: '/\\*',
          end: '\\*/'
        }
      ]
    };

    const ASQL_STRING = {
      className: 'string',
      variants: [
        {
          begin: /"/,
          end: /"/,
          contains: [{ begin: /\\./ }]
        },
        {
          begin: /'/,
          end: /'/,
          contains: [{ begin: /\\./ }]
        }
      ]
    };

    const ASQL_NUMBER = {
      className: 'number',
      begin: /-?\b\d+\.?\d*\b/,
      relevance: 0
    };

    const ASQL_OPERATORS = {
      className: 'operator',
      begin: /==|!=|<>|<=|>=|[<>]|\?\?|[+\-*/%]|\|/,
      relevance: 0
    };

    const ASQL_COUNT_SHORTHAND = {
      className: 'built_in',
      begin: /#(?![a-zA-Z0-9_])/,
      relevance: 10
    };

    const ASQL_DESCENDING_SORT = {
      className: 'operator',
      begin: /-(?=[a-zA-Z_])/,
      relevance: 0
    };

    const ASQL_DATE_LITERAL = {
      className: 'number',
      begin: /@\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2})?/,
      relevance: 10
    };

    const ASQL_RELATIVE_DATE = {
      className: 'built_in',
      begin: /\b\d+\s+(?:day|days|week|weeks|month|months|year|years|hour|hours|minute|minutes|second|seconds)\s+(?:ago|from\s+now)\b/i,
      relevance: 10
    };

    const ASQL_MULTIWORD_KEYWORDS = {
      className: 'keyword',
      begin: /\b(?:group\s+by|order\s+by|partition\s+by|not\s+in|is\s+not\s+null|is\s+null|left\s+join|right\s+join|inner\s+join|outer\s+join|cross\s+join|full\s+join|stash\s+as|distinct\s+on|dense\s+rank)\b/i,
      relevance: 10
    };

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
          ASQL_RELATIVE_DATE,
          ASQL_NUMBER,
          ASQL_MULTIWORD_KEYWORDS,
          ASQL_COUNT_SHORTHAND,
          ASQL_DESCENDING_SORT,
          ASQL_OPERATORS
        ]
      };
    });
    
    console.log('ASQL language registered with highlight.js');
  }
})();
