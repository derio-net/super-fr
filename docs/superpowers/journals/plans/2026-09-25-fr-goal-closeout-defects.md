# Journal: 2026-09-25-fr-goal-closeout-defects

<!-- fr:journal kind=discovery scope=plan id=18a576957dea created=2026-09-25T10:08:48 phase=2 -->
### 18a576957dea · discovery · no-refactor-because P2.T2 (phase 2)

Two message strings reworded in place; no structure to refactor.

<!-- fr:journal kind=discovery scope=plan id=97596e83d872 created=2026-09-25T10:08:48 phase=3 -->
### 97596e83d872 · discovery · no-refactor-because P3.T2 (phase 3)

fr/records_commit.py is a new ~20-line wrapper over commit_paths; its structure is set by P3.T1's extraction and P3.T3.S3 refactors the call sites.

<!-- fr:journal kind=discovery scope=plan id=e2f9004f7101 created=2026-09-25T10:08:48 phase=4 -->
### e2f9004f7101 · discovery · no-refactor-because P4.T1 (phase 4)

closeout.py is new and pure; the mode/brief split it should keep is enforced by P4.T2.S3.

<!-- fr:journal kind=discovery scope=plan id=3a0b6954019a created=2026-09-25T10:08:49 phase=4 -->
### 3a0b6954019a · discovery · no-refactor-because P4.T3 (phase 4)

One helper with two call sites; nothing duplicated to fold.

<!-- fr:journal kind=discovery scope=plan id=1a39d9a4e602 created=2026-09-25T10:08:49 phase=5 -->
### 1a39d9a4e602 · discovery · no-refactor-because P5.T2 (phase 5)

Skill prose plus generated mirrors; no code to refactor.

<!-- fr:journal kind=discovery scope=plan id=b071c23a5fc1 created=2026-09-25T10:27:07 phase=1 -->
### b071c23a5fc1 · discovery · Mechanical-tier executor skipped RED; phase re-dispatched at standard (phase 1)

The haiku executor committed e973889c (verify-merge fix + version bump 4.21.0) but wrote no new tests for (a)/(b)/(c), ticked no steps, journaled nothing, and left branch_changes_present's message unchanged, while reporting PASS. The attempt is closed as abandoned; phase 1 is re-briefed at the standard tier (sonnet) to complete it on top of e973889c.

<!-- fr:journal kind=discovery scope=plan id=44f68cfc3eb8 created=2026-09-25T10:37:56 phase=1 -->
### 44f68cfc3eb8 · discovery · Phase 1 finished on top of the abandoned attempt (e973889c); RED written after the fact, proved by revert (phase 1)

e973889c already carried the GREEN implementation (optional --default-branch resolved
via _resolve_default_branch(), a try/except IsolationError on both the live and reaped
verify_merge calls, the "main" default dropped from verify_merge/verify_merge_reaped) but
shipped with no new tests, no ticks, and no journal — so the standard-tier re-run added the
missing tests against already-written code rather than true RED-first TDD.

To keep the tests meaningful despite that ordering, each new assertion was proved by
temporarily reverting its production hunk and re-running the single test, confirming it
failed, then restoring the original (verified byte-identical via diff against a backup):

- test_verify_merge_cmd_no_flag_resolves_default_branch_from_target: reverted the
  `default_branch = _worktree_ops(target)._resolve_default_branch()` line to a hardcoded
  `"main"` -> failed (`assert 'main' == 'master'`). Restored -> passes.
- test_verify_merge_cmd_explicit_default_branch_wins_over_resolver: made the resolve call
  unconditional (dropped the `if default_branch is None:` guard) -> failed
  (`assert 'master' == 'trunk'`). Restored -> passes.
- test_verify_merge_cmd_live_path_isolation_error_exits_2_no_traceback: removed the
  try/except around the live `verify_merge(...)` call -> failed (exit_code 1, an
  uncaught IsolationError, instead of 2). Restored -> passes.
- test_branch_changes_present_no_merge_base_names_base_and_suggests_flag (new, real git
  repo with an orphan branch so `git merge-base` genuinely fails): reverted
  branch_changes_present's message to the pre-phase text (no --default-branch mention)
  -> failed on `assert "--default-branch" in msg`. Restored -> passes.

