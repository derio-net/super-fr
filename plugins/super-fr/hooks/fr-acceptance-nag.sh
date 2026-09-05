#!/bin/bash
# SessionStart hook: inject open acceptance debt (2026-07-04 spec §6.1).
#
# Repos that adopted the acceptance matrix surface their open skipped /
# not-implemented rows into every agent session — the conversational nag the
# operator mandated (warnings on a cron run's Actions page reach nobody).
# Output is capped by `fr acceptance status --brief` (counts + 3 oldest).
#
# Fail-open: ANY missing precondition (no cwd, no git, no matrix, no fr, a
# broken matrix) exits 0 silently — session start must never break on a nag.

set -eu

command -v jq >/dev/null 2>&1 || exit 0

input=$(cat)
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$cwd" ] && [ -d "$cwd" ] || exit 0

repo_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -f "$repo_root/docs/acceptance/matrix.yaml" ] || exit 0
command -v fr >/dev/null 2>&1 || exit 0

# Capture stderr separately: `fr acceptance status` is exempt from the
# artifact-migration gate, but `fr` still refuses when it cannot establish the
# repo's state — and swallowing that made the nag disappear with no explanation
# at the exact moment the operator most needed to know why (review r5-c5).
err_file=$(mktemp) || exit 0
out=$(cd "$repo_root" && fr acceptance status --brief 2>"$err_file") || {
  err=$(cat "$err_file" 2>/dev/null)
  rm -f "$err_file"
  case "$err" in
    *"must be migrated"*|*"migrate artifacts"*)
      printf 'acceptance nag skipped: artifacts stale — run `fr migrate artifacts --yes`\n'
      ;;
  esac
  exit 0
}
rm -f "$err_file"
[ -n "$out" ] || exit 0
case "$out" in
  *"no acceptance debt"*) exit 0 ;;
esac

message=$(printf 'Acceptance debt in this repo (backfill owed — details: fr acceptance status):\n%s\n' "$out")
event=$(printf '%s' "$input" | jq -r '.hook_event_name // empty')
if [ "$event" = "pre_llm_call" ]; then
  first_turn=$(printf '%s' "$input" | jq -r '.extra.is_first_turn // false')
  [ "$first_turn" = "true" ] || exit 0
  jq -n --arg context "$message" '{context: $context}'
elif [ "$event" = "on_session_start" ]; then
  # Forward-compatible with a Hermes release that consumes lifecycle context.
  jq -n --arg context "$message" '{context: $context}'
else
  printf '%s\n' "$message"
fi
exit 0
