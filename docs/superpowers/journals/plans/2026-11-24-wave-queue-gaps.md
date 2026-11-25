<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-wave-queue-gaps

<!-- fr:journal kind=decision scope=plan id=p1-stack-target-two-sides created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-stack-target-two-sides · decision · The command layer and the planner compute the stack target with one function (phase 1)

`queue_handback.stack_target(rep)` is the last combination on the replay's base that
holds no ejected entry, else the base. The planner calls it on the combinations `_valid`
leaves after this pass's ejections (`aimed`); the driver's `lineage_reads` calls it on
the last record's replay (or uses `main` now when the record's base is stale). The
planner's target is always a prefix of the records', so an `onto` the planner named is an
ancestor of the target `leads` is read against, and a re-issue never fires spuriously.

<!-- fr:journal kind=decision scope=plan id=p1-carry-brief-mark created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-carry-brief-mark · decision · A carry brief is recorded as a free re-issue at the carrying head (phase 1)

No new event kind: the carry brief writes `ConflictEvent(head=<carrying head>,
onto=<target>, reissue=true)`, paths taken from the batch's latest conflict. That is the
once-per-head mark (`lineage_actions` emits `queue-carry` only for a head with no conflict
event) and spends no budget. With no clean hand-back head the event is `held`, which the
board already shows as a merge-conflict Need.

<!-- fr:journal kind=decision scope=plan id=p1-base-target-brief created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-base-target-brief · decision · In slot mode with nothing standing the brief reads as today (phase 1)

Per plan P1.T3.S3, a target on the default branch (`onto_ref` `origin/<default>`) keeps
today's step 2 (`git fetch origin && git merge origin/<default>`); only an `fr-queue/`
ref gets the slot wording and the wait-for-a-re-issue check. The event still records
`onto` (the base sha), so a later move is judged by `leads`.

<!-- fr:journal kind=discovery scope=plan id=p1-fresh-twin created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-fresh-twin · discovery · Checkout.carried drops a combination rebuilt fresh into main's history (phase 1)

An R13 fresh rebuild has the same tree and parents as the combination it replaces but a
new sha, so a head that merged the original would read as carrying it once the twin
landed. `carried` looks, per candidate, for a commit in the target's history since the
candidate's first parent with the same tree and parents (one `git log` per candidate,
only for built shas the head reaches).

<!-- fr:journal kind=discovery scope=plan id=p1-explicit-reexport created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-explicit-reexport · discovery · mypy needs src importers of the moved rules to import from handback_rules (phase 1)

`batch_drive` re-exports the moved names for tests and other callers, but mypy's
no-implicit-reexport refuses `from fr.triage.batch_drive import conflict_decision` in
src. `wave_queue`, `views` and `triage_batch_cmd` now import them from
`fr.triage.handback_rules`; one import line changed in `triage_batch_cmd`.

<!-- fr:journal kind=finding scope=plan id=p1-acceptance-check-foreign-rows created=2026-11-25T00:43:26+00:00 phase=1 state=open review_scope=out -->
### p1-acceptance-check-foreign-rows · finding [open] (reviewer: out of scope) · fr acceptance check --no-fetch reports 43 errors on other features' rows (phase 1)

Rows such as `issues-page-filter-guard` and `privacy-snapshot-keys` name tests and a spec
(`2026-11-22-triage-hardening`) this branch does not have; the fold reads them from the
default ref, which is ahead of this branch's base. None is a wave-queue-gaps row; a merge
of origin/main into the branch should clear them.

<!-- fr:journal kind=discovery scope=plan id=p1-t5-test-order created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-t5-test-order · discovery · The T5.S1 driver tests were written after the T5.S2 wiring (phase 1)

The slot, re-issue and carry driver tests in test_triage_batch_drive_cmd.py passed on
first run because the wiring landed first (red was not observed for them). They assert
strings only the new code produces (`fr-queue/`, `git merge <sha>`, `Merge queue carry`,
`reissue: true`), so they would fail without it.

<!-- fr:journal kind=lens scope=plan id=lens-errors-1 created=2026-11-25T00:43:26+00:00 phase=1 lens=errors step=implement-phase -->
### lens-errors-1 · lens · GitError is mapped to None (R5) in lineage reads and the carry reset search; check no unreadable answer is read as leads or carries nothing (phase 1)

<!-- fr:journal kind=lens scope=plan id=lens-tests-1 created=2026-11-25T00:43:26+00:00 phase=1 lens=tests step=implement-phase -->
### lens-tests-1 · lens · the driver hand-back tests were written after the code; check they pin behaviour, and that the planner tests cover the third-pass no-op (phase 1)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-25T00:43:26+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a smoke module and a mechanical move out of the budgeted modules; the move is the cleanup, and the delegate is one line

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-25T00:43:26+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

a stamp bump and two optional defaulted fields refused below 14 beside the existing checks; nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-25T00:43:26+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

new pure helpers, and conflict_brief moved as it was plus one step-2 branch; batch_dispatch re-exports it by name

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-25T00:43:26+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the planner logic went into queue_handback helpers from the start (wave_queue grew by the calls only); the two gitseam reads are small methods with no shared shape to extract

<!-- fr:journal kind=finding scope=plan id=p1-acceptance-check-foreign-rows-resolved created=2026-11-25T02:00:28+00:00 state=open resolves=p1-acceptance-check-foreign-rows out_of_scope=true -->
### p1-acceptance-check-foreign-rows-resolved · finding [out-of-scope] · resolves p1-acceptance-check-foreign-rows: fr acceptance check --no-fetch reports 43 errors on other features' rows

