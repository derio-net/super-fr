# Ops gate truth: no stale ops workspace; every gate walks the rows it verifies

Batch `ops-gate-truth`: derio-net/super-fr#1617 and derio-net/super-fr#1621, one PR.

## Background

Both issues come from one live DevOps-gated run in derio-net/frank (fr 8.3.0rc6).

**#1617.** `fr ops gate` runs a run's post-merge ops from its ops workspace
(`chore/ops-<plan>`). Stage 3 is the only place that workspace moves: `stage_3` calls
`tree.rebase_onto(origin/<default>, …)` (`packages/fr/src/fr/ops/gate.py`, `stage_3`), and
`STAGES` marks stage 4 done only by `_recorded(4)`. A stage 4 that failed therefore reruns
against the stage-3 tree forever. In the live run the failing op was fixed on the default
branch after the merge, and every rerun applied the old definition. The trust grant still
matched, because it matched the old content, so nothing warned. The op evidence `apply_phase`
writes stays uncommitted in the workspace until `Gate.finish` commits `docs/`, so a hand
rebase, or re-creating the workspace, can lose it. The operator's workaround was a hand
`git merge origin/main`.

**#1621.** In the same run every stage of the gate completed while all six acceptance rows
stayed `not-implemented`:

- `fr closeout outcome` (`commands/closeout_cmd.py`) stores a Test Plan step's evidence in
  the spec journal, but nothing links a step to the rows it proves.
- `fr gate pass --gate devops` refuses only on `fr.ops.holds.devops_blockers`, which counts
  ops and devops steps, never rows.
- Stage 7 inspects only rows gated `tester` (`_tester_owns`), and printed "no tester step
  remains".
- Stage 8 printed "archived" while `fr archive` had held the plan (an unticked manual phase).
  `fr archive` exits 0 on a hold and leaves the plan directory in place, and `stage_8` does
  not check it again.

The rows the devops gate owns are already computable. A row whose strategy is the run's
strategy inherits the run's gate (`fr.verification.rows.SpecVerification.gate`), so
`run_exit(...).gated_rows` and `.row_gates` name them. What is missing is the step-to-row
link, a row term in the gate's blockers, and an honest report of what is still owed.

## Requirements

R1. Before stages 4, 5, 6 and 7 of `fr ops gate` act, every time they run (reruns
included), the gate fetches the default branch and compares two things between the ops
workspace and `origin/<default>`: the op set the run's plan loads (`fr.ops.load.load_ops`,
op by op on its full definition) and the run's Test Plan steps. When both are equal the stage
proceeds and says nothing.

R2. When either differs, the gate names each op added, removed or changed (by id) and says
whether the Test Plan changed. It then asks the operator to confirm bringing the workspace up
to date. That confirmation is asked whether or not `--yes` was given. A declined confirmation
fails the stage, and nothing changes.

R3. On confirmation the gate first commits the workspace's uncommitted gate records under
`docs/` on the ops branch. It then merges `origin/<default>` into the ops branch with a merge
commit (never a rebase, so the pushed ops branch moves forward only) and pushes it, leased on
the sha fr last pushed. A merge that conflicts is aborted, which leaves the workspace at the
records commit. The stage then fails, naming the conflicted paths and the commands that merge
by hand.

R4. After a refresh the stage checks trust again on the merged content before any probe or
apply runs. An op set that changed therefore asks for trust again, and its preview shows the
new commands.

R5. When the run's plan directory does not exist on `origin/<default>`, the stage fails and
names the missing directory. It does not refresh.

R6. A Test Plan step may name the acceptance rows it proves with a pointer
`(rows: <id>[, <id>…])`. The pointer comes after the optional gate tag and the optional
`(op: <id>)` pointer, and is followed by whitespace. fr parses the pointer into the step's
`rows` and removes it from the step's text. Anywhere else the same characters stay text.

R7. `fr closeout outcome --ran --evidence <e>` on a step that names rows records, in the same
commit as the outcome, a passing walk on each named row. The walk's strategy is the row's
effective strategy. Its harness is `operator` and its model is `human`, unless `--harness` or
`--model` is given. Its evidence is `Test Plan step <n>: <e>`. A row the walk makes
walk-verified moves to `walked`. Any other row keeps its status, and the command names the
harnesses that row still owes. A row an earlier feature merged changes by amendment into the
run's feature fragment. `--na` and `--owed` write no walk. `--supersede --ran` adds another
walk. The command refuses, and writes nothing, when a named id is not a row that cites the
run's spec, or when the row's effective strategy is `none`.

