#!/usr/bin/env bash
# Row archive-dry-run: `fr archive --dry-run` reports what the run would do and changes
# nothing: not the tree, not the index, not the forge. It exits with the code the real
# run would, in a plan-dir run and in a --branch run.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_owed_world.sh"
export PATH="$here/fixtures/archive-dry-run/bin:$PATH"

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
[ -z "$(git status --porcelain)" ] || { git add -A && git commit -qm outcomes || fail "outcomes commit"; }
tip="$(git rev-parse HEAD)"

snapshot() {
  { git status --porcelain --untracked-files=all; git diff --cached; git rev-parse HEAD
    git worktree list; } 2>&1
}
no_forge_writes() {
  refuse_grep '^(issue (create|comment|close)|label create)' "$(cat "$FAKE_GH_LOG")" "$1"
}

# 1. A plan-dir dry run lists the move and writes nothing; the real run then agrees.
before="$(snapshot)"
run_fr dry archive "docs/superpowers/plans/$plan" --dry-run
dry_rc=$RC
expect_grep 'archived:' "$dry" "the dry run prints the real run's line"
expect_grep 'would stage' "$dry" "the dry run summarises what it would stage"
[ "$(snapshot)" = "$before" ] || fail "a plan dry run changed the tree, the index or HEAD"
[ -d "docs/superpowers/plans/$plan" ] || fail "a plan dry run moved the plan"
no_forge_writes "a plan dry run wrote to the forge"
run_fr real archive "docs/superpowers/plans/$plan" --issues all
[ "$RC" -eq "$dry_rc" ] || fail "the dry run exited $dry_rc, the real run $RC"
git reset -q --hard "$tip" && git clean -qfd

# 2. A --branch dry run changes nothing and exits as the real run does.
git checkout -q main && git merge -q --no-ff chore/closeout-widget -m "merge closeout" \
  && git push -q origin main || fail "merge the branch"
git checkout -q chore/closeout-widget
: > "$FAKE_GH_LOG"   # step 1's real run wrote; the --branch dry run must add nothing
before="$(snapshot)"
run_fr dry archive --branch chore/closeout-widget --dry-run
dry_rc=$RC
[ "$(snapshot)" = "$before" ] || fail "a --branch dry run changed the tree, the index or HEAD"
no_forge_writes "a --branch dry run wrote to the forge"
run_fr real archive --branch chore/closeout-widget
[ "$RC" -eq "$dry_rc" ] || fail "the --branch dry run exited $dry_rc, the real run $RC"
echo "ok: archive-dry-run"
