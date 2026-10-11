# Journal: 2026-10-11-merge-train-safety

<!-- fr:journal kind=decision scope=plan id=p1-gate-before-moved-head created=2026-10-11T20:45:51+00:00 phase=1 -->
### p1-gate-before-moved-head · decision · The approval gate runs before _open_head, so a foreign push reads as unapproved, not a moved head (phase 1)

Per spec §A "Merging", `_approved_and_ready` runs before `_open_head`. A head moved by a push fr did not make is therefore `Void` and the merge returns `unapproved` (with the reason "was approved at A, but its head moved to H"), which the driver steps over; `HeadMovedError` (which stops a train) now only arises for a head fr's own update moved. `batch merge` reports the void reason. `test_triage_batch_merge_ready`'s moved-head tests record an fr update to keep testing HeadMovedError.

<!-- fr:journal kind=decision scope=plan id=p1-snapshot-approvals-source created=2026-10-11T20:45:51+00:00 phase=1 -->
### p1-snapshot-approvals-source · decision · The driver computes Snapshot.approvals from live labels; the board and drive --plan from facts (phase 1)

The driver already reads `pr_view` per queued PR in its snapshot, so its verdicts use the live labels (after `settle_approvals` ran under --yes and the judgements were reloaded). `views.drive_snapshot` uses `fact_approvals` over collected labels. A label fr voided this pass still shows in that pass's facts, so the board reads `First` for it until the next collect; the merge gate itself always reads live. The re-label Need covers both a `Void` verdict and an `Unlabelled` PR whose last approval was voided (`approval.voided_at`).

<!-- fr:journal kind=decision scope=plan id=p1-label-creation-call-sites created=2026-10-11T20:45:51+00:00 phase=1 -->
### p1-label-creation-call-sites · decision · Where ensure_approval_label runs, and only under --yes for the writing verbs (phase 1)

collect: through the real `ClientForge` only (`forge.client`), so a test forge never reaches it; batch dispatch and batch merge: only under --yes (a preview writes nothing); drive: once per repo per pass, before settling, for repos with an open batch PR; `fr init scaffold`: `approval_label_target` (GitHub origin only), which `tests/conftest.py` neutralizes so no test clone reaches a real forge.

<!-- fr:journal kind=decision scope=plan id=p1-fakes-location created=2026-10-11T20:45:51+00:00 phase=1 -->
### p1-fakes-location · decision · The in-process GhClient fakes extended are fakes.FakeGhClient, MergeForge and the drive World (phase 1)

The plan named `tests/unit/triage_fixtures.py`, but its `FakeForge` is the collect `Forge` seam, not a `GhClient`. `pr_ready`, `label_exists` and pr_view labels went to the GhClient fakes the merge, dispatch and drive tests actually use: `tests/unit/fakes.py::FakeGhClient`, `test_triage_batch_merge.MergeForge`, `test_triage_batch_drive_cmd.World`, plus `test_triage_batch_merge_git.GitForge`.

<!-- fr:journal kind=discovery scope=plan id=p1-scenario-remote-url created=2026-10-11T20:45:51+00:00 phase=1 -->
### p1-scenario-remote-url · discovery · The scenario reaches its bare remote by a file://localhost URL, not url.insteadOf (phase 1)

`git remote get-url` expands `url.<base>.insteadOf`, and the driver reads the batch's repo from that URL (`gitseam.repo_of_url`), so an insteadOf-rewritten origin names a local path and the driver refuses the clone. The scenario uses `file://localhost/<world>/github/derio-net/super-fr.git`, whose last two path parts name the repo. Captured label lookups (`labels/bug` 200, `labels/approved-fr` 404) were added to tests/fixtures/github_rest from a host session on 2026-10-11.

<!-- fr:journal kind=finding scope=plan id=p1-triage-batch-cmd-import-cycle created=2026-10-11T20:45:51+00:00 phase=1 state=open review_scope=out -->
### p1-triage-batch-cmd-import-cycle · finding [open] (reviewer: out of scope) · Importing fr.commands.triage_batch_cmd before fr.cli fails on a cycle (phase 1)

`import fr.commands.triage_batch_cmd` on its own raises ImportError (triage_claim_cmd imports `_fail` from a partially initialised triage_kanban_cmd). It predates this branch (checked on a stash of it). Tests import `fr.cli` first; the new tripwire does too.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-11T20:45:51+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Each new verb is a few lines beside its siblings in each client (pr_merge, close_pr, file_exists shapes); nothing duplicated beyond the per-backend argv/route, which is the seam's point.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-11T20:45:51+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

Folded as written: views lost the dead ready-pr loop and its _all_prs/batch_of_pr helpers, kanban's first_actions and awaiting_approval share one _default_plan; nothing further to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-11T20:45:51+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