Not caused by this change: the fold reads other features' rows from origin/main (triage-hardening, intake-admit), whose specs and tests this branch's base predates. Merging origin/main into the branch clears it; the run merges origin/main before deliver.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-25T02:00:31+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · The carry brief's rev-list lists the dead slot commit, so the cherry-pick reapplies what R4 drops (phase 1)

queue_handback.carry_brief step 2 ran `git rev-list --no-merges --reverse <reset>..origin/<branch>`: a squash slot commit (single parent) and, under merge, the ejected entry's second-parent commits are listed. Fix: `--first-parent --no-merges`; an integration test runs the brief's commands over the queue_git World.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-25T02:00:31+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · A budget-held conflict event is re-issued free when its onto stops leading (phase 1)

reissue_due and reissue_actions ignored `delivered`, so a ConflictEvent(delivered=held) whose onto stopped leading reached _queue_hand_back(reissue=True) and was briefed to the session for free. Fix: no re-issue when delivered == held.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-25T02:00:31+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · With no slot standing, the carry brief and merge_clause fetch `origin/origin/<default>` (phase 1)

carry_brief step 2 and merge_clause emitted `git fetch origin origin/<default>` when handback_onto / target_ref returned `origin/<default>`. Fix: fetch the bare branch name.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-25T02:00:31+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · OtherEntry keys never get queue_carries, so a carrying non-batch PR is built and landed (phase 1)

lineage_reads looped only over the batch live map; close-out, archive, export and housekeeping entries are admitted later in the pure pass. Fix: read each open non-batch PR head's carry into Snapshot.queue_head_carries, and queue_snapshot gives each admitted entry the carry of the head it is built at.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-25T02:00:31+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · The rebuild-on-moved-main branch builds carrying entries (phase 1)

wave_queue._plan_open returned from the R14 rebuild branch before hold_lineage ran. Fix: hold_lineage runs first, the rebuild window is built from what remains, and the held entries' carry actions are planned on that pass.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-25T02:00:31+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · An unreadable reset candidate writes a durable held ConflictEvent (violates R5) (phase 1)

carry_hand_back treated a GitError on a reset candidate as not free and, with no clean head, wrote a held conflict event: a transient error became a permanent Need. Fix: when no candidate is clean and one raised, hold for the pass with a line and write no event.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-25T02:00:31+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · lineage_reads has no test, and no drive test lets the planner emit queue-reissue/queue-carry (phase 1)

Driver tests scripted planner actions and DriveCheckout.leads always returned True. Fix: direct lineage_reads tests over a fake driver/clone, and drive tests where the real planner plans the carry and the re-issue.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-11-25T02:00:31+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · fr-triage SKILL.md still describes the pre-R1 conflict hand-back (phase 1)

SKILL.md said the brief merges origin/main, never hands a head back twice, never force-pushes, at most two hand-backs. Fix: describe the stack target, the free re-issue, the carry brief and the R5 hold, matching the fr-wave-driver explainer; mirrors regenerated.

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-25T02:00:31+00:00 phase=1 -->
### review-p1-1 · review · independent code review of phase 1: 8 findings, all in scope (phase 1)

Independent reviewer read phase 1 (910c0b9..cb22ff3) against R1-R6, R16 and spec sections A, D, E. Eight in-scope findings: the carry brief's rev-list and fetch ref, a held hand-back re-issued free, non-batch entries never lineage-checked, the moved-main rebuild skipping the carry hold, a transient GitError turned into a durable Need, missing lineage_reads and end-to-end planner tests, and stale skill prose. All eight fixed with tests.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-25T02:00:31+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: The carry brief's rev-list lists the dead slot commit, so the cherry-pick reapplies what R4 drops (phase 1)

carry_brief step 2 lists `git rev-list --first-parent --no-merges --reverse`; tests/integration/test_queue_lineage.py::test_the_carry_brief_drops_the_dead_slot_commit (slot and no-slot) runs steps 2-4 in a session clone and asserts the slot sha is neither listed nor an ancestor of the rebuilt head; unit test test_the_carry_brief_lists_first_parent_commits_only.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-25T02:00:31+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: A budget-held conflict event is re-issued free when its onto stops leading (phase 1)

reissue_due returns False for delivered == held and reissue_actions skips a held event (no warning either); tests test_a_held_handback_is_never_reissued_free (unit) and test_a_budget_held_handback_is_not_reissued_when_its_onto_stops_leading (planner).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-25T02:00:31+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: With no slot standing, the carry brief and merge_clause fetch `origin/origin/<default>` (phase 1)

target_ref returns the bare default branch and carry_brief fetches fetch_name(onto_ref) (origin/ stripped); tests test_the_carry_brief_with_no_slot_fetches_the_bare_default_branch, test_the_merge_clause_with_no_slot_fetches_the_bare_default_branch, and the integration test's no-slot case runs the fetch.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-25T02:00:31+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: OtherEntry keys never get queue_carries, so a carrying non-batch PR is built and landed (phase 1)

lineage_reads returns queue_head_carries (repo -> open non-batch PR head -> carry, GitError None); batch_drive._carries merges it into QueueSnapshot.carries by each admitted entry's built head. Tests test_a_non_batch_prs_head_is_read_by_head, test_an_admitted_entry_takes_its_carry_by_the_head_it_is_built_at and the drive test test_a_non_batch_entrys_head_has_its_carry_read.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-25T02:00:31+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: The rebuild-on-moved-main branch builds carrying entries (phase 1)

