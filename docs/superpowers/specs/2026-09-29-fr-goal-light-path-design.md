# fr-goal light path for small single-phase goals — design

**Date:** 2026-09-29 · **Issue:** derio-net/super-fr#780 (batch `light-path`, wave 8)
**Run:** `2026-09-29-feat-batch-light-path` · **Branch:** `feat/batch-light-path`

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | A second shipped shape, `fr-goal-light`, exists. A run reaches it through `fr run start fr-goal-light`, or when the brainstorm record declares `shape: fr-goal-light`, which rebinds the run. A rebind is allowed only while the run's first step is being resolved, and only onto a shape that begins with that same step. | input "fr-goal light path for small single-phase goals"<br>decision d1-select-brainstorm-rebind |
| R2 | On the light shape, the `plan` step refuses a plan with more than one agentic phase. `[manual]` phases are allowed. The refusal names the fix. | input "fold plan review into spec review for one-phase plans"<br>decision d1-select-brainstorm-rebind |
| R3 | On the light shape, one dispatched `fr-spec-reviewer` reviews the spec and the one-phase plan together, after the plan is written. It is held to the same evidence gate as `spec-review` (review, reviewer, findings, requirements, coverage). `fr plan self-review` still runs as a cli step. The per-phase code review (`review-phase`, with a dispatched reviewer) stays. | input "one review dispatch"<br>input "fold plan review into spec review for one-phase plans"<br>decision d2-reviews-spec-plan-once-code-once |
| R4 | On every shape, `fr run resolve --record` also advances by default. After applying the record it runs any following `kind: cli` steps and prints the next dispatch brief, in the same invocation. `--no-advance` keeps today's behaviour. | input "one bookkeeping call per step"<br>input "resolve+record+advance in one fr run call"<br>decision d3-one-call-default-all-shapes |
| R5 | `fr run advance` runs consecutive `kind: cli` steps in one invocation. It stops at the first agent step (printing its brief), an operator gate, a failure, or the end of the run. | decision d3-one-call-default-all-shapes |
| R6 | An `implement-phase` or `review-phase` record may name a full-suite log as `evidence: {tests: <log>}`. fr verifies who wrote the log and that it is fresh, then stores its hash and the code tree it covers. `deliver` accepts `tests: reuse` when HEAD's code tree still equals the latest such unit's tree, and otherwise refuses with the fresh-run instruction. | input "deliver reuses the executor's verified suite log on an unchanged tree"<br>decision d4-suite-reuse-tree-matched |
| R7 | The fr-goal skill documents the light path and the one-call resolve. The phase executor and the spec reviewer return a fixed structured shape: the executor returns its suite log path, the reviewer covers spec and plan. The orchestrator is told to act on those returns and never to open a subagent's transcript or re-read what a brief already carries. | input "subagents return structured results"<br>decision d5-context-prose-and-brief-keys |
| R8 | On the super-fr-3 feature-C benchmark, the light path costs at most 2× plain's money and takes at most 2.5× plain's time, with delivery still verified. | input "Target ≤ 2× plain's cost, ≤ 2.5× its time on feature C."<br>decision d6-test-plan-rerun-feature-c |

## Design

The input's delivery rules (branch name, draft PR on spec commit, `Closes` line, no member issue as `tracking_issue`) are instructions for this run and are honoured by it. They are not product requirements.

### Background: where a small goal's money goes

Take 9 (feature C, one phase) cost $7.67 and 45 min against plain's $2.13 and 12.8 min. The orchestrator carried 76% of that. Take 10 measured 6.75 to 24 bookkeeping turns per step, against a target of 1 to 2. Three fixed costs don't shrink with the goal:

