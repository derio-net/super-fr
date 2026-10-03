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

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-10-02T20:49:38+00:00 phase=3 -->
### review-p3 · review · phase 3 review: 7 findings (4 in scope, fixed; 3 out of scope) (phase 3)

Independent review of 155eb479..HEAD against R15 and design H. The group scope, facts schema 4 (schema 3 still loads), the state-directory rule, the repeated-name refusal, per-repo collect with a failing repo skipped, and the shared cap were verified; 641 triage tests passed in the reviewer's run. In-scope findings were fixed in 76de055b.

<!-- fr:journal kind=finding scope=plan id=rh-1 created=2026-10-02T20:49:38+00:00 phase=3 state=open review_scope=in -->
### rh-1 · finding [open] (reviewer: in scope) · The drive refusal test cannot tell 'every group repo' from 'repos with batches' (phase 3)

The stricter rule (every repo of a group needs a --checkout) was not pinned by a test.

<!-- fr:journal kind=finding scope=plan id=rh-2 created=2026-10-02T20:49:38+00:00 phase=3 state=open review_scope=out -->
### rh-2 · finding [open] (reviewer: out of scope) · Cap and refusal tests partly pass without new driver code (phase 3)

The cap was already global; the tests are legitimate regression guards.

<!-- fr:journal kind=finding scope=plan id=rh-3 created=2026-10-02T20:49:38+00:00 phase=3 state=open review_scope=in -->
### rh-3 · finding [open] (reviewer: in scope) · Group strictness applies to a plain plan print and was undocumented (phase 3)

Spec-conformant, but the skill should say it.

<!-- fr:journal kind=finding scope=plan id=rh-4 created=2026-10-02T20:49:38+00:00 phase=3 state=open review_scope=in -->
### rh-4 · finding [open] (reviewer: in scope) · Scope.group keeps whichever casing came last (phase 3)

scope.target, repos and facts.repos depended on input casing and order.

<!-- fr:journal kind=finding scope=plan id=rh-5 created=2026-10-02T20:49:38+00:00 phase=3 state=open review_scope=in -->
### rh-5 · finding [open] (reviewer: in scope) · Unrelated SKILL.md rewrap churn (phase 3)

The group change re-joined unrelated wrapped lines and enlarged the mirror diff.

<!-- fr:journal kind=finding scope=plan id=rh-6 created=2026-10-02T20:49:38+00:00 phase=3 state=open review_scope=out -->
### rh-6 · finding [open] (reviewer: out of scope) · Facts schema 4 is stamped for repo and org scopes too (phase 3)

Spec-mandated; facts.json is a recollectable cache.

<!-- fr:journal kind=finding scope=plan id=rh-7 created=2026-10-02T20:49:38+00:00 phase=3 state=open review_scope=out -->
### rh-7 · finding [open] (reviewer: out of scope) · No check that facts.kind matches the requested scope (phase 3)

Pre-existing for repo and org scopes.

<!-- fr:journal kind=finding scope=plan id=rh-1-resolved created=2026-10-02T20:49:38+00:00 phase=3 state=fixed resolves=rh-1 -->
### rh-1-resolved · finding [fixed] · resolves rh-1: The drive refusal test cannot tell 'every group repo' from 'repos with batches' (phase 3)

Fixed in 76de055b with tests.

<!-- fr:journal kind=finding scope=plan id=rh-3-resolved created=2026-10-02T20:49:38+00:00 phase=3 state=fixed resolves=rh-3 -->
### rh-3-resolved · finding [fixed] · resolves rh-3: Group strictness applies to a plain plan print and was undocumented (phase 3)

Fixed in 76de055b with tests.

<!-- fr:journal kind=finding scope=plan id=rh-4-resolved created=2026-10-02T20:49:38+00:00 phase=3 state=fixed resolves=rh-4 -->
### rh-4-resolved · finding [fixed] · resolves rh-4: Scope.group keeps whichever casing came last (phase 3)

Fixed in 76de055b with tests.

<!-- fr:journal kind=finding scope=plan id=rh-5-resolved created=2026-10-02T20:49:38+00:00 phase=3 state=fixed resolves=rh-5 -->
### rh-5-resolved · finding [fixed] · resolves rh-5: Unrelated SKILL.md rewrap churn (phase 3)

Fixed in 76de055b with tests.

