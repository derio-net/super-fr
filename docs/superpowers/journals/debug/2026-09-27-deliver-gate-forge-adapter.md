# Journal: 2026-09-27-deliver-gate-forge-adapter

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-27T14:27:11+00:00 -->
### repro · repro · deliver refuses forever on a GitLab/Gitea checkout

Observed (gh#742): an OpenCode run on a self-hosted GitLab (host redacted) opened the MR with glab, then `fr run resolve --step deliver` refused twice: "cannot read the PR <mr-url> (none of the git remotes ... point to a known GitHub host)", advising `gh pr create`. Cursor stuck on deliver; closeout unreachable. Static repro: commands/run_cmd.py `_deliver_pr_gate` imports `fr.gh` and calls `gh.view_pr_body(ref, cwd=repo_root)` unconditionally; `gh` cannot read a GitLab/Gitea PR, so the gate can never pass there. Every existing test (test_deliver_pr_body.py, conftest `complete_live_pr`) monkeypatches `fr.gh.view_pr_body`, so the non-GitHub path was never exercised.
