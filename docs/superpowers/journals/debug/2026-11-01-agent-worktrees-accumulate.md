<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-agent-worktrees-accumulate

<!-- fr:journal kind=repro scope=debug id=60a8a809f57d created=2026-11-01T19:51:00+00:00 -->
### 60a8a809f57d · repro · agent-* worktrees accumulate in-repo, unlocked, never removed

Observed 2026-11-01 in super-fr's own base clone (Claude Code 2.1.316): 19 `.claude/worktrees/agent-*` linked worktrees, all clean, detached, none with a `locked` file in `.git/worktrees/<name>/`; 3 created today by live goal runs, so the leak is ongoing. Same shape as frank's 31 (gh#1270). Repro: dispatch any Agent with `isolation: "worktree"` in an fr-enabled repo with super-fr installed; after the subagent finishes, `git worktree list` still lists `<repo>/.claude/worktrees/agent-<id>`.

<!-- fr:journal kind=hypothesis scope=debug id=h1-remove-not-fired created=2026-11-01T19:52:51+00:00 -->
### h1-remove-not-fired · hypothesis · H1: Claude Code never fires WorktreeRemove for hook-created subagent worktrees

Tested 2026-11-01 (Claude Code 2.1.316) in a throwaway repo with project-only settings (--setting-sources project) and logging WorktreeCreate/WorktreeRemove probe hooks. One isolated general-purpose subagent, read-only commands, clean worktree. CREATE logged (input: session_id, transcript_path, cwd, prompt_id, hook_event_name, name=agent-<id>; no agent_id). REMOVE never logged, through subagent completion and session exit; worktree left behind. CONFIRMED.
