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

<!-- fr:journal kind=decision scope=plan id=p2-warn-every-pass created=2026-10-11T22:26:27+00:00 phase=2 -->
### p2-warn-every-pass · decision · The walk warns on every pass for a failing PR; the dedup is the recorded events (phase 2)

The walk no longer dedups a failing PR's warn by head in Snapshot.warned. Each red warn carries red=True and checks; _Driver._recover decides from red_decision whether the pass has anything to say, and the pass prints nothing for a skip. _Driver.warned stays: _report_once and the close reports still read it.

<!-- fr:journal kind=decision scope=plan id=p2-red-session-status-lazy created=2026-10-11T22:26:27+00:00 phase=2 -->
### p2-red-session-status-lazy · decision · The session is read only when rules 1-3 leave the decision to it (phase 2)

_recover asks red_decision with status idle first; only a handback result reads the runner's status and decides again. A runner that cannot be messaged reads as absent, so its red PR is a needs-you. A wait prints its line once per (batch, head, status) from self.reported, since it records nothing.

<!-- fr:journal kind=discovery scope=plan id=p2-positive-rule-shapes-not-captured created=2026-10-11T22:26:27+00:00 phase=2 -->
### p2-positive-rule-shapes-not-captured · discovery · Positive merge_queue/strict rule shapes are not captures (phase 2)

The repo's own ruleset has neither rule, so the positive base_rules cases in tests/unit/test_merge_train_base_rules.py and the scenario's strict rule are built from the captured rule record's key shape plus the documented parameters, stated in the fake's docstring. The 404 of branches/main/protection and the negative rules are live captures.

<!-- fr:journal kind=discovery scope=plan id=p2-scenario-drive-exit-3 created=2026-10-11T22:26:27+00:00 phase=2 -->
### p2-scenario-drive-exit-3 · discovery · A pass waiting on checks exits 3 (phase 2)

The red-recovery scenario accepts drive exit 0 or 3, since a pass whose only PR is pending exits 3 by design.

<!-- fr:journal kind=discovery scope=plan id=p2-git-fake-lacked-base-rules created=2026-10-11T22:26:27+00:00 phase=2 -->
### p2-git-fake-lacked-base-rules · discovery · CI red: the integration GitForge fake had no base_rules (phase 2)

Phase 2 made batch merge read GhClient.base_rules once per command. tests/integration/test_triage_batch_merge_git.py's GitForge (its labels were already approved) had no such method, so the command died before merging (merged == []). Fixed by giving the fake base_rules returning BaseRules(); the gate is untouched. I had run only unit files locally, which hid it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-11T22:26:27+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

red_decision and red_brief are new pure functions beside conflict_decision and conflict_brief; nothing duplicated.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-11T22:26:27+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

base_rules is one method per backend beside required_check_names; the strict change is one condition in _land.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-10-11T22:26:27+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

_skip_held is a small helper beside _refuse_held, whose with-ids path is unchanged.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-10-11T22:26:27+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

