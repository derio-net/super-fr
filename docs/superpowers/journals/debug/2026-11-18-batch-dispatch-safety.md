<!-- fr:journal-schema=4 -->
# Journal: 2026-11-18-batch-dispatch-safety

<!-- fr:journal kind=repro scope=debug id=a368515f54ab created=2026-11-18T12:15:40+00:00 -->
### a368515f54ab · repro · #1499: a raising existing_dispatches degrades to an empty snapshot and tick submits anyway

packages/fr-dispatch/src/fr_dispatch/__init__.py (dedup snapshot block): on exception, existing = set(); every item then looks undispatched and is submitted. Pinned as intended behaviour by tests/unit/test_tick_workitem.py::test_a_raising_existing_dispatches_degrades_to_an_empty_snapshot (asserts 1 dispatch).
