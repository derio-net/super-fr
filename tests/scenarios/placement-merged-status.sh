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
# in a note, and `fr archive --branch feat/d` refuses. Nothing reaches a forge.
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

# enter <branch>: an isolation workspace for <branch>, with one pushed code commit
enter() {
  cd "$base" || fail "cd $base"
  run_fr out isolation up --branch "$1"
  require_exit 0 "$out"
  cd "$HOME/.cache/fr/worktrees/$repo/${1//\//__}" || fail "no worktree for $1: $out"
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
echo "ok: placement-merged-status"
