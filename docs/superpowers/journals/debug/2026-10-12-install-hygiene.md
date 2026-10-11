# Journal: 2026-10-12-install-hygiene

<!-- fr:journal kind=repro scope=debug id=562d771ae07f created=2026-10-11T23:07:15+00:00 -->
### 562d771ae07f · repro · Three install-hygiene repros (gh#1124, gh#1087, gh#1105)

- #1124: with fr-worktree-create.sh registered both in hooks.json and ~/.claude/settings.json, two copies run for one agent-* WorktreeCreate; the loser fails on `.git/worktrees/agent-<id>/index.lock`, so the isolation:worktree Agent dispatch fails.
- #1087: install.sh/bootstrap.sh preflights stop at the FIRST missing command with 'Install it first' and no install command for the host OS.
- #1105: ensure-phase-executor-allowlist.sh inserts only `super-fr:fr-phase-executor` and strips a bare `fr-phase-executor` as stale, yet `fr init agents` writes project agents dispatched by the bare name.
