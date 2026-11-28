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

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · _existing_pass (gate.py:1532-1540, reached from stage 6 at :1384 when gate:devops-passed is on the PR) judges with devops_blockers with no head exclusions, so PR-head walks/outcomes discharge the gate after a refresh and stage 6 is marked done, against R6/R12 and the shape's "stage 6 refuses while head-free blockers remain"

Raised by the security lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · content the refresh merges in from the default branch still discharges items: only the pinned head's walks/outcomes/ticks are excluded and merged-in plan-journal entries only for reopened ops (refresh.py:102,198), contradicting the shape's "merged-in entries never count" (shape.md:8) and the lens's "merged-in content must not discharge anything"

Raised by the security lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-security-r3 · finding [open] (reviewer: in scope) · gate_items judges ops by the latest plan-journal entry with no PR-head exclusion (holds.py:140-144), so stage 6's "head excluded" refusal and R20's DoD line count head-carried op closures; only stage 4 running first protects this

Raised by the security lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r4 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-security-r4 · finding [open] (reviewer: in scope) · head_walks (gate.py:1257) and closeout _head_walks (closeout_cmd.py:328) read only fragment names present in the ops workspace, so walks in a head fragment the workspace lacks (renamed/moved) are never excluded; list the head's tree instead

Raised by the security lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r5 created=2026-11-28T09:12:02+00:00 state=open review_scope=out -->
### l-security-r5 · finding [open] (reviewer: out of scope) · under quiet/stealth head_walks skips every fragment (gate.py:1258) as journal exclusions already do: walks/outcomes the feature run wrote to the fr artifact branch before merge are never excluded, so the PR-controlled boundary holds only under repo placement

Raised by the security lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-security-r6 created=2026-11-28T09:12:02+00:00 state=open review_scope=out -->
### l-security-r6 · finding [open] (reviewer: out of scope) · _passed (gate.py:1698-1706) still treats a bare gate:devops-passed label as stage 6 done without any blocker check when no refresh reopened or forgot stage 6, so a hand-added label skips the head-free check

Raised by the security lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · refresh.py:152 relies on HostCheckout.fetch, which swallows a failed default-branch fetch as a warning, so drift compares against a stale origin/<default> and can read "equal" (fail-open on R1)

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · GitError from materialise (refresh.py:159), is_ancestor (refresh.py:166, ops_gate_cmd.py:75-82) and a non-UTF-8 head fragment in head_walks (gate.py:1261) escapes run() as a traceback, never a StageFailed

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · after a conflict merged by hand (or a failed merge commit, ops_gate_cmd.py:100), reopened.before never gains the merged-in entry ids (refresh.py:198 skipped), so default-branch entries close reopened ops against R6; the commit-failure path also leaves MERGE_HEAD with no abort hint

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · _say_done (gate.py:1490-1525) reports an unreadable or owed Definition of Done but run() still returns GateResult(True), so `fr ops gate` exits 0

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r5 · finding [open] (reviewer: in scope) · _existing_pass (gate.py:1541) catches only OpsLoadError; AcceptanceError/SectionError/SettingsError from run_exit/gated_rows escape as a traceback in stage 6

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r6 · finding [open] (reviewer: in scope) · gate_cmd._refuse_on_blockers (gate_cmd.py:134-149) does not catch SettingsError, which the new gated_rows -> disabled() call can raise: traceback instead of an exit-2 refusal

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r7 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r7 · finding [open] (reviewer: in scope) · closeout_cmd._head_walks (closeout_cmd.py:333) treats any failed `git show`, including an unknown --pr-head sha, as an absent fragment: an empty exclusion, against its docstring's refusal promise

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r8 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r8 · finding [open] (reviewer: in scope) · closeout_cmd._shape_default (closeout_cmd.py:351) silently drops an unreadable cursor for an explicit --run, so the row's walk strategy changes or is refused with no signal

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r9 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r9 · finding [open] (reviewer: in scope) · head_manual_ticks (gate.py:1464-1474) calls .get()/int() on PR-controlled YAML; a malformed phase raises AttributeError/ValueError that _say_done does not catch (traceback on the final line)

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-errors-r10 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-errors-r10 · finding [open] (reviewer: in scope) · closeout outcome calls close_commands (closeout_cmd.py:222) before the not-committed warning (closeout_cmd.py:224); an AcceptanceError there tracebacks after the write and hides that warning

