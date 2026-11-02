<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-release-crosscheck-first-parent

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-02T22:13:25+00:00 -->
### repro-1 · repro · logged_prs names issues as PRs; every release cuts an RC

On origin/main at 2755e97c5 (v6.1.0-rc.17), release.logged_prs(repo, v6.0.0) returns 30 numbers including #1242, #1266, #1270, #1315, #1322, which are issues: trailing (#N) refs on feature-branch commits reachable through merge commits' second parents. The forge read correctly omits them, so waiting_prs raises GateStateUnknownError and every release run cuts an RC. git log --first-parent v6.0.0..HEAD shows only 'Merge pull request #N' and release-bot commits.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-11-02T22:13:31+00:00 -->
### root-cause · root-cause · full-DAG log walks into merged branches

scripts/release.py logged_prs runs git log <tag>..HEAD over the whole DAG, so _PR_SUBJECT_RE's squash alternative also matches every commit inside a merge-committed branch, where (#N) is an issue ref, not the PR that landed it. Only first-parent commits name the PR that landed them (merge: 'Merge pull request #N'; squash/rebase: trailing (#N)).
