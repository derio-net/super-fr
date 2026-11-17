<!-- fr:journal-schema=4 -->
# Journal: 2026-11-17-triage-intake

<!-- fr:journal kind=decision scope=plan id=p1-intake-admits-bot-logins created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-intake-admits-bot-logins · decision · Intake also admits the debt workflow's bot logins (BOT_LOGINS) (phase 1)

R2 names claim_trusted(config, viewer) only. check already trusts fr.debt.render.BOT_LOGINS as a debt-digest author, and collect now clears the body of an ineligible issue, so a bot-authored digest (whose association is not OWNER/MEMBER/COLLABORATOR) would lose the marker in its body and stop being read as a digest. intake_trusted() is claim_trusted | BOT_LOGINS, used by collect, issue_reason and the association-read gate. No second association list; only the login set widens, by the logins check already trusts.

<!-- fr:journal kind=decision scope=plan id=p1-create-edit-leave-unjudged-to-save created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-create-edit-leave-unjudged-to-save · decision · create/edit leave an uncollected AND unjudged member to the save's own refusal (phase 1)

rejected_members rejects an absent key as `not collected` (R6). For create and edit, _refuse_rejected passes the judgements and skips an uncollected member that is not judged either, so the existing `members [...] are not judged` refusal (exit 2, nothing written) still names the real cause. dispatch passes no judgements, so it rejects every uncollected member as R6 says.

<!-- fr:journal kind=decision scope=plan id=p1-acceptance-record-shape created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-acceptance-record-shape · decision · Acceptance moves use the AcceptanceItem shape, not {row, op} (phase 1)

The four intake rows are still pending on this branch (not merged on the default ref), so a record entry is a row move ({id, status, notes, levels}), not an amendment; the {row, op, ...} shape the brief gave is for merged rows. Levels are unit refs anchored on test names.

<!-- fr:journal kind=discovery scope=plan id=p1-circular-import-batch-intake created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-circular-import-batch-intake · discovery · fr.triage.batch cannot import fr.triage.intake at module level (phase 1)

intake -> claims -> batch is a cycle. suggest() imports untrusted_issues inside the function. check.py, collect.py, views.py and triage_batch_cmd.py import intake at module level without a cycle.

<!-- fr:journal kind=discovery scope=plan id=p1-rest-list-carries-association-outside-projection created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-rest-list-carries-association-outside-projection · discovery · REST list_issues returns authorAssociation outside the field projection (phase 1)

_project() raises on a field the record lacks and cuts to the requested fields, and `gh issue list --json` has no association field, so collect cannot ask for it. RealGhRestClient.list_issues adds authorAssociation to each projected record (empty string when absent); collect reads the key's presence to skip the extra read.

<!-- fr:journal kind=discovery scope=plan id=p1-fixture-churn-from-intake created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-fixture-churn-from-intake · discovery · Many fixtures built issues with no author; intake now treats them as untrusted (phase 1)

Fixtures gained author_association OWNER (the shared _issue helpers, triage_board_fixtures.issue, the scenario fixture generators, which were regenerated at schema 14), FakeForge.issue_associations answers OWNER for an unscripted repo, and the old `untrusted marker stays ranked` assertion in test_triage_debt_sets now says it is set apart. Facts schema asserts moved 13 -> 14.

<!-- fr:journal kind=discovery scope=plan id=p1-ready-fr-also-created-by-init-scaffold created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-ready-fr-also-created-by-init-scaffold · discovery · init scaffold and merge --yes create ready-fr too (phase 1)

They share ensure_approval_label, which now ensures both labels; their tests assert both. Each label is checked and created on its own, so one failure never hides the other.

<!-- fr:journal kind=discovery scope=plan id=p1-dispatch-repair-also-refuses created=2026-11-17T12:32:05+00:00 phase=1 -->
### p1-dispatch-repair-also-refuses · discovery · dispatch --repair is refused for a batch with a rejected member (phase 1)

R6 places the check in dispatch_batch after the repo is resolved and before the tracking gate, which `--repair` shares. A dispatched batch whose member is later edited by an outside author or closed with no association therefore needs ready-fr (or removing the member) before a repair, as the spec's rule reads.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a one-constant label and a fragment: nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the association read mirrors the existing optional-read helpers (_closed_in_progress, _gated_prs); no duplication to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

