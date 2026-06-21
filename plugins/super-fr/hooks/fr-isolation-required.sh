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

# jq is load-bearing: under `set -eu` an absent jq aborts here (no deny emitted
# → fail-open). Same posture as fr-isolation-guard.sh — a discipline backstop,
# not a security boundary; the hook tests skip when jq is missing.
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')
[ -n "$file" ] || exit 0   # no parseable target — not an isolation decision

# Edit tools always pass an absolute path; a relative one would resolve the
# toplevel against the wrong (session-cwd) repo, so make the assumption explicit.
case "$file" in /*) ;; *) exit 0 ;; esac

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
# current toplevel AND mode == "worktree" AND the toplevel is a LINKED worktree
# (git-common-dir != git-dir). The linked-worktree check is what defeats a stale
# marker copied into the primary working tree.
#
# ONLY mode=worktree is honored. The marker records `mode` for forward-compat
# with a future container-native Target, but until that Target ships (and adds
# its own in-container probe here) any non-worktree mode — including a typo or a
# stale `devcontainer` marker — must fail CLOSED rather than blanket-allow on a
# toplevel match. So unknown modes fall through to the allowlist / deny.
marker="$rtop/.fr-isolation"
if [ -f "$marker" ]; then
  recorded=$(jq -r '.toplevel // empty' "$marker" 2>/dev/null || true)
  mode=$(jq -r '.mode // "worktree"' "$marker" 2>/dev/null || echo worktree)
  rrecorded=""
  [ -n "$recorded" ] && rrecorded=$(cd "$recorded" 2>/dev/null && pwd -P || echo "$recorded")
  if [ "$rrecorded" = "$rtop" ] && [ "$mode" = "worktree" ]; then
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
  # Symlink-robust repo-relative path: resolve the existing-ancestor dir
  # (`pwd -P`) and re-attach the not-yet-created tail, so a macOS `/tmp` →
  # `/private/tmp` toplevel doesn't make the strip silently no-op (which would
  # drop the operator's escape to a confusing deny).
  rdir=$(cd "$dir" 2>/dev/null && pwd -P) || rdir="$dir"
  rfile="$rdir${file#"$dir"}"
  rel=""
  case "$rfile" in "$rtop"/*) rel=${rfile#"$rtop"/} ;; esac
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
