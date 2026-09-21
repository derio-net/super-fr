#!/bin/bash
# PostToolUse(Skill) hook: record "fr pipeline active" for this session.
#
# When fr-goal / fr-brainstorming / fr-execute is invoked, write a
# session-keyed sentinel naming the base repo. The companion PreToolUse hook
# (fr-isolation-guard.sh) denies base-repo-cwd Bash commands while the
# sentinel lives. Cleared by a successful `fr isolation down` of this session's
# workspace (clear_workspace_sentinels() in fr/isolation/types.py), by the
# guard's self-heal when EVERY workspace this session bound is gone (a
# per-sentinel fact, not a count of the repo's worktrees — #472/#529), by
# `fr isolation down --all` (clear_repo_sentinels(), repo-wide by design), and
# by the 48h GC below. See #265/#341; same philosophy
# as agent-worktree-required.sh, extended from the Agent tool to inline Bash.
#
# Optional `workspaces` list: added to by `fr isolation attach`
# (stamp_sentinel_workspace) — each workspace this session bound in this repo,
# RELATIVE to ~/.cache/fr, never absolute. Absent/empty = fresh (armed). This
# writer never ADDS an entry, but it carries the live ones across a skill
# reload (below).

set -eu

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
[ "$tool_name" = "Skill" ] || exit 0

# Field name is not formally documented for Skill; read the likely spellings.
skill=$(printf '%s' "$input" | jq -r \
  '.tool_input.skill_name // .tool_input.skill // .tool_input.name // empty')

case "$skill" in
  fr-goal|fr-brainstorming|fr-execute) ;;          # bare names
  *:fr-goal|*:fr-brainstorming|*:fr-execute) ;;    # plugin-namespaced
  *) exit 0 ;;
esac

cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
session_id=$(printf '%s' "$input" | jq -r '.session_id // empty')
[ -n "$cwd" ] && [ -n "$session_id" ] || exit 0

# Pipeline skills only matter inside a repo; a non-git cwd is a no-op.
repo_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$repo_root" ] || exit 0

# Linked worktree (.git is a file, not a dir) → this IS the isolation
# workspace; keying the sentinel here would make the guard deny the very
# place work happens. Only the base repo gets a sentinel.
[ -d "$repo_root/.git" ] || exit 0

dir="${FR_SENTINEL_DIR:-$HOME/.cache/fr/sentinels}"
mkdir -p "$dir"

# GC: sentinels self-expire with their sessions (48h = 2880 min).
find "$dir" -name '*.json' -mmin +2880 -delete 2>/dev/null || true

sentinel="$dir/$session_id.json"

# Carry the LIVE part of the stamp across a reload. fr-goal loads, `fr run
# start` binds (and stamps), then fr-goal invokes fr-brainstorming — which
# re-runs this hook. A from-scratch rewrite erased the stamp, the sentinel read
# as fresh forever, and a reaped workspace locked the session out exactly as
# #472 describes. Carried only when BOTH hold, because a stamp is a claim about
# this repo's pipeline:
#   * same repo_root — a pipeline in another repo starts fresh;
#   * the entry's directory still exists — a dead entry is a PREVIOUS
#     pipeline's, and carried alone it would read as orphaned and retire this
#     new pipeline on its first command (#529 again).
# Carrying a live entry into a NEW pipeline in the same session cannot disarm
# it: the guard heals only when NO entry survives, and the new pipeline's own
# workspace is added to the set when it binds.
# Only `attach` ever ADDS an entry; this writer can only keep or drop them.
carried="[]"
if [ -f "$sentinel" ]; then
  prev_root=$(jq -r '.repo_root // empty' "$sentinel" 2>/dev/null || true)
  if [ "$prev_root" = "$repo_root" ]; then
    while IFS= read -r ws; do
      [ -n "$ws" ] && [ -d "$HOME/.cache/fr/$ws" ] || continue
      carried=$(printf '%s' "$carried" | jq -c --arg w "$ws" '. + [$w]')
    done <<EOF_WS
$(jq -r '(.workspaces // []) | if type == "array" then .[] else empty end
         | select(type == "string")' "$sentinel" 2>/dev/null || true)
EOF_WS
  fi
fi

# tmp + mv: the guard reads this file on every Bash call, and a half-written
# sentinel parses as no repo_root — an unguarded command.
tmp="$sentinel.tmp.$$"
jq -n \
  --arg repo_root "$repo_root" \
  --arg skill "$skill" \
  --arg started_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson workspaces "$carried" \
  '{repo_root: $repo_root, skill: $skill, started_at: $started_at}
   + (if ($workspaces | length) == 0 then {} else {workspaces: $workspaces} end)' \
  > "$tmp"
mv -f "$tmp" "$sentinel"

exit 0
