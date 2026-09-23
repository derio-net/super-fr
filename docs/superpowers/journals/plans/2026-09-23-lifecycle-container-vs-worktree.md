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

<!-- fr:journal kind=discovery scope=plan id=59d279fcdb7d created=2026-09-23T02:08:07 phase=3 -->
### 59d279fcdb7d · discovery · remote reuse uses --no-track + explicit upstream config, not --track (phase 3)

The plan/spec name `git worktree add --track -b <B> <wt> origin/<B>`. Verified against git 2.53: in a `--single-branch` clone (fetch refspec maps only main) `--track` fails with 'cannot set up tracking information; starting point origin/<B> is not a branch' (exit 255, no residue). So the remote row runs `git worktree add --no-track -b <B> <wt> origin/<B>` and then sets `branch.<B>.remote=origin` / `branch.<B>.merge=refs/heads/<B>` — same upstream as --track in every clone shape. Pinned by the single-branch integration test and the unit test's config assertions.

<!-- fr:journal kind=discovery scope=plan id=b77e57ef8363 created=2026-09-23T02:08:08 phase=3 -->
### b77e57ef8363 · discovery · P3.T2 refactor: classification is a pure classify_branch() from the start (phase 3)

Rather than growing _git_worktree_add then extracting, the §3.E table was written directly as `classify_branch(branch, *, local_sha, remote: RemoteView, ahead, behind, base, worktree) -> BranchDecision` (module-level, pure; raises IsolationError for the refused row). Git gathering lives in `_remote_view` (ls-remote --exit-code → 0 exists / 2 absent / else unknown; explicit-refspec fetch; a failed fetch is unknown), `_ahead_behind` (rev-list --left-right --count) and `_rev`; `_ref_exists` now delegates to `_rev`. Cold-start lines append ` (<sha12>)` after the existing text, so 'basing new branch X on origin/main (fetched)' remains a substring.

<!-- fr:journal kind=discovery scope=plan id=7b7b6cf00c2a created=2026-09-23T02:08:08 phase=3 -->
### 7b7b6cf00c2a · discovery · Rows the §3.E table leaves open, as decided (phase 3)

(1) no local <B>, origin unknown, local origin/<B> ref present, --base given: REFUSED like the exists+--base row (the ref is evidence the name is taken; message says 'was last fetched (origin unreachable)'). (2) --no-fetch: a local origin/<B> ref is treated as 'exists'; no ref is 'unknown' with reason '--no-fetch', so a local <B> prints '(origin not checked: --no-fetch)' and a cold start carries the could-not-check WARNING. (3) ls-remote exit 0 then a failed explicit fetch is 'unknown' per the #354 invariant — with no local ref this still cold-starts (as the table says) even though origin just reported <B> present; the WARNING names the fork risk. (4) No origin remote → 'absent', unchanged from today.

<!-- fr:journal kind=discovery scope=plan id=3f54c04d7371 created=2026-09-23T02:14:48 phase=3 -->
### 3f54c04d7371 · discovery · phase-3 acceptance row left not-implemented for phase 6 (phase 3)

The #438 row (Isolation lifecycle, 'up --branch <B> on a branch that exists only on origin…') stays not-implemented, matching phase 2's precedent (8af43aee8ee9): 06.yaml flips rows after the live walks. Refs to cite then: tests/integration/test_up_branch_reuses_origin.py (fresh clone, --single-branch clone, --base refusal, behind+WARNING) and tests/unit/test_isolation_branch_classify.py (every §3.E row, ls-remote exit codes, --no-fetch).

<!-- fr:journal kind=finding scope=plan id=p3-f1 created=2026-09-23T02:31:18 phase=3 state=fixed -->
### p3-f1 · finding [fixed] · ls-remote exit 0 + failed fetch + no local ref cold-started a second history (#438 itself) (phase 3)

