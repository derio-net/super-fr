#!/usr/bin/env bash
# Row owed-close-at-merge (spec 2026-11-15-owed-archive-side-effects R1-R3): what
# `fr journal resolve --state fixed` does with an owed entry's filed issue. Off the
# default branch it makes no forge call and prints the `Closes <owner/repo>#<n>` line
# the branch's PR body must carry; on the default branch the same resolve closes the
# issue exactly once, with the discharge note as its comment. The PR-body listing
# and deliver's check (R4, R5) are proven by tests/unit/test_owed_close_at_merge.py
# and tests/unit/test_deliver_closing_keywords.py, not here. The world is
# closeout-owed's (`_owed_world.sh`), with its recording `gh`
# (fixtures/closeout-owed/bin/gh) — no real forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_owed_world.sh"
export PATH="$here/fixtures/closeout-owed/bin:$PATH"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log"
: > "$FAKE_GH_LOG"

git init -q -b main . || fail "git init"
owed_world
owed_world_commit
git checkout -q -b chore/closeout-widget || fail "housekeeping branch"
run_fr out closeout outcome --spec "$spec" --step 1 --na --reason "the suite runs in CI"
require_exit 0 "$out"
run_fr out closeout outcome --spec "$spec" --step 2 --owed --why "needs the merged build"
require_exit 0 "$out"
run_fr out archive "docs/superpowers/plans/$plan" --no-issues
require_exit 0 "$out"
expect_grep "filed: $key -> example-org/widgets#1" "$out" "the owed step is filed"
[ -z "$(git status --porcelain)" ] || { git add -A && git commit -qm archive || fail "archive commit"; }
filed="$(git rev-parse HEAD)"

# 1. Off the default branch: the discharge is recorded and the forge is not called.
: > "$FAKE_GH_LOG"
run_fr out journal resolve --scope spec --slug 2026-10-11-widget --id test-plan-step-2 \
  --state fixed --note "walked live after merge: green"
require_exit 0 "$out"
expect_grep 'closes when this branch merges' "$out" "the close is deferred to the merge"
expect_grep 'Closes example-org/widgets#1' "$out" "the closing line to carry is printed"
[ ! -s "$FAKE_GH_LOG" ] || fail "resolve off the default branch called the forge: $(cat "$FAKE_GH_LOG")"

# 2. On the default branch (the archive merged, the discharge not yet): one close.
git reset -q --hard "$filed" || fail "drop the branch's discharge"
git checkout -q main && git merge -q --ff-only chore/closeout-widget || fail "merge to main"
git push -q origin main || fail "publish main"
run_fr out journal resolve --scope spec --slug 2026-10-11-widget --id test-plan-step-2 \
  --state fixed --note "walked live after merge: green"
require_exit 0 "$out"
expect_grep 'closed example-org/widgets#1' "$out" "the discharge on main closes the issue"
expect_grep 'issue comment 1 --repo example-org/widgets --body Discharged: walked live after merge: green' \
  "$(tr '\n' ' ' < "$FAKE_GH_LOG")" "the close carries the discharge note as its evidence comment"
[ "$(grep -c '^issue close' "$FAKE_GH_LOG")" -eq 1 ] || fail "expected exactly one close: $(cat "$FAKE_GH_LOG")"
refuse_grep 'Closes example-org/widgets#1' "$out" "on main no closing line is owed"
echo "ok: owed-close-at-merge"
