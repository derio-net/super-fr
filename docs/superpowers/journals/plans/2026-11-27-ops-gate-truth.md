<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-ops-gate-truth

<!-- fr:journal kind=decision scope=plan id=p1-reopen-before-merge created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-reopen-before-merge · decision · the refresh reopens changed ops (and forgets stages >= 4) before the merge, not after it (phase 1)

§A orders it merge -> push -> reopen. A merge that conflicts is aborted and the operator
merges by hand (R3); on the rerun the workspace already matches the default branch, so
drift is empty and nothing would reopen: the changed op's old closure would still close
it, which is gh#1617's defect again. So `refresh` sets the reopened set (and calls
`forget(4)` past stage 4) right after the confirmation and the records commit, before
`merge_commit`. A declined confirmation still changes nothing (R2); `Restart` is raised
only after a clean merge, push and trust.

<!-- fr:journal kind=decision scope=plan id=p1-restart-bounded created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-restart-bounded · decision · run() goes back to the first unrecorded stage on Restart, at most twice per invocation (phase 1)

A refresh merges the default branch, so the next comparison is equal; a third Restart in
one invocation can only mean the branch keeps moving, and the stage fails asking for a
re-run (MAX_RESTARTS = 2 in fr.ops.gate).

<!-- fr:journal kind=discovery scope=plan id=p1-merge-already-contained created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-merge-already-contained · discovery · merge_commit of a commit the ops branch already holds commits nothing (phase 1)

Drift can differ while the default branch adds nothing new (the workspace's own ops.yaml
was edited). `git merge --no-ff --no-commit` then leaves no MERGE_HEAD and a commit would
fail; `OpsWorkspace.merge_commit` returns the current head instead.

<!-- fr:journal kind=discovery scope=plan id=p1-label-passed-stage-6 created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-label-passed-stage-6 · discovery · a Restart from stage 7 forgets stage 6, but stage 6 stays done while the PR carries gate:devops-passed (phase 1)

`_passed` reads stage 6 done from the host state OR the forge label. After a refresh at
stage 7 that reopened an op, stage 4 and 5 rerun but stage 6 is skipped when the label
is already on the PR. Stage 4 still re-applies the reopened op; the gate pass is not
re-checked. Left as is (R6 names stage 4, which runs).

<!-- fr:journal kind=discovery scope=plan id=p1-fast-tier-cost created=2026-11-27T23:19:34+00:00 phase=1 -->
### p1-fast-tier-cost · discovery · the --fr-scope fast tier selects thousands of tests on this branch (spec/plan docs pull in every own_artifacts test) (phase 1)

The T1 run of the fast tier was still at ~6% after ~15 minutes on a loaded host (load ~20);
the per-task runs used the touched test files and their neighbours instead, and the fast
tier ran once, last.

<!-- fr:journal kind=finding scope=plan id=p1-sec-r1 created=2026-11-27T23:19:34+00:00 phase=1 state=fixed review_scope=in -->
### p1-sec-r1 · finding [fixed] (reviewer: in scope) · refresh diffed origin/<default>, then merge_commit fetched and merged the ref again (TOCTOU) (phase 1)

If the default branch moved between the comparison and the merge, the merged content
differed from what the operator confirmed and the reopened set came from a stale diff.
Fixed: `refresh` resolves `origin/<default>` once (`rev_parse`, `valid_sha`),
materialises and diffs that sha, names its first 12 characters in the question and passes
the sha to `merge_commit`; `OpsWorkspace.merge_commit` refuses a non-sha and a non-commit
(`cat-file -e <sha>^{commit}`) and merges exactly that sha (its fetch only brings objects).
Tests: test_ops_gate.py::test_the_refresh_merges_the_sha_it_diffed_though_the_default_branch_moved,
test_a_default_tip_that_is_no_sha_is_refused_before_any_diff; test_ops_gate_cmd.py::
test_merge_commit_merges_the_pinned_sha_not_a_moved_tip,
test_merge_commit_refuses_anything_but_a_commit_sha.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-27T23:19:34+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

drift is three small readers and one comparison; nothing repeated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-27T23:19:34+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

merge_commit reuses gitseam's Worktree.merge/abort_merge; the commit is one git call, so no new gitseam helper was needed

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-27T23:19:34+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the exclusion set shared by _unclosed and apply_phase was written once (_excluded over refresh.closure_exclusions) in the green step itself

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · A restart reaching stage 6 skips it when gate:devops-passed is already on the PR (phase 1)

