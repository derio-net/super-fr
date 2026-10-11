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
