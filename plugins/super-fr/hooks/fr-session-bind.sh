#!/bin/bash
# PostToolUse(Bash): bind this session to the fr workspace the command just
# targeted (spec 2026-09-04 §5.B.1). Transport only — the engine is
# `fr isolation attach/detach`. Never blocks: exits 0 on every path, and an
# attach after a FAILED `up` finds no state and is a harmless no-op.
#
# Matches, start-anchored (only a LEADING `fr …`, mirroring the guard):
#   fr isolation up|exec [--branch <b>] … → attach --session --repo [--branch]
#   fr run start <shape> --branch <b> …    → attach (same branch; #500)
#   fr isolation down …                    → detach --session
# A leading `cd <dir> &&|;` folds into --repo — same shape the guard strips
# (#421). Subagent input (agent_id present) never rebinds the parent session.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/fr-isolation-decision.sh
. "$SCRIPT_DIR/lib/fr-isolation-decision.sh"

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0
command -v fr >/dev/null 2>&1 || exit 0

[ "$(printf '%s' "$input" | jq -r '.tool_name // empty')" = "Bash" ] || exit 0
[ -z "$(printf '%s' "$input" | jq -r '.agent_id // empty')" ] || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
[ -n "$session_id" ] && [ -n "$cwd" ] && [ -n "$command" ] || exit 0

first=$(printf '%s\n' "$command" | sed -n '1p')
repo="$cwd"

# Groups: 2 = "dq", 3 = 'sq', 4 = bare target; 6 = the rest after && or ;.
cd_re='^[[:space:]]*cd[[:space:]]+("([^"]+)"|'\''([^'\'']+)'\''|([^[:space:];&|]+))[[:space:]]*(&&|;)[[:space:]]*(.*)$'
cd_target=$(printf '%s' "$first" | sed -nE "s/$cd_re/\\2\\3\\4/p")
if [ -n "$cd_target" ]; then
  case "$cd_target" in "~"*) cd_target="$HOME${cd_target#\~}" ;; esac
  repo=$(cd "$cwd" 2>/dev/null && cd "$cd_target" 2>/dev/null && pwd -P) || exit 0
  first=$(printf '%s' "$first" | sed -nE "s/$cd_re/\\6/p")
fi

# `FR_ISOLATION_TARGET=worktree fr isolation up` (the form the guard's own deny
# prescribes on a docker-less host) and `uv run fr run start` (AGENTS.md's form
# inside a worktree) are still those commands. Unrecognised, they never bound
# the session, the sentinel was never stamped, and a reaped workspace locked the
# session out: #472, on exactly the hosts that use the prefix (review H1).
first=$(fr_strip_command_prefix "$first")

verb=$(printf '%s' "$first" | sed -nE 's/^[[:space:]]*fr[[:space:]]+isolation[[:space:]]+(up|exec|down)([[:space:]]|$).*/\1/p')
# `fr run start` ENTERS isolation itself (spec 2026-09-20 §3.C.2), so it creates
# exactly the workspace this hook exists to attribute — but it could never match
# the regex above, which is why every fr-goal workspace reported sessions=none
# (#500). Mapped to `up` so it reuses the attach branch and the --branch regex
# below unchanged. Start-anchored like everything else here: `echo fr run start`
# must not bind. Only `start`; `advance`/`resolve` create no workspace.
if [ -z "$verb" ]; then
  verb=$(printf '%s' "$first" | sed -nE 's/^[[:space:]]*fr[[:space:]]+run[[:space:]]+start([[:space:]]|$).*/up/p')
fi
[ -n "$verb" ] || exit 0

branch=$(printf '%s' "$first" | sed -nE 's/.*--branch(=|[[:space:]]+)("([^"]+)"|'\''([^'\'']+)'\''|([^[:space:]]+)).*/\3\4\5/p')

case "$verb" in
  up|exec)
    if [ -n "$branch" ]; then
      fr isolation attach --session "$session_id" --repo "$repo" --branch "$branch" --harness claude >/dev/null 2>&1 || true
    else
      fr isolation attach --session "$session_id" --repo "$repo" --harness claude >/dev/null 2>&1 || true
    fi ;;
  down)
    fr isolation detach --session "$session_id" >/dev/null 2>&1 || true ;;
esac

exit 0
