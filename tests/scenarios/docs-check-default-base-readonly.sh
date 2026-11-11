#!/usr/bin/env bash
# Row docs-check-default-base-readonly: with no --base, `fr docs check` diffs
# against the remote's default branch on a feature branch, runs only the
# structural checks on the default branch itself, still runs over a tree holding
# a stale artifact (migration gate on), and writes nothing.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_docs_fixture.sh"
unset FR_SKIP_MIGRATION   # the gate is live: `docs` must be exempt from it

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
docs_world "$world"

# A stale-stamped artifact: a plan from the first plan-folder schema.
mkdir -p docs/superpowers/plans/old
printf 'schema_version: 1\nplan: old\n' > docs/superpowers/plans/old/_meta.yaml
printf 'x = 2\n' > src/x.py
git add -A && git_ci commit -qm "change covered file, add stale artifact" || fail "commit"
snap() { git status --porcelain; git for-each-ref; git rev-parse HEAD; cat docs/superpowers/plans/old/_meta.yaml; }
before="$(snap)"

run_fr out docs check
require_exit 1 "$out"
expect_grep 'docs/a\.md' "$out" "no --base: the stale page is found against origin's default branch"
expect_grep 'src/x\.py' "$out" "the changed path is named"
[ "$before" = "$(snap)" ] || fail "fr docs wrote to the repo"
run_fr out validate artifacts
require_exit 1 "$out"   # proves the artifact really is stale, so the exemption was exercised

# On the default branch itself only structure is checked.
git checkout -q main
git merge -q --ff-only feature || fail "merge"
git push -q origin main && git fetch -q origin
before="$(snap)"
run_fr out docs check
require_exit 0 "$out"
[ "$before" = "$(snap)" ] || fail "fr docs wrote to the repo on the default branch"
echo "ok: docs-check-default-base-readonly"
