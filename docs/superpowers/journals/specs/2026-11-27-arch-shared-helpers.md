<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-arch-shared-helpers

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-27T09:02:49+00:00 input=true -->
### operator-brief · discovery · Operator brief: batch arch-shared-helpers (#1512, #1513, #1514, #1523)

/fr-goal batch arch-shared-helpers

Batch `arch-shared-helpers` of derio-net/super-fr: 4 issues, delivered as ONE pull request.
Batch title: #1318: shared duplicate-key YAML detector, record placement and hermetic-git fixtures, small duplicate readers
- super-fr#1512 Share the duplicate-key YAML detector between artifacts, harness and lenses (R04)
- super-fr#1513 Share the record-file placement helper across the record migration tests (R05)
- super-fr#1514 Share the hermetic-git test fixture across gate-backfill and merge-evidence tests (R06)
- super-fr#1523 Small duplicate readers left by the #1318 review: gate help text, _pr_time, _created_since, naive-as-UTC parsers
Why together: #1318 cheap shared-helper slices; no giant module touched.

Delivery rules: branch `feat/batch-arch-shared-helpers`; open a draft PR as soon as the spec is
committed, its body carrying one `Closes derio-net/super-fr#<n>` line per member; batches
`closeout-state` and `queue-followups` of this wave also change
packages/fr/src/fr/commands/triage_batch_cmd.py (whichever lands second resolves the queue's
conflict hand-back); no member issue as a phase `tracking_issue`; the wave driver owns
mergeability and CI (no `fr pr settle` loop); never add `approved-fr`.
(Issue bodies as on the tracker; the batch block was marked untrusted.)

<!-- fr:journal kind=decision scope=spec id=q-shape created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-shape · decision · Shape: fr-goal-light, one agentic phase

Operator chose fr-goal-light with a single phase for all four asks (recommended): small mechanical extractions, no behaviour change.

<!-- fr:journal kind=decision scope=spec id=q-yaml-home created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-yaml-home · decision · Strict YAML loader lives in fr.yamlio

Operator chose fr.yamlio (recommended): it imports only yaml and is already the one place that picks a loader. Stays on pure-Python SafeLoader; #1286 keeps the libyaml switch.

<!-- fr:journal kind=decision scope=spec id=q-utc-home created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-utc-home · decision · parse_as_utc lives in new fr/utc_time.py

Operator chose a new top-level standard-library-only module (recommended), so debt and usage never import fr.triage and parse_aware's module stays single-contract.

<!-- fr:journal kind=decision scope=spec id=q-verify created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-verify · decision · Verification: strategy none, gate developer

Operator chose no install walk (recommended): the CI unit suite and the new AST guards prove a no-behaviour-change refactor; nothing to do after merge.

<!-- fr:journal kind=decision scope=spec id=q-rows created=2026-11-27T09:02:49+00:00 decided_by=operator -->
### q-rows · decision · No new acceptance rows

Operator chose no new rows (recommended): no product behaviour changes; the guards are tests, not business claims.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-arch-shared-helpers-p1 created=2026-11-27T09:04:33+00:00 -->
### phase-split-2026-11-27-arch-shared-helpers-p1 · decision · review-size: the whole batch (R1-R9) is one reviewable diff; it has no acceptance rows by operator decision q-rows, so the phase serves the requirements directly

<!-- fr:journal kind=finding scope=spec id=spr-r1 created=2026-11-27T09:11:52+00:00 state=open review_scope=in -->
### spr-r1 · finding [open] (reviewer: in scope) · R5 misses test_merge_evidence.stub_fetch, whose own setenv of both variables trips R5's guard

target: spec (and plan). tests/unit/test_merge_evidence.py:36-48 stub_fetch sets GIT_CONFIG_GLOBAL and
GIT_CONFIG_NOSYSTEM itself and is imported by six archive/status test modules; the R5 guard (no setenv of
either variable) would fail on test_merge_evidence.py. Scope in: this change's own guard fails on a module it edits.

<!-- fr:journal kind=finding scope=spec id=spr-r2 created=2026-11-27T09:11:52+00:00 state=open review_scope=in -->
### spr-r2 · finding [open] (reviewer: in scope) · R8 claims one naive-as-UTC reader, but liveness._parse_instant and claims._created hold the same contract

target: spec. packages/fr/src/fr/run/liveness.py:307-312 and packages/fr/src/fr/triage/claims.py:174-182 read a
naive time as UTC and a bad value as None; R8's single-owner claim is contradicted after the change.

<!-- fr:journal kind=finding scope=spec id=spr-r3 created=2026-11-27T09:11:52+00:00 state=open review_scope=in -->
### spr-r3 · finding [open] (reviewer: in scope) · Design shape and Design leave out files the change touches; R6/R8 tests have no named home

target: spec. The shape omits test_init_scaffold.py, the R9 prose files, the change fragment and stamped pages;
the Design names no test module for the R6 help test or the parse_as_utc tests.