one small final step in collect (_withhold_untrusted_bodies); no earlier code was repeated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

is_set_apart gained one clause and CheckResult one field, matching the existing sets; nothing to simplify

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

one shared helper (_refuse_rejected) already serves create, edit and dispatch, and one builder (rejected_by_batch) serves both snapshots

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

render_brief changed in place around one helper (quote_untrusted); no duplicate remained

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t8 created=2026-11-17T12:32:05+00:00 phase=1 -->
### no-refactor-p1-t8 · discovery · no-refactor-because P1.T8 (phase 1)

ensure_approval_label now loops over its two labels; the loop is the cleanup

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-17T14:44:50+00:00 phase=1 -->
### review-phase-1 · review · Phase 1 code review (intake trust R1-R8): boundary holds; 5 in-scope findings, 1 out (phase 1)

Independent read-only reviewer over 8228c5e..HEAD. Confirmed: body withholding is the single
final collect step over listed, viewed and carried issues; logins/associations compared
case-insensitively; unread author/association fails closed; both snapshot builders fill
`rejected` and the pass checks it before `after` and the cap; create/edit/dispatch refuse
before any write; schema 13 -> 14 load tested; fr never applies `ready-fr`; `quote_untrusted`
splits every line break and prefixes each line, so the close marker cannot be forged.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-17T14:44:50+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Close-out, red-CI, conflict and archive-conflict briefs and dispatch_comment embed batch.title unquoted (phase 1)

batch_dispatch.py:256,290,315,338 and batch_drive.py:821. A batch title written from issue text reached the command line of a new session. Spec R7 covered only the launch brief: spec amended (3b8409ae8).

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-17T14:44:50+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · view_issue never reads authorAssociation, so a viewed trusted member's issue is rejected (phase 1)

gh.py:288 ISSUE_VIEW_FIELDS and collect.py ~825. Fails closed, but blocks a MEMBER's batch past the list limit until ready-fr. Spec R1 amended (3b8409ae8).

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-17T14:44:50+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · BOT_LOGINS admission makes every github-actions issue eligible, not only the debt digest (phase 1)

intake.py:35. A workflow filing issues from untrusted input would yield batchable, body-kept issues with no operator step. Spec R2 amended: the bot is admitted only with the digest marker; merge-protection.md lists the clause.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-17T14:44:50+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · ready-fr label match is case-sensitive while the forge's labels are not (phase 1)

intake.py:46. Spec R2 amended to compare label names case-insensitively.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-17T14:44:50+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · dispatch --repair refused for an already-dispatched batch with a rejected member (phase 1)

triage_batch_cmd.py:1827.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-17T14:44:50+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · Titles of ineligible issues still reach facts.json and triage check output (phase 1)

Per spec R3 (bodies only). Residual injection vector through titles read by the triage agent; a future hardening pass, not caused by this change, which narrows the surface.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-17T14:44:50+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Close-out, red-CI, conflict and archive-conflict briefs and dispatch_comment embed batch.title unquoted (phase 1)

Fixed in 563a780dc and 23feaa3f4: every batch brief and dispatch_comment names the batch by id; titles sit in the quoted untrusted block (title_block); hostile-title tests in tests/unit/test_batch_brief_titles.py.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-17T14:44:50+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: view_issue never reads authorAssociation, so a viewed trusted member's issue is rejected (phase 1)

Fixed in fead4edbe: viewed issues get their association through the same per-repo issue_associations read (none when login or label admits; None on a failed read).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-17T14:44:50+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: BOT_LOGINS admission makes every github-actions issue eligible, not only the debt digest (phase 1)

Fixed in fead4edbe: intake_reason judges the body; the debt bot is admitted only with the digest marker, judged before withholding; merge-protection.md lists the clause.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-17T14:44:50+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: ready-fr label match is case-sensitive while the forge's labels are not (phase 1)

