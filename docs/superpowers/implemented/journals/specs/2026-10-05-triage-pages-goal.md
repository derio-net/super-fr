# Journal: 2026-10-05-triage-pages-goal

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-05T21:01:46+00:00 input=true -->
### operator-brief · discovery · Operator brief (batch triage-pages-goal), verbatim

/fr-goal Triage pages: one goal per page, one home per fact, authored sections everywhere, driver exports the state

Batch `triage-pages-goal` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#970: Triage pages: one goal per page, partition and de-duplicate their data, and export the state from the driver (fr-brainstorming)
Brainstorm first: one goal per page, one home per fact, summary before detail, driver export of the triage state. Folds in super-fr#968 and super-fr#887.
Note: Operator priority 2026-10-05: artifact issues first (wave 4).

## super-fr#968: Triage pages: the board and origins page have no home for authored sections, so hand-written analysis is lost on re-render
Board and origins page have no fragment mechanism; architecture's `load_manifest`/`validate_fragment` is the one to share.
Note: Folded into super-fr#970, whose design covers it. Close when #970 lands: `gh issue close 968 -R derio-net/super-fr --reason "not planned" --comment "Folded into #970."`

## super-fr#887: Board's wave 'Closing order' table has no per-batch tier column
Wave tables omit each batch's tier, on purpose per spec design D.
Note: Folded into super-fr#970 (board layout).

## Why these belong together
Wave 4: the artifact UX brainstorm. fr-goal starts with fr-brainstorming and will stop at its question round for the operator.

## Delivery rules
- Work on branch `feat/batch-triage-pages-goal`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#970
  Closes derio-net/super-fr#968
  Closes derio-net/super-fr#887
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

