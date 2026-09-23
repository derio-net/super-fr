# Journal: 2026-09-23-lifecycle-container-vs-worktree

<!-- fr:journal kind=discovery scope=plan id=0ff1a43ad622 created=2026-09-23T01:05:39 phase=4 -->
### 0ff1a43ad622 · discovery · no-refactor-because P4.T1 (phase 4)

Red-only task: it writes failing tests; production code does not exist yet, the refactor pass is P4.T3.S3.

<!-- fr:journal kind=discovery scope=plan id=b2698d7d0da0 created=2026-09-23T01:05:40 phase=4 -->
### b2698d7d0da0 · discovery · no-refactor-because P4.T2 (phase 4)

Red-only task: failing tests only; the refactor pass for the preserve module is P4.T3.S3.

<!-- fr:journal kind=discovery scope=plan id=94d22e0fbf2e created=2026-09-23T01:05:40 phase=5 -->
### 94d22e0fbf2e · discovery · no-refactor-because P5.T1 (phase 5)

Red-only task: failing tests only; refactor lives in P5.T2.S2.

<!-- fr:journal kind=discovery scope=plan id=63c9d00fb633 created=2026-09-23T01:05:40 phase=6 -->
### 63c9d00fb633 · discovery · no-refactor-because P6.T1 (phase 6)

Prose, generated mirrors and a version bump: no code structure to refactor; mirrors are generator-owned.

<!-- fr:journal kind=discovery scope=plan id=41a03e1da877 created=2026-09-23T01:05:41 phase=6 -->
### 41a03e1da877 · discovery · no-refactor-because P6.T2 (phase 6)

Live verification and matrix status moves: no code is written.

<!-- fr:journal kind=discovery scope=plan id=8f763b55b51e created=2026-09-23T01:05:48 phase=1 -->
### 8f763b55b51e · discovery · no-refactor-because P1.T1 (phase 1)

Red-only task: failing tests only; the phase's green task carries the refactor step.

<!-- fr:journal kind=discovery scope=plan id=e1e4eeb0c509 created=2026-09-23T01:05:49 phase=2 -->
### e1e4eeb0c509 · discovery · no-refactor-because P2.T1 (phase 2)

Red-only task: failing tests only; the phase's green task carries the refactor step.

<!-- fr:journal kind=discovery scope=plan id=b653780d4c09 created=2026-09-23T01:05:49 phase=3 -->
### b653780d4c09 · discovery · no-refactor-because P3.T1 (phase 3)

Red-only task: failing tests only; the phase's green task carries the refactor step.

<!-- fr:journal kind=discovery scope=plan id=9dfaeed2a006 created=2026-09-23T01:17:00 phase=1 -->
### 9dfaeed2a006 · discovery · P1.T2 refactor: strict container lookup shared by restart and stop (phase 1)