<!-- fr:journal kind=finding scope=plan id=rh-2-resolved created=2026-10-02T20:49:38+00:00 phase=3 state=open resolves=rh-2 out_of_scope=true -->
### rh-2-resolved · finding [out-of-scope] · resolves rh-2: Cap and refusal tests partly pass without new driver code (phase 3)

The cap was already global; the tests are legitimate regression guards.

<!-- fr:journal kind=finding scope=plan id=rh-6-resolved created=2026-10-02T20:49:38+00:00 phase=3 state=open resolves=rh-6 out_of_scope=true -->
### rh-6-resolved · finding [out-of-scope] · resolves rh-6: Facts schema 4 is stamped for repo and org scopes too (phase 3)

Spec-mandated; facts.json is a recollectable cache.

<!-- fr:journal kind=finding scope=plan id=rh-7-resolved created=2026-10-02T20:49:38+00:00 phase=3 state=open resolves=rh-7 out_of_scope=true -->
### rh-7-resolved · finding [out-of-scope] · resolves rh-7: No check that facts.kind matches the requested scope (phase 3)

Pre-existing for repo and org scopes.

<!-- fr:journal kind=decision scope=plan id=p4-operator-answer-not-derivable created=2026-10-02T21:13:37+00:00 phase=4 -->
### p4-operator-answer-not-derivable · decision · R18's "batch waiting on an operator answer" is not produced; spec amended (phase 4) (phase 4)

No deterministic signal exists. The facts carry no run cursor, and the driver's Snapshot
(batches, stages, PRs, runner dispatches) has nothing about an operator gate; the only place
such a gate shows is the batch branch's run cursor, which collect does not read and the Forge
seam does not expose. Inventing one (a label, a stage guess) would make Needs you now disagree
with the driver. The other five kinds and unplaced are implemented; a test pins that no
`operator-answer` row exists. R18 and Test Plan 13 in the spec now say what is missing and why,
and that the row joins when a deterministic signal exists.

<!-- fr:journal kind=decision scope=plan id=p4-post-merge-signal created=2026-10-02T21:13:37+00:00 phase=4 -->
### p4-post-merge-signal · decision · The post_merge row is read from facts, not from a recorded failure (phase 4) (phase 4)

A failed post_merge leaves no durable record (only a per-pass warn). The deterministic signal in
the facts is: batch merged (stage merged or partial) more than ten minutes before the collect, its
repo's `.fr/triage.yaml` declares `post_merge`, and neither a `post_merge` nor a `closeout` event
exists. "Now" is `facts.collected_at`, never a clock. The row reads "has not succeeded (it failed,
or no driver is running)". Stated in R18 of the spec.

<!-- fr:journal kind=decision scope=plan id=p4-views-share-the-drivers-inputs created=2026-10-02T21:13:37+00:00 phase=4 -->
### p4-views-share-the-drivers-inputs · decision · Needs you now and Next up run drive_pass over a Snapshot built from facts alone (phase 4) (phase 4)

`views.drive_snapshot` builds the driver's Snapshot from facts.json (each open batch PR as the facts
show it, `checks_verdict` for the verdict, release commit unknown so the ten-minute rule applies) and
the board reads `blocked`, `warn` and `dispatch` off `drive_pass`'s own actions. A test pins that the
blocked and failing-CI rows equal the driver's actions on the same facts. Only the draft-and-green,
stale-dispatch, post_merge and unplaced rows are computed in views, from the same facts.

<!-- fr:journal kind=decision scope=plan id=p4-preselect-ignores-cancelled created=2026-10-02T21:13:37+00:00 phase=4 -->
### p4-preselect-ignores-cancelled · decision · A cancelled batch does not hold a wave open for preselection (phase 4) (phase 4)

R16 says the highest wave with a batch "not yet merged". A cancelled batch never merges and needs
nothing, so counting it would preselect a wave with no live work; abandoned and partial batches DO
count (they need the operator). Recorded as a reading of R16, not a change to it.

<!-- fr:journal kind=decision scope=plan id=p4-one-script-element created=2026-10-02T21:13:37+00:00 phase=4 -->
### p4-one-script-element · decision · The tab script is concatenated into the viewer's single script element (phase 4) (phase 4)

The existing render tests pin exactly one script element. `TABS_SCRIPT` is a constant appended to
`SCRIPT`, so no facts text reaches it and that guard still holds. The tab markup is complete with
scripts off (no panel carries `hidden`, the tab row itself is `hidden`); the script hides all but the
selected panel and reveals the row. Key handling was also checked once against a stub DOM in node.

