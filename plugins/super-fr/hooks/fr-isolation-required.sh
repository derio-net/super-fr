#!/bin/bash
# PreToolUse(Edit|Write|MultiEdit|NotebookEdit) hook: deny edits to tracked
# source/docs in an fr-enabled repo unless they land in a valid fr-isolation
# workspace. Mirrors agent-worktree-required.sh (Agent tool) and complements
# fr-isolation-guard.sh (Bash tool) — but is MARKER-based and
# session-independent, so it catches a session that wanders into another
# fr-enabled repo's base clone and edits it with no active pipeline sentinel
# (#328 Task 3).
#
# Invariant: edits to tracked source in an fr-enabled repo happen inside an
# fr-isolation workspace, never the base clone. Ambiguity (no marker / mismatch
# / wrong place) BLOCKS. Escapes: FR_BASE_OK=1, or a `.fr-isolation-allow`
# globlist at the repo root for operator-managed paths.

set -eu

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
case "$tool_name" in
  Edit | Write | MultiEdit | NotebookEdit) ;;
  *) exit 0 ;;
esac

# Deliberate base-clone edit — the documented escape hatch.
[ "${FR_BASE_OK:-}" = "1" ] && exit 0

file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')
[ -n "$file" ] || exit 0   # no parseable target — not an isolation decision

# Nearest existing ancestor dir (Write targets a not-yet-created file).
dir=$(dirname "$file")
while [ ! -d "$dir" ] && [ "$dir" != "/" ] && [ "$dir" != "." ]; do
  dir=$(dirname "$dir")
done
[ -d "$dir" ] || exit 0

toplevel=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$toplevel" ] || exit 0
rtop=$(cd "$toplevel" 2>/dev/null && pwd -P) || exit 0

# fr-enabled? A devcontainer profile (every isolation-capable repo has one) or
# an fr plans dir. Neither → not our concern, allow.
fr_enabled=0
for cfg in "$rtop"/.devcontainer/*/devcontainer.json; do
  [ -f "$cfg" ] && fr_enabled=1 && break
done
[ -d "$rtop/docs/superpowers/plans" ] && fr_enabled=1
[ "$fr_enabled" = 1 ] || exit 0

# Valid isolation marker → allow. Valid = present AND recorded toplevel ==
# current toplevel AND (for mode=worktree) the toplevel is a LINKED worktree
# (git-common-dir != git-dir). The linked-worktree check is what defeats a
# stale marker copied into the primary working tree.
marker="$rtop/.fr-isolation"
if [ -f "$marker" ]; then
  recorded=$(jq -r '.toplevel // empty' "$marker" 2>/dev/null || true)
  mode=$(jq -r '.mode // "worktree"' "$marker" 2>/dev/null || echo worktree)
  rrecorded=""
  [ -n "$recorded" ] && rrecorded=$(cd "$recorded" 2>/dev/null && pwd -P || echo "$recorded")
  if [ "$rrecorded" = "$rtop" ]; then
    if [ "$mode" != "worktree" ]; then
      exit 0   # container-native isolation: the container is the boundary
    fi
    common=$(git -C "$rtop" rev-parse --git-common-dir 2>/dev/null || true)
    gitdir=$(git -C "$rtop" rev-parse --git-dir 2>/dev/null || true)
    rcommon=$(cd "$rtop" && cd "$common" 2>/dev/null && pwd -P) || rcommon="$common"
    rgitdir=$(cd "$rtop" && cd "$gitdir" 2>/dev/null && pwd -P) || rgitdir="$gitdir"
    [ "$rcommon" != "$rgitdir" ] && exit 0   # a linked worktree → valid
  fi
fi

# Operator-managed exemptions: a `.fr-isolation-allow` globlist at the repo
# root, matched against the file's repo-relative path (bash pattern match — `*`
# spans `/`, so `projects/**` matches nested paths).
allow="$rtop/.fr-isolation-allow"
if [ -f "$allow" ]; then
  rel=""
  case "$file" in
    "$rtop"/*) rel=${file#"$rtop"/} ;;
    "$toplevel"/*) rel=${file#"$toplevel"/} ;;
  esac
  if [ -n "$rel" ]; then
    while IFS= read -r pattern || [ -n "$pattern" ]; do
      [ -n "$pattern" ] || continue
      case "$pattern" in \#*) continue ;; esac
      # shellcheck disable=SC2254
      if [[ "$rel" == $pattern ]]; then exit 0; fi
    done < "$allow"
  fi
fi

jq -n --arg reason "fr-isolation: edit to \`$file\` blocked — not inside an fr-isolation workspace. Enter isolation (\`fr isolation up\` / fr-goal) and edit in the worktree; or add the path to \`.fr-isolation-allow\`; or set FR_BASE_OK=1 for a deliberate base-clone edit. See ~/.claude/rules/fr-isolation-required.md (#328)." \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
exit 0