Raised by the errors lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · R4 test is tautological: apply_phase already calls gate.trust (gate.py:681), so removing refresh's re-trust (refresh.py:204) keeps test_ops_gate.py:1606 green; R4 unpinned at stages 5-7

Raised by the tests lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · stage 6's _existing_pass judges the pre-refresh label with devops_blockers without head walk/outcome exclusion (gate.py:1385,1540), contradicting R12 and the shape's trust boundary; existing-pass tests use only op blockers

Raised by the tests lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · gate_items op items count plan-journal op entries the PR head carries (holds.py:146); stage 6 _owed_items and the R20 DoD never exclude them, unlike _unclosed/apply_phase; shape trust boundary contradicted, untested

Raised by the tests lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · drift loads ops with runbook needs from a scratch tree that holds only _head_paths (gate.py:717, refresh.py:159); a runbook outside spec/plan/fragments/.fr fails stages 4-7 every run; no runbook test

Raised by the tests lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · closeout_cmd._head_walks silently returns an empty exclusion when git show fails for a valid-looking sha (closeout_cmd.py:333) despite its "refuses" docstring; no negative test

Raised by the tests lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-tests-r6 · finding [open] (reviewer: in scope) · FakeTree._walk_named_rows (test_ops_gate.py:164) diverges from real closeout outcome: fixed strategy live, any-passing not latest-per-harness, ignores --pr-head, edits rows not amendments

Raised by the tests lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-tests-r7 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-tests-r7 · finding [open] (reviewer: in scope) · untested: R13 ran on a multi-harness row keeping status in _ask_rows; R3 records-commit-before-abort and post-conflict host state; R3 lease value (FakeTree.head constant); R14 unreadable setting

Raised by the tests lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · stage 6's _existing_pass (gate.py:1532-1549) judges blockers with devops_blockers, not head-free, so PR-head outcomes or a head-written `walked` status can let a pre-refresh gate:devops-passed stand; contradicts fr-devops-gate.md:186-189 and the shape's trust boundary

Raised by the docs-accuracy lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · _recovery (gate.py:1552-1580) picks open steps without head exclusion, so a step closed only by a PR-head outcome gets no `closeout outcome` command while stage 6 still refuses on it; contradicts ops.md:254 and fr-devops-gate.md:194 ("commands that close each item")

Raised by the docs-accuracy lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · ops.md:316-329 orders the refresh as commit, merge, push, reopen, and says a conflict leaves the workspace at the records commit, but refresh.py:181-190 reopens the ops and forgets stages before the merge, so a conflict leaves them reopened and forgotten

Raised by the docs-accuracy lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-docs-accuracy-r4 · finding [open] (reviewer: in scope) · fr-devops-gate SKILL.md:82-83 drops where `fr ops attest` runs (fr isolation exec on chore/ops-<slug>), its --plan (required for a runbook op, ops_cmd.py:451) and "an op with a check cannot be attested"; worse guidance than the text it replaced

Raised by the docs-accuracy lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5 created=2026-11-28T09:12:02+00:00 state=open review_scope=in -->
### l-docs-accuracy-r5 · finding [open] (reviewer: in scope) · fr-devops-gate SKILL.md:114 says a hand-run `fr gate pass` "judges the merged tree"; gate_cmd reads the current checkout, as ops.md says ("as the checkout holds them")

Raised by the docs-accuracy lens reviewer at lens-review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r6 created=2026-11-28T09:12:02+00:00 state=open review_scope=out -->
### l-docs-accuracy-r6 · finding [open] (reviewer: out of scope) · the new "merge, never rebase, because the ops branch is already pushed; a rebase would rewrite your evidence" rationale (fr-devops-gate.md:109-111, ops.md:325-326) sits beside stage 3, which still rebases that pushed ops branch with a lease

