# Journal: 2026-09-14-statusline-session-branch

<!-- fr:journal kind=discovery scope=plan id=858243a70dfe created=2026-09-14T22:01:23 phase=1 -->
### 858243a70dfe · discovery · P1.T1.S1 RED confirmed against the v1 segment (phase 1)

Rewrote tests/unit/test_statusline_segment.py for contract v2 (fixture kept, all v1 tests deleted, `_plain` + `NONE` + test_not_a_git_repo + test_missing_cwd added). Against the v1 script: `2 failed in 30.89s`, both with `AssertionError: plain output must be exactly three lines: '\n\n'` (v1 prints two empty lines for a non-repo cwd). After the v2 skeleton: `2 passed`.

<!-- fr:journal kind=decision scope=plan id=4ba9a412e844 created=2026-09-14T22:02:10 phase=1 -->
### 4ba9a412e844 · decision · Dropped the unused 'time' import from the v2 test module (phase 1)

P1.T1.S1 said "keep the imports", but deleting the v1 timing guard leaves `import time` unused and CI runs `ruff check packages/ tests/` (F401). Removed it so the phase commit is lint-clean. Phase 2 re-adds `time` when it restores the 0.5 s timing guard (spec §7).

<!-- fr:journal kind=finding scope=plan id=9881719eb4a1 created=2026-09-14T22:03:02 phase=1 state=open -->
### 9881719eb4a1 · finding [open] · shellcheck SC2034 on the skeleton: session_id and cwd unused until phase 2 (phase 1)

On the embedded v2 skeleton, `shellcheck plugins/super-fr/scripts/fr-statusline-segment.sh` gives rc=1 with two SC2034 warnings: `session_id` and `cwd` are read from stdin/--cwd, but no code uses them until the phase-2 resolution rules land. `bash -n` passes. No CI job or test runs shellcheck (grep over tests/, .github/, packages/), so nothing is gated. I added no `# shellcheck disable` lines, so the script matches the plan text. Phase 2 must re-run shellcheck and expect rc=0.

<!-- fr:journal kind=decision scope=plan id=865ef03fe54e created=2026-09-14T22:04:03 phase=1 -->
### 865ef03fe54e · decision · no-refactor-because: P1.T1 (phase 1)

no-refactor-because: P1.T1 — the GREEN script is the verbatim skeleton from the plan and the test module is the fixture plus two goldens. Nothing is duplicated to clean up. The only lint noise is SC2034 (see the open finding), and phase 2 removes it by using the variables.

<!-- fr:journal kind=finding scope=plan id=1a97c378d1be created=2026-09-14T22:39:05 phase=1 state=open -->
### 1a97c378d1be · finding [open] · Full-suite gate rc=1: tripwire flags an unarchived plan on origin/main (not this phase) (phase 1)

P1.T1.S3 full suite (devcontainer): `3 failed, 2886 passed, 85 skipped in 2095.77s`, rc=1, coverage 91.41% (gate 75% met). One failure is deterministic and comes from repo state: `tests/unit/test_tripwire_unarchived_plans.py::test_no_merged_but_unarchived_plans` reports `merged-but-unarchived plan(s) — complete on origin/main but still in docs/superpowers/plans/: ['2026-07-24-remove-vk-legacy-fallbacks']`. origin/main is at b257d34 (#408). The phase diff touches no plan-archive files. The fix is outside phase 1: someone must run `fr archive` for that plan on main, or rebase the branch after main archives it. CI on this branch will fail this tripwire until then.

<!-- fr:journal kind=finding scope=plan id=c48ecd9911fa created=2026-09-14T22:39:08 phase=1 state=open -->
### c48ecd9911fa · finding [open] · Full-suite gate rc=1: bridge install env failure + load timeout (not this phase) (phase 1)

The other two S3 failures come from the environment. (1) `tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper` fails every time: `ERROR: /home/vscode/.local/share/uv/tools/fr/bin/python cannot import fr_vk.bridge — bridge wrapper not installed`. The container uv tool env for fr lacks fr-vk; the fix is `uv tool install --force --with packages/fr-vk packages/fr` in the container. (2) `tests/integration/test_bridge_entry_point.py::test_python_dash_m_dry_run_exits_zero` hit `subprocess.TimeoutExpired ... after 30 seconds` during the full run (host load average 5-11, three fr containers) and PASSED on a targeted rerun, so it is a flake. Neither test touches the statusline segment or its test. Rerun of the three: `2 failed, 1 passed`.

<!-- fr:journal kind=finding scope=plan id=review-p1-suite-gate created=2026-09-14T22:41:36 phase=1 state=refuted -->
### review-p1-suite-gate · finding [refuted] · Review p1: full-suite rc=1 is not caused by phase 1 (phase 1)

Verified at review. origin/main CI run 34828373985 (b257d34) fails only tests/unit/test_tripwire_unarchived_plans.py (plan 2026-07-24-remove-vk-legacy-fallbacks complete but unarchived on main) - pre-existing, out of scope for this PR, noted for the PR body. test_install_bridge passes in CI; its failure is the container's uv tool env lacking fr_vk.bridge. test_bridge_entry_point hit a 30 s timeout under host load and passed in isolation. Supersedes executor entries 1a97c378d1be and c48ecd9911fa.

<!-- fr:journal kind=finding scope=plan id=review-p1-header-wording created=2026-09-14T22:41:38 phase=1 state=open -->
### review-p1-header-wording · finding [open] · Review p1: segment header writes plain output as 'fr | none' (ambiguous, spec review fixed the same wording) (phase 1)

Fix in phase 2 P2.T1.S3 when the header is rewritten to describe rules 1-2: spell each line as alternatives (state fr or none; branch: <b> or no branch; worktree: <path> or no fr-isolation).

<!-- fr:journal kind=finding scope=plan id=review-p1-time-import created=2026-09-14T22:41:41 phase=1 state=open -->
### review-p1-time-import · finding [open] · Review p1: 'import time' removed with the v1 timing test; phase 2 must re-add it (phase 1)

Executor removed the unused import so ruff passes. P2.T1.S1 restores test_runs_well_under_budget and must re-add 'import time'. Also re-confirm shellcheck-style unused-variable warnings (executor entry 9881719eb4a1) disappear once phase 2 uses session_id and cwd.
