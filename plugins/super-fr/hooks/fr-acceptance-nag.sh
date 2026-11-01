#!/bin/bash
# SessionStart hook: inject open acceptance debt (2026-07-04 spec §6.1).
#
# Repos that adopted the acceptance matrix surface their open acceptance debt
# (unwired / walk-owed / not-implemented / failing) into every agent session — the conversational nag the
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
  # A partial migration commits what it could and then refuses (review p1-r4):
  # the commit has landed, so say so even though the nag itself is skipped.
  printf '%s\n' "$err" | grep -m 1 '^fr: migrated and committed' || true
  case "$err" in
    *"must be migrated"*|*"migrate artifacts"*)
      printf 'acceptance nag skipped: artifacts stale — in an fr-isolation workspace (`fr isolation up --branch <branch>`) the next fr command migrates and commits them; elsewhere run `fr migrate artifacts --yes` on a branch\n'
      ;;
  esac
  exit 0
}
# The gate may have migrated and committed on the way in (spec
# 2026-11-01-auto-migrate-own-commit R11): a session's first gated command is
# often this one, so its one-line commit notice is relayed to the session.
notice=$(grep -m 1 '^fr: migrated and committed' "$err_file" 2>/dev/null || true)
rm -f "$err_file"
debt=""
if [ -n "$out" ]; then
  case "$out" in
    *"no acceptance debt"*) ;;
    *) debt=$(printf 'Acceptance debt in this repo (backfill owed — details: fr acceptance status):\n%s\n' "$out") ;;
  esac
fi
[ -n "$notice" ] || [ -n "$debt" ] || exit 0
if [ -n "$notice" ] && [ -n "$debt" ]; then
  message=$(printf '%s\n%s' "$notice" "$debt")
elif [ -n "$notice" ]; then
  message=$notice
else
  message=$debt
fi
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
