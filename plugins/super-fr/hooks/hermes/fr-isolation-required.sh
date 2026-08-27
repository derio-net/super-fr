#!/bin/bash
# Hermes Agent pre_tool_call hook: deny edits to tracked source/docs in an
# fr-enabled repo unless they land in a valid fr-isolation workspace — the
# Hermes-harness sibling of plugins/super-fr/hooks/fr-isolation-required.sh
# (Claude Code). Hermes's shell-hooks bridge (agent/shell_hooks.py) pipes a JSON
# payload on stdin and accepts a Claude-Code-style `{"decision":"block",...}` on
# stdout, so the only harness-specific work here is the tool-name vocabulary
# (write_file|patch vs Edit|Write|…), the tool_input path key, and the deny
# shape. The marker/allowlist/fr-enabled decision is the shared library.
#
# JSON parsing goes through the shared library (fr_json_field), which resolves
# python3 — or, failing that, jq — from ABSOLUTE paths. The hook never calls a
# bare `jq`: on the Hermes pod the gateway service PATH omits the PVC bin dir
# where jq lives, so a PATH lookup aborted the hook with exit 127 and silently
# disarmed the guard. Every failure mode below is an explicit JSON decision,
# never a bare non-zero exit.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="$SCRIPT_DIR/../lib/fr-isolation-decision.sh"

# Deny output must not itself need a JSON encoder: escape with sed (always on
# the base PATH) and keep every reason a single line.
json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr -d '\n\r'; }
emit_block() { printf '{"decision":"block","reason":"%s"}\n' "$(json_escape "$1")"; }

if [ ! -r "$LIB" ]; then
  emit_block 'fr-isolation edit guard unavailable: the shared decision library is missing, so the isolation context cannot be established. Refusing edits until the hook install is repaired.'
  exit 0
fi
# shellcheck source=../lib/fr-isolation-decision.sh
. "$LIB"

if ! fr_json_resolve; then
  emit_block 'fr-isolation edit guard unavailable: no JSON parser (python3 or jq) could be resolved, so the tool payload cannot be read. Refusing edits until the dependency is restored.'
  exit 0
fi

input=$(cat)

# Hermes edit-equivalent tools. terminal/execute_code (bash) are gated by the
# sibling fr-isolation-guard.sh, not here.
tool_name=$(printf '%s' "$input" | fr_json_field tool_name) || tool_name='__HOOK_PARSE_ERROR__'
if [ "$tool_name" = "__HOOK_PARSE_ERROR__" ]; then
  emit_block 'fr-isolation edit guard: the pre_tool_call payload is not valid JSON, so the isolation context cannot be established. Refusing the call.'
  exit 0
fi

case "$tool_name" in
  write_file | patch) ;;
  *) exit 0 ;;
esac

# Hermes tool_input carries the target under `path` (write_file) or `file_path`.
file=$(printf '%s' "$input" | fr_json_field tool_input.path) || file='__HOOK_PARSE_ERROR__'
if [ "$file" = "__HOOK_PARSE_ERROR__" ]; then
  emit_block 'fr-isolation edit guard: the pre_tool_call payload is not valid JSON, so the isolation context cannot be established. Refusing the call.'
  exit 0
fi
if [ -z "$file" ]; then
  file=$(printf '%s' "$input" | fr_json_field tool_input.file_path) || file=''
  case "$file" in __HOOK_PARSE_ERROR__) file='' ;; esac
fi

# Call in an `if` so a deny (`return 1`) does not trip `set -e`.
if fr_isolation_decide_edit "$file"; then
  exit 0
fi

emit_block "fr-isolation: edit to '$file' blocked — not inside an fr-isolation workspace. Enter isolation ('fr isolation up' / fr-goal) and edit in the worktree; or add the path to '.fr-isolation-allow'; or set FR_BASE_OK=1 for a deliberate base-clone edit."
exit 0
