#!/bin/bash
# PostToolUse(Skill) hook: record "fr pipeline active" for this session.
#
# When fr-goal / fr-brainstorming / fr-execute is invoked, write a
# session-keyed sentinel naming the base repo. The companion PreToolUse hook
# (fr-isolation-guard.sh) denies base-repo-cwd Bash commands while the
# sentinel lives. Cleared by `fr isolation down` (guard-observed) and by the
# 48h GC below. See #265; same philosophy as agent-worktree-required.sh,
# extended from the Agent tool to inline Bash.

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

dir="${FR_SENTINEL_DIR:-$HOME/.cache/fr/sentinels}"
mkdir -p "$dir"

# GC: sentinels self-expire with their sessions (48h = 2880 min).
find "$dir" -name '*.json' -mmin +2880 -delete 2>/dev/null || true

jq -n \
  --arg repo_root "$repo_root" \
  --arg skill "$skill" \
  --arg started_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{repo_root: $repo_root, skill: $skill, started_at: $started_at}' \
  > "$dir/$session_id.json"

exit 0