1. **Two separate review stages before any code exists.** `spec-review` dispatches a reviewer, then `plan` and `plan-review` each take their own round trip (`plugins/super-fr/workflows/fr-goal.yaml:98-112`).
2. **Two or more `fr` calls per step.** `resolve --record` applies the record and moves the cursor (`packages/fr/src/fr/record/apply.py:831-956`), but it never briefs the next step: `_complete_step` sets `cursor = _next_step_id(...)` and returns (`packages/fr/src/fr/commands/run_cmd.py:886-889`). A separate `fr run advance` prints the brief (`run_cmd.py:4155-4177`). A `kind: cli` step then costs one more `advance` per step (`run_cmd.py:4199-4214` returns after one step). Every call re-reads the orchestrator's whole context.
3. **A fresh full suite at `deliver`.** `_verify_tests_log` accepts only a log written by a main-thread Bash call since `deliver` opened (`run_cmd.py:2212-2313`, `packages/fr/src/fr/run/telemetry.py:1012-1034`). So the executor's green run, done minutes earlier on the same tree, is thrown away and repeated.

### A. The `fr-goal-light` shape (R1, R2, R3)

New file `plugins/super-fr/workflows/fr-goal-light.yaml`. It also ships in the wheel's `fr/workflows/`, the same way `fr-goal.yaml` resolves (`packages/fr/src/fr/workflow/resolve.py:151-198`).

```
brainstorm (gate: operator)            # identical to fr-goal
plan                                   # fr-plan; evidence: [single-phase]
spec-plan-review                       # agent: fr-spec-reviewer, tier: hard
                                       #   needs: [spec, plan]; emits: [journal:spec, acceptance]
                                       #   evidence: [review, reviewer, findings, requirements, coverage]
plan-review (cli)                      # fr plan self-review {{ artifacts.plan }}
implement { implement-phase, review-phase }   # identical members to fr-goal
journal-check (cli)                    # identical
deliver                                # identical, plus `tests: reuse` (§D)
```

- **Order.** `plan` comes before the review so a single dispatch sees both documents. `plan-review` (deterministic) comes after the reviewer, so the plan is self-reviewed once more after the reviewer's fixes land.
- **`spec-plan-review`** reuses the `spec-review` evidence machinery unchanged: `_evidence_target` routes a step that emits `journal:spec` to the spec journal (`run_cmd.py:1452-1462`), and `_verify_reviewer` checks `expected_agent=step.agent` (`run_cmd.py:2096-2185`). Plan findings go into the **spec journal** as well, tagged `target: plan` in the body, so `findings` (derived from that one journal) gates both documents. This step emits no `journal:plan` and never ticks.
- **`single-phase`** is a new derived evidence name, never passed. It is computed on the light shape's `plan` resolve from the emitted plan's phases. The plan must have exactly one phase that is not `[manual]`, otherwise the resolve is refused: `single-phase: the light shape takes one agentic phase; this plan has N (<ids>). Merge them, or start a new run on fr-goal.` This is a structural rule, checked at authoring time, rather than a hope that the plan stays small.
- **Derived-evidence dispatch** follows the existing pattern (`_verified_evidence`, `run_cmd.py:1580-1753`). `Step` gains no field, and the manifest stays `schema: 1` (`packages/fr/src/fr/workflow/model.py:27,115`).

**Rebind at brainstorm (R1).** The record kind gains an optional top-level `shape: <name>` key (`StepRecord`, `packages/fr/src/fr/record/model.py:216-247`). `apply_record` validates it before any write. The rebind is allowed when all of these hold:

1. the step being resolved is the run's first step, and no other step has left `pending`;
2. `resolve_workflow(<name>)` finds the target, and its first step has the same id as the current step;
3. the target is not the run's current shape. A same-shape declaration is a no-op, which is idempotent.

On success, fr rewrites `RunState.workflow` to `<name>@<schema>` and replaces `RunState.steps` with the target's step records. The resolved first step's record is carried over. The cursor then moves by the usual `_complete_step`, so `_check_step_drift` (`run_cmd.py:756-806`) sees a consistent step set from then on. Any other use is refused, naming the rule. The rebind rides the brainstorm record's one commit.

