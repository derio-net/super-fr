#!/usr/bin/env bash
# Row walk-recording-prints-close: `fr acceptance set-status --walk` records a
# walk naming harness, model and strategy; once every row citing an issue is
# walk-verified it prints the close command (nothing under `tracking: none`).
# Printing only: the commands are never run and no forge is reached.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

mkdir -p docs/acceptance
cat > docs/acceptance/matrix.yaml <<'YAML'
schema_version: 4
org: derio-net
repo: toy
rows:
  - id: row-a
    capability: "Cap"
    acceptance: "needs the released build"
    origin: ["toy:docs/superpowers/specs/2026-10-06-toy.md#R1"]
    status: skipped
    verify: live
    issues: ["derio-net/toy#7"]
  - id: row-b
    capability: "Cap"
    acceptance: "also carries issue 7"
    origin: ["toy:docs/superpowers/specs/2026-10-06-toy.md#R1"]
    status: skipped
    verify: live
    issues: ["derio-net/toy#7"]
YAML

walk() {  # <row> [extra...]
  local row="$1"; shift
  run_fr out acceptance set-status --id "$row" --status skipped --notes "walked" \
    --walk walk.log --harness claude-code --model scenario-model --strategy live "$@"
}

# A walk with no harness, model or strategy is refused and changes nothing.
before="$(cat docs/acceptance/matrix.yaml)"
run_fr out acceptance set-status --id row-a --status skipped --notes n --walk walk.log
require_exit 2 "$out"
[ "$before" = "$(cat docs/acceptance/matrix.yaml)" ] || fail "a refused walk rewrote the matrix"

# row-b still waits for its own walk, so row-a's walk frees nothing.
walk row-a;                                   require_exit 0 "$out"
grep -q 'outcome: pass' docs/acceptance/matrix.yaml || fail "the walk was not recorded as a pass"
grep -q 'harness: claude-code' docs/acceptance/matrix.yaml || fail "the walk did not record its harness"
grep -q 'model: scenario-model' docs/acceptance/matrix.yaml || fail "the walk did not record its model"
refuse_grep 'issue close' "$out" "a close was printed while another row still holds the issue open"

# The last holder's walk prints the close and the unlabel commands.
walk row-b;                                   require_exit 0 "$out"
expect_grep 'gh issue close 7 --repo derio-net/toy --comment' "$out" "the close command is printed"
expect_grep 'walk.log' "$out" "the close comment cites the walk evidence"
expect_grep 'gh issue edit 7 --repo derio-net/toy --remove-label fr:awaiting-live' "$out" \
  "the label-removal command is printed"

# Under tracking: none nothing is printed at all.
mkdir -p .devcontainer
printf 'schema_version: 2\nprofiles:\n  dev:\n    purpose: x\nforge: {type: github}\ntracking: {type: none}\n' \
  > .devcontainer/fr-profiles.yaml
cat > docs/acceptance/matrix.yaml <<'YAML'
schema_version: 4
org: derio-net
repo: toy
rows:
  - id: row-c
    capability: "Cap"
    acceptance: "tracked nowhere"
    origin: ["toy:docs/superpowers/specs/2026-10-06-toy.md#R1"]
    status: skipped
    verify: live
    issues: ["derio-net/toy#9"]
YAML
walk row-c;                                   require_exit 0 "$out"
refuse_grep 'issue close|issues close' "$out" "a close was printed under tracking: none"
echo "ok: walk-recording-prints-close"
