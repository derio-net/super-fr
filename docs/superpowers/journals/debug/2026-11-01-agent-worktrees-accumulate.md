<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-agent-worktrees-accumulate

<!-- fr:journal kind=repro scope=debug id=60a8a809f57d created=2026-11-01T19:51:00+00:00 -->
### 60a8a809f57d · repro · agent-* worktrees accumulate in-repo, unlocked, never removed

Observed 2026-11-01 in super-fr's own base clone (Claude Code 2.1.316): 19 `.claude/worktrees/agent-*` linked worktrees, all clean, detached, none with a `locked` file in `.git/worktrees/<name>/`; 3 created today by live goal runs, so the leak is ongoing. Same shape as frank's 31 (gh#1270). Repro: dispatch any Agent with `isolation: "worktree"` in an fr-enabled repo with super-fr installed; after the subagent finishes, `git worktree list` still lists `<repo>/.claude/worktrees/agent-<id>`.
