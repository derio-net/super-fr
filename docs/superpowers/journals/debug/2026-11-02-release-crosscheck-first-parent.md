<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-release-crosscheck-first-parent

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-02T22:13:25+00:00 -->
### repro-1 · repro · logged_prs names issues as PRs; every release cuts an RC

On origin/main at 2755e97c5 (v6.1.0-rc.17), release.logged_prs(repo, v6.0.0) returns 30 numbers including #1242, #1266, #1270, #1315, #1322, which are issues: trailing (#N) refs on feature-branch commits reachable through merge commits' second parents. The forge read correctly omits them, so waiting_prs raises GateStateUnknownError and every release run cuts an RC. git log --first-parent v6.0.0..HEAD shows only 'Merge pull request #N' and release-bot commits.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-11-02T22:13:31+00:00 -->
### root-cause · root-cause · full-DAG log walks into merged branches

scripts/release.py logged_prs runs git log <tag>..HEAD over the whole DAG, so _PR_SUBJECT_RE's squash alternative also matches every commit inside a merge-committed branch, where (#N) is an issue ref, not the PR that landed it. Only first-parent commits name the PR that landed them (merge: 'Merge pull request #N'; squash/rebase: trailing (#N)).

<!-- fr:journal kind=finding scope=debug id=fix-first-parent created=2026-11-02T22:18:30+00:00 state=fixed -->
### fix-first-parent · finding [fixed] · logged_prs uses git log --first-parent

scripts/release.py logged_prs now runs git log --first-parent <tag>..HEAD. Pinned by three tests in tests/unit/test_release_script.py (test_gh1333_*): a merge commit whose branch commits cite (#7)/(#8) gives a known state and the final is cut; a missed merge is named by its PR (#50) and never by its issues; logged_prs over squash + merge + bot commit returns exactly {42, 50}. All three were red first (output reproduced the production 'misses #7, #8'). Release tests: 178 passed. On the real history, logged_prs(v6.0.0) now names 25 PRs and no issue.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-11-02T22:21:34+00:00 -->
### review-1 · review · independent review: no blockers

Independent reviewer (fresh context, read-only) judged --first-parent correct for merge and squash landings and the bot/direct pushes; all three tests fail on the old code. Findings: (1) low-medium, pre-existing: allow_rebase_merge is on, and a rebase merge puts branch subjects on the first-parent line, so an issue ref there would still read as a missed PR; addressed by the AGENTS.md caveat and the PR body; disabling rebase merges is a repo-settings decision left to the operator. (2) low: the bot-skip test never exercised the release-prefix skip; fixed by adding a non-bot 'release: v9.9.9 (#98)' commit. (3) nit: AGENTS.md wording too absolute; fixed ('usually' + rebase caveat). Re-verified: 139 pass with the fix; the 3 gh1333 tests fail against the old release.py.
