#!/bin/bash
# WorktreeCreate (spec 2026-09-04 §5.B.3): session worktrees become fr
# workspaces; subagent worktrees (agent-*) keep Claude's default shape. The
# LAST stdout line is the worktree path; everything else goes to stderr. A
# registered hook cannot decline, so every branch below prints a path or exits 1.
set -eu
input=$(cat)
name=$(printf '%s' "$input" | jq -r '.name // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
session_id=$(printf '%s' "$input" | jq -r '.session_id // empty')
[ -n "$name" ] && [ -n "$cwd" ] || { echo "fr-worktree-create: missing name or cwd" >&2; exit 1; }
root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || {
  echo "fr-worktree-create: $cwd is not a git repo" >&2; exit 1; }

mimic_default() {
  # Claude's default: <repo>/.claude/worktrees/<name>, detached at origin/HEAD (fresh) else HEAD.
  dir="$root/.claude/worktrees/$name"
  if [ -d "$dir" ]; then printf '%s\n' "$dir"; exit 0; fi
  mkdir -p "$root/.claude/worktrees"
  base=$(git -C "$root" rev-parse --verify -q origin/HEAD 2>/dev/null || git -C "$root" rev-parse HEAD)
  git -C "$root" worktree add --detach "$dir" "$base" >&2
  printf '%s\n' "$dir"
  exit 0
}
has_profile() { ls -d "$root"/.devcontainer/*/ >/dev/null 2>&1; }
fr_enabled() { [ -d "$root/docs/superpowers/plans" ] || has_profile; }

case "$name" in agent-*) mimic_default ;; esac
if ! fr_enabled || ! command -v fr >/dev/null 2>&1; then mimic_default; fi

branch="$name"; case "$name" in */*) ;; *) branch="wt/$name" ;; esac
if [ -z "${FR_ISOLATION_TARGET:-}" ] && ! has_profile; then
  echo "fr-worktree-create: no devcontainer profile in $root — host-worktree mode for this worktree" >&2
  export FR_ISOLATION_TARGET=worktree
fi
args=(isolation up --repo "$root" --branch "$branch")
[ -n "$session_id" ] && args+=(--session "$session_id" --harness claude)
args+=(--print-path)
# Serialize per repo+branch. install.sh registers this script in settings.json
# as well as the plugin's hooks.json (Claude Code 2.1.281 skipped the plugin
# one for `claude --worktree`), so wherever Claude Code honours both, two copies
# run at once and would race on one `git worktree add`. A nonzero exit fails
# creation outright. The second copy waits, then gets the same path from the
# idempotent `up`. mkdir is the atomic step; a lock whose holder is dead is
# reclaimed; the wait is bounded, since a cold `devcontainer up` is slow.
locks="$HOME/.cache/fr/locks"; mkdir -p "$locks"
lock="$locks/worktree-create.$(printf '%s' "$root|$branch" | cksum | cut -d' ' -f1)"
waited=0
until mkdir "$lock" 2>/dev/null; do
  holder=$(cat "$lock/pid" 2>/dev/null || true)
  if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then rm -rf "$lock"; continue; fi
  [ "$waited" -ge 900 ] && { echo "fr-worktree-create: gave up waiting for $lock" >&2; exit 1; }
  sleep 1; waited=$((waited + 1))
done
echo $$ > "$lock/pid"
trap 'rm -rf "$lock"' EXIT
out=$(fr "${args[@]}") || { echo "fr-worktree-create: fr isolation up failed" >&2; exit 1; }
path=$(printf '%s\n' "$out" | sed -e 's/\x1b\[[0-9;]*m//g' | awk 'NF{l=$0} END{print l}')
[ -n "$path" ] && [ -d "$path" ] || {
  echo "fr-worktree-create: no worktree path from fr isolation up" >&2; exit 1; }
printf '%s\n' "$path"