<!-- fr:journal kind=discovery scope=plan id=p4-renderer-already-had-title created=2026-10-02T21:13:37+00:00 phase=4 -->
### p4-renderer-already-had-title · discovery · The board already emitted a title; the real gaps were the explicit-theme tokens and the 10px gutter (phase 4) (phase 4)

Of the three hand patches R12 names, the renderer already wrote a `<title>`; it lacked the
`:root[data-theme]` variants and used a 10px side gutter at 480px. Tokens now come from
`components.TOKENS_CSS`, generated from one light and one dark dict so the three variants cannot
drift; the gutter is `components.GUTTER_CSS` (16px). Both are shared with the later architecture page.

<!-- fr:journal kind=discovery scope=plan id=p4-batch-card-attribute-order created=2026-10-02T21:13:37+00:00 phase=4 -->
### p4-batch-card-attribute-order · discovery · An existing test pins the batch card's attribute order (phase 4) (phase 4)

`<article class="batch" data-batch="..."` is matched literally by test_triage_batch_board, so the
new `id="batch-<id>"` anchor (the target of Needs-you rows) is appended after `data-batch`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-10-02T21:13:37+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

red-only task: tests, no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-10-02T21:13:37+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

red-only task: tests, no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t4 created=2026-10-02T21:13:37+00:00 phase=4 -->
### no-refactor-p4-t4 · discovery · no-refactor-because P4.T4 (phase 4)

documentation, acceptance row and mirrors only: no production code to clean

<!-- fr:journal kind=review scope=plan id=review-p4 created=2026-10-02T21:20:42+00:00 phase=4 -->
### review-p4 · review · phase 4 review: 6 findings (5 in scope, fixed; 1 out of scope) (phase 4)

Independent review of 1b2bcb48..HEAD against R9, R12, R16-R20 and design D and I, including the real sample board opened in a browser at 1100px and 400px: latest wave preselected, click and arrow/Home/End keys move and activate tabs, dark theme readable, no horizontal scroll, all panes shown with JavaScript off. 692 triage tests passed. In-scope findings were fixed in e174d1af.

<!-- fr:journal kind=finding scope=plan id=ri-1 created=2026-10-02T21:20:42+00:00 phase=4 state=open review_scope=in -->
### ri-1 · finding [open] (reviewer: in scope) · With scripts disabled every wave table shows but nothing says which wave each is (phase 4)

Panels had no heading or wave column; R16's no-JS path was met literally but unusable.

<!-- fr:journal kind=finding scope=plan id=ri-2 created=2026-10-02T21:20:42+00:00 phase=4 state=open review_scope=in -->
### ri-2 · finding [open] (reviewer: in scope) · Snapshot acceptance counts are read from the cwd's matrix whatever the triaged scope (phase 4)

A render of another repo recorded this repo's rows; the cwd with no matrix silently dropped the group.

<!-- fr:journal kind=finding scope=plan id=ri-3 created=2026-10-02T21:20:42+00:00 phase=4 state=open review_scope=in -->
### ri-3 · finding [open] (reviewer: in scope) · The inferred post_merge row also fires for old merged batches that never had a close-out (phase 4)

Hand-merged batches from before the driver existed would be listed forever.

<!-- fr:journal kind=finding scope=plan id=ri-4 created=2026-10-02T21:20:42+00:00 phase=4 state=open review_scope=in -->
### ri-4 · finding [open] (reviewer: in scope) · Snapshot is stored before the page is rendered, and a prune failure aborts after the write (phase 4)

A failing render left a snapshot of a board that never existed.

<!-- fr:journal kind=finding scope=plan id=ri-5 created=2026-10-02T21:20:42+00:00 phase=4 state=open review_scope=in -->
### ri-5 · finding [open] (reviewer: in scope) · Re-rendering without a new collect erases 'Since last report' (phase 4)

Every render stored a snapshot; an identical one made the next diff 'Nothing changed'.

<!-- fr:journal kind=finding scope=plan id=ri-6 created=2026-10-02T21:20:42+00:00 phase=4 state=open review_scope=out -->
### ri-6 · finding [open] (reviewer: out of scope) · The Closing order rows have no per-batch tier (phase 4)

Not a spec gap: design D's column list omits tier, and Next up carries it.

