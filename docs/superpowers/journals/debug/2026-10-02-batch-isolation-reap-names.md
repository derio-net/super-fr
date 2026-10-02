# Journal: 2026-10-02-batch-isolation-reap-names

<!-- fr:journal kind=hypothesis scope=debug id=8f66781ceb79 created=2026-10-02T16:37:46+00:00 -->
### 8f66781ceb79 · hypothesis · Batch premise (one root cause) does not hold: three independent causes across four members

All four sites are confirmed live on 599ba629 (packages/fr/src/fr/isolation/local.py):

- #844 and #553 share a cause: fr uses a branch NAME as a workspace's identity and never checks that the name still points at this workspace's work. gc's `_pr_from` (:2783) takes any PR whose head is that name. `gh pr view <branch>` returns a PR that merged before the workspace existed, and gc reaps on it (:1930-1933). The marker's `branch` is written (:2548), but the edit gate (`fr-isolation-decision.sh` `_fr_marker_valid`) never compares it with HEAD.
- #578 has its own cause, an ordering defect: `up` makes its side effects (worktree, then `_devcontainer_up` at :1050) before it records them (`save_state` at :1053). A raise in between leaves resources that status/down cannot address.
- #843 has its own cause, a file-append defect: `_write_isolation_marker` appends to a shared `info/exclude` (:2564) and assumes the file ends in a newline.

The batch rule says to stop and ask before fixing anything when there is more than one root cause. Paused for the operator.
