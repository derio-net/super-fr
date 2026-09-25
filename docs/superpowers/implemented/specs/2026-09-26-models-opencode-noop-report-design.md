# Distinguish absent OpenCode agents from an idempotent apply

- **Issue:** [#505](https://github.com/derio-net/super-fr/issues/505)
- **Date:** 2026-09-26
- **Status:** designed

## Problem and goal

`fr models apply --harness opencode` currently prints `nothing to update (no
OpenCode agent files found)` whenever the materializer returns an empty
`changes` list. That list is empty both when no matching agent files exist and
when every discovered agent already matches the resolved configuration. The
second message is false: the files exist; the operation was simply idempotent.

Report the number of matching agent files considered independently from the
files changed. Preserve the existing missing-files message only when the count
is zero. When files were found and none need an update, report
`<n> agent files already up to date`.

The count includes only `.md` files in `opencode/agent/` whose filename suffix
matches a known phase tier. Unrelated files do not count. Both `fr models set`
and `fr models apply` share the reporting helper and must report the same
distinction.

## Design

`materialize_agents` returns a result containing `considered` and `changes`.
Increment `considered` only after a file's suffix identifies a supported tier;
the `changes` field retains existing reporting for successful rewrites and
unwritable agent files. The CLI uses `considered` when `changes` is empty to
distinguish the two no-op cases.

## Acceptance and test plan

- A missing agent directory or a directory with no matching tier agent reports
  `nothing to update (no OpenCode agent files found)`.
- One or more matching agent files already correct reports
  `<n> agent files already up to date` and does not rewrite them.
- Unrelated files are excluded from the considered count.
- Existing change/problem reporting and materialization behavior remain intact.
- Run focused tests in `tests/unit/test_opencode_agents_materialize.py` and
  `tests/unit/test_models_cmd.py`, then the full test suite and standard lint.
- Post-merge: run the focused models command/tests against the merged branch.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-26-models-opencode-noop-report | `derio-net/super-fr` | `2026-09-26-models-opencode-noop-report` | — |
