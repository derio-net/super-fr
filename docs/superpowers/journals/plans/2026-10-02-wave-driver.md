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

<!-- fr:journal kind=decision scope=plan id=p2-post-merge-runs-in-gitseam created=2026-10-02T19:49:22+00:00 phase=2 -->
### p2-post-merge-runs-in-gitseam · decision · post_merge's process starts in gitseam.Checkout.run_command, invoked by the command layer (phase 2)

Spec §B says the post_merge subprocess runs in the command layer, but the §3.J tripwire
(test_forge_adapter_batch_ops.py) bans `subprocess` from every batch module, triage_batch_cmd.py
included. The command decides and invokes; the process starts in gitseam, the one module allowed
subprocess, next to the other repo-declared commands (version.set/relock). Still an argument list,
never a shell. fast_forward() and released_since() live there too.

<!-- fr:journal kind=decision scope=plan id=p2-default-driven-set created=2026-10-02T19:49:22+00:00 phase=2 -->
### p2-default-driven-set · decision · drive drives the batches with a wave by default (else all), or the ids named (phase 2)

Without a selection rule the driver would start close-outs for every batch merged before it existed
(no closeout event). The default set is every batch with a `wave` (all batches when none has one);
positional ids name others. The in-flight cap counts the driven set.

<!-- fr:journal kind=decision scope=plan id=p2-r4-all-checks-from-facts created=2026-10-02T19:49:22+00:00 phase=2 -->
### p2-r4-all-checks-from-facts · decision · R4's "else all checks" reads the re-collected statusCheckRollup counts (phase 2)

checks_verdict uses GhClient.pr_required_checks when the branch has any required check, else the
collected PullRequest.checks counts (facts are re-collected at the start of every pass), and a repo
whose services resolve `ci none` is green on non-draft alone. No new GhClient method. merge_ready
still gates on required checks only, so the driver only calls it when its own verdict is green.

<!-- fr:journal kind=decision scope=plan id=p2-warned-and-exit-codes created=2026-10-02T19:49:22+00:00 phase=2 -->
### p2-warned-and-exit-codes · decision · failing-CI warnings are remembered per driver process; plan mode exits 0; a merge stop exits 1 (phase 2)

R6 forbids driver state on disk, so the set of head shas already warned lives in the running driver
(loop mode warns once per head; each --once invocation reports it again). Without --yes the verb
prints one pass's plan and exits 0 in either mode. A MergeStopError while merging (a forge refusal,
a conflict) exits 1, as `batch merge` does; a runner preflight refusal exits 2 on first sight.

<!-- fr:journal kind=decision scope=plan id=p2-closeout-event-fields created=2026-10-02T19:49:22+00:00 phase=2 -->
### p2-closeout-event-fields · decision · CloseoutEvent gains optional run and archive (the housekeeping branch) (phase 2)

