#!/usr/bin/env bash
# Row exit-gates-set-downgrade: `fr verification set` rewrites one line of the
# spec's Verification section and journals why; once spec-review is done, a change
# that makes the exit wait less is refused without a verified operator answer.
# No forge: the label re-sync finds no PR (no `origin`) and stays silent.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

SPEC=docs/superpowers/specs/2026-10-14-toy.md
RUN=r1
mkdir -p docs/superpowers/specs docs/superpowers/runs docs/acceptance
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
YAML
cat > "$SPEC" <<'MD'
# Toy

## Requirements

R1. x

## Verification

strategy: candidate
- row-live: live — needs the released build

Prose stays put.
MD

write_cursor() {  # <spec-review state>
  cat > docs/superpowers/runs/$RUN.yaml <<YAML
schema_version: 10
run: $RUN
workflow: fr-goal@1
branch: feat/toy
started: '2026-10-14T00:00:00+00:00'
cursor: spec-review
steps:
  brainstorm:
    state: done
    at: '2026-10-14T00:01:00+00:00'
    emitted:
      spec: $SPEC
  spec-review:
    state: $1
YAML
}

git checkout -q -b feat/toy
write_cursor running
git add -A && git commit -qm seed

# Before spec-review is done there is no guard: the rewrite touches one line.
before="$(cat "$SPEC")"
run_fr out verification set --run $RUN --strategy none --reason "drafting"
require_exit 0 "$out"
expect_grep 'exit-change-1' "$out" "the change is numbered"
expect_grep '^strategy: none$' "$(cat "$SPEC")" "the strategy line was rewritten"
refuse_grep '^strategy: candidate$' "$(cat "$SPEC")" "the old strategy line is gone"
expect_grep 'Prose stays put' "$(cat "$SPEC")" "the rest of the spec is untouched"
diff <(printf '%s\n' "$before") "$SPEC" | grep -c '^[<>]' | grep -qx 2 || fail "more than one line changed"
expect_grep 'exit-change-1' "$(cat docs/superpowers/journals/specs/*.md)" "the reason is journalled"
[ -z "$(git status --porcelain)" ] || fail "the change was not committed"

# A row line and its gate are inserted beside their kind.
run_fr out verification set --run $RUN --row row-live --strategy live --gate tester --reason "walk it after merge"
require_exit 0 "$out"
expect_grep '^gate: row-live=tester$' "$(cat "$SPEC")" "the row gate line was inserted"
expect_grep '^- row-live: live — walk it after merge$' "$(cat "$SPEC")" "the row bullet was rewritten"

# After spec-review: waiting less is refused, and nothing changes.
write_cursor done
git add -A && git commit -qm "spec-review done"
tip="$(git rev-parse HEAD)"
run_fr out verification set --run $RUN --row row-live --strategy candidate --reason "too slow"
require_exit 2 "$out"
expect_grep -- '--answered-by operator' "$out" "the refusal names the way forward"
[ "$(git rev-parse HEAD)" = "$tip" ] || fail "a refused change committed"
expect_grep '^- row-live: live' "$(cat "$SPEC")" "a refused change left the spec alone"
run_fr out verification set --run $RUN --row row-live --strategy live --gate developer --reason "x" --answered-by agent
require_exit 2 "$out"

# Waiting more is allowed without an answer.
run_fr out verification set --run $RUN --strategy live --reason "stronger"
require_exit 0 "$out"
expect_grep '^strategy: live$' "$(cat "$SPEC")" "a stronger change needs no answer"

# A spec with no Verification section is refused, naming how to add one.
printf '# Bare\n\nR1. x\n' > "$SPEC"
run_fr out verification set --run $RUN --strategy live --reason "x"
require_exit 2 "$out"
expect_grep '## Verification' "$out" "the refusal names the section to add"
echo "ok: exit-gates-set-downgrade"
