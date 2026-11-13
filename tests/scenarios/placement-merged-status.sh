#!/usr/bin/env bash
# Row placement-merged-status (spec 2026-11-04-repo-feature-settings R17's quiet/stealth
# clause, R25; plan 2026-11-12-placement-resolver phase 5).
#
# A quiet repo (origin/fr says placement: quiet). feat/a adds a row and merges into main
# by a merge commit; feat/b amends it. From a third workspace, `fr acceptance status`
# shows the row unamended while feat/b is unmerged, and amended, with both features
# listed as merged in merge order, once feat/b merges. `fr archive --branch feat/b`
# appends `merged: <sha>` to features/feat__b/merged.yaml in one pushed commit on `fr`
# and moves nothing. A forged `merged:` record for an unmerged feat/d is ignored, named
# in a note, and `fr archive --branch feat/d` refuses. feat/f, pushed fresh from main
# with no code of its own, is not merged (review p5-r1). feat/e, squash-merged, is not
# merged by git, and `fr archive --branch feat/e` refuses saying a squash needs the
# forge readable (no forge here: origin is a local path, review p5-r2). feat/a, deleted
# everywhere after its merge, stays merged and archives by the heads `fr push` recorded
# (review p5-r3). Nothing reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

HOME="$(mktemp -d)" && export HOME
export FR_ISOLATION_TARGET=worktree
base="$(pwd)"
origin="$(mktemp -d)/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
echo seed > README.md
git add -A && git commit -qm seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null
repo="$(basename "$(git rev-parse --show-toplevel)")"
frwt="$HOME/.cache/fr/worktrees/$repo/fr"

run_fr out settings init --quiet
require_exit 0 "$out"

# enter <branch> [nocode]: an isolation workspace for <branch>, with one code commit
# (pushed by the next `fr push`), or none with `nocode`
enter() {
  cd "$base" || fail "cd $base"
  run_fr out isolation up --branch "$1"
  require_exit 0 "$out"
  cd "$HOME/.cache/fr/worktrees/$repo/${1//\//__}" || fail "no worktree for $1: $out"
  [ "${2:-}" = nocode ] && return 0
  echo "$1" > "code-${1//\//-}.txt"
  git add -A && git commit -qm "feat(x): code on $1" || fail "code commit on $1"
}

# merge <branch>: merge it into main by a merge commit, in the base clone, and push
merge() {
  ( cd "$base" && git fetch -q origin && git merge -q --no-ff -m "Merge $1" "origin/$1" \
      && git push -q origin main && git fetch -q origin ) || fail "merge $1"
}

enter feat/a
run_fr out acceptance init
require_exit 0 "$out"
run_fr out acceptance add --id m-row --capability c --acceptance "merged status holds" \
  --origin spec:2026-11-13-a#R1 --feature legacy --status not-implemented --notes n \
  --repo derio-net/m
require_exit 0 "$out"
run_fr out push
require_exit 0 "$out"
merge feat/a

enter feat/b
run_fr out acceptance amend --id m-row --op set-status --status unwired --notes "b moved it" \
  --why "b's tests" --feature 2026-11-13-b
require_exit 0 "$out"
run_fr out push
require_exit 0 "$out"
run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'unwired: 1' "$out" "feat/b's own view applies its pending amendment"

enter feat/c
run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'not-implemented: 1' "$out" "an unmerged feature's amendment is not in another view"
expect_grep '^merged: feat__a at [0-9a-f]{12}$' "$out" "feat/a is listed as merged, alone"

merge feat/b
merged_b="$(git -C "$base" rev-parse origin/main)"
run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'unwired: 1' "$out" "feat/b's amendment applies once its code branch merged"
expect_grep "^merged: feat__a at [0-9a-f]{12}, feat__b at ${merged_b:0:12}$" "$out" \
  "both features are merged, in merge order"

# R25: archive appends merged and moves nothing
main_before="$(git --git-dir="$origin" rev-parse main)"
run_fr out archive --branch feat/b
require_exit 0 "$out"
expect_grep "recorded: feat/b merged at ${merged_b:0:12}" "$out" "archive records the merge"
git --git-dir="$origin" show fr:features/feat__b/merged.yaml | grep -qx -- "- merged: $merged_b" \
  || fail "origin fr lacks the merged record"
names="$(git --git-dir="$origin" show --name-only --format= fr)"
[ "$names" = "features/feat__b/merged.yaml" ] || fail "the archive commit touches more: $names"
[ "$(git --git-dir="$origin" rev-parse main)" = "$main_before" ] || fail "archive moved main"
[ -z "$(find "$frwt/features" -name implemented)" ] || fail "archive moved files to implemented/"
run_fr out archive --branch feat/b
require_exit 0 "$out"
expect_grep 'already recorded' "$out" "a second archive writes nothing"

