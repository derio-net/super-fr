<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-ops-gate-truth

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-27T21:50:01+00:00 input=true -->
### operator-brief · discovery · Operator brief: batch ops-gate-truth (#1617, #1621), verbatim

Batch `ops-gate-truth` of derio-net/super-fr, delivered as one PR on `feat/batch-ops-gate-truth` (Closes #1617, #1621).

## derio-net/super-fr#1617: fr ops gate: stage-4 reruns apply a stale op set — the ops workspace never picks up an op fixed on main after the merge

## Summary

`fr ops gate` runs a run's post-merge ops from its ops workspace (`chore/ops-<plan>`), and that checkout stays frozen at the commit from stage 3 ("verify-merge, rebase, ready"). When an op is fixed on the default branch **after** the merge, every stage-4 re-run keeps reading and applying the **old** op definition. Nothing says the workspace is behind. The earlier trust grant still matches, because it matches the stale content, so the gate silently re-applies an op that is already known to be wrong.

## Observed (derio-net/frank, run `2026-11-16-feat-gpu-speech-service-1006`, fr 8.3.0rc6)

1. Stage 3 rebased `chore/ops-2026-11-16--infer--speech-service` onto main at `d1988cbc`.
2. Stage 4: op `postmerge-timeslice-allocatable` applied but its check read OPEN. Root cause was in the op (it synced ArgoCD apps that ignore the ClusterPolicy `/spec`).
3. The fix merged to main as frank#1015 (`74e1ce51`), changing that op's `apply`, `summary`, `side_effects` and `undo` in the plan's `ops.yaml`.
4. Re-running `fr ops gate --run … --yes` printed `already trusted (granted <yesterday>); nothing written`. It showed the **old** summary and `side effects: (none declared)` / `undo: none declared`, applied the **old** commands, and failed the same way. The ops workspace HEAD was still `7b4e17ef` (stage 3), without `74e1ce51`.
5. Workaround: `git merge origin/main` into the ops workspace by hand. It had to be a merge, not a rebase, to keep the gate's uncommitted journal entries (`op-postmerge-*-image` done records). After that, stage 4 sees the fixed op and asks for trust again.

## Why it matters

- A post-merge op that fails is normally fixed on main, because the feature branch is gone by then. The supported repair path has no way to reach the gate.
- The failure is silent: same trust grant, same output shape, no warning that the op set on main differs from the one being applied. It reads as "the fix didn't work".
- The gate's own state (journal entries for already-DONE ops) lives uncommitted in that workspace, so the obvious manual repair (a rebase, or re-creating the workspace) can lose it. See also the autostash hazard in fr worktrees shared between sessions.

## Expected

- Before stage 4 (and on every rerun), the gate compares the plan's `ops.yaml` in the ops workspace with the default branch. When they differ it says so, naming the ops that changed, and offers to bring the workspace up to date (merge, preserving uncommitted gate records), or refuses until it is.
- A changed op set always re-triggers trust, which it does once the content actually changes, and the preview shows the new commands.
- Optionally: commit gate journal records as they are written, so the workspace is never carrying unrecorded state that a refresh could clobber.

Related: #1614 (mutating ops that do not act, found on the same run), #1220 (fr ops), #1489 (self-operating DevOps gate).


## derio-net/super-fr#1621: Gates: every gate should walk the acceptance rows it verifies (not only tester), and a plan/spec should carry a Definition of Done listing its owed gates

## Summary

A devops-gated run can pass every DevOps-gate stage while its acceptance rows stay `not-implemented`. Only the tester gate walks rows. Every other gate records Test Plan step evidence that never reaches the acceptance matrix, and nothing tells the operator.

Operator's direction for the fix:
1. **Generalize gates.** Every gate should be able to mark the rows it verifies as walked, with evidence, as the tester gate does now. Row walking should not be a tester-only capability.
2. **Definition of Done.** A plan (or its spec) should carry a Definition of Done that collects every gate the work owes, plus what each gate must produce, so the close-out is a checklist fr can verify rather than a sequence of stages that can each report "done".

## Observed (derio-net/frank, run `2026-11-16-feat-gpu-speech-service-1006`, fr 8.3.0rc6)

- The spec's `## Verification` says `strategy: live`, `gate: devops`. All six rows (`infer-speech-*`) are `verify: live`.
- `fr ops gate` stages 4–8 all completed. The operator walked all 7 Test Plan steps live, each recorded with `fr closeout outcome --ran --evidence …`. The evidence is good: STT auto-detect per language, the TTS listening verdicts, the GPU hand-over drain and restore, a 15-minute batch with alert history, the exposure checks, and a benchmark.
- Afterwards all six rows on main still read **`not-implemented`**:
  - `fr closeout outcome` stores a step's evidence but has no link from a Test Plan step to the row(s) it proves.
  - Stage 7, "tester hand-off", inspects only rows gated `tester` (`_tester_owns` in `fr/ops/gate.py`). It printed "no tester step remains", which is true and irrelevant here.
  - Stage 6, "gate pass", passed with every row unwalked.
  - Stage 8 reported "archived" while it had actually HELD the archive (manual phase 3 unticked) and filed the hold as owed work (frank#1019). The hold was correct; the message was not.
- To fix the matrix, the operator must run `fr acceptance set-status --walk` per row by hand, copying the evidence the gate had already recorded.

## Proposal

**A. Gates generalized over rows**
- Any gate (devops, tester, reviewer, security, …) can walk the rows assigned to it, recording `--walk <evidence>` the same way, and its pass refuses while an assigned row is unwalked or failed.
- The step-to-row link should be declared: a Test Plan step names the rows it proves (as `(op: <id>)` names an op), for example `(rows: infer-speech-stt-api)`. Recording the step's outcome then walks those rows with that evidence. A row nobody's step covers is reported before the gate can pass.
- The stage that currently says "no tester step remains" should report the rows the run owes **for its own gate**, not only tester rows.

**B. A Definition of Done per plan/spec**
- Derived from what the spec already declares (verification strategy and gate, per-row gates and verify strategies, ops, manual phases, follow-ups the spec defers), plus anything the plan adds. One list, for example:
  - gates owed: devops (ops pre/post-merge, Test Plan steps 1–7, rows A–F walked), tester (none);
  - manual phases owed: phase 3;
  - follow-ups owed: the spec's deferred asks filed as issues.
- `fr ops gate`, `fr gate pass` and `fr archive` read it. The close-out is done only when every DoD item is discharged; anything still owed is named. `fr run status` / `fr pickup --run` show the DoD with what is owed, so a run cannot look finished while it is not.
- This also makes the stage messages honest: "archived" only when the plan actually moved, "gate pass" only when that gate's DoD items are met.

## Related

- #1310: the tester-gate walker. Generalizing gates would let it share the row-walk machinery.
- #1189: routing batch PRs to a declared exit. A DoD is the run-level version of that exit.
- #1614 and #1617 come from the same run: ops that only print, and the stale ops workspace.

<!-- fr:journal kind=decision scope=spec id=q1-stale-ops-refresh created=2026-11-27T21:50:01+00:00 decided_by=operator -->
### q1-stale-ops-refresh · decision · Stale ops workspace: confirm, then merge

Q: what should `fr ops gate` do when the ops workspace's op set or Test Plan differs from the default branch at stages 4-7?
A (operator): name the changed ops; on confirmation commit the uncommitted gate records, merge origin/<default> (never rebase), push leased; trust re-asks on changed content; a conflict aborts and refuses with the manual steps.

<!-- fr:journal kind=decision scope=spec id=q2-dod-scope created=2026-11-27T21:50:01+00:00 decided_by=operator -->
### q2-dod-scope · decision · Definition of Done: derived, shown and used

Q: how much of #1621 part B ships here?
A (operator): a derived DoD, no authored section: `fr run dod`, included in `fr pickup --run`, read by the ops gate's messages.

<!-- fr:journal kind=decision scope=spec id=q3-walk-identity created=2026-11-27T21:50:01+00:00 decided_by=operator -->
### q3-walk-identity · decision · Operator-walked steps record harness operator, model human

Q: what harness/model does a walk written by `fr closeout outcome --ran` record?
A (operator): `harness: operator`, `model: human` by default, overridable with `--harness`/`--model`; strategy = the row's effective strategy; a row naming specific harnesses stays owed.

<!-- fr:journal kind=decision scope=spec id=q4-uncovered-rows created=2026-11-27T21:50:01+00:00 decided_by=operator -->
### q4-uncovered-rows · decision · Uncovered gated rows: caught at authoring and at the gate

Q: where is a devops/tester-gated row that no step names caught?
A (operator): `fr plan self-review` reports it; stage 5 asks the operator to walk each still-uncovered devops row directly (ran/owed).

<!-- fr:journal kind=decision scope=spec id=q5-tester-pass created=2026-11-27T21:50:01+00:00 decided_by=operator -->
### q5-tester-pass · decision · One gate_blockers function for both post-merge gates

Q: should `fr gate pass --gate tester` also refuse on unclosed tester steps/rows when a run resolves?
A (operator): yes; `gate_blockers(root, run, gate)` serves both; with no run tester behaves as today.

<!-- fr:journal kind=decision scope=spec id=q6-verification created=2026-11-27T21:50:01+00:00 decided_by=operator -->
### q6-verification · decision · Verification: strategy none, gate developer, CI-verified rows

Q: how is this run verified, and does it add rows?
A (operator): `strategy: none`, `gate: developer`, batch settle report lines; one row per requirement group verified by unit tests in CI; no Test Plan.

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · R16 puts the DoD in closeout_brief, but fr pickup --run prints devops_brief for a devops-gated run

check: codebase/consistency
target: spec
evidence: pickup_cmd.py:85-88 branches to devops_brief when devops_gated; its finished form says nothing is left (closeout.py:659-674).

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · The OpsTree merge port is implemented by OpsWorkspace in ops_gate_cmd.py, not gitseam.Worktree

check: codebase/consistency
target: spec
evidence: OpsWorkspace (ops_gate_cmd.py:45) implements OpsTree; Worktree.merge disables directory-rename detection only; abort_merge exists (gitseam.py:1310).

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · R10/R11 have no mechanism for walking or owing a row no step names

check: codebase/consistency
target: spec
evidence: R7's path is keyed to a step; set-status --walk needs harness/model/strategy (acceptance_cmd.py:592-599).

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · Two definitions of a walked row (walk_verified vs status == walked in the driver)

check: codebase/consistency
target: spec
evidence: triage/ledger.py:150 reads status == walked; walk_verified ignores a later failing walk.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · A walk the PR carries closes a devops row inside the stage, while PR-carried step outcomes do not

check: codebase/consistency
target: spec
evidence: stage 5 excludes outcomes at the pinned head (gate.py:1100-1107); rows had no such exclusion.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · Under acceptance: off, R7 refuses every --ran on a step that names rows

check: codebase/consistency
target: spec
evidence: no row exists under acceptance off, so the unknown-id refusal would always fire.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · R13 has no severity and misses test_plan: off, cross-repo specs and the ops promotion

check: codebase/consistency
target: spec
evidence: plan_review/checks.py severities; cross-repo exemption at 266/421; exit_for_spec lacks _promote.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · DoD discharged items cannot come from gate_blockers; owed items counted twice

check: codebase/consistency
target: spec
evidence: devops_blockers returns only holding lines (holds.py:79-101); owed steps and archive-written manual phases are also owed entries.

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · R17 still says complete over a held archive and leaves the nothing-ran line unspecified

check: codebase/consistency
target: spec
evidence: the live hold was a manual phase, a group outside devops; gate.py:1385 nothing-ran line.

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · A changed op stage 4 already closed stays closed after the refresh

check: codebase/consistency
target: spec
evidence: recorded_close does not tie evidence to op content (evidence.py:83-95); apply_phase skips closed ops; a refresh at 5-7 never returns to 4.

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · R7's walk identity is wrong for probe-recorded steps and does not cover --spec

check: codebase/consistency
target: spec
evidence: _probe_step records ran with no question (gate.py:1074-1077); closeout outcome has a --spec form.

<!-- fr:journal kind=finding scope=spec id=s-r12 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r12 · finding [open] (reviewer: in scope) · A row named only by a step recorded n/a is held and never asked about

check: codebase/consistency
target: spec
evidence: R7 writes no walk on n/a; R10 asked only about rows no step names.

<!-- fr:journal kind=finding scope=spec id=s-r13 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r13 · finding [open] (reviewer: in scope) · The R7 walk path does not print the issue-close commands set-status --walk prints

check: codebase/consistency
target: spec
evidence: acceptance_cmd.py:623-641 _print_close_commands; walks.py issues_now_closable.

<!-- fr:journal kind=finding scope=spec id=s-r14 created=2026-11-27T22:01:12+00:00 state=open review_scope=in -->
### s-r14 · finding [open] (reviewer: in scope) · No run_app command is registered outside run_cmd.py; name where dod_cmd is imported

check: codebase/consistency
target: spec
evidence: every @run_app.command lives in run_cmd.py (budget 8895); cli.py:55 imports run_app.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-27T22:01:12+00:00 -->
### spec-review · review · independent spec review: 14 findings, all in scope, all fixed in the spec

Reviewer fr-spec-reviewer checked q1-q6 against the requirements (no contradiction) and every named file/helper with path:line. 14 findings (s-r1..s-r14), all in scope; each fixed in the spec, which now has R1-R20; row origins re-pointed by amendment.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-27T22:01:12+00:00 lens=security step=spec-review -->
### lens-security-1 · lens · the refresh merges and re-trusts default-branch op content, and row walks inside the stage must exclude PR-carried walks

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-27T22:01:12+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · new refusal paths (drift on an unreadable side, merge conflict/abort, fr run dod exit codes) must fail closed, never read as nothing owed

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-27T22:01:12+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · fake-port tests of stages 4-8 must cover reruns, declines, conflicts, reopened ops and PR-carried exclusions, not only the happy path

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: R16 puts the DoD in closeout_brief, but fr pickup --run prints devops_brief for a devops-gated run

R19 now names closeout_brief and both forms of devops_brief; the finished form says complete only when the whole DoD is discharged.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: The OpsTree merge port is implemented by OpsWorkspace in ops_gate_cmd.py, not gitseam.Worktree

Design §A and the shape name OpsWorkspace.merge_commit (fetch origin, Worktree.merge, commit or abort_merge) in commands/ops_gate_cmd.py; the wording says directory-rename detection.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: R10/R11 have no mechanism for walking or owing a row no step names

R13 and Design §B name the exact `fr acceptance set-status` invocations for ran and owed (harness operator, model human, effective strategy, --feature); R14 prints the same command.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: Two definitions of a walked row (walk_verified vs status == walked in the driver)

R10 defines fr.acceptance.walks.row_walked (status walked and latest walk passed) as the one rule; the driver's ledger and gate_items both read it.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: A walk the PR carries closes a devops row inside the stage, while PR-carried step outcomes do not

R12 plus gate_items' exclude_walks: inside the DevOps stage walks the pinned PR head carries never close a row.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: Under acceptance: off, R7 refuses every --ran on a step that names rows

R8: under acceptance: off the pointer is parsed and ignored; nothing is walked, asked, counted or reported.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: R13 has no severity and misses test_plan: off, cross-repo specs and the ops promotion

R16: severity warn; nothing under test_plan/gates/acceptance off or for a cross-repo spec; effective gates include the plan-ops devops promotion.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: DoD discharged items cannot come from gate_blockers; owed items counted twice

R10 adds item-level gate_items (discharged or not) that gate_blockers and the DoD both derive from; R17 drops owed entries another group already reports.

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: R17 still says complete over a held archive and leaves the nothing-ran line unspecified

R20: complete only when every DoD item, from every group, is discharged, on both the ran-stages and the nothing-ran paths.

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: A changed op stage 4 already closed stays closed after the refresh

R6 and Design §A: changed/added ops are reopened host-side (old closures ignored, entry ids before the refresh excluded); a refresh at stage 5-7 forgets stages >= 4 so the run returns to stage 4.

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r11 -->
### s-r11-resolved · finding [fixed] · resolves s-r11: R7's walk identity is wrong for probe-recorded steps and does not cover --spec

R9: a probe-recorded step walks with harness fr-ops-probe, model op:<id>; the feature is the slug of the spec, the run's or --spec's.

<!-- fr:journal kind=finding scope=spec id=s-r12-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r12 -->
### s-r12-resolved · finding [fixed] · resolves s-r12: A row named only by a step recorded n/a is held and never asked about

R13 asks about each unwalked devops row that no ran step names, which covers n/a-only rows.

<!-- fr:journal kind=finding scope=spec id=s-r13-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r13 -->
### s-r13-resolved · finding [fixed] · resolves s-r13: The R7 walk path does not print the issue-close commands set-status --walk prints

R9 prints the close commands; Design §B moves the printer into fr.acceptance.walks so both writers share it.

<!-- fr:journal kind=finding scope=spec id=s-r14-resolved created=2026-11-27T22:01:12+00:00 state=fixed resolves=s-r14 -->
### s-r14-resolved · finding [fixed] · resolves s-r14: No run_app command is registered outside run_cmd.py; name where dod_cmd is imported

R18 and the shape: cli.py imports commands.dod_cmd after run_app, which registers `fr run dod`.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T22:01:13+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  closeout-outcome-walks-the-rows-a-step-names: none
  gate-pass-refuses-unwalked-gated-rows: none
  ops-gate-refreshes-a-stale-ops-workspace: none
  ops-gate-reports-a-held-archive: none
  ops-gate-walks-and-reports-its-own-rows: none
  run-definition-of-done: none
  self-review-flags-uncovered-gated-rows: none
row_kinds:
  closeout-outcome-walks-the-rows-a-step-names: none
  gate-pass-refuses-unwalked-gated-rows: none
  ops-gate-refreshes-a-stale-ops-workspace: none
  ops-gate-reports-a-held-archive: none
  ops-gate-walks-and-reports-its-own-rows: none
  run-definition-of-done: none
  self-review-flags-uncovered-gated-rows: none
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-ops-gate-truth-p2 created=2026-11-27T22:05:02+00:00 -->
### phase-split-2026-11-27-ops-gate-truth-p2 · decision · ask: gate row walks (#1621 part A, R7-R16)

Phase 2 serves its own ask: the step-to-row link and the row term of every post-merge gate. It is independently reviewable from the refresh (phase 1) and reads phase 1's stage hooks.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-ops-gate-truth-p3 created=2026-11-27T22:05:04+00:00 -->
### phase-split-2026-11-27-ops-gate-truth-p3 · decision · ask: derived Definition of Done (#1621 part B, R17-R20)

Phase 3 serves its own ask: the derived DoD, fr run dod, the briefs and the final line. It derives from phase 2's gate_items.