The pass label stood in for stage 6 after a restart (gate.py), so the pass stood against reopened ops and a changed Test Plan; R6 not met.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Entry ids are snapshotted before the merge, so merged-in default-branch entries can close a reopened op (phase 1)

refresh.py took `before` ahead of the merge; journal entries brought in by merging origin/<default> then counted as closures recorded here.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · A Test Plan-only refresh at stage 6/7 does not send the run back to stage 5 (phase 1)

refresh.py forgot stages only on reopened ops, leaving new devops steps unwalked after the pass.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Missing tests for MAX_RESTARTS, a skipped-stage-6 restart, push failure after merge, and stage 6/7 refresh (phase 1)

tests/unit/test_ops_refresh.py and test_ops_gate.py covered the stage 4/5 paths only.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-28T00:23:13+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · A no-op merge whose ops still differ re-prompts every stage and storms restarts to MAX_RESTARTS (phase 1)

Tagged out by the reviewer. Fixed anyway in this PR, because the refresh loop this phase added is what storms.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-11-28T00:23:13+00:00 phase=1 -->
### review-phase-1 · review · Phase 1 review (stale ops refresh), five findings, all fixed (phase 1)

Independent review of the phase-1 diff (ops/refresh.py, ops/gate.py, commands/ops_gate_cmd.py, tests, docs) against spec R1-R6.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: A restart reaching stage 6 skips it when gate:devops-passed is already on the PR (phase 1)

406786085: the label stands in for stage 6 only when no op is reopened and 6 was not forgotten; otherwise stage 6 checks devops_blockers on the refreshed tree and fails naming them; fr never removes the label.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Entry ids are snapshotted before the merge, so merged-in default-branch entries can close a reopened op (phase 1)

406786085: `before` is unioned with the entry ids read after the merge, so merged-in entries never count.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: A Test Plan-only refresh at stage 6/7 does not send the run back to stage 5 (phase 1)

406786085 + 031ec0309: a Test Plan-only drift at stage 6/7 forgets stages 5+ and restarts; docs updated.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Missing tests for MAX_RESTARTS, a skipped-stage-6 restart, push failure after merge, and stage 6/7 refresh (phase 1)

406786085: tests for the MAX_RESTARTS bound, a failed push and its rerun, refresh at stages 6 and 7, and is_ancestor on real git.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-28T00:23:13+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: A no-op merge whose ops still differ re-prompts every stage and storms restarts to MAX_RESTARTS (phase 1)

dca2c3ada + 406786085: a pinned sha already in the ops branch with drift persisting fails the stage before the prompt, naming what differs.

<!-- fr:journal kind=decision scope=plan id=p2-rows-field-last created=2026-11-28T01:48:09+00:00 phase=2 -->
### p2-rows-field-last · decision · Step.rows is the dataclass's last field, not right after op (phase 2)

`_step` builds `Step(n, text, gate, raw, op, line)` positionally, so a field inserted
after `op` would have shifted `line`. `rows` was appended after `line` with a default;
every other caller builds `Step` by keyword or with fewer positionals.

<!-- fr:journal kind=decision scope=plan id=p2-ran-vs-na-by-title created=2026-11-28T01:48:09+00:00 phase=2 -->
### p2-ran-vs-na-by-title · decision · R13's "a step recorded ran" is read from the outcome entry's title (phase 2)

`fold_step_outcomes` folds ran and n/a into one kind, `discovery`. The new
`holds._fold_outcomes` keeps what the latest outcome says: `n/a` when its title ends
`: n/a` (the title `fr closeout outcome` writes), `owed` for an owed entry, else `ran`;
an owed entry resolved `fixed` reads `ran`. `holds.ran_steps` reads it. The FakeTree in
tests/unit/test_ops_gate.py now titles its outcomes as the real command does.

<!-- fr:journal kind=decision scope=plan id=p2-tester-run-resolution created=2026-11-28T01:48:09+00:00 phase=2 -->
### p2-tester-run-resolution · decision · the tester pass resolves the run exactly as the devops pass does, refusals included (phase 2)