<!-- fr:journal kind=finding scope=plan id=ri-1-resolved created=2026-10-02T21:20:42+00:00 phase=4 state=fixed resolves=ri-1 -->
### ri-1-resolved · finding [fixed] · resolves ri-1: With scripts disabled every wave table shows but nothing says which wave each is (phase 4)

Fixed in e174d1af with tests.

<!-- fr:journal kind=finding scope=plan id=ri-2-resolved created=2026-10-02T21:20:42+00:00 phase=4 state=fixed resolves=ri-2 -->
### ri-2-resolved · finding [fixed] · resolves ri-2: Snapshot acceptance counts are read from the cwd's matrix whatever the triaged scope (phase 4)

Fixed in e174d1af with tests.

<!-- fr:journal kind=finding scope=plan id=ri-3-resolved created=2026-10-02T21:20:42+00:00 phase=4 state=fixed resolves=ri-3 -->
### ri-3-resolved · finding [fixed] · resolves ri-3: The inferred post_merge row also fires for old merged batches that never had a close-out (phase 4)

Fixed in e174d1af with tests.

<!-- fr:journal kind=finding scope=plan id=ri-4-resolved created=2026-10-02T21:20:42+00:00 phase=4 state=fixed resolves=ri-4 -->
### ri-4-resolved · finding [fixed] · resolves ri-4: Snapshot is stored before the page is rendered, and a prune failure aborts after the write (phase 4)

Fixed in e174d1af with tests.

<!-- fr:journal kind=finding scope=plan id=ri-5-resolved created=2026-10-02T21:20:42+00:00 phase=4 state=fixed resolves=ri-5 -->
### ri-5-resolved · finding [fixed] · resolves ri-5: Re-rendering without a new collect erases 'Since last report' (phase 4)

Fixed in e174d1af with tests.

<!-- fr:journal kind=finding scope=plan id=ri-6-resolved created=2026-10-02T21:20:42+00:00 phase=4 state=open resolves=ri-6 out_of_scope=true -->
### ri-6-resolved · finding [out-of-scope] · resolves ri-6: The Closing order rows have no per-batch tier (phase 4)

Design D omits tier from the wave table; the board matches the spec.

<!-- fr:journal kind=decision scope=plan id=p5-closing-prs-from-pr-list created=2026-10-02T21:34:20+00:00 phase=5 -->
### p5-closing-prs-from-pr-list · decision · Closing PRs come from the existing PR list, not a new Forge call (phase 5)

`collect` reads `list_issues(state=all)` and `list_prs(state=all)` through the existing
seam and takes the MERGED PRs whose `closingIssuesReferences` name the issue (a PR closed
unmerged closed nothing). No Forge method was added. `gh.ISSUE_LIST_FIELDS` gained
`state,closedAt,stateReason`, which the open-issue path ignores.

<!-- fr:journal kind=decision scope=plan id=p5-closed-without-reason created=2026-10-02T21:34:20+00:00 phase=5 -->
### p5-closed-without-reason · decision · A closed issue with no state reason is counted apart, not as completed (phase 5)

Median time to fix uses `reason == completed` only. A close with no recorded reason is
neither completed nor not planned, so the time-to-fix table shows it in its own
"Closed, no reason" column rather than guessing. Open and not-planned are separate columns.

<!-- fr:journal kind=decision scope=plan id=p5-regression-names-its-pr created=2026-10-02T21:34:20+00:00 phase=5 -->
### p5-regression-names-its-pr · decision · A regression without a `pr:` is refused when origins.yaml is read (phase 5)

The skill's rule (a regression needs the PR that broke it named) is a structural
invariant of `Origin`, so a file that breaks it fails at `check`/`render` with the path,
not on the page.

<!-- fr:journal kind=decision scope=plan id=p5-conclusion-batch-links created=2026-10-02T21:34:20+00:00 phase=5 -->
### p5-conclusion-batch-links · decision · The conclusion links a batch to the board's `batch-<id>` anchor; unknown ids stay visible (phase 5)

Batches resolve against `judgements.yaml` in the same state directory; a link goes to
`triage.html#batch-<id>` (the anchor phase 4 added). An id the file does not hold, or no
judgements file at all, renders as an `unresolved` span with no link, never dropped.

<!-- fr:journal kind=discovery scope=plan id=p5-judgements-validate-batch-members created=2026-10-02T21:34:20+00:00 phase=5 -->
### p5-judgements-validate-batch-members · discovery · A batch fixture needs its members judged (phase 5)

`Judgements` rejects a batch whose ids are not in `issues:`; the tests judge `widgets#3`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-10-02T21:34:20+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

