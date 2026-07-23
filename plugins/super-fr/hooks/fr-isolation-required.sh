#!/bin/bash
# PreToolUse(Edit|Write|MultiEdit|NotebookEdit) hook: deny edits to tracked
# source/docs in an fr-enabled repo unless they land in a valid fr-isolation
# workspace. Mirrors agent-worktree-required.sh (Agent tool) and complements
# fr-isolation-guard.sh (Bash tool) — but is MARKER-based and
# session-independent, so it catches a session that wanders into another
# fr-enabled repo's base clone and edits it with no active pipeline sentinel
# (#328 Task 3).
#
# Invariant: edits to tracked source in an fr-enabled repo happen inside an
# fr-isolation workspace, never the base clone. Ambiguity (no marker / mismatch
# / wrong place) BLOCKS. Escapes: FR_BASE_OK=1, or a `.fr-isolation-allow`
# globlist at the repo root for operator-managed paths.

set -eu

# The marker/allowlist/fr-enabled decision is shared with the Hermes
# pre_tool_call hook; it lives in one tested library. This entrypoint owns only
# the Claude tool-name gate, the file-path extraction, and the Claude deny JSON.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/fr-isolation-decision.sh
. "$SCRIPT_DIR/lib/fr-isolation-decision.sh"

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
case "$tool_name" in
  Edit | Write | MultiEdit | NotebookEdit) ;;
  *) exit 0 ;;
esac

# jq is load-bearing: under `set -eu` an absent jq aborts here (no deny emitted
# → fail-open). Same posture as fr-isolation-guard.sh — a discipline backstop,
# not a security boundary; the hook tests skip when jq is missing.
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

# Call in an `if` so a deny (`return 1`) does not trip `set -e`.
if fr_isolation_decide_edit "$file"; then
  exit 0
fi

jq -n --arg reason "fr-isolation: edit to \`$file\` blocked — not inside an fr-isolation workspace. Enter isolation (\`fr isolation up\` / fr-goal) and edit in the worktree; or add the path to \`.fr-isolation-allow\`; or set FR_BASE_OK=1 for a deliberate base-clone edit. See ~/.claude/rules/fr-isolation-required.md (#328)." \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
exit 0
