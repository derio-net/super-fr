#!/usr/bin/env bash
# Row review-lenses-accumulate: in a fixture repo with a started run, lenses are added
# through step records at two steps and through `fr journal add --kind lens` from the
# command line; `fr lenses status` shows each with its reasons and the adding step; an
# unknown lens and an empty reason are refused with the journal unchanged. (The reshape
# and adopt cases arrive with the lens-review step.)
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_lens_fixture.sh"
world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
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
echo "ok: review-lenses-accumulate"
