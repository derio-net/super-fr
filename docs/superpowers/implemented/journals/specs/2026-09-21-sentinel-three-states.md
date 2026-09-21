# Journal: 2026-09-21-sentinel-three-states

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-21T16:57:54 -->
### d1 · decision · Stamp the sentinel with a cache-relative workspace path

Operator: option 1 (stamp the sentinel), path relative to the fr cache dir, never absolute (privacy: no username).

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-21T16:57:54 -->
### d2 · decision · Never-stamped sentinel stays armed until 48h GC or down

Operator: no grace-window heal; fresh means fresh.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-21T16:57:54 -->
### d3 · decision · #432: guard messages only; down --all hardening is a follow-up

Operator: messages only, guard-side.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-21T16:57:55 -->
### d4 · decision · verify-merge falls back to origin/main when workspace is reaped

Operator: include in this PR.

<!-- fr:journal kind=review scope=spec id=r1 created=2026-09-21T16:58:06 -->
### r1 · review · Spec vs codebase reality

Verified: attach() is the single bind point (sessions.py:100) and fr-session-bind.sh routes up/exec/run start through it; sentinel_dir/clear_repo_sentinels live in isolation/types.py; verify_merge needs state.worktree today. Two fixes folded in: (1) guard must compare worktree paths after pwd -P (macOS /private symlinks) when matching git worktree list; (2) a stale global fr on PATH won't stamp, so the sentinel stays fresh/armed - fail closed, noted in the rule text.
