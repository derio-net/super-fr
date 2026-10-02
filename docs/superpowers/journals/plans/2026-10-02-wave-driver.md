# Journal: 2026-10-02-wave-driver

<!-- fr:journal kind=decision scope=plan id=p1-merge-ready-split created=2026-10-02T19:14:09+00:00 phase=1 -->
### p1-merge-ready-split · decision · merge_ready shares merge_one's helpers instead of copying its loop (phase 1)

merge_one was split into _open_head (state/draft/head checks) and _land (merge or push the update); merge_one keeps the blocking _checks waits, merge_ready (returns MergeAttempt: merged/updated/already-merged/draft/failing/pending) reads required checks once and never waits. All existing merge tests pass unchanged.

<!-- fr:journal kind=decision scope=plan id=p1-dispatch-batch-extract created=2026-10-02T19:14:09+00:00 phase=1 -->
### p1-dispatch-batch-extract · decision · dispatch_batch is the verbatim body of the dispatch command (phase 1)

dispatch_batch(target, facts, judgements, batch, *, to, checkout_path, repair, handle, reserved_version, yes) holds everything after the batch lookup; refusals stay typer.Exit with the verb's exit codes, so the driver catches typer.Exit. Existing dispatch tests pass unchanged.

<!-- fr:journal kind=discovery scope=plan id=p1-kind-features-deferred created=2026-10-02T19:14:09+00:00 phase=1 -->
### p1-kind-features-deferred · discovery · Judgement.kind and Judgements.features do not exist yet (phase 1)

Spec A/Test Plan 1 say kind and features load on any version, but they are R9 (a later phase) and the strict model has neither today. Phase 1 added only wave/after; the kind/features load-on-any-version test belongs with the phase that adds those fields.

<!-- fr:journal kind=discovery scope=plan id=p1-stamp-assertions-updated created=2026-10-02T19:14:09+00:00 phase=1 -->
### p1-stamp-assertions-updated · discovery · Existing tests that pinned schema 2 as the write stamp moved to 3 (phase 1)

Behaviour-preserving for dispatch/merge, but tests that asserted the write stamp (schema: 2) or that schema 3 is refused now assert 3 and refuse 4 (test_triage_batch_model, _verbs, _list, test_triage_model, test_triage_cli). closeout_state matches a future closeout event by name until the phase that adds CloseoutEvent.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-02T19:14:09+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

red-only task: tests, no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-02T19:14:09+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the green change was the smallest addition beside existing validators; check_dependencies/dependency_state sit next to check_open_membership, nothing duplicated to fold
