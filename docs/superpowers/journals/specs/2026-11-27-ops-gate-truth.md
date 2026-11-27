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