Under artifact-versioning rules this is a shape change to the **record** kind: `current_version` goes 4 → 5 (`packages/fr/src/fr/artifacts/registry.py:441`), with a stamp-only `SchemaMigration` in a new `fr/artifacts/record_shape.py`, registered through `fr/artifacts/__init__.py`, and the validator extended. The **run** kind's shape does not change, because `workflow` and `steps` are already free fields of `RunState`.

### B. One call per step (R4, R5)

`advance_cmd`'s body (`run_cmd.py:4031-4214`) is extracted into `_advance_once(repo_root, run_id, *, redispatch) -> AdvanceStop`. Its outcomes are `brief`, `gate`, `cli-done`, `cli-failed`, `refused`, `complete`, and printing is unchanged. On top of it:

- **`fr run advance`** loops `_advance_once` while it returns `cli-done` and the new cursor is a `cli` step. That way a `plan-review` → `implement` transition, or `journal-check` → `deliver`, costs one call. A failure prints as today and exits 1. The loop is capped by the step count, so a manifest can never spin.
- **`fr run resolve --record`** (`run_cmd.py:5042-5084`) calls the same loop after `apply_record` succeeds, unless `--no-advance` is passed. The one-line outcome prints first, then the advance output exactly as `fr run advance` would print it, including the brief JSON on its own line. Exit codes: 0 when the chain stopped on a brief, gate, or run end; 1 when a chained cli step failed. In that case the record is already committed, and the message says `record applied; <step> failed (exit N)`, so nobody re-applies the record. A refused record never advances.
- **Unchanged:** the flag form (`--state/--evidence`) doesn't advance, because humans and runners use it and their contract stays. `--redispatch` stays on `advance` only.
- **Commits:** the apply commit and the advance commit stay separate commits. The cost this removes is calls, and the orchestrator's context re-read on each one, not git commits.

The skill prose drops every "then `fr run advance`" that follows a `resolve --record`.

### C. Structured returns and a small orchestrator context (R7)

- `plugins/super-fr/agents/fr-phase-executor.md`: the return block (today "the test command run and its pass/fail summary", line 131) becomes a fixed shape: `record: <path>`, `outcome: done|failed|blocked`, `tests_log: <host-visible path>|none`, `summary: <≤5 lines>`. The executor's last act before returning is the full suite, written to a host-visible log outside `<run>.records/`. The long-command form it already documents (lines 151-154) keeps its `exit=N` line. That log goes in the record's `evidence: {tests: <log>}`.
- `plugins/super-fr/agents/fr-spec-reviewer.md`: when the brief names a plan, the reviewer also checks it. It checks that the phase reads back against the spec's requirements, that it is a single agentic phase with TDD-shaped steps, and that every acceptance row the spec creates is linked. Each finding carries `target: spec|plan`. The return shape is otherwise unchanged.
- `plugins/super-fr/skills/fr-goal/SKILL.md` gets a **Light path** section. It covers when to declare `shape: fr-goal-light` (a goal whose asks plan to one agentic phase), the step order, and three context rules: act on a subagent's structured return, never open its transcript, and never re-read a spec or plan that the brief or `fr pickup` already carries. §5 and §8 describe `tests: reuse`, and every step describes the one-call resolve.
- The canonical changes are mirrored with `scripts/sync-opencode.py` and `scripts/sync-hermes.py`. The published explainer `docs/explainers/01-fr-goal.md` (and its `.html`) gains the light path, per explainers-currency.

### D. `deliver` reuses a verified suite log (R6)

**Recording on a phase unit.** An `implement-phase` or `review-phase` record may carry `evidence: {tests: <log>}`. It is optional, so no manifest change is needed. On resolve, fr runs these checks:

1. **Writer.** The log must be written by the unit's own holder, using the same rules as `_verify_tests_log` (not empty, not in `<run>.records/`, mtime inside a completed Bash window that redirects into it). The transcript differs, though: it is the claimed agent's subagent transcript (`witness_transcript`, `telemetry.py:993-1009`) on Claude Code; on OpenCode it is the child session named by the claim; and for an inline unit it is the orchestrator's main thread. `orchestrator_wrote_since` is generalised to `wrote_since(transcript|session, log, since)`. When nothing can be read, the log is recorded as `unobserved=tests`, as today.
2. **Freshness.** The log's mtime must be later than the newest mtime of every **code** path that differs from the merge-base, counting both committed changes and anything uncommitted.
3. **Witness.** fr stores `tests=<shown>@<sha256[:12]>;tree=<code-tree-hash>` in the unit's `evidence` (`dict[str, str]`, `packages/fr/src/fr/run/model.py:221`). The tree is computed after the record's own commit.

