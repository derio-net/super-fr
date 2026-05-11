# Vk V2 Library Implementation Plan

## Phase 1: Schema + parser foundation

### Task 1: Pydantic schemas

- P1.T1.S1: Create v2 package skeleton

- P1.T1.S2: Write fixture v2 plan folder (minimal valid)

- P1.T1.S3: Write test asserting pydantic loads `_meta.yaml`

- P1.T1.S4: Implement `PlanMeta` pydantic model

- P1.T1.S5: Test PlanMeta rejects bad input

- P1.T1.S6: Test PhaseDoc loads minimal fixture

- P1.T1.S7: Implement `PhaseDoc`, `Task`, `Step`, `PhaseStateBlock`, `StepState`, `Completion`

- P1.T1.S8: Test cross-validation — state.steps keys match step ids

- P1.T1.S9: Add cross-validator to PhaseDoc

### Task 2: `vk.v2.parse`

- P1.T2.S1: Test parse() round-trips minimal fixture

- P1.T2.S2: Implement `vk.v2.parse`

- P1.T2.S3: Wire parse() into `vk.v2.__init__`

- P1.T2.S4: Test parse() rejects v1 plan

- P1.T2.S5: Test parse() enforces vk_version constraint

- P1.T2.S6: Add version-constraint enforcement in parse()

### Task 3: Round-trip and regression check

- P1.T3.S1: Test round-trip — parse, serialize back, parse again equals original

- P1.T3.S2: Verify v1 tests still pass

- P1.T3.S3: Verify ruff and mypy clean on new code

- P1.T3.S4: Commit Phase 1

## Phase 2: Library projection chain

### Task 1: Renderer (pure)

- P2.T1.S1: Define `RenderedState`, `RenderedIssue`, `GhState`, `PhaseObservation`, `PrObservation`

- P2.T1.S2: Test `render()` for the simplest case (one undispatched agentic phase, no observation)

- P2.T1.S3: Implement `render()` skeleton + body template

- P2.T1.S4: Test lifecycle label projection — table-driven

- P2.T1.S5: Implement lifecycle-label projection table

- P2.T1.S6: Test phase-completion projection — agentic

- P2.T1.S7: Implement `_phase_complete()` per spec rules

- P2.T1.S8: Test archive_decision = all phases complete

- P2.T1.S9: Implement and verify

- P2.T1.S10: Test render() drift warnings (3 cases per spec)

- P2.T1.S11: Implement drift warnings in render()

### Task 2: Observer (gh-API-backed)

- P2.T2.S1: Define `GhClient` Protocol

- P2.T2.S2: Implement `FakeGhClient` for tests

- P2.T2.S3: Test `observe()` for one-phase plan with no tracking_issue

- P2.T2.S4: Implement `observe()` skeleton

- P2.T2.S5: Test `observe()` for dispatched phase with merged PR

- P2.T2.S6: Implement linked-PR discovery

### Task 3: Differ + Applier

- P2.T3.S1: Define `Diff`, `IssueLabelChange`, `IssueStateChange`, `IssueBodyChange`, `IssueCreate`, `RepoLabelEnsure`

- P2.T3.S2: Test `diff()` — undispatched phase yields IssueCreate

- P2.T3.S3: Implement `diff()`

- P2.T3.S4: Test diff is idempotent — re-diff after apply yields no mutations

- P2.T3.S5: Test `apply()` honors managed-labels-only rule

- P2.T3.S6: Implement `apply()`

- P2.T3.S7: Test `apply()` dry-run returns mutations without calling gh

- P2.T3.S8: Test `apply()` is atomic-per-mutation, accumulates failures

- P2.T3.S9: Implement failure accumulation

- P2.T3.S10: Run idempotency end-to-end

- P2.T3.S11: Verify ruff, mypy, full test suite

- P2.T3.S12: Commit Phase 2

## Phase 3: CLI surface + migration tool + GHA workflow

### Task 1: `vk apply` command + e2e

- P3.T1.S1: Test e2e — fixture plan → vk apply --dry-run → assert mutations

- P3.T1.S2: Implement `vk apply` typer command

- P3.T1.S3: Test `vk apply --all` walks plans/

- P3.T1.S4: Implement `--all` — find plan folders under `docs/superpowers/plans/`, apply each. Run: green.

### Task 2: `vk plan create / edit / rework / rework-add / rework-list`

- P3.T2.S1: Test `vk plan create` scaffolds a folder + appends spec row

- P3.T2.S2: Implement `vk.plan.create()` library function

- P3.T2.S3: Implement `vk plan create` CLI command

- P3.T2.S4: Test `vk plan edit --tick P1.T1.S1`

- P3.T2.S5: Implement `vk plan edit --tick`

- P3.T2.S6: Test `vk plan edit --complete-phase`

- P3.T2.S7: Implement `vk.plan.complete_phase()` and CLI

- P3.T2.S8: Test `vk plan rework` scaffolds sibling folder + spec row + parent_plan field

- P3.T2.S9: Implement `vk.plan.rework_create()` and CLI

- P3.T2.S10: Test `vk plan rework-add`

- P3.T2.S11: Implement `vk.plan.rework_add_origin()` and CLI

- P3.T2.S12: Test `vk plan rework-list`

- P3.T2.S13: Implement `vk.plan.rework_list()` and CLI

- P3.T2.S14: Test `vk plan self-review` lints

