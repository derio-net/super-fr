<!-- fr:journal-schema=2 -->
# Journal: 2026-10-14-merge-truth

<!-- fr:journal kind=decision scope=plan id=p1-settle-drops-release-op created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-settle-drops-release-op · decision · A settle op replaces the release op for the same key (phase 1)

plan_sync drops the owed release for a key that also has a settle target (a closed member of a releasing batch): settle releases the own marker and unlabels in one pass, and carries the batch so claims_released is still recorded. Otherwise the pass would edit the same issue twice.

<!-- fr:journal kind=decision scope=plan id=p1-settle-closed-needs-now created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-settle-closed-needs-now · decision · settle_closed takes now= beside the planned arguments (phase 1)

The plan's signature (client, repo, number, me, trusted) has no clock; the released marker form needs one, so settle_closed(client, repo, number, *, me, now, trusted) is keyword-only. A label-only settle (no own marker) returns the new Done action 'unlabelled', distinct from 'none' (left alone).

<!-- fr:journal kind=decision scope=plan id=p1-carried-settle-waits created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-carried-settle-waits · decision · Settle of a carried repo waits, by the key's repo (phase 1)

settle is in _LIVE_READ_ACTIONS and read_repo() resolves it by env.owner_repo(key) because a settle may name no batch; a skipped repo's settles are not planned (unread filter, same key repo). facts.json is host-local (not a REF_FILES entry), so retire writes it with write_text_atomic and no state-ref publication is needed.

<!-- fr:journal kind=discovery scope=plan id=p1-fake-forge-closed-filter created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-fake-forge-closed-filter · discovery · FakeForge now filters the closed read by label (phase 1)

tests/unit/triage_fixtures.py FakeForge.list_issues returned the closed set regardless of the label filter; with two label reads it now filters (gh ANDs labels, one per read), so the single-label tests keep their meaning.

<!-- fr:journal kind=discovery scope=plan id=p1-idle-guard-flake-under-load created=2026-10-14T00:20:45+00:00 phase=1 -->
### p1-idle-guard-flake-under-load · discovery · test_run_idle_guard hang test fails under the full parallel suite only (phase 1)

Full suite: 12309 passed, 118 skipped, 1 failed (tests/integration/test_run_idle_guard.py::test_fails_open_when_fr_hangs_and_does_not_hang_with_it). The file passes alone (52 passed); the test is wall-clock bound and touches nothing this phase changed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

skeleton task: a change fragment and a stub; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

release() rewrites its marker in one edit line; settle_closed's differs (labels, state check), so no shared helper is worth extracting

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

plan_sync/execute grew by one branch each; ClaimOp.label is the only shared bit and was added with the change

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

the settle path reuses claim_sync.execute and _claim_write; the repo-of-op lookup was extracted as _op_repo/read_repo in the same change

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

the withdraw path is its own helper (_withdraw_take) from the start; nothing duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t8 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t8 · discovery · no-refactor-because P1.T8 (phase 1)

one helper (_forget_claims) added; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t9 created=2026-10-14T00:20:45+00:00 phase=1 -->
### no-refactor-p1-t9 · discovery · no-refactor-because P1.T9 (phase 1)

scenario scripts and the shared fake gh; nothing to clean

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-10-14T00:34:03+00:00 phase=1 -->
### p1-review · review · Phase 1 review: 8 findings (6 in scope, all fixed; 2 out of scope) (phase 1)

An independent reviewer read 23cd1092~1..e430d2ea against spec R1–R6, R15 and §A–§C. Verdict: ready with fixes. No Critical or Important findings. The targeted suites (685 tests) passed.
Both executor deviations were judged justified: settle_closed takes a keyword-only now=, and the scenarios sit at level int.
The in-scope findings p1-r1..r6 were each verified and fixed test-first, in a3eceb3e, 0ab0fa9c, 5dc09501, 2ec7afef, 312e8619, 8414408a and 7495d3c7. Afterwards, 525 targeted tests passed.
The orchestrator re-ran p1-r2's tests against the pre-fix writer, and both failed.
p1-r7 and p1-r8 are out of scope.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-14T00:34:03+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · settle on a non-GitHub repo raises UnsupportedForgeOperation; claim sync and every drive pass exit 2 (phase 1)

claim_sync.execute settle branch and triage_batch_cmd._claim_write. Settle ops were planned for glab/tea repos, whose list_issue_comments is unsupported.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-14T00:34:03+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · settle_closed reads view_issue twice and always edits labels (phase 1)

