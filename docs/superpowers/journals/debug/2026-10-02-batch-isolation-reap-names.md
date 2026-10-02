# Journal: 2026-10-02-batch-isolation-reap-names

<!-- fr:journal kind=hypothesis scope=debug id=8f66781ceb79 created=2026-10-02T16:37:46+00:00 -->
### 8f66781ceb79 · hypothesis · Batch premise (one root cause) does not hold: three independent causes across four members

All four sites are confirmed live on 599ba629 (packages/fr/src/fr/isolation/local.py):

- #844 and #553 share a cause: fr uses a branch NAME as a workspace's identity and never checks that the name still points at this workspace's work. gc's `_pr_from` (:2783) takes any PR whose head is that name. `gh pr view <branch>` returns a PR that merged before the workspace existed, and gc reaps on it (:1930-1933). The marker's `branch` is written (:2548), but the edit gate (`fr-isolation-decision.sh` `_fr_marker_valid`) never compares it with HEAD.
- #578 has its own cause, an ordering defect: `up` makes its side effects (worktree, then `_devcontainer_up` at :1050) before it records them (`save_state` at :1053). A raise in between leaves resources that status/down cannot address.
- #843 has its own cause, a file-append defect: `_write_isolation_marker` appends to a shared `info/exclude` (:2564) and assumes the file ends in a newline.

The batch rule says to stop and ask before fixing anything when there is more than one root cause. Paused for the operator.

<!-- fr:journal kind=decision scope=debug id=dcaa57ca57da created=2026-10-02T16:42:20+00:00 -->
### dcaa57ca57da · decision · Operator: fix all four in one PR, one failing test per cause

#844: a MERGED PR counts as this workspace's only if it merged after the state's created_at; otherwise fall back to merged-by-content. #553: fail closed on drift between HEAD's branch and the marker's branch, and gc refuses to reap a drifted workspace. #578: save state before devcontainer up. #843: write a newline before appending to info/exclude.

<!-- fr:journal kind=repro scope=debug id=820a49a90f94 created=2026-10-02T16:45:20+00:00 -->
### 820a49a90f94 · repro · All four reproduce as failing tests on 599ba629

tests/unit/test_isolation_reap_names.py and three new tests in test_isolation_decision_core.py, all red for the reported reason:
- #844: a gh PR MERGED at 2020-01-01 is reported as verdict=merged, action=reaped for a workspace created today.
- #553: a worktree drifted to fix/other gets reaped on feat/registered's PR, and the edit gate still allows edits there.
- #578: with fail_on=devcontainer, up raises and load_state returns None.
- #843: an exclude file ending in '*.log' with no newline becomes '*.log.fr-isolation'.

<!-- fr:journal kind=root-cause scope=debug id=ab8f5b8f215e created=2026-10-02T17:00:12+00:00 -->
### ab8f5b8f215e · root-cause · #844/#553: fr treats a branch NAME as a workspace's identity and never checks the name still means this workspace

gc trusts any MERGED PR that `gh pr view <name>` returns, even one that merged before the workspace existed. Nothing compares the marker's branch with HEAD, so a checkout to another branch keeps passing every gate, and gc/down reap on the registered branch's verdict.

<!-- fr:journal kind=root-cause scope=debug id=328225b68c5e created=2026-10-02T17:00:13+00:00 -->
### 328225b68c5e · root-cause · #578: up performs side effects before recording them

`LocalWorktreeDevcontainerTarget.up` ran `_devcontainer_up` before `save_state`, so a raise between them stranded the worktree and container with no record.

<!-- fr:journal kind=root-cause scope=debug id=4afd4f1b079f created=2026-10-02T17:00:14+00:00 -->
### 4afd4f1b079f · root-cause · #843: the append to the shared info/exclude assumed a trailing newline

`_write_isolation_marker` appended `.fr-isolation` directly, so a hand-edited last line with no newline (`*.log`) became `*.log.fr-isolation`.

<!-- fr:journal kind=finding scope=debug id=fix-844 created=2026-10-02T17:00:15+00:00 state=fixed -->
### fix-844 · finding [fixed] · #844 fixed: gc ignores a MERGED PR that merged before the workspace's created_at

