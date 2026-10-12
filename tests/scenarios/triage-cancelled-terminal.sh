#!/usr/bin/env bash
# Row triage-cancelled-batch-terminal: a dispatched batch that was cancelled and had its
# claims released (one with a wave, one without) is not shown as Running on board.html,
# and `fr triage check --json` lists no claim or release owed for its members. Facts are
# fixtures/cancelled-terminal-facts.json (made by make_cancelled_terminal_facts.py); the
# judgements are written here. Nothing reaches a forge or a runner (render-only board).
# `check --json` reports owed CLAIMS only (it has no releases-owed field); that no release
# is owed is pinned by tests/unit/test_triage_cancelled_terminal.py.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

state="$(mktemp -d)"
trap 'rm -rf "$state"' EXIT
cp "$here/fixtures/cancelled-terminal-facts.json" "$state/facts.json"
cat > "$state/judgements.yaml" <<'YAML'
schema: 6
tiers: [{n: 1, title: Now}]
issues:
  "widgets#1": {tier: 1}
  "widgets#2": {tier: 1}
  "widgets#3": {tier: 1}
  "widgets#4": {tier: 1}
batches:
  - id: with-wave
    title: Cancelled with a wave
    ids: ["widgets#1", "widgets#2"]
    wave: 1
    events:
      - {kind: dispatch, at: "2026-10-01T10:00:00Z", runner: fake, handle: h1, branch: feat/batch-with-wave}
      - {kind: cancel, at: "2026-10-01T12:00:00Z", reason: dropped}
      - {kind: claims_released, at: "2026-10-01T12:01:00Z", keys: ["widgets#1", "widgets#2"]}
  - id: no-wave
    title: Cancelled without a wave
    ids: ["widgets#3", "widgets#4"]
    events:
      - {kind: dispatch, at: "2026-10-01T10:00:00Z", runner: fake, handle: h2, branch: feat/batch-no-wave}
      - {kind: cancel, at: "2026-10-01T12:00:00Z", reason: dropped}
      - {kind: claims_released, at: "2026-10-01T12:01:00Z", keys: ["widgets#3", "widgets#4"]}
YAML

run_fr out triage board --repo example-org/widgets --dir "$state"
require_exit 0 "$out"
board="$(cat "$state/board.html")"
for id in with-wave no-wave; do
  card="$(printf '%s' "$board" | tr '\n' ' ' | grep -o "<details class=\"card[^\"]*\" id=\"card-$id\".*" | sed 's#</details>.*##')"
  expect_grep "card-$id" "$card" "$id has a card on the board"
  expect_grep 'stage-cancelled' "$card" "$id reads as cancelled"
  refuse_grep 'session running' "$card" "$id is not described as running"
done
running="$(printf '%s' "$board" | tr '\n' ' ' | grep -o '<section class="col" data-column="running">.*' | sed 's#</section>.*##')"
expect_grep 'data-column="running"' "$running" "the Running column was found"
refuse_grep 'card-with-wave|card-no-wave' "$running" "neither batch sits in the Running column"

run_fr out triage check --repo example-org/widgets --dir "$state" --json
require_exit 0 "$out"
json="$(printf '%s' "$out" | tr -d '[:space:]')"
expect_grep '"claims_owed":\[\]' "$json" "no claim is owed for a cancelled, released batch"
echo "ok: triage-cancelled-terminal"