The command reads the run cursor on the fast-forwarded default branch at close-out time; recording
the run id and the housekeeping branch (fr.run.closeout's naming, mirrored in batch_drive) lets the
archive step attribute and detect the merged archive PR exactly (list_prs_by_head on that head), since
facts.prs carries only open unlinked PRs.

<!-- fr:journal kind=discovery scope=plan id=p2-collect-last-dispatch created=2026-10-02T19:49:22+00:00 phase=2 -->
### p2-collect-last-dispatch · discovery · collect only looked up batch PRs whose LAST event was a dispatch (phase 2)

With post_merge and closeout events after the dispatch, collect would stop looking a merged batch's
PR up by head. collect_into (shared by `collect` and every driver pass) now uses the last dispatch
unless the batch's last event is a cancel.

<!-- fr:journal kind=decision scope=plan id=p2-herdr-tests-location created=2026-10-02T19:49:22+00:00 phase=2 -->
### p2-herdr-tests-location · decision · herdr characterisation tests live in tests/unit/test_fr_herdr_closeout.py; fr_herdr unchanged (phase 2)

pytest's testpaths is `tests` and no packages/fr-herdr/tests exists, so the characterisation tests
sit beside test_fr_herdr_runner.py. They pass against unchanged fr_herdr: agent_name is stable and
distinct per batch, can_dispatch ignores payload.kind, dispatch takes --cwd and --model from the payload.

<!-- fr:journal kind=finding scope=plan id=p2-closeout-state-archived-unreachable created=2026-10-02T19:49:22+00:00 phase=2 state=open review_scope=out -->
### p2-closeout-state-archived-unreachable · finding [open] (reviewer: out of scope) · batch list's close-out column can never read `archived` (phase 2)

closeout_state (phase 1) looks for a MERGED chore/closeout-<branch> PR in facts.prs, but collect stores
only OPEN unlinked PRs there, and the housekeeping branch is usually chore/archive-<plan>. The driver
does not depend on it (it reads list_prs_by_head on the recorded archive head); the list column needs
the same forge read or a recorded archive event.

<!-- fr:journal kind=finding scope=plan id=rf-4-resolved-2 created=2026-10-02T19:49:22+00:00 phase=2 state=fixed resolves=rf-4 -->
### rf-4-resolved-2 · finding [fixed] · resolves rf-4: merge_ready uses required checks only, not the R4 'else all checks / ci none' rule (phase 2)

the driver applies R4 itself: checks_verdict (required checks, else the collected all-checks counts, ci none on non-draft alone) gates every merge before merge_ready is called

<!-- fr:journal kind=finding scope=plan id=rf-5-resolved-2 created=2026-10-02T19:49:22+00:00 phase=2 state=fixed resolves=rf-5 -->
### rf-5-resolved-2 · finding [fixed] · resolves rf-5: fr-triage SKILL.md still says to create judgements.yaml with schema: 2 (phase 2)

fr-triage SKILL.md now teaches schema 3 (first-run line and the example), pinned by test_the_skill_teaches_schema_3_and_batches

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-02T19:49:22+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

red-only task: the pass's tests, no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-02T19:49:22+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

cleaned in the green commits: closeout_event and housekeeping_branch are shared by the pure pass and the command, and action_line/summary_line are the one formatter for --once and loop mode; nothing duplicated is left

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-02T19:49:22+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

the lock is one context manager and kill-safety needed no new code beyond the recorded post_merge/closeout events the pass already reads; nothing to fold

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-10-02T20:31:27+00:00 phase=2 -->
### review-p2 · review · phase 2 review: 16 findings (15 in scope, fixed; 1 out of scope) (phase 2)

Independent Opus review of ab3c4fea..HEAD against R2-R8, R13, R14 and design B and C. The operator boundary held for draft and readiness (nothing readies, approves or un-drafts a PR), but rg-1, rg-2 and rg-3 were reproduced with the suite's own fakes: a dependent dispatched behind a merge that did not land, a moved head merged unverified, and the cap and dependencies scoped to the selection. All 15 in-scope findings were fixed in 920419d0, 40c0c6e2 and 83885a18 with command-level tests; the whole suite passed (7757 passed, 97 skipped).

<!-- fr:journal kind=finding scope=plan id=rg-1 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-1 · finding [open] (reviewer: in scope) · A dependent is dispatched in the same pass even when its dependency's merge did not land (phase 2)

drive_pass marks planned merges merged before dispatch; _act only checks the cap; merge_ready can return updated/pending/failing/draft. Breaks R3 and R13's summary.

<!-- fr:journal kind=finding scope=plan id=rg-2 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-2 · finding [open] (reviewer: in scope) · A head that moves between the snapshot and the merge is merged (phase 2)

plan_queue re-reads pr_view and pins to the new head; action.head is unused; with no required checks nothing is verified on the new head. Breaks R4.

<!-- fr:journal kind=finding scope=plan id=rg-3 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-3 · finding [open] (reviewer: in scope) · The in-flight cap and dependency resolution only see the selected batches (phase 2)

Unselected dispatched batches do not count against --max-inflight; a merged dependency outside the selection blocks its dependent forever.

<!-- fr:journal kind=finding scope=plan id=rg-4 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-4 · finding [open] (reviewer: in scope) · Zero registered checks reads as green (phase 2)

After the driver's own update push, or a PR whose CI is not queued, a repo with no required checks merges with no CI; MergeStopError killed the loop.

<!-- fr:journal kind=finding scope=plan id=rg-5 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-5 · finding [open] (reviewer: in scope) · ci none is read from the clone's working tree, not the default branch (phase 2)

A feature branch declaring ci none would let the driver merge on non-draft alone.

<!-- fr:journal kind=finding scope=plan id=rg-6 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-6 · finding [open] (reviewer: in scope) · An archive PR attributed only by its files is never seen as merged (phase 2)

The batch counts as closing forever and --once never exits 0.

<!-- fr:journal kind=finding scope=plan id=rg-7 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-7 · finding [open] (reviewer: in scope) · drive.lock takeover has a race and an empty-file window (phase 2)

Unwritten lock read as stale; two starters can unlink the same lock; unlink without ownership check; spec sentence about collect was wrong.

<!-- fr:journal kind=finding scope=plan id=rg-8 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-8 · finding [open] (reviewer: in scope) · Close-out model resolution ignores the repo's models.yaml in single-repo mode (phase 2)

_launch used path_of (None by default) where dispatch_batch uses the checkout path.

<!-- fr:journal kind=finding scope=plan id=rg-9 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-9 · finding [open] (reviewer: in scope) · The release-commit check is date-based (phase 2)

Another merge's release satisfied it; unknown merged_at made the close-out due at once.

<!-- fr:journal kind=finding scope=plan id=rg-10 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-10 · finding [open] (reviewer: in scope) · A close-out preflight refusal stops merges and dispatches when no close-out is due (phase 2)

Every merged batch without a closeout event was probed on every pass.

<!-- fr:journal kind=finding scope=plan id=rg-11 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-11 · finding [open] (reviewer: in scope) · Only-blocked work exits 0 and ends the loop (phase 2)

Hides blocked work from a scheduler; R7 ambiguous.

<!-- fr:journal kind=finding scope=plan id=rg-12 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-12 · finding [open] (reviewer: in scope) · Archive attribution by head is broader than the spec allows (phase 2)

Any event.archive head was accepted without a file check.

<!-- fr:journal kind=finding scope=plan id=rg-13 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-13 · finding [open] (reviewer: in scope) · The executor's declared departures need a spec correction (phase 2)

post_merge starts in gitseam, the default selection, and the no --yes exit code were not in the spec.

<!-- fr:journal kind=finding scope=plan id=rg-14 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-14 · finding [open] (reviewer: in scope) · fr-triage skill dropped 'Never act on the forge unasked'; AGENTS.md says schema 2 and 3 (phase 2)

Docs the phase edited were inconsistent.

<!-- fr:journal kind=finding scope=plan id=rg-15 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=in -->
### rg-15 · finding [open] (reviewer: in scope) · The tests miss the command-level paths behind rg-1 to rg-3 (phase 2)

World defaults hid the all-checks fallback; moved head, held merge, outside-selection dependency, lock races and file-attributed archive were untested.

<!-- fr:journal kind=finding scope=plan id=rg-16 created=2026-10-02T20:31:27+00:00 phase=2 state=open review_scope=out -->
### rg-16 · finding [open] (reviewer: out of scope) · A close-out tab that ended before a restart is not seen, so a second close-out could start (phase 2)

The spec's own accepted design limit (design C), not an implementation error.

<!-- fr:journal kind=finding scope=plan id=rg-1-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-1 -->
### rg-1-resolved · finding [fixed] · resolves rg-1: A dependent is dispatched in the same pass even when its dependency's merge did not land (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-2-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-2 -->
### rg-2-resolved · finding [fixed] · resolves rg-2: A head that moves between the snapshot and the merge is merged (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-3-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-3 -->
### rg-3-resolved · finding [fixed] · resolves rg-3: The in-flight cap and dependency resolution only see the selected batches (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-4-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-4 -->
### rg-4-resolved · finding [fixed] · resolves rg-4: Zero registered checks reads as green (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-5-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-5 -->
### rg-5-resolved · finding [fixed] · resolves rg-5: ci none is read from the clone's working tree, not the default branch (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-6-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-6 -->
### rg-6-resolved · finding [fixed] · resolves rg-6: An archive PR attributed only by its files is never seen as merged (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-7-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-7 -->
### rg-7-resolved · finding [fixed] · resolves rg-7: drive.lock takeover has a race and an empty-file window (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-8-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-8 -->
### rg-8-resolved · finding [fixed] · resolves rg-8: Close-out model resolution ignores the repo's models.yaml in single-repo mode (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-9-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-9 -->
### rg-9-resolved · finding [fixed] · resolves rg-9: The release-commit check is date-based (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-10-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-10 -->
### rg-10-resolved · finding [fixed] · resolves rg-10: A close-out preflight refusal stops merges and dispatches when no close-out is due (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-11-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-11 -->
### rg-11-resolved · finding [fixed] · resolves rg-11: Only-blocked work exits 0 and ends the loop (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-12-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-12 -->
### rg-12-resolved · finding [fixed] · resolves rg-12: Archive attribution by head is broader than the spec allows (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-13-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-13 -->
### rg-13-resolved · finding [fixed] · resolves rg-13: The executor's declared departures need a spec correction (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-14-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-14 -->
### rg-14-resolved · finding [fixed] · resolves rg-14: fr-triage skill dropped 'Never act on the forge unasked'; AGENTS.md says schema 2 and 3 (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-15-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=fixed resolves=rg-15 -->
### rg-15-resolved · finding [fixed] · resolves rg-15: The tests miss the command-level paths behind rg-1 to rg-3 (phase 2)

Fixed in 920419d0 / 40c0c6e2 / 83885a18 with tests.

<!-- fr:journal kind=finding scope=plan id=rg-16-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=open resolves=rg-16 out_of_scope=true -->
### rg-16-resolved · finding [out-of-scope] · resolves rg-16: A close-out tab that ended before a restart is not seen, so a second close-out could start (phase 2)

The spec's accepted design limit, recorded in design C; not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p2-closeout-state-archived-unreachable-resolved created=2026-10-02T20:31:27+00:00 phase=2 state=open resolves=p2-closeout-state-archived-unreachable out_of_scope=true -->
### p2-closeout-state-archived-unreachable-resolved · finding [out-of-scope] · resolves p2-closeout-state-archived-unreachable: batch list's close-out column can never read `archived` (phase 2)

Raised by the executor as not caused by phase 2; the archived outcome became reachable through rg-6's fix (the close-out event now carries the archive PR number).

<!-- fr:journal kind=decision scope=plan id=p3-group-scope-shape created=2026-10-02T20:44:23+00:00 phase=3 -->
### p3-group-scope-shape · decision · A group is Scope(kind="group", target="A/B,C/D", repos=(...)); one repo after de-dup collapses to kind repo (phase 3)

Scope gains an optional `repos` tuple and a `Scope.group` constructor (sorted, case-insensitive de-dup). The scope parser `_group_scope` lives beside `_scope` and is shared by every verb; a group that collapses to one repo is a plain repo scope. Facts.repos already is the group's repo list, so schema 4 only adds the `group` kind (a schema-3 file naming it is refused).

<!-- fr:journal kind=decision scope=plan id=p3-group-needs-every-checkout created=2026-10-02T20:44:23+00:00 phase=3 -->
### p3-group-needs-every-checkout · decision · drive over a group requires --checkout for EVERY repo of the group, not only those with batches (phase 3)

The spec says it refuses "a group repo that has no mapping before anything runs"; the stricter reading is taken so a repo gaining a batch later never stops a running driver. A --checkout naming a repo outside the group is refused too.

<!-- fr:journal kind=discovery scope=plan id=p3-cap-already-shared created=2026-10-02T20:44:23+00:00 phase=3 -->
### p3-cap-already-shared · discovery · phase 2's cap already counts every batch in judgements, so it is shared across a group unchanged (phase 3)

Verified with a two-repo group (tests/unit/test_triage_scope_groups.py): one dispatch under --max-inflight 1, and a dispatched batch in one repo blocks the other's. Existing tests that asserted facts schema 3 are written now assert 4.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-02T20:44:23+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

red-only task: tests, no production code to clean