Raised by the docs-accuracy lens reviewer at lens-review.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-28T09:12:02+00:00 -->
### lens-review-1 · review · Lens review: security, errors, tests, docs-accuracy over the whole feature diff

Four lens reviewers each read the whole feature diff (merge-base 085d1cbe) under one lens. 29 findings: 26 in scope, all fixed; 3 out of scope.

```review-lens
lens: security
examined: packages/fr/src/fr/ops/refresh.py, packages/fr/src/fr/ops/gate.py, packages/fr/src/fr/ops/holds.py, packages/fr/src/fr/acceptance/walks.py, packages/fr/src/fr/commands/ops_gate_cmd.py, packages/fr/src/fr/commands/closeout_cmd.py, packages/fr/src/fr/commands/gate_cmd.py, packages/fr/src/fr/run/dod.py, docs/superpowers/specs/2026-11-27-ops-gate-truth-design.md
```
```review-findings
l-security-r1 | in | _existing_pass (gate.py:1532-1540, reached from stage 6 at :1384 when gate:devops-passed is on the PR) judges with devops_blockers with no head exclusions, so PR-head walks/outcomes discharge the gate after a refresh and stage 6 is marked done, against R6/R12 and the shape's "stage 6 refuses while head-free blockers remain"
l-security-r2 | in | content the refresh merges in from the default branch still discharges items: only the pinned head's walks/outcomes/ticks are excluded and merged-in plan-journal entries only for reopened ops (refresh.py:102,198), contradicting the shape's "merged-in entries never count" (shape.md:8) and the lens's "merged-in content must not discharge anything"
l-security-r3 | in | gate_items judges ops by the latest plan-journal entry with no PR-head exclusion (holds.py:140-144), so stage 6's "head excluded" refusal and R20's DoD line count head-carried op closures; only stage 4 running first protects this
l-security-r4 | in | head_walks (gate.py:1257) and closeout _head_walks (closeout_cmd.py:328) read only fragment names present in the ops workspace, so walks in a head fragment the workspace lacks (renamed/moved) are never excluded; list the head's tree instead
l-security-r5 | out | under quiet/stealth head_walks skips every fragment (gate.py:1258) as journal exclusions already do: walks/outcomes the feature run wrote to the fr artifact branch before merge are never excluded, so the PR-controlled boundary holds only under repo placement
l-security-r6 | out | _passed (gate.py:1698-1706) still treats a bare gate:devops-passed label as stage 6 done without any blocker check when no refresh reopened or forgot stage 6, so a hand-added label skips the head-free check
```

