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

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-09-23T02:40:56 phase=3 -->
### p3-review · review · Phase 3 review (independent reviewer): 1 major, 6 minor, 5 nits (phase 3)

Departure (a) --no-track + manual upstream accepted (reproduced git 2.53 refusal). p3-f1 (confirmed-but-unfetched cold start = #438 again) fixed by refusing; p3-f2..f7, f9..f12 fixed with tests; p3-f8 refuted (no repo-wide fetch refspec rewrite; limitation recorded). 563392ab; isolation suites re-run by orchestrator.

<!-- fr:journal kind=discovery scope=plan id=cf0f06832b13 created=2026-09-23T02:53:59 phase=4 -->
### cf0f06832b13 · discovery · P4.T3 refactor: one refusal-naming helper from the start (phase 4)

Refactored, not no-refactor: `preserve.name_runs(runs, refusal)` is the single prefixing helper; `_down_worktree_tail` and `down_refusal` both call it (runs computed once per call via `branch_runs`). `held_runs(state)` (pure query on the target, `preserve.runs_line`) feeds the `down --all` blast radius so the line shows under --force too.

<!-- fr:journal kind=discovery scope=plan id=5eda16e6d196 created=2026-09-23T02:54:00 phase=4 -->
### 5eda16e6d196 · discovery · Deviation: stage copies into staging/, commit promotes into files/ (phase 4)

Spec §3.D.2 says stage copies into `files/`. Built as `<preserved>/staging/` (cleared at each stage) promoted into `files/` by `commit` after the verified removal. Reason: on a SECOND teardown whose removal then fails, copying straight into `files/` would overwrite the prior snapshot while its tombstone still records the old base_blob, so a later restore could overwrite on a stale base. Staging keeps "files/ and teardown.json always agree". A failed down still leaves the copies (in staging/) and no new tombstone, as the spec requires.

<!-- fr:journal kind=discovery scope=plan id=eb6c376495b8 created=2026-09-23T02:54:00 phase=4 -->
### eb6c376495b8 · discovery · Decisions the spec leaves open in preserve (as built) (phase 4)

(1) branch_runs: a mapping with NO `branch` key is schema-foreign -> kept as active+unreadable; a mapping whose branch differs is excluded; `steps` not a mapping of mappings on a matching branch -> unreadable. id = `run` field else file stem; cursor = `cursor` else `?`. Line: `holds run <id> at step <cursor>` (+ ` (unreadable run file <file>)`), one line per active run, as the first line(s) of the refusal. (2) restore is skipped once the tombstone carries `restored_at`; a new teardown drops it. (3) the `restored N` count is copied/overwritten files only; re-applied deletions are silent; each conflict gets its own stderr line naming the cache copy. (4) a deletion base_blob is not stored: restore derives it as `git rev-parse <tombstone head>:<path>`, keeping the §3.D schema. (5) a commit() failure AFTER the verified removal is a stderr WARNING naming staging/, never a raise (worktree already gone; raising would strand state). (6) `preserve=False` without `force` is refused at the target as well as the CLI. (7) `down --all` also accepts `--force --no-preserve`. (8) a gc reap GcAction detail carries `ended run <id> at step <c> — record preserved at <dir>`.

<!-- fr:journal kind=discovery scope=plan id=71d6e81c74d0 created=2026-09-23T02:54:01 phase=4 -->
### 71d6e81c74d0 · discovery · Forced down of a tree git cannot read now needs --no-preserve (phase 4)

stage() runs `git status --porcelain=v1 -z -uall`; when it fails (dir exists, not a git checkout) the down aborts with the workspace intact and the message names `--force --no-preserve`, the spec escape for an unreadable tree. tests/unit/test_isolation.py::test_down_raises_when_worktree_remove_fails updated: force=True now refuses naming --no-preserve; force=True+preserve=False reaches the worktree-remove post-condition it targets.

<!-- fr:journal kind=discovery scope=plan id=c1fec7563b6c created=2026-09-23T02:54:01 phase=4 -->
### c1fec7563b6c · discovery · Phase 6 owes: fr-isolation SKILL.md --force sentence (phase 4)

plugins/super-fr/skills/fr-isolation/SKILL.md (~line 110) still reads "uncommitted changes do not." The code sentence (_hazard_detail, down --force help) now adds "except fr's own records under docs/superpowers/, which are preserved and restored by the next up", and `--no-preserve` exists. Left for 06.yaml (skills/docs + both mirror syncs) per the plan split.

<!-- fr:journal kind=discovery scope=plan id=83e667284b0b created=2026-09-23T03:00:44 phase=4 -->
### 83e667284b0b · discovery · phase-4 acceptance row left not-implemented for phase 6 (phase 4)

isolation-down-preserves-run stays not-implemented, matching phases 2/3 (8af43aee8ee9, 3f54c04d7371): 06.yaml flips rows after the live walks, and the #575 integration walk (spec Test Plan 9) is phase 5. Unit refs to cite then: tests/unit/test_isolation_preserve.py (discovery, refusal naming, stage/commit, restore, gc keying, CLI lines).

<!-- fr:journal kind=finding scope=plan id=p4-f1 created=2026-09-23T03:15:41 phase=4 state=fixed -->
### p4-f1 · finding [fixed] · A teardown merged into an already-restored tombstone (phase 4)

commit() starts fresh (files/ moved aside, lists emptied) when the prior tombstone has restored_at; only an unrestored one merges. tests/unit/test_isolation_preserve.py::test_p4_f1_down_after_a_restore_starts_a_fresh_tombstone (down, up, commit fixes, down, up).

<!-- fr:journal kind=finding scope=plan id=p4-f2 created=2026-09-23T03:15:41 phase=4 state=fixed -->
### p4-f2 · finding [fixed] · Partial worktree remove + retry destroyed the staged cursor (phase 4)

staging/stage.json (head, runs, files, deleted, removal_attempted) is written at stage time; mark_removal_attempted() flips it just before git worktree remove. A protected staging/ is never rmtree'd; a retry merges (new copies win per path, earlier kept), keeps the first attempt's deleted/runs, adds no new deletions, and ended_runs is the union. tests/unit/test_isolation_preserve.py::test_p4_f2_partial_remove_then_retry_keeps_the_staged_cursor.

<!-- fr:journal kind=finding scope=plan id=p4-f3 created=2026-09-23T03:15:41 phase=4 state=fixed -->
### p4-f3 · finding [fixed] · Gitignored cursor claimed preserved but never copied (phase 4)

porcelain now runs with --ignored=matching limited to docs/superpowers (ignored dirs walked), and every run file branch_runs returned is copied whether listed or not (base_blob HEAD:<file> or null). TeardownReport.unpreserved_runs lists active runs whose file was not copied and the CLI never says preserved for them. tests/unit/test_isolation_preserve.py::test_p4_f3_a_gitignored_cursor_is_preserved.

<!-- fr:journal kind=finding scope=plan id=p4-f4 created=2026-09-23T03:15:42 phase=4 state=fixed -->
### p4-f4 · finding [fixed] · Failed commit left staging unprotected and blamed --no-preserve (phase 4)

TeardownReport.reason (NO_PRESERVE or 'could not record the teardown (...); the staged copies are at <staging>'); CLI prints it instead of the --no-preserve text; restore() prints a notice pointing at an unpromoted protected staging/; the next down merges it; promotion uses os.replace. tests/unit/test_isolation_preserve.py::test_p4_f4_failed_commit_keeps_staging_says_why_and_is_found_again.

<!-- fr:journal kind=finding scope=plan id=p4-f5 created=2026-09-23T03:15:42 phase=4 state=fixed -->
### p4-f5 · finding [fixed] · Cold-start re-creation of the branch name passed the descendant guard (phase 4)

_git_worktree_add passes new_branch=True on the cold-start path; restore then restores nothing and prints the preserved dir plus a cp -R command. tests/unit/test_isolation_preserve.py::test_p4_f5_cold_start_recreation_does_not_restore; the up spy asserts new_branch=False for an existing branch.

<!-- fr:journal kind=finding scope=plan id=p4-f6 created=2026-09-23T03:15:43 phase=4 state=fixed -->
### p4-f6 · finding [fixed] · A rename lost its source half (phase 4)

The -z rename source under docs/superpowers/ is recorded in deleted (copies keep their source). tests/unit/test_isolation_preserve.py::test_p4_f6_rename_source_is_not_resurrected (path with a space and newline).

<!-- fr:journal kind=finding scope=plan id=p4-f7 created=2026-09-23T03:15:43 phase=4 state=fixed -->
### p4-f7 · finding [fixed] · Non-regular entries aborted down --force (phase 4)

Symlinks (dangling or to a dir) and nested repositories are skipped, never followed, never fatal, and listed in TeardownReport.skipped / a 'down: not preserved (not a regular file)' line. tests/unit/test_isolation_preserve.py::test_p4_f7_non_regular_entries_are_skipped_not_fatal.

<!-- fr:journal kind=finding scope=plan id=p4-f8 created=2026-09-23T03:15:44 phase=4 state=fixed -->
### p4-f8 · finding [fixed] · Descendant guard lacked a vanished-head check (phase 4)

restore runs git cat-file -e <head>^{commit} first, with its own 'no longer exists in this repo' notice. tests/unit/test_isolation_preserve.py::test_p4_f8_a_vanished_head_is_named_and_nothing_restored.

<!-- fr:journal kind=finding scope=plan id=p4-f9 created=2026-09-23T03:15:44 phase=4 state=fixed -->
### p4-f9 · finding [fixed] · Tombstone written after staging was removed (phase 4)

commit promotes, writes teardown.json atomically (write_text_atomic), and only then removes staging/ and files.old/. tests/unit/test_isolation_preserve.py::test_p4_f9_tombstone_is_written_before_staging_is_removed.

<!-- fr:journal kind=finding scope=plan id=p4-f10 created=2026-09-23T03:15:45 phase=4 state=fixed -->
### p4-f10 · finding [fixed] · git status failure forced --no-preserve (phase 4)

When git status fails on an existing dir, stage falls back to a git-less copy of docs/superpowers/** with base_blob null (restore only fills absent paths or reports a conflict). tests/unit/test_isolation_preserve.py::test_p4_f10_git_less_fallback_when_status_fails; test_isolation.py::test_down_raises_when_worktree_remove_fails reverted to force=True alone.

<!-- fr:journal kind=finding scope=plan id=p4-f11 created=2026-09-23T03:15:45 phase=4 state=fixed -->
### p4-f11 · finding [fixed] · Tombstones for clean downs and a 'restored 0' line (phase 4)

PreserveRecord.worthwhile = a changed file, a deletion or an active run; otherwise no staging and no tombstone (committed-unchanged run files are copied but flagged changed=False). The restored line prints only when N>0. tests/unit/test_isolation_preserve.py::test_p4_f11_clean_down_and_identical_restore_are_silent.

<!-- fr:journal kind=finding scope=plan id=p4-f12 created=2026-09-23T03:15:45 phase=4 state=fixed -->
### p4-f12 · finding [fixed] · Undecodable porcelain raised a raw UnicodeDecodeError (phase 4)

_porcelain catches it and raises IsolationError naming --force --no-preserve. tests/unit/test_isolation_preserve.py::test_p4_f12_undecodable_porcelain_is_an_isolation_error.

<!-- fr:journal kind=finding scope=plan id=p4-f13 created=2026-09-23T03:15:46 phase=4 state=fixed -->
### p4-f13 · finding [fixed] · ExternalTarget.down accepted preserve=False without force (phase 4)

Refused with the same rule as the other targets. tests/unit/test_isolation_preserve.py::test_p4_f13_external_down_refuses_no_preserve_without_force.

<!-- fr:journal kind=finding scope=plan id=p4-f14 created=2026-09-23T03:15:46 phase=4 state=fixed -->
### p4-f14 · finding [fixed] · No line when files were preserved but no run was active (phase 4)

CLI prints 'down: preserved N file(s) at <dir>'. tests/unit/test_isolation_preserve.py::test_p4_f14_cli_names_preserved_files_without_a_run.

<!-- fr:journal kind=finding scope=plan id=p4-f15 created=2026-09-23T03:15:47 phase=4 state=fixed -->
### p4-f15 · finding [fixed] · Restore trusted tombstone paths (phase 4)

_safe() (TypeGuard) requires a relative path under docs/superpowers/ with no '..'; others are skipped with a stderr line, for files and deleted alike, and at merge time. tests/unit/test_isolation_preserve.py::test_p4_f15_restore_rejects_escaping_paths.

<!-- fr:journal kind=finding scope=plan id=p4-f16 created=2026-09-23T03:15:47 phase=4 state=fixed -->
### p4-f16 · finding [fixed] · Rename source-half assertion missing (phase 4)

test_force_down_preserves_only_docs_superpowers now asserts deleted == [gone.md, old.md]; test_p4_f6 checks the source is not resurrected after up.

<!-- fr:journal kind=decision scope=plan id=p4-d1 created=2026-09-23T03:36:57 -->
### p4-d1 · decision · Restore never deletes; recorded deletions are reported, not re-applied

Phase-4 re-review N1/N2 (and f1, f6 before them) all trace to restore re-applying recorded deletions: a stale or bogus deletion silently deletes a committed file. Orchestrator decision (safety over fidelity): restore only ever writes absent/base-blob-matching files; deletions stay in teardown.json and are listed on stderr as 'not re-deleted'. A resurrected file is visible and harmless; a vanished committed file is neither. Spec §3.D.4 updated accordingly.

<!-- fr:journal kind=finding scope=plan id=p4-n1 created=2026-09-23T03:41:47 phase=4 state=fixed -->
### p4-n1 · finding [fixed] · A clean tree got no staging protection (phase 4)

stage() writes stage.json for every preserving down (no files, no runs included) and mark_removal_attempted() creates it if missing, so the retry after a partial removal is always recognised and adds no deletions; commit() of an unworthy record removes staging and the empty dir. The n1 probe's outcome (committed spec re-deleted) is gone, also by p4-d1. tests/unit/test_isolation_preserve.py::test_p4_n1_clean_tree_partial_remove_is_protected.

<!-- fr:journal kind=finding scope=plan id=p4-n2 created=2026-09-23T03:41:48 phase=4 state=fixed -->
### p4-n2 · finding [fixed] · A retry on an intact tree merged stale entries (phase 4)

_merge_prior keeps an earlier file entry only when the path is absent or unreadable in the tree (the tree wins otherwise), keeps an earlier deletion only while the path is still absent, and an earlier run only when its file is gone; paths that came only from the earlier attempt are never re-copied; each snapshot keeps its own base_blob. tests/unit/test_isolation_preserve.py::test_p4_n2_intact_retry_drops_stale_staged_entries.

<!-- fr:journal kind=finding scope=plan id=p4-n3 created=2026-09-23T03:41:48 phase=4 state=fixed -->
### p4-n3 · finding [fixed] · A declined tombstone was merged back by the next teardown (phase 4)

restore() declines (cold start, non-descendant, vanished or null head) by moving the preserved dir to preserved/<branch>@<UTC> with declined_at, naming it in the notice; commit() starts fresh whenever the prior head is null or not an ancestor of record.head (git --git-dir=<common> merge-base --is-ancestor). tests/unit/test_isolation_preserve.py::test_p4_n3_a_declined_tombstone_is_moved_aside, ::test_p4_n3_commit_starts_fresh_over_an_unrelated_prior_head; test_restore_refuses_a_non_descendant_head and test_p4_f5 now read the moved-aside dir.

<!-- fr:journal kind=finding scope=plan id=p4-n4 created=2026-09-23T03:41:49 phase=4 state=fixed -->
### p4-n4 · finding [fixed] · The git-less fallback nulled the head (phase 4)

commit() keeps the prior head when record.head is None and then merges (the one reading of n3's 'either is null' that honours n4: a null PRIOR head starts fresh, a null record head inherits); restore() treats a null head like a vanished one (declined, moved aside). tests/unit/test_isolation_preserve.py::test_p4_n4_commit_keeps_the_prior_head_when_git_less, ::test_p4_n4_null_head_restores_nothing_and_moves_aside.

<!-- fr:journal kind=finding scope=plan id=p4-n5 created=2026-09-23T03:41:49 phase=4 state=fixed -->
### p4-n5 · finding [fixed] · A crash between promotion and tombstone write lost copies (phase 4)

_merge_prior also accepts a copy at <root>/files/<path> that no tombstone lists (and commit leaves it in place). tests/unit/test_isolation_preserve.py::test_p4_n5_a_promoted_but_unrecorded_copy_survives_a_retry.

<!-- fr:journal kind=finding scope=plan id=p4-n6 created=2026-09-23T03:41:50 phase=4 state=fixed -->
### p4-n6 · finding [fixed] · Ignored caches, unbounded ignored copies, symlinked restore destinations (phase 4)

walk() skips .venv, __pycache__, node_modules, .pytest_cache, .mypy_cache, .ruff_cache (and a match that IS one); ignored files are capped at 50 MB in total, the rest listed in skipped with the reason (run files bypass the cap); restore refuses a destination whose resolved path is not under worktree.resolve(). tests/unit/test_isolation_preserve.py::test_p4_n6_ignored_caches_and_oversize_are_skipped, ::test_p4_n6_restore_refuses_a_destination_outside_the_worktree.

<!-- fr:journal kind=discovery scope=plan id=a6146db3145b created=2026-09-23T03:41:50 phase=4 -->
### a6146db3145b · discovery · p4-d1 applied: restore never deletes (phase 4)

Deletion re-application and its restore-time base-blob lookup removed; recorded deletions still present in the checkout are reported as 'isolation: N path(s) deleted before teardown were not re-deleted: <paths>' (RestoreResult.not_redeleted). Tests updated: test_restore_absent_copied_base_blob_overwritten_deletion_reported, test_p4_f1 (F survives the first up), test_p4_f6_rename_source_is_recorded_and_reported; new test_p4_d1_restore_never_deletes_and_reports_it. Spec §3.D.4 deletion bullet rewritten, the decline bullet widened (null/vanished head, cold start, moved aside), and a §4 Risks line added.

<!-- fr:journal kind=finding scope=plan id=p4-n7 created=2026-09-23T03:57:05 phase=4 state=fixed -->
### p4-n7 · finding [fixed] · A fresh commit over an unrestored tombstone deleted the only preserved copy (phase 4)

Invariant stated in preserve.py's module docstring and at each site: nothing deletes preserved data (a tombstone and the files/ it lists) unless that tombstone carries restored_at. commit() now sets an unrestored prior aside via _set_aside (<branch>@<UTC>, set_aside_reason lineage-break | null-prior-head, staging/ kept live) instead of files -> files.old -> rmtree; files.old is only used and removed for a restored prior, and an existing files.old (interrupted commit) is no longer rmtree'd; a later deletion no longer unlinks a preserved copy (the copy stays listed, deletion recorded only for unpreserved paths). _decline shares _set_aside. Tests: tests/unit/test_isolation_preserve.py::test_p4_n7_fresh_commit_over_an_unrestored_tombstone_sets_it_aside (the n7 probe), ::test_p4_n7_no_rmtree_touches_an_unrestored_record_on_the_fresh_path (spies shutil.rmtree and Path.unlink; only root/staging may be touched).

<!-- fr:journal kind=finding scope=plan id=p4-n8 created=2026-09-23T03:57:06 phase=4 state=fixed -->
### p4-n8 · finding [fixed] · The unfinished-teardown notice promised a merge after the decline had moved staging (phase 4)

restore() prints the notice after deciding: with the live path and 'the next fr isolation down merges them' when not declined, with <branch>@<UTC>/staging/files and 'set aside with the declined record and will not be merged' when declined. Tests: tests/unit/test_isolation_preserve.py::test_p4_n8_the_unfinished_teardown_notice_is_true_after_a_decline; test_p4_f4 now asserts 'merges them' on the non-declined path.

<!-- fr:journal kind=finding scope=plan id=p4-n9 created=2026-09-23T03:57:06 phase=4 state=fixed -->
### p4-n9 · finding [fixed] · The decline hint printed a literal <worktree> (phase 4)

_decline takes the real worktree; the hint is cp -R <aside>/files/. <worktree path>/. Test: tests/unit/test_isolation_preserve.py::test_p4_n9_the_decline_hint_names_the_real_worktree.

<!-- fr:journal kind=review scope=plan id=p4-review created=2026-09-23T04:06:50 phase=4 -->
### p4-review · review · Phase 4 review (independent reviewer, 3 rounds): 4+3+1 majors, all closed (phase 4)

Round 1: p4-f1..f16 (4 major data-loss holes, each reproduced by probe) fixed in a4790043. Round 2 re-verify: p4-n1..n6 (3 majors) + orchestrator decision p4-d1 (restore never deletes) fixed in fb3ce370. Round 3 re-verify: p4-n7 (fresh commit deleted an unrestored record) + n8/n9 fixed in 7540e57e with the invariant 'nothing deletes preserved data unless restored_at'. Orchestrator audited all 5 deletion sites in preserve.py against it. Reviewer: no other path found where down --force loses an uncommitted docs/superpowers file or up writes content the operator did not have.

<!-- fr:journal kind=discovery scope=plan id=a99bdd74ec5d created=2026-09-23T04:19:34 phase=5 -->
### a99bdd74ec5d · discovery · explain_missing: set-aside records are named, never promised to up (phase 5)

Decision (spec §3.D.5 lists three answers; built four). A tombstone carrying `set_aside_at` or `declined_at` (`<branch>@<UTC>/`) is NOT a live tombstone — `restore` never reads it — so it is not offered as `fr isolation up --branch`. But it still holds the run, so the never-existed text ("fr has no record of one") would be false. Checked after live tombstones and before never-existed: `<torn-down head>; its preserved record was set aside at <dir> (<reason>) and is not restored automatically; its copy is <dir>/files/<run file>.` Classified by tombstone content, not by the `@` in the dir name.

<!-- fr:journal kind=discovery scope=plan id=7aae8ece5011 created=2026-09-23T04:19:35 phase=5 -->
### 7aae8ece5011 · discovery · explain_missing: preserved vs committed, and restored tombstones (phase 5)

preserved = the tombstone is unrestored, holds `files/<run file>`, and that copy's git blob id (computed in Python: sha1 for a 40-hex base, sha256 for 64) differs from the recorded `base_blob` (or base is null). Everything else that lists the run reads "committed": a committed-unchanged cursor copied under p4-f3, and a RESTORED tombstone (restore skips it, so promising a restore would be false). Newest `torn_down_at` wins among several. Live workspaces come from the isolation state dir, read per file tolerantly; the caller's own checkout is skipped. The function never raises — any exception falls through to the never-existed text.

<!-- fr:journal kind=discovery scope=plan id=f1edd9204591 created=2026-09-23T04:19:35 phase=5 -->
### f1edd9204591 · discovery · P5.T2 refactor: one load path (phase 5)

Refactored during green: the three direct `load_run_state` call sites (advance, resolve, claim) now call `_load_or_exit` inside their existing try (typer.Exit passes through their except), so there is ONE load path and one missing-run message (`_missing_run_exit`: lazy import of `fr.isolation.preserve.explain_missing`, soft_wrap, exit 2). `load_run_state` untouched. Side effect: parse errors at those sites now print soft_wrap like the rest. `fr run start`'s same-id refusal ("run r1 already exists") now also prints `inspect it: fr run status <id>` / `resume it: fr run advance <id>`, matching the second-run refusal — after a restore the derived id usually collides first, so this is the refusal an operator actually meets.

<!-- fr:journal kind=discovery scope=plan id=a685cf24b981 created=2026-09-23T04:19:36 phase=5 -->
### a685cf24b981 · discovery · Integration walk uses a 3-step custom shape, not fr-goal (phase 5)

tests/integration/test_run_survives_teardown.py drives the real CLI (CliRunner, real git, FR_ISOLATION_TARGET=worktree, hermetic HOME/GIT_CONFIG_*, isolation_cmd._runner fakes gh as no-PR) with a shipped-dir shape `walk` (cli one, cli two, agent three) instead of `fr run start fr-goal`: fr-goal starts on an agent step, and the walk needs a deterministic committed→advanced→dirty cursor. Pinned: `holds run r1 at step two`, the `down: ended run r1 at step two here — its record is preserved at <dir>; ...` line, the full torn-down message from `fr run advance r1` in the base clone (exit 2, no run file written), `isolation: restored 1 preserved file(s) (run r1 at two)`, status reads cursor `two`, a re-start names `fr run advance r1`.

<!-- fr:journal kind=discovery scope=plan id=85815977c916 created=2026-09-23T04:27:01 phase=5 -->
### 85815977c916 · discovery · phase-5 acceptance rows left not-implemented for phase 6 (phase 5)

run-missing-explains-teardown and isolation-down-preserves-run stay not-implemented, matching phases 2-4 (8af43aee8ee9, 3f54c04d7371, 83e667284b0b): 06.yaml flips rows after the live walks. Refs to cite then: tests/unit/test_isolation_explain_missing.py (every order, set-aside, never-raises), tests/unit/test_run_cli.py::test_a_missing_run_is_explained_at_every_load_site and ::test_start_refusing_an_existing_run_id_names_advance, tests/integration/test_run_survives_teardown.py (the #575 acceptance-4 walk).

<!-- fr:journal kind=finding scope=plan id=p5-f1 created=2026-09-23T04:37:54 phase=5 state=fixed -->
### p5-f1 · finding [fixed] · Unfinished teardown answered 'fr has no record' (phase 5)

Verified: with preserve.commit raising during down --force, only staging/stage.json (removal_attempted) remains and explain_missing said never-existed. Fixed: every preserved dir's staging/stage.json is checked after live tombstones, before set-aside; the message says the teardown was never recorded, names <dir>/staging/files/<run file>, and "copy it back, or the next `fr isolation down --branch <b>` merges it" (the set-aside wording when the dir's tombstone is set aside). Test: test_p5_f1_an_unrecorded_teardown_names_the_staged_copy.

<!-- fr:journal kind=finding scope=plan id=p5-f2 created=2026-09-23T04:37:55 phase=5 state=fixed -->
### p5-f2 · finding [fixed] · _cursor_preserved hashed raw worktree bytes against git's clean blob (phase 5)

Verified (CRLF: `* text eol=crlf` with a committed CRLF cursor, raw-bytes SHA-1 != LF-normalised blob). Fixed: commit persists `changed` in teardown.json files entries (prior entries keep theirs; stage.json/_merge_prior already carried it); explain_missing reads it and falls back to raw blob comparison only when the key is absent. Tests: test_p5_f2_a_filtered_committed_cursor_reads_committed (CRLF), test_p5_f2_without_changed_the_blob_fallback_handles_sha256 (same/different, 64-hex base).

<!-- fr:journal kind=finding scope=plan id=p5-f3 created=2026-09-23T04:37:55 phase=5 state=fixed -->
### p5-f3 · finding [fixed] · 'committed on <b>' was the fallback for every non-preserved case (phase 5)

Fixed: "committed" only for a files entry with non-null base_blob and changed false (or fallback blob-equal); a restored tombstone says "its record was restored into a workspace at <restored_at>; if that workspace is gone, what survives is what <b> committed"; no files entry or no copy says "fr kept no copy of its record". Tests: test_p5_f3_a_restored_tombstone_says_restored_not_committed (no-preserve dirty down after a restore), test_p5_f3_a_tombstone_with_no_copy_says_so.

<!-- fr:journal kind=finding scope=plan id=p5-f4 created=2026-09-23T04:37:56 phase=5 state=fixed -->
### p5-f4 · finding [fixed] · 'up … restores it' promised when restore would decline (phase 5)

Fixed: before promising, `git cat-file -e <head>^{commit}` and `show-ref --verify refs/heads/<b>` or `refs/remotes/origin/<b>`; on failure the message gives <dir>/files/<file> and says up "will not restore it automatically (<why>)". Not a full descendant check (that needs the post-up HEAD). Tests: test_p5_f4_a_deleted_branch_is_not_promised_a_restore, test_p5_f4_a_vanished_head_is_not_promised_a_restore.

<!-- fr:journal kind=finding scope=plan id=p5-f5 created=2026-09-23T04:37:56 phase=5 state=fixed -->
### p5-f5 · finding [fixed] · run check --idle missing from the load-site parametrization (phase 5)

Added `check-idle` case; it passed on arrival (check already used _load_or_exit) — now pinned.

<!-- fr:journal kind=finding scope=plan id=p5-f6 created=2026-09-23T04:37:57 phase=5 state=fixed -->
### p5-f6 · finding [fixed] · No set-aside test with set_aside_reason (phase 5)

Added test_p5_f6_a_lineage_break_set_aside_names_its_reason; passed on arrival (reason was already rendered) — now pinned.

<!-- fr:journal kind=finding scope=plan id=p5-f7 created=2026-09-23T04:37:57 phase=5 state=fixed -->
### p5-f7 · finding [fixed] · _live_holder returned the first holder regardless of the run file's branch (phase 5)

Verified red (sorted state files put feat__a-other first). Fixed: holders whose run file names their own branch win, else the first. Test: test_p5_f7_the_holder_on_the_runs_own_branch_wins.

<!-- fr:journal kind=finding scope=plan id=p5-f8 created=2026-09-23T04:37:57 phase=5 state=fixed -->
### p5-f8 · finding [fixed] · Tombstone partition used a tuple-membership test (phase 5)

Fixed: one pass, one predicate (_is_set_aside) splits listing into live/aside. Refactor only; covered by the existing ordering and set-aside tests.

<!-- fr:journal kind=finding scope=plan id=p5-f9 created=2026-09-23T04:37:58 phase=5 state=fixed -->
### p5-f9 · finding [fixed] · _load_or_exit used is_file for the missing check (phase 5)

Fixed: `not path.exists()`, OSError branch kept. No dedicated test: the only behavioural difference is a directory at the run path, which now reports via load_run_state's RunStateError instead of the explanation.

<!-- fr:journal kind=discovery scope=plan id=e9c5d1f3c8ae created=2026-09-23T04:37:58 phase=5 -->
### e9c5d1f3c8ae · discovery · Integration walk leaves fr-goal's shipped manifest unexercised after a restore (phase 5)

test_run_survives_teardown.py uses the custom `walk` shape, so no test yet advances the SHIPPED fr-goal manifest on a restored cursor (manifest resolution, gates, agent-step briefs after restore). Phase 6's live walk covers it.

<!-- fr:journal kind=review scope=plan id=p5-review created=2026-09-23T04:47:04 phase=5 -->
### p5-review · review · Phase 5 review (independent reviewer): 1 major, 3 minor, 5 nits — all fixed (phase 5)

p5-f1 (crashed teardown answered 'no record') fixed with an unfinished-teardown answer; p5-f2..f4 truthfulness of preserved/committed/restore claims fixed (persisted git-computed 'changed' flag, restored-tombstone wording, branch/head reachability check); p5-f5..f9 nits fixed. Decisions a99bdd74ec5d, a685cf24b981 accepted; 7aae8ece5011 corrected by f2. 09a89293; suites re-run by orchestrator.

<!-- fr:journal kind=discovery scope=plan id=p6-live-471 created=2026-09-23T04:52:27 phase=6 -->
### p6-live-471 · discovery · Live walk #471: stop -> status stopped -> exec auto-resumes, install survives (phase 6)

Live walk, 2026-09-23, this host (macOS + Docker), `dev` profile, `uv run fr` from the fix/lifecycle-container-vs-worktree worktree (fr 4.18.0), throwaway workspace `tmp/lifecycle-live-walk` (never pushed). Spec Test Plan 13 / #471 acceptance 1-3.

```
$ fr isolation up --branch tmp/lifecycle-live-walk
isolation: basing new branch tmp/lifecycle-live-walk on origin/main (fetched) (1ba61de23e6d)
isolation up: worktree=~/.cache/fr/worktrees/super-fr/tmp__lifecycle-live-walk profile=dev branch=tmp/lifecycle-live-walk
$ fr isolation exec --branch tmp/lifecycle-live-walk -- sh -c 'sudo sh -c "printf ... > /usr/local/bin/fr-walk-probe && chmod +x ..." && fr-walk-probe'
live-walk-471 installed                       # in-container install, outside the worktree
$ fr isolation status --branch tmp/lifecycle-live-walk
tmp/lifecycle-live-walk: profile=dev container=running ...
$ fr isolation stop --branch tmp/lifecycle-live-walk
isolation stop: tmp/lifecycle-live-walk stopped (db403085c3ff) — worktree, state and bindings kept; `fr isolation up`, `restart` or the next `exec` resumes it.
$ fr isolation status --branch tmp/lifecycle-live-walk
tmp/lifecycle-live-walk: profile=dev container=stopped ...
$ fr isolation exec --branch tmp/lifecycle-live-walk -- fr-walk-probe
isolation: container for tmp/lifecycle-live-walk was stopped — resuming (devcontainer up)     # stderr
live-walk-471 installed                                                                       # the install survived
$ fr isolation status --branch tmp/lifecycle-live-walk
tmp/lifecycle-live-walk: profile=dev container=running ...
$ docker ps --filter id=db403085c3ff   ->  db403085c3ff Up 6 seconds   # same container, resumed not recreated
```

All three #471 acceptances hold live: stop frees the container and status reads `stopped`; exec auto-resumes with the stderr notice; an in-container install survives stop/resume.

<!-- fr:journal kind=discovery scope=plan id=p6-live-577 created=2026-09-23T04:58:50 phase=6 -->
### p6-live-577 · discovery · Live walk #577: rebuild applies a new feature; scratch file and run cursor survive (phase 6)

Live walk, 2026-09-23, this host (macOS + Docker), `dev` profile, fr 4.18.0 from this worktree, same throwaway `tmp/lifecycle-live-walk` (never pushed). Spec Test Plan 12 / #577 acceptance 1-2. The run was started INSIDE the throwaway (`fr run start` refuses from inside a workspace of another branch: "this workspace is isolated for branch 'fix/…', not 'tmp/…' — … run `fr run start` from outside the workspace").

```
$ cd ~/.cache/fr/worktrees/super-fr/tmp__lifecycle-live-walk
$ fr run start fr-goal --branch tmp/lifecycle-live-walk
started run 2026-09-23-tmp-lifecycle-live-walk (fr-goal@1) — cursor: brainstorm
$ fr run advance 2026-09-23-tmp-lifecycle-live-walk      # brainstorm: blocked on operator gate
$ echo "uncommitted scratch, live walk #577" > scratch-live-walk.txt
$ fr isolation exec … -- sh -c 'command -v node || echo "node: absent"'
node: absent
# add "ghcr.io/devcontainers/features/node:1": {"version": "lts"} to .devcontainer/dev/devcontainer.json (uncommitted)
$ fr isolation rebuild --branch tmp/lifecycle-live-walk
isolation rebuild: tmp/lifecycle-live-walk recreated (db403085c3ff → ca1f21ea6b4f) from …/tmp__lifecycle-live-walk/.devcontainer/dev/devcontainer.json; worktree untouched
$ fr isolation exec … -- sh -c 'node --version; command -v fr-walk-probe || echo gone; cat scratch-live-walk.txt'
v24.21.0                                   # the new feature's tool answers
fr-walk-probe: gone (container recreated)  # the #471 install did not survive a rebuild — as the skill table says
uncommitted scratch, live walk #577        # the scratch file survived
$ git status --short
 M .devcontainer/dev/devcontainer-lock.json   # devcontainer CLI writes the lock beside the profile
 M .devcontainer/dev/devcontainer.json
?? docs/superpowers/runs/2026-09-23-tmp-lifecycle-live-walk.yaml
?? scratch-live-walk.txt
$ fr run status 2026-09-23-tmp-lifecycle-live-walk
cursor: brainstorm / brainstorm: blocked          # cursor intact
# revert the profile (git checkout -- both files), rebuild again:
isolation rebuild: tmp/lifecycle-live-walk recreated (ca1f21ea6b4f → eba2355df529) …; worktree untouched
```

Both rebuilds also printed `warning: could not remove image sha256:… (shared or in use?): … No such image` — see finding p6-f1 (fixed in this phase).

<!-- fr:journal kind=discovery scope=plan id=p6-live-575 created=2026-09-23T04:58:51 phase=6 -->
### p6-live-575 · discovery · Live walk #575: down refuses naming the run, --force preserves, advance explains, up restores, shipped fr-goal advances (phase 6)

Live walk, 2026-09-23, same throwaway after the #577 walk (fr 4.18.0 from this worktree). #575 acceptance 1-4 end to end, including the SHIPPED fr-goal manifest advancing on a restored cursor (closes the gap e9c5d1f3c8ae named).

```
# in the throwaway: commit the cursor locally (never pushed), then move it
$ git commit -m "tmp: live-walk cursor (never pushed)"            # 28982a7b
$ fr run resolve 2026-09-23-tmp-lifecycle-live-walk --step brainstorm --state done --no-questions --reason "…" --emitted spec=docs/superpowers/specs/2026-09-23-tmp-live-walk-design.md
brainstorm: done                                                   # cursor → spec-review, run file now dirty
$ fr isolation down --branch tmp/lifecycle-live-walk              # rc=2
error: holds run 2026-09-23-tmp-lifecycle-live-walk at step spec-review
isolation: tmp/lifecycle-live-walk has 4 uncommitted change(s) — refusing to reap (nothing was deleted).
  docs/superpowers/runs/….yaml, docs/superpowers/journals/specs/….md, docs/superpowers/specs/….md, scratch-live-walk.txt
$ fr isolation down --branch tmp/lifecycle-live-walk --force      # rc=0
down: ended run 2026-09-23-tmp-lifecycle-live-walk at step spec-review here — its record is preserved at <repo>/.git/fr/preserved/tmp__lifecycle-live-walk; `fr isolation up --branch tmp/lifecycle-live-walk` restores it
isolation down: tmp/lifecycle-live-walk cleaned up.
# from the fix/lifecycle-container-vs-worktree worktree:
$ fr run advance 2026-09-23-tmp-lifecycle-live-walk               # rc=2 (run status: same text)
run 2026-09-23-tmp-lifecycle-live-walk is not in this checkout: its workspace for tmp/lifecycle-live-walk (~/.cache/fr/worktrees/super-fr/tmp__lifecycle-live-walk) was torn down at 2026-09-23T02:57:19Z; its record is preserved — `fr isolation up --branch tmp/lifecycle-live-walk` restores it, then run fr from there.
$ fr isolation up --branch tmp/lifecycle-live-walk
isolation: reusing local branch tmp/lifecycle-live-walk at 28982a7b2c19
isolation: restored 3 preserved file(s) (run 2026-09-23-tmp-lifecycle-live-walk at spec-review)
$ git status --short        # run file M, spec + spec journal ??; scratch-live-walk.txt gone (outside docs/superpowers — by design)
$ fr run status …           # cursor: spec-review, brainstorm: done — the ADVANCED cursor
$ fr run advance …          # shipped fr-goal@1 on the restored cursor:
spec-review: dispatch brief {"kind": "agent", "needs": ["spec"], "step": "spec-review", "workflow": "fr-goal@1", …}
                            # → spec-review: running
# teardown
$ fr isolation down --force --branch tmp/lifecycle-live-walk      # preserved again (active run), cleaned up
$ git branch -D tmp/lifecycle-live-walk; rm -rf <git-common-dir>/fr/preserved/tmp__lifecycle-live-walk
$ fr isolation status | grep -c lifecycle-live-walk  → 0; git worktree list → 0; docker ps -a → 0
```

Wording nit noticed, not changed (spec §3.D.1 fixes the prefix and tests pin it): the refusal's first line renders as `error: holds run <id> at step <s>` — the subject (the branch) is implied by the next line. Left for the orchestrator/reviewer.

<!-- fr:journal kind=finding scope=plan id=p6-f1 created=2026-09-23T04:58:51 phase=6 state=fixed -->
### p6-f1 · finding [fixed] · rebuild warned 'could not remove image (shared or in use?)' for an image already gone (phase 6)

Both live rebuilds (features profile) printed the warning with docker's 'No such image' — the old image id was already removed when fr ran rmi. _reclaim_image (local.py, shared with down) now treats 'No such image' as reclaimed and warns only for an image still present. Tests: tests/unit/test_isolation_container_verbs.py::TestRebuild::test_an_already_gone_old_image_is_not_a_warning and ::test_a_still_present_old_image_still_warns.