<!-- fr:journal kind=finding scope=spec id=spr-r4 created=2026-11-27T09:11:52+00:00 state=open review_scope=in -->
### spr-r4 · finding [open] (reviewer: in scope) · Phase title cut to 'Shared helpers from the' because '#1318' was read as a YAML comment

target: plan. docs/superpowers/plans/2026-11-27-arch-shared-helpers/01.yaml:4.

<!-- fr:journal kind=finding scope=spec id=spr-r5 created=2026-11-27T09:11:52+00:00 state=open review_scope=in -->
### spr-r5 · finding [open] (reviewer: in scope) · Task 5 is not red/green/refactor and gives no reason

target: plan. 01.yaml Task 5 (prose, sync, fragment, stamps, checks) has no TDD shape and no stated reason.

<!-- fr:journal kind=finding scope=spec id=spr-r6 created=2026-11-27T09:11:52+00:00 state=open review_scope=in -->
### spr-r6 · finding [open] (reviewer: in scope) · P1.T2.S1 compares rendered --help output to a literal, and rich wraps that output

target: plan. journal_cmd.py:218-223's help renders through typer/rich at terminal width; compare the click
parameter's .help string instead.

<!-- fr:journal kind=review scope=spec id=spec-plan-review-1 created=2026-11-27T09:11:52+00:00 -->
### spec-plan-review-1 · review · Spec+plan review: 6 findings (spr-r1..spr-r6), all in scope

Independent fr-spec-reviewer checked the spec against operator decisions q-shape, q-yaml-home, q-utc-home,
q-verify, q-rows and phase-split-p1 (all honoured) and against the code (file:line for every named helper).
It found no behaviour change in the detector move, the parse_aware substitutions or parse_as_utc; the R3 and R4
guards have no false positives. Findings: spr-r1, spr-r2, spr-r3 (spec); spr-r4, spr-r5, spr-r6 (plan).

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-27T09:11:52+00:00 lens=tests step=spec-plan-review -->
### lens-tests-1 · lens · Fixtures and record helpers move across 17+ test modules and new AST guards are added: check activation and payloads are unchanged

<!-- fr:journal kind=finding scope=spec id=spr-r1-resolved created=2026-11-27T09:11:52+00:00 state=fixed resolves=spr-r1 -->
### spr-r1-resolved · finding [fixed] · resolves spr-r1: R5 misses test_merge_evidence.stub_fetch, whose own setenv of both variables trips R5's guard

Spec Background, R5 and Design now say stub_fetch calls apply_hermetic_git(monkeypatch), keeping its signature; plan P1.T4.S2 names the step.

<!-- fr:journal kind=finding scope=spec id=spr-r2-resolved created=2026-11-27T09:11:52+00:00 state=fixed resolves=spr-r2 -->
### spr-r2-resolved · finding [fixed] · resolves spr-r2: R8 claims one naive-as-UTC reader, but liveness._parse_instant and claims._created hold the same contract

Folded both readers in: R8 widened to parse_as_utc(value: object) with non-string giving None; Background, Design, shape and plan P1.T2.S2/S3 name liveness._parse_instant and claims._created; plan files list adds both modules.

<!-- fr:journal kind=finding scope=spec id=spr-r3-resolved created=2026-11-27T09:11:52+00:00 state=fixed resolves=spr-r3 -->
### spr-r3-resolved · finding [fixed] · resolves spr-r3: Design shape and Design leave out files the change touches; R6/R8 tests have no named home

Design shape now lists test_init_scaffold.py, test_opencode_agent_mirror.py, the rule and its mirror, sync-opencode.py, the fragment and the stamped pages; tests/unit/test_journal_gate_help.py and tests/unit/test_utc_time.py are named in Design and plan.

<!-- fr:journal kind=finding scope=spec id=spr-r4-resolved created=2026-11-27T09:11:52+00:00 state=fixed resolves=spr-r4 -->
### spr-r4-resolved · finding [fixed] · resolves spr-r4: Phase title cut to 'Shared helpers from the' because '#1318' was read as a YAML comment

Phase title quoted in 01.yaml.

<!-- fr:journal kind=finding scope=spec id=spr-r5-resolved created=2026-11-27T09:11:52+00:00 state=fixed resolves=spr-r5 -->
### spr-r5-resolved · finding [fixed] · resolves spr-r5: Task 5 is not red/green/refactor and gives no reason

Task 5's title now states why it is not TDD-shaped: prose, mirrors and stamps only; the mirror tripwires and fr docs check are its tests.

<!-- fr:journal kind=finding scope=spec id=spr-r6-resolved created=2026-11-27T09:11:52+00:00 state=fixed resolves=spr-r6 -->
### spr-r6-resolved · finding [fixed] · resolves spr-r6: P1.T2.S1 compares rendered --help output to a literal, and rich wraps that output

R6, Design and P1.T2.S1 now read the --gate click parameter's .help from typer.main.get_command(app), never the rendered --help.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T09:11:54+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates: {}
row_kinds: {}
run_gate: developer
run_kind: none
```
