#!/usr/bin/env bash
# Row archive-dry-run: `fr archive --dry-run` prints what the run would do and changes
# nothing, and exits with the code the real run returns. For a plan-dir run with
# `--issues all` and for a `--branch` run, each with something to archive, it compares
# the dry run with a real run of IDENTICAL arguments on the same tree: the same exit
# code, the same `archived:` lines, and the owed issue the real run files is the one the
# dry run reports it would file. After each dry run the tree, the index, HEAD, the refs
# and the registered worktrees are unchanged and the forge log holds no write.
# Not here: a forge call the preview does not know (exit 1, naming it) cannot be
# injected into an installed `fr`, so tests/unit/test_archive_dry_run.py covers it
# (test_an_unknown_forge_call_exits_one_naming_it,
# test_a_crash_after_a_refused_call_still_names_it_and_exits_one).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_owed_world.sh"
export PATH="$here/fixtures/archive-dry-run/bin:$PATH"
scenario_require_fresh_repo

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log"
: > "$FAKE_GH_LOG"

git init -q -b main . || fail "git init"
owed_world
owed_world_commit
# The archive's fetch may set origin/HEAD, a remote-tracking ref R11 lets a dry run move;
# set it first, so the snapshot below holds every ref still.
git remote set-head origin main >/dev/null || fail "origin/HEAD"
git checkout -q -b chore/closeout-widget || fail "housekeeping branch"
run_fr out closeout outcome --spec "$spec" --step 1 --na --reason "the suite runs in CI"
require_exit 0 "$out"
run_fr out closeout outcome --spec "$spec" --step 2 --owed --why "needs the merged build"
require_exit 0 "$out"
[ -z "$(git status --porcelain)" ] || { git add -A && git commit -qm outcomes || fail "outcomes commit"; }
tip="$(git rev-parse HEAD)"

snapshot() {
  { git status --porcelain --untracked-files=all; git diff --cached; git rev-parse HEAD
    git for-each-ref --format='%(refname) %(objectname)'; git worktree list --porcelain; } 2>&1
}
unchanged() {  # unchanged <before> <what>
  local now; now="$(snapshot)"
  [ "$now" = "$1" ] || fail "$2: $(diff <(printf '%s\n' "$1") <(printf '%s\n' "$now"))"
}
forge_writes() { grep -E '^(issue (create|comment|close|edit)|label create)' "$FAKE_GH_LOG"; }
archived_lines() { printf '%s\n' "$1" | grep -E '^ *archived:' | sed 's/^ *//'; }

# 1. A plan-dir dry run with --issues all: it lists the move and the owed issue it would
#    file, writes nothing, and the real run with the same arguments agrees.
args=(archive "docs/superpowers/plans/$plan" --issues all)
before="$(snapshot)"
run_fr dry "${args[@]}" --dry-run
dry_rc=$RC
expect_grep "archived: docs/superpowers/plans/$plan -> " "$dry" "the dry run prints the real run's move"
expect_grep 'would stage' "$dry" "the dry run summarises what it would stage"
expect_grep "filed: $key -> example-org/widgets#900000" "$dry" "the dry run says it would file the owed issue"
expect_grep "create_issue\('example-org/widgets'" "$dry" "the dry run lists the forge write it would make"
refuse_grep 'fr-archive-dry-run-' "$dry" "the dry run printed a scratch path"
refuse_grep 'moves staged via git mv' "$dry" "the dry run told the operator to commit moves it never made"
unchanged "$before" "a plan dry run changed the tree, the index, HEAD, a ref or a worktree"
[ -d "docs/superpowers/plans/$plan" ] || fail "a plan dry run moved the plan"
[ -z "$(forge_writes)" ] || fail "a plan dry run wrote to the forge: $(forge_writes)"
run_fr real "${args[@]}"
[ "$RC" -eq "$dry_rc" ] || fail "the dry run exited $dry_rc, the real run $RC"
[ "$(archived_lines "$dry")" = "$(archived_lines "$real")" ] ||
  fail "the dry run's moves differ from the real run's: $(archived_lines "$dry") vs $(archived_lines "$real")"
expect_grep "filed: $key -> example-org/widgets#1" "$real" "the real run files the owed issue"
expect_grep '^issue create' "$(forge_writes)" "the real run wrote to the forge"
git reset -q --hard "$tip" && git clean -qfd

# 2. A --branch dry run of a merged branch with a plan to archive: it lists the move,
#    writes nothing, and the real run with the same arguments agrees.
git checkout -q main && git merge -q --no-ff chore/closeout-widget -m "merge closeout" &&
  git push -q origin main || fail "merge the outcomes"
git checkout -q -b feat/gadget || fail "feature branch"
gadget=2026-10-12-gadget
cp -R "docs/superpowers/plans/$plan" "docs/superpowers/plans/$gadget"
sed -i.bak "s/^plan: .*/plan: $gadget/" "docs/superpowers/plans/$gadget/_meta.yaml" &&
  rm "docs/superpowers/plans/$gadget/_meta.yaml.bak"
git add -A && git commit -qm "feat: gadget plan" && git push -q origin feat/gadget || fail "gadget branch"
git checkout -q main && git merge -q --no-ff feat/gadget -m "Merge feat/gadget" &&
  git push -q origin main || fail "merge the gadget branch"
git checkout -q -b chore/closeout-gadget origin/main || fail "gadget housekeeping branch"
: > "$FAKE_GH_LOG"
args=(archive --branch feat/gadget)
before="$(snapshot)"
run_fr dry "${args[@]}" --dry-run
dry_rc=$RC
expect_grep "archived: docs/superpowers/plans/$gadget -> " "$dry" "the --branch dry run prints the move"
expect_grep 'would stage' "$dry" "the --branch dry run summarises what it would stage"
unchanged "$before" "a --branch dry run changed the tree, the index, HEAD, a ref or a worktree"
[ -z "$(forge_writes)" ] || fail "a --branch dry run wrote to the forge: $(forge_writes)"
run_fr real "${args[@]}"
[ "$RC" -eq "$dry_rc" ] || fail "the --branch dry run exited $dry_rc, the real run $RC"
[ "$(archived_lines "$dry")" = "$(archived_lines "$real")" ] ||
  fail "the --branch dry run's moves differ from the real run's"
echo "ok: archive-dry-run"