```review-lens
lens: errors
examined: packages/fr/src/fr/ops/refresh.py, packages/fr/src/fr/ops/gate.py, packages/fr/src/fr/commands/ops_gate_cmd.py, packages/fr/src/fr/run/dod.py, packages/fr/src/fr/commands/dod_cmd.py, packages/fr/src/fr/ops/holds.py, packages/fr/src/fr/commands/gate_cmd.py, packages/fr/src/fr/commands/closeout_cmd.py, packages/fr/src/fr/run/closeout.py, packages/fr/src/fr/acceptance/walks.py, packages/fr/src/fr/commands/acceptance_cmd.py, packages/fr/src/fr/plan_review/checks.py, packages/fr/src/fr/spec.py, packages/fr/src/fr/triage/ledger.py, docs/superpowers/specs/2026-11-27-ops-gate-truth-design.md
```
```review-findings
l-errors-r1 | in | refresh.py:152 relies on HostCheckout.fetch, which swallows a failed default-branch fetch as a warning, so drift compares against a stale origin/<default> and can read "equal" (fail-open on R1)
l-errors-r2 | in | GitError from materialise (refresh.py:159), is_ancestor (refresh.py:166, ops_gate_cmd.py:75-82) and a non-UTF-8 head fragment in head_walks (gate.py:1261) escapes run() as a traceback, never a StageFailed
l-errors-r3 | in | after a conflict merged by hand (or a failed merge commit, ops_gate_cmd.py:100), reopened.before never gains the merged-in entry ids (refresh.py:198 skipped), so default-branch entries close reopened ops against R6; the commit-failure path also leaves MERGE_HEAD with no abort hint
l-errors-r4 | in | _say_done (gate.py:1490-1525) reports an unreadable or owed Definition of Done but run() still returns GateResult(True), so `fr ops gate` exits 0
l-errors-r5 | in | _existing_pass (gate.py:1541) catches only OpsLoadError; AcceptanceError/SectionError/SettingsError from run_exit/gated_rows escape as a traceback in stage 6
l-errors-r6 | in | gate_cmd._refuse_on_blockers (gate_cmd.py:134-149) does not catch SettingsError, which the new gated_rows -> disabled() call can raise: traceback instead of an exit-2 refusal
l-errors-r7 | in | closeout_cmd._head_walks (closeout_cmd.py:333) treats any failed `git show`, including an unknown --pr-head sha, as an absent fragment: an empty exclusion, against its docstring's refusal promise
l-errors-r8 | in | closeout_cmd._shape_default (closeout_cmd.py:351) silently drops an unreadable cursor for an explicit --run, so the row's walk strategy changes or is refused with no signal
l-errors-r9 | in | head_manual_ticks (gate.py:1464-1474) calls .get()/int() on PR-controlled YAML; a malformed phase raises AttributeError/ValueError that _say_done does not catch (traceback on the final line)
l-errors-r10 | in | closeout outcome calls close_commands (closeout_cmd.py:222) before the not-committed warning (closeout_cmd.py:224); an AcceptanceError there tracebacks after the write and hides that warning
```

```review-lens
lens: tests
examined: packages/fr/src/fr/ops/refresh.py, packages/fr/src/fr/ops/gate.py, packages/fr/src/fr/ops/holds.py, packages/fr/src/fr/acceptance/walks.py, packages/fr/src/fr/commands/closeout_cmd.py, packages/fr/src/fr/commands/gate_cmd.py, packages/fr/src/fr/commands/ops_gate_cmd.py, packages/fr/src/fr/spec.py, packages/fr/src/fr/run/dod.py, tests/unit/test_ops_gate.py, tests/unit/test_ops_refresh.py, tests/unit/test_ops_gate_cmd.py, tests/unit/test_closeout_outcome.py, tests/unit/test_ops_holds_gate_items.py, tests/unit/test_ops_gate_pass.py, tests/unit/test_run_dod.py, tests/unit/test_dod_cmd.py, tests/unit/test_acceptance_walks.py, tests/unit/test_ops_testplan.py
```
```review-findings
l-tests-r1 | in | R4 test is tautological: apply_phase already calls gate.trust (gate.py:681), so removing refresh's re-trust (refresh.py:204) keeps test_ops_gate.py:1606 green; R4 unpinned at stages 5-7
l-tests-r2 | in | stage 6's _existing_pass judges the pre-refresh label with devops_blockers without head walk/outcome exclusion (gate.py:1385,1540), contradicting R12 and the shape's trust boundary; existing-pass tests use only op blockers
l-tests-r3 | in | gate_items op items count plan-journal op entries the PR head carries (holds.py:146); stage 6 _owed_items and the R20 DoD never exclude them, unlike _unclosed/apply_phase; shape trust boundary contradicted, untested
l-tests-r4 | in | drift loads ops with runbook needs from a scratch tree that holds only _head_paths (gate.py:717, refresh.py:159); a runbook outside spec/plan/fragments/.fr fails stages 4-7 every run; no runbook test
l-tests-r5 | in | closeout_cmd._head_walks silently returns an empty exclusion when git show fails for a valid-looking sha (closeout_cmd.py:333) despite its "refuses" docstring; no negative test
l-tests-r6 | in | FakeTree._walk_named_rows (test_ops_gate.py:164) diverges from real closeout outcome: fixed strategy live, any-passing not latest-per-harness, ignores --pr-head, edits rows not amendments
l-tests-r7 | in | untested: R13 ran on a multi-harness row keeping status in _ask_rows; R3 records-commit-before-abort and post-conflict host state; R3 lease value (FakeTree.head constant); R14 unreadable setting
```