claim_writes.settle_closed: one avoidable read per settle (~206 on the first live pass), and a label edit even when no release label is present.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-14T00:34:03+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · plan_sync settle attributes a member to the first batch containing the key (phase 1)

claim_sync.py settle planning: the first match may be an archived or cancelled batch, so claims_released lands on the wrong batch.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-14T00:34:03+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · scope retire clobbers a concurrent facts.json and skips _forget_claims on the unsupported-forge exit (phase 1)

triage_claim_cmd scope retire writes back facts loaded at start, and _fail on UnsupportedForgeOperation runs before _forget_claims.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-14T00:34:03+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · Acceptance rows do not cite --yes tests proving clearing (phase 1)

triage-release-pending-true cited no test of a --yes pass clearing a release-pending member. triage-closed-issues-unclaimed cited only the pure drive_pass test.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-14T00:34:03+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · Carried-repo settle filter tested only via the read_repo helper (phase 1)

There was no pass-level test that a carried or skipped repo's settle is withheld.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-14T00:34:03+00:00 phase=1 state=open review_scope=out -->
### p1-r7 · finding [open] (reviewer: out of scope) · Closed issues held by a retired scope are never settled (phase 1)

Retire handles open issues only, which predates this change. R6 concerns open members.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-14T00:34:03+00:00 phase=1 state=open review_scope=out -->
### p1-r8 · finding [open] (reviewer: out of scope) · A closed issue with an own un-released marker but no label is never settled (phase 1)

Spec §A keys the closed set on the two labels by design. Such an issue shows nothing false on any surface.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-14T00:34:03+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: settle on a non-GitHub repo raises UnsupportedForgeOperation; claim sync and every drive pass exit 2 (phase 1)

a3eceb3e: plan_sync plans no settle for a repo whose client is UnsupportedBatchOps. Both claim sync and the drive plan through it. Test test_triage_claim_sync.py::test_sync_plans_no_settle_on_a_non_github_repo.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-14T00:34:03+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: settle_closed reads view_issue twice and always edits labels (phase 1)

0ab0fa9c: settle_closed takes the labels from its first read and skips the edit and re-read when no release label is present. Tests test_settle_closed_views_the_issue_once_and_edits_labels_once and test_settle_closed_with_no_release_label_edits_no_label_and_still_releases both fail on the pre-fix writer.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-14T00:34:03+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: plan_sync settle attributes a member to the first batch containing the key (phase 1)

5dc09501: the settle batch is the owing one (owed_claims, then owed_releases, then the first match). Test test_a_settle_serves_the_batch_that_owes_the_key_not_the_first_listing_it.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-14T00:34:03+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: scope retire clobbers a concurrent facts.json and skips _forget_claims on the unsupported-forge exit (phase 1)

2ec7afef: _forget_claims reloads facts.json before rewriting, and retire forgets the released claims before the unsupported-forge exit. Tests test_scope_retire_does_not_clobber_facts_a_collect_rewrote_meanwhile and test_scope_retire_forgets_the_released_claims_before_an_unsupported_forge_exit.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-14T00:34:03+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: Acceptance rows do not cite --yes tests proving clearing (phase 1)

312e8619 adds test_a_yes_pass_clears_a_release_pending_member, and 8414408a/7495d3c7 add the --yes refs to both rows. fr acceptance check reports 521 rows OK.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-14T00:34:03+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: Carried-repo settle filter tested only via the read_repo helper (phase 1)

312e8619: test_a_yes_pass_leaves_a_closed_hit_of_a_skipped_repo_alone runs a pass and asserts no settle line and no label edit.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-14T00:34:03+00:00 phase=1 state=open resolves=p1-r7 out_of_scope=true -->
### p1-r7-resolved · finding [out-of-scope] · resolves p1-r7: Closed issues held by a retired scope are never settled (phase 1)

Not caused by this change: scope retire has always released claims on open issues only. A retired scope's claims on closed issues predate this batch.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-14T00:34:03+00:00 phase=1 state=open resolves=p1-r8 out_of_scope=true -->
### p1-r8-resolved · finding [out-of-scope] · resolves p1-r8: A closed issue with an own un-released marker but no label is never settled (phase 1)

Not caused by this change: the closed set is keyed on the two labels by spec §A. An unlabelled closed issue with a stale marker misleads no surface.