Fixed in fead4edbe: ready-fr compared case-insensitively.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-17T14:44:50+00:00 phase=1 state=refuted resolves=p1-r5 -->
### p1-r5-resolved · finding [refuted] · resolves p1-r5: dispatch --repair refused for an already-dispatched batch with a rejected member (phase 1)

Kept on purpose. At a security boundary a batch whose member is now ineligible must be admitted with ready-fr before fr writes to the forge for it again; repair re-posts the dispatch comment and labels derived from member text. The unread-association case the reviewer cited is removed by the p1-r2 fix, so a trusted member's batch is no longer blocked by it.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-17T14:44:50+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: Titles of ineligible issues still reach facts.json and triage check output (phase 1)

R3 deliberately clears bodies only; titles are needed to triage at all. Not caused by this change, which removes the body surface; title hardening is a separate decision.

<!-- fr:journal kind=decision scope=plan id=p2-held-reason-stored-per-pass created=2026-11-17T15:50:30+00:00 phase=2 -->
### p2-held-reason-stored-per-pass · decision · merge_ctx holds a repo by storing its DefaultBranchUnknown for the pass (phase 2) (phase 2)

_ctx_held maps repo to the DefaultBranchUnknown raised first and re-raises that same instance, so every later use is instant, with no second fetch and, through _ctx_or_hold's existing _unknown_said set, no second warning. The allowed merge methods are kept in _allowed[repo] from the build; method is recomputed each use with choose_method over them.

<!-- fr:journal kind=discovery scope=plan id=p2-driver-loop-test-green-before-impl created=2026-11-17T15:50:30+00:00 phase=2 -->
### p2-driver-loop-test-green-before-impl · discovery · The loop-level held-pass test already passed before the change (phase 2) (phase 2)

