<!-- fr:journal-schema=4 -->
# Journal: 2026-11-18-batch-dispatch-safety

<!-- fr:journal kind=repro scope=debug id=a368515f54ab created=2026-11-18T12:15:40+00:00 -->
### a368515f54ab · repro · #1499: a raising existing_dispatches degrades to an empty snapshot and tick submits anyway

packages/fr-dispatch/src/fr_dispatch/__init__.py (dedup snapshot block): on exception, existing = set(); every item then looks undispatched and is submitted. Pinned as intended behaviour by tests/unit/test_tick_workitem.py::test_a_raising_existing_dispatches_degrades_to_an_empty_snapshot (asserts 1 dispatch).

<!-- fr:journal kind=repro scope=debug id=19afb9cd6fd8 created=2026-11-18T12:15:43+00:00 -->
### 19afb9cd6fd8 · repro · #1501: cncd build_ingest_payload follows plan-folder symlinks into the payload

packages/fr-cncd/src/fr_cncd/runner.py build_ingest_payload: {p.name: p.read_text() for p in plan.dir.iterdir() if p.is_file()} — is_file() and read_text() both follow symlinks, so a symlink in the plan folder ships the target's content (any file on the dispatching host) to the cncd server.

<!-- fr:journal kind=hypothesis scope=debug id=3ee30c3d4daa created=2026-11-18T12:15:45+00:00 -->
### 3ee30c3d4daa · hypothesis · Two independent root causes, not one

#1499 is a fail-open error policy in the generic tick (dedup lookup failure treated as 'nothing dispatched'). #1501 is an input-trust defect in the cncd adapter (filesystem reads follow links). Different packages, different code paths; fixing one does not touch the other. The batch rule requires stopping to ask before fixing either.

<!-- fr:journal kind=decision scope=debug id=6d5ec886e0d4 created=2026-11-18T13:07:53+00:00 decided_by=operator -->
### 6d5ec886e0d4 · decision · Operator: fix both root causes in the one batch PR; a plan-folder symlink refuses the cncd dispatch

<!-- fr:journal kind=root-cause scope=debug id=244b6f50f92a created=2026-11-18T13:09:09+00:00 -->
### 244b6f50f92a · root-cause · #1499: tick reads a failed dedup lookup as an empty one; #1501: build_ingest_payload follows symlinks via is_file()/read_text()

Two causes (operator accepted both in one PR). 1) fr_dispatch.tick sets existing=set() when runner.existing_dispatches raises, so every item looks new and is submitted again. 2) fr_cncd.runner.build_ingest_payload filters with Path.is_file() and reads with Path.read_text(); both follow symlinks, so a link in a plan folder sends its target's content to the cncd server.

<!-- fr:journal kind=finding scope=debug id=4093a821b62c created=2026-11-18T13:20:49+00:00 state=fixed -->
### 4093a821b62c · finding [fixed] · Fixed both: tick returns early on a failed dedup lookup; cncd refuses a symlinked plan-folder entry

fr_dispatch.tick: a raising existing_dispatches fails every item with 'dedup fetch failed' (metric reason dedup) and returns before any dispatch or stamp, like the preflight blocker. fr_cncd.runner._plan_folder_files: raises CncdError naming any symlink before reading; tick reports it as that item's backend_error. Pinned by tests/unit/test_tick_workitem.py::test_a_raising_existing_dispatches_submits_nothing_this_tick (replaces the test that pinned the fail-open) and tests/integration/test_cncd_stub_server.py::test_a_symlink_in_the_plan_folder_refuses_the_dispatch; both failed before the fix (commit 21b50d235).

<!-- fr:journal kind=review scope=debug id=f19a115c74e9 created=2026-11-18T13:22:00+00:00 -->
### f19a115c74e9 · review · Independent adversarial review: no defects in either fix

Reviewer (separate context, read-only) found no path from a failed dedup lookup to a submit, and the early return matches the preflight-blocker shape (one failure and metric per item, one heartbeat, skipped=len(items)). Below-threshold notes, not fixed here: a runner that swallows its own lookup error and returns an empty set (possible in fr_herdr _list_tabs, unverified) still looks empty to tick; a check-then-read race and hardlinks need write access to the checkout; a symlinked plan dir itself is not checked. None is in this batch's scope.
