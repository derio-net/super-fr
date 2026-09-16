#!/bin/bash
# Codex PreToolUse hook: deny edits to tracked source/docs in an
# fr-enabled repo unless they land in a valid fr-isolation workspace.
# The Codex sibling of fr-isolation-required.sh (Claude) and
# hermes/fr-isolation-required.sh. Codex accepts the SAME deny shape
# Claude emits, so only the input parsing is harness-specific:
# tool_name is "apply_patch" (even when the matcher says Edit/Write)
# and the patch text arrives in tool_input.command, naming MULTIPLE
# files per call, repo-relative.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="$SCRIPT_DIR/../lib/fr-isolation-decision.sh"
PATCHLIB="$SCRIPT_DIR/../lib/fr-apply-patch-paths.sh"

json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr -d '\n\r'; }
emit_deny() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' \
    "$(json_escape "$1")"
}

[ -r "$LIB" ] && [ -r "$PATCHLIB" ] || {
  emit_deny 'fr-isolation edit guard unavailable: a shared decision library is missing, so the isolation context cannot be established. Refusing edits until the hook install is repaired.'
  exit 0; }
# shellcheck source=../lib/fr-isolation-decision.sh
. "$LIB"
# shellcheck source=../lib/fr-apply-patch-paths.sh
. "$PATCHLIB"

if ! fr_json_resolve; then
  emit_deny 'fr-isolation edit guard unavailable: no JSON parser (python3 or jq) could be resolved, so the tool payload cannot be read. Refusing edits until the dependency is restored.'
  exit 0
fi
if ! fr_git_resolve; then
  emit_deny 'fr-isolation edit guard unavailable: git could not be resolved, so the isolation context cannot be established. Refusing edits until the dependency is restored.'
  exit 0
fi

input=$(cat)
tool_name=$(printf '%s' "$input" | fr_json_field tool_name) || tool_name='__HOOK_PARSE_ERROR__'
if [ "$tool_name" = "__HOOK_PARSE_ERROR__" ]; then
  emit_deny 'fr-isolation edit guard: the PreToolUse payload is not valid JSON, so the isolation context cannot be established. Refusing the call.'
  exit 0
fi
case "$tool_name" in
  apply_patch | Edit | Write | MultiEdit | NotebookEdit) ;;
  *) exit 0 ;;
esac

cwd=$(printf '%s' "$input" | fr_json_field cwd) || cwd=''
command=$(printf '%s' "$input" | fr_json_field tool_input.command) || command=''
file=$(printf '%s' "$input" | fr_json_field tool_input.file_path) || file=''
for v in "$cwd" "$command" "$file"; do
  if [ "$v" = "__HOOK_PARSE_ERROR__" ]; then
    emit_deny 'fr-isolation edit guard: the PreToolUse payload is not valid JSON, so the isolation context cannot be established. Refusing the call.'
    exit 0
  fi
done
[ -n "$cwd" ] || cwd=$PWD

# Candidate targets: an explicit file_path (Edit/Write-shaped
# payloads) else every path the patch body names.
if [ -n "$file" ]; then
  targets=$(printf '%s\n' "$file")
else
  targets=$(fr_apply_patch_paths "$command")
fi
[ -n "$targets" ] || exit 0

# A patch is ATOMIC: Codex cannot partially apply, so ANY blocked
# path denies the whole call.
while IFS= read -r t; do
  [ -n "$t" ] || continue
  abs=$(fr_resolve_against "$cwd" "$t")
  if fr_isolation_decide_edit "$abs"; then continue; fi
  emit_deny "fr-isolation: edit to '$t' blocked - not inside an fr-isolation workspace. Enter isolation ('fr isolation up' / fr-goal) and edit in the worktree; or add the path to '.fr-isolation-allow'; or set FR_BASE_OK=1 for a deliberate base-clone edit."
  exit 0
done <<EOF
$targets
EOF
exit 0
