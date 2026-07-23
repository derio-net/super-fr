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

# Claude Code dispatches a PLUGIN subagent by its plugin-qualified id, so the
# hook sees `super-fr:fr-phase-executor` — not the bare directory name. The
# already-present `hookify:conversation-analyzer` entry is the precedent. An
# allowlist carrying only the bare name never matches, and every fr-goal phase
# dispatch is blocked (fr-goal then degrades to inline execution).
QUALIFIED='super-fr:fr-phase-executor'

# Idempotence probes the QUALIFIED name specifically. Probing the bare name (as
# this script originally did) is satisfied by a stale bare-only entry, so every
# reinstall reported "already done" and the hook never self-healed.
if grep -q "$QUALIFIED" "$hook"; then
  exit 0
fi

# The allowlist is a single case arm whose pattern is a `|`-joined list of
# bypassing subagent types, e.g.:
#   Explore|Plan|claude-code-guide|statusline-setup|hookify:conversation-analyzer)
# Anchor on the known-stock `Explore|Plan` prefix and prepend our types to the
# list. Using Explore as the anchor keeps the edit robust to trailing members.
#
# ONLY the qualified id is inserted — that is what Claude Code sends, and the
# allowlist must stay fail-closed for anything else. The first expression strips
# a stale bare-only entry left by the pre-fix script, so an already-broken hook
# is repaired rather than ending up with both spellings.
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
sed -e 's/^\([[:space:]]*\)fr-phase-executor|Explore|Plan|/\1Explore|Plan|/' \
    -e "s/^\([[:space:]]*\)Explore|Plan|/\1$QUALIFIED|Explore|Plan|/" \
    "$hook" >"$tmp"

if ! grep -q "$QUALIFIED" "$tmp"; then
  # Anchor not found (hook shape changed). Fail loud rather than silently skip,
  # so drift is visible instead of leaving dispatch mysteriously blocked.
  echo "ensure-phase-executor-allowlist: could not find the 'Explore|Plan|' allowlist anchor in $hook" >&2
  exit 1
fi

cat "$tmp" >"$hook"
echo "allowlisted $QUALIFIED in $hook"
