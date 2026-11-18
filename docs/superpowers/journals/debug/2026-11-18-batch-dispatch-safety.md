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
