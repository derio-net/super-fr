#!/bin/bash
# SessionEnd: drop this session's workspace binding (spec 2026-09-04 §5.B.2).
# `resume` keeps the id and the worktree, so it is not an end for our purposes.
# Transport only — the engine is `fr isolation detach`. Never blocks: exit 0
# on every path.
#
# The detach is BACKGROUNDED on purpose, and the redirections are load-bearing.
# Claude Code aborts a SessionEnd hook at SESSION_END_HOOK_TIMEOUT_MS_DEFAULT
# (1500ms) and reports it to the operator as "Hook cancelled". A plugin cannot
# raise that floor: getSessionEndHookTimeoutMs only sums `timeout` fields
# declared in settings.json-level hooks, never in a plugin manifest — shipping
# `"timeout": N` in hooks.json is inert. Meanwhile `fr` costs ~2s of Python
# interpreter start before doing any work, so a synchronous call is aborted
# mid-flight: the operator sees an error AND the binding leaks under
# ~/.cache/fr/sessions/.
#
# Fire-and-forget costs nothing that was not already given up: this call is
# best-effort by contract and its output was already discarded. The child must
# hold no descriptor on the hook's stdio, because the harness waits for those
# pipes to close, not merely for the hook to exit — an unredirected child would
# keep it waiting the full ~2s and the abort would fire anyway.

set -eu

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0
command -v fr >/dev/null 2>&1 || exit 0

[ "$(printf '%s' "$input" | jq -r '.reason // empty')" != "resume" ] || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty')
[ -n "$session_id" ] || exit 0

nohup fr isolation detach --session "$session_id" >/dev/null 2>&1 </dev/null &

exit 0
