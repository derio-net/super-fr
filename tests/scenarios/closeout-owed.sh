#!/usr/bin/env bash
# Rows closeout-step-outcomes and owed-durable-at-archive: a close-out whose
# Test Plan step was skipped never drops it silently. `fr archive` holds the
# merged plan naming every step with no outcome and the command that records
# it; `fr closeout outcome` records one step n/a and the other owed; `fr
# archive` then moves the plan and files the owed step as one `fr:owed` issue
# even under --no-issues; and `fr debt` lists it. The fixture is a fresh `git
# init` with a bare local origin (so the plan is merged; reached through
# `insteadOf` from a github.com url naming the repo), a v5 matrix naming the
# repo, and a recording `gh` (fixtures/closeout-owed/bin/gh) — no real forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export PATH="$here/fixtures/closeout-owed/bin:$PATH"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log"
: > "$FAKE_GH_LOG"

plan=2026-10-11-widget
spec=docs/superpowers/specs/2026-10-11-widget-design.md
key='spec:2026-10-11-widget#step2'

git init -q -b main . || fail "git init"
# The harness already `git init`ed this fixture with the host's default branch,
# and a re-init ignores -b: point HEAD at main explicitly (CI defaults to master).
git symbolic-ref HEAD refs/heads/main || fail "HEAD to main"
git init -q --bare -b main "$world/origin.git" || fail "bare origin"
# Owed filing trusts only the origin remote's configured url, so it names the
# repo (github.com/example-org/widgets); `insteadOf` serves it from the bare repo.
git remote add origin https://github.com/example-org/widgets.git
git config url."$world/origin.git".insteadOf https://github.com/example-org/widgets.git
mkdir -p docs/acceptance "docs/superpowers/plans/$plan" docs/superpowers/specs
cat > docs/acceptance/matrix.yaml <<'YAML'
schema_version: 5
org: example-org
repo: widgets
rows: []
YAML
cat > "$spec" <<MD
# Widget

## Test Plan

1. Run the widget suite in CI.
2. Walk the widget live after merge.

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
cat > "docs/superpowers/plans/$plan/01.yaml" <<'YAML'
schema_version: 2
phase:
  number: 1
  title: Build it
  tag: agentic
  depends_on: []
  tracking_issue: null
  files:
    - src/**
tasks:
  - number: 1
    title: Build
    steps:
      - id: P1.T1.S1
        text: Build the widget
state:
  steps:
    P1.T1.S1:
      state: x
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
YAML
git add -A && git commit -qm seed || fail "seed commit"
git push -q origin main || fail "push"
# A close-out runs on a housekeeping branch off the merged default branch.
git checkout -q -b chore/closeout-widget || fail "housekeeping branch"

# 1. Archive holds: two steps, neither recorded — each named with its command.
run_fr out archive "docs/superpowers/plans/$plan"
require_exit 2 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
expect_grep 'Test Plan step\(s\) 1, 2 have no recorded outcome' "$flat" "the hold names the steps"
expect_grep "fr closeout outcome --spec $spec --step 2" "$flat" "the hold prints the command"
[ -d "docs/superpowers/plans/$plan" ] || fail "a held plan moved"

# 2. Record the outcomes: step 1 n/a, step 2 owed.
run_fr out closeout outcome --spec "$spec" --step 1 --na --reason "the suite runs in CI"
require_exit 0 "$out"
run_fr out closeout outcome --spec "$spec" --step 2 --owed --why "needs the merged build"
require_exit 0 "$out"
run_fr out closeout outcome --spec "$spec" --step 2 --ran --evidence "x"
require_exit 2 "$out"
expect_grep 'already recorded: test-plan-step-2' "$out" "a recorded step is refused"
run_fr out journal check --scope spec --slug 2026-10-11-widget
require_exit 0 "$out"
expect_grep '1 owed action\(s\) open: test-plan-step-2' "$out" "an owed step passes the check, listed"

# 3. Archive moves the plan and files the owed step, whatever --no-issues says.
run_fr out archive "docs/superpowers/plans/$plan" --no-issues
require_exit 0 "$out"
[ ! -d "docs/superpowers/plans/$plan" ] || fail "the plan did not move"
expect_grep "filed: $key -> example-org/widgets#1" "$out" "the owed step is filed"
log="$(tr '\n' ' ' < "$FAKE_GH_LOG")"
expect_grep 'issue create --repo example-org/widgets --title Owed: .*--label fr:owed' "$log" \
  "one fr:owed issue is created"
expect_grep "<!-- fr-owed:$key --> --label fr:owed" "$log" "the issue carries the owed key's marker"
[ "$(grep -c '^issue create' "$FAKE_GH_LOG")" -eq 1 ] || fail "more than one issue was filed"
journal=docs/superpowers/implemented/journals/specs/2026-10-11-widget.md
expect_grep 'filed_as=example-org/widgets#1' "$(cat "$journal")" "the journal records where it went"

# 4. The debt report lists it, once, from the journal.
run_fr out debt --offline
require_exit 0 "$out"
expect_grep "$key \(journal\)" "$out" "fr debt lists the owed step"
[ "$(printf '%s\n' "$out" | grep -c "$key")" -eq 1 ] || fail "the owed step is listed more than once"
# 5. Discharge it: the evidence closes the filed issue through the forge.
run_fr out journal resolve --scope spec --slug 2026-10-11-widget --id test-plan-step-2 \
  --state fixed --note "walked live after merge: green"
require_exit 0 "$out"
expect_grep 'closed example-org/widgets#1' "$out" "the discharge closes the issue"
log="$(tr '\n' ' ' < "$FAKE_GH_LOG")"
expect_grep 'issue comment 1 --repo example-org/widgets --body Discharged: walked live after merge: green' \
  "$log" "the evidence is the closing comment"
expect_grep 'issue close --repo example-org/widgets 1' "$log" "the recording gh saw the close"
run_fr out debt --offline
require_exit 0 "$out"
refuse_grep "$key" "$out" "a discharged step is no longer owed"
echo "ok: closeout-owed"