_plan_open runs hold_lineage before the R14 branch; the rebuild window is drawn from the remaining entries and the held entries' lineage_actions are planned on the moved base. Test test_a_carrying_entry_is_not_rebuilt_when_main_moved.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-25T02:00:31+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: An unreadable reset candidate writes a durable held ConflictEvent (violates R5) (phase 1)

carry_hand_back remembers a candidate that raised; with none clean it returns a 'held this pass: git could not read' line and writes no event. Test test_an_unreadable_reset_candidate_holds_the_carry_this_pass_only.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-25T02:00:31+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: lineage_reads has no test, and no drive test lets the planner emit queue-reissue/queue-carry (phase 1)

tests/unit/test_operator_entries_lineage.py covers the land/method filter, the built set from every record of the scope, the target (last standing, main when the record base is stale), the per-(sha, target) cache and GitError -> None never cached; the fake DriveCheckout now scripts leads/carries/GitError, and test_the_planner_holds_a_carrying_head_with_one_queue_carry / test_the_planner_reissues_a_handback_whose_onto_stopped_leading drive the real planner.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-11-25T02:00:31+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: fr-triage SKILL.md still describes the pre-R1 conflict hand-back (phase 1)

plugins/super-fr/skills/fr-triage/SKILL.md's conflict hand-back sentence now names the stack target and onto, the free re-issue (never for a held one), the carry brief and its force-push, the non-batch Need and the R5 pass hold; sync-opencode.py and sync-hermes.py regenerated the mirrors.

<!-- fr:journal kind=decision scope=plan id=p2-default-branch-read created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-default-branch-read · decision · queue add reads the default branch from the forge (new GhClient.repo_default_branch) (phase 2)

The verb runs with no clone, and facts carry no default branch, so R11's base check
needs a forge read. `repo_default_branch(repo)` is on the GhClient protocol, both GitHub
adapters (`GET repos/{repo}`) and the unsupported mixin (glab/tea raise). It raises when
unread, and the verb refuses on any forge error, so no refusal or admission rests on an
unread answer. The driver keeps its own base check (`base_refusal`) at admission.

<!-- fr:journal kind=decision scope=plan id=p2-verb-push-now created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-verb-push-now · decision · queue add/remove push the state ref inside the command and restore the file on a refused push (phase 2)

R11 says a refused push exits 2. The deferred push of `_sync_with_ref` only warns on a
remote refusal, so the verb calls `push_now` after the write; any `TriageError` (a CAS
conflict, a refusal, the privacy guard) restores judgements.yaml byte for byte and exits
2 with "nothing changed, run the command again". Re-running then never meets "already
added" for a write that never left the host.

<!-- fr:journal kind=decision scope=plan id=p2-trust-before-preapproval created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-trust-before-preapproval · decision · An added non-batch PR is trust-checked before any preapproval write (phase 2)

R13 lists the adder's trust, green checks and no conflict; R12's admission also needs a
same-repo PR by an allowed author. `operator_reads` checks the PR's own trust (and that it
is no reserved close-out/archive/export/housekeeping PR) first, so the driver never adds
`approved-fr` to a fork or a stranger's PR that collect now reads differently. Such a PR
stays pending (R15: added, open, unlanded), so it holds the drain and, after
`stall_hours`, gives the Need naming `queue remove`.

<!-- fr:journal kind=decision scope=plan id=p2-live-checks created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-live-checks · decision · Preapproval and operator admission read the PR's checks live (phase 2)

`checks_verdict` falls back to the collected counts when no check is required; for an
operator PR those can be the counts of an older head. `operator_reads` builds the counts
from `pr_checks` read now, so a preapproval never approves a new head on its
predecessor's green.

<!-- fr:journal kind=decision scope=plan id=p2-operator-eject-no-verdict created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-operator-eject-no-verdict · decision · An operator eject is no verdict on the head: replay drops it from the order only (phase 2)

A `queue_eject` with reason `operator` removes the key from `Replay.order` and records
nothing in `ejected`, so a PR removed and added again joins at once at the same head
rather than waiting for a push. The executor records the event and hands nothing back.

<!-- fr:journal kind=decision scope=plan id=p2-operator-under-placement created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-operator-under-placement · decision · Operator entries stay queue entries in a repo that keeps no fr artifacts (phase 2)

`queue_snapshot` drops every non-batch entry when the repo's placement is not `repo`
(no close-out, archive, export or housekeeping PR lands there). An operator PR is no fr
artifact, so it is kept; the filter keeps `kind == "operator"` admissions.

<!-- fr:journal kind=discovery scope=plan id=p2-entry-builder-kinds created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-entry-builder-kinds · discovery · The executor's entry builder refused every kind it did not list (phase 2)

`_Driver._queue_entry` returned None for a non-batch key whose kind was not closeout,
archive, export or housekeeping, so an admitted operator entry would have been planned
and never built. The planner and RecordingQueue tests could not see it; the driver seam
test now calls `RecordingQueue.ports.entry_of("operator#300")`. Like a close-out, an
operator draft is readied when the queue builds it.

<!-- fr:journal kind=discovery scope=plan id=p2-t3-test-order created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-t3-test-order · discovery · The T3.S1 operator_reads tests were written after operator_reads (phase 2)

