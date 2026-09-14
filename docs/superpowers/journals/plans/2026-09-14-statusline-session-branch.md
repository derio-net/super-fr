# Journal: 2026-09-14-statusline-session-branch

<!-- fr:journal kind=discovery scope=plan id=858243a70dfe created=2026-09-14T22:01:23 phase=1 -->
### 858243a70dfe · discovery · P1.T1.S1 RED confirmed against the v1 segment (phase 1)

Rewrote tests/unit/test_statusline_segment.py for contract v2 (fixture kept, all v1 tests deleted, `_plain` + `NONE` + test_not_a_git_repo + test_missing_cwd added). Against the v1 script: `2 failed in 30.89s`, both with `AssertionError: plain output must be exactly three lines: '\n\n'` (v1 prints two empty lines for a non-repo cwd). After the v2 skeleton: `2 passed`.

<!-- fr:journal kind=decision scope=plan id=4ba9a412e844 created=2026-09-14T22:02:10 phase=1 -->
### 4ba9a412e844 · decision · Dropped the unused 'time' import from the v2 test module (phase 1)

P1.T1.S1 said "keep the imports", but deleting the v1 timing guard leaves `import time` unused and CI runs `ruff check packages/ tests/` (F401). Removed it so the phase commit is lint-clean. Phase 2 re-adds `time` when it restores the 0.5 s timing guard (spec §7).

<!-- fr:journal kind=finding scope=plan id=9881719eb4a1 created=2026-09-14T22:03:02 phase=1 state=fixed -->
### 9881719eb4a1 · finding [open] · shellcheck SC2034 on the skeleton: session_id and cwd unused until phase 2 (phase 1)

On the embedded v2 skeleton, `shellcheck plugins/super-fr/scripts/fr-statusline-segment.sh` gives rc=1 with two SC2034 warnings: `session_id` and `cwd` are read from stdin/--cwd, but no code uses them until the phase-2 resolution rules land. `bash -n` passes. No CI job or test runs shellcheck (grep over tests/, .github/, packages/), so nothing is gated. I added no `# shellcheck disable` lines, so the script matches the plan text. Phase 2 must re-run shellcheck and expect rc=0.

<!-- fr:journal kind=decision scope=plan id=865ef03fe54e created=2026-09-14T22:04:03 phase=1 -->
### 865ef03fe54e · decision · no-refactor-because: P1.T1 (phase 1)

no-refactor-because: P1.T1 — the GREEN script is the verbatim skeleton from the plan and the test module is the fixture plus two goldens. Nothing is duplicated to clean up. The only lint noise is SC2034 (see the open finding), and phase 2 removes it by using the variables.

<!-- fr:journal kind=finding scope=plan id=1a97c378d1be created=2026-09-14T22:39:05 phase=1 state=refuted -->
### 1a97c378d1be · finding [open] · Full-suite gate rc=1: tripwire flags an unarchived plan on origin/main (not this phase) (phase 1)

