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

R6. An op that a refresh found changed or added is reopened, until stage 4 completes again.
Its closure recorded before the refresh no longer closes it: only its live status, or
evidence recorded after the refresh, does. Plan-journal entries the merge brought in from
the default branch never count as evidence recorded after it. When the refresh ran at stage
5, 6 or 7 and reopened an op, the host state forgets stages 4 and later. When it ran at stage
6 or 7 and only the Test Plan changed, it forgets stages 5 and later. Either way the same run
goes back to the first forgotten stage before anything later runs. After such a restart, a
`gate:devops-passed` label already on the PR counts only once the devops blockers, read on the
refreshed workspace, are empty. When they are not, stage 6 fails, naming them, and never
removes the label itself. A merge that was a no-op (the pinned commit already in the ops
branch) but leaves the comparison still differing fails the stage, naming the ops: it never
merges, reopens or restarts again.

R7. A Test Plan step may name the acceptance rows it proves with a pointer
`(rows: <id>[, <id>…])`. The pointer comes after the optional gate tag and the optional
`(op: <id>)` pointer, and is followed by whitespace. fr parses the pointer into the step's
`rows` and removes it from the step's text. Anywhere else the same characters stay text.

R8. Under `acceptance: off` a `(rows: …)` pointer is parsed and ignored: no walk is written
(R9), asked for (R13) or counted (R10), and self-review reports nothing (R16).

R9. `fr closeout outcome --ran --evidence <e>` on a step that names rows records, in the same
commit as the outcome, a passing walk on each named row. The walk's strategy is the row's
effective strategy. Its harness is `operator` and its model is `human`, unless `--harness` or
`--model` is given. Stage 5 records the step of an op whose probe passed with harness
`fr-ops-probe` and model `op:<id>`, because nobody walked it. The walk's evidence is
`Test Plan step <n>: <e>`. A row whose walk makes it walk-verified moves to `walked`. Any other
row keeps its status, and the command names the harnesses that row still owes. A row changes
by amendment into the feature fragment of the spec. The spec is the run's, or the one
`--spec` names, and its slug is the feature. When a walk frees an issue, the command prints
that issue's close commands, as `fr acceptance set-status --walk` does. `--na` and `--owed`
write no walk. `--supersede --ran` adds another walk. The command refuses, and writes nothing,
when a named id is not a row that cites the spec, or when the row's effective strategy is
`none`.

