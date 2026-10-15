// ESLint config for the ASQL playground browser frontend.
//
// `asql/playground/static/**/*.js` uses cross-file globals loaded via
// script tags rather than ES modules.

import js from "@eslint/js";
import globals from "globals";

const asqlGlobals = {
  ACCORDION_PREVIEW_ROWS: "readonly",
  CodeMirror: "readonly",
  EXAMPLES_DATA: "readonly",
  Expression: "readonly",
  Sortable: "readonly",
  SortableList: "readonly",
  createAccordionColumnHeaders: "readonly",
  createAccordionDataContainer: "readonly",
  createAccordionDataRow: "readonly",
  createAccordionStepHeader: "readonly",
  generateFakeData: "readonly",
  getTransformLabel: "readonly",
  module: "readonly",
  showOutputError: "readonly",
  visualEditor: "writable",
};

// Defer rules that would flag a large backlog of pre-existing findings.
const sharedRules = {
  "no-unused-vars": "off",
  "no-useless-escape": "off",
  "no-empty": "off",
  "no-redeclare": "off",
  "no-func-assign": "off",
  "no-case-declarations": "off",
  "no-control-regex": "off",
};

export default [
  {
    ignores: ["**/node_modules/**", "**/*.min.js", "vscode-extension/**", ".venv/**", ".smoke-venv/**", "site/**", "dist/**"],
  },
  js.configs.recommended,
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: globals.browser,
    },
    rules: sharedRules,
  },
  {
    files: ["asql/playground/static/**/*.js"],
    languageOptions: {
      globals: asqlGlobals,
    },
  },
  {
    files: ["docs/static/**/*.js"],
    languageOptions: {
      globals: {
        hljs: "readonly",
      },
    },
  },
  {
    files: ["syntax/codemirror/**/*.js"],
    languageOptions: {
      globals: {
        CodeMirror: "readonly",
        define: "readonly",
        require: "readonly",
        module: "readonly",
      },
    },
  },
];
