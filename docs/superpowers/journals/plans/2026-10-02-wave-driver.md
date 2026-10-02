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

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-10-02T19:18:10+00:00 phase=1 -->
### review-p1 · review · phase 1 review: 5 findings (3 in scope, fixed; 2 out of scope) (phase 1)

Independent review of afd59853..HEAD against the spec (R1, design A and B's extraction) and the plan: schema 1-3 reads and the stamp, dependency validation, the dispatch_batch and merge_ready extraction (behaviour-preserving; merge_ready never waits), tests. Focused triage tests passed in the reviewer's run. In-scope findings were fixed in 5eef69ad with tests.

<!-- fr:journal kind=finding scope=plan id=rf-1 created=2026-10-02T19:18:10+00:00 phase=1 state=open review_scope=in -->
### rf-1 · finding [open] (reviewer: in scope) · batch edit cannot clear after or wave (phase 1)

No way to pass an empty set or unset the wave on an edit (triage_batch_cmd.py batch_edit_command).

<!-- fr:journal kind=finding scope=plan id=rf-2 created=2026-10-02T19:18:10+00:00 phase=1 state=open review_scope=in -->
### rf-2 · finding [open] (reviewer: in scope) · closeout_state matches a future event by name; the branch is unreachable and untested (phase 1)

Batch.events had no closeout kind, so started and archived were dead code (batch.py closeout_state).

<!-- fr:journal kind=finding scope=plan id=rf-3 created=2026-10-02T19:18:10+00:00 phase=1 state=open review_scope=in -->
### rf-3 · finding [open] (reviewer: in scope) · merge_ready prints a duplicate 'merged' line (phase 1)

batch_merge.py: ctx.say after _land plus _merge's own line; one merge, two lines (R13).

<!-- fr:journal kind=finding scope=plan id=rf-4 created=2026-10-02T19:18:10+00:00 phase=1 state=open review_scope=out -->
### rf-4 · finding [open] (reviewer: out of scope) · merge_ready uses required checks only, not the R4 'else all checks / ci none' rule (phase 1)

The spec places the check rule in the driver pass (phase 2); merge_ready alone must not be used on a repo with no required checks.

<!-- fr:journal kind=finding scope=plan id=rf-5 created=2026-10-02T19:18:10+00:00 phase=1 state=open review_scope=out -->
### rf-5 · finding [open] (reviewer: out of scope) · fr-triage SKILL.md still says to create judgements.yaml with schema: 2 (phase 1)

A schema 2 file still loads and upgrades on the first write; skill updates are a later phase.

<!-- fr:journal kind=finding scope=plan id=rf-1-resolved created=2026-10-02T19:18:10+00:00 phase=1 state=fixed resolves=rf-1 -->
### rf-1-resolved · finding [fixed] · resolves rf-1: batch edit cannot clear after or wave (phase 1)

Fixed in 5eef69ad with tests.

<!-- fr:journal kind=finding scope=plan id=rf-2-resolved created=2026-10-02T19:18:10+00:00 phase=1 state=fixed resolves=rf-2 -->
### rf-2-resolved · finding [fixed] · resolves rf-2: closeout_state matches a future event by name; the branch is unreachable and untested (phase 1)

Fixed in 5eef69ad with tests.

<!-- fr:journal kind=finding scope=plan id=rf-3-resolved created=2026-10-02T19:18:10+00:00 phase=1 state=fixed resolves=rf-3 -->
### rf-3-resolved · finding [fixed] · resolves rf-3: merge_ready prints a duplicate 'merged' line (phase 1)

Fixed in 5eef69ad with tests.

<!-- fr:journal kind=finding scope=plan id=rf-4-resolved created=2026-10-02T19:18:10+00:00 phase=1 state=open resolves=rf-4 out_of_scope=true -->
### rf-4-resolved · finding [out-of-scope] · resolves rf-4: merge_ready uses required checks only, not the R4 'else all checks / ci none' rule (phase 1)

Phase 2's driver pass owns the check rule; not caused by phase 1.

<!-- fr:journal kind=finding scope=plan id=rf-5-resolved created=2026-10-02T19:18:10+00:00 phase=1 state=open resolves=rf-5 out_of_scope=true -->
### rf-5-resolved · finding [out-of-scope] · resolves rf-5: fr-triage SKILL.md still says to create judgements.yaml with schema: 2 (phase 1)

Skill and mirror updates ship with the phase that changes the driver; harmless until then.
