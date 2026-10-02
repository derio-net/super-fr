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
