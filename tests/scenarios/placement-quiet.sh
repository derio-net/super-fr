#!/usr/bin/env bash
# Row placement-quiet: the quiet placement end to end (spec
# 2026-11-04-repo-feature-settings R2, R3, R23). In a fresh repo with a local bare
# origin: `fr settings init --quiet` pushes the orphan `fr` branch; `fr isolation up`
# (host worktree) records quiet; a plan, a journal entry and a run cursor land on `fr` under
# features/feat__q/, a code commit stays on feat/q, and `fr push` pushes both. Then:
# feat/q carries no fr path and no chore(fr) subject, every `fr` commit after the root
# touches one feature path, and deleting origin's `fr` makes the workspace refuse,
# naming both placements. Nothing reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

HOME="$(mktemp -d)" && export HOME           # the fr and feature worktrees live below it
export FR_ISOLATION_TARGET=worktree
origin="$(mktemp -d)/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
echo seed > README.md
git add -A && git commit -qm seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null
repo="$(basename "$(git rev-parse --show-toplevel)")"

run_fr out settings init --quiet
require_exit 0 "$out"
expect_grep 'predates' "$out" "init --quiet states the known limitation"
git --git-dir="$origin" show fr:settings.yaml | grep -qx 'placement: quiet' \
  || fail "origin/fr:settings.yaml does not say placement: quiet"

run_fr out isolation up --branch feat/q
require_exit 0 "$out"
wt="$HOME/.cache/fr/worktrees/$repo/feat__q"
frwt="$HOME/.cache/fr/worktrees/$repo/fr"
[ -d "$wt" ] && [ -d "$frwt" ] || fail "no feature or fr worktree: $out"
grep -q '"placement": "quiet"' "$wt/.fr-isolation" || fail "the marker does not record quiet"
cd "$wt" || fail "cd $wt"

run_fr out plan create --slug 2026-11-12-q --target-repo derio-net/q
require_exit 0 "$out"
run_fr out journal add --scope plan --slug 2026-11-12-q --kind discovery --title t --body b --global
require_exit 0 "$out"
run_fr out run start fr-goal --branch feat/q
require_exit 0 "$out"
cursor="$(ls "$frwt"/features/feat__q/docs/superpowers/runs/*.yaml 2>/dev/null | head -1)"
[ -n "$cursor" ] || fail "no run cursor below the feature path: $out"
run_id="$(basename "$cursor" .yaml)"
echo code > code.txt
git add code.txt && git commit -qm "feat(q): a code change" || fail "code commit"
refuse_grep '.' "$(git status --porcelain)" "the product checkout is clean"

run_fr out push
require_exit 0 "$out"

fr_paths="$(git --git-dir="$origin" ls-tree -r --name-only feat/q | grep -E '^docs/(superpowers|acceptance)/' || true)"
[ -z "$fr_paths" ] || fail "origin feat/q carries fr paths: $fr_paths"
git --git-dir="$origin" log --format=%s feat/q | grep -q '^feat(q): a code change$' \
  || fail "origin feat/q lacks the code commit"
refuse_grep '^chore\(fr\)' "$(git --git-dir="$origin" log --format=%s main..feat/q)" \
  "no chore(fr) commit on feat/q"
expect_grep '^features/feat__q/docs/superpowers/plans/2026-11-12-q/_meta.yaml$' \
  "$(git --git-dir="$origin" ls-tree -r --name-only fr)" "origin fr holds the plan"
root="$(git --git-dir="$origin" rev-list --max-parents=0 fr)"
for c in $(git --git-dir="$origin" rev-list fr ^"$root"); do
  names="$(git --git-dir="$origin" show --name-only --format= "$c")"
  [ -n "$names" ] || fail "fr commit $c touches nothing"
  stray="$(printf '%s\n' "$names" | grep -v '^features/feat__q/' || true)"
  [ -z "$stray" ] || fail "fr commit $c touches more than one feature path: $stray"
done

git push -q origin --delete fr || fail "delete origin fr"
run_fr out run status "$run_id"
[ "$RC" -ne 0 ] || fail "run status did not refuse after origin's fr was deleted: $out"
flat="$(printf '%s' "$out" | tr '\n' ' ')"
expect_grep 'placement: quiet' "$flat" "the refusal names quiet"
expect_grep 'placement: repo' "$flat" "the refusal names repo"
echo "ok: placement-quiet"
