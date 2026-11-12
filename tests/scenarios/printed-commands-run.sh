#!/usr/bin/env bash
# Row printed-commands-run (spec 2026-11-08 R3-R6): the commands `fr gate backfill` and `fr gate
# pass` print are run, as printed, through the installed `fr`. The fixture is gate-backfill-apply's
# (a walk-owed row with a note, a merged plan's unticked manual phase, both delivered by PR #12)
# and the same stateful recording `gh`, extended to comment on and close issues and PRs. After
# `--yes` files the row's tracker, the dry run prints the link command; it must keep the row's
# status and note. `fr gate pass` then prints the discharge command, which must run once its
# placeholders are filled.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export PATH="$here/fixtures/printed-commands-run/bin:$PATH"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log" FAKE_GH_STATE="$world/state.json"
export HOME="$world/home"
mkdir -p "$HOME"
: > "$FAKE_GH_LOG"
cat > "$FAKE_GH_STATE" <<JSON
{"next": 20, "labels": [], "prs": {"12": {"labels": []}}, "issues": {}}
JSON

plan=2026-10-11-widget
spec=docs/superpowers/specs/2026-10-11-widget-design.md

git symbolic-ref HEAD refs/heads/main || fail "HEAD to main"
git config user.email scenario@example.com && git config user.name scenario
git init -q --bare -b main "$world/origin.git" || fail "bare origin"
git remote add origin https://github.com/example-org/widgets.git
git config url."$world/origin.git".insteadOf https://github.com/example-org/widgets.git
mkdir -p docs/acceptance "docs/superpowers/plans/$plan" docs/superpowers/specs src
matrix_fragment <<YAML
schema_version: 5
org: example-org
repo: widgets
rows:
  - id: widget-live
    capability: widget
    acceptance: the widget runs live
    status: walk-owed
    notes: shipped, walk owed
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
cat > "docs/superpowers/plans/$plan/01.yaml" <<YAML
schema_version: 2
phase:
  number: 1
  title: Phase 1
  tag: agentic
  depends_on: []
  tracking_issue: null
tasks:
  - number: 1
    title: Do it
    steps:
      - id: P1.T1.S1
        text: Do the thing
state:
  steps:
    P1.T1.S1:
      state: "x"
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
YAML
echo 'x = 1' > src/widget.py
git add -A && git commit -qm "feat: widget (#12)" || fail "commit"
git push -q origin main || fail "push"

run_fr out gate backfill
require_exit 0 "$out"
run_fr out gate backfill --yes
require_exit 0 "$out"
refuse_grep '^issue close' "$(cat "$FAKE_GH_LOG")" "an issue was closed"

# 1. the link command the dry run prints runs as printed, and keeps the row's status and note
run_fr out gate backfill
require_exit 0 "$out"
link="$(printf '%s\n' "$out" | grep -E '^ +fr acceptance set-status .* --issue ' | sed 's/^ *//')"
[ -n "$link" ] || fail "the dry run printed no link command: $out"
refuse_grep ' --(notes|status) ' "$link" "the link command is link-only"
eval "$link" > "$world/link.out" 2>&1 || fail "the printed link command failed: $link: $(cat "$world/link.out")"
# R16: the row is merged, so the link is an amendment in the fragment of the feature whose
# delivery it closes (the row's origin spec), never in the row owner's legacy fragment.
expect_grep ' --feature 2026-10-11-widget' "$link" "the link names the feature it closes"
row="$(sed -n '/id: widget-live/,/^  - id:/p' docs/acceptance/features/legacy.yaml)"
expect_grep 'status: walk-owed' "$row" "the merged row is not edited in place"
refuse_grep 'example-org/widgets#' "$(cat docs/acceptance/features/legacy.yaml)" "the link went to legacy"
amended="$(cat docs/acceptance/features/2026-10-11-widget.yaml)"
expect_grep 'status: walk-owed' "$amended" "the linked row kept its status"
expect_grep 'shipped, walk owed' "$amended" "the linked row kept its note"
expect_grep 'example-org/widgets#' "$amended" "the linked row names its tracker"

# 2. the gate pass prints the discharge command; it runs once its placeholders are filled
run_fr out gate pass --repo example-org/widgets --pr 12 --gate tester --notes "walked live" --yes
require_exit 0 "$out"
discharge="$(printf '%s\n' "$out" | grep -E '^ +fr acceptance set-status .* --status walked ' | sed 's/^ *//')"
[ -n "$discharge" ] || fail "gate pass printed no discharge command: $out"
for flag in --walk --harness --model --strategy; do
  expect_grep "$flag "  "$discharge" "the discharge command names $flag"
done
filled="$(printf '%s\n' "$discharge" | sed -e 's/"<walk log>"/walk.log/' -e 's/"<harness>"/claude-code/' \
  -e 's/"<model>"/model-x/' -e 's/"<strategy>"/live/' -e 's/"<what passed>"/"walked live"/')"
refuse_grep '<' "$filled" "an unfilled placeholder is left"
eval "$filled" > "$world/discharge.out" 2>&1 || fail "the printed discharge command failed: $filled: $(cat "$world/discharge.out")"
expect_grep ' --feature 2026-10-11-widget' "$discharge" "the discharge names the feature it closes"
expect_grep 'status: walked' "$(cat docs/acceptance/features/2026-10-11-widget.yaml)" "the discharge moved the row"
echo "ok: printed-commands-run"