A scenario script, a fake forge and three matrix rows; no production code to refactor.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · pr_ready forge refusal escapes the gate (driver ForgeReadError, batch merge crash) (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · board judges checks with ci_none=False, so a ci none repo is never asked for the label (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · scaffold origin test tests the conftest stub (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · prose tripwire splitter merges bullets and misses label/REST forms (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · dispatch_batch checks the label once per dispatch, not once per pass (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · UpdateEvent recorded only after push (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · pr_ready is not head-pinned (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · board builds 3 snapshots and 2 passes per render (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · same --yes pass's board shows a just-voided PR as approved (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r10 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r10 · finding [open] (reviewer: in scope) · dead draft readiness; foreign-push pre-check still stops the train (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r11 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=in -->
### p1-r11 · finding [open] (reviewer: in scope) · label-gate scenario covers only the driver (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r12 created=2026-10-11T21:11:30+00:00 phase=1 state=open review_scope=out -->
### p1-r12 · finding [open] (reviewer: out of scope) · archive and export PR merges bypass the approval gate (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-11T21:11:30+00:00 phase=1 -->
### p1-review-1 · review · phase 1 review: 12 findings (11 in, 1 out) (phase 1)

Independent reviewer raised p1-r1..p1-r12; TOCTOU check: the gate's verified head is the sha pr_merge pins (--match-head-commit / REST sha), so no unapproved head can land; pr_ready head-pinning added (p1-r7). All 11 in-scope findings fixed by the implementer with tests; p1-r12 out of scope.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: pr_ready forge refusal escapes the gate (driver ForgeReadError, batch merge crash) (phase 1)

pr_ready forge refusals (FORGE_ERRORS) become `unready` with the forge's words. Test: test_merge_train_gate.py#test_a_forge_refusing_to_ready_leaves_the_draft_unready_with_its_words

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: board judges checks with ci_none=False, so a ci none repo is never asked for the label (phase 1)

Board paths take the repos judged ci none; fr triage render/board read it from the local clone. Test: test_merge_train_label_board.py#test_a_ci_none_repo_asks_for_the_label_with_no_check_at_all

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: scaffold origin test tests the conftest stub (phase 1)

The test undoes the stub and checks the real approval_label_target on four origins. Test: test_merge_train_label_board.py#test_init_scaffold_targets_only_a_github_origin

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: prose tripwire splitter merges bullets and misses label/REST forms (phase 1)

Sentences end at line breaks; `label` verb and `labels[]=approved-fr` caught; three probes added. Test: test_tripwire_approval_label_prose.py#test_an_instruction_to_add_the_label_is_caught

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: dispatch_batch checks the label once per dispatch, not once per pass (phase 1)

The pass's seen set is threaded through dispatch_batch. Test: test_triage_batch_drive_cmd.py#test_a_pass_dispatching_several_batches_checks_the_label_once

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: UpdateEvent recorded only after push (phase 1)

Recorded after commit_all and before the push; spec §B updated. Test: test_merge_train_gate.py#test_an_update_is_recorded_before_its_push

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: pr_ready is not head-pinned (phase 1)

The head is re-read after pr_ready; a moved head is unapproved and nothing merges. Test: test_merge_train_gate.py#test_a_head_that_moves_while_the_draft_is_readied_is_not_merged

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: board builds 3 snapshots and 2 passes per render (phase 1)

_default_plan returns snapshot+pass, built once. Corrects the phase 1 record's refactor P1.T5 claim that nothing was left to clean. Test: test_merge_train_label_board.py#test_a_board_render_builds_one_snapshot_and_one_pass

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: same --yes pass's board shows a just-voided PR as approved (phase 1)

Voided labels are dropped from in-memory facts and facts.json is rewritten. Test: test_triage_batch_drive_cmd.py#test_the_pass_that_voids_an_approval_leaves_facts_and_board_without_the_label

<!-- fr:journal kind=finding scope=plan id=p1-r10-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r10 -->
### p1-r10-resolved · finding [fixed] · resolves p1-r10: dead draft readiness; foreign-push pre-check still stops the train (phase 1)

draft value removed; a foreign push is stepped over, only an fr-made move stops; test asserts the void. Test: test_triage_batch_drive_cmd.py#test_a_foreign_push_after_the_snapshot_is_stepped_over_not_a_stop

<!-- fr:journal kind=finding scope=plan id=p1-r11-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=fixed resolves=p1-r11 -->
### p1-r11-resolved · finding [fixed] · resolves p1-r11: label-gate scenario covers only the driver (phase 1)

Scenario extended: batch merge held/exit 2/preview, approve-pr Need, awaiting-approval card, ready before merge. Test: tests/integration/test_scenarios.py#test_merge_train_label_gate

<!-- fr:journal kind=finding scope=plan id=p1-r12-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=open resolves=p1-r12 out_of_scope=true -->
### p1-r12-resolved · finding [out-of-scope] · resolves p1-r12: archive and export PR merges bypass the approval gate (phase 1)

Archive (_archive) and export (_export_merge) PRs are fr's own housekeeping PRs, not batch PRs; spec §A scopes the approval gate to batch PRs, so this change did not cause it. It belongs to the follow-up proper-gate design.

<!-- fr:journal kind=finding scope=plan id=p1-triage-batch-cmd-import-cycle-resolved created=2026-10-11T21:11:30+00:00 phase=1 state=open resolves=p1-triage-batch-cmd-import-cycle out_of_scope=true -->
### p1-triage-batch-cmd-import-cycle-resolved · finding [out-of-scope] · resolves p1-triage-batch-cmd-import-cycle: Importing fr.commands.triage_batch_cmd before fr.cli fails on a cycle (phase 1)

Importing fr.commands.triage_batch_cmd before fr.cli fails on origin/main too (1248d439); this change neither introduced nor worsened the cycle.