New RemoteView state `unfetched` (ls-remote said exists, the explicit fetch failed, or no origin/<B> after it). No local <B> and no local origin/<B> ref → IsolationError 'origin/<B> exists but could not be fetched (<reason>) — retry, or `git fetch origin +refs/heads/<B>:refs/remotes/origin/<B>`'. With a stale local ref → reuse it, WARNING 'fetch of origin/<B> failed — reusing the last-fetched origin/<B> (<sha>); it may be stale'. --base beside unfetched+ref is refused like exists. Spec §3.E gained the refuse row. Tests: tests/unit/test_isolation_branch_classify.py::test_remote_exists_but_fetch_fails_without_ref_is_refused, ::test_remote_exists_fetch_fails_with_stale_ref_reuses_it (runner fails only the refspec fetch).

<!-- fr:journal kind=finding scope=plan id=p3-f2 created=2026-09-23T02:31:18 phase=3 state=fixed -->
### p3-f2 · finding [fixed] · _ahead_behind read a failed rev-list as (0,0) (phase 3)

Renamed `_relation`, returns None when it cannot count; classify_branch takes `relation: tuple[int,int] | None` (replacing ahead/behind) and prints '(differs from origin/<B> at <sha>; relation unknown)' when the shas differ and the relation is None. Tests: tests/unit/test_isolation_branch_classify.py::test_relation_unknown_is_reported_not_read_as_equal, ::test_classify_branch_relation_unknown.

<!-- fr:journal kind=finding scope=plan id=p3-f3 created=2026-09-23T02:31:19 phase=3 state=fixed -->
### p3-f3 · finding [fixed] · probe/fetch could block on a credential prompt or slow ssh (phase 3)

Runner seam extended minimally: `subprocess_runner` gains optional `env` and `timeout`; with a timeout stdin is /dev/null and an expiry returns exit 124 + 'timed out' stderr (never raises; 124 is not 2, so a probe timeout is unknown). `_run_network` runs ls-remote, the refspec fetch, the cold-start `git fetch origin` and `remote set-head --auto` with GIT_TERMINAL_PROMPT=0, a 60s timeout, and GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=15' only when none of GIT_SSH_COMMAND / GIT_SSH / core.sshCommand is set. Cost: every test fake runner had to accept the new kwargs (**kw) — 25 fakes across test_isolation*.py and two integration files; no production Runner other than subprocess_runner exists. Tests: tests/unit/test_isolation_branch_classify.py::test_network_calls_are_non_interactive_and_bounded, ::test_operator_ssh_command_env_is_respected, ::test_operator_core_ssh_command_is_respected, ::test_subprocess_runner_timeout_is_a_failure_not_a_hang, ::test_ls_remote_other_failure_is_unknown_never_absence[124].

<!-- fr:journal kind=finding scope=plan id=p3-f4 created=2026-09-23T02:31:19 phase=3 state=fixed -->
### p3-f4 · finding [fixed] · an unknown probe was followed by a second full fetch in _cold_start_base (phase 3)

`_cold_start_base(..., origin_reachable=False)` when the probe was unknown: skips the fetch and returns local HEAD with 'WARNING: origin unreachable — basing <B> on local HEAD' (the today-equivalent of a failed fetch). Test: tests/unit/test_isolation_branch_classify.py::test_unknown_probe_skips_the_second_full_fetch (no git fetch at all).

<!-- fr:journal kind=finding scope=plan id=p3-f5 created=2026-09-23T02:31:19 phase=3 state=fixed -->
### p3-f5 · finding [fixed] · git config return codes for the upstream were ignored (phase 3)

`_set_upstream` checks each rc; on failure prints 'WARNING: could not set <B>'s upstream to origin/<B> (<why>) — set branch.<B>.remote=origin and branch.<B>.merge=refs/heads/<B> yourself' and continues (the worktree is already correct). Test: tests/unit/test_isolation_branch_classify.py::test_failed_upstream_config_warns.

<!-- fr:journal kind=finding scope=plan id=p3-f6 created=2026-09-23T02:31:20 phase=3 state=fixed -->
### p3-f6 · finding [fixed] · missing tests for wrapper ref, short-circuit, no-origin, --no-fetch no ref, CLI exit 2 (phase 3)