(Issue bodies of #970, #968 and #887 as read 2026-10-05 via `gh issue view`; their
asks are restated in the spec's Background and Requirements.)

<!-- fr:journal kind=decision scope=spec id=q1-board-backlog-collapsed created=2026-10-05T21:01:46+00:00 -->
### q1-board-backlog-collapsed · decision · Board keeps the backlog, collapsed per sub-section; batch cards collapsed and stage-filterable

Q: where do backlog by tier, patterns, features, parked, PRs and batch cards go?
A (operator, verbatim): "Batch cards should be a. collapsed and b. filterable by state
(merged, cancelled, etc in multi-select). Since last report should be a nice table showing
the transitions. Clicking on a batch should jump to the batches section for more details.
Regarding q1, 2. collapsed on the board and each sub category (Patterns, Parked etc..) also
collapsed.." -> spec R2, R3, R5.

<!-- fr:journal kind=decision scope=spec id=q2-architecture-summary created=2026-10-05T21:01:46+00:00 -->
### q2-architecture-summary · decision · Architecture summary strip becomes the page's own answer

Operator chose: replace the strip with lines then/now and the top 3 subsystems by open defects (R6).

<!-- fr:journal kind=decision scope=spec id=q3-history-page created=2026-10-05T21:01:46+00:00 -->
### q3-history-page · decision · History gets its own page

Operator chose a separate history.html: snapshot timeline, finished waves, dated fragments (R8).

<!-- fr:journal kind=decision scope=spec id=q4-data-scope created=2026-10-05T21:01:46+00:00 -->
### q4-data-scope · decision · Data in scope - origins schema 2, severity on judgements, duplicate_of on judgements; per-wave cost out

Operator selected origins.yaml schema 2, severity on every open issue, structured duplicates in judgements (R10, R11). Per-wave cost not selected (non-goal).

<!-- fr:journal kind=decision scope=spec id=q5-driver-opens-export-pr created=2026-10-05T21:01:46+00:00 -->
### q5-driver-opens-export-pr · decision · The driver itself opens and merges the export PR

Operator chose: driver commits in a worktree, pushes chore/triage-state-wave-<N>, opens the PR via a new GhClient.pr_create, merges it when green like an archive PR; one export per wave, recorded (R13).

<!-- fr:journal kind=decision scope=spec id=q6-fr-verbs-replace-sync created=2026-10-05T21:01:46+00:00 -->
### q6-fr-verbs-replace-sync · decision · fr triage state export|import replace docs/triage/sync.sh

Operator chose fr verbs owning the file list; the driver calls the same function; opt-in export: {path: docs/triage} in .fr/triage.yaml (R12, R15).

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · Since last report table: SnapshotDiff is not typed, and acceptance moves are not in acceptance_note

target: spec
evidence: snapshot.py:69-75, :248-288 hold pre-formatted strings; acceptance_note is only the not-tracked notice.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · views.finished_waves called from batch_drive.drive_pass creates an import cycle

target: spec
evidence: views imports batch_drive at module level (views.py:32-43).
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · Origins SCHEMA constant is shared with origins-facts.json; bumping it to 2 breaks the facts loader

target: spec
evidence: origins.py:53, :208-218, :264-265.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · Board's preselected wave can name a finished wave that is no longer a tab

target: spec
evidence: render.py:732-734 keys.index(...) would raise; views.py:336-347.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · Finished-wave predicate never finishes a wave holding an abandoned batch

target: spec
evidence: batch.py:224-240, :57.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · Step-3b export decision: PrState is the wrong type, head-unchanged has nothing to compare against, the untrusted row is missing

target: spec
evidence: batch_drive.py:72-124; triage_batch_cmd.py:2151.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · _export is not idempotent across a crash between push, pr_create and recording the Export

target: spec
evidence: gitseam.py:412-413 push has no force.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · Drive loop exits on summary.done before a pending export PR is merged

target: spec
evidence: triage_batch_cmd.py:2309-2313; batch_drive.py:141-165.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · Post-merge check 2 can never hold: the Export record is written to the cache after the export commit

target: spec
evidence: Test Plan post-merge 2 vs §I steps 3-6.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · Judgements writer and readers need more than the spec lists to carry schema 4 and exports

target: spec
evidence: model.py:45-46, :556; batch.py:396-431; batch_drive.py:127-138.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · Re-export aliases do not keep test_triage_architecture.py working, and the Test Plan says the tests move anyway

target: spec
evidence: tests/unit/test_triage_architecture.py:545, :651, :680, :253-256.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · R15 history manifest must list timeline and finished-waves before the fragments, or R8's order breaks

target: spec
evidence: R8/R9/R15.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-13 · finding [open] (reviewer: in scope) · Board's existing filter/sort bar and closing-order kind chips have no stated place

target: spec
evidence: render.py:273, :722-729.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-14 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-14 · finding [open] (reviewer: in scope) · duplicate_of: backlog placement, unread targets and forge-URL construction are unspecified

target: spec
evidence: model.py:376-377, :154-156.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-15 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-15 · finding [open] (reviewer: in scope) · Group scopes are not covered by the export rules

target: spec
evidence: model.py:48, :105-136.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=finding scope=spec id=sr-16 created=2026-10-05T21:09:00+00:00 state=open review_scope=in -->
### sr-16 · finding [open] (reviewer: in scope) · Test Plan omits several things the design builds

target: spec
evidence: Test Plan vs §C, §E, §F, §H, §I.
Raised by the independent fr-spec-reviewer; full text in its return.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-05T21:09:00+00:00 -->
### spec-review-1 · review · independent spec review: 16 findings

fr-spec-reviewer (separate read-only context) checked the spec against the six decisions (q1-q6, all honoured), the triage code it names (file:line verified throughout packages/fr/src/fr/triage, fr/ghclient.py, the triage commands), and itself. Findings raised: sr-1 .. sr-16, all in scope; all fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: Since last report table: SnapshotDiff is not typed, and acceptance moves are not in acceptance_note

Fixed in the spec: §B step 2: SnapshotDiff gains structured transitions built beside the strings; acceptance rows come from acceptance_moved's comparison; strings stay for the timeline.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: views.finished_waves called from batch_drive.drive_pass creates an import cycle

Fixed in the spec: §D: finished_waves(batches, stages) lives in batch_drive.py beside closeout_event; views re-exports it.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: Origins SCHEMA constant is shared with origins-facts.json; bumping it to 2 breaks the facts loader

Fixed in the spec: §E: split into FACTS_SCHEMA=1 and CLASSIFICATION_SCHEMA=2; load_origins reads 1 or 2.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: Board's preselected wave can name a finished wave that is no longer a tab

Fixed in the spec: R8 + §B step 4 + §D: preselected_wave gains `among`; board passes unfinished keys, history the finished ones (highest finished).

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: Finished-wave predicate never finishes a wave holding an abandoned batch

Fixed in the spec: R8 + §D: abandoned is terminal; predicate takes derived stages (driver Snapshot already carries them).

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: Step-3b export decision: PrState is the wrong type, head-unchanged has nothing to compare against, the untrusted row is missing

Fixed in the spec: R13 + §I: export_prs typed LivePr; merge at the live head like _archive; table gains trusted/pending/failing/draft rows.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: _export is not idempotent across a crash between push, pr_create and recording the Export

Fixed in the spec: R13 + §I: export-adopt row adopts an open PR on the head; push(force=True) to the driver-owned branch.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: Drive loop exits on summary.done before a pending export PR is merged

Fixed in the spec: R13 + §I: owed exports count as closing (or blocked when warned), so done stays false; tested.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: Post-merge check 2 can never hold: the Export record is written to the cache after the export commit

Fixed in the spec: Test Plan post-merge 2 restated: main equals the cache as of the export commit, excepting the exports: entry.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: Judgements writer and readers need more than the spec lists to carry schema 4 and exports

Fixed in the spec: §G: JUDGEMENTS_READS gains 4; save_exports sibling writer with the same discipline; Export field order and AwareDatetime `at`; Action gains wave, action_line prints it.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: Re-export aliases do not keep test_triage_architecture.py working, and the Test Plan says the tests move anyway

Fixed in the spec: §C: no aliases; manifest/fragment tests move to test_triage_fragments.py, rewritten.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: R15 history manifest must list timeline and finished-waves before the fragments, or R8's order breaks

Fixed in the spec: R15 + §C: the history manifest names timeline and finished-waves first; §C states the appended rule's consequence.

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-13 -->
### sr-13-resolved · finding [fixed] · resolves sr-13: Board's existing filter/sort bar and closing-order kind chips have no stated place

Fixed in the spec: §B: kind chips keep heading Waves; FILTER_BAR moves inside Backlog by tier; §C names which section owns each filter.

<!-- fr:journal kind=finding scope=spec id=sr-14-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-14 -->
### sr-14-resolved · finding [fixed] · resolves sr-14: duplicate_of: backlog placement, unread targets and forge-URL construction are unspecified

Fixed in the spec: R11 + §B + §E: duplicates leave the tier sections; collect views duplicate_of targets; links use the facts URL else plain text (origins: same-repo URL with the number replaced).

<!-- fr:journal kind=finding scope=spec id=sr-15-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-15 -->
### sr-15-resolved · finding [fixed] · resolves sr-15: Group scopes are not covered by the export rules

Fixed in the spec: R13 + §I: group and org scopes both warn; tested.

<!-- fr:journal kind=finding scope=spec id=sr-16-resolved created=2026-10-05T21:09:00+00:00 state=fixed resolves=sr-16 -->
### sr-16-resolved · finding [fixed] · resolves sr-16: Test Plan omits several things the design builds

Fixed in the spec: Test Plan: pr_create adapter, _export_merge + exit 1, loop not done while owed, writer, CLI verbs end to end, moved-name note, collect viewing, rows linkage.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-05-triage-pages-goal-p2 created=2026-10-05T21:12:47+00:00 -->
### phase-split-2026-10-05-triage-pages-goal-p2 · decision · ask: the board's first screen (R2-R5, #887) is its own reviewable ask, and carries the visual evidence

Board relayout is independent of phase 1's page partition once the shared chrome and fragments exist.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-05-triage-pages-goal-p3 created=2026-10-05T21:12:48+00:00 -->
### phase-split-2026-10-05-triage-pages-goal-p3 · decision · ask: data improvements (R10, R11) are their own ask

Schema changes to origins.yaml and judgements plus their display; reviewable apart from layout.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-05-triage-pages-goal-p4 created=2026-10-05T21:12:49+00:00 -->
### phase-split-2026-10-05-triage-pages-goal-p4 · decision · ask: the driver export (R12, R13) is its own ask

State sync verbs and the driver's per-wave export PR.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-05-triage-pages-goal-p5 created=2026-10-05T21:12:50+00:00 -->
### phase-split-2026-10-05-triage-pages-goal-p5 · decision · tier: skills docs, mirrors and this repo's state (R14, R15) are mechanical and wait on #969

Prose and file moves; R15 depends on #969 merging.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-05-triage-pages-goal-p4 created=2026-10-05T21:12:51+00:00 -->
### tier-2026-10-05-triage-pages-goal-p4 · decision · hard: phase 4 adds a forge write path and changes the driver's decision table, crash recovery and loop termination

Every drive run relies on drive_pass and Summary.done; an error there strands waves or double-opens PRs.