R10. `fr.acceptance.walks.row_walked(row)` is the one rule for a walked row: its status is
`walked` and its latest walk (by `at`) passed. The driver's rows-walked pass
(`fr.triage.ledger`) reads it, and so do the gate's blockers. `fr.ops.holds.gate_items(repo_root,
run, gate, *, exclude_walks=…)`, for `gate` one of `tester` and `devops`, returns one item for
each thing that gate owns, discharged or not, each with a one-line reason:

- each plan op, closed or not by recorded evidence (devops only, as today);
- each Test Plan step whose effective gate is `gate`, with or without a `ran` or `n/a`
  outcome;
- each row whose effective gate is `gate`, walked or not by `row_walked`. A row's reason says
  why: no walk, a failing latest walk, or the harnesses still owed.

A walk named in `exclude_walks` (the DevOps stage passes the walks the pinned PR head carries)
does not count. `gate_blockers` returns the lines of the owed items. `devops_blockers` stays,
and equals `gate_blockers(..., "devops")`.

R11. `fr gate pass --gate <g>` refuses while `gate_blockers` is not empty for the run it
resolves, for both post-merge gates. The run is `--run <id>`, else the run whose branch is the
PR's head ref, as `--gate devops` resolves it today. When no run resolves, `--gate tester`
behaves as it does today.

R12. Inside the DevOps stage, a row walk the pinned PR head already carries never closes a
row: the stage judges rows with those walks excluded, as it already excludes the step
outcomes the head carries. The head's walks are read from every fragment holding a row the
stage judges. With walks excluded, a row counts as walked only when every harness it owes has
a latest passing walk among the walks that remain: a row status the head wrote never counts,
and the harnesses a stage-written walk still owes are counted over the remaining walks.

R13. Stage 5 also asks the operator about each devops-gated row that is not walked (R10, R12)
and that no walk this stage wrote has discharged, after the steps. This covers a row no step
names and a row whose naming steps were recorded `n/a`. The answer is `ran <evidence>` or
`owed <why>`. `ran` records the walk with `fr acceptance set-status --walk` (harness
`operator`, model `human`, the row's effective strategy, `--feature` the spec slug).
`owed` sets the row's status to `walk-owed` through the same command, with the reason in its
note.

R14. Stage 6 lists, before the pass, what the devops gate still owes by `gate_blockers`,
with the PR head's walks excluded (R12), and fails the stage without running `fr gate pass`
while any remain. It prints, for each unwalked row, the R13 `set-status --walk` command to
run in the ops workspace, one per harness the row still owes. An unreadable fragment,
section or setting fails the stage with its message. Stage 7's tester pass names the run
with `--run`, as stage 6's does. Stage 7 reports the rows and steps the tester gate owes
by the same function.

R15. Stage 8 reports `archived` only when the plan directory moved. When `fr archive` held
the plan, stage 8 reports `archive held` with each held reason `fr archive` printed, and its
audit record says the same. The stage still publishes the housekeeping PR and completes.

R16. `fr plan self-review` warns (severity `warn`, never `error`) about each row that cites
the plan's spec, whose effective gate is `devops` or `tester`, and that no Test Plan step
with the same effective gate names with `(rows: …)`. It also warns about each `(rows: …)` id
that names no row citing the spec. Effective gates include the `devops` that a plan with ops
adds (`fr.verification.exit`'s promotion). It reports nothing under `acceptance: off`,
`test_plan: off` or `gates: off`, or for a cross-repo spec.

R17. `fr.run.dod.definition_of_done(repo_root, run)` derives a run's Definition of Done from
what the spec, plan and run already declare. Nothing is authored, and it is no artifact kind.
For each post-merge gate in the run's effective gates it holds that gate's `gate_items`. It
also holds the plan's unticked `[manual]` phases and the open `owed` entries of the run's spec
and plan journals. An `owed` entry already reported in another group is left out of the `owed`
group: a Test Plan step's outcome, and a manual phase that `fr archive` wrote back. Each item
is either discharged or owed, with a one-line reason.

R18. `fr run dod <run-id> [--json]` prints the Definition of Done. It writes no artifact itself (the CLI-entry gate may
migrate first, as for every `fr run` verb, and it runs host-side like them). It
exits 0 when every item is discharged, 1 when an item is owed, and 2 when the run or its
inputs cannot be read. It is defined in `commands/dod_cmd.py`, never in
`commands/run_cmd.py`. `cli.py` imports that module after `run_app`, which registers it.

R19. The close-out brief `fr pickup --run <id>` prints includes the Definition of Done. That
holds for `closeout_brief` and for both forms of `devops_brief` (in progress and finished).
The finished `devops_brief` says the stage is complete and nothing is left only when every
Definition of Done item is discharged. Otherwise it names each owed item.

R20. When `fr ops gate` has run every stage, and when a rerun finds every stage already done,
it says the DevOps stage is complete only when every Definition of Done item is discharged.
Otherwise it says every stage ran and lists each item still owed, from every group. As in R12,
nothing the pinned PR head carries discharges an item there: an `owed` resolution record or a
`[manual]` phase tick the head added counts as not there. A run that recorded a plan the
derivation cannot find is unreadable (exit 2 for `fr run dod`, "cannot be read" in the briefs and
the final line); only a run that recorded no plan has empty manual and plan-journal groups.

## Design shape

```text
packages/fr/src/fr/
  spec.py                    ~ Step gains `rows: tuple[str, ...]`; `(rows: …)` pointer   R7
  acceptance/walks.py        ~ row_walked(row): status walked + latest walk passed   R10
                             ~ close-command printing moved here from acceptance_cmd R9
  triage/ledger.py           ~ GatedRow.walked = row_walked(r)                       R10
  ops/
    refresh.py               + drift(): ops added/removed/changed, test plan changed;
                               refresh(): confirm → commit records → merge_commit
                               → leased push → reopen changed ops → trust          R1–R6
    gate.py                  ~ OpsTree port: merge_commit(ref, message)            R3
                             ~ HostGateState: reopened ops + entry ids before the
                               refresh; forget(from_stage)                         R6
                             ~ apply_phase: a reopened op ignores old closures     R6
                             ~ stages 4–7 call refresh first                       R1
                             ~ stage 5 asks unwalked devops rows (ran|owed)        R13
                             ~ stage 6/7 list gate_blockers; row-walk recovery     R14
                             ~ head walks excluded inside the stage                R12
                             ~ stage 8: plan dir still there → "archive held"      R15
                             ~ run(): final line reads the DoD                     R20
    holds.py                 ~ gate_items / gate_blockers(root, run, gate,
                               exclude_walks); devops_blockers kept                R10
  commands/
    ops_gate_cmd.py          ~ OpsWorkspace.merge_commit: fetch origin, merge,
                               commit or abort_merge                               R3
    closeout_cmd.py          ~ --ran on a step with rows → walk items in the same
                               record; --harness/--model; close commands          R9
    gate_cmd.py              ~ pass refuses on gate_blockers for tester too        R11
    dod_cmd.py               + `fr run dod <run-id> [--json]` on run_app           R18
  cli.py                     ~ import commands.dod_cmd after run_app               R18
  run/
    dod.py                   + definition_of_done(root, run) → DoD                 R17
    closeout.py              ~ closeout_brief and devops_brief show the DoD        R19
  plan_review/checks.py      ~ warn: gated-row coverage, unknown (rows:) ids       R16
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
     leased push ─► reopen changed ops (host state) ─► N > 4? forget stages ≥ 4, back to 4
                         │
                         ▼
                 trust (re-asks on change) ─► act