# A forged record for an unmerged feature is ignored
enter feat/d
run_fr out acceptance amend --id m-row --op set-status --status walk-owed --notes "d moved it" \
  --why "d's tests" --feature 2026-11-13-d
require_exit 0 "$out"
run_fr out push
require_exit 0 "$out"
tip="$(git -C "$base" rev-parse origin/main)"
printf -- '- merged: %s\n  head: %s\n' "$tip" "$tip" > "$frwt/features/feat__d/merged.yaml"
git -C "$frwt" add features/feat__d/merged.yaml && git -C "$frwt" commit -qm "chore(fr): forged" \
  || fail "forge the record"
git -C "$frwt" push -q origin fr || fail "push the forged record"
cd "$HOME/.cache/fr/worktrees/$repo/feat__c" || fail "cd feat__c"
run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'unwired: 1' "$out" "the forged record does not merge feat/d's amendment"
refuse_grep 'feat__d at' "$out" "feat/d is not listed as merged"
expect_grep 'feat__d.*never the truth' "$(printf '%s' "$out" | tr '\n' ' ')" \
  "the ignored record is named"
run_fr out archive --branch feat/d
require_exit 2 "$out"
expect_grep 'not merged' "$out" "archive refuses an unmerged branch"

# p5-r1: a branch fresh from main, pushed with nothing of its own, is not merged
enter feat/f nocode
run_fr out acceptance amend --id m-row --op set-status --status manual --notes "f moved it" \
  --why "f's tests" --feature 2026-11-13-f
require_exit 0 "$out"
run_fr out push
require_exit 0 "$out"
[ "$(git -C "$base" ls-remote origin refs/heads/feat/f | cut -f1)" = "$(git -C "$base" rev-parse origin/main)" ] \
  || fail "feat/f is not pushed at main's tip"
cd "$HOME/.cache/fr/worktrees/$repo/feat__c" || fail "cd feat__c"
run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'unwired: 1' "$out" "a fresh branch's amendment is not merged"
refuse_grep 'feat__f at' "$out" "feat/f is not listed as merged"
run_fr out archive --branch feat/f
require_exit 2 "$out"

# p5-r2: a squash merge is found only through the forge, and there is none here
enter feat/e
run_fr out acceptance amend --id m-row --op set-status --status walk-owed --notes "e moved it" \
  --why "e's tests" --feature 2026-11-13-e
require_exit 0 "$out"
run_fr out push
require_exit 0 "$out"
( cd "$base" && git fetch -q origin && git merge -q --squash origin/feat/e \
    && git commit -qm "feat(e): squashed" && git push -q origin main && git fetch -q origin ) \
  || fail "squash-merge feat/e"
cd "$HOME/.cache/fr/worktrees/$repo/feat__c" || fail "cd feat__c"
run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'unwired: 1' "$out" "a squash merge no forge confirmed is not merged"
expect_grep 'unmerged: .*feat__e.*squash or rebase merge' "$(printf '%s' "$out" | tr '\n' ' ')" \
  "status says a squash merge needs the forge"
run_fr out archive --branch feat/e
require_exit 2 "$out"
flat="$(printf '%s' "$out" | tr '\n' ' ')"
expect_grep 'squash or rebase merge' "$flat" "archive says a squash needs the forge"
expect_grep 'no origin remote names a forge repository' "$flat" "archive says why the forge was not read"

# p5-r3: feat/a, deleted everywhere after its merge, stays merged and archives
# (the merged workspace may already be reaped; a live one lets go of the branch first)
wa="$HOME/.cache/fr/worktrees/$repo/feat__a"
[ ! -d "$wa" ] || git -C "$wa" checkout -q --detach || fail "detach feat__a"
git -C "$base" push -q origin --delete feat/a || fail "delete origin feat/a"
if git -C "$base" rev-parse -q --verify refs/heads/feat/a >/dev/null; then
  git -C "$base" branch -q -D feat/a || fail "delete feat/a"
fi
git -C "$base" fetch -q --prune origin
git -C "$base" rev-parse -q --verify refs/remotes/origin/feat/a >/dev/null && fail "feat/a still has a ref"
run_fr out acceptance status
require_exit 0 "$out"
expect_grep '^merged: feat__a at [0-9a-f]{12}, feat__b at' "$out" "a deleted branch stays merged"
run_fr out archive --branch feat/a
require_exit 0 "$out"
expect_grep 'recorded: feat/a merged at' "$out" "a deleted branch archives by its recorded heads"
echo "ok: placement-merged-status"
