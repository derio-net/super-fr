# Retire `plan_ops.tick` and `complete_phase` onto the record engine

Issue: derio-net/super-fr#1522 (slice 4 of the `plan_ops.py` slices from the
architecture review, `docs/superpowers/audits/2026-11-16-architecture-review.md` §6.4).

## Background

Two code paths write a plan's step ticks and phase completions:

- `fr.plan_ops.tick` (`packages/fr/src/fr/plan_ops.py:513`) and
  `fr.plan_ops.complete_phase` (`plan_ops.py:566`). They parse the plan, change the
  phase file's `state:` block, **write it first** (`write_text_atomic`, `plan_ops.py:557`,
  `:590`), re-parse after the write, and stage the file. They raise `PlanEditError`.
- The step-record engine, `fr.record.apply.apply_record` (`record/apply.py:1602`). Its
  `_plan_writes` (`record/apply.py:698`) builds every tick and completion in an in-memory
  overlay, runs the refactor-or-justify gate on every completion (`_refactor_check`,
  `record/apply.py:784`), parses a scratch copy of the plan as it will be before any byte
  lands (`_check_plan_parses`, `record/apply.py:806`), then writes and commits once
  (`_commit` → `fr.records_commit.commit_records`, which never raises). It raises
  `RecordRefusedError`.

`fr plan edit --tick/--complete-phase` already uses the engine: it builds a one-entry
`StepRecord` and calls `apply_record` with a `RecordTarget(plan_dir=…)`
(`packages/fr/src/fr/commands/plan_cmd.py:276-317`). No module under `packages/` calls
`plan_ops.tick` or `plan_ops.complete_phase`; the other `plan_ops` importers
(`commands/undispatch_cmd.py`, `commands/apply_cmd.py`, `fr_dispatch/__init__.py`,
`record/apply.py`) use `set_tracking_issue`, `clear_tracking_issue`,
`rewrite_phase_text` and `_now_iso` only.

Only tests still call the two functions: 31 `from fr.plan_ops import …` lines plus 4
`plan_ops.tick(…)` / `plan_ops.complete_phase(…)` attribute calls, in six files (the table below).
So the old path is a second, laxer definition of "tick a step" that tests exercise and
the product does not. A test that passes through it proves nothing about what
`fr plan edit` or `fr run resolve --record` does.

Why this is a behaviour change and not a refactor: moving those tests onto the engine
changes, for each of them, (a) the write order (validate first, then write; a refusal
leaves the file byte-identical instead of written-then-rejected), (b) the refactor gate
on completions, which `plan_ops.complete_phase` never ran, (c) a commit after each write
where the old path only staged, and (d) the error type and wording.

## Requirements

