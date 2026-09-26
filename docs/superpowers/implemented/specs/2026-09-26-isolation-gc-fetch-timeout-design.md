# Isolation GC fetch timeout

## Problem

`IsolationTarget._reap_hazard` runs `git fetch origin <default>` through the
untimed `run` helper. A remote that hangs can therefore block `fr isolation
gc` indefinitely. The default-branch lookup and verify-merge fetches already
use `_run_network`, which applies the isolation network timeout (#652,
f4ecf915).

## Design

Route `_reap_hazard`'s fetch through `_run_network`, retaining its worktree
cwd and existing nonzero-return behavior: a failed or timed-out fetch remains
an `unverifiable` reap hazard, so gc skips the workspace rather than treating
unknown remote state as safe to reap. The existing local-first short circuit
and no-`origin` behavior remain unchanged.

Add a regression test that proves `_reap_hazard` uses `_run_network` for the
fetch and still reports an `unverifiable` hazard when the network call fails.

## Acceptance

An isolation gc candidate whose origin fetch hangs is bounded by the configured
network timeout and is not reaped on the resulting fetch failure.

## Test Plan

- Run the targeted isolation network-timeout tests, including the new
  `_reap_hazard` regression.
- Update the acceptance matrix with the regression test reference and set the
  row to `ci` when the test lands.
- Run the full test suite after merge.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-26-isolation-gc-fetch-timeout | `derio-net/super-fr` | `2026-09-26-isolation-gc-fetch-timeout` | — |