**Code tree.** This is the sha256 of `git ls-tree -r HEAD` with every path under `docs/superpowers/` and `docs/acceptance/` removed. Those are fr's artifact trees: runs, records, journals, plans, specs, and the matrix with its reports, which `resolve` itself writes between the suite run and `deliver`. Stated limit: a docs-only change under those two prefixes that breaks a test (for example `test_validate_artifacts` over the repo's own artifacts) is not seen as a tree change. CI still runs the suite on the PR, so this can't merge red. It can only reach a draft PR that the ready-guard holds.

**Reuse at `deliver`.** `evidence: {tests: reuse}` is accepted when HEAD's code tree equals the tree of the **most recently resolved** unit carrying a `tests` witness, and the working tree has no uncommitted code-path change. fr then records `tests=reused:<unit>:<witness>`. When the tree differs, the resolve is refused: `tests: reuse — the code tree changed since <unit> (<n> paths, e.g. <path>); run the full suite yourself into a log and name it`. A plain `tests: <log>` keeps today's orchestrator-only rule unchanged. The PR body renders the reused unit and its witness. Reuse is allowed on both shapes (d4 scoped it to the mechanism, not the light shape). A review-phase fix changes the tree, so it needs either its own recorded log or a fresh run at deliver.

### E. Harness parity

- **Transcript verification of the executor's log** is observed on Claude Code (subagent transcript) and OpenCode (child session). It is `unobserved` on Hermes, the same as every existing transcript gate.
- **The one-call resolve and cli chaining** are harness-neutral, since they are CLI behaviour.
- **The light shape** is a manifest, which every harness drives identically. `parity.yaml` gains no surface, because no hook or plugin changes.

### F. Out of scope

- A bound on spec-review re-dispatch loops (#808).
- Scratch-file homes for `fr plan create` (#812).
- Who gives the review ok at `deliver` (#814).
- The per-phase cost split (#636).

This PR measures nothing live. The benchmark is the post-merge Test Plan.

## Test Plan

Automated (CI, `uv run pytest`):

1. **Shape (R1, R2, R3).** `fr-goal-light` resolves and passes `fr workflow check`. Rebind at brainstorm succeeds, and it is refused after brainstorm, onto a shape with a different first step, or onto an unknown shape. A two-agentic-phase plan is refused at the light `plan` step and a one-phase plus `[manual]` plan passes. `spec-plan-review` is refused without a reviewer, review entry, or closed findings.
2. **One call (R4, R5).** `resolve --record` prints the next brief. It runs `plan-review` or `journal-check` inline and stops at the next agent step. It exits 1 on a chained cli failure with the record committed. `--no-advance` restores today's behaviour. `advance` chains consecutive cli steps.
3. **Reuse (R6).** A phase log written by the holder is recorded with its tree hash. A hand-written log is refused, and so is a stale log (older than a changed code file). `deliver` `tests: reuse` passes on an unchanged code tree, is refused after a code change, and passes after bookkeeping-only commits.
4. **Record kind v5.** The migration chain reaches 5 from 1, and a v4 record migrates.
5. **Prose (R7).** The skill, agent, and mirror tripwires stay green. A content test pins the Light path section and the executor's `tests_log` return key.

Post-merge — operator-driven:

6. **Benchmark (R8).** Rerun the super-fr-3 feature-C brief on the light path, with the same base and models as take 9 (or take 10). Compare cost and wall-clock time against plain. Pass when cost ≤ 2× and time ≤ 2.5×, with `deliver`'s evidence verified. Record the result on #780.
