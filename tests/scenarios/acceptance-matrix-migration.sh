#!/usr/bin/env bash
# Row acceptance-matrix-migration (spec 2026-11-04-repo-feature-settings R19):
# `fr migrate artifacts --yes` splits a v5 `docs/acceptance/matrix.yaml` by origin
# spec into docs/acceptance/features/<slug>.yaml (rows citing no single spec go to
# legacy.yaml), rewrites spec paths as logical `spec:<slug>` refs, and deletes the
# matrix and its committed reports; `fr acceptance status` then reports the same
# rows. The matrix is tests/fixtures/acceptance/matrix_v5_excerpt.yaml, a captured
# excerpt of this repo's own v5 matrix; the fixture is a fresh `git init`, no forge.
# Portable: no GNU-only flags (BSD/macOS and GNU userlands alike).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

git init -q -b main . 2>/dev/null || fail "git init"
mkdir -p docs/acceptance
cp "$here/../fixtures/acceptance/matrix_v5_excerpt.yaml" docs/acceptance/matrix.yaml \
  || fail "copy the captured matrix"
for report in report_local.html report_linked.html report_linked.md; do
  printf '<rendered>\n' > "docs/acceptance/$report"
done
git add -A && git commit -qm seed || fail "seed commit"
git checkout -qb feat/split || fail "branch"
rows_before="$(grep -c '^  - id: ' docs/acceptance/matrix.yaml)"

run_fr out migrate artifacts --yes
require_exit 0 "$out"
expect_grep 'migrated: docs/acceptance/matrix.yaml' "$out" "the matrix is migrated"

[ ! -e docs/acceptance/matrix.yaml ] || fail "the matrix survived the split"
for report in report_local.html report_linked.html report_linked.md; do
  [ ! -e "docs/acceptance/$report" ] || fail "the committed report $report survived"
done
for feature in 2026-07-04-acceptance-matrix 2026-09-29-fr-goal-light-path legacy; do
  [ -f "docs/acceptance/features/$feature.yaml" ] || fail "no fragment for $feature"
done
light="$(cat docs/acceptance/features/2026-09-29-fr-goal-light-path.yaml)"
expect_grep '^repo: derio-net/super-fr$' "$light" "every fragment carries the repo's identity"
expect_grep 'spec:2026-09-29-fr-goal-light-path#R1' "$light" "a spec path became a logical ref"
refuse_grep 'docs/superpowers/implemented/specs/' "$light" "no spec path is left in a row origin"
legacy="$(cat docs/acceptance/features/legacy.yaml)"
expect_grep 'id: acceptance-report-dual' "$legacy" "a two-spec row is legacy"
expect_grep 'id: runner-unit-refusal' "$legacy" "a debug-journal row is legacy"
expect_grep 'journals/debug/' "$legacy" "a debug journal keeps its path ref"

run_fr out acceptance status
require_exit 0 "$out"
counts="$(printf '%s\n' "$out" | grep '^acceptance: ')" || fail "no status line: $out"
rows_after="$(printf '%s\n' "$counts" | tr ',' '\n' | awk -F': ' '{n += $NF} END {print n}')"
[ "$rows_after" -eq "$rows_before" ] \
  || fail "status reports $rows_after rows, the matrix held $rows_before: $counts"

run_fr out validate artifacts
require_exit 0 "$out"
echo "ok: acceptance-matrix-migration"
