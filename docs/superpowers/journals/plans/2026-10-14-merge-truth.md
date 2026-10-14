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

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-10-14T01:44:35+00:00 phase=2 -->
### p2-review · review · Phase 2 review: 10 findings (9 in scope, all fixed; 1 out of scope) plus one security finding, fixed (phase 2)

An independent reviewer read 818b6664~1..HEAD against spec R7–R12, §D and §E. 817 targeted tests passed, and both mirror syncs were clean. Verdict: approve after fixing p2-r1..r3 (Important). All five recorded executor deviations were judged acceptable; deviation 5 had the recovery gap fixed under p2-r1.
p2-r1..r9 were each verified and fixed test-first: 78d9bc0e, 97977658, ec2d8d7e, cd365272, aab8ab10, 31d264ed, 89d0249e, 9fc99268 and 613a945d. A widened run then passed 3552 tests, with ruff and mypy clean.
A background commit security review flagged a merge-pin bypass (TOCTOU on the CI gate). p2-r6's first fix had taken the archive PR's head from a view read after the checks. It is filed as p2-r11 and fixed in 2d7298e0 (`_pinned`: head, checks, head again; a moved head is pending). The orchestrator re-ran the TOCTOU tests (3 passed).
p2-r10 is out of scope.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · archive_conflict_brief makes a fresh session git switch in the base clone; herdr handback() ignores the brief (phase 2)

batch_dispatch.py archive brief and _hand_back_archive (checkout = main worktree), and fr_herdr.managed.handback prefix.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Archive stops keyed batch.id are filtered out by kanban.live_stops (phase 2)

The batch PR is MERGED for a closing batch, so a refused archive merge's card read 'ready to merge' (gh#987 again), and a held archive conflict's card was not needs-you.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · export:<repo> stop never cleared on hand merge or close; the Need had no liveness check (phase 2)

The export-reconcile and export-closed paths, and views.archive_conflict_needs.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · kanban._archive_prs hard-codes ci_none=False (phase 2)

A ci-none repo's card said checks pending while the driver merged.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · Export vs batch archive-conflict routed only by wave (phase 2)

This routing was fragile; a distinct kind is needed.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · _viewed took a fresh mergeable but kept the facts' head (phase 2)

The event and stop could record a stale head.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · triage-archive-pr-conflict-handed row omitted tests its notes claim (phase 2)

The wait-while-working, merge-clears-stop and forge-refusal tests were not cited.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · fr-triage SKILL.md driver paragraph behind the code (phase 2)

Drafts readied, the archive-conflict hand-back and Need, export stops, and the stop semantics sentence were not covered.

<!-- fr:journal kind=finding scope=plan id=p2-r9 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r9 · finding [open] (reviewer: in scope) · pr_ready refusal wording; delivered typed str with type: ignore; merge_ctx built before the carries() return (phase 2)

Small correctness and typing issues in _archive, _archive_conflict_event and _hand_back_archive.

<!-- fr:journal kind=finding scope=plan id=p2-r10 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=out -->
### p2-r10 · finding [open] (reviewer: out of scope) · A conflict at an unchanged head after a finished hand-back is skipped forever (phase 2)

This is the spec's skip rule (§E, R12), shared with batch-PR conflict_decision.

<!-- fr:journal kind=finding scope=plan id=p2-r11 created=2026-10-14T01:44:35+00:00 phase=2 state=open review_scope=in -->
### p2-r11 · finding [open] (reviewer: in scope) · Merge-pin bypass (TOCTOU): the archive merge could be pinned to a head CI never judged (phase 2)

Found by the background commit security review. pr_checks_verdict judges the PR's head at read time, while 31d264ed took the pinned head from a later pr_view, so a push between the reads pinned --match-head-commit to an unchecked head.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: archive_conflict_brief makes a fresh session git switch in the base clone; herdr handback() ignores the brief (phase 2)

78d9bc0e: brief step 1 is `fr isolation up --branch {branch}`. fr_herdr.managed gains HANDBACK_PREFIXES/is_handback (no fr.triage import). Tests in test_triage_batch_drive_cmd.py, test_herdr_managed.py and test_fr_herdr_runner.py.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Archive stops keyed batch.id are filtered out by kanban.live_stops (phase 2)

97977658: stops are keyed archive:<batch> (merge_stops.archive_stop_key) and live_stops checks them against the archive PR head. Tests test_a_refused_archive_merge_shows_its_stop_on_the_card and test_a_held_archive_conflict_card_needs_you.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: export:<repo> stop never cleared on hand merge or close; the Need had no liveness check (phase 2)

ec2d8d7e: reconcile and closed clear export_stop_key, and views._export_stop_live gives the Need a liveness check. Tests test_an_export_pr_merged_or_closed_by_hand_clears_its_conflict_stop and test_an_export_conflict_need_holds_only_while_its_pr_is_open_at_the_stop_head.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: kanban._archive_prs hard-codes ci_none=False (phase 2)