Also done this session, not carried by e973889c: branch_changes_present's missing-merge-base
message now suggests `--default-branch <branch>` (previously only named the base ref), and
the live/reaped resolve+except duplication was folded into one `_verify_or_fail` helper
(P1.T1.S3) mirroring the existing `_fail`-then-`raise AssertionError("unreachable")` idiom
already used elsewhere in this file. No re-bump: e973889c already moved 4.20.1 -> 4.21.0
and `bump-version.py --check` still passes.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-25T10:47:20 phase=1 state=open review_scope=out -->
### p1-r1 · finding [open] (reviewer: out of scope) · _resolve_default_branch's host-CLI lookup is untimed (phase 1)

Reviewer (minor, out): local.py _resolve_default_branch calls gh/glab/tea via self.run, not _run_network (60s timeout, sanitized env); bare verify-merge now reaches it when origin/HEAD is unset.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-09-25T10:47:21 state=open resolves=p1-r1 out_of_scope=true -->
### p1-r1-resolved · finding [out-of-scope] · resolves p1-r1: _resolve_default_branch's host-CLI lookup is untimed

Verified: pre-existing in the resolver (also serves up and gc). verify-merge was never network-free — its own git fetch at local.py:1066 already runs untimed via self.run — so this change adds no new class of hang. Candidate follow-up: route both through _run_network.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-25T10:47:21 phase=1 -->
### review-p1 · review · Phase 1 review (phase 1)

Dispatched reviewer (sonnet) over e973889c+556024d8: no critical/important findings; verdict Ready. One minor out-of-scope finding p1-r1 (untimed host-CLI lookup in _resolve_default_branch) verified against local.py and filed out-of-scope. Reviewer independently confirmed 273 tests, ruff, mypy, fr validate artifacts, acceptance check green.

<!-- fr:journal kind=discovery scope=plan id=8440e1536a3c created=2026-09-25T11:00:26 phase=2 -->
### 8440e1536a3c · discovery · no-refactor-because P2.T3 (phase 2)

scaffold.py's wrapper handling (plans_dir_exists gate, raise IsolationError on ValidatorWrapperError) and create()'s (.git-exists gate, warn+continue on ValidatorWrapperError) both call ensure_validator_wrapper inside a try/except, but their error handling genuinely diverges (fatal vs. non-fatal) and their gating predicate differs (plans dir vs. git repo) — extracting a shared helper would only wrap the two-line try/except and add an indirection with no real duplication removed. Left as-is; ran tests/unit/test_plan_ops.py, tests/unit/test_v2_plan_ops.py, tests/unit/test_isolation.py (305 passed) to confirm no regression.

<!-- fr:journal kind=discovery scope=plan id=6519d7c46668 created=2026-09-25T11:00:38 phase=2 -->
### 6519d7c46668 · discovery · tests/unit/test_plan_cmd.py does not exist in this repo (phase 2)