`fr gate pass --gate tester` uses `_run_for` (R11 says "as --gate devops resolves it
today"), so an unreadable cursor or several runs naming the head ref refuse there too.
Outside a checkout it passes as before, unless `--run` was given (then it refuses:
the named run's evidence cannot be read).

<!-- fr:journal kind=decision scope=plan id=p2-one-walk-per-row-per-range created=2026-11-28T01:48:09+00:00 phase=2 -->
### p2-one-walk-per-row-per-range · decision · a row named by several steps of one --step range gets one walk, from its first step (phase 2)

One `AcceptanceItem` per row per record. `closeout outcome --step 1-5 --ran` on a range
where steps 1 and 5 both name `r1` records one walk, evidence `Test Plan step 1: <e>`.

<!-- fr:journal kind=decision scope=plan id=p2-probe-identity-always created=2026-11-28T01:48:09+00:00 phase=2 -->
### p2-probe-identity-always · decision · stage 5 passes --harness fr-ops-probe --model op:<id> on every passing probe (phase 2)

R9 names the probe path's walk identity. The flags are passed whenever the probe passed,
whether or not the step names rows; with no rows they change nothing.

<!-- fr:journal kind=decision scope=plan id=p2-stage6-list-excludes-head created=2026-11-28T01:48:09+00:00 phase=2 -->
### p2-stage6-list-excludes-head · decision · stage 6's owed list excludes the PR head's walks and outcomes; fr gate pass does not (phase 2)

R14's listing uses `_owed_items` (gate_items with R12's exclusions), the stage's own
view. `fr gate pass` itself, run in the ops workspace, still folds everything the tree
holds (unchanged from fr-ops R14). The recovery commands are printed for rows
`row_walked` reads not walked with no exclusion, which is what the refused pass saw.

<!-- fr:journal kind=discovery scope=plan id=p2-reviewed-stamp-colon created=2026-11-28T01:48:09+00:00 phase=2 -->
### p2-reviewed-stamp-colon · discovery · a reviewed stamp note holding a colon and a space breaks the page front matter (phase 2)

`reviewed:` is a plain YAML scalar, so a note with `: ` inside (for example the rows
pointer spelled with its colon) makes the front matter unparseable; sync-readme then
silently dropped the page's link from the skills table. Stamp notes here avoid ": ".

<!-- fr:journal kind=discovery scope=plan id=p2-docs-check-reads-commits created=2026-11-28T01:48:09+00:00 phase=2 -->
### p2-docs-check-reads-commits · discovery · fr docs check judges committed pages; an edited but uncommitted page still reads stale (phase 2)

Six pages beyond the four the plan names cover touched paths (fr-acceptance, fr-triage,
index, gate-backfill, fr-brainstorming-and-plan, and the reference page); each was
stamped after checking its claims still hold.

<!-- fr:journal kind=discovery scope=plan id=p2-fast-tier-skill-length created=2026-11-28T01:48:09+00:00 phase=2 -->
### p2-fast-tier-skill-length · discovery · the fast tier caught fr-devops-gate SKILL.md over its 120-line budget (phase 2)

The fast tier (9696 passed, 1 failed, 57 min on a loaded host) failed only
test_skill_validation::test_under_120_lines[fr-devops-gate]: the new rows section
took the skill to 131 lines. The section was folded into one paragraph (115 lines),
the mirrors re-synced, and the skill's tests (validation, settings, both mirror
tripwires, tool neutrality, README sync, CLI smoke) re-ran green: 202 passed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-28T01:48:09+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

one regex and one optional field beside the op pointer; nothing repeated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-28T01:48:09+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

row_walked is four lines and close_commands is the moved printer itself; acceptance_cmd keeps a two-line wrapper

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-28T01:48:09+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

the row-walk builder is one helper (_row_walks) written once; its harness arithmetic was folded into owed_harnesses in P2.T6.S3

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-28T01:48:09+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

devops_blockers became the gate_blockers wrapper and gated_steps shares _gated_steps with gate_items in the green step itself

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-11-28T01:48:09+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

stage 5's row walk command and stage 6's recovery share row_walk_argv, and stages 6/7 share _owed_items, written once in the green step; the rest was deduped in P2.T6.S3

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · R12 leak: row_walked trusted the row status the PR head set, and owed_harnesses counted head walks (phase 2)

