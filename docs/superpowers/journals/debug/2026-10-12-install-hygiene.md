# Journal: 2026-10-12-install-hygiene

<!-- fr:journal kind=repro scope=debug id=562d771ae07f created=2026-10-11T23:07:15+00:00 -->
### 562d771ae07f · repro · Three install-hygiene repros (gh#1124, gh#1087, gh#1105)

- #1124: with fr-worktree-create.sh registered both in hooks.json and ~/.claude/settings.json, two copies run for one agent-* WorktreeCreate; the loser fails on `.git/worktrees/agent-<id>/index.lock`, so the isolation:worktree Agent dispatch fails.
- #1087: install.sh/bootstrap.sh preflights stop at the FIRST missing command with 'Install it first' and no install command for the host OS.
- #1105: ensure-phase-executor-allowlist.sh inserts only `super-fr:fr-phase-executor` and strips a bare `fr-phase-executor` as stale, yet `fr init agents` writes project agents dispatched by the bare name.

<!-- fr:journal kind=decision scope=debug id=65087cb3f1f0 created=2026-10-11T23:07:27+00:00 -->
### 65087cb3f1f0 · decision · Three independent causes in one batch: proceed, not stop

The batch rule says stop if investigation finds more than one root cause. The batch's own text already lists three independent mechanisms (hook race, preflight, allowlist) grouped by surface (install hygiene), so finding three is the stated premise, not a surprise. Proceeding with three fixes in one PR; flagged in the PR body for the operator.