- P3.T2.S15: Implement `vk.plan.self_review()` and CLI

### Task 3: `vk pickup`

- P3.T3.S1: Test `vk pickup` outputs full step text + PR title template + dependency reminder

- P3.T3.S2: Implement `vk pickup`

### Task 4: `vk spec status` + `--all`

- P3.T4.S1: Test `vk.spec.parse()` extracts Implementation Plans table without Status column

- P3.T4.S2: Implement `vk.spec.parse()`

- P3.T4.S3: Test `vk.spec.compute_status()` aggregates across plans

- P3.T4.S4: Implement `vk.spec.compute_status()`

- P3.T4.S5: Test `vk.spec.render_status_md()`

- P3.T4.S6: Implement `render_status_md()`

- P3.T4.S7: Implement `vk spec status` CLI

- P3.T4.S8: Implement `vk spec status --all`

### Task 5: `vk migrate v1-to-v2`

- P3.T5.S1: Test migrate converts a sample v1 plan to v2 folder

- P3.T5.S2: Implement migrate skeleton

- P3.T5.S3: Test migrate fails loud on per-phase target_repo override

- P3.T5.S4: Implement the cross-target-repo loud failure

- P3.T5.S5: Test migrate --skip-in-progress (default)

- P3.T5.S6: Implement `--skip-in-progress` (default true)

- P3.T5.S7: Test migrate handles v1 rework plans

- P3.T5.S8: Implement v1-rework parsing in migrate

- P3.T5.S9: Test migrate updates spec files (drops Status column, points File at folders)

- P3.T5.S10: Implement spec-file rewrite

### Task 6: GitHub Action workflow file

- P3.T6.S1: Write `.github/workflows/vk-spec-status.yml`

- P3.T6.S2: Add a thin wrapper workflow at `.github/workflows/_pr_spec_status.yml` for this repo's own use

- P3.T6.S3: Lint the workflow files

### Task 7: Final integration

- P3.T7.S1: Full e2e test — fixture plan, dispatch via apply, simulated state changes, complete

- P3.T7.S2: Run full test suite + linters

- P3.T7.S3: Commit Phase 3

## Phase 4: Retire v1 + skill updates

### Task 1: Delete v1 source modules + tests

- P4.T1.S1: Move v1 modules out of `src/vk/` — `git rm` per spec retirement table

- P4.T1.S2: Delete v1 tests — `git rm`

- P4.T1.S3: Update `src/vk/cli.py` — remove imports/registrations of deleted command modules

- P4.T1.S4: Move v2 commands from `vk.v2.commands` to `vk.commands` (the v2 namespace was a coexistence scaffold; collapse it now)

- P4.T1.S5: Run pytest — verify only v2 tests remain and all pass

- P4.T1.S6: Run ruff + mypy

### Task 2: Update skill files

- P4.T2.S1: Update `skills/vk-plan/SKILL.md`

- P4.T2.S2: Update `skills/vk-dispatch/SKILL.md`

- P4.T2.S3: Update `skills/vk-execute/SKILL.md`

- P4.T2.S4: Update `skills/vk-progress/SKILL.md`

- P4.T2.S5: Verify skills are coherent — read each SKILL.md after edits, ensure no dangling references

### Task 3: Confirm final state

- P4.T3.S1: `grep -rn "vk progress\|vk dispatch\|vk admin\|vk issue \|vk execute" skills/ src/`

- P4.T3.S2: `vk --help` — confirm only v2 commands shown.

- P4.T3.S3: Commit Phase 4

## Phase 5: v2.0.0 release

### Task 1: Bump version triplet

- P5.T1.S1: Update `pyproject.toml` — set `[project].version = "2.0.0"`

- P5.T1.S2: Update `.claude-plugin/plugin.json` — set `.version = "2.0.0"`

- P5.T1.S3: Update `.claude-plugin/marketplace.json` — set `.plugins[0].version = "2.0.0"`

- P5.T1.S4: Run `uv sync` — uv.lock picks up `vk==2.0.0`

- P5.T1.S5: Verify `uv run vk --version` — outputs `2.0.0`

### Task 2: CHANGELOG

- P5.T2.S1: Add v2.0.0 section to `CHANGELOG.md`

### Task 3: Tag and push

- P5.T3.S1: Commit Phase 5

- P5.T3.S2: Tag

- P5.T3.S3: Verify tag visible — `gh release view v2.0.0` (or check github.com)

## Phase 6: Self-migrate this repo's plans

### Task 1: Dry-run

- P6.T1.S1: From repo root, run dry-run

- P6.T1.S2: Sanity-check the output

### Task 2: Apply

- P6.T2.S1: Apply migration

- P6.T2.S2: Verify a sample migrated plan

- P6.T2.S3: Run full test suite — ensure migration didn't break anything

### Task 3: PR + review

- P6.T3.S1: Branch, commit, push

- P6.T3.S2: Open PR

- P6.T3.S3: Review and merge — operator action; once green, merge.

### Task 4: Post-completion housekeeping (documented; executed AFTER Phase 6)

- P6.T4.S1: Mark this plan Status: Complete via `vk plan edit ... --complete-phase` for any remaining unchecked steps

- P6.T4.S2: Run migration on the now-complete plan

- P6.T4.S3: Open a tiny follow-up PR archiving this plan

- P6.T4.S4: Plan 1 is closed. Plan 2 (bridge migration in willikins) is now unblocked.