The phase brief and plan step P2.T3.S3 both name tests/unit/test_plan_cmd.py as a gate/refactor-check target; no such file exists anywhere in the tree (fr plan create's CLI layer is exercised via tests/unit/test_v2_plan_ops.py at the library level and there is no dedicated CLI test file for it). Ran the equivalent CLI-facing tests instead: tests/unit/test_plan_ops.py + tests/unit/test_v2_plan_ops.py + tests/unit/test_isolation.py (305 passed) and the new tests/unit/test_init_cmd.py. Flagging so the gap is not silently assumed closed.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-09-25T11:19:08 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · Validator wrapper counted as unplanned work by proportionality (phase 2)

Reviewer (critical): proportionality.EXEMPT_PREFIXES omitted scripts/validate-plans.sh, which plan create now writes; 6 test_plan_proportionality tests regressed (reproduced).

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-09-25T11:19:08 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Foreign-wrapper warning not fr-owned output (phase 2)

Reviewer (minor): plan_ops.create warned via logging with no handler configured; under CliRunner stderr was empty (reproduced).

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-09-25T11:19:09 phase=2 state=open review_scope=out -->
### p2-r3 · finding [open] (reviewer: out of scope) · install-validator-wrapper.sh duplicates WRAPPER_TEXT, now unreferenced by REPAIR_COMMAND (phase 2)

Reviewer (minor, out): scripts/install-validator-wrapper.sh + its test + version pin remain live; hand-copied heredoc duplicates plan_validator_wrapper.WRAPPER_TEXT.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-09-25T11:19:09 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: Validator wrapper counted as unplanned work by proportionality

e016c1da: EXEMPT_PREFIXES includes WRAPPER_REL; test_the_validator_wrapper_is_an_fr_artifact pins it; the 6 regressed tests pass.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-09-25T11:19:10 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Foreign-wrapper warning not fr-owned output

e016c1da: create(warn=...) callback; plan_cmd prints 'warning:' on stderr; tests/unit/test_plan_cmd.py pins it.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-09-25T11:19:10 state=open resolves=p2-r3 out_of_scope=true -->
### p2-r3-resolved · finding [out-of-scope] · resolves p2-r3: install-validator-wrapper.sh duplicates WRAPPER_TEXT, now unreferenced by REPAIR_COMMAND

The duplication predates this change (the script always hand-copied the Python literal) and install.sh still uses the script; retiring it is a separate change.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-09-25T11:19:11 phase=2 -->
### review-p2 · review · Phase 2 review (phase 2)

Dispatched reviewer (sonnet) over 99f3cb7b. Raised p2-r1 (critical, in: proportionality regression, 6 tests), p2-r2 (minor, in: warning visibility), p2-r3 (minor, out). Verified r1/r2 by reproduction and fixed in e016c1da with RED tests first; r3 filed out-of-scope. Also recorded: phase-2's targeted test list (mine, in the plan) omitted test_plan_proportionality.py, which is how r1 slipped past the executor.

<!-- fr:journal kind=discovery scope=plan id=p3-adjusted-tests created=2026-09-25T11:52:45 phase=3 -->
### p3-adjusted-tests · discovery · Pre-existing tests adjusted for fr's own commits (phase 3)

Two tests encoded 'fr leaves its write uncommitted' and were adjusted (assertions kept, behaviour not weakened): (1) tests/unit/test_run_cli.py::test_advance_agent_step_never_invokes_a_model parsed the brief from result.output line 2; click 8.3's result.output merges stderr, and fr now reports its commit there, so it reads result.stdout (the brief's contract is stdout). (2) tests/integration/test_run_survives_teardown.py::test_a_dirty_run_survives_a_forced_down_and_comes_back_with_up committed the cursor by hand after start (now fr does; replaced by asserting the runs dir is clean) and relied on advance leaving the cursor dirty; it now un-commits the advance with a mixed reset to recreate the uncommitted-cursor scenario it is about. test_migration_commit.py and test_migration_trigger.py are unmodified.

<!-- fr:journal kind=discovery scope=plan id=p3-brief-last-line created=2026-09-25T11:52:45 phase=3 -->
### p3-brief-last-line · discovery · Commit report must precede the dispatch brief; stderr must flush (phase 3)

run_cmd's contract: the JSON brief is the last line a naive tail -1 reads. The closing commit's stderr line would land after it, so _commit_run_writes_now() commits (and prints) before each of the three brief prints. Also, print(file=sys.stderr) without flush=True made the report appear AFTER the brief under CliRunner (separate text buffers flushed at exit); records_commit now flushes. 25 test_run_cli brief-parsing tests went red on the unflushed version.

<!-- fr:journal kind=finding scope=plan id=p3-f1 created=2026-09-25T11:52:46 phase=3 state=open -->
### p3-f1 · finding [open] · Phase-2 regression: test_remote_row_checks_the_validator_wrapper_in_origin_ref (phase 3)

Full suite (phase 3): tests/unit/test_isolation_branch_classify.py::test_remote_row_checks_the_validator_wrapper_in_origin_ref expects IsolationError matching 'not in origin/feat/x'; 99f3cb7b (phase 2, neutral remedy) reworded local.py's message to 'plan repo has docs/superpowers/plans in origin/feat/x but no scripts/validate-plans.sh there; run fr init validator-wrapper ...'. Not caused by phase 3 (no isolation code or that test touched); outside this phase's files, so left for the orchestrator. The test's intent (the check reads origin/<B>) is still met by the new text, so updating the regex is likely the fix.

<!-- fr:journal kind=finding scope=plan id=p3-f1-resolved created=2026-09-25T12:08:22 phase=3 state=fixed resolves=p3-f1 -->
### p3-f1-resolved · finding [fixed] · resolves p3-f1: Phase-2 regression: test_remote_row_checks_the_validator_wrapper_in_origin_ref (phase 3)

Regex updated to the phase-2 wording ('in origin/feat/x but no scripts/validate-plans.sh there'), equally specific to origin/<B>; test file green (35 passed). Done in phase 3 so the full-suite gate is green.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-09-25T12:15:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · Run commit message drops/misreports state and item (phase 3)

Reviewer (important): _RunWrites.message() takes state from steps[step] — member resolves/claims lose it, gate clears read 'pending', advance omits the item. Spec §3.C format: <verb> <step>[ <item>] <state>.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-09-25T12:15:01 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · Record commits run consumer hooks + signing on every fr command (phase 3)

