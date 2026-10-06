# Journal: 2026-10-06-triage-dedupe

<!-- fr:journal kind=decision scope=plan id=one-phase created=2026-10-06T07:49:15+00:00 -->
### one-phase · decision · One agentic phase: one ask, small surfaces read against one spec

Model, engine, check, board, driver and skill are one reviewable ask (triage finds and records duplicates); a second phase would add a fixed executor/reviewer round trip and a skeleton task for no review benefit.

<!-- fr:journal kind=discovery scope=plan id=skill-120-line-cap created=2026-10-06T08:27:13+00:00 phase=1 -->
### skill-120-line-cap · discovery · fr-triage SKILL.md sat exactly at the 120-line cap (phase 1)

tests/unit/test_skill_validation.py caps every SKILL.md at 120 lines and fr-triage was already at 120, so the dedupe teaching had to be paid for by joining wrapped paragraphs (no words dropped) and putting the example row on one flow line.

<!-- fr:journal kind=discovery scope=plan id=kanban-phrase-table created=2026-10-06T08:27:13+00:00 phase=1 -->
### kanban-phrase-table · discovery · A new ActionKind needs a phrase in triage/kanban.py (phase 1)

kanban._ACTION_PHRASES is indexed by every ActionKind (test_every_action_kind_has_a_phrase), so adding dedupe to the driver needed a phrase there; the action names no batch and is never a card hint.

<!-- fr:journal kind=discovery scope=plan id=dedupe-fixture-states created=2026-10-06T08:27:13+00:00 phase=1 -->
### dedupe-fixture-states · discovery · The calibration capture is mostly closed issues (phase 1)

594/607/631/640/647/724/725 are closed on the forge today; the test loads every captured issue as open, since the engine compares open issues only and the capture is of text, not state.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-06T08:27:13+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

Task 6 is skill prose, mirrors, fragment and matrix; there is no code to restructure (the 120-line skill cap was met by joining wrapped lines, content unchanged).

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · main (#976) already ships duplicate_of with other semantics; spec and code reconciled (phase 1)

Review p1 finding p1-r1: main (#976) already ships duplicate_of with other semantics; spec and code reconciled.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · _FINDING matched hyphenated prose such as finding out-of-scope (phase 1)

Review p1 finding p1-r2: _FINDING matched hyphenated prose such as finding out-of-scope.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · finding and #ref signals read only the body (phase 1)

Review p1 finding p1-r3: finding and #ref signals read only the body.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · R10 could miss the final wave when the finishing pass ends the drive (phase 1)

Review p1 finding p1-r4: R10 could miss the final wave when the finishing pass ends the drive.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · an unselected member's hand-merged archive was never fetched (phase 1)

Review p1 finding p1-r5: an unselected member's hand-merged archive was never fetched.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · keys sorted as text (phase 1)

Review p1 finding p1-r6: keys sorted as text.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · capture script not self-contained, no per-state shots (phase 1)

Review p1 finding p1-r7: capture script not self-contained, no per-state shots.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · a large candidate group listed every pair (phase 1)

Review p1 finding p1-r8: a large candidate group listed every pair.

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · captured #454/#458 never asserted (phase 1)

Review p1 finding p1-r9: captured #454/#458 never asserted.

<!-- fr:journal kind=finding scope=plan id=p1-r10 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=in -->
### p1-r10 · finding [open] (reviewer: in scope) · intro paragraph indented, group lines flush (phase 1)

Review p1 finding p1-r10: intro paragraph indented, group lines flush.

<!-- fr:journal kind=finding scope=plan id=p1-o1 created=2026-10-06T08:59:54+00:00 phase=1 state=open review_scope=out -->
### p1-o1 · finding [open] (reviewer: out of scope) · fr's capture-script witness reads a value-taking uv flag as the program (phase 1)

fr.run.telemetry._executes treats `uv run --with playwright python script.py` as running `playwright`, so a capture run that way is never witnessed; `--with=playwright` passes. Documented limit in shell_named_since's docstring, not caused by this change.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-10-06T08:59:54+00:00 phase=1 -->
### p1-review · review · Phase 1 code review (independent reviewer) (phase 1)

Reviewer re-read spec, plan and the committed diff from a detached HEAD worktree, ran the 8 affected test files (407 passed), stress-tested escaping, drove the board UI itself and opened fresh screenshots. Findings raised: p1-r1, p1-r2, p1-r3, p1-r4, p1-r5, p1-r6, p1-r7, p1-r8, p1-r9, p1-r10 (all in scope). Plus p1-o1 (out of scope) from the orchestrator.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: main (#976) already ships duplicate_of with other semantics; spec and code reconciled (phase 1)

Merged origin/main and reconciled per spec §2.1 (decision d-merge-976): one duplicate_of; chains load and are reported by duplicate_chained; duplicates leave tiers into Parked plus the original-row Duplicates paragraph; finished = #976's finished_waves; spec R3/R5/R8/R10, §3.D, §3.E amended. Stored docs/triage judgements (255) still load.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: _FINDING matched hyphenated prose such as finding out-of-scope (phase 1)

A finding id now needs a digit or backticks; tests test_a_hyphenated_word_after_finding_is_prose_not_an_id and test_a_backticked_finding_id_needs_no_digit.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: finding and #ref signals read only the body (phase 1)

Both read title plus body (_text); test test_the_finding_and_reference_may_sit_in_the_title.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: R10 could miss the final wave when the finishing pass ends the drive (phase 1)

_Driver.observation_owed grants one extra pass when a wave was unfinished at the last pass's start; loop-level test test_a_finishing_loop_runs_one_observation_pass_only_when_a_wave_was_unfinished.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=refuted resolves=p1-r5 -->
### p1-r5-resolved · finding [refuted] · resolves p1-r5: an unselected member's hand-merged archive was never fetched (phase 1)

After the #976 merge the dedupe step reads Snapshot.finished = finished_waves(judgements.batches, stages), computed over EVERY batch from close-out events (archived set) and derived stages; no archive PR list is read for the decision, so the selection no longer affects it.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: keys sorted as text (phase 1)

dedupe.key_order sorts by (repo, number); test test_keys_order_by_number_not_text.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: capture script not self-contained, no per-state shots (phase 1)

New capture_dedupe_board.py renders the boards from code and writes one shot per named state at 1280px and 375px (used for deliver's fresh screenshots).

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: a large candidate group listed every pair (phase 1)

Board shows 10 pairs per group then +N more (PAIRS_SHOWN); check --json keeps all; test test_a_large_candidate_group_lists_ten_pairs_then_a_count.

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: captured #454/#458 never asserted (phase 1)

Calibration test now asserts the (454, 458) group.

<!-- fr:journal kind=finding scope=plan id=p1-r10-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=fixed resolves=p1-r10 -->
### p1-r10-resolved · finding [fixed] · resolves p1-r10: intro paragraph indented, group lines flush (phase 1)

After the merge main's .tier-desc has no left margin; re-captured phone/desktop Possible duplicates shots show intro and groups flush.

<!-- fr:journal kind=finding scope=plan id=p1-o1-resolved created=2026-10-06T08:59:54+00:00 phase=1 state=open resolves=p1-o1 out_of_scope=true -->
### p1-o1-resolved · finding [out-of-scope] · resolves p1-o1: fr's capture-script witness reads a value-taking uv flag as the program (phase 1)

A limit of fr's run telemetry, not of triage dedupe; this change neither introduced nor touches it.
