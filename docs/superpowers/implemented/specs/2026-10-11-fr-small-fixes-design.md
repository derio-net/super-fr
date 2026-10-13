# fr small fixes: tracker close state, models errors, skill column count

Triage batch `fr-small-fixes`: four small, independent fixes delivered as one PR
(super-fr#1102, #1057, #1055, #1066).

## Background

- **#1102.** `GithubTracker.transition(item, "done")`
  (`packages/fr/src/fr/tracker/github.py:114`) calls
  `edit_issue_state(repo, number, state="closed")`. `RealGhClient`,
  `RealGlabClient` and `RealGhRestClient` accept only `OPEN`/`CLOSED` and raise
  `ValueError` on anything else, so moving any tracker item to `done` raises. The
  existing test passed only because `FakeGhClient.edit_issue_state`
  (`tests/unit/fakes.py:190`) stores whatever string it is given.
- **#1057.** `fr.bindings.probe._NOT_FOUND` (`probe.py:49`,
  `ProviderModelNotFoundError:[^"\\\n]*`) stops only at a quote, backslash or
  newline. OpenCode wraps the error as `Cause([Fail(ProviderModelNotFoundError: …?)])`,
  so the dead-binding reason `fr models check` shows ends in `)]))`. The verdict is
  correct; only the displayed reason is wrong. The captured fixture
  `tests/fixtures/bindings/opencode-run-not-found.stderr` already holds this shape.
- **#1055.** `fr.models.load_models` (`models.py:56`) raises `ModelsError` on a
  wrong structure and lets `yaml.YAMLError` escape on unparseable YAML. No caller
  catches either. `fr run start` saves the run and only then calls
  `_orchestrator_model_notice` → `_resolved_model` → `load_models`, so a corrupt
  `models.yaml` prints a traceback after the run was already started. `fr run
  advance` and every `fr models` command crash the same way.