Refactored rather than no-refactor: `LocalWorktreeDevcontainerTarget._ps_parts_strict` (docker ps --all; a non-zero rc or missing docker binary raises IsolationError 'docker is unreachable', never reads as absence — #354) and `_require_container(state, nothing)` (raises with the `fr isolation up` hint). `restart` now uses `_require_container` too. Behaviour change for restart: a FAILED docker ps used to surface as 'no container — nothing to restart'; it now says docker is unreachable. Phase 2's `_ensure_running` can build on `_ps_parts_strict`.

<!-- fr:journal kind=discovery scope=plan id=1e6486082107 created=2026-09-23T01:17:01 phase=1 -->
### 1e6486082107 · discovery · stop treats exited/created/dead as already stopped; status maps only exited (phase 1)

`_NOT_RUNNING = {exited, created, dead}`: stop on any of these is a no-op success ('already stopped (<id>, docker state <s>)'). A container absent after a successful `docker stop` (e.g. --rm) is accepted as stopped. status maps only `exited` -> `stopped` per spec §3.B (helper `_shown_container_state`); `created`/`dead` pass through. The FakeRunner in tests/unit/test_isolation.py gained a stateful `stopped` set + `stop_sticks` flag (still-running-after-stop case).

<!-- fr:journal kind=finding scope=plan id=p1-f1 created=2026-09-23T01:28:31 phase=1 state=fixed -->
### p1-f1 · finding [fixed] · stop verified the first docker ps line, not this container (phase 1)

Verification now looks the container up by id among all (id,state) pairs (_ps_pairs_strict); test_verifies_this_container_by_id_not_first_line.

<!-- fr:journal kind=finding scope=plan id=p1-f2 created=2026-09-23T01:28:31 phase=1 state=fixed -->
### p1-f2 · finding [fixed] · No tests for missing docker binary or restart's new unreachable message (phase 1)

Added test_missing_docker_binary_is_unreachable and TestRestart.test_failed_docker_ps_is_unreachable_not_absent.

<!-- fr:journal kind=finding scope=plan id=p1-f3 created=2026-09-23T01:28:32 phase=1 state=fixed -->
### p1-f3 · finding [fixed] · CLI stop tests passed on the already-stopped no-op (phase 1)

Fake records docker argv; tests assert docker stop was issued and 'already' absent.

<!-- fr:journal kind=finding scope=plan id=p1-f4 created=2026-09-23T01:28:32 phase=1 state=fixed -->
### p1-f4 · finding [fixed] · dead container reported as already stopped and promised a resume (phase 1)

dead now returns a message naming fr isolation rebuild --branch <b>; test_dead_container_points_at_rebuild.

<!-- fr:journal kind=finding scope=plan id=p1-f5 created=2026-09-23T01:28:33 phase=1 state=fixed -->
### p1-f5 · finding [fixed] · _container_id (and later _container_state) had no callers (phase 1)

Both removed.

<!-- fr:journal kind=finding scope=plan id=p1-f6 created=2026-09-23T01:28:33 phase=1 state=fixed -->
### p1-f6 · finding [fixed] · match='docker' too loose (phase 1)

Tightened to 'unreachable'.

<!-- fr:journal kind=finding scope=plan id=p1-f7 created=2026-09-23T01:28:34 phase=1 state=fixed -->
### p1-f7 · finding [fixed] · status read a failed docker ps as 'not running' (#354) (phase 1)

status now renders 'unknown (docker unreachable)'; test_failed_query_is_unknown_not_absent.

<!-- fr:journal kind=finding scope=plan id=p1-f8 created=2026-09-23T01:28:34 phase=1 state=refuted -->
### p1-f8 · finding [refuted] · stop help/message promise exec resume before phase 2 lands (phase 1)

All phases ship in one PR (spec §3.B); the phase is never merged alone. Phase 2 implements the promised resume.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-09-23T01:28:34 phase=1 -->
### p1-review · review · Phase 1 review (independent reviewer): 0 major, 4 minor, 4 nits (phase 1)

Findings p1-f1..p1-f7 fixed with tests; p1-f8 refuted (single-PR delivery). Full suite 4539 passed / 88 skipped; ruff + mypy clean.

<!-- fr:journal kind=discovery scope=plan id=108b178f281e created=2026-09-23T01:36:16 phase=2 -->
### 108b178f281e · discovery · P2.T2 refactor: one devcontainer addressing helper (phase 2)

Refactored rather than no-refactor: `_config_path(worktree, profile)` (the BRANCH config path) and `_devcontainer_argv(worktree, profile, *sub)` (`devcontainer <sub> --workspace-folder --config`) are now shared by `exec`, `_ssh_agent_probe` and `_devcontainer_up`, so the three can no longer drift. `_devcontainer_up` appends `--remove-existing-container` / `--build-no-cache` AFTER the mount, so rebuild argv == up argv + flags (pinned by test). `_carried_state(branch, worktree, profile)` is the shared §3.C record builder for both `up` implementations.

<!-- fr:journal kind=discovery scope=plan id=2b2d6293bbdb created=2026-09-23T01:36:17 phase=2 -->
### 2b2d6293bbdb · discovery · exec/_ensure_running semantics as built (phase 2)

Any `running`/`restarting` row among the label-filtered containers → exec directly; otherwise the FIRST row decides: exited/created → stderr notice + `_devcontainer_up` (no remove flag); paused → `docker unpause`; anything else (dead, removing, unknown) and absent → `no usable container for <b> … fr isolation rebuild --branch <b> recreates it (worktree kept)`. A failed resume/unpause re-raises naming the same rebuild line. docker-ps failure keeps the phase-1 wording from `_ps_pairs_strict` (`docker is unreachable — …`), not the spec literal `cannot run in <b>`. A FileNotFoundError from the runner (devcontainer CLI missing) becomes an IsolationError; the CLI `exec` now routes IsolationError through `_fail` (exit 2, one line). Existing tests that exec'd against an absent container were updated: `test_exec_passthrough` now has a running container, and the CLI `fake_run` fixture models `devcontainer up` → `cid running`, `docker rm` → gone.

<!-- fr:journal kind=discovery scope=plan id=8dbe79bb6dd7 created=2026-09-23T01:36:17 phase=2 -->
### 8dbe79bb6dd7 · discovery · rebuild image reclaim needs both image ids (phase 2)

rebuild reclaims the old image only when BOTH the old and the new image id were read and they differ; an unreadable new image (inspect failed) skips `rmi` rather than guess. The new container id is the first post-rebuild `docker ps --all` row whose id differs from the old one (falls back to the first row). No old container is fine: the message reads `(none → <new>)`, which is the path exec directs an absent/dead workspace to.

<!-- fr:journal kind=discovery scope=plan id=8af43aee8ee9 created=2026-09-23T01:42:58 phase=2 -->
### 8af43aee8ee9 · discovery · phase-2 acceptance rows left not-implemented on purpose (phase 2)

`fr plan edit --complete-phase 2` warns that isolation-rebuild-keeps-worktree and isolation-stop-and-resume are still not-implemented. Left as-is: 06.yaml (Live walks and matrix flips) owns flipping all five rows after the live walks; unit refs to cite then: tests/unit/test_isolation_container_verbs.py (TestRebuild, TestExecEnsureRunning, CLI tests).

<!-- fr:journal kind=finding scope=plan id=p2-f1 created=2026-09-23T01:52:26 phase=2 state=fixed -->
### p2-f1 · finding [fixed] · rebuild reported a successful recreate as failed when the re-query failed (phase 2)

rebuild now catches IsolationError from the post-up docker ps: returns the recreated line with new=unknown, skips the image reclaim, warns on stderr. Test: tests/unit/test_isolation_container_verbs.py::TestRebuild::test_failed_requery_after_successful_up_is_still_success.

<!-- fr:journal kind=finding scope=plan id=p2-f2 created=2026-09-23T01:52:27 phase=2 state=fixed -->
### p2-f2 · finding [fixed] · _devcontainer_up leaked FileNotFoundError (traceback on up/rebuild) (phase 2)

_devcontainer_up converts FileNotFoundError via the new module helper _missing_binary (shared by up, rebuild, resume); exec's handler now wraps only the devcontainer exec call. Test: tests/unit/test_isolation_container_verbs.py::TestRebuild::test_missing_devcontainer_binary_is_an_isolation_error.

<!-- fr:journal kind=finding scope=plan id=p2-f3 created=2026-09-23T01:52:27 phase=2 state=fixed -->
### p2-f3 · finding [fixed] · carried-state load raised on a corrupt/empty/truncated record (phase 2)

carried_state catches (ValidationError, OSError, ValueError) from load_state, warns on stderr naming the state path, and writes a fresh record. Test: tests/unit/test_isolation_container_verbs.py::test_up_over_a_corrupt_record_starts_fresh_with_warning (garbage, empty, truncated).

<!-- fr:journal kind=finding scope=plan id=p2-f4 created=2026-09-23T01:52:28 phase=2 state=fixed -->
### p2-f4 · finding [fixed] · sessions carried across a record for a different worktree (phase 2)

carried_state only carries when prior.worktree.resolve() == worktree.resolve(). Test: tests/unit/test_isolation_container_verbs.py::test_up_does_not_carry_a_record_for_a_different_worktree.

<!-- fr:journal kind=finding scope=plan id=p2-f5 created=2026-09-23T01:52:28 phase=2 state=fixed -->
### p2-f5 · finding [fixed] · ExternalTarget.up still dropped sessions and created_at (phase 2)

Carry logic lifted to fr.isolation.types.carried_state(repo_root, branch, worktree, profile), used by the local, host-worktree and external targets (the LocalWorktreeDevcontainerTarget._carried_state method is gone). Test: tests/unit/test_isolation_container_verbs.py::test_external_up_carries_sessions_and_created_at_forward.

<!-- fr:journal kind=finding scope=plan id=p2-f6 created=2026-09-23T01:52:28 phase=2 state=fixed -->
### p2-f6 · finding [fixed] · resume-failure message buried the rebuild hint after multi-line output (phase 2)

_ensure_running now raises 'could not resume the container for <b> — `fr isolation rebuild --branch <b>` recreates it (worktree kept).' then a newline, then devcontainer's output; the unpause failure uses the same shape. Tests: tests/unit/test_isolation_container_verbs.py::TestExecReviewFixes::test_resume_failure_first_line_names_rebuild and tests/unit/test_isolation_container_verbs.py::test_cli_exec_failed_resume_first_line_names_rebuild (CLI: the error: line names the rebuild).

<!-- fr:journal kind=finding scope=plan id=p2-f7 created=2026-09-23T01:52:29 phase=2 state=fixed -->
### p2-f7 · finding [fixed] · exec: no worktree check; FileNotFoundError hint assumed devcontainer (phase 2)

exec checks state.worktree.is_dir() first ('run `fr isolation up --branch <b>`', no docker call); the missing-binary message is built from err.filename (fallback err.args[0]) with no assumed name. Tests: tests/unit/test_isolation_container_verbs.py::TestExecReviewFixes::test_missing_worktree_names_up_before_any_docker, ::test_missing_binary_hint_names_the_binary.

<!-- fr:journal kind=finding scope=plan id=p2-f8 created=2026-09-23T01:52:29 phase=2 state=fixed -->
### p2-f8 · finding [fixed] · rebuild new-id pick only excluded the old id (phase 2)

The new id is the first post-rebuild row absent from the whole before set (fallback: first row). Test: tests/unit/test_isolation_container_verbs.py::TestRebuild::test_new_id_is_one_absent_from_the_whole_before_set.

<!-- fr:journal kind=finding scope=plan id=p2-f9 created=2026-09-23T01:52:30 phase=2 state=fixed -->
### p2-f9 · finding [fixed] · _ensure_running decided on the first row only (phase 2)

With several containers under the label: any running/restarting → exec; else the first resumable (exited/created) → devcontainer up; else the first paused → unpause; raise only when none is usable. Tests: tests/unit/test_isolation_container_verbs.py::TestExecReviewFixes::test_several_containers_prefer_a_usable_one (dead first, then exited/paused), ::test_resumable_preferred_over_paused.

<!-- fr:journal kind=finding scope=plan id=p2-f10 created=2026-09-23T01:52:30 phase=2 state=fixed -->
### p2-f10 · finding [fixed] · test_running_execs_directly under-asserted (phase 2)

Now asserts exactly one docker call and that it is ps. Test: tests/unit/test_isolation_container_verbs.py::TestExecEnsureRunning::test_running_execs_directly.

<!-- fr:journal kind=finding scope=plan id=p2-f11 created=2026-09-23T01:52:31 phase=2 state=fixed -->
### p2-f11 · finding [fixed] · rebuild failure test did not pin state/marker or the wording (phase 2)

Asserts state file + .fr-isolation marker byte-identical after the failed rebuild and the 'may already have been removed' / 'worktree and run are intact' / 'fr isolation rebuild --branch <b>' wording. Test: tests/unit/test_isolation_container_verbs.py::TestRebuild::test_failure_never_reclaims_and_names_the_retry.

<!-- fr:journal kind=finding scope=plan id=p2-f12 created=2026-09-23T01:52:31 phase=2 state=fixed -->
### p2-f12 · finding [fixed] · CLI fake_run shared one global container across workspaces (phase 2)

tests/unit/test_isolation_cmd.py fake_run now keys live containers on the devcontainer up --workspace-folder= value and answers docker ps by the --filter=label=devcontainer.local_folder= value (docker rm removes by id). Whole test_isolation_cmd.py green.

<!-- fr:journal kind=finding scope=plan id=p2-f13 created=2026-09-23T01:52:32 phase=2 state=fixed -->
### p2-f13 · finding [fixed] · up restamped the marker's created_at while the state kept the old one (phase 2)

_write_isolation_marker takes created_at; local and host-worktree up pass the carried state's created_at. Test: tests/unit/test_isolation_container_verbs.py::test_up_marker_created_at_matches_the_carried_record.

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-09-23T02:00:53 phase=2 -->
### p2-review · review · Phase 2 review (independent reviewer): 0 major, 6 minor, 7 nits (phase 2)

All 13 (p2-f1..p2-f13) verified real and fixed with tests in 3387b79f; full suite 4579 passed / 88 skipped per executor, isolation suites re-run by orchestrator.