Stage judged walked by row.status (walks.py:54) and counted owed harnesses over all walks (gate.py:1291, closeout_cmd.py:297).

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Stage 5 skipped rows named by a ran step and stage 6's fr gate pass counted head walks, so a head-only walk passed the devops gate (phase 2)

gate.py:1310,1362; holds.py:72-80.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · head_walks read only the run's own feature fragment (phase 2)

gate.py:1253: head walks on spec-citing rows in other fragments were not excluded.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · _owed_items let AcceptanceError/SectionError/SettingsError escape as a traceback (phase 2)

gate.py:1373-1391; holds.py:196.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · Stage-6 row recovery printed an operator walk that cannot discharge a row owing other harnesses (phase 2)

gate.py:1291,1446.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · Stage 7's tester gate pass omitted --run (phase 2)

gate.py:1481: run resolution could refuse on several runs or an unrelated unreadable cursor.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · Skill and ops.md claimed PR-head walks never count while fr gate pass counted them (phase 2)

SKILL.md:109; docs/ops.md:435.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · fr-devops-gate SKILL.md re-wrapped into ~200-char lines to fit the 120-line budget (phase 2)

SKILL.md ~100-109; fast tier was not re-run after the fix.

<!-- fr:journal kind=finding scope=plan id=p2-r9 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=in -->
### p2-r9 · finding [open] (reviewer: in scope) · row_walked's max-by-at broke ties to the first walk (phase 2)

walks.py:56: a same-second later failing walk read as passed.

<!-- fr:journal kind=finding scope=plan id=p2-r10 created=2026-11-28T03:59:17+00:00 phase=2 state=open review_scope=out -->
### p2-r10 · finding [open] (reviewer: out of scope) · The triage driver's rows-walked tester pass bypasses gate_blockers (phase 2)

batch_drive.py:1632; triage_batch_cmd.py:6180.

<!-- fr:journal kind=decision scope=plan id=p2-ran-vs-na-by-title-superseded created=2026-11-28T03:59:17+00:00 phase=2 -->
### p2-ran-vs-na-by-title-superseded · decision · Supersedes p2-ran-vs-na-by-title: the ran/n-a fold was removed with ran_steps (phase 2)

After p2-r2, stage 5 asks about every row not walked head-free; no step-outcome fold decides which rows are skipped.

<!-- fr:journal kind=decision scope=plan id=p2-stage6-list-excludes-head-superseded created=2026-11-28T03:59:17+00:00 phase=2 -->
### p2-stage6-list-excludes-head-superseded · decision · Supersedes p2-stage6-list-excludes-head: stage 6 refuses on head-free blockers (phase 2)

After p2-r2, stage 6 computes gate_blockers with the PR head's walks excluded and fails before running fr gate pass while any remain (spec R14).

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-11-28T03:59:17+00:00 phase=2 -->
### review-phase-2 · review · Phase 2 review (rows and walks): nine in-scope findings fixed, one out of scope (phase 2)

Independent review of the phase-2 diff (dfb5a02..HEAD) against spec R7-R16.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: R12 leak: row_walked trusted the row status the PR head set, and owed_harnesses counted head walks (phase 2)

fix(acceptance)+fix(closeout)+fix(ops): head-free row_walked ignores status and requires every owed harness to have a latest passing non-head walk; closeout --pr-head counts owed harnesses over non-head walks.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Stage 5 skipped rows named by a ran step and stage 6's fr gate pass counted head walks, so a head-only walk passed the devops gate (phase 2)

fix(ops): stage 5 asks every row not walked head-free (ran_steps shortcut removed); stage 6 fails before fr gate pass while head-free blockers remain.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: head_walks read only the run's own feature fragment (phase 2)

fix(ops): head_walks reads every fragment on the head, through the artifact root.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: _owed_items let AcceptanceError/SectionError/SettingsError escape as a traceback (phase 2)

fix(ops): _owed_items and _gate_exit turn AcceptanceError, SectionError, SettingsError, TestPlanHeadingError and OSError into StageFailed.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Stage-6 row recovery printed an operator walk that cannot discharge a row owing other harnesses (phase 2)

fix(ops): recovery_argvs prints one walk command per owed harness; only the last sets walked.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: Stage 7's tester gate pass omitted --run (phase 2)

fix(ops): stage 7's tester pass passes --run.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: Skill and ops.md claimed PR-head walks never count while fr gate pass counted them (phase 2)