red-only task: tests, no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t2 created=2026-10-02T21:34:20+00:00 phase=5 -->
### no-refactor-p5-t2 · discovery · no-refactor-because P5.T2 (phase 5)

nothing to extract: the board has no chart or table helpers (its tables are board-specific rows), so the page reuses what IS shared - FONTS, esc, plural, TOKENS_CSS, GUTTER_CSS - and the engine is one new module; ruff format, ruff check and mypy clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t3 created=2026-10-02T21:34:20+00:00 phase=5 -->
### no-refactor-p5-t3 · discovery · no-refactor-because P5.T3 (phase 5)

acceptance row, mirrors and tripwires only: no production code to clean

<!-- fr:journal kind=review scope=plan id=review-p5 created=2026-10-02T21:41:25+00:00 phase=5 -->
### review-p5 · review · phase 5 review: 7 findings (6 in scope, fixed; 1 out of scope) (phase 5)

Independent review of e8860c9e..HEAD against R10, R12, R20 and design E, with the real sample page opened in a browser at 1100px and 400px (filter, dark theme, conclusion links, no horizontal scroll). 841 triage tests passed in the reviewer's run. The chart legibility and table wrapping defects were observed in the browser. All in-scope findings were fixed in 92ec0f54 with tests.

<!-- fr:journal kind=finding scope=plan id=rj-1 created=2026-10-02T21:41:25+00:00 phase=5 state=open review_scope=in -->
### rj-1 · finding [open] (reviewer: in scope) · The filings-per-day chart scales to the container: giant with overlapping labels on a short window (phase 5)

Observed in the browser: 5 days stretched to 1008px, date labels overlapping; the opposite at 30+ days on a phone.

<!-- fr:journal kind=finding scope=plan id=rj-2 created=2026-10-02T21:41:25+00:00 phase=5 state=open review_scope=in -->
### rj-2 · finding [open] (reviewer: in scope) · The issue table breaks words mid-word at phone width (phase 5)

overflow-wrap:anywhere on every cell; the scroll wrapper never engaged.

<!-- fr:journal kind=finding scope=plan id=rj-3 created=2026-10-02T21:41:25+00:00 phase=5 state=open review_scope=in -->
### rj-3 · finding [open] (reviewer: in scope) · Org-scope truncation of the repo list is dropped silently (phase 5)

collect_origins discarded the Truncation list from scope_repos.

<!-- fr:journal kind=finding scope=plan id=rj-4 created=2026-10-02T21:41:25+00:00 phase=5 state=open review_scope=in -->
### rj-4 · finding [open] (reviewer: in scope) · No test covers group or org scope, a skipped repo's warning, or the limit warnings (phase 5)

New branches of collect_origins had no failing test if removed.

<!-- fr:journal kind=finding scope=plan id=rj-5 created=2026-10-02T21:41:25+00:00 phase=5 state=open review_scope=in -->
### rj-5 · finding [open] (reviewer: in scope) · Widening ISSUE_LIST_FIELDS affects every issue-list verb (phase 5)

The shared constant now asked for stateReason for triage collect too.

<!-- fr:journal kind=finding scope=plan id=rj-6 created=2026-10-02T21:41:25+00:00 phase=5 state=open review_scope=in -->
### rj-6 · finding [open] (reviewer: in scope) · Skill text slightly overstates what the engine does (phase 5)

Missing: a bad origins.yaml fails every verb that reads it; the duplicate check is prose-only.

<!-- fr:journal kind=finding scope=plan id=rj-7 created=2026-10-02T21:41:25+00:00 phase=5 state=open review_scope=out -->
### rj-7 · finding [open] (reviewer: out of scope) · Closing-PR and issue lists rely on newest-first 1000-row pages (phase 5)

Matches how the existing collector treats limits; the limit warning covers truncation.

<!-- fr:journal kind=finding scope=plan id=rj-1-resolved created=2026-10-02T21:41:25+00:00 phase=5 state=fixed resolves=rj-1 -->
### rj-1-resolved · finding [fixed] · resolves rj-1: The filings-per-day chart scales to the container: giant with overlapping labels on a short window (phase 5)

Fixed in 92ec0f54 with tests.

<!-- fr:journal kind=finding scope=plan id=rj-2-resolved created=2026-10-02T21:41:25+00:00 phase=5 state=fixed resolves=rj-2 -->
### rj-2-resolved · finding [fixed] · resolves rj-2: The issue table breaks words mid-word at phone width (phase 5)