- **#1066.** The fr-triage skill (canonical and both generated mirrors, line 101)
  and the `fr triage board` command's docstring
  (`commands/triage_kanban_cmd.py:502`) say "six lifecycle columns".
  `fr.triage.kanban.COLUMN_TITLES` has seven (Partial was added by gh#985).

## Requirements

R1. Moving a tracker item to `done` on the GitHub tracker closes its Issue through the client's `CLOSED` state, without raising.
R2. The test fake's `edit_issue_state` accepts only `OPEN` and `CLOSED`, as the real clients do, and raises `ValueError` on any other state.
R3. A dead binding's reason, as `fr models check` and the `fr run` notices show it, ends at the provider's own message and does not carry the closing brackets of the wrapper OpenCode prints around it.
R4. A models config that is not valid YAML is reported as a `ModelsError` that names the file, just like a structurally invalid one.
R5. When `fr run start` reads the models config (a harness is detected), a corrupt one still starts the run, exits 0 and prints one warning line naming the file and the problem instead of a traceback.
R6. When `fr run advance`, `fr run resolve`'s chained advance or a `fr models …` command reads the models config, a corrupt one is refused with one `fr: <path>: <problem>` line and exit 2 instead of a traceback; after `fr run resolve --record` has applied its record, that line says the record was applied and only the advance after it was refused. A corrupt config is never read as "no bindings". Where no harness is detected, nothing reads the config and behaviour is unchanged.
R7. The fr-triage skill names every board column by its title and states no column count, and the `fr triage board` docstring states neither a count nor the titles. A unit test reads the titles live from `COLUMN_TITLES` and fails when the skill's board paragraph leaves one out or states a column count, so a column added or renamed later breaks CI until the skill catches up.

## Design

### A. Tracker close (R1, R2)

`tracker/github.py` passes `state="CLOSED"`. `FakeGhClient.edit_issue_state`
raises `ValueError(f"unknown issue state: {state!r}")` for anything but
`OPEN`/`CLOSED`, matching `RealGhClient`. The tracker's done test asserts the
recorded call carries `CLOSED`. Any other test that leaned on the lenient fake is
corrected to pass a real state.

### B. Dead-binding reason (R3)

`classify` trims the matched reason: after the `_NOT_FOUND` match, strip a
trailing run of `)`, `]` and whitespace characters. The regex is left alone, so a
parenthesis inside the provider's own message survives. A unit test feeds
`classify` the captured `opencode-run-not-found.stderr` (and a line shaped like the
issue's `…?)]))`) and asserts the reason ends in `?`, and the hint is unchanged.

### C. Corrupt models config (R4–R6)

- `load_models` catches `yaml.YAMLError` and raises
  `ModelsError(f"{path}: not valid YAML: <first line of the error>")`.
- `fr run start`: the post-save `_orchestrator_model_notice` and `_binding_health`
  calls are wrapped so that a `ModelsError` prints one yellow
  `warning: <message> — model bindings ignored for this notice` line. The run
  stays started and the command exits 0.
- `fr run advance` (and the advance `resolve` chains), plus the `fr models`
  commands, turn a `ModelsError` into `fr: <message>` on stderr and exit 2. Catch
  it once at each command's entry rather than at every `load_models` call, so the
  brief's `unbound_tiers` never reads a broken config as unbound.
- `fr run resolve --record` is the exception to "at the entry": the record is
  applied and committed before `_advance_chain` reads the config, and
  `_advance_after_record`'s contract is that a failure after the apply says so.
  The `ModelsError` is caught inside `_advance_after_record` and printed as
  `record applied; the advance after it was refused: fr: <path>: <problem>`, exit 2,
  like that function's existing refusals, so nobody re-applies the record.
- No new load is added: with no harness detected, `_resolved_model` and
  `_binding_health` read nothing today, and that stays true.

### D. Board columns (R7)

The columns are moving under this change: open PRs add columns (#1107 adds
"Needs you · start" and "Needs you · review", nine in all) and rename the skill
paragraph's lead (#1151: `**The board:**` → `**Batches:**`). So nothing here
hard-codes either:

- The skill's board sentence reads "a live Kanban of the batches across its
  columns (Proposed, Waiting, Running, PR open, Closing out, Partial, Done)",
  naming the titles as they are on `main` when this PR is cut, with no count.
- The `fr triage board` docstring says "one card per batch in its lifecycle
  column (`fr.triage.kanban.COLUMN_TITLES`)", naming no count and no titles, so it
  cannot drift.
- The tripwire imports `COLUMN_TITLES` at test time, never a copied list. It
  finds the skill's board paragraph by its content (the line containing
  "`fr triage board` writes `board.html`"), not by its bold lead. It asserts
  every title appears there, and that no `<number-word or digit> (lifecycle )?columns`
  phrase does. Whichever of this PR and a column-changing PR merges second goes
  red in CI until the skill lists the new titles. That is the point.
- Run `scripts/sync-opencode.py` and `scripts/sync-hermes.py` to regenerate the
  mirrors. The edit lengthens an existing line, so the SKILL.md line cap is
  unaffected.

## Verification

strategy: none
- tracker-done-closes-issue: none — unit tests in CI exercise the tracker against the strict fake; no installed build is needed to show it.
- models-dead-reason-trimmed: none — `classify` is pure and the captured OpenCode fixture is its input; CI's unit tests prove it.
- models-corrupt-config-reported: none — CLI tests drive `fr run start`/`advance`/`resolve --record`/`fr models` over a corrupt config in CI.
- triage-skill-board-columns: none — a unit tripwire compares the skill text to `COLUMN_TITLES`.

## Non-goals

- Making the real clients case-insensitive: the protocol's states are `OPEN`/`CLOSED`.
- Any change to the probe verdict logic: only the displayed reason.
- Repairing a corrupt models.yaml automatically.
- `fr triage batch dispatch`/`drive`, which also read models.yaml (`triage_batch_cmd.py` `_orchestrator`): operator decision d1 named run start, advance, resolve's chained advance and `fr models`. Triage is left as it is, and is listed for the operator at PR review.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-11-fr-small-fixes | `derio-net/super-fr` | `2026-10-11-fr-small-fixes` | — |
