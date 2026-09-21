#!/bin/bash
# Stop: refuse to end a turn on an fr run that is ADVANCEABLE WITH NOBODY
# WORKING ON IT, and hand back the next command (gh#518; spec
# 2026-09-20-unit-record-unification §4.G). "Keep going" was an fr-goal
# obligation with no enforcing artifact: the cursor knew the next step, and
# nothing consulted it before a turn ended.
#
# Transport only. WHETHER a run is idle is `fr run check --idle`'s answer
# (`fr.run.liveness.is_idle`) and nobody else's: this script knows a session, a
# worktree and an opaque position token, and holds no opinion about a run.
#
# THE RULE OF THIS FILE: it blocks on exactly one thing — a clean, parsed
# "idle" from fr, at a position it has not acted on — and is SILENT, EXIT 0, on
# everything else. A guard that blocks wrongly leaves an operator unable to end
# a turn, which is worse than the stall it prevents. So:
#
#   - It ALWAYS exits 0. On Claude Code exit 2 from a Stop hook IS a block, and
#     `fr` exits 2 for every refusal it makes (the artifact-migration gate
#     included) — so there is NO `set -e` here, deliberately unlike this
#     directory's other hooks, and an EXIT trap forces 0 over anything that
#     slips. Blocking is said on stdout ({"decision": "block"}), never by code.
#   - FAIL OPEN: jq or fr missing, fr erroring / refusing / hanging / too old
#     to know `--idle`, bad JSON, no binding, no worktree, no run — all silence.
#   - Legitimate stops are silence because fr says so: a pending operator gate,
#     an outstanding manual phase, a HELD unit (on Claude Code an executor runs
#     in the background and its return arrives as a notification — a turn that
#     ends meanwhile is CORRECT), a failed step, a finished run, no run.
#   - THE LOOP BREAKER: at most ONE block per run position per session. The
#     position last acted on is remembered beside the session binding; if fr
#     reports the same one again, the stop goes through. Without this a failing
#     `advance` — or a model that simply keeps stopping — is a trap. And if the
#     position cannot be WRITTEN, it does not block at all.
#   - Two independent brakes from the harness itself (both captured from
#     Claude Code 2.1.278, tests/fixtures/hooks/): `stop_hook_active` — this
#     stop was itself caused by a Stop hook — and `background_tasks` /
#     `session_crons` — the session is paused and WILL be woken. It proceeds
#     only on a payload that says `stop_hook_active: false` in so many words; a
#     build that drops the field silences the guard rather than un-braking it.
#     (A third brake is the binary's own: it overrides a Stop hook after
#     CLAUDE_CODE_STOP_HOOK_BLOCK_CAP consecutive blocks, default 8.)
#
# Session -> worktree comes from ~/.cache/fr/sessions/<session-id>.json (gh#500),
# keyed on `worktree` ALONE: that file says `harness: "claude"` where
# `fr.harness` says "claude-code" — two vocabularies, not this hook's to settle.
# NOT the payload's `cwd`: an orchestrator sits in the base clone. Runs with no
# binding are invisible to this guard, and silent (spec §4.I).

trap 'exit 0' EXIT
exec 2>/dev/null

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0
command -v fr >/dev/null 2>&1 || exit 0

# One expression, one answer: the session id, or nothing. Anything unexpected
# in the payload — wrong event, a subagent, a missing or non-boolean
# `stop_hook_active`, work in flight — yields nothing.
session_id=$(printf '%s' "$input" | jq -r '
  if type == "object"
     and .hook_event_name == "Stop"
     and .stop_hook_active == false
     and ((.agent_id // "") == "")
     and ((.background_tasks // []) | length) == 0
     and ((.session_crons // []) | length) == 0
  then (.session_id | strings) else empty end')
case "$session_id" in ''|*/*|.|..) exit 0 ;; esac

sessions_dir="${FR_SESSIONS_DIR:-${HOME:-}/.cache/fr/sessions}"
binding="$sessions_dir/$session_id.json"
[ -f "$binding" ] || exit 0
worktree=$(jq -r 'if type == "object" then (.worktree | strings) else empty end' <"$binding")
[ -n "$worktree" ] && [ -d "$worktree" ] || exit 0

# fr costs ~2s of interpreter start and may block on something this hook cannot
# see. Bounded here rather than left to the harness's hook timeout; `timeout(1)`
# is not on a stock macOS, so the watchdog is a subshell. Every child has its
# stdio detached: the harness waits for the hook's PIPES to close, not merely
# for the hook to exit (fr-session-unbind.sh learned this the hard way).
budget="${FR_IDLE_GUARD_TIMEOUT:-20}"
case "$budget" in ''|*[!0-9]*) budget=20 ;; esac
out=$(mktemp "${TMPDIR:-/tmp}/fr-run-idle-guard.XXXXXX") || exit 0
( cd "$worktree" && exec fr run check --idle --format json ) >"$out" </dev/null &
fr_pid=$!
( sleep "$budget"; kill -9 "$fr_pid" ) >/dev/null </dev/null &
watchdog=$!
wait "$fr_pid"
rc=$?
command -v pkill >/dev/null 2>&1 && pkill -P "$watchdog"
kill "$watchdog"
answer=$(cat "$out")
rm -f "$out"

# Exit 3 AND a parsed object saying idle AND both strings present. Either half
# alone is not an answer.
[ "$rc" -eq 3 ] || exit 0
verdict=$(printf '%s' "$answer" | jq -r 'if type == "object" and .idle == true then "idle" else empty end')
[ "$verdict" = "idle" ] || exit 0
position=$(printf '%s' "$answer" | jq -r '(.position | strings) // empty')
next_command=$(printf '%s' "$answer" | jq -r '(.next_command | strings) // empty')
[ -n "$position" ] && [ -n "$next_command" ] || exit 0
run=$(printf '%s' "$answer" | jq -r '(.run | strings) // "this run"')
detail=$(printf '%s' "$answer" | jq -r '(.detail | strings) // ""')

# The loop breaker. Remember FIRST, block second — and only if the memory took.
memory="$sessions_dir/$session_id.idle-guard"
[ "$(cat "$memory")" != "$position" ] || exit 0
printf '%s\n' "$position" >"$memory" || exit 0
[ "$(cat "$memory")" = "$position" ] || exit 0

jq -n --arg run "$run" --arg detail "$detail" --arg next "$next_command" --arg wt "$worktree" '{
  decision: "block",
  reason: ("fr run \($run) is idle — \($detail) (gh#518). Nothing is blocking it: "
    + "run `\($next)` now, in \($wt), and act on what it prints — a dispatch brief "
    + "means dispatch that unit in this same turn, then report. If you are stopping "
    + "on purpose (the operator asked, or you are waiting on something fr cannot "
    + "see), just stop again: this guard acts once per run position and will let "
    + "it through.")
}'
exit 0
