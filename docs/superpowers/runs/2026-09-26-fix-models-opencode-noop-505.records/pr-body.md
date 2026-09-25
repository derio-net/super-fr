# Fix #505: distinguish absent OpenCode agent files from idempotent applies

## Summary

`materialize_agents` now returns the count of matching tier-agent files separately from its changes. `fr models apply --harness opencode` preserves the no-files message only when no matching files exist; otherwise an unchanged set reports `<n> agent files already up to date`. Added independent regression coverage for both outcomes and bumped the package/plugin version from 4.22.0 to 4.22.1.

- Spec: `docs/superpowers/specs/2026-09-26-models-opencode-noop-report-design.md`
- Plan: `docs/superpowers/plans/2026-09-26-models-opencode-noop-report`
- Issue: https://github.com/derio-net/super-fr/issues/505

## Operator decisions

- Count only OpenCode agent files discovered by `materialize_agents`; unrelated files do not count.
- The focused models command/tests are sufficient for the post-merge Test Plan.

## Verification

- Focused tests: 25 passed (`tests/unit/test_opencode_agents_materialize.py`, `tests/unit/test_models_cmd.py`).
- Ruff check and format, mypy, artifact validation, acceptance check, and version sync passed.
- Full suite: 5,458 passed and 97 skipped on the first run, with one unrelated transcript fixture failure; an isolated rerun reproduced it. A second full run also had a test subprocess timeout in `test_suite_isolation_inherited_columns.py`. Full logs and gate results: `docs/superpowers/runs/2026-09-26-fix-models-opencode-noop-505.records/full-suite.log`.

## Operator gates

- Brainstorm questions were answered by the operator. OpenCode cannot mechanically verify the answer from a session transcript.

## Manual phases

None.

## Test Plan

Post-merge, run the focused models command/tests against the merged branch.

## Acceptance debt

`fr acceptance status --brief`: unchanged repository-wide debt — 205 ci, 23 skipped, 9 not-implemented, 1 scheduled.

`fr acceptance check --added-since origin/main`: no acceptance rows added.

## Ready checklist

- [ ] CI green
- [ ] Explicit review approved
- [ ] No commits since review approval

## Findings

No unresolved in-scope findings. The phase-1 review finding about seeding the positive-case fixture was fixed and re-reviewed in the same branch.

## Out-of-scope findings

None.

## Proportionality

202 lines changed against an estimate of 220 (0.9×). `fr plan proportionality` reports `.claude-plugin/marketplace.json` as an out-of-plan touch; it is the generated version synchronization artifact required by the patch bump.

## Cost

Usage was not observable in this OpenCode run; `fr run cost` reports no captured usage. No dollar amount is claimed.
