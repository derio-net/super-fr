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

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# The hook has TWO surfaces naming the allowlist, and they drift apart: the
# `case` arm that actually decides, and a human-readable "Exempt: …" stderr
# message a few lines below that tells a blocked caller what IS allowed. Each
# gets its OWN probe and its own repair.
#
# Probing once for both is the exact bug this file already records: a probe
# satisfied by one surface reports "already done" for the other, forever. (The
# original probe was `grep -q fr-phase-executor`, which a stale *bare* entry
# satisfied, so every reinstall skipped the repair.) So: no shared early exit.
changed=0

# --- 1. The `case` arm (authoritative; drift here fails loud) ----------------
#
# The allowlist is a single case arm whose pattern is a `|`-joined list, e.g.:
#   Explore|Plan|claude-code-guide|statusline-setup|hookify:conversation-analyzer)
# Anchor on the known-stock `Explore|Plan` prefix and prepend our type. Using
# Explore as the anchor keeps the edit robust to trailing members.
#
# ONLY the qualified id is inserted — that is what Claude Code sends, and the
# allowlist must stay fail-closed for anything else. The strip expressions
# remove a stale bare entry left by the pre-fix script, so an already-broken
# hook is repaired rather than ending up with both spellings — at the head of
# the arm (where the pre-fix script put it) AND as a `|`-delimited member
# anywhere else, which the head-anchored form alone silently left behind
# (rev2-f6).
#
# Every expression is scoped to NON-COMMENT lines, and so is the probe: a hook
# whose header comment documents its own allowlist verbatim otherwise satisfies
# a file-wide probe, so the real `case` arm is never patched and this script
# exits 0 reporting success while dispatch stays blocked — re-creating the
# silent inline-degradation incident it was written to end (rev2-f6).
if ! grep -v '^[[:space:]]*#' "$hook" | grep -q "$QUALIFIED|Explore|Plan|"; then
  sed -e '/^[[:space:]]*#/!s/^\([[:space:]]*\)fr-phase-executor|Explore|Plan|/\1Explore|Plan|/' \
      -e '/^[[:space:]]*#/!s/|fr-phase-executor\([|)]\)/\1/' \
      -e "/^[[:space:]]*#/!s/^\([[:space:]]*\)Explore|Plan|/\1$QUALIFIED|Explore|Plan|/" \
      "$hook" >"$tmp"

  if ! grep -v '^[[:space:]]*#' "$tmp" | grep -q "$QUALIFIED|Explore|Plan|"; then
    # Anchor not found (hook shape changed). Fail loud rather than silently
    # skip, so drift is visible instead of leaving dispatch mysteriously
    # blocked.
    echo "ensure-phase-executor-allowlist: could not find the 'Explore|Plan|' allowlist anchor in $hook" >&2
    exit 1
  fi

  cat "$tmp" >"$hook"
  changed=1
fi

# --- 2. The "Exempt: …" stderr message (advisory; absence is fine) -----------
#
# super-fr#420 checklist item 4: left alone, this message keeps listing the
# pre-fix five and so contradicts the `case` arm three lines above it — anyone
# reading a denial to learn what is permitted is told the wrong thing.
#
# Unlike the `case` anchor this is NOT required to exist: the message is the org
# hook's own prose, and a host whose hook has none is simply left alone. Absence
# is a silent no-op, never a failure.
#
# Decided PER LINE, and never on a line that is not ours to edit (rev2-f5). The
# live org hook carries the exempt list TWICE — a "Read-only subagent types (…)"
# rationale comment as well as the real stderr message — so the previous
# file-wide probe plus unanchored expressions:
#   * rewrote the comment too, asserting that fr-phase-executor is a READ-ONLY
#     subagent type, which super-fr's own shipped rule contradicts in as many
#     words ("The reason is *not* 'this agent is read-only'"); and
#   * let one already-qualified line satisfy the probe for every other, so once
#     any line was fixed the real message stayed stale forever — verbatim the
#     "one surface reports done for another" failure this file's header warns
#     about.
#
# awk rather than sed because the decision has three cases (not ours /
# already-correct / repairable), and `changed` is decided by comparing content,
# so the repair is its own probe — no separate predicate is left that the wrong
# surface can satisfy. The two boundary-qualified strips (`: ` / `, `) replace
# the stale bare entry in one step, which is what keeps a foreign plugin id like
# `someplugin:fr-phase-executor` from being eaten mid-token.
awk -v q="$QUALIFIED" '
  /^[[:space:]]*#/  { print; next }
  index($0, q)      { print; next }
  !/Explore, Plan,/ { print; next }
  {
    if (!sub(/: fr-phase-executor, Explore, Plan,/, ": " q ", Explore, Plan,") &&
        !sub(/, fr-phase-executor, Explore, Plan,/, ", " q ", Explore, Plan,"))
      sub(/Explore, Plan,/, q ", Explore, Plan,")
    print
  }
' "$hook" >"$tmp"

if ! cmp -s "$hook" "$tmp"; then
  cat "$tmp" >"$hook"
  changed=1
fi

[ "$changed" -eq 1 ] || exit 0
echo "allowlisted $QUALIFIED in $hook"
