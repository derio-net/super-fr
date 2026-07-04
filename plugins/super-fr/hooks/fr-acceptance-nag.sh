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

out=$(cd "$repo_root" && fr acceptance status --brief 2>/dev/null) || exit 0
[ -n "$out" ] || exit 0
case "$out" in
  *"no acceptance debt"*) exit 0 ;;
esac

printf 'Acceptance debt in this repo (backfill owed — details: fr acceptance status):\n%s\n' "$out"
exit 0
