#!/bin/bash
# Idempotently allowlist `fr-phase-executor` in the org agent-worktree hook.
#
# fr-goal dispatches each plan phase to the narrow `fr-phase-executor` subagent
# (2026-07-22 fr-goal-subagent-execution spec §B.1, option 3). That subagent
# writes code, so the org hook `agent-worktree-required.sh` would block it for
# lacking its own worktree — but it runs SERIALLY inside the already-isolated fr
# workspace, so a private worktree is neither needed nor wanted (one shared
# branch → one PR). super-fr co-manages the hook's allowlist for this one type.
#
# Usage: ensure-phase-executor-allowlist.sh <path-to-agent-worktree-required.sh>
#
# - Inserts `fr-phase-executor` into the existing allowlist `case` pattern.
# - Idempotent: a second run is a no-op.
# - Safe no-op when the hook file is absent (e.g. a machine without the org
#   convention installed) — never creates it.

set -eu

hook="${1:?usage: ensure-phase-executor-allowlist.sh <hook-path>}"

# Absent hook → nothing to manage. Exit success so install.sh flows on.
[ -f "$hook" ] || exit 0

# Already present → idempotent no-op.
if grep -q 'fr-phase-executor' "$hook"; then
  exit 0
fi

# The allowlist is a single case arm whose pattern is a `|`-joined list of
# bypassing subagent types, e.g.:
#   Explore|Plan|claude-code-guide|statusline-setup|hookify:conversation-analyzer)
# Anchor on the known-stock `Explore|Plan` prefix and prepend our type to the
# list. Using Explore as the anchor keeps the edit robust to trailing members.
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
sed 's/^\([[:space:]]*\)Explore|Plan|/\1fr-phase-executor|Explore|Plan|/' "$hook" >"$tmp"

if ! grep -q 'fr-phase-executor' "$tmp"; then
  # Anchor not found (hook shape changed). Fail loud rather than silently skip,
  # so drift is visible instead of leaving dispatch mysteriously blocked.
  echo "ensure-phase-executor-allowlist: could not find the 'Explore|Plan|' allowlist anchor in $hook" >&2
  exit 1
fi

cat "$tmp" >"$hook"
echo "allowlisted fr-phase-executor in $hook"
