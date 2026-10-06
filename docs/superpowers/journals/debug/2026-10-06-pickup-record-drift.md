# Journal: 2026-10-06-pickup-record-drift

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-06T09:08:28+00:00 -->
### repro-1 · repro · fr pickup drops ## Step record on a drifted cursor, silently

started_run, then a repo-override fr-goal.yaml gains a step after deliver; fr pickup --phase 1 exits 0 with no Step record section and nothing on stderr. Pinned by tests/unit/test_record_template.py::test_pickup_on_a_drifted_cursor_keeps_the_record_and_warns_once.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-10-06T09:08:44+00:00 -->
### rc-1 · root-cause · _run_unit_record uses the strict resolver; _record_section swallows its drift refusal

pickup_cmd._run_unit_record calls run_cmd._resolve_manifest_for_state, which raises _StepDriftError on step drift; _record_section's bare except Exception returns [] so the section disappears with no warning. Single cause: the lenient read-only resolver (_resolve_manifest_for_read, spec 2026-10-05 §B) was never applied to pickup, which only reads the cursor.
