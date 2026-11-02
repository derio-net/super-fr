#!/usr/bin/env bash
# Row gate-backfill-apply-ledger (spec 2026-11-01-gate-backfill R6-R10, R14): `fr gate backfill
# --yes` applies the reviewed plan file through the forge adapter only. The fixture is the dry-run
# scenario's (a walk-owed row and a merged plan's unticked manual phase, both delivered by PR #12),
# plus a second walk-owed row and a hand-made tracker (#5, someone else's). After the dry run the
# plan file's decisions are edited with sed: the row stays `owed`, the manual phase `adopt`s #5 and
# the second row is parked. A stateful recording `gh` (fixtures/gate-backfill-apply/bin/gh) keeps
# what was written, so the second `--yes` is proven to write nothing.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export PATH="$here/fixtures/gate-backfill-apply/bin:$PATH"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log" FAKE_GH_STATE="$world/state.json"
export HOME="$world/home"
mkdir -p "$HOME"
: > "$FAKE_GH_LOG"
cat > "$FAKE_GH_STATE" <<JSON
{"next": 20, "labels": [], "prs": {"12": {"labels": []}},
 "issues": {"5": {"title": "widget phase 2 by hand", "body": "someone filed this", "author": "someone-else",
                  "labels": [], "state": "OPEN", "comments": []}}}
JSON

plan=2026-10-11-widget
spec=docs/superpowers/specs/2026-10-11-widget-design.md

git symbolic-ref HEAD refs/heads/main || fail "HEAD to main"
git init -q --bare -b main "$world/origin.git" || fail "bare origin"
git remote add origin https://github.com/example-org/widgets.git
git config url."$world/origin.git".insteadOf https://github.com/example-org/widgets.git
mkdir -p docs/acceptance "docs/superpowers/plans/$plan" docs/superpowers/specs src
cat > docs/acceptance/matrix.yaml <<YAML
schema_version: 5
org: example-org
repo: widgets
rows:
  - id: widget-live
    capability: widget
    acceptance: the widget runs live
    status: walk-owed
    origin:
      - widgets:$spec#R1
  - id: widget-park
    capability: widget
    acceptance: the widget parks
    status: walk-owed
    origin:
      - widgets:$spec#R2
YAML
cat > "$spec" <<MD
# Widget

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| $plan | example-org/widgets | \`docs/superpowers/plans/$plan\` | — |
MD
cat > "docs/superpowers/plans/$plan/_meta.yaml" <<YAML
schema_version: 2
plan: $plan
spec: $spec
target_repo: example-org/widgets
created: '2026-10-11'
YAML
printf '# Widget plan\n' > "docs/superpowers/plans/$plan/_prose.md"
phase() { # <n> <tag> <state>
cat > "docs/superpowers/plans/$plan/0$1.yaml" <<YAML
schema_version: 2
phase:
  number: $1
  title: Phase $1
  tag: $2
  depends_on: []
  tracking_issue: null
tasks:
  - number: 1
    title: Do it
    steps:
      - id: P$1.T1.S1
        text: Do the thing
state:
  steps:
    P$1.T1.S1:
      state: "$3"
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
YAML
}
phase 1 agentic x
phase 2 manual ' '
echo 'x = 1' > src/widget.py
git add -A && git commit -qm "feat: widget (#12)" || fail "commit"
git push -q origin main || fail "push"


run_fr out gate backfill
require_exit 0 "$out"
plan_file="$HOME/.cache/fr/gate-backfill/example-org--widgets/plan.yaml"
[ -f "$plan_file" ] || fail "no plan file at $plan_file"
sed -i.bak "/key: plan:$plan#p2/,/^ *decision:/ s|^\( *decision:\).*|\1 'adopt example-org/widgets#5'|" "$plan_file"
sed -i.bak "/key: row:widget-park/,/^ *decision:/ s|^\( *decision:\).*|\1 park|" "$plan_file"
grep -q "adopt example-org/widgets#5" "$plan_file" || fail "the adopt decision was not written"

writes='^(label create|issue (edit|create|comment|close)|pr (edit|comment))'
refuse_grep "$writes" "$(cat "$FAKE_GH_LOG")" "the dry run wrote to the forge"

run_fr out gate backfill --yes
require_exit 0 "$out"
log="$(cat "$FAKE_GH_LOG")"
expect_grep 'label create gate:tester ' "$log" "gate:tester ensured"
expect_grep 'label create gate:devops ' "$log" "gate:devops ensured"
expect_grep 'label create fr:owed ' "$log" "fr:owed ensured"
expect_grep 'label create fr:awaiting-live ' "$log" "fr:awaiting-live ensured"
expect_grep 'issue edit 12 --repo example-org/widgets --add-label gate:tester' "$log" "PR 12 labelled tester"
expect_grep 'issue edit 12 --repo example-org/widgets --add-label gate:devops' "$log" "PR 12 labelled devops"
expect_grep 'issue create .*--label fr:awaiting-live --label fr:owed' "$log" "the row's tracker"
expect_grep 'issue comment 5 .*fr-gate-adopt:plan:'"$plan"'#p2 gate:devops pr:12' "$log" "the adopt comment"
expect_grep 'issue edit 5 --repo example-org/widgets --add-label fr:owed' "$log" "the adopted issue labelled"
[ "$(printf '%s\n' "$log" | grep -c '^issue create ')" -eq 1 ] || fail "expected exactly one tracker filed"
refuse_grep 'issue (edit|close) 5 .*--body' "$log" "the adopted issue's body was edited"
refuse_grep '^issue close' "$log" "an issue was closed"
refuse_grep 'widget-park' "$(grep -E "$writes" "$FAKE_GH_LOG")" "the parked row reached the forge"

before="$(grep -Ec "$writes" "$FAKE_GH_LOG")"
run_fr out gate backfill --yes
require_exit 0 "$out"
after="$(grep -Ec "$writes" "$FAKE_GH_LOG")"
[ "$before" -eq "$after" ] || fail "the second --yes wrote ($before -> $after): $(tail -n 5 "$FAKE_GH_LOG")"
[ -z "$(git status --porcelain)" ] || fail "--yes wrote a repo file: $(git status --porcelain)"
echo "ok: gate-backfill-apply"
