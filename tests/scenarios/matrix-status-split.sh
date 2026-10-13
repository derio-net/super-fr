#!/usr/bin/env bash
# Row matrix-status-split: `fr migrate artifacts --yes` moves every `skipped`
# row of a version-4 matrix into exactly one of unwired / walk-owed / walked by
# the fixed rule (a passing walk, else a post-merge verify, else unwired),
# leaves other statuses alone, and `manual` is the operator's explicit move. A
# matrix that still says `skipped` after the split is refused by name, with the
# migrate command. The matrix is fixtures/matrix-status-split-v4.yaml; nothing
# here reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

git init -q -b main . || fail "git init"
mkdir -p docs/acceptance
cp "$here/fixtures/matrix-status-split-v4.yaml" docs/acceptance/matrix.yaml
git add -A && git commit -qm seed || fail "seed commit"
git checkout -qb feat/split || fail "branch"

run_fr out migrate artifacts --yes
require_exit 0 "$out"
expect_grep 'migrated: docs/acceptance/matrix.yaml' "$out" "the matrix is migrated"

matrix="$(cat docs/acceptance/matrix.yaml)"
expect_grep '^schema_version: 5$' "$matrix" "the matrix is stamped version 5"
refuse_grep 'status: skipped' "$matrix" "no row still says skipped"

run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'ci: 1' "$out" "the ci row is untouched"
expect_grep 'unwired: 2' "$out" "rows with neither a walk nor a post-merge verify are unwired"
expect_grep 'walk-owed: 1' "$out" "a post-merge verify without a pass owes a walk"
expect_grep 'walked: 1' "$out" "a passing walk makes the row walked"
expect_grep 'owed-row \[walk-owed\]' "$out" "a walk-owed row is listed as debt"
refuse_grep 'walked-row \[' "$out" "a walked row is not debt"

git add -A && git commit -qm migrate || fail "migrate commit"
run_fr out acceptance set-status --id process-row --status manual --notes "a process, never automatable"
require_exit 0 "$out"
run_fr out acceptance status
expect_grep 'manual: 1' "$out" "manual is the operator's explicit move"
refuse_grep 'process-row \[' "$out" "a manual row is not debt"

sed -i.bak 's/status: manual/status: skipped/' docs/acceptance/matrix.yaml && rm -f docs/acceptance/matrix.yaml.bak
run_fr out acceptance status
[ "$RC" -ne 0 ] || fail "a v5 matrix saying skipped must be refused: $out"
expect_grep 'skipped' "$out" "the refusal names the status"
expect_grep 'fr migrate artifacts --yes' "$out" "the refusal names the way forward"
echo "ok: matrix-status-split"