```review-lens
lens: docs-accuracy
examined: docs/ops.md, docs/explainers/fr-devops-gate.md, docs/explainers/fr-exit-gates.md, docs/explainers/fr-acceptance.md, docs/explainers/fr-brainstorming-and-plan.md, docs/explainers/fr-triage.md, docs/explainers/index.md, docs/gate-backfill.md, docs/reference/acceptance-matrix.md, docs/reference/cli.md, docs/reference/workflow-shapes.md, plugins/super-fr/skills/fr-devops-gate/SKILL.md, plugins/super-fr/skills/fr-plan/SKILL.md, packages/fr/src/fr/ops/gate.py, packages/fr/src/fr/ops/refresh.py, packages/fr/src/fr/ops/holds.py, packages/fr/src/fr/run/dod.py, packages/fr/src/fr/commands/dod_cmd.py, packages/fr/src/fr/run/closeout.py, packages/fr/src/fr/commands/closeout_cmd.py, packages/fr/src/fr/commands/gate_cmd.py, packages/fr/src/fr/acceptance/walks.py, packages/fr/src/fr/spec.py, packages/fr/src/fr/plan_review/checks.py, packages/fr/src/fr/triage/ledger.py, packages/fr/src/fr/commands/ops_gate_cmd.py, packages/fr/src/fr/commands/acceptance_cmd.py, packages/fr/src/fr/cli.py
```
```review-findings
l-docs-accuracy-r1 | in | stage 6's _existing_pass (gate.py:1532-1549) judges blockers with devops_blockers, not head-free, so PR-head outcomes or a head-written `walked` status can let a pre-refresh gate:devops-passed stand; contradicts fr-devops-gate.md:186-189 and the shape's trust boundary
l-docs-accuracy-r2 | in | _recovery (gate.py:1552-1580) picks open steps without head exclusion, so a step closed only by a PR-head outcome gets no `closeout outcome` command while stage 6 still refuses on it; contradicts ops.md:254 and fr-devops-gate.md:194 ("commands that close each item")
l-docs-accuracy-r3 | in | ops.md:316-329 orders the refresh as commit, merge, push, reopen, and says a conflict leaves the workspace at the records commit, but refresh.py:181-190 reopens the ops and forgets stages before the merge, so a conflict leaves them reopened and forgotten
l-docs-accuracy-r4 | in | fr-devops-gate SKILL.md:82-83 drops where `fr ops attest` runs (fr isolation exec on chore/ops-<slug>), its --plan (required for a runbook op, ops_cmd.py:451) and "an op with a check cannot be attested"; worse guidance than the text it replaced
l-docs-accuracy-r5 | in | fr-devops-gate SKILL.md:114 says a hand-run `fr gate pass` "judges the merged tree"; gate_cmd reads the current checkout, as ops.md says ("as the checkout holds them")
l-docs-accuracy-r6 | out | the new "merge, never rebase, because the ops branch is already pushed; a rebase would rewrite your evidence" rationale (fr-devops-gate.md:109-111, ops.md:325-326) sits beside stage 3, which still rebases that pushed ops branch with a lease
```

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: _existing_pass (gate.py:1532-1540, reached from stage 6 at :1384 when gate:devops-passed is on the PR) judges with devops_blockers with no head exclusions, so PR-head walks/outcomes discharge the gate after a refresh and stage 6 is marked done, against R6/R12 and the shape's "stage 6 refuses while head-free blockers remain"

Fixed in cef624685 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: content the refresh merges in from the default branch still discharges items: only the pinned head's walks/outcomes/ticks are excluded and merged-in plan-journal entries only for reopened ops (refresh.py:102,198), contradicting the shape's "merged-in entries never count" (shape.md:8) and the lens's "merged-in content must not discharge anything"

