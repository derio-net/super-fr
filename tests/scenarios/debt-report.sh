#!/usr/bin/env bash
# Row debt-report: `fr debt` reports acceptance debt by status, lists walked
# rows with their walk date and never counts them as debt, reports plans and
# owed actions, as text and as JSON, and writes nothing. The fixture repo is a
# fresh `git init` with a hand-written version-5 matrix; --offline keeps it from
# reaching a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

git init -q -b main . || fail "git init"
mkdir -p docs/acceptance
cat > docs/acceptance/matrix.yaml <<'YAML'
schema_version: 5
org: example-org
repo: widgets
rows:
  - id: wired-row
    capability: demo
    acceptance: Runs in CI.
    status: ci
  - id: unwired-row
    capability: demo
    acceptance: A test exists but CI does not run it.
    status: unwired
  - id: owed-row
    capability: demo
    acceptance: A live walk is owed.
    status: walk-owed
  - id: walked-row
    capability: demo
    acceptance: Proven live.
    status: walked
    walks:
      - {strategy: live, harness: h, model: m, outcome: pass, at: '2026-09-30T10:00:00Z', evidence: e}
YAML
git add -A && git commit -qm seed || fail "seed commit"
before="$(git status --porcelain)"

run_fr out debt --offline
require_exit 0 "$out"
expect_grep 'unwired-row \[unwired\]' "$out" "an unwired row is listed as debt"
expect_grep 'owed-row \[walk-owed\]' "$out" "a walk-owed row is listed as debt"
expect_grep 'walked-row \[walked 2026-09-30\]' "$out" "a walked row shows its walk date"
refuse_grep 'walked-row \[(unwired|walk-owed)' "$out" "a walked row is not debt"
expect_grep 'row:owed-row \(row\)' "$out" "the walk-owed row is also an owed item, once"
expect_grep 'forge unavailable' "$out" "offline says the forge was not used"

run_fr out debt --offline --json
require_exit 0 "$out"
json="$(printf '%s' "$out" | tr -d '[:space:]')"
expect_grep '"by_status":\{[^}]*"unwired":1' "$json" "the JSON counts unwired"
expect_grep '"by_status":\{[^}]*"walk-owed":1' "$json" "the JSON counts walk-owed"
expect_grep '"key":"row:owed-row"' "$json" "the JSON carries the owed key"

[ "$(git status --porcelain)" = "$before" ] || fail "fr debt wrote to the repo"
echo "ok: debt-report"
