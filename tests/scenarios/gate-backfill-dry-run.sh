#!/usr/bin/env bash
# Rows gate-backfill-dry-run-plan (spec 2026-11-01-gate-backfill R1-R5, R11): `fr gate backfill`
# without --yes reads the forge, writes a plan file OUTSIDE the repo, prints every candidate and
# writes nothing to the forge. The fixture is a fresh `git init` with a bare local origin (reached
# through `insteadOf` from a github.com url naming example-org/widgets), a v5 matrix with one
# walk-owed row, a merged plan with an unticked manual phase, both delivered by a squash commit
# `feat: widget (#12)`, and a recording `gh` (fixtures/gate-backfill/bin/gh) that answers reads only.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export PATH="$here/fixtures/gate-backfill/bin:$PATH"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log"
export HOME="$world/home"
mkdir -p "$HOME"
: > "$FAKE_GH_LOG"

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
expect_grep 'row:widget-live +gate=tester +PR #12 \(commit\) +-> owed' "$out" "the row line"
expect_grep "plan:$plan#p2 +gate=devops +PR #12 \(commit\) +-> owed" "$out" "the manual phase line"
expect_grep 'key: row:widget-live' "$(cat "$plan_file")" "the plan file names the row"
expect_grep "key: plan:$plan#p2" "$(cat "$plan_file")" "the plan file names the phase"
[ -z "$(git status --porcelain)" ] || fail "the dry run wrote a repo file: $(git status --porcelain)"
refuse_grep '^(pr (edit|comment)|issue (create|comment|close|edit)|label|api -X|api .*(-X|--method))' \
  "$(cat "$FAKE_GH_LOG")" "a forge write reached gh"
echo "ok: gate-backfill-dry-run"