R8. `fr.ops.holds.gate_blockers(repo_root, run, gate)`, for `gate` one of `tester` and
`devops`, returns one line for each thing that holds that gate. These are: each plan op not
closed by recorded evidence (devops only, as today); each Test Plan step whose effective gate
is `gate` and that has no `ran` or `n/a` outcome; and each row whose effective gate is `gate`
and that is not walk-verified in this checkout. A row's line says why: no walk, a failing
latest walk, or the harnesses still owed. `devops_blockers` stays, and equals
`gate_blockers(..., "devops")`.

R9. `fr gate pass --gate <g>` refuses while `gate_blockers` is not empty for the run it
resolves, for both post-merge gates. The run is `--run <id>`, else the run whose branch is the
PR's head ref, as `--gate devops` resolves it today. When no run resolves, `--gate tester`
behaves as it does today.

R10. Stage 5 also asks the operator about each devops-gated row that no devops step names
and that is not walk-verified, after the steps: `ran <evidence>` or `owed <why>`. `ran`
records a walk as R7 does (evidence: the answer). `owed` sets the row's status to `walk-owed`,
with the reason in its note.

R11. Stage 6 lists, before the pass, what the devops gate still owes by `gate_blockers`.
When the pass is refused it prints, for each unwalked row, the command that records its walk
in the ops workspace. Stage 7 reports the rows and steps the tester gate owes by the same
function.

R12. Stage 8 reports `archived` only when the plan directory moved. When `fr archive` held
the plan, stage 8 reports `archive held` with each held reason `fr archive` printed, and its
audit record says the same. The stage still publishes the housekeeping PR and completes.

R13. `fr plan self-review` reports a finding for each row that cites the plan's spec, whose
effective gate is `devops` or `tester`, and that no Test Plan step with the same effective
gate names with `(rows: …)`. It also reports one for each `(rows: …)` id that names no row
citing the spec. Under `acceptance: off` or `gates: off` it reports neither.

R14. `fr.run.dod.definition_of_done(repo_root, run)` derives a run's Definition of Done from
what the spec, plan and run already declare. Nothing is authored, and it is no artifact kind.
For each post-merge gate in the run's effective gates it holds three groups: ops (devops
only), Test Plan steps and rows. It also holds the plan's unticked `[manual]` phases and the
open `owed` entries of the run's spec and plan journals. Each item is either discharged or
owed, with a one-line reason.

R15. `fr run dod <run-id> [--json]` prints the Definition of Done. It changes nothing. It
exits 0 when every item is discharged, 1 when an item is owed, and 2 when the run or its
inputs cannot be read. It is registered from a module of its own, never in
`commands/run_cmd.py`.

R16. The close-out brief that `fr pickup --run <id>` prints includes the Definition of Done.

R17. When `fr ops gate` has run every stage, it says `the DevOps stage is complete` only when
the Definition of Done's devops items are all discharged. Otherwise it says that every stage
ran and lists each item that is still owed, from every group.

## Design shape

```text
packages/fr/src/fr/
  spec.py                    ~ Step gains `rows: tuple[str, ...]`; `(rows: …)` pointer   R6
  ops/
    refresh.py               + drift(workspace, default tree) → ops added/removed/changed,
                               test-plan changed; refresh(gate): confirm → commit records
                               → merge origin/<default> → leased push → trust     R1–R5
    gate.py                  ~ stages 4–7 call refresh first                      R1
                             ~ stage 5 asks uncovered devops rows (ran|owed)      R10
                             ~ stage 6/7 list gate_blockers; stage 6 recovery     R11
                               prints row-walk commands
                             ~ stage 8: plan dir still there → "archive held"     R12
                             ~ run(): final line reads the DoD                    R17
    holds.py                 ~ gate_blockers(root, run, gate); devops_blockers =  R8
                               gate_blockers(…, "devops"); rows term
  commands/
    closeout_cmd.py          ~ --ran on a step with rows → walk items in the same  R7
                               record; --harness/--model (default operator/human)
    gate_cmd.py              ~ pass refuses on gate_blockers for tester too        R9
    dod_cmd.py               + `fr run dod <run-id> [--json]`, attached to run_app R15
  run/
    dod.py                   + definition_of_done(root, run) → DoD                 R14
    closeout.py              ~ closeout_brief appends the DoD                      R16
  plan_review/checks.py      ~ gated-row coverage + unknown (rows:) ids            R13
  triage/gitseam.py          ~ Worktree: merge commit / abort for the refresh      R3
```

```text
stage N in 4..7 ──► drift?(ops, test plan) ── equal ──► act
                         │ differs
                         ▼
               name ops changed ─► confirm? ── no ──► fail, nothing changed
                         │ yes
                         ▼
        commit docs/ records ─► merge origin/<default> ── conflict ──► abort, fail, name paths
                         │ clean
                         ▼
               leased push ─► trust (re-asks on change) ─► act
```

## Design

### A. The stale ops workspace (R1–R5)