```

## Design

### A. The stale ops workspace (R1–R6)

`fr/ops/refresh.py` holds two functions.

- `drift(tree, default_root, plan_rel, spec_rel) -> Drift`. It loads the ops on both sides
  with `load_ops`, keys them by id and compares each `LoadedOp.op` (the frozen model, so
  equality is a comparison of the whole definition). It also compares `test_plan_steps` of
  the run's spec on both sides. The default side is a scratch tree from
  `GateHost.materialise(origin/<default>, …)` (the same paths `_head_paths` names), removed
  afterwards, as `_refuse_an_ops_gap` does. A plan directory that is absent on the default
  side raises `StageFailed` (R5). A side that cannot be read is a refusal, never "equal".
- `refresh(gate, tree, stage)`. Under `drift`'s answer it confirms (`gate.prompt.confirm`,
  always asked), then `tree.commit_paths(["docs"], …)`, then
  `tree.merge_commit(f"origin/{default}", message)`. `merge_commit` is a new `OpsTree` port
  method. `OpsWorkspace` (`commands/ops_gate_cmd.py`) implements it: `git fetch origin`, as
  its `rebase_onto` does, then `gitseam.Worktree.merge` (no-commit, rerere off,
  directory-rename detection off), then a commit, or `Worktree.abort_merge` and a
  `StageFailed` naming the conflicted paths. Next come `gate.publish(tree)` (leased), the
  reopening (R6) and `gate.trust(tree)`.

R6 is persisted host-side, in `HostGateState`, as `reopened: {ops: [ids], before: [entry
ids]}`: the changed and added op ids, and the plan-journal entry ids present at the refresh.
`apply_phase` treats a reopened op as not closed by recorded evidence. Its live status still
decides whether it runs. Its journal closure counts only for an entry not in `before`.
Stage 4's completion clears `reopened`. A refresh at stage 5, 6 or 7 that reopened anything
calls `state.forget(4)`, which drops stages 4 and later. `run()` reads `recorded()` before
each stage, so the same invocation goes back to stage 4.

Rows are left out of the comparison on purpose: the ops branch writes row walks (R9, R13)
that the default branch does not hold yet, so a row comparison would always differ.

### B. Rows a gate verifies (R7–R16)

The pointer grammar sits beside `_POINTER_RE` in `spec.py`: `(rows: a, b)`. Ids use the same
character class as op ids, split on commas, and blanks are refused. Older fr reads the
pointer as part of the step's text, which is harmless.

`closeout outcome` builds one `StepRecord`: the existing outcome `JournalItem`, plus one
`AcceptanceItem(id, status, notes, walk=Walk(...))` for each named row. It goes through
`engine.apply_record` with `RecordTarget(feature=<spec slug>)`, so a merged row is amended and
one commit holds both. The status becomes `walked` when `walk_verified` holds after the walk.
Otherwise the existing status stays, and the note names the harnesses still owed. The
issue-close printing (`_print_close_commands`) moves into `fr.acceptance.walks`, so both
writers print the same thing. Stage 5's probe path passes `--harness fr-ops-probe --model
op:<id>`.

`row_walked` replaces the `r.status == "walked"` test in `fr.triage.ledger` and is used by
`gate_items`. Every writer that sets `walked` (`set-status`, R9) already needs a passing walk
(`walked_error`), so the one visible change is this: a row whose latest walk failed no
longer counts as walked.

`gate_items` reads rows from `run_exit(...)`: `gated_rows` filtered by `row_gates[id] ==
gate`. `exclude_walks` maps a row id to walks to ignore. Inside the DevOps stage those are
the walks the pinned PR head's fold carries for the row (the fragment read with
`tree.show(head, …)`, as `head_entry_ids` reads journals). `_tester_owns` is replaced by
`gate_items(..., "tester")`; stage 7 keeps the declared-run-gate check.

Stage 5's row question runs each answer through `tree.fr(["acceptance", "set-status", …])`.
`ran` gives `--id <row> --status walked --walk "<answer>" --harness operator --model human
--strategy <effective> --notes "walked in the DevOps stage of run <id>" --feature <slug>`, or
`--status <current>` when the walk would not make the row walk-verified. `owed` gives
`--status walk-owed --notes "<why>" --feature <slug>`.

`fr plan self-review` gains `_gated_row_coverage_issues` in `plan_review/checks.py`, of
severity `warn`, beside `_ops_gap_issues`. It uses `exit_for_spec` plus the same promotion
`run_exit` applies (`devops` when `plan_has_ops`), and `steps_gated` for each gate. It has the
same cross-repo exemption as its neighbours.

### C. Definition of Done (R17–R20)

`fr/run/dod.py` returns `DefinitionOfDone(groups: tuple[DodGroup, ...])`. A group is
`(name, items: tuple[DodItem(what, discharged: bool, why)])`. The groups are `gate:devops` and
`gate:tester` (their `gate_items`), `manual phases` (the plan's unticked `[manual]` phases)
and `owed` (open `owed` entries of the run's spec and plan journals, minus the
`test-plan-step-*` entries and the manual-phase entries `fr archive` writes back, which other
groups already report). It runs no probe: it states what was recorded. `discharged` is true
for the whole DoD only when every item is. `commands/dod_cmd.py` renders it as text or JSON.
`run/closeout.py` appends the text form to `closeout_brief` and to both forms of
`devops_brief`, and its finished form reads the DoD. `ops/gate.py`'s `run` builds the DoD on
the ops workspace for its final line, on both the ran-stages path and the nothing-ran path.

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

- A tester-gate walker (#1310). It can reuse `gate_blockers` and the R9 walk path.
- An authored `## Definition of Done` section. The operator chose a derived DoD only.
- Committing each gate record as it is written (#1617's optional point). R3 commits them
  before a refresh, which removes the hazard the issue names.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-27-ops-gate-truth | `derio-net/super-fr` | `2026-11-27-ops-gate-truth` | — |