Fixed in b8bad7344: the shape claimed merged-in entries never count, which overstated R6. The spec (R6) limits the exclusion to entries that would close a REOPENED op; other default-branch content is reviewed, merged evidence and is meant to count. The shape now states exactly that, so the diff and its shape agree; no code change was needed.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-security-r3 -->
### l-security-r3-resolved · finding [fixed] · resolves l-security-r3: gate_items judges ops by the latest plan-journal entry with no PR-head exclusion (holds.py:140-144), so stage 6's "head excluded" refusal and R20's DoD line count head-carried op closures; only stage 4 running first protects this

Fixed in cef624685 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-security-r4-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-security-r4 -->
### l-security-r4-resolved · finding [fixed] · resolves l-security-r4: head_walks (gate.py:1257) and closeout _head_walks (closeout_cmd.py:328) read only fragment names present in the ops workspace, so walks in a head fragment the workspace lacks (renamed/moved) are never excluded; list the head's tree instead

Fixed in cef624685 and 61cc2aeb2 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-security-r5-resolved created=2026-11-28T09:12:02+00:00 state=open resolves=l-security-r5 out_of_scope=true -->
### l-security-r5-resolved · finding [out-of-scope] · resolves l-security-r5: under quiet/stealth head_walks skips every fragment (gate.py:1258) as journal exclusions already do: walks/outcomes the feature run wrote to the fr artifact branch before merge are never excluded, so the PR-controlled boundary holds only under repo placement

Out of scope: under quiet/stealth placement journal exclusions already skipped artifact-branch content before this change; head_walks follows the same existing placement rule. Closing it needs a placement-aware definition of PR-controlled content, a separate design question.

<!-- fr:journal kind=finding scope=plan id=l-security-r6-resolved created=2026-11-28T09:12:02+00:00 state=open resolves=l-security-r6 out_of_scope=true -->
### l-security-r6-resolved · finding [out-of-scope] · resolves l-security-r6: _passed (gate.py:1698-1706) still treats a bare gate:devops-passed label as stage 6 done without any blocker check when no refresh reopened or forgot stage 6, so a hand-added label skips the head-free check

Out of scope: _passed treating a bare gate:devops-passed label as stage 6 done predates this change (the reviewer says so); this change adds the head-free check on the paths it touches and does not alter how a hand-set label is trusted.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: refresh.py:152 relies on HostCheckout.fetch, which swallows a failed default-branch fetch as a warning, so drift compares against a stale origin/<default> and can read "equal" (fail-open on R1)

Fixed in 62bb2fdd7 and 08f3a40e1 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: GitError from materialise (refresh.py:159), is_ancestor (refresh.py:166, ops_gate_cmd.py:75-82) and a non-UTF-8 head fragment in head_walks (gate.py:1261) escapes run() as a traceback, never a StageFailed

Fixed in cef624685 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: after a conflict merged by hand (or a failed merge commit, ops_gate_cmd.py:100), reopened.before never gains the merged-in entry ids (refresh.py:198 skipped), so default-branch entries close reopened ops against R6; the commit-failure path also leaves MERGE_HEAD with no abort hint

Fixed in 62bb2fdd7 and 08f3a40e1 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: _say_done (gate.py:1490-1525) reports an unreadable or owed Definition of Done but run() still returns GateResult(True), so `fr ops gate` exits 0

Fixed in cef624685 and 08f3a40e1 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r5 -->
### l-errors-r5-resolved · finding [fixed] · resolves l-errors-r5: _existing_pass (gate.py:1541) catches only OpsLoadError; AcceptanceError/SectionError/SettingsError from run_exit/gated_rows escape as a traceback in stage 6

Fixed in cef624685 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r6 -->
### l-errors-r6-resolved · finding [fixed] · resolves l-errors-r6: gate_cmd._refuse_on_blockers (gate_cmd.py:134-149) does not catch SettingsError, which the new gated_rows -> disabled() call can raise: traceback instead of an exit-2 refusal