P1.T1.S3 full suite (devcontainer): `3 failed, 2886 passed, 85 skipped in 2095.77s`, rc=1, coverage 91.41% (gate 75% met). One failure is deterministic and comes from repo state: `tests/unit/test_tripwire_unarchived_plans.py::test_no_merged_but_unarchived_plans` reports `merged-but-unarchived plan(s) — complete on origin/main but still in docs/superpowers/plans/: ['2026-07-24-remove-vk-legacy-fallbacks']`. origin/main is at b257d34 (#408). The phase diff touches no plan-archive files. The fix is outside phase 1: someone must run `fr archive` for that plan on main, or rebase the branch after main archives it. CI on this branch will fail this tripwire until then.

<!-- fr:journal kind=finding scope=plan id=c48ecd9911fa created=2026-09-14T22:39:08 phase=1 state=refuted -->
### c48ecd9911fa · finding [open] · Full-suite gate rc=1: bridge install env failure + load timeout (not this phase) (phase 1)

The other two S3 failures come from the environment. (1) `tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper` fails every time: `ERROR: /home/vscode/.local/share/uv/tools/fr/bin/python cannot import fr_vk.bridge — bridge wrapper not installed`. The container uv tool env for fr lacks fr-vk; the fix is `uv tool install --force --with packages/fr-vk packages/fr` in the container. (2) `tests/integration/test_bridge_entry_point.py::test_python_dash_m_dry_run_exits_zero` hit `subprocess.TimeoutExpired ... after 30 seconds` during the full run (host load average 5-11, three fr containers) and PASSED on a targeted rerun, so it is a flake. Neither test touches the statusline segment or its test. Rerun of the three: `2 failed, 1 passed`.

<!-- fr:journal kind=finding scope=plan id=review-p1-suite-gate created=2026-09-14T22:41:36 phase=1 state=refuted -->
### review-p1-suite-gate · finding [refuted] · Review p1: full-suite rc=1 is not caused by phase 1 (phase 1)

Verified at review. origin/main CI run 34828373985 (b257d34) fails only tests/unit/test_tripwire_unarchived_plans.py (plan 2026-07-24-remove-vk-legacy-fallbacks complete but unarchived on main) - pre-existing, out of scope for this PR, noted for the PR body. test_install_bridge passes in CI; its failure is the container's uv tool env lacking fr_vk.bridge. test_bridge_entry_point hit a 30 s timeout under host load and passed in isolation. Supersedes executor entries 1a97c378d1be and c48ecd9911fa.

<!-- fr:journal kind=finding scope=plan id=review-p1-header-wording created=2026-09-14T22:41:38 phase=1 state=fixed -->
### review-p1-header-wording · finding [open] · Review p1: segment header writes plain output as 'fr | none' (ambiguous, spec review fixed the same wording) (phase 1)

Fix in phase 2 P2.T1.S3 when the header is rewritten to describe rules 1-2: spell each line as alternatives (state fr or none; branch: <b> or no branch; worktree: <path> or no fr-isolation).

<!-- fr:journal kind=finding scope=plan id=review-p1-time-import created=2026-09-14T22:41:41 phase=1 state=fixed -->
### review-p1-time-import · finding [open] · Review p1: 'import time' removed with the v1 timing test; phase 2 must re-add it (phase 1)

Executor removed the unused import so ruff passes. P2.T1.S1 restores test_runs_well_under_budget and must re-add 'import time'. Also re-confirm shellcheck-style unused-variable warnings (executor entry 9881719eb4a1) disappear once phase 2 uses session_id and cwd.

<!-- fr:journal kind=discovery scope=plan id=b6915fdbd0d0 created=2026-09-14T22:45:21 phase=2 -->
### b6915fdbd0d0 · discovery · P2.T1.S1 RED confirmed against the phase-1 skeleton (phase 2)

Added 17 cases to tests/unit/test_statusline_segment.py (15 goldens from the step + restored test_runs_well_under_budget and test_never_invokes_fr, adapted to _plain; import time re-added). Run (container, git 2.51.1): `11 failed, 8 passed in 2.66s`. Failed, because the skeleton always prints the none rows: test_bound_from_base_clone, test_bound_from_non_repo_cwd, test_stale_binding_ignored, test_unbound_base_clone, test_unbound_inside_fr_workspace, test_base_clone_subdirectory, test_plain_linked_worktree, test_missing_session_id_is_unbound, test_cwd_flag_reads_no_stdin, test_ansi_colours, test_oneline. Passed (NONE-shaped, as the step expects): test_not_a_git_repo, test_missing_cwd, test_detached_agent_worktree, test_unknown_session_id_is_unbound, test_path_like_session_id_is_unbound, test_unknown_format_falls_back_to_plain, test_runs_well_under_budget, test_never_invokes_fr. Deviation: the step's `WT = ...` constant is not added; every expectation uses world.featx, so the constant would be dead code.

<!-- fr:journal kind=discovery scope=plan id=33881b2ba043 created=2026-09-14T22:46:11 phase=2 -->
### 33881b2ba043 · discovery · P2.T1.S2 GREEN: resolution block verbatim, --path-format=absolute works on container git 2.51.1 (phase 2)

Inserted the plan's resolution block verbatim in place of the phase-1 placeholder. Segment tests: `19 passed in 3.02s` (rc=0). The container git is 2.51.1 (>= 2.31), so `rev-parse --path-format=absolute` is supported and the relative-common-dir fallback was not needed.

<!-- fr:journal kind=finding scope=plan id=review-p1-header-wording-fixed created=2026-09-14T22:48:27 phase=2 state=fixed -->
### review-p1-header-wording-fixed · finding [fixed] · Fixed review-p1-header-wording: segment header spells plain output as alternatives (phase 2)

Closes review-p1-header-wording. Re-adding the same id is idempotent and did not change its state, so this entry uses the -fixed id. P2.T1.S3 rewrote the fr-statusline-segment.sh header to describe resolution rules 1-2 as implemented. It spells the plain output as alternatives: line 1 state "fr" or "none"; line 2 "branch: <b>" or "no branch"; line 3 "worktree: <abs path>" or "no fr-isolation". The test module docstring uses the same "or" wording.

<!-- fr:journal kind=finding scope=plan id=review-p1-time-import-fixed created=2026-09-14T22:48:30 phase=2 state=fixed -->
### review-p1-time-import-fixed · finding [fixed] · Fixed review-p1-time-import: import time restored with the timing guard (phase 2)

Closes review-p1-time-import. P2.T1.S1 re-added `import time` in tests/unit/test_statusline_segment.py together with test_runs_well_under_budget (0.5 s, bound case). `uv run ruff check packages/ tests/` and `uv run ruff format --check packages/ tests/` both pass (rc=0).

<!-- fr:journal kind=finding scope=plan id=9881719eb4a1-fixed created=2026-09-14T22:48:33 phase=2 state=fixed -->
### 9881719eb4a1-fixed · finding [fixed] · Fixed 9881719eb4a1: shellcheck is clean now that session_id and cwd are used (phase 2)

Closes 9881719eb4a1 and the shellcheck re-check that review-p1-time-import asked for. With the phase-2 resolution block, `shellcheck plugins/super-fr/scripts/fr-statusline-segment.sh` on the host gives rc=0 with no SC2034 warnings. `bash -n` gives rc=0.

<!-- fr:journal kind=discovery scope=plan id=d048fcdb74ad created=2026-09-14T22:48:36 phase=2 -->
### d048fcdb74ad · discovery · P2.T1.S3 gate: shellcheck only on the host; the script runs under /bin/bash 3.2 (phase 2)

The container has no shellcheck, so shellcheck ran on the host Mac (rc=0). `/bin/bash -n` (GNU bash 3.2.57) gives rc=0. Smoke runs under /bin/bash 3.2 on the host: `--cwd <this fr workspace>` prints fr / branch: feat/statusline-session-branch / worktree: <path>; `--cwd <subdir> --format oneline` prints fr:feat/statusline-session-branch; stdin JSON with a non-repo cwd prints the none rows. All exit 0, so the script has no bash-4 syntax, and host git accepts --path-format=absolute. The v1-contract git grep ('iso:' or 'worktrees (') over the segment and its test prints nothing (rc=1). The segment tests after the refactor: 19 passed.

<!-- fr:journal kind=decision scope=plan id=37366178176a created=2026-09-14T22:48:39 phase=2 -->
### 37366178176a · decision · no-refactor-because: P2.T1 (code); refactor limited to comments (phase 2)

no-refactor-because: P2.T1 — the GREEN block is the plan's verbatim resolution code and has no duplication to extract. The refactor step changed only comments: the segment header now describes rules 1-2 exactly as implemented, and the test docstring uses the 'or' wording.

<!-- fr:journal kind=discovery scope=plan id=82e81ea8df02 created=2026-09-14T22:52:59 phase=2 -->
### 82e81ea8df02 · discovery · P2.T1.S3 full suite: rc=1, only known pre-existing failures (phase 2)

Container full suite: `2 failed, 2904 passed, 85 skipped in 309.33s`, rc=1, coverage 91.41% (gate 75% met). Failures, both known and not caused by this phase (see review-p1-suite-gate): tests/unit/test_tripwire_unarchived_plans.py::test_no_merged_but_unarchived_plans (unarchived plan on origin/main) and tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper (container uv tool env lacks fr_vk.bridge). The load-dependent tests/integration/test_bridge_entry_point.py timeout did not happen this run.

<!-- fr:journal kind=discovery scope=plan id=journal-no-state-update created=2026-09-14T22:56:40 phase=2 -->
### journal-no-state-update · discovery · fr journal has no way to close a finding; open markers flipped in place (phase 2)

fr journal add is append-only and idempotent by id (re-adding an id keeps its state); check counts every finding whose own header says state=open. Phase 2 closed the phase-1 findings under new -fixed ids, leaving the originals open. Resolved at review by editing the five header tokens in place: 9881719eb4a1, review-p1-header-wording, review-p1-time-import -> fixed (9b2f370); 1a97c378d1be, c48ecd9911fa -> refuted (pre-existing on main / container-only, see review-p1-suite-gate). Tooling gap worth an fr issue: fr journal resolve --id <id> --state fixed|refuted.

<!-- fr:journal kind=finding scope=plan id=review-p2-budget-claim created=2026-09-14T22:56:43 phase=2 state=fixed -->
### review-p2-budget-claim · finding [fixed] · Review p2: spec claimed v2 is 'well under the old ~100 ms'; measured numbers now in spec 5.A (phase 2)

Host /bin/bash 3.2, Xcode git first: bound ~77 ms, unbound in repo ~100 ms, non-repo ~65 ms; v1 120-155 ms for the same session. bash and jq start ~36 ms each. Spec Budget paragraph corrected; no code change needed (v2 is faster than v1; CI guard 0.5 s).

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-09-14T22:56:45 phase=2 -->
### review-p2 · review · Review p2: resolution logic sound; host smoke on real sessions matches d3/d4 (phase 2)

Checked 9b2f370 against spec 5.A: quoted paths (worktree with a space renders), path-like session ids dropped, stale binding falls through to cwd rule, --cwd skips stdin, physical-path compare, bash 3.2 syntax only. Host smoke: this session (index 8427b705 bound to feat/statusline-session-branch by fr run start) -> fr rows in green even from the willikins cwd, as d3 intends; a bound Flexible Health index -> green rows; cwd in the workspace without a sid -> fr rows. Branch CI run 34894525072: only the pre-existing unarchived-plans tripwire fails (1 failed, 2892 passed).
