#!/usr/bin/env bash
# Row triage-closed-in-progress-set: closed issues still labelled `fr:in-progress` are a
# set of their own in `fr triage check`, with each entry's state (stale, release-pending,
# held), and `fr triage clean-labels` without --yes names only the stale one and writes
# nothing. The facts are fixtures/closed-in-progress-facts.json (schema 9), the output of
# the model's own serializer; nothing here reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

state="$(mktemp -d)"
trap 'rm -rf "$state"' EXIT
cp "$here/fixtures/closed-in-progress-facts.json" "$state/facts.json"

run_fr out triage check --repo example-org/widgets --dir "$state" --json
require_exit 0 "$out"
json="$(printf '%s' "$out" | tr -d '[:space:]')"
expect_grep '"key":"widgets#1"[^}]*"state":"stale"' "$json" "the stale entry is listed with its state"
expect_grep '"key":"widgets#2"[^}]*"state":"release-pending"' "$json" "the release-pending entry is listed"
expect_grep '"key":"widgets#3"[^}]*"state":"held"' "$json" "the held entry is listed"

run_fr out triage clean-labels --repo example-org/widgets --dir "$state"
require_exit 0 "$out"
expect_grep 'widgets#1' "$out" "the stale entry is a target"
refuse_grep 'widgets#2|widgets#3' "$out" "release-pending and held entries are never targets"
expect_grep 'nothing written' "$out" "a dry run writes nothing"
echo "ok: triage-closed-in-progress"
