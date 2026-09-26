# Journal: 2026-09-26-container-git-ownership

<!-- fr:journal kind=decision scope=spec id=trust-scope created=2026-09-26T15:02:21 -->
### trust-scope · decision · safe.directory trust scope in POST_CREATE

Operator chose the workspace path via $PWD, not a wildcard.

<!-- fr:journal kind=decision scope=spec id=call-scope created=2026-09-26T15:02:21 -->
### call-scope · decision · Which fr git calls carry -c safe.directory

Operator chose all calls through fr.git.git_answer plus the raw update-index restore in commit.py.

<!-- fr:journal kind=decision scope=spec id=test-plan-and-models created=2026-09-26T15:02:21 -->
### test-plan-and-models · decision · No post-merge test plan; all tiers claude-sonnet-5

Operator confirmed both.
