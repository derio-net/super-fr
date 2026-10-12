#!/usr/bin/env bash
# Row triage-config-skew-visible: a repo whose .fr/triage.yaml carried a key this fr
# ignored, and a skipped repo, are named on the rendered board (role="alert") and in
# `fr triage check --json` (`skipped`, `config_ignored`). The facts are
# fixtures/config-skew-facts.json (schema 9), made by make_config_skew_facts.py.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

state="$(mktemp -d)"
trap 'rm -rf "$state"' EXIT
cp "$here/fixtures/config-skew-facts.json" "$state/facts.json"

run_fr out triage render --org example-org --dir "$state"
require_exit 0 "$out"
html="$(cat "$state/triage.html")"
expect_grep 'role="alert"' "$html" "the skew banner is on triage.html"
expect_grep 'future_key' "$html" "the ignored key is named"
expect_grep 'example-org/gadgets' "$html" "the skipped repo is named"

run_fr out triage board --org example-org --dir "$state"
require_exit 0 "$out"
board="$(cat "$state/board.html")"
expect_grep 'role="alert"' "$board" "the skew banner is on board.html"
expect_grep 'future_key' "$board" "board.html names the ignored key"
expect_grep 'example-org/gadgets' "$board" "board.html names the skipped repo"

run_fr out triage check --org example-org --dir "$state" --json
require_exit 0 "$out"
json="$(printf '%s' "$out" | tr -d '[:space:]')"
expect_grep '"skipped":\[\{"repo":"example-org/gadgets"' "$json" "check lists the skipped repo"
expect_grep '"config_ignored":\{"example-org/widgets":\["future_key"\]' "$json" "check lists the ignored key"

run_fr out triage check --org example-org --dir "$state"
require_exit 0 "$out"
first="$(printf '%s\n' "$out" | head -1)"
expect_grep 'skipped repos' "$first" "the skipped section comes first in the text report"
echo "ok: triage-config-skew"