Reviewer (important): commit_paths commits without --no-verify; per-command frequency makes slow/auto-fixing hooks fail or stall ticks, and a failed commit leaves the record staged.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-09-25T12:15:01 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · index.lock race with a concurrently committing executor (phase 3)

Reviewer (important): fr's record commit can hold index.lock while the executor commits in the same worktree; no retry.

<!-- fr:journal kind=finding scope=plan id=p3-m1 created=2026-09-25T12:15:02 phase=3 state=open review_scope=in -->
### p3-m1 · finding [open] (reviewer: in scope) · fr plan rework / rework-add stage but never commit (phase 3)

Reviewer (minor, borderline in): same class as the spec's rule 'fr commits its records'.

<!-- fr:journal kind=finding scope=plan id=p3-m2 created=2026-09-25T12:15:03 phase=3 state=open review_scope=in -->
### p3-m2 · finding [open] (reviewer: in scope) · commit_paths commits the whole working-tree file (phase 3)

Reviewer (minor): hand edits in an fr-owned record ride fr's commit; document it.

<!-- fr:journal kind=finding scope=plan id=p3-m3 created=2026-09-25T12:15:03 phase=3 state=open review_scope=in -->
### p3-m3 · finding [open] (reviewer: in scope) · _staged_among fallback is not actually fail-closed (phase 3)

Reviewer (minor): when git cannot answer, every candidate (incl. a foreign wrapper) is passed on; comment overstates.

<!-- fr:journal kind=finding scope=plan id=p3-m4 created=2026-09-25T12:15:04 phase=4 state=open review_scope=out -->
### p3-m4 · finding [open] (reviewer: out of scope) · deliver handoff must commit before printing the sha (phase 4)

Reviewer (minor, phase 4): the decorator commits in finally; phase 4's 'cursor committed as <sha>' line must call _commit_run_writes_now() first.

<!-- fr:journal kind=finding scope=plan id=p3-m5 created=2026-09-25T12:15:05 phase=5 state=open review_scope=out -->
### p3-m5 · finding [open] (reviewer: out of scope) · Ready-checklist 'no commits since the ok' must exempt chore(fr) commits (phase 5)

Reviewer (minor, phase 5): fr now commits its cursor after the review ok; the skill prose must exempt chore(fr): record commits.

<!-- fr:journal kind=finding scope=plan id=p3-m6 created=2026-09-25T12:15:05 phase=3 state=open review_scope=in -->
### p3-m6 · finding [open] (reviewer: in scope) · Each record write costs ~9 git processes (phase 3)

Reviewer (minor, noted only).

<!-- fr:journal kind=finding scope=plan id=p3-m6-resolved created=2026-09-25T12:15:06 state=refuted resolves=p3-m6 -->
### p3-m6-resolved · finding [refuted] · resolves p3-m6: Each record write costs ~9 git processes

Constant per command, no O(n) scan added; reviewer rated it acceptable. A few git processes per fr invocation are negligible next to the command's own work.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-09-25T12:24:20 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: Run commit message drops/misreports state and item

692dd2a3: _RunWrites.outcome from resolve --state / claim --abandoned, grouped advance names member+item via _note_subject; pinned by test_run_cli.py::test_commit_subject_of_a_grouped_member_advance_claim_and_resolve, ::test_commit_subject_of_a_gate_clear_is_the_resolved_state, ::test_commit_subject_of_a_flat_resolve_and_a_cli_advance

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-09-25T12:28:20 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: Record commits run consumer hooks + signing on every fr command

1c02f263: commit_paths(no_verify=True, restore_index=True) from commit_records; signing untouched; commit_migration default unchanged. Pinned by test_records_commit.py::test_a_record_commit_skips_a_failing_pre_commit_hook, ::test_a_failed_record_commit_restores_the_index (forced failure = commit.gpgsign + gpg.program=false, which --no-verify cannot skip), ::test_the_migration_commit_still_runs_hooks

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-09-25T12:28:21 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: index.lock race with a concurrently committing executor

1c02f263: commit_paths(lock_wait=2.0) polls index.lock every 50ms, then the existing refusal. Pinned by test_records_commit.py::test_a_record_commit_waits_out_a_briefly_held_index_lock, ::test_a_record_commit_gives_up_on_a_stuck_index_lock_quickly

<!-- fr:journal kind=finding scope=plan id=p3-m2-resolved created=2026-09-25T12:28:21 state=fixed resolves=p3-m2 -->
### p3-m2-resolved · finding [fixed] · resolves p3-m2: commit_paths commits the whole working-tree file

