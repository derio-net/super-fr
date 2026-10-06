#!/usr/bin/env bash
# Row shipped-verification-strategies: candidate, client-live, prerelease and
# live ship and validate; the candidate family installs through the repo's
# install contract, and a repo without it is refused by name.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

run_fr out verification list;                 require_exit 0 "$out"
for s in candidate client-live prerelease live; do
  expect_grep "^$s +" "$out" "shipped strategy $s is listed"
  run_fr one verification check "$s";         require_exit 0 "$one"
  expect_grep "$s: ok" "$one" "shipped strategy $s validates"
done
run_fr out verification check --all;          require_exit 0 "$out"

# A candidate walk in a repo WITHOUT the install contract is refused by name
# (R8), before anything is installed: a committed fixture with a run cursor, a
# spec whose `## Verification` says `strategy: candidate`, and one row citing it
# with a scenario.
mkdir -p docs/superpowers/runs docs/superpowers/specs docs/acceptance scenarios
cat > docs/superpowers/runs/w1.yaml <<'YAML'
schema_version: 1
run: w1
workflow: fr-goal@1
branch: b
started: '2026-10-06T11:00:00+00:00'
cursor: deliver
steps:
  spec:
    state: done
    at: '2026-10-06T12:00:00+00:00'
    emitted:
      spec: docs/superpowers/specs/s.md
YAML
printf '# S\n\n## Verification\n\nstrategy: candidate\n' > docs/superpowers/specs/s.md
cat > docs/acceptance/matrix.yaml <<'YAML'
schema_version: 4
org: o
repo: proj
rows:
  - id: row-a
    capability: c
    acceptance: a works
    origin: ["proj:docs/superpowers/specs/s.md#R1"]
    status: not-implemented
    scenario: scenarios/row-a.sh
YAML
printf '#!/bin/sh\nexit 0\n' > scenarios/row-a.sh
chmod +x scenarios/row-a.sh
git add -A && git commit -qm fixture --no-verify
run_fr out verification walk --run w1 --model scenario
require_exit 2 "$out"
expect_grep 'candidate-install' "$out" "a repo without the install contract is refused by name"
echo "ok: shipped-verification-strategies"
