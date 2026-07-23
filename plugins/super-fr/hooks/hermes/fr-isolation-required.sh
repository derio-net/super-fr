#!/bin/bash
# Hermes Agent pre_tool_call hook: deny edits to tracked source/docs in an
# fr-enabled repo unless they land in a valid fr-isolation workspace — the
# Hermes-harness sibling of plugins/super-fr/hooks/fr-isolation-required.sh
# (Claude Code). Hermes's shell-hooks bridge (agent/shell_hooks.py) pipes a JSON
# payload on stdin and accepts a Claude-Code-style `{"decision":"block",...}` on
# stdout, so the only harness-specific work here is the tool-name vocabulary
# (write_file|patch vs Edit|Write|…), the tool_input path key, and the deny
# shape. The marker/allowlist/fr-enabled decision is the shared library.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../lib/fr-isolation-decision.sh
. "$SCRIPT_DIR/../lib/fr-isolation-decision.sh"

input=$(cat)

# Hermes edit-equivalent tools. terminal/execute_code (bash) are gated by the
# sibling fr-isolation-guard.sh, not here.
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
case "$tool_name" in
  write_file | patch) ;;
  *) exit 0 ;;
esac

# Hermes tool_input carries the target under `path` (write_file) or `file_path`.
file=$(printf '%s' "$input" | jq -r '.tool_input.path // .tool_input.file_path // empty')

# Call in an `if` so a deny (`return 1`) does not trip `set -e`.
if fr_isolation_decide_edit "$file"; then
  exit 0
fi

jq -n --arg reason "fr-isolation: edit to \`$file\` blocked — not inside an fr-isolation workspace. Enter isolation (\`fr isolation up\` / fr-goal) and edit in the worktree; or add the path to \`.fr-isolation-allow\`; or set FR_BASE_OK=1 for a deliberate base-clone edit." \
  '{decision: "block", reason: $reason}'
exit 0
