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
# Usage: ensure-phase-executor-allowlist.sh <hook-path> [<plugin-qualified-id>]
#
# The id defaults to `super-fr:fr-phase-executor`. install.sh also passes
# `super-fr:fr-spec-reviewer` (2026-09-24 spec §E, gh#593): the stock hook
# decides by NAME, not by tools, so even a read-only agent outside its `case`
# arm must pass `isolation: "worktree"` — and a worktree cut from `main` cannot
# see the feature branch's spec it is dispatched to review.
#
# - Inserts the qualified id AND its bare name into the allowlist `case` arm
#   (gh#1105: `fr init agents` renders project agents dispatched by the bare
#   name, `fr-phase-executor`, while the plugin's is `super-fr:fr-phase-executor`).
# - Idempotent: a second run is a no-op.
# - Safe no-op when the hook file is absent (e.g. a machine without the org
#   convention installed) — never creates it.

set -eu

hook="${1:?usage: ensure-phase-executor-allowlist.sh <hook-path> [<plugin-qualified-id>]}"

# Absent hook → nothing to manage. Exit success so install.sh flows on.
[ -f "$hook" ] || exit 0

# Claude Code dispatches a PLUGIN subagent by its plugin-qualified id
# (`super-fr:fr-phase-executor`) and a PROJECT agent by its bare name
# (`fr-phase-executor`). Both exist: the plugin ships one, and `fr init agents`
# renders `.claude/agents/fr-phase-executor.md` into a repo (cloud-triage §H). So
# both spellings are allowlisted. The bare name was once stripped here as a
# stale entry, written by a pre-fix version that inserted ONLY the bare name;
# since project agents exist it is a real dispatch target (gh#1105).
QUALIFIED="${2:-super-fr:fr-phase-executor}"
BARE="${QUALIFIED#*:}"
IDS=("$QUALIFIED")
[ "$BARE" = "$QUALIFIED" ] || IDS+=("$BARE")

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# The hook has TWO surfaces naming the allowlist, and they drift apart: the
# `case` arm that actually decides, and a human-readable "Exempt: …" stderr
# message a few lines below that tells a blocked caller what IS allowed. Each
# gets its OWN probe and its own repair, PER ID.
#
# Probing once for several things is the exact bug this file already records: a
# probe satisfied by one surface (or one spelling) reports "already done" for
# the other, forever. (The original probe was `grep -q fr-phase-executor`, which
# a bare entry satisfied, so the qualified one was never inserted.) So: no shared
# early exit, and each id is probed as a WHOLE member — `fr-phase-executor` is
# never found inside `super-fr:fr-phase-executor`.
changed=0

# --- 1. The `case` arm (authoritative; drift here fails loud) ----------------
#
# The allowlist is a single case arm whose pattern is a `|`-joined list, e.g.:
#   Explore|Plan|claude-code-guide|statusline-setup|hookify:conversation-analyzer)
# Anchor on the known-stock `Explore|Plan|` and insert a missing id just before
# it. Membership is position-independent: an id already anywhere in the arm is
# left alone, so a hand-placed entry is never duplicated.
#
# Every expression is scoped to NON-COMMENT lines, and so is the probe: a hook
# whose header comment documents its own allowlist verbatim otherwise satisfies
# a file-wide probe, so the real `case` arm is never patched and this script
# exits 0 reporting success while dispatch stays blocked — re-creating the
# silent inline-degradation incident it was written to end (rev2-f6).
in_arm() {
  grep -v '^[[:space:]]*#' "$1" | grep -E 'Explore\|Plan\|' |
    grep -Eq "(^[[:space:]]*|\|)$2(\||\))"
}
for id in "${IDS[@]}"; do
  in_arm "$hook" "$id" && continue
  sed -e "/^[[:space:]]*#/!s/^\([[:space:]]*\)\(\([^|)#[:space:]]*|\)*\)Explore|Plan|/\1\2$id|Explore|Plan|/" \
    "$hook" >"$tmp"
  if ! in_arm "$tmp" "$id"; then
    # Anchor not found (hook shape changed). Fail loud rather than silently
    # skip, so drift is visible instead of leaving dispatch mysteriously
    # blocked.
    echo "ensure-phase-executor-allowlist: could not find the 'Explore|Plan|' allowlist anchor in $hook" >&2
    exit 1
  fi
  cat "$tmp" >"$hook"
  changed=1
done

# --- 2. The "Exempt: …" stderr message (advisory; absence is fine) -----------
#
# super-fr#420 checklist item 4: left alone, this message contradicts the `case`
# arm three lines above it — anyone reading a denial to learn what is permitted
# is told the wrong thing.
#
# Unlike the `case` anchor this is NOT required to exist: the message is the org
# hook's own prose, and a host whose hook has none is simply left alone. Absence
# is a silent no-op, never a failure.
#
# Decided PER LINE, and never on a line that is not ours to edit (rev2-f5): the
# live org hook carries the exempt list twice — a "Read-only subagent types (…)"
# rationale comment as well as the real stderr message — and the comment must
# not come to call a code-writing agent read-only. An id counts as present only
# as a whole, comma-separated member (preceded by a space or `(`, followed by
# `,` or `)`), so the bare name is not found inside a qualified one, and a
# foreign id like `someplugin:fr-phase-executor` is never edited. `changed` is
# decided by comparing content, so the repair is its own probe.
for id in "${IDS[@]}"; do
  awk -v q="$id" '
    function has(line, tok,   i, pre, post) {
      while ((i = index(line, tok)) > 0) {
        pre = (i == 1) ? "" : substr(line, i - 1, 1)
        post = substr(line, i + length(tok), 1)
        if ((pre == " " || pre == "(") && (post == "," || post == ")")) return 1
        line = substr(line, i + length(tok))
      }
      return 0
    }
    /^[[:space:]]*#/  { print; next }
    !/Explore, Plan,/ { print; next }
    has($0, q)        { print; next }
    { sub(/Explore, Plan,/, q ", Explore, Plan,"); print }
  ' "$hook" >"$tmp"
  if ! cmp -s "$hook" "$tmp"; then
    cat "$tmp" >"$hook"
    changed=1
  fi
done

[ "$changed" -eq 1 ] || exit 0
echo "allowlisted ${IDS[*]} in $hook"