docs(skill)+docs(ops): skill, docs/ops.md and the explainer state the head-free rule and that stage 6 stops before the pass.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: fr-devops-gate SKILL.md re-wrapped into ~200-char lines to fit the 120-line budget (phase 2)

docs(skill): re-wrap undone; the skill fits 120 lines by condensing and pointing to the fr ops guide.

<!-- fr:journal kind=finding scope=plan id=p2-r9-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=fixed resolves=p2-r9 -->
### p2-r9-resolved · finding [fixed] · resolves p2-r9: row_walked's max-by-at broke ties to the first walk (phase 2)

fix(acceptance): a tie on at goes to the later walk in the list.

<!-- fr:journal kind=finding scope=plan id=p2-r10-resolved created=2026-11-28T03:59:17+00:00 phase=2 state=open resolves=p2-r10 out_of_scope=true -->
### p2-r10-resolved · finding [out-of-scope] · resolves p2-r10: The triage driver's rows-walked tester pass bypasses gate_blockers (phase 2)

Pre-existing: the triage driver's rows-walked tester pass predates this change; this PR changes fr gate pass and the DevOps stage only.

<!-- fr:journal kind=decision scope=plan id=p3-owed-left-out-only-when-reported created=2026-11-28T05:35:58+00:00 phase=3 -->
### p3-owed-left-out-only-when-reported · decision · The owed group leaves out a step outcome or manual-phase entry only when another group reports that step or phase (phase 3)

R17 says an owed entry already reported elsewhere is left out. A `test-plan-step-<n>[-k]`
owed entry is dropped only when step n is an item of a gate group (GateItem gained an
optional `step`), and a `manual-phase-<n>` entry only when phase n is in the manual
group. An owed outcome of a step no post-merge gate owns (a developer step) stays in
the owed group, so it is never hidden.

<!-- fr:journal kind=decision scope=plan id=p3-final-line-head-free created=2026-11-28T05:35:58+00:00 phase=3 -->
### p3-final-line-head-free · decision · The DevOps stage's final line reads the DoD with the PR head's walks and outcomes excluded (phase 3)

`run()` builds the DoD on the ops workspace through `_head_exclusions` (the same R12
exclusions `_owed_items` uses, now one helper), so a walk or outcome the PR author wrote
cannot make the stage say complete. `fr run dod` and the pickup briefs read the checkout
as it is. An unreadable DoD (or no recorded head) says "every stage ran; the Definition
of Done cannot be read", never complete. GateResult's ok and exit code are unchanged.

<!-- fr:journal kind=decision scope=plan id=p3-cli-import-order created=2026-11-28T05:35:58+00:00 phase=3 -->
### p3-cli-import-order · decision · cli.py's dod_cmd import sits where ruff's isort puts it, before run_cmd (phase 3)

The plan said "right after the run_cmd import"; ruff's import sorting moves it. The order
is immaterial: dod_cmd imports run_app from commands.run_cmd itself, so the command is
registered whichever import runs first. run_cmd.py is untouched.

<!-- fr:journal kind=decision scope=plan id=p3-finished-owed-brief created=2026-11-28T05:35:58+00:00 phase=3 -->
### p3-finished-owed-brief · decision · A finished DevOps stage with owed items gets its own brief heading and lists them; no reap line (phase 3)

The finished devops_brief keeps its "DevOps stage complete ... Nothing is left" text only
when the DoD is discharged. Otherwise it is headed "every stage ran, work still owed",
lists `dod.owed()` and points at `fr run dod <run>`; it does not tell the operator to reap
the workspace while work is owed. Every brief form ends with the DoD section.

<!-- fr:journal kind=discovery scope=plan id=p3-dod-needs-a-readable-exit created=2026-11-28T05:35:58+00:00 phase=3 -->
### p3-dod-needs-a-readable-exit · discovery · A repo whose acceptance identity cannot be resolved has an unreadable DoD (phase 3)

run_exit raises AcceptanceError ("cannot resolve repo identity") in a repo with no
fragment and no github origin, so the DoD is a DodError there and the brief prints
"Definition of Done — cannot be read". The test fixtures for the closeout brief write a
matrix; the old gh#1275 test now builds a real plan folder and a closed op.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-28T05:35:58+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

dod.py reuses gate_items, run_exit, the plan parser and the owed fold; the only new code is the grouping, and the text renderer it shares was folded in P3.T3.S3

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-28T05:35:58+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