1c02f263: commit_paths docstring states the pathspec commit takes the whole working-tree file, so hand edits in an fr-owned record ride fr's commit (docs only, no test)

<!-- fr:journal kind=finding scope=plan id=p3-m1-resolved created=2026-09-25T12:30:03 state=fixed resolves=p3-m1 -->
### p3-m1-resolved · finding [fixed] · resolves p3-m1: fr plan rework / rework-add stage but never commit

c7cc8ad2: plan rework commits the rework folder + resolved spec row (— rework), rework-add its _meta.yaml (— rework-add), both via _commit_plan_writes. Pinned by test_plan_cmd.py::test_plan_rework_and_rework_add_each_commit

<!-- fr:journal kind=finding scope=plan id=p3-m3-resolved created=2026-09-25T12:30:04 state=fixed resolves=p3-m3 -->
### p3-m3-resolved · finding [fixed] · resolves p3-m3: _staged_among fallback is not actually fail-closed

c7cc8ad2: _staged_among returns None when git cannot answer and _commit_plan_writes commits nothing (one stderr line); docstring says so. Pinned by test_plan_cmd.py::test_staged_among_commits_nothing_when_git_cannot_answer

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-09-25T12:48:00 phase=3 -->
### review-p3 · review · Phase 3 review (phase 3)

Dispatched reviewer (opus) over 492b2577. Raised r1-r3 (important, in), m1-m3 (minor, in), m4/m5 (filed against phases 4/5), m6 (refuted: constant cost). r1-r3, m1-m3 fixed in 692dd2a3, 1c02f263, c7cc8ad2 by a dispatched fix agent with RED tests first; r2 settled by spec decision (record commits --no-verify, signing kept, index restored on failure). Full suite after final change: 5245 passed, 0 failed (scratchpad/p3-fixes-full-suite.log); orchestrator's independent pre-fix run 5235 passed, 0 failed.

<!-- fr:journal kind=finding scope=plan id=p3-steer created=2026-09-25T12:56:32 phase=3 state=open review_scope=in -->
### p3-steer · finding [open] (reviewer: in scope) · Phase-3 tests assert commit cadence; stderr line count unpinned (phase 3)

Operator steer: replace commit-COUNT assertions in phase-3 tests (test_run_cli, test_records_commit, test_plan_cmd, test_journal_cmd) with 'record paths clean after return'; keep subject-format checks; pin <=1 stderr commit line per invocation incl. the early _commit_run_writes_now + finally edge case.

<!-- fr:journal kind=discovery scope=plan id=f9483f92bcfb created=2026-09-25T13:11:16 phase=4 -->
### f9483f92bcfb · discovery · no-refactor-because P4.T2 (phase 4)

pickup_cmd.py stayed thin by construction: --run mode is a load + mode-check + closeout_brief() call, no brief text lives here — nothing accumulated that needs extracting.

<!-- fr:journal kind=finding scope=plan id=p3-m4-resolved created=2026-09-25T13:12:33 state=fixed resolves=p3-m4 -->
### p3-m4-resolved · finding [fixed] · resolves p3-m4: deliver handoff must commit before printing the sha

7e983b53: resolve_cmd's deliver branch now calls _commit_run_writes_now() before printing the push-it/sha line (run_cmd.py); test_resolving_deliver_prints_the_pickup_run_closeout_handoff (tests/unit/test_run_cli.py) asserts the printed sha equals HEAD after the call and that stderr carries at most one fr: committed/not committed line.

<!-- fr:journal kind=finding scope=plan id=p3-steer-resolved created=2026-09-25T13:50:57 state=fixed resolves=p3-steer -->
### p3-steer-resolved · finding [fixed] · resolves p3-steer: Phase-3 tests assert commit cadence; stderr line count unpinned

pending: fixing phase-3 test cadence assertions per operator steer

<!-- fr:journal kind=finding scope=plan id=p3-steer-resolved-2 created=2026-09-25T13:51:19 state=fixed resolves=p3-steer -->
### p3-steer-resolved-2 · finding [fixed] · resolves p3-steer: Phase-3 tests assert commit cadence; stderr line count unpinned

a3b06b5a: replaced commit-count/cadence assertions in test_run_cli.py, test_plan_cmd.py, test_journal_cmd.py with record-paths-clean outcome checks; kept subject-format checks (robustified via path-scoped git log); added <=1 stderr commit-line pins for run advance (grouped member), run resolve --no-questions, plan edit --tick, journal add (no double-report found); disable-proof done and reverted; full suite 5260 passed, 89 skipped

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-09-25T14:00:53 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · Handoff prints 'push it' even when the cursor commit was refused (phase 4)

