#!/bin/bash
# Build the sandbox the guard verdict table (guard-verdicts.yaml) is judged in.
#
#   bash guard-world.sh <root>
#
# ONE builder for both engines: the Python loader (tests/unit/test_hooks_guard.py)
# runs the bash guard in it, and the TypeScript loader
# (packages/fr-opencode-plugin/test/guard-verdicts.test.ts) runs the port in it.
# Two builders could drift into two worlds, and a table that passes in two
# different worlds proves nothing about parity.
#
# Every path below appears in the table as a placeholder ({root}, {base}, …),
# substituted with the REAL (symlink-resolved) root at load time.
#
#   {root}/home                                   HOME
#   {root}/home/.cache/fr/worktrees/base/feat     linked worktree of base, valid marker
#   {root}/base                                   fr-enabled base clone (the pipeline's repo)
#   {root}/base/sub                               a subdirectory of it
#   {root}/base-wt-unmarked                       linked worktree of base, NO marker, outside prefixes
#   {root}/other                                  another fr-enabled repo, no marker
#   {root}/plain                                  a git repo that is not fr-enabled (dotfiles-$HOME shape)
#   {root}/plain/sub                              a subdirectory of it
#   {root}/scratch                                a plain dir on the allowed-prefix list
#   {root}/elsewhere                              a plain dir NOT on the list
#   {root}/sentinels                              FR_SENTINEL_DIR
#   {root}/bin/bin-no-git                         this host's PATH minus git (the
#                                                 "git is not on PATH" row)
set -eu

root=$1
mkdir -p "$root"
root=$(cd "$root" && pwd -P)

g() { git -c user.email=t@example.com -c user.name=t -c init.defaultBranch=main "$@" >/dev/null 2>&1; }

mkrepo() {
  mkdir -p "$1"
  g -C "$1" init -q
  printf 'x\n' >"$1/f"
  g -C "$1" add f
  g -C "$1" commit -q -m init
}

mkdir -p "$root/home/.cache/fr/worktrees/base" "$root/sentinels" "$root/scratch" "$root/elsewhere"

mkrepo "$root/base"
mkdir -p "$root/base/docs/superpowers/plans" "$root/base/sub"
g -C "$root/base" worktree add -q -b feat "$root/home/.cache/fr/worktrees/base/feat"
wt="$root/home/.cache/fr/worktrees/base/feat"
printf '{"toplevel": "%s", "mode": "worktree", "branch": "feat"}\n' "$wt" >"$wt/.fr-isolation"
g -C "$root/base" worktree add -q -b unmarked "$root/base-wt-unmarked"

mkrepo "$root/other"
mkdir -p "$root/other/docs/superpowers/plans"

mkrepo "$root/plain"
mkdir -p "$root/plain/sub"

# A PATH holding this host's executables MINUS git: the guard's own helpers
# (jq, sed, …) must still resolve, so the row proves "git unreachable" and not
# "PATH was empty". Built from the CALLER's PATH, never a curated list — a list
# would drift from the guard's real tool surface, and a row that denies because
# `jq` vanished is not evidence about git. One `ln` per PATH entry (many targets
# per call) instead of one per file: file-by-file symlinking cost seconds.
nogit="$root/bin/bin-no-git"
mkdir -p "$nogit"
_oldifs=${IFS-}
IFS=:
for _d in ${PATH:-}; do
  IFS=$_oldifs
  [ -n "$_d" ] && [ -d "$_d" ] || continue
  ln -s "$_d"/* "$nogit"/ 2>/dev/null || true
  IFS=:
done
IFS=$_oldifs
rm -f "$nogit"/git "$nogit"/git-*
