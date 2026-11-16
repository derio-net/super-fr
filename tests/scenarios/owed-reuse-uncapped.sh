#!/usr/bin/env bash
# Row owed-reuse-uncapped: `fr archive` finds an existing owed issue by its `fr:owed`
# label, so a repo with more open issues than the listing limit never gets a duplicate;
# and a listing that reached its limit cannot be trusted, so nothing is filed, no label
# is created and the owed entry stays in its journal. Uses a recording `gh`
# (fixtures/owed-reuse-uncapped/bin/gh) and a fresh `git init` with a bare local origin.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_owed_world.sh"
export PATH="$here/fixtures/owed-reuse-uncapped/bin:$PATH"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log" FAKE_GH_KEY="$key"
: > "$FAKE_GH_LOG"

git init -q -b main . || fail "git init"
owed_world
owed_world_commit
git checkout -q -b chore/closeout-widget || fail "housekeeping branch"
run_fr out closeout outcome --spec "$spec" --step 1 --na --reason "the suite runs in CI"
require_exit 0 "$out"
run_fr out closeout outcome --spec "$spec" --step 2 --owed --why "needs the merged build"
require_exit 0 "$out"
[ -z "$(git status --porcelain)" ] || { git add -A && git commit -qm outcomes || fail "outcomes commit"; }
journal=docs/superpowers/implemented/journals/specs/2026-10-11-widget.md

# 1. More open issues than the limit: the owed one is found by its label and reused.
export FAKE_GH_MODE=many
run_fr out archive "docs/superpowers/plans/$plan" --no-issues
require_exit 0 "$out"
expect_grep "reused: $key -> example-org/widgets#7" "$out" "the existing owed issue is reused"
refuse_grep '^issue create' "$(cat "$FAKE_GH_LOG")" "a duplicate was filed"
expect_grep 'filed_as=example-org/widgets#7' "$(cat "$journal")" "the journal records the reused issue"

# 2. A listing that reached its limit: nothing is filed, no label is created.
git reset -q --hard HEAD && git clean -fdq || fail "reset to the committed outcomes"
: > "$FAKE_GH_LOG"
export FAKE_GH_MODE=limit
run_fr out archive "docs/superpowers/plans/$plan" --no-issues
require_exit 0 "$out"
expect_grep 'reached its limit of 200' "$out" "the warning names the limit"
refuse_grep '^issue create' "$(cat "$FAKE_GH_LOG")" "an issue was filed at the limit"
refuse_grep '^label create' "$(cat "$FAKE_GH_LOG")" "a label was created at the limit"
refuse_grep 'filed_as=' "$(cat "$journal")" "the journal claims a filing"
expect_grep "fr-owed|owed" "$(cat "$journal")" "the owed entry stays in the journal"
echo "ok: owed-reuse-uncapped"