cd365272: ci_none is passed through build_board → _card → live_stops → _archive_prs. Test test_a_ci_none_repos_archive_pr_with_no_checks_reads_ready_to_merge.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Export vs batch archive-conflict routed only by wave (phase 2)

aab8ab10: new ActionKind export-conflict, routed by kind. Tests test_a_conflicting_export_pr_is_its_own_export_conflict_kind and the export stop-key test.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: _viewed took a fresh mergeable but kept the facts' head (phase 2)

31d264ed, completed by 2d7298e0 (see p2-r11): the head and mergeable come from the same read the verdict describes. Test test_viewed_takes_head_and_mergeable_from_the_same_fresh_read.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: triage-archive-pr-conflict-handed row omitted tests its notes claim (phase 2)

89d0249e: the row cites the wait, clear, refusal, hand-merge, kanban-stop and export-liveness tests. fr acceptance check reports 521 rows OK.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: fr-triage SKILL.md driver paragraph behind the code (phase 2)

9fc99268: the driver paragraph was updated in place (120 lines) and both syncs were run. The sync, skill-validation and tool-neutrality tripwires pass.

<!-- fr:journal kind=finding scope=plan id=p2-r9-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r9 -->
### p2-r9-resolved · finding [fixed] · resolves p2-r9: pr_ready refusal wording; delivered typed str with type: ignore; merge_ctx built before the carries() return (phase 2)

613a945d: the ready-step wording, ConflictDelivery typing and the early return before brief and merge_ctx. Tests test_a_refused_ready_on_a_draft_archive_is_worded_as_the_ready_step and test_an_archive_conflict_left_to_another_driver_builds_no_merge_context.

<!-- fr:journal kind=finding scope=plan id=p2-r10-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=open resolves=p2-r10 out_of_scope=true -->
### p2-r10-resolved · finding [out-of-scope] · resolves p2-r10: A conflict at an unchanged head after a finished hand-back is skipped forever (phase 2)

Not caused by this change's design choice: the skip-on-same-head rule is the spec's (§E/R12) and pre-exists for batch-PR conflicts (conflict_decision). An escalation after a finished hand-back is a rule change for both, so it belongs to its own issue.

<!-- fr:journal kind=finding scope=plan id=p2-r11-resolved created=2026-10-14T01:44:35+00:00 phase=2 state=fixed resolves=p2-r11 -->
### p2-r11-resolved · finding [fixed] · resolves p2-r11: Merge-pin bypass (TOCTOU): the archive merge could be pinned to a head CI never judged (phase 2)

2d7298e0: _pinned reads head, then checks, then head again. A moved head is pending, with no archive action and no pr_merge, and the merge stays pinned with --match-head-commit to that head. Collected counts are used only at their collected head. Tests test_an_archive_pr_pushed_between_its_view_and_its_checks_is_never_merged[facts/head] (re-run by the orchestrator: passed).

<!-- fr:journal kind=decision scope=plan id=p3-ctx-or-hold created=2026-10-14T01:54:17+00:00 phase=3 -->
### p3-ctx-or-hold · decision · One _ctx_or_hold helper is the catch-and-say for every merge_ctx caller (phase 3) (phase 3)

DefaultBranchUnknown(ForgeReadError, code 2) is raised only by the fetch and default_branch read (via _fresh_config(hold_unknown=True), which other _fresh_config callers do not set) and by _base_rules' default_branch read (GitError). _ctx_or_hold catches that type alone and prints "held: <repo> default branch unknown (<cause>)" once per repo per pass (_unknown_said, reset each pass). Callers: _merge_batch, _enqueue, _recover, _hand_back, _archive, _hand_back_archive, _export_merge. _queue_reads keeps its own earlier hold ("queue mode unknown"). A held --once pass exits 3 (work remains), as any held merge does.

<!-- fr:journal kind=discovery scope=plan id=p3-wait-out-pin-1178 created=2026-10-14T01:54:17+00:00 phase=3 -->
### p3-wait-out-pin-1178 · discovery · wait_out renewal spends no GraphQL, the test passed on arrival (phase 3) (phase 3)

test_wait_out_renewal_spends_no_graphql_in_an_exhausted_window passed immediately, as expected: #1153 landed R12 (visibility read via REST repo_visibility). It is the regression pin for #1178, not a fix.

<!-- fr:journal kind=discovery scope=plan id=p3-heal-test-passes-on-arrival created=2026-10-14T01:54:17+00:00 phase=3 -->
### p3-heal-test-passes-on-arrival · discovery · The origin/HEAD heal test already passed; the unreachable-origin one was the red one (phase 3) (phase 3)

Checkout.default_branch already heals a missing origin/HEAD with `remote set-head --auto`, so test_yes_pass_over_a_clone_without_origin_head_heals_and_merges is a pin. Deviation: the unreachable-origin test uses one repo (World is single-repo), so "the other repo's work still runs" is not asserted; the hold is per repo by construction (_unknown_said is keyed by repo).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-14T01:54:17+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

a test-only task over an already-correct renewal path; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-14T01:54:17+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

acceptance status moves only; no code
