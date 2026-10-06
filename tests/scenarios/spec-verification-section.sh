#!/usr/bin/env bash
# Row spec-verification-section: a spec's `## Verification` section sets the
# run's strategy and per-row overrides, a post-merge row without a reason fails
# `fr plan self-review`, and a legacy `verify: post-merge` row reads as `live`.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

SPEC=docs/superpowers/specs/2026-10-06-toy.md
PLAN=docs/superpowers/plans/2026-10-06-toy
mkdir -p docs/superpowers/specs docs/acceptance

# A matrix still at schema 3, carrying the legacy spelling.
cat > docs/acceptance/matrix.yaml <<'YAML'
schema_version: 3
org: derio-net
repo: toy
rows:
  - id: row-live
    capability: "Cap"
    acceptance: "needs the released build"
    origin: ["toy:docs/superpowers/specs/2026-10-06-toy.md#R1"]
    status: not-implemented
    verify: post-merge
  - id: row-cand
    capability: "Cap"
    acceptance: "scripted"
    origin: ["toy:docs/superpowers/specs/2026-10-06-toy.md#R1"]
    status: not-implemented
YAML

write_spec() {  # <verification-lines>
  cat > "$SPEC" <<YAML
# Toy

## Requirements

R1. x

## Verification

strategy: candidate
$1

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
YAML
}
write_spec "- row-live: live"
cat > phases.yaml <<'YAML'
- number: 1
  title: One
  tag: agentic
  tier: standard
  acceptance: [row-live, row-cand]
  tasks:
    - number: 1
      title: t
      steps:
        - {id: P1.T1.S1, text: s}
YAML
git add -A >/dev/null 2>&1
git commit -qm "fixture" >/dev/null 2>&1 || true

# Legacy verify: post-merge migrates to live, and nothing else moves.
run_fr out migrate artifacts --yes;           require_exit 0 "$out"
grep -q '^schema_version: 4' docs/acceptance/matrix.yaml || fail "the matrix did not reach schema 4"
grep -q 'verify: live' docs/acceptance/matrix.yaml || fail "verify: post-merge did not become live"
! grep -q 'verify: post-merge' docs/acceptance/matrix.yaml || fail "verify: post-merge survived"

run_fr out plan create --slug 2026-10-06-toy --target-repo derio-net/toy \
  --spec "$SPEC" --phases-file phases.yaml;   require_exit 0 "$out"

# A post-merge row with no reason fails self-review, by name.
run_fr out plan self-review "$PLAN";          require_exit 1 "$out"
expect_grep 'row-live' "$out" "the refusal names the row"
expect_grep 'post-merge' "$out" "the refusal says the row is post-merge"
expect_grep 'reason' "$out" "the refusal asks for a reason"
# An agent pre-merge row with no scenario fails too.
expect_grep 'row-cand' "$out" "the refusal names the row with no scenario"
expect_grep 'scenario' "$out" "the refusal asks for a scenario"

# The reason satisfies it; the scenario path is the row's own.
write_spec "- row-live: live — needs the released build"
cat > docs/acceptance/matrix.yaml <<'YAML'
schema_version: 4
org: derio-net
repo: toy
rows:
  - id: row-live
    capability: "Cap"
    acceptance: "needs the released build"
    origin: ["toy:docs/superpowers/specs/2026-10-06-toy.md#R1"]
    status: not-implemented
    verify: live
  - id: row-cand
    capability: "Cap"
    acceptance: "scripted"
    origin: ["toy:docs/superpowers/specs/2026-10-06-toy.md#R1"]
    status: not-implemented
    scenario: tests/scenarios/row-cand.sh
YAML
run_fr out plan self-review "$PLAN"
refuse_grep '^\[error\]' "$out" "a reasoned section with a scenario passes self-review"

# A malformed section is refused naming the line.
write_spec "- row-live live no dash"
run_fr out plan self-review "$PLAN";          require_exit 1 "$out"
expect_grep 'malformed' "$out" "a malformed section is refused"
echo "ok: spec-verification-section"