Fixed in 61cc2aeb2 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-errors-r7-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r7 -->
### l-errors-r7-resolved · finding [fixed] · resolves l-errors-r7: closeout_cmd._head_walks (closeout_cmd.py:333) treats any failed `git show`, including an unknown --pr-head sha, as an absent fragment: an empty exclusion, against its docstring's refusal promise

Fixed in 61cc2aeb2 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-errors-r8-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r8 -->
### l-errors-r8-resolved · finding [fixed] · resolves l-errors-r8: closeout_cmd._shape_default (closeout_cmd.py:351) silently drops an unreadable cursor for an explicit --run, so the row's walk strategy changes or is refused with no signal

Fixed in 61cc2aeb2 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-errors-r9-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r9 -->
### l-errors-r9-resolved · finding [fixed] · resolves l-errors-r9: head_manual_ticks (gate.py:1464-1474) calls .get()/int() on PR-controlled YAML; a malformed phase raises AttributeError/ValueError that _say_done does not catch (traceback on the final line)

Fixed in cef624685 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-errors-r10-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-errors-r10 -->
### l-errors-r10-resolved · finding [fixed] · resolves l-errors-r10: closeout outcome calls close_commands (closeout_cmd.py:222) before the not-committed warning (closeout_cmd.py:224); an AcceptanceError there tracebacks after the write and hides that warning

Fixed in 61cc2aeb2 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: R4 test is tautological: apply_phase already calls gate.trust (gate.py:681), so removing refresh's re-trust (refresh.py:204) keeps test_ops_gate.py:1606 green; R4 unpinned at stages 5-7

Fixed in 62bb2fdd7 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: stage 6's _existing_pass judges the pre-refresh label with devops_blockers without head walk/outcome exclusion (gate.py:1385,1540), contradicting R12 and the shape's trust boundary; existing-pass tests use only op blockers

Fixed in cef624685 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: gate_items op items count plan-journal op entries the PR head carries (holds.py:146); stage 6 _owed_items and the R20 DoD never exclude them, unlike _unclosed/apply_phase; shape trust boundary contradicted, untested

Fixed in cef624685 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: drift loads ops with runbook needs from a scratch tree that holds only _head_paths (gate.py:717, refresh.py:159); a runbook outside spec/plan/fragments/.fr fails stages 4-7 every run; no runbook test

Fixed in bc0d2f008 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: closeout_cmd._head_walks silently returns an empty exclusion when git show fails for a valid-looking sha (closeout_cmd.py:333) despite its "refuses" docstring; no negative test

Fixed in 61cc2aeb2 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-tests-r6 -->
### l-tests-r6-resolved · finding [fixed] · resolves l-tests-r6: FakeTree._walk_named_rows (test_ops_gate.py:164) diverges from real closeout outcome: fixed strategy live, any-passing not latest-per-harness, ignores --pr-head, edits rows not amendments

