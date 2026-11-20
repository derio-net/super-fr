#!/bin/bash
# WorktreeRemove (spec 2026-09-04 §5.B.4). agent-* worktrees: plain git removal,
# in either shape: `~/.cache/fr/agent-worktrees/<key>/agent-*` (gh#1270, locked
# by fr-worktree-create.sh, so unlocked first) or the legacy in-repo
# `<repo>/.claude/worktrees/agent-*`. Claude Code 2.1.316 was measured never
# firing this for a subagent; `fr isolation gc` is what actually reaps them.
# Everything else: `fr isolation down --worktree`, which keeps a workspace with an
# open PR — the reason goes to stderr and `fr isolation status` still shows it.
set -eu
# shellcheck source=lib/fr-isolation-decision.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/fr-isolation-decision.sh"
input=$(cat)
path=$(printf '%s' "$input" | fr_jq -r '.worktree_path // empty')
[ -n "$path" ] || exit 0
case "$path" in
  */.claude/worktrees/agent-*|*/.cache/fr/agent-worktrees/*/agent-*)
    common=$(fr_git -C "$path" rev-parse --git-common-dir 2>/dev/null) || { rm -rf "$path"; exit 0; }
    case "$common" in /*) ;; *) common="$path/$common" ;; esac
    # --git-dir, not the common dir's parent: right for bare and
    # --separate-git-dir layouts too, where that parent is not a repository.
    fr_git --git-dir="$common" worktree unlock "$path" >/dev/null 2>&1 || true
    fr_git --git-dir="$common" worktree remove --force "$path" >&2 || rm -rf "$path"
    exit 0 ;;
esac
fr_fr_resolve || exit 0
# Serialized per worktree path, for the same reason as fr-worktree-create.sh:
# install.sh also registers this script in settings.json, so wherever Claude
# Code honours both registrations two teardowns of one workspace would run at
# once. The second waits, then finds nothing to remove.
locks="$HOME/.cache/fr/locks"; mkdir -p "$locks"
lock="$locks/worktree-remove.$(printf '%s' "$path" | cksum | cut -d' ' -f1).lock"
waited=0
# The lock is a FILE made by the shell itself: `noclobber` opens it O_EXCL, so the
# exclusion is the kernel's and rests on no external binary (an external `mkdir` was
# seen succeeding twice on one path on Linux CI, gh#1463/gh#1586). It is created and
# holds the holder's pid in one step; a reader that sees it empty just waits.
until ( set -o noclobber; echo $$ > "$lock" ) 2>/dev/null; do
  holder=$(cat "$lock" 2>/dev/null || true)
  if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then rm -f "$lock"; continue; fi
  [ "$waited" -ge 300 ] && { echo "fr-worktree-remove: gave up waiting for $lock" >&2; exit 0; }
  sleep 1; waited=$((waited + 1))
done
trap 'rm -f "$lock"' EXIT
"$FR_FR_BIN" isolation down --worktree "$path" >&2 ||
  echo "fr-worktree-remove: fr isolation down refused for $path; workspace kept (see fr isolation status)" >&2
exit 0
