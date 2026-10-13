#!/usr/bin/env bash
# Row exit-gates-verify-without-section: a row's own `verify:` is checked by
# `fr plan self-review` even when the spec has no `## Verification` section (#1155).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

SPEC=docs/superpowers/specs/2026-10-14-toy.md
PLAN=docs/superpowers/plans/2026-10-14-toy
mkdir -p docs/superpowers/specs docs/acceptance

write_spec() {
  cat > "$SPEC" <<'YAML'
# Toy

## Requirements

R1. x

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
YAML
}
write_matrix() {  # <extra row lines>
  cat > docs/acceptance/matrix.yaml <<YAML
schema_version: 5
org: derio-net
repo: toy
rows:
  - id: row-a
    capability: "Cap"
    acceptance: "needs the released build"
    origin: ["toy:docs/superpowers/specs/2026-10-14-toy.md#R1"]
    status: not-implemented
$1
YAML
}
write_spec
write_matrix "    verify: live"
cat > phases.yaml <<'YAML'
- number: 1
  title: One
  tag: agentic
  tier: standard
  acceptance: [row-a]
  tasks:
    - number: 1
      title: t
      steps:
        - {id: P1.T1.S1, text: s}
YAML
git add -A >/dev/null 2>&1
git commit -qm "fixture" >/dev/null 2>&1 || true

run_fr out plan create --slug 2026-10-14-toy --target-repo derio-net/toy \
  --spec "$SPEC" --phases-file phases.yaml;   require_exit 0 "$out"

# A post-merge row with no reason and no section: flagged, and the message asks for the section.
run_fr out plan self-review "$PLAN";          require_exit 1 "$out"
expect_grep 'row-a' "$out" "the refusal names the row"
expect_grep 'reason' "$out" "the refusal asks for a reason"
expect_grep '## Verification' "$out" "the refusal asks for a Verification section"
expect_grep 'every other row' "$out" "the refusal warns that other rows then take the section strategy"

# An unresolvable verify: is flagged too.
write_matrix "    verify: no-such-strategy"
run_fr out plan self-review "$PLAN";          require_exit 1 "$out"
expect_grep 'no-such-strategy' "$out" "an unresolvable verify: is flagged"

# No row verify: and no section — the world before strategies, unchanged.
write_matrix ""
run_fr out plan self-review "$PLAN";          require_exit 0 "$out"
refuse_grep '^\[error\]' "$out" "a section-less spec with no verify: passes"
echo "ok: exit-gates-verify-without-section"
