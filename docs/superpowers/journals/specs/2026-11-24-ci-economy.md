<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-ci-economy

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-24T14:48:29+00:00 input=true -->
### operator-brief · discovery · Operator brief (fr-goal invocation, plus a mid-run scope addition)

/fr-goal Build derio-net/super-fr#1647: three CI economy fixes. 1) Cancel superseded
pull_request CI runs with a per-ref concurrency group, never for pushes to main, fr-queue/**
or merge_group, and make sure ci-ok and the wave driver's checks_verdict read a cancelled run
as superseded, not red. 2) Stop re-testing a landed queue combination on main: the
fast-forwarded sha already passed every required check on fr-queue/**. The release's own
pre-publish suite must stay intact. 3) Have the wave merge queue's combination builder
resolve conflicts in generated files (scripts/sync-readme.py's docs/reference/cli.md, the
OpenCode/Hermes mirrors, the repo's mirrors: in .fr/triage.yaml) by regenerating them, and
resolve docs reviewed: stamp conflicts by taking the newer stamp, so only real conflicts are
handed back to sessions. Read spec 2026-11-19-wave-merge-queue (R6 and R13 especially) and
packages/fr/src/fr/triage/ first. The issue's operator-policy section is out of scope.
Standalone feature, one PR.

Scope addition: #1647 now has a fourth ask. A PR that changes nothing installable (by
scripts/installable.py's definition, e.g. close-out, archive and triage-state export PRs)
must not run the whole suite. Use a classifier job: run lint, validate-artifacts,
docs-check, the acceptance check and the --fr-scope tests for the changed files, and skip
the shards, collect, split-check and coverage. ci-ok must still report, and must read the
skipped jobs as passing only for that classification. Tests that read this repo's own
artifacts must still run whenever those artifacts change. Include it in this run's spec.

<!-- fr:journal kind=decision scope=spec id=q1-cancelled-reads-pending created=2026-11-24T14:48:29+00:00 decided_by=operator -->
### q1-cancelled-reads-pending · decision · A cancelled check reads as pending (superseded), never failing

Operator chose 'Pending' over 'failing unless a newer run exists'. A hand-cancel with no re-run stays pending; check_wait_minutes surfaces it for the queue. Spec R3, R4.

<!-- fr:journal kind=decision scope=spec id=q2-landed-gate-job created=2026-11-24T14:48:29+00:00 decided_by=operator -->
### q2-landed-gate-job · decision · Skip main's CI by a classifying job that finds a prior green ci-ok on the sha

Operator chose the gate job in ci.yml over dropping push:main. Hand merges keep full CI; release.yml untouched. Spec R5-R7.

<!-- fr:journal kind=decision scope=spec id=q3-generated-globs created=2026-11-24T14:48:29+00:00 decided_by=operator -->
### q3-generated-globs · decision · Generated paths are declared by a new generated: glob list in .fr/triage.yaml

Operator chose explicit generated: globs over inferring them from mirror output. Mirror commands run only on a generated conflict and may not change paths outside the globs. Spec R8-R13.

<!-- fr:journal kind=decision scope=spec id=q4-light-lane-paths created=2026-11-24T14:48:29+00:00 decided_by=operator -->
### q4-light-lane-paths · decision · The light lane excludes tests/ and .github/

Operator chose: light only when every changed path is non-installable AND outside tests/ and .github/. Spec R15.

<!-- fr:journal kind=decision scope=spec id=q5-own-artifacts-marker created=2026-11-24T14:48:29+00:00 decided_by=operator -->
### q5-own-artifacts-marker · decision · Own-artifact tests carry an own_artifacts marker that --fr-scope selects, held by a tripwire

Operator chose the marker + fr-scope + tripwire over a fixed list in ci.yml. Spec R18, R19.

<!-- fr:journal kind=decision scope=spec id=q6-verification created=2026-11-24T14:48:29+00:00 decided_by=operator -->
### q6-verification · decision · Strategy none (CI unit tests) plus three post-merge live rows; gate tester

Operator chose CI + live rows with gate: tester. Spec ## Verification.

<!-- fr:journal kind=finding scope=spec id=s-r1-1 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-1 · finding [open] (reviewer: in scope) · R13 'written in whole' excludes docs/reference/cli.md; README stays a real conflict

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-2 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-2 · finding [open] (reviewer: in scope) · Mirror commands import the combination's fr; no command line or environment named

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-3 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-3 · finding [open] (reviewer: in scope) · `if: !cancelled()` leaves a SKIPPED ci-ok that GitHub and fr read as passing

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-4 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-4 · finding [open] (reviewer: in scope) · R4 claims check_wait_minutes reports a cancelled check; slot_check only reports missing ones

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-5 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-5 · finding [open] (reviewer: in scope) · R3's reader list misses ops/gate and verify_ci; a bare grep tripwire would hit stage 'cancelled'

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-6 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-6 · finding [open] (reviewer: in scope) · GraphQL statusCheckRollup.state has no CANCELLED; R3 cannot be met by editing _CI_FAIL

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-7 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-7 · finding [open] (reviewer: in scope) · R7 cache saved on fr-queue/** is invisible to PR and main runs

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-8 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-8 · finding [open] (reviewer: in scope) · The landed lane drops main's strict fr validate artifacts

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-9 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-9 · finding [open] (reviewer: in scope) · R5 trusts any successful ci-ok from another run, PR or foreign app included

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-10 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-10 · finding [open] (reviewer: in scope) · A light-lane ci-ok is tests: ci deliver evidence; the spec is silent

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-11 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-11 · finding [open] (reviewer: in scope) · R19's tripwire heuristic misses tests that hand REPO_ROOT to an fr reader

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-12 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-12 · finding [open] (reviewer: in scope) · classify and scoped-tests need full history or the light lane never fires

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-13 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-13 · finding [open] (reviewer: in scope) · Test Plan lacks pre-merge lines for the unit tests the Verification rows cite, R4 and R14

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-14 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-14 · finding [open] (reviewer: in scope) · Design names Worktree.run_argv/changed_paths and config plumbing that do not exist

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=finding scope=spec id=s-r1-15 created=2026-11-24T14:57:19+00:00 state=open review_scope=in -->
### s-r1-15 · finding [open] (reviewer: in scope) · R3's stay-failing list omits STALE and status-context error

Raised by the independent spec reviewer; see spec-review-1.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-24T14:57:19+00:00 -->
### spec-review-1 · review · independent spec review: 15 findings, all in scope, all fixed

fr-spec-reviewer checked the spec against the six operator decisions (none contradicted), the codebase (file:line for every named file, function and job) and itself. Findings s-r1-1..s-r1-15, all in scope; each fixed in the spec (commit 'docs(spec): address spec review') and, where rows moved, by acceptance rewording.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-24T14:57:19+00:00 lens=security step=spec-review -->
### lens-security-1 · lens · queue builds run mirror commands from PR code on the driver host, and main's CI skip trusts a prior run

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-24T14:57:19+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · the feature changes which tests CI runs and what a green ci-ok certifies

<!-- fr:journal kind=finding scope=spec id=s-r1-1-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-1 -->
### s-r1-1-resolved · finding [fixed] · resolves s-r1-1: R13 'written in whole' excludes docs/reference/cli.md; README stays a real conflict

R9-R11/R13 add a generated-block kind: hunks inside <!-- generated:NAME --> markers take ours and are regenerated; cli.md and README.md are covered by blocks, not whole-file globs, and a mirror changing a block of a non-glob file is not overreach.

<!-- fr:journal kind=finding scope=spec id=s-r1-2-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-2 -->
### s-r1-2-resolved · finding [fixed] · resolves s-r1-2: Mirror commands import the combination's fr; no command line or environment named

R11 adds a 10-minute timeout and names a missing program as a hand-back; R13 runs each mirror via `uv run --frozen`; Design §C says the .venv lives in the git-ignored scratch worktree.

<!-- fr:journal kind=finding scope=spec id=s-r1-3-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-3 -->
### s-r1-3-resolved · finding [fixed] · resolves s-r1-3: `if: !cancelled()` leaves a SKIPPED ci-ok that GitHub and fr read as passing

R2 now keeps ci-ok `if: always()`: a superseded run's red ci-ok sits on the superseded sha, which no reader or ruleset judges a PR by; ci-ok is never skipped, so a hand-cancelled head cannot read green.

<!-- fr:journal kind=finding scope=spec id=s-r1-4-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-4 -->
### s-r1-4-resolved · finding [fixed] · resolves s-r1-4: R4 claims check_wait_minutes reports a cancelled check; slot_check only reports missing ones

R4 and Design §A: slot_check counts a cancelled required check as not reported for `late`, in both branches; a Test Plan line covers it.

<!-- fr:journal kind=finding scope=spec id=s-r1-5-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-5 -->
### s-r1-5-resolved · finding [fixed] · resolves s-r1-5: R3's reader list misses ops/gate and verify_ci; a bare grep tripwire would hit stage 'cancelled'

R3 adds ops.gate._checks_green and verify_ci (cancelled = waiting, exit 75); the tripwire is scoped to check-state sets; GitLab/Gitea named out of scope.

<!-- fr:journal kind=finding scope=spec id=s-r1-6-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-6 -->
### s-r1-6-resolved · finding [fixed] · resolves s-r1-6: GraphQL statusCheckRollup.state has no CANCELLED; R3 cannot be met by editing _CI_FAIL

Design §A exempts the GraphQL aggregate rollup state explicitly, with the reason (display-only, GitHub folds CANCELLED).

<!-- fr:journal kind=finding scope=spec id=s-r1-7-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-7 -->
### s-r1-7-resolved · finding [fixed] · resolves s-r1-7: R7 cache saved on fr-queue/** is invisible to PR and main runs

R7 rewritten: no new save; hand merges and the release commit's full run still save on main, and PR restores keep the entry from expiring.

<!-- fr:journal kind=finding scope=spec id=s-r1-8-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-8 -->
### s-r1-8-resolved · finding [fixed] · resolves s-r1-8: The landed lane drops main's strict fr validate artifacts

R5/R17: validate-artifacts (strict) runs in the landed lane too.

<!-- fr:journal kind=finding scope=spec id=s-r1-9-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-9 -->
### s-r1-9-resolved · finding [fixed] · resolves s-r1-9: R5 trusts any successful ci-ok from another run, PR or foreign app included

Design §B matches a workflow run: path ci.yml, head_branch fr-queue/*, event push, conclusion success, not this run; permissions contents+actions read.

<!-- fr:journal kind=finding scope=spec id=s-r1-10-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-10 -->
### s-r1-10-resolved · finding [fixed] · resolves s-r1-10: A light-lane ci-ok is tests: ci deliver evidence; the spec is silent

New R18: a light-lane ci-ok stays valid tests: ci evidence, with the reason; verify_ci does not read the lane.

<!-- fr:journal kind=finding scope=spec id=s-r1-11-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-11 -->
### s-r1-11-resolved · finding [fixed] · resolves s-r1-11: R19's tripwire heuristic misses tests that hand REPO_ROOT to an fr reader

R20 widens the tripwire to any module resolving the checkout root (constant, Path(__file__).parents, tests/ helper) and states what it misses.

<!-- fr:journal kind=finding scope=spec id=s-r1-12-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-12 -->
### s-r1-12-resolved · finding [fixed] · resolves s-r1-12: classify and scoped-tests need full history or the light lane never fires

R15/R16 and Design §D require full history for classify and scoped-tests; a workflow-shape test pins fetch-depth: 0.

<!-- fr:journal kind=finding scope=spec id=s-r1-13-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-13 -->
### s-r1-13-resolved · finding [fixed] · resolves s-r1-13: Test Plan lacks pre-merge lines for the unit tests the Verification rows cite, R4 and R14

Test Plan gains pre-merge lines for every row, R4 and R14 included.

<!-- fr:journal kind=finding scope=spec id=s-r1-14-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-14 -->
### s-r1-14-resolved · finding [fixed] · resolves s-r1-14: Design names Worktree.run_argv/changed_paths and config plumbing that do not exist

Design §C names the new Worktree.run_argv and snapshot_tracked and threads mirrors/generated through QueuePorts, build, _combine, _merged_tree, _keeps_merge_content and _resolve.

<!-- fr:journal kind=finding scope=spec id=s-r1-15-resolved created=2026-11-24T14:57:19+00:00 state=fixed resolves=s-r1-15 -->
### s-r1-15-resolved · finding [fixed] · resolves s-r1-15: R3's stay-failing list omits STALE and status-context error

R3 lists STALE and status-context error/failure as failing.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-24T14:57:20+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  ci-cancelled-reads-pending: none
  ci-landed-skip: tester
  ci-light-lane: tester
  ci-superseded-runs: tester
  own-artifacts-tests-selected: none
  queue-regenerates-generated: none
row_kinds:
  ci-cancelled-reads-pending: none
  ci-landed-skip: live
  ci-light-lane: live
  ci-superseded-runs: live
  own-artifacts-tests-selected: none
  queue-regenerates-generated: none
run_gate: tester
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-24-ci-economy-p2 created=2026-11-24T15:00:03+00:00 -->
### phase-split-2026-11-24-ci-economy-p2 · decision · ask: asks 1, 2 and 4's CI side — ci.yml lanes, concurrency and the landed skip are one reviewable workflow change

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-24-ci-economy-p3 created=2026-11-24T15:00:05+00:00 -->
### phase-split-2026-11-24-ci-economy-p3 · decision · ask: ask 4's test-selection side — the own_artifacts marker, tripwire and fr-scope rule

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-24-ci-economy-p4 created=2026-11-24T15:00:07+00:00 -->
### phase-split-2026-11-24-ci-economy-p4 · decision · ask: ask 3 — the queue combination builder resolves generated files and stamps