R1. `fr.plan_ops` no longer defines `tick` or `complete_phase`. The record engine (`fr.record.apply.apply_record`) is the only writer of a plan's step ticks and phase completions.
R2. A tripwire test fails when any Python file under `packages/` or `tests/` imports `tick` or `complete_phase` from `fr.plan_ops`, or reads either as an attribute of the `plan_ops` module. It reads the syntax tree (`ast`), runs no subprocess, and names the file and line.
R3. Tests that used the two functions only to set up plan state use one shared test helper, `tests/plan_state.py`, which builds a `StepRecord` (`TickItem` / `CompleteItem`) and calls `apply_record` with `RecordTarget(plan_dir=…)`, choosing the repo root exactly as `fr plan edit` does (`parse(plan_dir).repo_root`, else the plan directory). It raises the engine's own errors.
R4. When the refactor gate refuses a test fixture's completion, the fixture is changed (a refactor step, or a `no-refactor-because` reason in the plan journal). The helper never bypasses or disables a gate.
R5. Each refusal and property the old functions' own tests pinned stays pinned, now against the engine through the helper: a re-tick with the same state keeps its `ticked_at`; a skip (`-`) without a note is refused; an unknown step id is refused; completing a manual phase without a note is refused; completing an agentic phase with unticked steps is refused; a tick or completion leaves every byte outside the `state:` block unchanged (including a `|-` block scalar and a flow-style `state:` block). A test matches the engine's error type and wording. A property an existing engine test already pins is not tested twice; the plan names each one dropped and the test that already pins it.
R6. A new test proves the write-order change: a tick or completion the engine refuses leaves every phase file of the plan byte-identical.
R7. `fr plan edit --tick` and `--complete-phase` keep their output, exit codes and commit unchanged; their existing tests pass unchanged.
R8. Comments and docstrings in `packages/` that name the retired functions (for example `_check_plan_parses`'s docstring, `record/apply.py:808`) are reworded. Archived documents and the audit report are not rewritten.

## Design

### What goes

`plan_ops.py` loses `tick`, `complete_phase` and the section header above them
(`# fr.plan.tick / fr.plan.complete_phase`). Imports that only they used (`Literal`, if no
other use remains) go too. `rewrite_phase_text`, `_now_iso`, `set_tracking_issue` and
`clear_tracking_issue` stay; the engine and the bridge still use them.

### The test helper

`tests/plan_state.py` (the `tests` directory is already a package):

```python
def tick(plan_dir, step_id, *, state="x", note=None) -> ApplyOutcome
def complete_phase(plan_dir, phase_n, *, note=None) -> ApplyOutcome
```

Each builds a one-entry `StepRecord` and calls
`apply_record(repo_root, None, record, target=RecordTarget(plan_dir=…, message=…))`, the
same call `fr plan edit` makes. The names match the old ones on purpose, so a setup
call site changes only its import line. A skip without a note fails when `TickItem` is
built (the model's validator), before the engine runs; the helper lets that error
through as it is.

A fixture plan in a directory that is not a git repository still works: `commit_records`
reports a missing repository on stderr and does not raise, so the write lands and the
commit is skipped. In a git repository (`test_journal_cmd.py`'s `_init_repo`), each
helper call now commits the phase file. No assertion in those tests reads the index or
counts commits; the plan confirms that per file.

### Which tests change, and why

| File | Sites | What they use it for | Change |
|---|---|---|---|
| `tests/unit/test_v2_plan_ops.py` | 15 | 9 behaviour tests of `tick`/`complete_phase` (`:494-600`, `:715`); 6 self-review fixtures (`:837-1117`, `:1831`) | behaviour tests move onto the helper, with `RecordRefusedError` / the engine's wording (R5); fixtures change the import only |
| `tests/unit/test_journal_cmd.py` | 10 | set up a completed or ticked phase for `fr journal check --require-reviews` | import only; the fixtures' tasks are empty or single-step, so the refactor gate is inert (`record/gates.py:40`) |
| `tests/unit/test_plan_ops.py` | 2 + 4 | 2 placement fixtures (`:291`, `:317`); 3 byte-identity tests of a tick and a completion calling `plan_ops.tick`/`complete_phase` as attributes (`:607-665`) | fixtures change the import; byte-identity tests move onto the helper (R5) |
| `tests/integration/test_v2_full_lifecycle.py` | 2 | an end-to-end plan lifecycle | import only, unless the refactor gate refuses a task (R4) |
| `tests/unit/test_run_cli.py` | 1 | fixture (`:6382`) | import only |
| `tests/unit/test_run_idle.py` | 1 | fixture (`:145`) | import only |

`test_tripwire_tick_source_neutral.py` is about `fr_dispatch.tick`, a different function,
and does not change.

Expectation changes the move brings, stated so a reviewer can check them:

- Error type: `PlanEditError` → `RecordRefusedError`, or the `TickItem` validation error
  for a skip without a note.
- Wording: "not found in any phase" → "unknown tick id … no such step in the plan";
  "manual; --note is required" → "manual; completing it needs a note"; the unticked
  message keeps "unticked steps".
- Write order: a refused call now leaves the file untouched (R6), where the old path
  could leave a written file and then raise from the re-parse.
- A completion now runs the refactor gate (R4).
- A write now commits, where it only staged.

### The tripwire

`tests/unit/test_tripwire_plan_ops_tick_retired.py` walks every `*.py` under `packages/`
and `tests/` with `ast`. It fails on `from fr.plan_ops import tick` /
`complete_phase` (alias or not), on `plan_ops.tick` / `plan_ops.complete_phase` attribute
access where `plan_ops` is bound to `fr.plan_ops`, and on `fr.plan_ops` defining either
name. It also checks it would see a planted violation, so an empty walk cannot pass. It
is marked `own_artifacts`, because it reads this checkout's files.

### Acceptance

One row, `plan-state-written-by-record-engine`: a plan's step ticks and phase
completions are written only by the record engine, validated whole before any byte
lands. Levels: the tripwire (R2) and the byte-identical refusal test (R6). Status
`not-implemented` at brainstorm; `ci` once both tests are in CI.

## Design shape

```text
packages/fr/src/fr/
  plan_ops.py                 - tick(), complete_phase()     (R1: no caller left)
  record/apply.py             ~ _check_plan_parses docstring  (R8)
  commands/plan_cmd.py          unchanged: already builds a StepRecord → apply_record (R7)

tests/
  plan_state.py               + tick(), complete_phase() → StepRecord → apply_record (R3)
  unit/test_tripwire_plan_ops_tick_retired.py
                              + ast ban on the retired names (R2)
  unit/test_v2_plan_ops.py    ~ behaviour tests onto the engine; fixtures re-import (R5)
  unit/test_plan_ops.py       ~ byte-identity tests onto the engine (R5) + refusal leaves bytes (R6)
  unit/test_journal_cmd.py    ~ import only
  unit/test_run_cli.py        ~ import only
  unit/test_run_idle.py       ~ import only
  integration/test_v2_full_lifecycle.py  ~ import only (R4 if the gate refuses)

before:  test ──► plan_ops.tick ──► write ──► re-parse ──► stage
after:   test ──► plan_state.tick ──► StepRecord ──► apply_record
                                         overlay ─► refactor gate ─► scratch parse ─► write ─► commit
```

## Verification

strategy: none
gate: developer

Nothing installed changes: `fr plan edit` already uses the engine (R7). The suite in this
PR's CI is the proof: the re-pointed behaviour tests, the byte-identical refusal test and
the tripwire. No Test Plan: no behaviour exists that only a released build can show.

## Implementation Plans

- `docs/superpowers/plans/2026-11-28-retire-plan-ops-tick/` (written at the `plan` step).