Two scenario scripts, a fake herdr and two keys on the existing fake gh; no production code.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-11T22:39:53+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · base_rules raises on the free-plan rules 403 and on a protection 403: batch merge exits 1 and the driver skips every pass (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-11T22:39:53+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · _recover builds merge_ctx and fetches before rule 1 (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-11T22:39:53+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · a red PR held by another driver's runner is silent (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-11T22:39:53+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · status-read and hand-back-failure lines print every pass (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-11T22:39:53+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · untested: batch merge base_rules -> ctx.rules, the forge-error path, _red_phrase, a reupdate keeping the approval (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-11T22:39:53+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · red-recovery scenario never exercises rule 2's head_before dedup (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-10-11T22:39:53+00:00 phase=2 -->
### p2-review-1 · review · phase 2 review: 6 findings, all in scope (phase 2)

Independent reviewer raised p2-r1..p2-r6 (p2-r1 Important); all fixed by the implementer with tests.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-11T22:39:53+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: base_rules raises on the free-plan rules 403 and on a protection 403: batch merge exits 1 and the driver skips every pass (phase 2)

Free-plan 403 on rules reads as no rules; protection 403 degrades to not strict with one warning; transient failures still raise; RealGhClient delegates. Test: test_merge_train_base_rules.py#test_a_protection_403_degrades_to_not_strict_and_warns_once

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-11T22:39:53+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: _recover builds merge_ctx and fetches before rule 1 (phase 2)

Rule 1 is checked from persisted events before any context or base read. Test: test_triage_batch_drive_cmd.py#test_an_already_handed_back_red_head_builds_no_context_and_reads_no_base

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-11T22:39:53+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: a red PR held by another driver's runner is silent (phase 2)

Says once: left to that runner's driver. Test: test_triage_batch_drive_cmd.py#test_a_red_pr_whose_runner_this_driver_lacks_says_so_once

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-11T22:39:53+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: status-read and hand-back-failure lines print every pass (phase 2)

All recovery lines go through one _said_once helper. Test: test_triage_batch_drive_cmd.py#test_a_failing_status_read_and_a_failing_send_are_each_said_once

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-11T22:39:53+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: untested: batch merge base_rules -> ctx.rules, the forge-error path, _red_phrase, a reupdate keeping the approval (phase 2)

Four tests added. Test: test_triage_batch_merge.py#test_batch_merge_reads_the_base_rules_once_and_strict_checks_update_a_routinely_behind_pr

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-11T22:39:53+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: red-recovery scenario never exercises rule 2's head_before dedup (phase 2)

Phase A makes h2 red with an unmoved base and asserts a hand-back and exactly two update events. Test: tests/integration/test_scenarios.py#test_merge_train_red_recovery

<!-- fr:journal kind=decision scope=plan id=p3-queue-reads-in-snapshot created=2026-10-11T23:16:49+00:00 phase=3 -->
### p3-queue-reads-in-snapshot · decision · Queue state and the base are read in the driver's snapshot, and only for batches already enqueued (phase 3)

Snapshot gains queue_repos, queue_versioned, queue_rest, queue_states and bases. _Driver._queue_reads asks base_rules once per repo per pass (the cache merge_ctx also uses), then pr_queue_state and the fetched base only for a batch with an EnqueueEvent. An unreadable base leaves the repo's states out, so the walk decides nothing rather than guessing an ejection.

<!-- fr:journal kind=decision scope=plan id=p3-queue-walk-branch created=2026-10-11T23:16:49+00:00 phase=3 -->
### p3-queue-walk-branch · decision · Queue mode is a separate _walk_queue; _walk_train only branches at its entry (phase 3)

The merge train's loop is renamed _walk_merge_train and untouched, so a repo with no queue keeps its train byte for byte. A queue Train has no head or candidates; it carries enqueue and in_merge_queue, and train_line prints them.

<!-- fr:journal kind=decision scope=plan id=p3-queue-ejected-need-live-only created=2026-10-11T23:16:49+00:00 phase=3 -->
### p3-queue-ejected-need-live-only · decision · The queue-ejected Need comes from a driver pass, not the facts-only board (phase 3)

The ejection is a warn action with ejected=True (dedup key per head in Snapshot.warned); views.queue_needs turns it into the queue-ejected Need. The board and drive --plan read no forge, so they leave queue_repos empty and show the ordinary train; the driver prints the line. Likewise a card reads 'in merge queue' only from a plan built with queue state.

<!-- fr:journal kind=discovery scope=plan id=p3-once-warn-dedup-per-process created=2026-10-11T23:16:49+00:00 phase=3 -->
### p3-once-warn-dedup-per-process · discovery · A warn dedup in Snapshot.warned lasts one driver process, so two --once passes each say the ejection (phase 3)

self.warned is per driver object, as for red-CI warns, so the scenario-level test asserts the line once and the pure walk test pins the per-head dedup.

<!-- fr:journal kind=discovery scope=plan id=p3-merge-queue-rule-not-captured created=2026-10-11T23:16:49+00:00 phase=3 -->
### p3-merge-queue-rule-not-captured · discovery · The merge_queue rule shape in the fake gh is documented, not captured (phase 3)

The repo's ruleset has no merge queue, so the fake adds a rule in the captured rules' key shape with the documented merge_queue parameters, stated in its docstring. The GraphQL isInMergeQueue/autoMergeRequest answers in the unit tests are likewise the documented pullRequest shape.

<!-- fr:journal kind=discovery scope=plan id=p3-queue-read-needs-origin-head created=2026-10-11T23:16:49+00:00 phase=3 -->
### p3-queue-read-needs-origin-head · discovery · CI red: _queue_reads resolved the default branch through origin/HEAD for every repo with an open PR (phase 3)

The cloud driver's clone has no origin/HEAD, so gitseam.default_branch raised inside the per-pass queue read even for draft or failing PRs with nothing to merge or enqueue (the version-drift scenario passed locally, where origin/HEAD happens to be set). Fixed: rules are read only for a repo with an open, non-failing PR (or one enqueued before), and a GitError/TriageError from the default branch reads as no queue. A unit test pins both.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-11T23:16:49+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

pr_enqueue and pr_queue_state are two new methods beside pr_merge in each backend; nothing duplicated.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-11T23:16:49+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

Two one-line trigger additions to existing workflows; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-10-11T23:16:49+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

A scenario script, one fake-gh key and matrix rows; no production code.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · queue-ejected Need unreachable (facts-only needs_you) (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · _enqueue skips _approved_and_ready (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · a queue hold suppresses red recovery (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · kanban in-merge-queue never renders (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · an enqueue refusal is a held line said once (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · a just-merged PR reads as ejected (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · rule 2 applies in queue repos (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · _queue_reads swallows errors as no queue (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · removing approved-fr after enqueue is not honoured (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=in -->
### p3-r10 · finding [open] (reviewer: in scope) · weak tests (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r11 created=2026-10-11T23:39:00+00:00 phase=3 state=open review_scope=out -->
### p3-r11 · finding [open] (reviewer: out of scope) · a repo without origin/HEAD and an approved green PR aborts every pass at merge_ctx (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=review scope=plan id=p3-review-1 created=2026-10-11T23:39:00+00:00 phase=3 -->
### p3-review-1 · review · phase 3 review: 11 findings (10 in, 1 out) (phase 3)

Independent reviewer raised p3-r1..p3-r11; check 4 confirmed no merge around a queue. All 10 in-scope findings fixed with tests; spec §D updated.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: queue-ejected Need unreachable (facts-only needs_you) (phase 3)

Ejection with an unmoved base is recorded once per (pr, head); queue_needs reads events. Test: test_an_ejected_green_pr_with_the_base_unmoved_needs_you_and_is_not_enqueued_again

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: _enqueue skips _approved_and_ready (phase 3)

Enqueue goes through the shared gate (label re-read, pr_ready, head re-check); the fake refuses drafts. Test: test_an_approved_draft_is_readied_then_enqueued

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: a queue hold suppresses red recovery (phase 3)

A held queue repo still emits red warns. Test: test_a_held_queue_repo_still_reports_a_red_member_so_recovery_runs

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: kanban in-merge-queue never renders (phase 3)

Facts-only views infer queue membership from the last enqueued event at the current head. Test: test_facts_only_views_show_an_enqueued_pr_in_the_merge_queue_not_merge_ready

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: an enqueue refusal is a held line said once (phase 3)

Each refusal is recorded with the forge's words; a second at the same head stops retries and raises an enqueue-refused Need (a conflict cannot be told apart from the refusal text, so it is the Need, per spec). Test: test_two_refusals_at_one_head_become_a_need_and_stop_the_retries

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: a just-merged PR reads as ejected (phase 3)

State/merged fetched in the queue-state read; a merged/closed PR is never ejected. Test: test_a_merged_pr_read_after_the_view_is_never_taken_for_ejected

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: rule 2 applies in queue repos (phase 3)

red_decision(queue=True) skips rule 2. Test: test_a_queue_repo_red_pr_is_never_re_updated

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: _queue_reads swallows errors as no queue (phase 3)

Catch narrowed to the default-branch lookup; such a repo is held with a once-said warning. Test: test_an_unknown_default_branch_holds_the_candidate_repo_and_says_so_once

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: removing approved-fr after enqueue is not honoured (phase 3)

pr_dequeue added; settle_approvals dequeues an fr-enqueued PR whose label is gone or voided. Test: test_removing_the_label_after_the_enqueue_dequeues_the_pr_and_a_relabel_enqueues_it

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=fixed resolves=p3-r10 -->
### p3-r10-resolved · finding [fixed] · resolves p3-r10: weak tests (phase 3)

Specific assertions; the ejected test asserts the Need; the fake refuses drafts. Test: test_a_pr_ejected_with_the_base_moved_is_enqueued_again

<!-- fr:journal kind=finding scope=plan id=p3-r11-resolved created=2026-10-11T23:39:00+00:00 phase=3 state=open resolves=p3-r11 out_of_scope=true -->
### p3-r11-resolved · finding [out-of-scope] · resolves p3-r11: a repo without origin/HEAD and an approved green PR aborts every pass at merge_ctx (phase 3)

merge_ctx's _fresh_config default-branch lookup raising ForgeReadError on a clone with no origin/HEAD predates phase 3 (origin/main behaves the same); phase 3 only stopped its own queue read from triggering it earlier.
