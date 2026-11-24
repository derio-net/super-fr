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
