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
      keyword: 'from where select project group by sort order take limit join with let as on desc asc descending ascending store and or not is in if set',
      literal: 'true false null',
      built_in: 'sum avg average count min max month year day date upper lower trim concat substring length date_trunc date_format'
    };

    const ASQL_OPERATORS = {
      className: 'operator',
      begin: /(==|!=|<=|>=|[<>]|[+\-*/%]|\|)/,
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

    const ASQL_COMMENT = {
      className: 'comment',
      begin: /#/,
      end: /$/,
      contains: [
        {
          begin: /\b(a|an|the|are|I|I'm|isn't|don't|doesn't|won't|but|just|so|you|your|they|their|it|its|we|our|me|my|was|were|been|being|have|has|had|do|does|did|will|would|should|could|may|might|must|can)\b/i,
          relevance: 0
        }
      ]
    };

    const ASQL_COUNT_SHORTHAND = {
      className: 'keyword',
      begin: /#(?![a-zA-Z0-9_])/,
      relevance: 0
    };

    const ASQL_DESCENDING_SORT = {
      className: 'operator',
      begin: /-\s*[a-zA-Z_][a-zA-Z0-9_]*/,
      relevance: 0
    };

    const ASQL_MULTIWORD_KEYWORDS = {
      className: 'keyword',
      begin: /\b(group\s+by|not\s+in|is\s+not\s+null|is\s+null)\b/i,
      relevance: 10
    };

    const ASQL_FUNCTION = {
      className: 'built_in',
      begin: /\b(sum|avg|average|count|min|max|month|year|day|date|upper|lower|trim|concat|substring|length|date_trunc|date_format)\s*\(/i,
      relevance: 10
    };

    const ASQL_IDENTIFIER = {
      className: 'variable',
      begin: /[a-zA-Z_][a-zA-Z0-9_]*/,
      relevance: 0
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
          ASQL_NUMBER,
          ASQL_MULTIWORD_KEYWORDS,
          ASQL_COUNT_SHORTHAND,
          ASQL_DESCENDING_SORT,
          ASQL_FUNCTION,
          ASQL_OPERATORS,
          ASQL_IDENTIFIER
        ]
      };
    });
  }
})();