`fr/ops/refresh.py` holds two functions.

- `drift(tree, default_root, plan_rel, spec_rel) -> Drift`. It loads the ops on both sides
  with `load_ops`, keys them by id and compares each `LoadedOp.op` (the frozen model, so
  equality is a comparison of the whole definition). It also compares `test_plan_steps` of
  the run's spec on both sides. The default side is a scratch tree from
  `GateHost.materialise(origin/<default>, …)` (the same paths `_head_paths` names), removed
  afterwards, as `_refuse_an_ops_gap` does. A plan directory that is absent on the default
  side raises `StageFailed` (R5).
- `refresh(gate, tree)`. Under `drift`'s answer it confirms (`gate.prompt.confirm`, always
  asked), then `tree.commit_paths(["docs"], "chore(ops): <slug> gate records before refresh")`,
  then `tree.merge_commit(origin/<default>, message)`. That is a new `OpsTree` port method,
  implemented on `gitseam.Worktree` over its existing `merge` (no-commit, rerere off,
  rename detection off) plus a commit or `merge --abort`. The function finishes with
  `gate.publish(tree)` (leased) and `gate.trust(tree)`.

Stages 4, 5, 6 and 7 call `refresh` first. Rows are left out of the comparison on purpose:
the ops branch writes row walks (R7, R10) that the default branch does not hold yet, so a
row comparison would always differ.

### B. Rows a gate verifies (R6–R13)

The pointer grammar sits beside `_POINTER_RE` in `spec.py`: `(rows: a, b)`. Ids use the same
character class as op ids, split on commas, and blanks are refused. Older fr reads the
pointer as part of the step's text, which is harmless.

`closeout outcome` builds one `StepRecord`: the existing outcome `JournalItem`, plus one
`AcceptanceItem(id, status, notes, walk=Walk(...))` for each named row. It goes through
`engine.apply_record` with `RecordTarget(feature=<run's spec slug>)`, so a merged row is
amended and one commit holds both. The status becomes `walked` when
`fr.acceptance.walks.walk_verified` holds after the walk. Otherwise the existing status stays,
and the note says which harnesses are still owed.

`gate_blockers` extends `devops_blockers` with a rows term, read from `run_exit(...)`:
`gated_rows` filtered by `row_gates[id] == gate`, each judged with `walk_verified` and its
latest walk. Stage 6 and stage 7 both read it. `_tester_owns` is replaced by it (the
declared-run-gate check stays in stage 7).

`fr plan self-review` gains `_gated_row_coverage_issues`, which uses `steps_gated` with each
gate on the plan's spec steps and the effective exit's rows.

### C. Definition of Done (R14–R17)

`fr/run/dod.py` returns
`DefinitionOfDone(groups: tuple[DodGroup, ...])`. A group is
`(name, items: tuple[DodItem(what, discharged: bool, why)])`. The groups are
`gate:devops` / `gate:tester` (the ops, steps and rows of `gate_blockers`, discharged ones
included), `manual phases` (the plan's unticked `[manual]` phases) and `owed` (open `owed`
entries in the run's spec and plan journals). It runs no probe: like `gate_blockers`, it
states what was recorded. `commands/dod_cmd.py` renders it as text or JSON.
`run/closeout.py`'s `closeout_brief` appends the text form. `ops/gate.py`'s `run` builds it
on the ops workspace for its final line.

## Verification

strategy: none
gate: developer
settle.conflicts: report — batch ops-gate-truth: the wave driver owns this PR's mergeability
settle.ci: report — batch ops-gate-truth: the wave driver owns this PR's CI

- ops-gate-refreshes-a-stale-ops-workspace: none — unit tests with fake ports drive stages 4–7 against a drifted default branch, in this PR's CI
- closeout-outcome-walks-the-rows-a-step-names: none — unit tests of the pointer grammar and of `fr closeout outcome` against a fixture repo, in CI
- gate-pass-refuses-unwalked-gated-rows: none — unit tests of `gate_blockers` and `fr gate pass` for both gates, in CI
- ops-gate-walks-and-reports-its-own-rows: none — unit tests of stages 5–7 with fake ports, in CI
- ops-gate-reports-a-held-archive: none — a unit test of stage 8 with a held archive, in CI
- self-review-flags-uncovered-gated-rows: none — unit tests of the self-review check, in CI
- run-definition-of-done: none — unit tests of `definition_of_done`, `fr run dod` and the pickup brief, in CI

## Out of scope

- A tester-gate walker (#1310). It can reuse `gate_blockers` and the R7 walk path.
- An authored `## Definition of Done` section. The operator chose a derived DoD only.
- Committing each gate record as it is written (#1617's optional point). R3 commits them
  before a refresh, which removes the hazard the issue names.