In a loop pass a failed fetch is first met by _fetched_reader / _archived readers, which hold or skip the pass by design (gh#1025), so the end-to-end test guards the behaviour (one fetch when a reader fetched first, held pass, acts again) but is not red against the old code. The red tests are the two merge_ctx unit tests (method/version refresh with one methods read, hand-back held).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-17T15:50:30+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

the _fresh_config split removed the duplication it would have left; nothing else to clean

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-11-17T15:57:28+00:00 phase=2 -->
### review-phase-2 · review · Phase 2 code review (R9 per-pass fetch): contract holds; 2 in-scope test gaps, 1 out (phase 2)

Independent read-only reviewer over e3c1d1f0a..HEAD. Confirmed: merge_ctx checks _ctx_held first, fetches
unless _fetched has the repo, re-checks the config; _ctx_checked/_ctx_held reset beside _fetched each pass;
every caller (including _closeout_hand_back) goes through _ctx_or_hold; held repos spend no budget;
version and method follow each pass's config, allowed methods read once at build; no double fetch.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-17T15:57:28+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · Loop-level held-pass test passes on lifetime-cached code because other readers fetch every pass (phase 2)

tests/unit/test_triage_batch_drive_cmd.py test_a_failed_fetch_holds_the_repo_for_that_pass_only_and_fetches_once_per_pass.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-17T15:57:28+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · No unit test that a held repo re-raises without a second fetch, nor that a stale config leaves the repo unchecked (phase 2)

The hold is spec step 1 of §B.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-17T15:57:28+00:00 phase=2 state=open review_scope=out -->
### p2-r3 · finding [open] (reviewer: out of scope) · _fetched_reader lets GitError escape and does not record the failed fetch, so a pass may retry it (phase 2)

triage_batch_cmd.py ~4811. Pre-existing reader; the spec bounds only the merge-context fetch.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-17T15:57:28+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: Loop-level held-pass test passes on lifetime-cached code because other readers fetch every pass (phase 2)

dbaa04087: the loop test spies on merge_ctx and asserts pass 2's use is held and pass 3's ok; reverting the per-pass reset turns it red. The check-once-never-refetch variant is caught by test_the_merge_context_follows_each_passs_config_without_a_second_methods_read (expects a second fetch after the pass reset).

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-17T15:57:28+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: No unit test that a held repo re-raises without a second fetch, nor that a stale config leaves the repo unchecked (phase 2)

dbaa04087: two _Clone unit tests — a failed fetch holds and re-raises DefaultBranchUnknown with one fetch; a stale config raises ForgeReadError code 2 and leaves the repo out of _ctx_checked and _ctx_held.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-17T15:57:28+00:00 phase=2 state=open resolves=p2-r3 out_of_scope=true -->
### p2-r3-resolved · finding [out-of-scope] · resolves p2-r3: _fetched_reader lets GitError escape and does not record the failed fetch, so a pass may retry it (phase 2)

Not caused by this change: _fetched_reader's fetch handling predates it and R9 bounds only the merge-context fetch; merge_ctx itself holds after one failure.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-17T16:41:51+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

one bounded loop replacing a single call; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-17T16:41:51+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

_open_checkout delegates to the new _checkout_refusal; nothing left to fold

<!-- fr:journal kind=decision scope=plan id=p3-close-never-raises-drops-forge-failures created=2026-11-17T16:41:51+00:00 phase=3 -->
### p3-close-never-raises-drops-forge-failures · decision · close.py _FAILURES tuple removed (phase 3)

close_gate_trackers now catches Exception at all three sites, so the _FAILURES tuple (FORGE_ERRORS + UnsupportedForgeOperation) had no remaining user and was deleted with its imports. The list-read message keeps its prior text; per-issue errors read `issue #<n>: <Type>: <msg>`; a failed EvidenceReader build reports `evidence not read: <Type>: <msg>` and closes nothing.

<!-- fr:journal kind=review scope=plan id=review-phase-3 created=2026-11-17T16:47:21+00:00 phase=3 -->
### review-phase-3 · review · Phase 3 code review (R10-R12): no blocking defects; 1 in-scope, 2 out (phase 3)

Independent read-only reviewer over 8f02d19..HEAD. Confirmed: a missing ADD is never swallowed, the retry is
bounded and idempotent, the REST 404 tolerance is untouched; the dry run and --yes share _checkout_refusal and
the dry run exits 0 writing nothing; close_gate_trackers catches Exception (not BaseException) at all three
sites, isolates each issue and records `issue #<n>: <Type>: <msg>`; _pass_gate reports the summary; nothing
imported close._FAILURES.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-17T16:47:21+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · swap_issue_labels' regex cannot match a label name holding an apostrophe, so #1406 stays unfixed for it (phase 3)

gh.py ~436. Fails safe (re-raises), but the fix did not cover such labels.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-17T16:47:21+00:00 phase=3 state=open review_scope=out -->
### p3-r2 · finding [open] (reviewer: out of scope) · The retry assumes gh resolves all labels before mutating; unverified without a live gh (phase 3)

A repeated add or removal is idempotent, so the retry is safe either way; only the docstring's claim was too strong.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-17T16:47:21+00:00 phase=3 state=open review_scope=out -->
### p3-r3 · finding [open] (reviewer: out of scope) · close_gate_trackers returns early on an EvidenceReader failure instead of recording per issue (phase 3)

Matches the 'not read' semantics; the reader is shared by every issue, so per-issue recording would repeat one error.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-17T16:47:21+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: swap_issue_labels' regex cannot match a label name holding an apostrophe, so #1406 stays unfixed for it (phase 3)

ba9de9d0a: each pending removal is matched by its exact quoted name (no name parsing); test test_an_undefined_removal_whose_name_holds_an_apostrophe_is_dropped was red first.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-17T16:47:21+00:00 phase=3 state=open resolves=p3-r2 out_of_scope=true -->
### p3-r2-resolved · finding [out-of-scope] · resolves p3-r2: The retry assumes gh resolves all labels before mutating; unverified without a live gh (phase 3)

gh's resolve-before-mutate order is gh's behaviour, not this change's; ba9de9d0a reworded the docstring to state that a partial apply would only repeat idempotent edits.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-17T16:47:21+00:00 phase=3 state=refuted resolves=p3-r3 -->
### p3-r3-resolved · finding [refuted] · resolves p3-r3: close_gate_trackers returns early on an EvidenceReader failure instead of recording per issue (phase 3)

Not a defect: one shared reader failing means no issue can be judged; recording it once is the accurate report.
