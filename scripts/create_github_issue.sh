#!/usr/bin/env bash
set -euo pipefail

# Creates a GitHub issue and appends required PR title + branch naming.
#
# Requirements (per .cursorrules):
# - PR Title: "<product>: <description> (#<issue-number>)"
# - Branch: "issue-<issue-number>-<short-slug>"
#
# Usage:
#   ./scripts/create_github_issue.sh \
#     --title "asql: implement when conditional expressions" \
#     --product "asql" \
#     --pr-desc "implement when conditional expressions" \
#     --slug "when-conditional" \
#     --body-file /path/to/body.md
#
# Notes:
# - body template may include placeholders:
#   __ISSUE_NUMBER__, __PR_TITLE__, __BRANCH__

usage() {
  cat <<'EOF'
Usage:
  create_github_issue.sh --title <title> --product <product> --pr-desc <desc> --slug <slug> --body-file <file>

Args:
  --title      Issue title (shown in GitHub)
  --product    Product prefix for PR title (e.g. "asql")
  --pr-desc    PR description (without issue number)
  --slug       Short branch slug (kebab-case)
  --body-file  Markdown file used as the issue body template

Outputs:
  Prints the created issue URL
EOF
}

TITLE=""
PRODUCT=""
PR_DESC=""
SLUG=""
BODY_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title) TITLE="$2"; shift 2;;
    --product) PRODUCT="$2"; shift 2;;
    --pr-desc) PR_DESC="$2"; shift 2;;
    --slug) SLUG="$2"; shift 2;;
    --body-file) BODY_FILE="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ -z "$TITLE" || -z "$PRODUCT" || -z "$PR_DESC" || -z "$SLUG" || -z "$BODY_FILE" ]]; then
  echo "Missing required args" >&2
  usage
  exit 2
fi

if [[ ! -f "$BODY_FILE" ]]; then
  echo "Body file not found: $BODY_FILE" >&2
  exit 2
fi

BODY_TEMPLATE="$(cat "$BODY_FILE")"

ISSUE_URL="$(gh issue create --title "$TITLE" --body "$BODY_TEMPLATE")"
ISSUE_NUMBER="$(gh issue view "$ISSUE_URL" --json number -q .number)"

PR_TITLE="$PRODUCT: $PR_DESC (#$ISSUE_NUMBER)"
BRANCH="issue-$ISSUE_NUMBER-$SLUG"

BODY_FINAL="$BODY_TEMPLATE"
BODY_FINAL="${BODY_FINAL//__ISSUE_NUMBER__/$ISSUE_NUMBER}"
BODY_FINAL="${BODY_FINAL//__PR_TITLE__/$PR_TITLE}"
BODY_FINAL="${BODY_FINAL//__BRANCH__/$BRANCH}"

# Append required info (even if template didn't include placeholders)
BODY_FINAL+=$'\n\n---\n\n'
BODY_FINAL+=$'## PR / branch\n'
BODY_FINAL+="- PR Title: \"$PR_TITLE\""$'\n'
BODY_FINAL+="- Branch: \"$BRANCH\""$'\n'
BODY_FINAL+=$'\n## Close behavior\n'
BODY_FINAL+="Use: Fixes #$ISSUE_NUMBER"$'\n'

gh issue edit "$ISSUE_NUMBER" --body "$BODY_FINAL" >/dev/null

echo "$ISSUE_URL"