Fixed in 92ec0f54 with tests.

<!-- fr:journal kind=finding scope=plan id=rj-3-resolved created=2026-10-02T21:41:25+00:00 phase=5 state=fixed resolves=rj-3 -->
### rj-3-resolved · finding [fixed] · resolves rj-3: Org-scope truncation of the repo list is dropped silently (phase 5)

Fixed in 92ec0f54 with tests.

<!-- fr:journal kind=finding scope=plan id=rj-4-resolved created=2026-10-02T21:41:25+00:00 phase=5 state=fixed resolves=rj-4 -->
### rj-4-resolved · finding [fixed] · resolves rj-4: No test covers group or org scope, a skipped repo's warning, or the limit warnings (phase 5)

Fixed in 92ec0f54 with tests.

<!-- fr:journal kind=finding scope=plan id=rj-5-resolved created=2026-10-02T21:41:25+00:00 phase=5 state=fixed resolves=rj-5 -->
### rj-5-resolved · finding [fixed] · resolves rj-5: Widening ISSUE_LIST_FIELDS affects every issue-list verb (phase 5)

Fixed in 92ec0f54 with tests.

<!-- fr:journal kind=finding scope=plan id=rj-6-resolved created=2026-10-02T21:41:25+00:00 phase=5 state=fixed resolves=rj-6 -->
### rj-6-resolved · finding [fixed] · resolves rj-6: Skill text slightly overstates what the engine does (phase 5)

Fixed in 92ec0f54 with tests.

<!-- fr:journal kind=finding scope=plan id=rj-7-resolved created=2026-10-02T21:41:25+00:00 phase=5 state=open resolves=rj-7 out_of_scope=true -->
### rj-7-resolved · finding [out-of-scope] · resolves rj-7: Closing-PR and issue lists rely on newest-first 1000-row pages (phase 5)

Matches the existing collector's limit handling; not caused by this change.

<!-- fr:journal kind=decision scope=plan id=p6-timeline-from-stored-snapshots created=2026-10-02T22:06:44+00:00 phase=6 -->
### p6-timeline-from-stored-snapshots · decision · The timeline steps through the stored snapshots, one tab per snapshot (phase 6)

A snapshot stores figures, batch stages, issue and PR states, not the rendered sections, so
"the measured sections as they were" is each snapshot's figures table (with change against the
snapshot before), its batch stages and the diff to the previous one. It reuses `tabs()` (newest
preselected, every step shown without JavaScript). `snapshot.stored_snapshots` reads the stamp
from the file name; unreadable files are skipped as absent. Zero snapshots says none; one says
there is nothing to step through yet.

<!-- fr:journal kind=decision scope=plan id=p6-r20-groups-manifest-orders-within created=2026-10-02T22:06:44+00:00 phase=6 -->
### p6-r20-groups-manifest-orders-within · decision · R20 fixes the groups; the manifest orders within them (phase 6)

The timeline is always first and is not a manifest entry. Generated sections then follow in
manifest order and the authored fragments after them in manifest order, whatever the interleaving
in the file. No manifest means every generated section and no fragments. A name that is neither a
generated section nor a plain file name directly inside `architecture/` is refused (exit 2), so a
manifest cannot reach outside the directory.

<!-- fr:journal kind=decision scope=plan id=p6-fragment-rules created=2026-10-02T22:06:44+00:00 phase=6 -->
### p6-fragment-rules · decision · Fragments are parsed strictly; scripts and document elements are refused (phase 6)

Well-formed means every non-void element is closed in order (optional end tags such as an
unclosed `<li>` are refused too). `<script>`, `<html>`, `<head>`, `<body>` and `<title>` are
refused: the page keeps one script element (a constant) and its own real title. Beyond the
spec's "well-formed", stated here so the skill can say it. A manifest entry with no file is
reported on stderr and as a note on the page, exit 0; a malformed one is exit 2 with nothing written.

<!-- fr:journal kind=decision scope=plan id=p6-missing-is-a-dash created=2026-10-02T22:06:44+00:00 phase=6 -->
### p6-missing-is-a-dash · decision · A measurement that cannot be taken, or that matched no file, is a dash (phase 6)

An unresolvable ref, a glob matching no file at that ref, or no git checkout at all gives no
figure (an em dash and a warning), never 0. A subsystem that genuinely did not exist at its
then_ref therefore reads as a dash with its commit still named in the other column.