Red was not observed for tests/unit/test_operator_reads.py: the module was written
first. They assert forge writes, recorded approval events and the snapshot fields the
read returns, which only the new code produces. The T1, T2 and T4 tests were red first;
the driver seam test's entry build was red with the command wiring stashed.

<!-- fr:journal kind=discovery scope=plan id=p2-archive-docstring created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-archive-docstring · discovery · archive_conflict_decision's 'never twice' docstring was accurate; reworded, not changed (phase 2)

The free re-issue is the batch PR's `conflict_decision` only; an archive PR's conflict is
still skipped at any head that has an `archive_conflict` event. Both docstrings now say
which rule re-issues. The merge of origin/main resolved six conflicts (skill by a
token-level three-way merge, mirrors regenerated; three explainer stamps keep both
sides; batch_dispatch keeps main's `unicodedata` and drops the `shlex` the move left
unused); every module stays within its budget.

<!-- fr:journal kind=discovery scope=plan id=p2-fast-tier-tripwires created=2026-11-25T03:35:45+00:00 phase=2 -->
### p2-fast-tier-tripwires · discovery · The fast tier caught two tripwires: the archive preview's method sets and the approval-label prose (phase 2)

`fr.archive_preview.READS` must name every GhClient method, so `repo_default_branch`
joined it. `test_tripwire_approval_label_prose` refuses a shipped sentence asking anyone
but the operator to add `approved-fr`; the skill's preapproval sentence now says the
operator approves in advance and the driver labels on the operator's behalf, which is
what R13 grants. The first fast tier run (10252 passed, these 2 failed) covered the whole
branch; after the fix the tier was run again over the fix commit's delta.

<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-11-25T03:35:45+00:00 phase=2 lens=security step=implement-phase -->
### lens-security-1 · lens · preapproval lets the driver add approved-fr itself; check the adder, PR trust, conflict and patch-id gates and the audit comment (phase 2)

<!-- fr:journal kind=lens scope=plan id=lens-errors-2 created=2026-11-25T03:35:45+00:00 phase=2 lens=errors step=implement-phase -->
### lens-errors-2 · lens · queue add's forge reads and state push, and operator_reads' unreadable patch-id, must fail closed for the pass, never write a durable event (phase 2)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-25T03:35:45+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

two closed-world event models, a ten-line pure fold and a writer that is the sibling of save_queues over the shared _rewrite; nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-25T03:35:45+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the verb imports _load_state, _scope, fail and push_now from triage_cmd and the trust helpers from batch; its one new forge read (repo_default_branch) sits in each adapter beside repo_visibility; the reserved-entry check lives in operator_entries, shared with the driver

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-25T03:35:45+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

operator_reads follows housekeeping_reads' shape on purpose (same settle, same writer) so the two trust rules read side by side; the preapproval conditions are one function (_preapprove) the batch and operator paths both call

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-25T04:48:17+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · R13: a preapproval could be recorded approved at a head the driver never checked or commented on (phase 2)

`_preapprove` returned early when approved-fr was already on, and added the label before the audit comment; `settle_approvals`/`settle_entry_approval` read a label with no live approval as `First` at the live head. For a batch PR `_preapprove` only labelled, and the batch's approval was recorded at the start of the NEXT pass, so a session push between passes was recorded approved at an unvetted H2 while the audit comment named H1. For an operator PR a failed `comment_pr` after `edit_issue_labels` left a label the next pass recorded as First at the live head with no audit comment. Fix: comment, then record the approval at the vetted head and patch-id, then label.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-25T04:48:17+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · R14/R15: the drive loop counted no operator work and ended over an undrained queue (phase 2)

Operator entries counted toward none of the Summary figures and `_operator_stall` returns nothing before stall_hours, so once every batch finished `Summary.done` was true and the loop exited, leaving a wave queue undrained with its hold open, or a between-waves queue built but never landed. Fix: count each pending operator entry (added, not removed, open, unlanded) as `pending` unless its stall Need is reported this pass (that Need is already counted blocked).

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-25T04:48:17+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · R11/R12: `queue add` to a repo with no batch was silently inert (phase 2)

`queue add` accepts any repo in facts.repos, but the driver's repos map is built from batches only, and operator_reads / _wave_queue_reads (and the housekeeping, barrier, lineage and placement reads) loop only over it. Fix: the queue readers get the batch map plus every collected repo a queue request of the scope names (unread/carried still skipped), so R14's between-waves queue works in a repo with no batch.

<!-- fr:journal kind=decision scope=plan id=p2-d1 created=2026-11-25T04:48:17+00:00 phase=2 -->
### p2-d1 · decision · p2-r1: preapproval records its own approval before the label, rather than trusting a label-only First beside an audit marker (phase 2)

Of the two sound options, recording the approval in the preapproval itself is the simpler: it uses the existing settle rule unchanged (a push changing the diff voids by patch-id) and needs no comment read. Order is audit comment, then the approval event (a batch PR's `ApprovalEvent` through the one batch event writer, an operator PR's queue `approval`), then the label: any failure before the label leaves no label, so nothing is approved; a recorded approval without its label is `Unlabelled`. A label already on with no live approval still settles as First: that is a person's label, as for any PR. Spec R13 and §C amended to state the order; the plan's "batch PR gets the label alone" is superseded.

<!-- fr:journal kind=decision scope=plan id=p2-d2 created=2026-11-25T04:48:17+00:00 phase=2 -->
### p2-d2 · decision · p2-r3: the driver reads queue requests' repos rather than `queue add` refusing a repo with no batch (phase 2)

