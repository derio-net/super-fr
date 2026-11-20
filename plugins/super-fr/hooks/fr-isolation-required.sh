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

# The deny is written by the resolved JSON parser (python3 or jq), never a bare
# `jq`: under `set -eu` a missing jq used to abort the hook before it printed a
# decision, which the harness reads as "no opinion" (super-fr#1509).
# A deny with a fixed reason, written without any parser: what is printed when
# the parser itself is missing or broken. Fixed text, so it needs no escaping.
deny_fixed() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$1"
}

deny() {
  _out=""
  if [ "$FR_JSON_KIND" = "python3" ]; then
    _out=$("$FR_JSON_BIN" -I -c 'import json, sys
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
    "permissionDecision": "deny", "permissionDecisionReason": sys.argv[1]}}))' "$1" 2>/dev/null) || _out=""
  else
    _out=$("$FR_JSON_BIN" -n --arg reason "$1" \
      '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}' 2>/dev/null) || _out=""
  fi
  # A parser that resolved but cannot run (a pyenv shim with no version selected,
  # the Xcode CLT stub) still denies, with the reason it could not write.
  if [ -n "$_out" ]; then printf '%s\n' "$_out"; else deny_fixed "fr-isolation: edit blocked (the JSON parser failed while writing the reason; super-fr#1509)."; fi
}

unreadable='fr-isolation edit guard: the PreToolUse payload could not be read (not valid JSON, or the JSON parser failed), so the edit cannot be judged. Refusing it (super-fr#1509).'

if ! fr_json_resolve; then
  # No parser: the payload cannot be read, so no edit can be judged.
  deny_fixed 'fr-isolation edit guard unavailable: no JSON parser (python3 or jq) could be resolved, so the tool payload cannot be read. Refusing edits until one is restored (super-fr#1509).'
  exit 0
fi

input=$(cat)

# Every read is guarded: under `set -eu` a parser that exits non-zero would
# otherwise end the hook with no decision, which the harness reads as allow.
tool_name=$(printf '%s' "$input" | fr_json_field tool_name) || tool_name='__HOOK_PARSE_ERROR__'
if [ "$tool_name" = "__HOOK_PARSE_ERROR__" ]; then
  deny_fixed "$unreadable"
  exit 0
fi
case "$tool_name" in
  Edit | Write | MultiEdit | NotebookEdit) ;;
  *) exit 0 ;;
esac

# NotebookEdit's target is `notebook_path` (its schema has no `file_path`), so
# reading only `file_path` handed the gate an empty path, which it allows.
file=$(printf '%s' "$input" | fr_json_field tool_input.file_path) || file='__HOOK_PARSE_ERROR__'
if [ -z "$file" ]; then
  file=$(printf '%s' "$input" | fr_json_field tool_input.notebook_path) || file='__HOOK_PARSE_ERROR__'
fi
if [ "$file" = "__HOOK_PARSE_ERROR__" ]; then
  deny_fixed "$unreadable"
  exit 0
fi

# Call in an `if` so a deny (`return 1`) does not trip `set -e`.
if fr_isolation_decide_edit "$file"; then
  exit 0
fi

drift=$(fr_isolation_drift_reason "$file")
if [ -n "$drift" ]; then
  deny "fr-isolation: edit to \`$file\` blocked — $drift (#553)"
  exit 0
fi
deny "fr-isolation: edit to \`$file\` blocked — not inside an fr-isolation workspace. Enter isolation (\`fr isolation up --branch <branch>\` / fr-goal) and edit in the worktree; or add the path to \`.fr-isolation-allow\`; or set FR_BASE_OK=1 for a deliberate base-clone edit. See ~/.claude/rules/fr-isolation-required.md (#328)."
exit 0