<!-- fr:journal kind=discovery scope=plan id=p6-checkout-option created=2026-10-02T22:06:44+00:00 phase=6 -->
### p6-checkout-option · discovery · The verb takes --checkout and --now-ref (phase 6)

Measuring needs a clone, which `fr triage` scope options do not name, so the command takes
`--checkout` (default the current toplevel, via the existing Checkout.at) and `--now-ref`
(default HEAD). Git processes start only in gitseam (new Checkout.short_rev and files_at).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t1 created=2026-10-02T22:06:44+00:00 phase=6 -->
### no-refactor-p6-t1 · discovery · no-refactor-because P6.T1 (phase 6)

red-only task: tests, no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t2 created=2026-10-02T22:06:44+00:00 phase=6 -->
### no-refactor-p6-t2 · discovery · no-refactor-because P6.T2 (phase 6)

nothing beyond sharing the page shell: the page already builds on components.TOKENS_CSS/GUTTER_CSS/TABS_CSS/tabs and the origins chart and chips, which gained public aliases (filings_chart, origin_counts) instead of copies

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t3 created=2026-10-02T22:06:44+00:00 phase=6 -->
### no-refactor-p6-t3 · discovery · no-refactor-because P6.T3 (phase 6)

acceptance row, gates and mirrors only: no production code to clean

<!-- fr:journal kind=review scope=plan id=review-p6 created=2026-10-02T22:15:36+00:00 phase=6 -->
### review-p6 · review · phase 6 review: 8 findings (7 in scope, fixed; 1 out of scope) (phase 6)

Independent review of 0b92b045..HEAD against R11, R12, R16, R17, R20 and design F and I, with the real sample page opened in a browser at 1100px and 400px (snapshot timeline and wave tabs by click and keyboard, SVG fragment in dark theme, chart, the missing-file note, no horizontal scroll). The measurement crash on a binary file was reproduced in a temporary git repo. All in-scope findings were fixed in 5d79e76e with tests (938 focused tests passed).

<!-- fr:journal kind=finding scope=plan id=rk-1 created=2026-10-02T22:15:36+00:00 phase=6 state=open review_scope=in -->
### rk-1 · finding [open] (reviewer: in scope) · A binary file in a subsystem crashes the render with an uncaught UnicodeDecodeError (phase 6)

gitseam show() decodes text; architecture.py caught only GitError.

<!-- fr:journal kind=finding scope=plan id=rk-2 created=2026-10-02T22:15:36+00:00 phase=6 state=open review_scope=in -->
### rk-2 · finding [open] (reviewer: in scope) · Per-file cat-file plus git show is slow and wrong at the edges (phase 6)

Two processes per file per ref; quoted non-ASCII paths counted as 0 lines; symlinks and gitlinks counted; splitlines differs from wc -l.

<!-- fr:journal kind=finding scope=plan id=rk-3 created=2026-10-02T22:15:36+00:00 phase=6 state=open review_scope=in -->
### rk-3 · finding [open] (reviewer: in scope) · The fragment check does not stop script execution or page breakage despite what the docs say (phase 6)

Event handlers, javascript: URLs, style, iframe, meta refresh were allowed; page-level title banned also in svg.

<!-- fr:journal kind=finding scope=plan id=rk-4 created=2026-10-02T22:15:36+00:00 phase=6 state=open review_scope=in -->
### rk-4 · finding [open] (reviewer: in scope) · The well-formedness check disagrees with the browser on unclosed or self-closing tags (phase 6)

The contract was not stated in the skill.

<!-- fr:journal kind=finding scope=plan id=rk-5 created=2026-10-02T22:15:36+00:00 phase=6 state=open review_scope=in -->
### rk-5 · finding [open] (reviewer: in scope) · A manifest listing only fragments silently drops every generated section (phase 6)

Contradicts R20's 'keeps everything'.

<!-- fr:journal kind=finding scope=plan id=rk-6 created=2026-10-02T22:15:36+00:00 phase=6 state=open review_scope=in -->
### rk-6 · finding [open] (reviewer: in scope) · Timeline stamps are UTC but unlabelled; size table says 'Source lines' (phase 6)

The counting rule was not stated.

<!-- fr:journal kind=finding scope=plan id=rk-7 created=2026-10-02T22:15:36+00:00 phase=6 state=open review_scope=in -->
### rk-7 · finding [open] (reviewer: in scope) · Tests lack the binary, non-ASCII, symlink, submodule, corrupt-facts and fragment-injection cases (phase 6)

