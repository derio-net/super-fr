# Journal: 2026-10-06-pickup-record-drift

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-06T09:08:28+00:00 -->
### repro-1 · repro · fr pickup drops ## Step record on a drifted cursor, silently

started_run, then a repo-override fr-goal.yaml gains a step after deliver; fr pickup --phase 1 exits 0 with no Step record section and nothing on stderr. Pinned by tests/unit/test_record_template.py::test_pickup_on_a_drifted_cursor_keeps_the_record_and_warns_once.
