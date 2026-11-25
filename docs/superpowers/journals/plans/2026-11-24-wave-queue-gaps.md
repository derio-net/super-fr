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