dod_cmd is one command over definition_of_done and dod_lines, loading the run through run_cmd's own _load_or_exit; nothing repeated to fold

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-28T07:05:41+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · The stage's final line let PR-head owed resolutions and manual-phase ticks discharge the owed and manual groups (phase 3)

R12's head exclusion reached only gate_items (dod.py:119-143,161-193; gate.py _say_done).

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-28T07:05:41+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · fr run dod was documented as changing nothing, but run is not a read-only command (phase 3)

trigger.py:93-105: the entry gate may migrate first; the run group's host-side refusal applies.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-28T07:05:41+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · A recorded but missing plan silently dropped manual phases and plan-journal owed entries (phase 3)

dod.py:138-142: run_plan_dir None gave an empty group, a fail-open complete.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-28T07:05:41+00:00 phase=3 state=open review_scope=out -->
### p3-r4 · finding [open] (reviewer: out of scope) · _say_done catches only DodError and StageFailed (phase 3)

gate.py ~1441: an unexpected exception would crash after all stages ran; no concrete case traced.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-28T07:05:41+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · No tests for head-carried resolutions or ticks inside the stage, nor for a recorded but missing plan (phase 3)

Both would have caught p3-r1 and p3-r3.

<!-- fr:journal kind=finding scope=plan id=p3-sec-r1 created=2026-11-28T07:05:41+00:00 phase=3 state=open review_scope=in -->
### p3-sec-r1 · finding [open] (reviewer: in scope) · The head's manual-tick lookup checked only the live plan location (phase 3)

Automated security review of gate.py: run_plan_dir can resolve the archived location too, so a head carrying the plan there escaped the exclusion.

<!-- fr:journal kind=decision scope=plan id=p3-head-manual-tick-rule created=2026-11-28T07:05:41+00:00 phase=3 -->
### p3-head-manual-tick-rule · decision · A manual phase counts as ticked by the PR head when the head's copy is ticked with the same state block (phase 3)

The plan does not exist on the base, so ticks cannot be compared with it. A tick or re-tick on the ops branch changes the state block and counts; one identical to the head's copy proves nothing inside the stage.

<!-- fr:journal kind=review scope=plan id=review-phase-3 created=2026-11-28T07:05:41+00:00 phase=3 -->
### review-phase-3 · review · Phase 3 review (Definition of Done): four in-scope findings and one security finding fixed, one out of scope (phase 3)

Independent review of the phase-3 diff (80a2995..HEAD) against spec R17-R20, plus an automated security review of gate.py.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-28T07:05:41+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: The stage's final line let PR-head owed resolutions and manual-phase ticks discharge the owed and manual groups (phase 3)

4368956ba: definition_of_done takes exclude_entries and exclude_manual_ticks; _say_done passes head_entry_ids and head_manual_ticks.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-28T07:05:41+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: fr run dod was documented as changing nothing, but run is not a read-only command (phase 3)

16c397225: docstring and docs say it writes no artifact itself, may migrate first and runs host-side; a test pins the devcontainer refusal.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-28T07:05:41+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: A recorded but missing plan silently dropped manual phases and plan-journal owed entries (phase 3)

4368956ba: a recorded plan neither live nor archived raises DodError (exit 2, cannot be read).

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-28T07:05:41+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: No tests for head-carried resolutions or ticks inside the stage, nor for a recorded but missing plan (phase 3)

4368956ba + 45b6cf3a3: tests in test_run_dod.py, test_dod_cmd.py and test_ops_gate.py.

<!-- fr:journal kind=finding scope=plan id=p3-sec-r1-resolved created=2026-11-28T07:05:41+00:00 phase=3 state=fixed resolves=p3-sec-r1 -->
### p3-sec-r1-resolved · finding [fixed] · resolves p3-sec-r1: The head's manual-tick lookup checked only the live plan location (phase 3)

30c4b4378: the head copy is looked up at the live and archived locations; an unreadable phase file is StageFailed.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-28T07:05:41+00:00 phase=3 state=open resolves=p3-r4 out_of_scope=true -->
### p3-r4-resolved · finding [out-of-scope] · resolves p3-r4: _say_done catches only DodError and StageFailed (phase 3)

A robustness note with no traced exception; the caught set matches _owed_items.