`_pr_from` now carries `mergedAt` (gh `--json state,url,mergedAt`, glab `merged_at`, tea's `merged` timestamp). In `_gc_one`, `_merged_before` drops such a PR, and the decision falls through to merged-by-content. A merge time that is missing or unparseable keeps the old by-name verdict: the forge reported nothing to compare, so the fix doesn't invent a new rule for that case. Pinned by test_isolation_reap_names.py (both directions, plus the gh argv).

<!-- fr:journal kind=finding scope=debug id=fix-553 created=2026-10-02T17:00:16+00:00 state=fixed -->
### fix-553 · finding [fixed] · #553 fixed: drift between HEAD and the marker's branch now fails closed in every gate and in the reap hazard

`_fr_branch_drift` in fr-isolation-decision.sh invalidates a worktree-mode marker when HEAD is a different branch. The Claude Code, Hermes and OpenCode edit gates all deny, naming both branches and `fr isolation up --branch <checked-out>`. The Bash guard inherits the check through decide_cwd. `_reap_hazard` gains kind=drifted-checkout, so gc skips the workspace and a non-forced down refuses. A detached HEAD is not drift, so editing mid-rebase still works. External markers are left unchanged: the preparer writes their branch. Pinned by test_isolation_decision_core.py, test_hooks_isolation_required.py, test_hermes_isolation_hook_edits.py, marker.test.ts and the gc test.

<!-- fr:journal kind=finding scope=debug id=fix-578 created=2026-10-02T17:00:18+00:00 state=fixed -->
### fix-578 · finding [fixed] · #578 fixed: up saves the state record and marker before devcontainer up

A failed devcontainer up now leaves a workspace that status lists, and the error names both the retry and `fr isolation down --branch <b>`. Pinned by test_failed_devcontainer_up_leaves_a_state_record_that_down_can_address.

<!-- fr:journal kind=finding scope=debug id=fix-843 created=2026-10-02T17:00:19+00:00 state=fixed -->
### fix-843 · finding [fixed] · #843 fixed: a newline is written first when info/exclude does not end in one

Pinned by test_up_does_not_glue_patterns_onto_an_exclude_line_without_trailing_newline.

<!-- fr:journal kind=review scope=debug id=ba856cfe61cb created=2026-10-02T17:08:07+00:00 -->
### ba856cfe61cb · review · Independent adversarial review: 2 findings on #553 recovery, both fixed; #844/#578/#843 clean

1. The drift check lived in `_fr_marker_valid`, which the Bash guards share, so a drifted worktree read as a base clone. The Hermes terminal guard then blocked `git checkout <registered>`, the recovery the deny recommends. Fixed: drift is now checked only in `fr_isolation_decide_edit`, and the shell stays open. Pinned by test_drifted_worktree_is_still_an_allowed_shell_context and test_switching_back_to_the_marker_branch_restores_edits.
2. The second remedy, `fr isolation up --branch <head>`, fails while <head> is checked out in the drifted worktree: git refuses to add a second worktree for the same branch. Fixed: the message now says `git switch <registered>` first, then `up --branch <head>`, in the shell lib, the TS port and the reap hazard.
Clean probes: no shell variable clobbering; `_merged_before` handles timezones; created_at carries over correctly; a half-built #578 workspace is warned about, never reaped; down works with no container; dry-run and live runs agree.

<!-- fr:journal kind=finding scope=debug id=fix-553-review created=2026-10-02T17:08:14+00:00 state=fixed -->
### fix-553-review · finding [fixed] · #553 drift no longer locks the shell; the remedy order works

Correction to fix-553: the Bash guard does NOT inherit the drift check. That was the review's finding 1, and the check is now edit-only.

<!-- fr:journal kind=review scope=debug id=2c489821fc0e created=2026-10-02T17:19:17+00:00 -->
### 2c489821fc0e · review · Delivered: draft PR #859, full suite green on e43dc5ca

7602 passed, 97 skipped; mypy, ruff and bun test (93) clean. Review findings: 2 raised, 2 fixed (entry ba856cfe61cb).