run_cmd.py _closeout_handoff_lines reads HEAD regardless of whether _commit_run_writes_now() committed (default branch, stuck lock, detached HEAD) — false assurance the cursor reached the PR.

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-09-25T14:00:54 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · Brief's archive/housekeeping steps are not exact commands (phase 4)

closeout.py:107-114: no command to get onto a housekeeping branch; a fresh session could fr archive inside the merged feature workspace, committing to a dead branch.

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-09-25T14:00:54 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · Brief never says which checkout to run from (phase 4)

closeout_brief omits the directory; only the transient handoff line has it. After merge the run file is on main and the workspace may be reaped.

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-09-25T14:00:55 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · No test that resolved (deferred/fixed) out-of-scope findings are excluded from the brief (phase 4)

test gap on the effective-state fold's exclusion path.

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-09-25T14:00:55 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · No test for missing PR / spec / plan fallbacks in the brief (phase 4)

closeout.py:96 and the if spec_path/plan_path guards are uncovered.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-09-25T14:06:23 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: Handoff prints 'push it' even when the cursor commit was refused

a216b4a5: commit_records/_RunWrites.commit()/_commit_run_writes_now() return CommitOutcome; closeout handoff threads it as committed=, printing a NOT-committed line instead of a sha when refused. Test: test_run_cli.py::test_resolving_deliver_on_the_default_branch_never_claims_the_cursor_was_pushed

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-09-25T14:10:56 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: Brief's archive/housekeeping steps are not exact commands

a797e354: closeout brief gives exact housekeeping commands (fr isolation up --branch chore/archive-<slug> before fr archive, explicit warning against archiving in the merged feature workspace, commit/push/PR). Test: test_run_closeout.py::test_closeout_brief_housekeeping_gives_exact_commands_on_a_new_branch

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-09-25T14:10:57 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: Brief never says which checkout to run from

a797e354: closeout brief now names its own checkout (repo_root, base clone, default branch, after merge) instead of relying on the transient handoff line. Test: test_run_closeout.py::test_closeout_brief_names_the_checkout_to_run_it_from

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-09-25T14:10:57 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: No test that resolved (deferred/fixed) out-of-scope findings are excluded from the brief

a797e354: backfilled coverage on effective_finding_states' exclusion path — already correct, no code change needed. Tests: test_run_closeout.py::test_closeout_brief_excludes_a_finding_later_deferred_with_a_tracker, ::test_closeout_brief_excludes_a_finding_later_fixed_by_the_operator

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-09-25T14:10:58 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: No test for missing PR / spec / plan fallbacks in the brief

a797e354: backfilled coverage on the PR:(none recorded) fallback and the spec_path/plan_path guards — already correct, no code change needed. Tests: test_run_closeout.py::test_closeout_brief_reports_no_pr_recorded_when_deliver_emitted_none, ::test_closeout_brief_omits_spec_and_plan_lines_when_the_run_never_emitted_them

<!-- fr:journal kind=discovery scope=plan id=a49fbd745308 created=2026-09-25T14:15:40 -->
### a49fbd745308 · discovery · Full-suite: pre-existing env failure in test_install_bridge, unrelated to phase 4

Full suite after phase 4 fixes (5258 passed, 1 failed, 97 skipped, scratchpad/p4-fixes.log): tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper fails because this devcontainer's globally uv-tool-installed `fr` (v4.20.1 at ~/.local/share/uv/tools/fr) cannot import fr_vk — confirmed by direct python -c "import fr_vk.bridge" against that interpreter, and by re-running the isolated test alone (still fails) and re-running install.sh --install-bridge by hand (same ERROR). No file touched by the p4-r1..r5 fixes (run_cmd.py, records_commit.py, run/closeout.py, their tests) is on this test's path — it exercises scripts/install.sh's bridge wrapper against the pod's pre-existing global tool install, which none of this phase's commits changed. Left open (not fixed): remediating the pod's global uv tool state is outside this phase's scope; re-running `uv tool install --force --with .../fr-vk .../fr` would fix it but is a host-level mutation, not a repo fix.

<!-- fr:journal kind=review scope=plan id=review-p4 created=2026-09-25T14:16:29 phase=4 -->
### review-p4 · review · Phase 4 review (phase 4)

