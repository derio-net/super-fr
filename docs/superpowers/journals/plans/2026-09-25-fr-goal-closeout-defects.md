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