R14's between-waves queue must work in a scope with no batch in that repo, so `queue add` keeps accepting any collected repo and the driver reads it (`queue_requests.reader_repos`, keys no batch id can take; the Snapshot's own `repos` stays the batches').

<!-- fr:journal kind=review scope=plan id=review-p2-1 created=2026-11-25T04:48:17+00:00 phase=2 -->
### review-p2-1 · review · independent code review of phase 2: 3 findings, all in scope (phase 2)

Independent review of phase 2 (R11-R15, §C, §F) raised p2-r1 (preapproval at an unvetted head), p2-r2 (the loop counted no operator work) and p2-r3 (a request repo with no batch was never read); all three in scope and fixed with failing-first tests at the command-layer seam. The merge resolution on the branch was verified lossless.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-25T04:48:17+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: R13: a preapproval could be recorded approved at a head the driver never checked or commented on (phase 2)

operator_entries._preapprove now comments, records the approval (via `_approver`: the batch event writer for a batch PR, the queue writer for an operator PR), then labels. Tests: test_operator_reads.py::test_a_preapproved_batch_pr_records_the_batch_approval_at_the_vetted_head, ::test_a_push_between_the_preapproval_and_the_next_settle_voids_a_batch_approval (two passes, H2 pushed between the label and the settle: voided, label off), ::test_a_failed_audit_comment_leaves_no_label_and_no_approval, ::test_a_preapproved_operator_pr_is_recorded_before_it_is_labelled.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-25T04:48:17+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: R14/R15: the drive loop counted no operator work and ended over an undrained queue (phase 2)

wave_queue.operator_work counts pending operator entries minus those whose stall Need is reported (the Need now carries `entries=(key,)`); drive_pass adds it to `pending`. Tests: test_triage_batch_drive_cmd.py::test_an_added_operator_entry_keeps_a_finished_drive_from_reading_done, ::test_a_removed_or_landed_operator_entry_lets_the_drive_read_done, ::test_the_loop_waits_on_an_added_entry_and_ends_once_it_is_removed; test_wave_queue_operator_planner.py::test_a_pending_entry_is_the_drivers_work_until_its_stall_need_makes_it_the_operators.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-25T04:48:17+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: R11/R12: `queue add` to a repo with no batch was silently inert (phase 2)

queue_requests.reader_repos adds every collected repo a request of the scope names to the map the snapshot's queue readers (wave queue, housekeeping, operator, barrier, lineage, placements, post_merge repos) loop over. Test: test_triage_batch_drive_cmd.py::test_an_added_pr_in_a_repo_with_no_batch_is_read_and_lands_between_waves.

<!-- fr:journal kind=decision scope=plan id=p3-merge-ci-economy created=2026-11-25T10:40:57+00:00 phase=3 -->
### p3-merge-ci-economy · decision · Merged #1669's head 59ee50bf5 instead of waiting for main, on the operator's decision (phase 3)

