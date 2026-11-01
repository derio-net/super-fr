#!/bin/bash
# WorktreeRemove (spec 2026-09-04 §5.B.4). agent-* worktrees: plain git removal,
# in either shape: `~/.cache/fr/agent-worktrees/<key>/agent-*` (gh#1270, locked
# by fr-worktree-create.sh, so unlocked first) or the legacy in-repo
# `<repo>/.claude/worktrees/agent-*`. Claude Code 2.1.316 was measured never
# firing this for a subagent; `fr isolation gc` is what actually reaps them.
# Everything else: `fr isolation down --worktree`, which keeps a workspace with an
# open PR — the reason goes to stderr and `fr isolation status` still shows it.
set -eu
input=$(cat)
path=$(printf '%s' "$input" | jq -r '.worktree_path // empty')
[ -n "$path" ] || exit 0
case "$path" in
  */.claude/worktrees/agent-*|*/.cache/fr/agent-worktrees/*/agent-*)
    common=$(git -C "$path" rev-parse --git-common-dir 2>/dev/null) || { rm -rf "$path"; exit 0; }
    case "$common" in /*) ;; *) common="$path/$common" ;; esac
    # --git-dir, not the common dir's parent: right for bare and
    # --separate-git-dir layouts too, where that parent is not a repository.
    git --git-dir="$common" worktree unlock "$path" >/dev/null 2>&1 || true
    git --git-dir="$common" worktree remove --force "$path" >&2 || rm -rf "$path"
    exit 0 ;;
esac
command -v fr >/dev/null 2>&1 || exit 0
# Serialized per worktree path, for the same reason as fr-worktree-create.sh:
# install.sh also registers this script in settings.json, so wherever Claude
# Code honours both registrations two teardowns of one workspace would run at
# once. The second waits, then finds nothing to remove.
locks="$HOME/.cache/fr/locks"; mkdir -p "$locks"
lock="$locks/worktree-remove.$(printf '%s' "$path" | cksum | cut -d' ' -f1)"
waited=0
until mkdir "$lock" 2>/dev/null; do
  holder=$(cat "$lock/pid" 2>/dev/null || true)
  if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then rm -rf "$lock"; continue; fi
  [ "$waited" -ge 300 ] && { echo "fr-worktree-remove: gave up waiting for $lock" >&2; exit 0; }
  sleep 1; waited=$((waited + 1))
done
trap 'rm -rf "$lock"' EXIT
echo $$ > "$lock/pid"
fr isolation down --worktree "$path" >&2 ||
  echo "fr-worktree-remove: fr isolation down refused for $path; workspace kept (see fr isolation status)" >&2
exit 0