Coverage gaps for the new measurement and guard.

<!-- fr:journal kind=finding scope=plan id=rk-8 created=2026-10-02T22:15:36+00:00 phase=6 state=open review_scope=out -->
### rk-8 · finding [open] (reviewer: out of scope) · Checkout.show() is text-only by contract (phase 6)

Pre-existing; only the new call site exposed it.

<!-- fr:journal kind=finding scope=plan id=rk-1-resolved created=2026-10-02T22:15:36+00:00 phase=6 state=fixed resolves=rk-1 -->
### rk-1-resolved · finding [fixed] · resolves rk-1: A binary file in a subsystem crashes the render with an uncaught UnicodeDecodeError (phase 6)

Fixed in 5d79e76e with tests.

<!-- fr:journal kind=finding scope=plan id=rk-2-resolved created=2026-10-02T22:15:36+00:00 phase=6 state=fixed resolves=rk-2 -->
### rk-2-resolved · finding [fixed] · resolves rk-2: Per-file cat-file plus git show is slow and wrong at the edges (phase 6)

Fixed in 5d79e76e with tests.

<!-- fr:journal kind=finding scope=plan id=rk-3-resolved created=2026-10-02T22:15:36+00:00 phase=6 state=fixed resolves=rk-3 -->
### rk-3-resolved · finding [fixed] · resolves rk-3: The fragment check does not stop script execution or page breakage despite what the docs say (phase 6)

Fixed in 5d79e76e with tests.

<!-- fr:journal kind=finding scope=plan id=rk-4-resolved created=2026-10-02T22:15:36+00:00 phase=6 state=fixed resolves=rk-4 -->
### rk-4-resolved · finding [fixed] · resolves rk-4: The well-formedness check disagrees with the browser on unclosed or self-closing tags (phase 6)

Fixed in 5d79e76e with tests.

<!-- fr:journal kind=finding scope=plan id=rk-5-resolved created=2026-10-02T22:15:36+00:00 phase=6 state=fixed resolves=rk-5 -->
### rk-5-resolved · finding [fixed] · resolves rk-5: A manifest listing only fragments silently drops every generated section (phase 6)

Fixed in 5d79e76e with tests.

<!-- fr:journal kind=finding scope=plan id=rk-6-resolved created=2026-10-02T22:15:36+00:00 phase=6 state=fixed resolves=rk-6 -->
### rk-6-resolved · finding [fixed] · resolves rk-6: Timeline stamps are UTC but unlabelled; size table says 'Source lines' (phase 6)

Fixed in 5d79e76e with tests.

<!-- fr:journal kind=finding scope=plan id=rk-7-resolved created=2026-10-02T22:15:36+00:00 phase=6 state=fixed resolves=rk-7 -->
### rk-7-resolved · finding [fixed] · resolves rk-7: Tests lack the binary, non-ASCII, symlink, submodule, corrupt-facts and fragment-injection cases (phase 6)

Fixed in 5d79e76e with tests.

<!-- fr:journal kind=finding scope=plan id=rk-8-resolved created=2026-10-02T22:15:36+00:00 phase=6 state=open resolves=rk-8 out_of_scope=true -->
### rk-8-resolved · finding [out-of-scope] · resolves rk-8: Checkout.show() is text-only by contract (phase 6)

gitseam show() is text-only by contract; the new measurement no longer uses it.

<!-- fr:journal kind=finding scope=plan id=rf-4-resolved-3 created=2026-10-02T22:15:53+00:00 state=open resolves=rf-4 out_of_scope=true -->
### rf-4-resolved-3 · finding [out-of-scope] · resolves rf-4: merge_ready uses required checks only, not the R4 'else all checks / ci none' rule

merge_ready's check rule (required checks else all, ci none) was addressed later by phase 2's driver pass; the state is restored because only the operator may move an out-of-scope finding to fixed

<!-- fr:journal kind=finding scope=plan id=rf-5-resolved-3 created=2026-10-02T22:15:54+00:00 state=open resolves=rf-5 out_of_scope=true -->
### rf-5-resolved-3 · finding [out-of-scope] · resolves rf-5: fr-triage SKILL.md still says to create judgements.yaml with schema: 2

the fr-triage skill's schema wording was updated later in phase 2; the state is restored because only the operator may move an out-of-scope finding to fixed