P3.T1.S1's precondition (#1669 landed on origin/main) was replaced by the operator's decision not to wait:
origin/feat/ci-economy at 59ee50bf5 was merged into this branch (a merge commit, no rebase). Conflicts in
gitseam.py and queue_exec.py kept both features (Checkout.leads/carried and BuildConflict.onto beside the
CI-economy Regen/mirrors work); test_triage_model.py keeps one facts-schema list (FACTS_SCHEMA 18 is #1669's,
JUDGEMENTS_SCHEMA 14 this branch's, no collision); the fr-triage skill and the two explainers' reviewed
entries keep both sides, and the opencode/hermes mirrors and cli.md were regenerated, not hand-resolved.
This phase reads TriageConfig.generated from the merged code.

<!-- fr:journal kind=discovery scope=plan id=p3-cited-paths-dot created=2026-11-25T10:40:57+00:00 phase=3 -->
### p3-cited-paths-dot · discovery · cited_paths strips a leading dot, so a dot-directory citation reads as its undotted name (phase 3)

`cited_paths` strips "." from each token's ends, so `.opencode/skills/x.md` is cited as
`opencode/skills/x.md`. The generated: exclusion therefore will not match such a citation by glob.
A PR's files carry the true path, so a batch with a PR is exact. Left as it is (suggest has the same behaviour).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-25T10:40:57+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

new pure module with no prior shape to clean; the one reuse change is same_file made public in batch.py

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-25T10:58:33+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · wave_overlaps pairs batches of different repos, which the per-repo queue can never conflict (phase 3)

wave_overlap.py paired any two open batches of one wave whatever their repo, so an org or group scope reported and briefed an overlap the queue cannot produce. Fix: skip pairs whose Batch.repo_name differs. Tests: test_batches_of_different_repos_never_overlap_though_they_cite_one_path (pure) and test_suggest_reports_no_overlap_between_batches_of_two_repos (command seam).

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-25T10:58:33+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · preapproval's forge-comments-off gate is untested, mislabelled and undocumented (phase 3)

_preapprove's _comments_off gate (operator_entries.py) had no test though test_tripwire_forge_writes.py's GATED entry claims it, both gates reported under the key preapprove-repo-labels, and the docs said preapproval always comments first. Fix: each gate reports under its own key (labels, comments); test_preapproval_does_nothing_while_forge_comments_are_off proves no comment, label or approval record and one report; the fr-triage skill and the fr-wave-driver explainer now say preapproval does nothing while forge comments or labels are off.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-25T10:58:33+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · docs overstate or omit the overlap report (phase 3)

fr-wave-driver.md said same-file batches will conflict (now may conflict); the batch suggest docstring (and so docs/reference/cli.md) and fr-triage.md did not mention the overlap pairs suggest prints. Updated both, regenerated README/cli.md and the OpenCode and Hermes skill mirrors, bumped fr-triage.md's reviewed stamp.

<!-- fr:journal kind=review scope=plan id=review-p3-1 created=2026-11-25T10:58:33+00:00 phase=3 -->
### review-p3-1 · review · independent code review of phase 3: 3 findings, all in scope (phase 3)

Reviewed phase 3 (R7-R10, R13 preapproval). Three findings, all in scope and fixed with tests. The #1669 merge resolution was verified to keep both features.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-25T10:58:33+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: wave_overlaps pairs batches of different repos, which the per-repo queue can never conflict (phase 3)

wave_overlaps skips pairs of different repos; two new tests (pure and suggest).

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-25T10:58:33+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: preapproval's forge-comments-off gate is untested, mislabelled and undocumented (phase 3)

Separate report keys, comments-off test, skill and explainer clause.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-25T10:58:33+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: docs overstate or omit the overlap report (phase 3)

may conflict; suggest docstring, cli.md, fr-triage.md and stamp updated; mirrors synced.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · The carry brief's bare --force-with-lease leases against the ref step 2 just fetched, not the head the driver checked

queue_handback.carry_brief step 6 said `git push --force-with-lease origin <branch>`; step 2 fetches the branch first, so the lease pins whatever is there at fetch time and a push made after the driver's check is silently replaced. Fix: lease on `<branch>:<head>` and stop on a refused push.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · An added PR in a skipped (unread or carried) repo is not in queue_pending, so drive_pass can read done

operator_reads looped set(repos.values()) - set(skip), so a skipped repo's queue_add requests were never counted; batch_drive's pending count (operator_work over queue_pending) could reach 0 while an added PR is open and unlanded.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · An added PR that never becomes ready, with no open wave queue, stays pending forever with no Need

_operator_stall ran only from _tail of an open wave queue that would otherwise drain (record.wave not None), so an untrusted, reserved or unapproved added PR outside such a queue was pending work every pass with no Need; the loop never ended.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · A non-batch entry admitted at a live head the collect never saw reads as carrying nothing

lineage_reads read carries per collected head_oid; operator and housekeeping entries are admitted at the live head from pr_view, and batch_drive._carries left an unread head out, so hold_lineage read it as () and the entry was built, against R5.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · An onto git cannot read is warned once and then held silently forever while the brief says wait

A dead slot commit absent from a fresh or pruned clone raises GitError every pass (gitseam leads/carried), read as None (R5); reissue_actions and lineage_actions warned once, then held the entry with no Need, while the session's brief told it to wait for a re-issue that never came.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-errors-r5 · finding [open] (reviewer: in scope) · carry_hand_back skips an unreadable newer reset candidate and briefs an older head

The newest-first loop over hand-back heads recorded a GitError and kept going, so a clean older head was chosen as the reset head while a newer one, maybe also clean and with more of the branch's work, was unread.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-errors-r6 · finding [open] (reviewer: in scope) · queue add/remove give a traceback on glab/tea and on an undecodable default-branch answer

triage_queue_cmd caught only FORGE_ERRORS; UnsupportedForgeOperation (repo_default_branch, viewer_login on glab/tea) and a json.loads ValueError in RealGhClient.repo_default_branch escaped as tracebacks.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · The third-pass no-op of a re-issue (§F 2) is untested end to end

No test showed that, after a re-issue, only the latest onto at the head is asked and a further pass with the new target leading sends nothing.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · test_the_latest_event_at_the_head_decides passes if latest_conflict returned the first event

Both events in the test named an onto and were delivered, so first and latest agreed; the test could not tell which one decided.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · The foreign-move-of-main re-issue (R2) has no test

_plan_open's rebuild branch returns before reissue_actions, and no test showed a re-issue ever follows a move of main outside the queue.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · The carry's reset-head choice is not pinned by order

No test had two hand-back heads, so the newest-clean rule of carry_hand_back was unpinned.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · slot_name is never checked against queue_exec.slot_ref

queue_handback.slot_name rebuilt the slot branch name by hand; nothing tied it to the executor's slot_ref, and the drive test checked only `/slot-2`.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-tests-r6 · finding [open] (reviewer: in scope) · The placement filter that keeps operator entries has no test

batch_drive.queue_snapshot under quiet/stealth keeps only `operator` admitted entries; no test covered it.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · fr-wave-driver.md says 'no earlier head of the branch', the code reads only hand-back heads

docs/explainers/fr-wave-driver.md (carry paragraph) vs operator_entries.carry_hand_back, which tries only heads a conflict event names.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · fr-wave-driver.md says create/edit print overlaps only 'with --wave'

The overlap report runs for create or edit of any batch in a wave (wave_overlap), not only when --wave is given.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · fr-triage SKILL.md step 5 does not say what to do with an `overlap in wave N` line

plugins/super-fr/skills/fr-triage/SKILL.md step 5 (Batch) omitted the three remedies R8-R10 give.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-docs-accuracy-r4 · finding [open] (reviewer: in scope) · SKILL.md's Schema 14 note omits the queue_requests list

The note and its 'only the engine appends' line named neither `queue_requests:` nor the `fr triage queue add|remove` that writes it.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5 created=2026-11-25T11:31:52+00:00 state=open review_scope=in -->
### l-docs-accuracy-r5 · finding [open] (reviewer: in scope) · 'any open PR' for queue add omits that collect must have read it

queue add refuses a PR facts.json does not hold (distrust of an unknown author); fr-wave-driver.md and SKILL.md said any open PR.

<!-- fr:journal kind=decision scope=plan id=lr-d1 created=2026-11-25T11:31:52+00:00 -->
### lr-d1 · decision · R4 amended: the carry brief's push is leased on the head the brief names

`git push --force-with-lease=<branch>:<head> origin <branch>`; a refused push means the branch moved, and the session waits for a re-issued brief. Spec R4 amended in this commit (l-security-r1).

<!-- fr:journal kind=decision scope=plan id=lr-d2 created=2026-11-25T11:31:52+00:00 -->
### lr-d2 · decision · R5 amended: an unreadable lineage escalates to a Need after stall_hours

R5's hold-with-warning stays; an entry held so for queue.stall_hours, counted from the later of its hand-back and its head's last change (a non-batch entry's approval time), is a queue-need naming the commit and the entry. With no known time it stays a warning. queue_handback._unread (l-errors-r4).

<!-- fr:journal kind=decision scope=plan id=lr-d3 created=2026-11-25T11:31:52+00:00 -->
### lr-d3 · decision · R15 amended: every pending operator entry gets a Need whatever the queue's state

At once when its trust rule refuses it (operator_reads' new queue_refused), else after stall_hours from the later of its add and the queue's last landing; wave_queue.operator_needs runs from plan_queue in every phase and _tail only withholds the drain. The Need counts as blocked (operator_work), so a drive can end. A skipped repo's added PRs stay pending from the state (l-errors-r1, l-errors-r2).

<!-- fr:journal kind=decision scope=plan id=lr-d4 created=2026-11-25T11:31:52+00:00 -->
### lr-d4 · decision · R11 and R13 amended: glab/tea refusal, and the preapproval re-checks the base

R11: on a forge whose adapter lacks the reads (glab, tea) queue add/remove refuse with exit 2 and write nothing. R13: the driver approves a preapproved PR only while its base, read at that time, is still the default branch (lens security hardening).

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-25T11:31:52+00:00 -->
### lens-review-1 · review · lens review (security, errors, tests, docs-accuracy): 18 findings, all in scope

Four lens reviewers over the feature diff. security: queue_handback.py, operator_entries.py, triage_queue_cmd.py, queue_exec.py, gitseam.py (1 finding plus the preapproval base hardening). errors: operator_entries.py, batch_drive.py, wave_queue.py, queue_handback.py, gitseam.py, triage_queue_cmd.py, ghclient.py, real_ghclient.py (6). tests: test_queue_handback.py, test_operator_entries_lineage.py, test_triage_batch_drive_cmd.py, test_wave_queue_handback_planner.py, test_wave_closeout.py, test_triage_queue_cmd.py, test_operator_reads.py (6 plus two small additions). docs-accuracy: docs/explainers/fr-wave-driver.md, plugins/super-fr/skills/fr-triage/SKILL.md (5). All fixed in one commit; four spec amendments (lr-d1..lr-d4).

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: The carry brief's bare --force-with-lease leases against the ref step 2 just fetched, not the head the driver checked

carry_brief step 6 is `git push --force-with-lease=<branch>:<head> origin <branch>` and says a refused push means stop and wait for a re-issued brief. Tests: test_queue_handback.py::test_the_carry_brief_leases_against_the_head_the_driver_checked; integration test_queue_lineage.py::test_the_carry_briefs_push_is_leased_on_the_head_it_names (runs step 6 for real: replaces the named head, refused once the branch moved). Hardening: _preapprove refuses (reported once, nothing written) when the live base is not the default branch: test_operator_reads.py::test_preapproval_refuses_a_pr_whose_base_moved_off_the_default_branch.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: An added PR in a skipped (unread or carried) repo is not in queue_pending, so drive_pass can read done

operator_reads counts, for each skipped repo, every added PR that no batch owns, no scope record landed and collect does not read as closed, from the state alone (operator_entries.skipped_pending, no forge read). Test: test_operator_reads.py::test_a_skipped_repos_added_prs_stay_pending_from_the_state_alone.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: An added PR that never becomes ready, with no open wave queue, stays pending forever with no Need

wave_queue.operator_needs (called by plan_queue in every phase) gives each pending operator entry a queue-need naming `fr triage queue remove --pr <n>`: at once when operator_reads' new queue_refused names it, else after stall_hours from the later of its add and the queue's last landing; _tail only withholds the drain. operator_work counts it as blocked. R15 amended. Tests: test_wave_queue_operator_planner.py::test_a_trust_refused_entry_is_a_need_at_once_whatever_the_queue_state, ::test_an_entry_that_never_becomes_ready_is_a_need_after_stall_hours_with_no_queue, ::test_an_entry_waiting_in_a_wave_queue_still_gets_its_need, ::test_a_between_waves_queue_drains_by_its_own_rule (updated); test_operator_reads.py::test_a_trust_refused_added_pr_is_named_as_refused.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: A non-batch entry admitted at a live head the collect never saw reads as carrying nothing

lineage_reads takes the pass's queue reads (`reads=`) and also reads each admitted operator and housekeeping entry's live head; batch_drive._carries maps an admitted entry whose head the read missed to None (held with the existing warning) in a repo whose heads were read. Tests: test_operator_entries_lineage.py::test_an_admitted_entrys_live_head_is_read_even_when_facts_hold_another, ::test_an_admitted_entry_takes_its_carry_by_the_head_it_is_built_at (updated).

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: An onto git cannot read is warned once and then held silently forever while the brief says wait

queue_handback._unread: an unreadable onto (reissue_actions) or head (lineage_actions) is warned once as before, and once held for stall_hours from the later of its hand-back and its head's last change (a non-batch entry's approval) it is a queue-need naming the commit and the entry. R5 amended (decision lr-d2). Tests: test_wave_queue_handback_planner.py::test_an_unreadable_onto_held_past_stall_hours_is_a_need_naming_the_commit_and_batch, ::test_an_unreadable_head_held_past_stall_hours_is_a_need_naming_the_head.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-errors-r5 -->
### l-errors-r5-resolved · finding [fixed] · resolves l-errors-r5: carry_hand_back skips an unreadable newer reset candidate and briefs an older head

carry_hand_back stops at the first GitError in newest-first order and returns the 'held this pass' line, never an older head. Test: test_triage_batch_drive_cmd.py::test_an_unreadable_newest_reset_candidate_never_briefs_an_older_head.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-errors-r6 -->
### l-errors-r6-resolved · finding [fixed] · resolves l-errors-r6: queue add/remove give a traceback on glab/tea and on an undecodable default-branch answer

queue add and remove catch UnsupportedForgeOperation and refuse 'the merge queue needs a GitHub repo (<repo> is <backend>); nothing written', exit 2; RealGhClient.repo_default_branch turns a JSON decode failure into GhError. R11 amended. Tests: test_triage_queue_cmd.py::test_a_forge_without_the_operation_refuses_cleanly[add|remove], ::test_an_undecodable_default_branch_answer_is_a_gh_error.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: The third-pass no-op of a re-issue (§F 2) is untested end to end

New test passed at once (the behaviour was right): test_operator_entries_lineage.py::test_only_the_latest_handbacks_onto_at_a_head_is_asked; test_triage_batch_drive_cmd.py::test_the_planner_reissues_a_handback_whose_onto_stopped_leading now executes the re-issue and runs a second pass with the new target leading: still one message, two conflict events, only the new onto asked.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: test_the_latest_event_at_the_head_decides passes if latest_conflict returned the first event

test_queue_handback.py::test_the_latest_event_at_the_head_decides now has events that disagree (onto then none: not due; held then session with onto: due). Passed at once: latest_conflict does take the latest.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: The foreign-move-of-main re-issue (R2) has no test

New test passed at once (the planner was right): test_wave_queue_handback_planner.py::test_a_foreign_move_of_main_reissues_once_naming_the_rebuilt_target: the rebuild pass re-issues nothing, the next pass with the rebuilt combinations recorded re-issues once, on r2 slot 2.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: The carry's reset-head choice is not pinned by order

New parametrized test passed at once: test_triage_batch_drive_cmd.py::test_the_carry_resets_to_the_newest_clean_hand_back_head (sha-099 then sha-100 clean: reset sha-100; sha-100 carrying: sha-099).

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: slot_name is never checked against queue_exec.slot_ref

slot_name is now derived from queue_exec.slot_ref (lazy import). Tests passed at once: test_queue_handback.py::test_the_slot_name_is_the_executors_slot_ref_without_refs_heads; test_a_slot_hand_back_names_the_slot_and_records_its_onto asserts the full `git fetch origin fr-queue/<scope-id>/slot-2`.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-tests-r6 -->
### l-tests-r6-resolved · finding [fixed] · resolves l-tests-r6: The placement filter that keeps operator entries has no test

New test passed at once: test_wave_closeout.py::test_under_quiet_placement_an_operator_entry_stays_and_housekeeping_goes. Also added: test_triage_queue_cmd.py::test_remove_of_a_batch_pr_records_the_queue_remove_on_disk and test_operator_reads.py::test_preapproval_skips_a_pr_whose_merge_state_is_dirty (both passed at once).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: fr-wave-driver.md says 'no earlier head of the branch', the code reads only hand-back heads

fr-wave-driver.md: 'If no head the queue handed back earlier is free of it'; the paragraph also states the lease on the named head and the stall_hours escalation.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: fr-wave-driver.md says create/edit print overlaps only 'with --wave'

fr-wave-driver.md: 'and `batch create` or `batch edit` of a batch in a wave, print each such pair'.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: fr-triage SKILL.md step 5 does not say what to do with an `overlap in wave N` line

SKILL.md step 5 (reworded in place, 120 lines kept): when suggest, create or edit prints an `overlap in wave N` line, merge the two, move one to wave N+1, or accept that whichever lands second gets the conflict hand-back. Mirrors regenerated.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-docs-accuracy-r4 -->
### l-docs-accuracy-r4-resolved · finding [fixed] · resolves l-docs-accuracy-r4: SKILL.md's Schema 14 note omits the queue_requests list

SKILL.md Schema 14 note names the `queue_requests:` list (`queue_add`, `queue_remove`, written by `fr triage queue add|remove`) in both the engine-appends line and the schema-14 sentence.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5-resolved created=2026-11-25T11:31:52+00:00 state=fixed resolves=l-docs-accuracy-r5 -->
### l-docs-accuracy-r5-resolved · finding [fixed] · resolves l-docs-accuracy-r5: 'any open PR' for queue add omits that collect must have read it

fr-wave-driver.md and SKILL.md: queue add takes an open PR that collect has read since it opened (`fr triage collect` first). Both pages also describe the new Needs, the preapproval base re-check and the leased push.
