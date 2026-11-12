#!/usr/bin/env bash
# Row review-lenses-accumulate: in a fixture repo with a started run, lenses are added
# through step records at two steps and through `fr journal add --kind lens` from the
# command line; `fr lenses status` shows each with its reasons and the adding step; an
# unknown lens and an empty reason are refused with the journal unchanged. A run started
# before its shape had `lens-review` is reshaped to owe it while its cursor is before
# `deliver`; one already on `deliver` is refused by reshape, which names
# `fr run adopt <plan-dir> --supersede`, and is carried over by that command with
# `lens-review` pending.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_lens_fixture.sh"
world="$(mktemp -d)"
top="$world"
trap 'rm -rf "$top"' EXIT
lens_world "$world"

lens_step design "  - {kind: lens, lens: security, title: the walk reads a token}" \
  "emitted: {spec: $LENS_SPEC}"
require_exit 0 "$out"
lens_step build "  - {kind: lens, lens: security, title: the walk builds a shell command}"
require_exit 0 "$out"
run_fr out journal add --scope spec --slug "$LENS_SLUG" --kind lens --lens tests \
  --title "only the happy path is tested"
require_exit 0 "$out"
expect_grep 'added lens lens-tests-1' "$out" "the command line names the assigned id"

before_status="$(git status --porcelain)"
run_fr out lenses status
require_exit 0 "$out"
expect_grep '^security: "the walk reads a token" \(step design, lens-security-1\); "the walk builds a shell command" \(step build, lens-security-2\)$' \
  "$out" "both reasons for one lens, each with its step"
expect_grep '^tests: "only the happy path is tested" \(command line, lens-tests-1\)$' "$out" \
  "the command-line addition records no step"
[ "$(git status --porcelain)" = "$before_status" ] || fail "fr lenses status wrote something"

before="$(cat "$LENS_JOURNAL")"
run_fr out journal add --scope spec --slug "$LENS_SLUG" --kind lens --lens no-such-lens \
  --title "why"
require_exit 2 "$out"
expect_grep 'no-such-lens' "$out" "the unknown lens is named"
run_fr out journal add --scope spec --slug "$LENS_SLUG" --kind lens --lens tests --title " "
require_exit 2 "$out"
expect_grep 'reason' "$out" "an empty reason is refused"
[ "$(cat "$LENS_JOURNAL")" = "$before" ] || fail "a refused addition changed the journal"

# --- runs in flight when lens-review shipped (R13) -------------------------------
start="$PWD"
flights="$world"
flight_world() {  # flight_world <dir>: a run f1 on `lens-flight`, the pre-lens shape
  world="$1"
  mkdir -p "$world/base" && cd "$world/base" && git init -q || fail "flight world"
  lens_review_repo "$world"
  cat > docs/superpowers/workflows/lens-flight.yaml <<'YAML'
workflow: lens-flight
schema: 1
unit: run
steps:
  - id: plan
    kind: agent
    emits: [plan]
  - id: implement
    kind: agent
    needs: [plan]
    emits: [journal:plan]
  - id: deliver
    kind: agent
    needs: [plan]
YAML
  git add -A docs && git_ci commit -qm "pre-lens shape" || fail "shape commit"
  run_fr out run start lens-flight --branch feat/walk --run-id f1
  require_exit 0 "$out"
  run_fr out run advance f1
  require_exit 0 "$out"
  run_fr out run resolve f1 --step plan --state done --emitted "plan=$LENS_PLAN_REL"
  require_exit 0 "$out"
}
with_lens_review() {  # the same shape once lens-review shipped
  awk '/^  - id: deliver$/ { print "  - id: lens-review\n    kind: agent\n    needs: [plan]\n    emits: [journal:plan]\n    evidence: [lenses, review, reviewer, findings]" } { print }' \
    docs/superpowers/workflows/lens-flight.yaml > lens-flight.tmp \
    && mv lens-flight.tmp docs/superpowers/workflows/lens-flight.yaml
  git add -A docs && git_ci commit -qm "lens-review shipped" || fail "shape commit"
}

flight_world "$flights/flight-a"
run_fr out run advance f1
require_exit 0 "$out"
with_lens_review
run_fr out run advance f1
require_exit 2 "$out"
expect_grep 'fr run reshape f1' "$out" "a drifted run names the reshape"
run_fr out run reshape f1 --yes
require_exit 0 "$out"
expect_grep 'added: lens-review' "$out" "reshape inserts lens-review"
run_fr out run status f1
expect_grep 'lens-review: pending' "$out" "the lens review is owed"
expect_grep 'step/plan:' "$out" "the plan unit is kept"
cd "$start" || fail "back"

flight_world "$flights/flight-b"
run_fr out run advance f1
run_fr out run resolve f1 --step implement --state done
require_exit 0 "$out"
run_fr out run status f1
expect_grep 'cursor: deliver' "$out" "the old run is on deliver"
with_lens_review
run_fr out run reshape f1 --yes
require_exit 2 "$out"
expect_grep 'fr run adopt <plan-dir> --supersede' "$out" "reshape at deliver names adopt --supersede"
run_fr out run adopt "$LENS_PLAN_REL" --supersede --workflow lens-flight --branch feat/walk \
  --run-id f2 --yes
require_exit 0 "$out"
run_fr out run status f2
require_exit 0 "$out"
expect_grep 'lens-review: pending' "$out" "the carried run owes the lens review"
expect_grep 'deliver: pending' "$out" "before deliver"
expect_grep 'step/implement:' "$out" "the old implement unit is carried"
cd "$start" || fail "back"
echo "ok: review-lenses-accumulate"
