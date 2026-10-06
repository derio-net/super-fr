#!/usr/bin/env bash
# Row awaiting-live-triage: issues labelled `fr:awaiting-live` are listed as
# their own set by `fr triage check` and never as unranked or unplaced work.
# The facts are fixtures/awaiting-live-facts.json, the output of the model's
# own serializer (open #1 labelled, closed #2 labelled, open #3 plain); nothing
# here reaches a forge. (The close-out brief's label line is unit-tested: it
# needs a delivered run and a PR body, which no fresh fixture repo has.)
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

state="$(mktemp -d)"
trap 'rm -rf "$state"' EXIT
cp "$here/fixtures/awaiting-live-facts.json" "$state/facts.json"

run_fr out triage check --repo example-org/widgets --dir "$state" --json
require_exit 0 "$out"
json="$(printf '%s' "$out" | tr -d '[:space:]')"
expect_grep '"awaiting_live":\[\{[^]]*"widgets#1"' "$json" "the open labelled issue is in the awaiting_live set"
refuse_grep '"awaiting_live":\[[^]]*widgets#2' "$json" "a closed issue is not in the set"
refuse_grep '"awaiting_live":\[[^]]*widgets#3' "$json" "an ordinary issue is not in the set"
expect_grep '"unranked":\[[^]]*widgets#3' "$json" "an ordinary issue is still unranked"
refuse_grep '"unranked":\[[^]]*widgets#1' "$json" "an awaiting-live issue is never unranked"
refuse_grep '"unplaced":\[[^]]*widgets#1' "$json" "an awaiting-live issue is never unplaced"

run_fr out triage check --repo example-org/widgets --dir "$state"
require_exit 0 "$out"
expect_grep 'awaiting live' "$out" "the text report names the set"
echo "ok: awaiting-live-triage"