Added tests/unit/test_isolation_branch_classify.py::test_remote_row_checks_the_validator_wrapper_in_origin_ref (plan repo whose origin/feat/x lacks the wrapper → 'not in origin/feat/x'), ::test_existing_worktree_short_circuit_never_probes, ::test_no_origin_output_unchanged (exact stderr lines both rows, no ls-remote), ::test_no_fetch_without_origin_ref_is_a_soft_line, ::test_no_fetch_local_branch_without_origin_ref, ::test_cli_maps_the_base_refusal_to_exit_2. All passed against the fixed code (they pin existing behaviour).

<!-- fr:journal kind=finding scope=plan id=p3-f7 created=2026-09-23T02:31:20 phase=3 state=fixed -->
### p3-f7 · finding [fixed] · spec §3.E and 03.yaml still named --track (phase 3)

Spec §3.E remote-reuse row now reads `git worktree add --no-track -b <B> <wt> origin/<B>` + `branch.<B>.{remote,merge}` with the reason and journal 59d279fcdb7d; 03.yaml P3.T1.S1 text updated likewise (text only, state untouched; fr validate artifacts clean).

<!-- fr:journal kind=finding scope=plan id=p3-f8 created=2026-09-23T02:31:21 phase=3 state=refuted -->
### p3-f8 · finding [refuted] · single-branch clone: <B>@{u} does not resolve — do not add a remote.origin.fetch refspec (phase 3)

Not changed, by design. Verified on git 2.53 in a --single-branch clone after the remote row: `git rev-parse --abbrev-ref @{u}` fails ('upstream branch refs/heads/feat/x not stored as a remote-tracking branch', exit 128) and `git status -sb` shows no ahead/behind, but `git pull --ff-only` works (branch.<B>.remote/merge are set). Making @{u} resolve needs a remote.origin.fetch refspec, which rewrites repo-wide config beyond this branch — rejected. Limitation accepted and recorded here.

<!-- fr:journal kind=finding scope=plan id=p3-f9 created=2026-09-23T02:31:21 phase=3 state=fixed -->
### p3-f9 · finding [fixed] · unknown/unfetched reasons omitted git's stderr (phase 3)

`_why(what, result)` → '<what> exited <rc>: <last non-empty stderr line>'; used for ls-remote, the refspec fetch and git config failures. Test: tests/unit/test_isolation_branch_classify.py::test_remote_exists_but_fetch_fails_without_ref_is_refused asserts 'git fetch exited 1: fatal: simulated failure'.

<!-- fr:journal kind=finding scope=plan id=p3-f10 created=2026-09-23T02:31:21 phase=3 state=fixed -->
### p3-f10 · finding [fixed] · diverged hint suggested --ff-only, which cannot succeed (phase 3)

Diverged now suggests `git -C <wt> merge origin/<B>`; strictly behind keeps `merge --ff-only`. Tests: tests/unit/test_isolation_branch_classify.py::test_local_branch_diverged_used_with_warning (asserts merge hint, no --ff-only), ::test_local_branch_behind_used_with_warning_never_rebased.

<!-- fr:journal kind=finding scope=plan id=p3-f11 created=2026-09-23T02:31:22 phase=3 state=fixed -->
### p3-f11 · finding [fixed] · test git config not hermetic (phase 3)

Autouse fixtures in tests/unit/test_isolation_branch_classify.py and tests/integration/test_up_branch_reuses_origin.py set HOME, GIT_CONFIG_NOSYSTEM=1, GIT_CONFIG_GLOBAL (empty file) and XDG_CONFIG_HOME under tmp_path, and unset GIT_SSH_COMMAND/GIT_SSH.

<!-- fr:journal kind=finding scope=plan id=p3-f12 created=2026-09-23T02:31:22 phase=3 state=fixed -->
### p3-f12 · finding [fixed] · --no-fetch/no-origin ordering and wording (phase 3)

`_remote_view` checks `_has_origin_remote()` first (no origin → absent, output unchanged); --no-fetch without a local origin/<B> ref is a new `unchecked` state: local <B> prints '(origin not checked: --no-fetch)', a cold start prints the soft 'isolation: origin/<B> not checked (--no-fetch, no local ref) — starting a new branch' instead of the second-history WARNING. Tests: tests/unit/test_isolation_branch_classify.py::test_no_fetch_without_origin_ref_is_a_soft_line, ::test_no_origin_output_unchanged.
