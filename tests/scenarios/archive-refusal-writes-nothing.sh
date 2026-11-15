#!/usr/bin/env bash
# Row archive-refusal-writes-nothing: a refused `fr archive <plan>` leaves the tree, the
# index and the forge as it found them, `--issues all` included; and on the default
# branch a plan skipped under `--all` says what it would record and writes nothing.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_owed_world.sh"
export PATH="$here/fixtures/archive-refusal-writes-nothing/bin:$PATH"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log"
: > "$FAKE_GH_LOG"

git init -q -b main . || fail "git init"
owed_world
# An unticked [manual] phase holds the plan.
cat > "docs/superpowers/plans/$plan/02.yaml" <<'YAML'
schema_version: 2
phase:
  number: 2
  title: Walk it live
  tag: manual
  depends_on: [1]
  tracking_issue: null
  files: []
tasks:
  - number: 1
    title: Walk
    steps:
      - id: P2.T1.S1
        text: Walk the widget
state:
  steps:
    P2.T1.S1:
      state: " "
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
YAML
owed_world_commit

snapshot() {
  { git status --porcelain; git diff --cached; git ls-files -o --exclude-standard
    find docs -type f -print0 | sort -z | xargs -0 cksum; } 2>&1
}
before="$(snapshot)"

# 1. A refused single-plan archive, with and without --issues all, changes nothing.
for flags in "" "--issues all"; do
  # shellcheck disable=SC2086
  run_fr out archive "docs/superpowers/plans/$plan" $flags
  require_exit 2 "$out"
  expect_grep 'refusing to archive' "$out" "the archive refuses ($flags)"
  [ "$(snapshot)" = "$before" ] || fail "a refused archive changed the tree or the index ($flags)"
  [ ! -e "docs/superpowers/journals" ] || fail "a refusal wrote a journal ($flags)"
  refuse_grep '^(issue (create|comment|close)|label create)' "$(cat "$FAKE_GH_LOG")" \
    "a refusal wrote to the forge ($flags)"
done

# 2. On the default branch, --all skips the plan and says what it would record.
run_fr out archive --all
require_exit 0 "$out"
expect_grep "would record owed: plan:$plan#p2 — " "$out" "the skip says what it would record"
[ "$(snapshot)" = "$before" ] || fail "a skip on the default branch changed the tree or the index"
refuse_grep '^(issue (create|comment|close)|label create)' "$(cat "$FAKE_GH_LOG")" \
  "a skip on the default branch wrote to the forge"
echo "ok: archive-refusal-writes-nothing"
