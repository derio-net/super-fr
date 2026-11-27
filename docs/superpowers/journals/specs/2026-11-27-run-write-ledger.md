<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-run-write-ledger

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-27T09:01:50+00:00 input=true -->
### operator-brief · discovery · Operator brief: batch arch-run-ledger (super-fr#1515)

Batch `arch-run-ledger` of derio-net/super-fr: 1 issue, delivered as ONE pull request.
Batch title: #1318: move the write ledger out of run_cmd.py into fr/run/writes.py

#### super-fr#1515 — Move the write ledger out of commands/run_cmd.py into fr/run/writes.py (the one cheap run_cmd slice)

Decomposition plan for `packages/fr/src/fr/commands/run_cmd.py` from the #1318 review (section 5.1). P3 refactor; no behaviour change. 8,862 lines; budget 8,900 in `tests/unit/test_tripwire_module_budget.py`. Line ranges at `39f06125`, unchanged on the #1318 branch.

**Why only one slice is cheap.** No module under `fr/run/`, `fr/record/`, `fr/lenses/` or `fr/verification/` imports `typer` or a console today. The write ledger is the only cluster with neither a `raise typer.Exit` nor a console print (0 / 0); lookup (B, 5 / 7), provenance (C, 9 / 11), briefs (E, 7 / 15), deliver gates (H, 17 / 28) and evidence (D, 55 / 73) all refuse by printing and exiting. Those move only after the verdict design (#1519), which now carries them.

**The slice (M):** `ResolveGuard`, `_RunWrites`, `_save_run_state`, `_commits_run_writes` ([`packages/fr/src/fr/commands/run_cmd.py:170-491`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L170-L491)) and the run helpers `_now`, `_fr_version`, `_capture_usage`, `_capture_on_new_host` ([`packages/fr/src/fr/commands/run_cmd.py:492-543`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L492-L543)), 374 lines, to a new `fr/run/writes.py`. Lines [`packages/fr/src/fr/commands/run_cmd.py:1-169`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L1-L169) (docstring, imports, the `_run_group` callback) stay.

**Preserved behaviour:** `_commit_run_writes_now` runs before a dispatch brief is printed ([`packages/fr/src/fr/commands/run_cmd.py:384-398`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L384-L398)); the decorator commits in `finally` on refusals; the four `ContextVar`s keep their meaning; the tail of `_resolve_body` is not moved. Moved names stay importable from `run_cmd` (as it already re-imports `fr.run.liveness`'s, [`packages/fr/src/fr/commands/run_cmd.py:85-98`](https://github.com/derio-net/super-fr/blob/39f06125eb377a25526586fefcc14007dabbca7c/packages/fr/src/fr/commands/run_cmd.py#L85-L98)) until `record/apply.py` imports them from `fr/run`.

**Callers to migrate:** `fr/record/apply.py:207` and `:1668` (`ResolveGuard` and the resolve path); tests that import `_save_run_state` or patch the ledger's names.

**Guards:** lower the line budget; a test that `fr/run/writes.py` imports neither `typer` nor a console.

**Shared with other open work:** #1500 (`save_run_state`, which `_save_run_state` calls) and the cursor-race issue #1511. Land #1500 first where they touch the same function.

---

Came out of the architecture review for #1318 (section 5.1 of `docs/superpowers/audits/2026-11-16-architecture-review.md`, which lands with that PR: https://github.com/derio-net/super-fr/blob/main/docs/superpowers/audits/2026-11-16-architecture-review.md).

<!-- fr:journal kind=decision scope=spec id=d-conflict-refusal created=2026-11-27T09:01:50+00:00 decided_by=operator -->
### d-conflict-refusal · decision · Cursor-conflict refusal stays in run_cmd as a thin wrapper

Q1 (operator): writes.py's save_run_state_noted lets RunStateConflictError propagate; run_cmd._save_run_state catches it, prints and exits 2 (R3).

<!-- fr:journal kind=decision scope=spec id=d-capture-on-new-host created=2026-11-27T09:01:50+00:00 decided_by=operator -->
### d-capture-on-new-host · decision · _capture_on_new_host stays in run_cmd

Q2 (operator): it needs fr.commands.common.resolve_repo_root; moving it would make fr/run import fr/commands. capture_usage moves (R1, R4).

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-27T09:01:50+00:00 decided_by=operator -->
### d-verification · decision · Verification: strategy none, gate developer

Q3 (operator): CI unit suite plus the new guard test is the proof; nothing waits after merge.

<!-- fr:journal kind=decision scope=spec id=d-migrate-callers created=2026-11-27T09:01:50+00:00 decided_by=operator -->
### d-migrate-callers · decision · Migrate apply.py and tests to fr.run.writes now

Q4 (operator): no compatibility-only re-exports in run_cmd; run_cmd imports only the aliases its body uses (R6).

<!-- fr:journal kind=finding scope=spec id=spr-r1 created=2026-11-27T09:08:17+00:00 state=open review_scope=in -->
### spr-r1 · finding [open] (reviewer: in scope) · Plan omits the docs-currency stamps for the two pages covering run_cmd.py and fr/run/**

target: plan. docs/reference/workflow-shapes.md:8-9 and docs/reference/cli.md:8 cover the changed paths; the plan had no step and no files entry for them, so fr docs check and deliver would refuse.

<!-- fr:journal kind=finding scope=spec id=spr-r2 created=2026-11-27T09:08:17+00:00 state=open review_scope=in -->
### spr-r2 · finding [open] (reviewer: in scope) · A test that imports `_capture_usage` from run_cmd is missed, and the plan's grep would not find it

target: plan. tests/unit/test_run_cost_cmd.py:345 imports `_capture_usage` from run_cmd; the grep searched no from-import form.

<!-- fr:journal kind=finding scope=spec id=spr-r3 created=2026-11-27T09:08:17+00:00 state=open review_scope=in -->
### spr-r3 · finding [open] (reviewer: in scope) · R1/R4 leave part of the moved range unplaced: `_Cmd`, the header comment and the unobserved/provenance helpers

target: spec. `_Cmd` (run_cmd.py:477), the gh#610 header comment (:164-171) and the helpers at :296-353 had no stated home in the spec.

<!-- fr:journal kind=finding scope=spec id=spr-r4 created=2026-11-27T09:08:17+00:00 state=open review_scope=in -->
### spr-r4 · finding [open] (reviewer: in scope) · Design shape's '-~330 lines' overstates the extraction

target: spec. The moved blocks total about 240 lines, about -225 net.

<!-- fr:journal kind=finding scope=spec id=spr-r5 created=2026-11-27T09:08:17+00:00 state=open review_scope=in -->
### spr-r5 · finding [open] (reviewer: in scope) · Layering guard keys on the import's module name only, so `from fr import commands` and relative imports pass

target: plan. A check on node.module alone misses `from fr import commands` and `from ..commands import common`.

<!-- fr:journal kind=review scope=spec id=spr-review created=2026-11-27T09:08:17+00:00 -->
### spr-review · review · independent spec+plan review: 5 findings, all in scope

Findings raised: spr-r1..spr-r5, all fixed in the spec and plan. All four operator decisions honoured (d-conflict-refusal, d-capture-on-new-host, d-verification, d-migrate-callers).

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-27T09:08:17+00:00 lens=tests step=spec-plan-review -->
### lens-tests-1 · lens · The move relies on monkeypatches following each lookup into fr.run.writes; check every patched name still intercepts where it is called

<!-- fr:journal kind=finding scope=spec id=spr-r1-resolved created=2026-11-27T09:08:17+00:00 state=fixed resolves=spr-r1 -->
### spr-r1-resolved · finding [fixed] · resolves spr-r1: Plan omits the docs-currency stamps for the two pages covering run_cmd.py and fr/run/**

Plan: docs pages added to files; P1.T4.S1 runs fr docs check and bumps both reviewed stamps (or edits). Spec Background names both pages.

<!-- fr:journal kind=finding scope=spec id=spr-r2-resolved created=2026-11-27T09:08:17+00:00 state=fixed resolves=spr-r2 -->
### spr-r2-resolved · finding [fixed] · resolves spr-r2: A test that imports `_capture_usage` from run_cmd is missed, and the plan's grep would not find it

Spec Background names test_run_cost_cmd.py:345 (and test_placement_emitted_paths.py:150, which stays); P1.T3.S2 migrates it and greps the from-import form.

<!-- fr:journal kind=finding scope=spec id=spr-r3-resolved created=2026-11-27T09:08:17+00:00 state=fixed resolves=spr-r3 -->
### spr-r3-resolved · finding [fixed] · resolves spr-r3: R1/R4 leave part of the moved range unplaced: `_Cmd`, the header comment and the unobserved/provenance helpers

R1 names `_Cmd` and the header comment; R4 lists the unobserved-gate cluster's six names; P1.T3.S1 matches.

<!-- fr:journal kind=finding scope=spec id=spr-r4-resolved created=2026-11-27T09:08:17+00:00 state=fixed resolves=spr-r4 -->
### spr-r4-resolved · finding [fixed] · resolves spr-r4: Design shape's '-~330 lines' overstates the extraction

Design shape now says about -225 lines net.

<!-- fr:journal kind=finding scope=spec id=spr-r5-resolved created=2026-11-27T09:08:17+00:00 state=fixed resolves=spr-r5 -->
### spr-r5-resolved · finding [fixed] · resolves spr-r5: Layering guard keys on the import's module name only, so `from fr import commands` and relative imports pass

R2 and the Design require both spellings caught; P1.T1.S1 judges module and module.name, resolves relative imports against fr.run, and plants both forms.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T09:08:18+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  run-cursor-conflict-refusal-kept: none
  run-write-ledger-cli-free: none
row_kinds:
  run-cursor-conflict-refusal-kept: none
  run-write-ledger-cli-free: none
run_gate: developer
run_kind: none
```
