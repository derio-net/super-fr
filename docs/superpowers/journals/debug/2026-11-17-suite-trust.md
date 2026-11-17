<!-- fr:journal-schema=4 -->
# Journal: 2026-11-17-suite-trust

<!-- fr:journal kind=repro scope=debug id=741daae6c2db created=2026-11-17T09:09:59+00:00 -->
### 741daae6c2db · repro · gh#1468: scenario fixture commits land in the live worktree when pytest inherits GIT_DIR

Sandbox repro: a linked worktree `wt`; `GIT_DIR=<live>/.git/worktrees/wt` (what a git hook and `git rebase -x` both export, observed); then the triage-closed-recovery fixture steps in a fresh tmp dir: `git init -q $PWD` (writes nothing, it reinitialises GIT_DIR), `git commit --allow-empty -m fixture` as scenario@example.invalid, `git checkout -b feat/fixture`. Result: the live worktree is on feat/fixture with an empty scenario commit; the tmp dir has no .git. Matches the retire-vk symptom exactly (first commit on the run branch, the rest on feat/fixture).

<!-- fr:journal kind=root-cause scope=debug id=d754fe402248 created=2026-11-17T09:10:01+00:00 -->
### d754fe402248 · root-cause · gh#1468: tests/integration/test_scenarios.py::_env passes GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE/GIT_COMMON_DIR through to every scenario

`_env` copies os.environ minus FR_HARNESS_FR and CI. A pytest started under a git hook or `git rebase -x` carries GIT_DIR naming the run worktree, so every scenario git command (the harness `git init`, `_common.sh`, `fixtures/triage-closed-recovery.py`, `fixtures/herdr-opencode.py`, ...) targets the live repo instead of its fixture. `scenario_require_fresh_repo` does not catch it: under GIT_DIR, `rev-parse --show-toplevel` reports cwd. Five other test modules already strip these variables (test_release_script, test_installable, test_change_fragment_gate, test_release_status, test_container_git_ownership); the scenario harness and `_common.sh` never did.

<!-- fr:journal kind=ruled-out scope=debug id=a90c7c7b2a5c created=2026-11-17T09:10:02+00:00 -->
### a90c7c7b2a5c · ruled-out · gh#1463: no two-process interleaving of the mkdir+pid lock double-holds; not reproduced on Linux

Hand trace of fr-worktree-create.sh/fr-worktree-remove.sh lock (mkdir, pid file, kill -0 reclaim, EXIT-trap rm -rf): with exactly two hook processes a reclaim can only delete a lock nobody holds, and a live holder never reads as dead. The stub is reached once per hook, inside the lock (_fr_is_enabled returns before any fr call: the fixture repo has docs/superpowers/plans). Stress: 150x each of the two tests at -n 8 on a 2-CPU aarch64 Linux devcontainer (bash 5.2.21): 300/300 passed. CI failures (runs 43918039963, 43903442254, 43901622994) show only the truncated `fr isolation up failed` variant (stub rmdir of in-flight failed, i.e. the two stubs overlapped); py3.11 and py3.14 both. No confident hypothesis yet.