<!-- fr:journal kind=decision scope=plan id=p2-live-checks-in-archive-prs created=2026-10-14T01:07:35+00:00 phase=2 -->
### p2-live-checks-in-archive-prs · decision · Head-found archive PR checks are read in _archive_prs, not inside _live_head_prs (phase 2)

The plan put the pr_checks_verdict call inside _live_head_prs. That helper also serves the export reuse read and close-out adoption, which never use checks, so reading checks there would add two forge reads per PR to paths that ignore them. _archive_prs calls pr_checks_verdict for an OPEN head-found PR absent from path 1, which is exactly R7's set.

<!-- fr:journal kind=decision scope=plan id=p2-card-archive-wait-hint created=2026-10-14T01:07:35+00:00 phase=2 -->
### p2-card-archive-wait-hint · decision · The card names its archive PR through a new _archive_wait hint, ahead of the fallback (phase 2)

idle_session returns None whenever an attributed archive PR exists, so _idle_hint can never see one; R10's "names the PR and its wait" is a separate hint, _archive_wait, placed after the idle hint and before the driver's action phrase: "archive PR #N: checks pending|failing", "ready to merge" or "conflicts with the default branch". _idle_hint is unchanged; with linked PRs now read, its "no archive PR" only shows when there truly is none.

<!-- fr:journal kind=decision scope=plan id=p2-held-archive-conflict-is-blocked created=2026-10-14T01:07:35+00:00 phase=2 -->
### p2-held-archive-conflict-is-blocked · decision · A held archive conflict plans a blocked action, so the loop can stop on it (phase 2)

Once a held archive_conflict event names the PR's head, the pure pass emits Action("blocked", "archive PR #N (...) conflicts and its hand-backs are spent; resolve it") and counts the batch blocked, not closing. Otherwise a looping drive would wait on it forever; now it ends with "only blocked batches remain". The pass that first decides held still emits archive-conflict, and the command writes the held event and the stop.

<!-- fr:journal kind=decision scope=plan id=p2-export-conflict-action created=2026-10-14T01:07:35+00:00 phase=2 -->
### p2-export-conflict-action · decision · A conflicting export PR plans an archive-conflict action carrying its wave (phase 2)

_export_row returns Action("archive-conflict", repo, ..., wave=w), counted blocked; _act routes a wave-carrying archive-conflict to _export_conflict, which calls record_stop keyed export:<repo>. needs_you takes an optional stops mapping (render and fr triage render pass load_stops) and lists an export:<repo> conflict stop as an archive-conflict Need. Its href is None because a stop does not carry the PR URL.

<!-- fr:journal kind=decision scope=plan id=p2-archive-conflict-fresh-payload-kind created=2026-10-14T01:07:35+00:00 phase=2 -->
### p2-archive-conflict-fresh-payload-kind · decision · A fresh archive-conflict session is dispatched with payload kind "conflict" (phase 2)

fr-herdr's managed descriptor role is Literal batch|conflict|closeout, read from payload["kind"]. The archive-conflict item (id <repo>/run/archive-conflict-<batch>-<n>) is a conflict session on the archive PR's branch, so it uses kind "conflict" and branch = the archive PR's head branch, carried on the new Action.branch field. The runner is the close-out event's runner, or the batch's launch runner when the close-out was done by hand.

<!-- fr:journal kind=discovery scope=plan id=p2-skill-schema-1-substring created=2026-10-14T01:07:35+00:00 phase=2 -->
### p2-skill-schema-1-substring · discovery · test_fr_triage_skill_example's "schema: 1" check was a substring test that schema 10 trips (phase 2)

The test asserted that "schema: 1" never appears in the skill, which "schema: 10" now contains. It now matches r"schema: 1\b". The three future-schema refusal tests moved from 10 to 11. AGENTS.md's batch paragraph still said schemas 1–8; it now says 1–10.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-14T01:07:35+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

pr_checks_verdict was extracted from live_checks as the change itself; nothing else duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-14T01:07:35+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

closing_repos is one helper used by live_repos and the pacing caller; plan_pass grew by one set union per branch

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-14T01:07:35+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

the waiting line reuses ARCHIVE_WAIT in drive, views and kanban; no duplication left

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-10-14T01:07:35+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

one Action flag and one pr_ready call; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-10-14T01:07:35+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

archive_conflict_decision mirrors conflict_decision but counts another event against another boundary; folding them would couple the two counters the spec keeps apart

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t7 created=2026-10-14T01:07:35+00:00 phase=2 -->
### no-refactor-p2-t7 · discovery · no-refactor-because P2.T7 (phase 2)

acceptance status moves only; no code
