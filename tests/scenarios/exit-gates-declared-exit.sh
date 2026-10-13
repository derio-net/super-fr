#!/usr/bin/env bash
# Row exit-gates-declared-exit: a run's exit (kinds + gates) comes from the
# strategy manifest's gate, the repo's remap and the spec's `gate:` lines, and
# `fr verification exit` prints it; the run is gated iff a gate is tester/devops.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

SPEC=docs/superpowers/specs/2026-10-14-toy.md
mkdir -p docs/superpowers/specs docs/acceptance .fr
cat > docs/acceptance/matrix.yaml <<'YAML'
schema_version: 5
org: derio-net
repo: toy
rows:
  - id: row-live
    capability: "Cap"
    acceptance: "needs the released build"
    origin: ["toy:docs/superpowers/specs/2026-10-14-toy.md#R1"]
    status: not-implemented
  - id: row-plain
    capability: "Cap"
    acceptance: "scripted"
    origin: ["toy:docs/superpowers/specs/2026-10-14-toy.md#R1"]
    status: not-implemented
YAML

write_spec() {  # <verification-lines>
  cat > "$SPEC" <<YAML
# Toy

## Requirements

R1. x

## Verification

$1
YAML
}

# The manifest's gate: `live` ships gate tester, so the live row gates the run.
write_spec "strategy: candidate
- row-live: live — needs the released build"
run_fr out verification exit --spec "$SPEC";    require_exit 0 "$out"
expect_grep 'kinds: candidate, live' "$out" "the exit lists both kinds"
expect_grep 'gated: row-live \(tester\)' "$out" "the live row is gated by its manifest default"
expect_grep 'gated: yes' "$out" "a tester gate makes the run gated"

# A spec gate line wins over the manifest default.
write_spec "strategy: candidate
gate: row-live=devops
- row-live: live — needs the released build"
run_fr out verification exit --spec "$SPEC";    require_exit 0 "$out"
expect_grep 'gated: row-live \(devops\)' "$out" "the row gate line beats the manifest default"

# The repo's remap of a kind: a candidate tested by hand is a tester gate.
write_spec "strategy: candidate"
printf 'exit:\n  gates:\n    candidate: tester\n' > .fr/triage.yaml
run_fr out verification exit --spec "$SPEC";    require_exit 0 "$out"
expect_grep 'run gate: tester' "$out" "the remap sets the run gate"
expect_grep 'gated: yes' "$out" "a remapped tester gate gates the run"

# No post-merge gate: a reviewer gate is recorded but holds nothing.
rm .fr/triage.yaml
write_spec "strategy: candidate
gate: reviewer"
run_fr out verification exit --spec "$SPEC";    require_exit 0 "$out"
expect_grep 'gates: reviewer' "$out" "the reviewer gate is recorded"
expect_grep 'gated: no' "$out" "a pre-merge gate does not gate the run"

# An unknown gate is refused naming the line.
write_spec "gate: wizard"
run_fr out verification exit --spec "$SPEC";    require_exit 2 "$out"
expect_grep 'gate' "$out" "an unknown gate is refused"
echo "ok: exit-gates-declared-exit"
