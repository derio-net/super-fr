# Journal: 2026-10-06-pickup-record-drift

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-06T09:08:28+00:00 -->
### repro-1 · repro · fr pickup drops ## Step record on a drifted cursor, silently

started_run, then a repo-override fr-goal.yaml gains a step after deliver; fr pickup --phase 1 exits 0 with no Step record section and nothing on stderr. Pinned by tests/unit/test_record_template.py::test_pickup_on_a_drifted_cursor_keeps_the_record_and_warns_once.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-10-06T09:08:44+00:00 -->
### rc-1 · root-cause · _run_unit_record uses the strict resolver; _record_section swallows its drift refusal

pickup_cmd._run_unit_record calls run_cmd._resolve_manifest_for_state, which raises _StepDriftError on step drift; _record_section's bare except Exception returns [] so the section disappears with no warning. Single cause: the lenient read-only resolver (_resolve_manifest_for_read, spec 2026-10-05 §B) was never applied to pickup, which only reads the cursor.

<!-- fr:journal kind=finding scope=debug id=f-1 created=2026-10-06T10:58:34+00:00 state=fixed -->
### f-1 · finding [fixed] · pickup reads the cursor with the lenient read-only resolver

pickup_cmd._run_unit_record now calls run_cmd._resolve_manifest_for_read: a step drift prints one stderr warning naming fr run reshape and the ## Step record section stays. Failing test first (test_pickup_on_a_drifted_cursor_keeps_the_record_and_warns_once), green after. Full suite: 8974 passed; 2 failures (test_install_marketplace_namespace purge, test_dispatch_lint_corpus) pass on rerun on both this branch and the base: load flakes under a 28-min contended run, not regressions.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-10-06T10:58:37+00:00 -->
### review-1 · review · Self-review of the diff: no in-scope findings

Read the diff end to end. Noted out of scope and left as is: a schema-version mismatch (not drift) still raises RunStateError, which _record_section still swallows silently. #988 is about step drift, and §B deliberately keeps schema mismatch as a refusal; the silent part could be its own follow-up.