Fixed in c0dfb331a (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-tests-r7-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-tests-r7 -->
### l-tests-r7-resolved · finding [fixed] · resolves l-tests-r7: untested: R13 ran on a multi-harness row keeping status in _ask_rows; R3 records-commit-before-abort and post-conflict host state; R3 lease value (FakeTree.head constant); R14 unreadable setting

Fixed in 62bb2fdd7 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: stage 6's _existing_pass (gate.py:1532-1549) judges blockers with devops_blockers, not head-free, so PR-head outcomes or a head-written `walked` status can let a pre-refresh gate:devops-passed stand; contradicts fr-devops-gate.md:186-189 and the shape's trust boundary

Fixed in cef624685 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: _recovery (gate.py:1552-1580) picks open steps without head exclusion, so a step closed only by a PR-head outcome gets no `closeout outcome` command while stage 6 still refuses on it; contradicts ops.md:254 and fr-devops-gate.md:194 ("commands that close each item")

Fixed in cef624685 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: ops.md:316-329 orders the refresh as commit, merge, push, reopen, and says a conflict leaves the workspace at the records commit, but refresh.py:181-190 reopens the ops and forgets stages before the merge, so a conflict leaves them reopened and forgotten

Fixed in 08f3a40e1 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-docs-accuracy-r4 -->
### l-docs-accuracy-r4-resolved · finding [fixed] · resolves l-docs-accuracy-r4: fr-devops-gate SKILL.md:82-83 drops where `fr ops attest` runs (fr isolation exec on chore/ops-<slug>), its --plan (required for a runbook op, ops_cmd.py:451) and "an op with a check cannot be attested"; worse guidance than the text it replaced

Fixed in 08f3a40e1 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5-resolved created=2026-11-28T09:12:02+00:00 state=fixed resolves=l-docs-accuracy-r5 -->
### l-docs-accuracy-r5-resolved · finding [fixed] · resolves l-docs-accuracy-r5: fr-devops-gate SKILL.md:114 says a hand-run `fr gate pass` "judges the merged tree"; gate_cmd reads the current checkout, as ops.md says ("as the checkout holds them")

Fixed in 08f3a40e1 (commit subject cites this id), with a test per the lens fix list.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r6-resolved created=2026-11-28T09:12:02+00:00 state=open resolves=l-docs-accuracy-r6 out_of_scope=true -->
### l-docs-accuracy-r6-resolved · finding [out-of-scope] · resolves l-docs-accuracy-r6: the new "merge, never rebase, because the ops branch is already pushed; a rebase would rewrite your evidence" rationale (fr-devops-gate.md:109-111, ops.md:325-326) sits beside stage 3, which still rebases that pushed ops branch with a lease

Out of scope: stage 3's rebase-with-lease of the ops branch predates this change, and the new merge-never-rebase rationale is about the stage 4-7 refresh; the reviewer notes the claim is not false.

<!-- fr:journal kind=finding scope=plan id=p2-r10-resolved-2 created=2026-11-28T13:22:34+00:00 phase=2 state=open resolves=p2-r10 tracked_by=https://github.com/derio-net/super-fr/issues/1776 -->
### p2-r10-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1776] · resolves p2-r10: The triage driver's rows-walked tester pass bypasses gate_blockers (phase 2)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1776.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved-2 created=2026-11-28T13:22:34+00:00 phase=3 state=open resolves=p3-r4 tracked_by=https://github.com/derio-net/super-fr/issues/1777 -->
### p3-r4-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1777] · resolves p3-r4: _say_done catches only DodError and StageFailed (phase 3)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1777.

<!-- fr:journal kind=finding scope=plan id=l-security-r5-resolved-2 created=2026-11-28T13:22:34+00:00 state=open resolves=l-security-r5 tracked_by=https://github.com/derio-net/super-fr/issues/1778 -->
### l-security-r5-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1778] · resolves l-security-r5: under quiet/stealth head_walks skips every fragment (gate.py:1258) as journal exclusions already do: walks/outcomes the feature run wrote to the fr artifact branch before merge are never excluded, so the PR-controlled boundary holds only under repo placement

Filed at deliver as https://github.com/derio-net/super-fr/issues/1778.

<!-- fr:journal kind=finding scope=plan id=l-security-r6-resolved-2 created=2026-11-28T13:22:34+00:00 state=open resolves=l-security-r6 tracked_by=https://github.com/derio-net/super-fr/issues/1779 -->
### l-security-r6-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1779] · resolves l-security-r6: _passed (gate.py:1698-1706) still treats a bare gate:devops-passed label as stage 6 done without any blocker check when no refresh reopened or forgot stage 6, so a hand-added label skips the head-free check

Filed at deliver as https://github.com/derio-net/super-fr/issues/1779.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r6-resolved-2 created=2026-11-28T13:22:34+00:00 state=open resolves=l-docs-accuracy-r6 tracked_by=https://github.com/derio-net/super-fr/issues/1780 -->
### l-docs-accuracy-r6-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1780] · resolves l-docs-accuracy-r6: the new "merge, never rebase, because the ops branch is already pushed; a rebase would rewrite your evidence" rationale (fr-devops-gate.md:109-111, ops.md:325-326) sits beside stage 3, which still rebases that pushed ops branch with a lease

Filed at deliver as https://github.com/derio-net/super-fr/issues/1780.
