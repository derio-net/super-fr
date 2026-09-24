# Flat Agent-Step Evidence Debt

## Background

Issue #605: `fr run check` and `fr run status` do not report evidence debt for
completed flat `kind: agent` steps such as `spec-review` and `deliver`. Their
unit key is `step/<id>`, which intentionally carries no state; completion is
stored on the corresponding `StepRecord.state`. `_unevidenced_units` currently
checks `units.unit_state(record, key) == "done"`, so it skips these completed
units even when evidence obligations are missing.

## Design

Keep the unit storage contract unchanged. When examining a flat step's unit,
determine completion from its parent `StepRecord.state`; retain unit-level state
lookup for grouped members, whose state is stored in the unit record. Continue
comparing the manifest's required evidence with evidence stored on the unit.
This preserves the existing debt wording and exit-code behavior: debt appears
in both status and check, but does not make check fail.

Regression coverage will exercise flat, completed agent steps with unmet
evidence through both CLI views, and establish that satisfying the obligations
removes the debt. Existing grouped-member tests must remain green.

## Test Plan

1. Add focused regression coverage proving `fr run check` and `fr run status`
   report `step/<id>` debt for a completed flat agent step whose evidence is
   missing; verify the check exit code remains unchanged.
2. Verify a flat step with all required evidence is not reported as debt, and
   run the relevant run-evidence tests plus the full test suite. At delivery,
   run the full suite in foreground chunks (the #607 delivery requirement),
   not as a backgrounded process.
3. Post-merge, create or use a run containing an unevidenced flat `kind: agent`
   step such as `spec-review` or `deliver`; confirm both `fr run check` and
   `fr run status` report it.

## Implementation Plans

| Plan | Repo | File | Depends on |
| --- | --- | --- | --- |
| 2026-09-25-flat-agent-step-evidence-debt | `derio-net/super-fr` | `2026-09-25-flat-agent-step-evidence-debt` | — |
