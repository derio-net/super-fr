#!/bin/bash
# WorktreeCreate (spec 2026-09-04 §5.B.3): session worktrees become fr
# workspaces; subagent worktrees (agent-*) are plain detached worktrees OUTSIDE
# the repo (gh#1270). The LAST stdout line is the worktree path; everything else
# goes to stderr. A registered hook cannot decline, so every branch below prints
# a path or exits 1.
#
# A registered WorktreeCreate replaces Claude's native creation, and with it the
# native lifecycle: Claude takes no lock and (measured on 2.1.316) never fires
# WorktreeRemove for a subagent. Left in `<repo>/.claude/worktrees/` they piled
# up and nested until Claude refused new isolated dispatches. So agent_worktree
# files them under `~/.cache/fr/agent-worktrees/<repo-key>/<name>`, locks each
# with the Claude pid, and `fr isolation gc` reaps the finished, clean ones.
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
  copy_worktreeinclude "$dir"
  printf '%s\n' "$dir"
  exit 0
}
agent_worktree() {
  # Claude's default base (origin/HEAD fresh, else the invoking checkout's HEAD),
  # but filed under the MAIN checkout's key, so a subagent dispatching from its
  # own worktree makes a sibling, never a nested child. The key is the main
  # checkout's basename, as `fr.isolation.types.repo_cache_name` computes it.
  common=$(git -C "$root" rev-parse --path-format=absolute --git-common-dir)
  case "$common" in */.git) key=$(basename "$(dirname "$common")") ;; *) key=$(basename "$root") ;; esac
  dir="$HOME/.cache/fr/agent-worktrees/$key/$name"
  if [ -d "$dir" ]; then
    # Two repos can share a basename: never hand a subagent the other's checkout.
    theirs=$(git -C "$dir" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
    [ "$theirs" = "$common" ] || {
      echo "fr-worktree-create: $dir belongs to another repository (${theirs:-not a git worktree})" >&2
      exit 1; }
    printf '%s\n' "$dir"; exit 0
  fi
  mkdir -p "$(dirname "$dir")"
  base=$(git -C "$root" rev-parse --verify -q origin/HEAD 2>/dev/null || git -C "$root" rev-parse HEAD)
  git -C "$root" worktree add --detach "$dir" "$base" >&2
  # The hook's parent is the Claude process (measured live): while it lives, gc
  # leaves this worktree alone. Best effort; an unlocked one still ages out.
  git -C "$root" worktree lock --reason "fr-agent pid=$PPID session=${session_id:-?}" "$dir" >&2 || true
  copy_worktreeinclude "$dir"
  printf '%s\n' "$dir"
  exit 0
}
copy_worktreeinclude() {
  # Best effort, like Claude's native path (super-fr#455): copy every file that
  # is git-ignored AND named by a `.worktreeinclude` pattern (gitignore syntax).
  # `ls-files -o -i --exclude-from` lists untracked files matching the include
  # patterns; `check-ignore` keeps those the repo's own ignore rules ignore.
  # The worktree is the COMMITTED tree, which may hold a symlink where the base
  # checkout has a real directory: never write through one (`no_link_under`),
  # never overwrite, and copy a source symlink as a link (`cp -P`), not its target.
  [ -f "$root/.worktreeinclude" ] || return 0
  git -C "$root" ls-files -z --others --ignored --exclude-from="$root/.worktreeinclude" 2>/dev/null \
    | git -C "$root" check-ignore -z --stdin 2>/dev/null \
    | while IFS= read -r -d '' rel; do
        if ! no_link_under "$1" "$rel"; then
          echo "fr-worktree-create: not copying $rel (a symlink or file is in the way)" >&2
          continue
        fi
        mkdir -p "$1/$(dirname "$rel")" && cp -P -p "$root/$rel" "$1/$rel" \
          || echo "fr-worktree-create: could not copy $rel" >&2
      done || true
}
no_link_under() {
  # True when no component of <dir>/<rel> exists as a symlink and <rel> itself
  # does not exist yet.
  # Expansion, not `read`, so a name holding a newline is still walked whole.
  local p="$1" rest="$2" part
  while [ -n "$rest" ]; do
    part=${rest%%/*}
    rest=${rest#"$part"}
    rest=${rest#/}
    p="$p/$part"
    [ -L "$p" ] && return 1
  done
  [ ! -e "$p" ]
}
has_profile() { ls -d "$root"/.devcontainer/*/ >/dev/null 2>&1; }
fr_enabled() { [ -d "$root/docs/superpowers/plans" ] || has_profile; }

# Serialize per repo+worktree name, BEFORE any branch that creates one.
# install.sh registers this script in settings.json as well as the plugin's
# hooks.json (Claude Code 2.1.281 skipped the plugin one for `claude --worktree`),
# so wherever Claude Code honours both, two copies run at once. A nonzero exit
# fails creation outright, and a registered hook cannot decline, so each copy
# must print the same path: the second waits, then finds the worktree made
# (mimic_default's `-d` check, or the idempotent `up`). This lock once covered
# only the `fr isolation up` path, and the two copies of every `agent-*`
# dispatch raced on one `git worktree add` (gh#1124). mkdir is the atomic step;
# a lock whose holder is dead is reclaimed; the wait is bounded, since a cold
# `devcontainer up` is slow.
locks="$HOME/.cache/fr/locks"; mkdir -p "$locks"
lock="$locks/worktree-create.$(printf '%s' "$root|$name" | cksum | cut -d' ' -f1)"
waited=0
until mkdir "$lock" 2>/dev/null; do
  holder=$(cat "$lock/pid" 2>/dev/null || true)
  if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then rm -rf "$lock"; continue; fi
  [ "$waited" -ge 900 ] && { echo "fr-worktree-create: gave up waiting for $lock" >&2; exit 1; }
  sleep 1; waited=$((waited + 1))
done
trap 'rm -rf "$lock"' EXIT
echo $$ > "$lock/pid"

case "$name" in agent-*) agent_worktree ;; esac
if ! fr_enabled || ! command -v fr >/dev/null 2>&1; then mimic_default; fi

branch="$name"; case "$name" in */*) ;; *) branch="wt/$name" ;; esac
if [ -z "${FR_ISOLATION_TARGET:-}" ] && ! has_profile; then
  echo "fr-worktree-create: no devcontainer profile in $root — host-worktree mode for this worktree" >&2
  export FR_ISOLATION_TARGET=worktree
fi
args=(isolation up --repo "$root" --branch "$branch")
[ -n "$session_id" ] && args+=(--session "$session_id" --harness claude)
args+=(--print-path)
out=$(fr "${args[@]}") || { echo "fr-worktree-create: fr isolation up failed" >&2; exit 1; }
path=$(printf '%s\n' "$out" | sed -e 's/\x1b\[[0-9;]*m//g' | awk 'NF{l=$0} END{print l}')
[ -n "$path" ] && [ -d "$path" ] || {
  echo "fr-worktree-create: no worktree path from fr isolation up" >&2; exit 1; }
printf '%s\n' "$path"
