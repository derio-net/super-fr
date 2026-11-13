#!/usr/bin/env bash
# Row placement-move-and-drift (spec 2026-11-04-repo-feature-settings R27, R28; plan
# 2026-11-12-placement-resolver phase 7).
#
# A repo-placement repo with one archived feature (feat/old, merged into main) and one live
# branch (feat/live, in its workspace, carrying its own acceptance row). `fr placement move
# --to quiet` is interrupted (origin refuses the push), and the re-run completes: every
# artifact on `fr`, the switch on, a pushed removal branch and nothing pushed to main.
# `fr acceptance status` reads the same before and after. In feat/live's workspace the next
# `fr run status` refuses naming `fr placement migrate-branch` (CI=true is set: detection
# never migrates), and `fr placement migrate-branch` clears it. Nothing reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
scenario_require_fresh_repo

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

# enter <branch>: an isolation workspace for <branch>, cwd in it
enter() {
  cd "$base" || fail "cd $base"
  run_fr out isolation up --branch "$1"
  require_exit 0 "$out"
  cd "$HOME/.cache/fr/worktrees/$repo/${1//\//__}" || fail "no worktree for $1: $out"
}

# feat/old: an archived spec and an acceptance row, merged into main
enter feat/old
mkdir -p docs/superpowers/implemented/specs
echo "# old" > docs/superpowers/implemented/specs/2026-11-13-old-design.md
git add -A && git commit -qm "docs(old): the spec" || fail "old spec"
run_fr out acceptance init
require_exit 0 "$out"
run_fr out acceptance add --id old-row --capability c --acceptance "the old feature holds" \
  --origin spec:2026-11-13-old#R1 --feature 2026-11-13-old --status manual --notes n --repo derio-net/m
require_exit 0 "$out"
run_fr out push
require_exit 0 "$out"
( cd "$base" && git fetch -q origin && git merge -q --no-ff -m "Merge feat/old" origin/feat/old \
    && git push -q origin main && git fetch -q origin ) || fail "merge feat/old"

# feat/live: a live branch carrying its own row
enter feat/live
run_fr out acceptance add --id live-row --capability c --acceptance "the live feature holds" \
  --origin spec:2026-11-13-live#R1 --feature 2026-11-13-live --status not-implemented \
  --notes n --repo derio-net/m
require_exit 0 "$out"
run_fr out push
require_exit 0 "$out"

cd "$base" || fail "cd base"
git pull -q --ff-only origin main || fail "pull main"
strip() { printf '%s\n' "$1" | grep -Ev '^(merged|unmerged|note):' ; }
run_fr before acceptance status
require_exit 0 "$before"
expect_grep 'manual: 1' "$before" "the merged row is counted before the move"
main_before="$(git --git-dir="$origin" rev-parse main)"

# An interrupted move: origin refuses the push mid-copy
chmod -R a-w "$origin" || fail "lock origin"
run_fr out placement move --to quiet
chmod -R u+w "$origin" || fail "unlock origin"
require_exit 2 "$out"
[ -f "$(git rev-parse --git-common-dir)/fr-placement-move.json" ] || fail "no state file after the interruption: $out"
git --git-dir="$origin" rev-parse -q --verify refs/heads/fr >/dev/null && fail "fr reached origin"

run_fr out placement move --to quiet
require_exit 0 "$out"
expect_grep 'resuming the move to quiet' "$out" "the re-run resumes"
expect_grep 'moved to placement quiet' "$out" "the move completes"
expect_grep 'git history still holds' "$out" "the move says history keeps the files"
expect_grep 'fr pr create' "$out" "the move prints the removal PR command"
[ -f "$(git rev-parse --git-common-dir)/fr-placement-move.json" ] && fail "state file left behind"
names="$(git --git-dir="$origin" ls-tree -r --name-only fr)"
expect_grep '^settings.yaml$' "$names" "the switch is on origin/fr"
expect_grep '^features/moved__2026-11-13-old/docs/acceptance/features/2026-11-13-old.yaml$' "$names" \
  "the archived feature's fragment is on fr"
expect_grep '^features/moved__2026-11-13-old/merged.yaml$' "$names" "a merged: record was synthesised"
expect_grep '^features/moved__2026-11-13-old/docs/superpowers/implemented/specs/' "$names" \
  "the archived spec is on fr"
subjects="$(git --git-dir="$origin" log --format=%s fr)"
[ "$(printf '%s\n' "$subjects" | sort | uniq -d)" = "" ] || fail "duplicated fr commits: $subjects"
[ "$(git --git-dir="$origin" rev-parse main)" = "$main_before" ] || fail "the move pushed to main"
removal="$(git --git-dir="$origin" ls-tree -r --name-only chore/fr-placement-move-to-quiet)" \
  || fail "no removal branch on origin"
refuse_grep '^docs/(superpowers|acceptance)/' "$removal" "the removal branch still holds fr files"

run_fr after acceptance status
require_exit 0 "$after"
[ "$(strip "$before")" = "$(strip "$after")" ] || fail "acceptance status changed:
--- before
$before
--- after
$after"

# The live branch drifted: detected and refused, never migrated
cd "$HOME/.cache/fr/worktrees/$repo/feat__live" || fail "cd feat__live"
head="$(git rev-parse HEAD)"
run_fr out run status
require_exit 2 "$out"
expect_grep 'fr placement migrate-branch' "$out" "run status names migrate-branch"
[ "$(git rev-parse HEAD)" = "$head" ] || fail "the gate moved the branch"
run_fr out placement migrate-branch
require_exit 0 "$out"
expect_grep 'migrated' "$out" "migrate-branch migrates"
git --git-dir="$origin" ls-tree -r --name-only fr \
  | grep -qx 'features/feat__live/docs/acceptance/features/2026-11-13-live.yaml' \
  || fail "the live row is not on origin/fr"
[ -e docs/acceptance/features/2026-11-13-live.yaml ] && fail "the live row stayed on the branch"
run_fr out run status
refuse_grep 'migrate-branch' "$out" "the drift is cleared"
run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'not-implemented: 1' "$out" "the live branch still sees its own row"
echo "ok: placement-move-and-drift"