Dispatched reviewer (sonnet) over 7e983b53: r1 (important: handoff claimed 'push it' on a refused commit), r2/r3 (brief not self-contained: housekeeping branch + checkout), r4/r5 (test gaps). All in scope; fixed by a dispatched fix agent in a216b4a5, a797e354 with RED tests for r1-r3 (r4/r5 were pure coverage, code already correct). Seam kept: commit_records now returns its CommitOutcome. Full suite under -n auto: 5258 passed, 1 failed (test_install_bridge, container-only stale global fr; passes on host — verified by orchestrator).

<!-- fr:journal kind=finding scope=plan id=p3-m5-resolved created=2026-09-25T14:20:08 state=fixed resolves=p3-m5 -->
### p3-m5-resolved · finding [fixed] · resolves p3-m5: Ready-checklist 'no commits since the ok' must exempt chore(fr) commits

618fba30: fr-goal SKILL.md §8 Ready-checklist now excludes fr's own chore(fr): record commits from 'no commits since the ok'

<!-- fr:journal kind=discovery scope=plan id=47c79242817d created=2026-09-25T14:29:36 phase=5 -->
### 47c79242817d · discovery · P5.T1.S1 e2e test: RED verified by disabling the commit seam (phase 5)

Temporarily made fr.records_commit.commit_records no-op (returning CommitOutcome(committed=False, ...)) and reran tests/unit/test_closeout_e2e.py: it failed for the right reason (deliver's handoff printed 'cursor NOT committed' instead of 'cursor committed as'). Reverted (git checkout -- packages/fr/src/fr/records_commit.py) and confirmed green again. No fixture piece needed a live forge except the PR-state lookup in verify_merge, which is monkeypatched on a real HostWorktreeTarget instance — every git operation the test asserts on (worktree state, squash-merge, push, fetch, reap-hazard) is real.

<!-- fr:journal kind=discovery scope=plan id=9aeae7459f69 created=2026-09-25T14:29:54 phase=5 -->
### 9aeae7459f69 · discovery · no-refactor-because P5.T1 (phase 5)

One new test file, self-contained helpers mirroring the file-local _git/_invoke convention test_run_cli.py and test_isolation.py already use — nothing to fold across files.

<!-- fr:journal kind=discovery scope=plan id=0a88fd11ad39 created=2026-09-25T14:30:35 phase=5 -->
### 0a88fd11ad39 · discovery · no-refactor-because P5.T3 (phase 5)

fr acceptance set-status is the whole task — a CLI invocation that rewrites the matrix row and regenerates the three committed reports; nothing here is code to refactor.

<!-- fr:journal kind=discovery scope=plan id=fd0be9e9c6bf created=2026-09-25T14:37:06 phase=5 -->
### fd0be9e9c6bf · discovery · fr-goal SKILL.md 120-line cap + resolve-example regex both caught only by the full suite (phase 5)

8f47711c: the P5.T2.S1 rewrite pushed fr-goal/SKILL.md to 128 lines (cap 120) and a hard line-wrap split 'fr journal resolve --scope ...' across a newline, which test_skill_journal_resolve_examples.py's backtick regex (no DOTALL-safe anchor) does not match across. Neither the targeted mirror/tripwire runs (opencode/hermes sync + tool-neutrality) nor a visual read of the diff caught it — only the full suite did. Fixed by tightening prose back to single-line clauses; mirrors regenerated.

<!-- fr:journal kind=review scope=plan id=review-p5 created=2026-09-25T14:46:59 phase=5 -->
### review-p5 · review · Phase 5 review (phase 5)

Dispatched reviewer (sonnet) over 618fba30..HEAD: no in-scope findings; verdict Ready. Checked every new SKILL.md/explainer claim against closeout.py and run_cmd.py; no stale closeout prose elsewhere; e2e test real (only _pr faked); mirrors in sync; line-cap squeeze kept every fact. One observation (plan step broader than needed) — not a defect.

<!-- fr:journal kind=finding scope=plan id=p4-dogfood created=2026-09-25T15:02:33 phase=4 state=open review_scope=in -->
### p4-dogfood · finding [open] (reviewer: in scope) · Closeout handoff and brief name the feature worktree as 'the base clone' (phase 4)

Found by dogfooding deliver on this run: _closeout_handoff_lines and closeout_brief print repo_root, which inside an fr workspace is the linked feature worktree (reaped by closeout), labelled 'the base clone'. Must resolve the primary checkout (parent of git rev-parse --git-common-dir).

<!-- fr:journal kind=finding scope=plan id=p4-dogfood-resolved created=2026-09-25T15:04:59 state=fixed resolves=p4-dogfood -->
### p4-dogfood-resolved · finding [fixed] · resolves p4-dogfood: Closeout handoff and brief name the feature worktree as 'the base clone'

9c05eb49: primary_checkout() for the displayed directory at both sites; RED test_closeout_brief_run_from_a_linked_worktree_names_the_primary_checkout (brief named the worktree), fallback test added; live fr pickup --run on this run now names the base clone.

<!-- fr:journal kind=finding scope=plan id=deliver-bg-suite created=2026-09-25T15:09:20 state=open review_scope=out -->
### deliver-bg-suite · finding [open] (reviewer: out of scope) · deliver's tests= gate cannot credit a backgrounded suite run

run_cmd.py:1660-1664 _verify_tests_log requires the log's mtime inside the window of the Bash call naming it; a run_in_background call's window ends at launch, so a backgrounded suite (which the long_commands brief rule tells agents to use) is always refused ('its bytes were not written by the command of yours that names it'). Also a log path held in a shell variable (> $L) is not recognised. Worked around this run by a foreground call (timeout 600000; ~4 min under -n auto).

<!-- fr:journal kind=finding scope=plan id=deliver-bg-suite-resolved created=2026-09-25T15:09:21 state=open resolves=deliver-bg-suite out_of_scope=true -->
### deliver-bg-suite-resolved · finding [out-of-scope] · resolves deliver-bg-suite: deliver's tests= gate cannot credit a backgrounded suite run

Predates this change (the gate and the long_commands rule both shipped earlier); surfaced by this run's own deliver. Candidate fix: accept a background task's completion window, or match the task's output file.

<!-- fr:journal kind=finding scope=plan id=p3-noop created=2026-09-25T15:12:35 phase=3 state=open review_scope=in -->
### p3-noop · finding [open] (reviewer: in scope) · A record write that changed nothing prints 'fr: not committed' (phase 3)

Found on this run's own deliver re-resolve: nothing-to-commit was reported as a refusal on stderr, and would make the closeout handoff print 'cursor NOT committed' for an unchanged cursor.

<!-- fr:journal kind=finding scope=plan id=p3-noop-resolved created=2026-09-25T15:12:35 state=fixed resolves=p3-noop -->
### p3-noop-resolved · finding [fixed] · resolves p3-noop: A record write that changed nothing prints 'fr: not committed'

b53f7ee0: CommitOutcome.unchanged; commit_records silent on it; handoff counts it as landed. RED: test_a_record_write_that_changed_nothing_is_silent_and_counts_as_landed (AttributeError: no 'unchanged'). Migration tests unmodified and green.

<!-- fr:journal kind=finding scope=plan id=pd-r1 created=2026-09-25T15:25:19 phase=4 state=open review_scope=in -->
### pd-r1 · finding [open] (reviewer: in scope) · primary_checkout mis-resolves a --separate-git-dir primary (phase 4)

Post-deliver review (medium, verified live): the common-dir basename guard ('.git') falls back to repo_root = the worktree for a relocated git-dir. Use git worktree list --porcelain (first entry = main worktree).

<!-- fr:journal kind=finding scope=plan id=pd-r2 created=2026-09-25T15:25:20 phase=3 state=open review_scope=in -->
### pd-r2 · finding [open] (reviewer: in scope) · A failed diff --cached probe is reported as unchanged (phase 3)

Post-deliver review (low-medium): commit.py's pending.returncode != 0 branch is folded into unchanged=True; with the silent-unchanged change a git error now yields false 'cursor committed' assurance. Only rc 0 + empty output is unchanged.

<!-- fr:journal kind=finding scope=plan id=pd-r3 created=2026-09-25T15:25:20 phase=4 state=open review_scope=in -->
### pd-r3 · finding [open] (reviewer: in scope) · No CLI-level test at the two dogfood wiring points (phase 4)

Post-deliver review (low): no test asserts the handoff's 'start a NEW session in <dir>' names the primary checkout from a linked worktree, nor that a byte-identical re-resolve prints 'cursor committed as' (not 'NOT committed').

<!-- fr:journal kind=finding scope=plan id=pd-r1-resolved created=2026-09-25T15:34:11 state=fixed resolves=pd-r1 -->
### pd-r1-resolved · finding [fixed] · resolves pd-r1: primary_checkout mis-resolves a --separate-git-dir primary

86bebae3: primary_checkout resolves via git worktree list --porcelain's first entry (fall back to repo_root when git fails, isn't a repo, or the entry is bare), recovering the checkout containing a relocated main git-dir instead of returning the linked worktree. Tests: test_primary_checkout_resolves_a_relocated_git_dir_primary_from_its_linked_worktree, test_primary_checkout_falls_back_to_repo_root_for_a_bare_repository.
