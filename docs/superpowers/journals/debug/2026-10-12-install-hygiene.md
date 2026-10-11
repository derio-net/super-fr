# Journal: 2026-10-12-install-hygiene

<!-- fr:journal kind=repro scope=debug id=562d771ae07f created=2026-10-11T23:07:15+00:00 -->
### 562d771ae07f · repro · Three install-hygiene repros (gh#1124, gh#1087, gh#1105)

- #1124: with fr-worktree-create.sh registered both in hooks.json and ~/.claude/settings.json, two copies run for one agent-* WorktreeCreate; the loser fails on `.git/worktrees/agent-<id>/index.lock`, so the isolation:worktree Agent dispatch fails.
- #1087: install.sh/bootstrap.sh preflights stop at the FIRST missing command with 'Install it first' and no install command for the host OS.
- #1105: ensure-phase-executor-allowlist.sh inserts only `super-fr:fr-phase-executor` and strips a bare `fr-phase-executor` as stale, yet `fr init agents` writes project agents dispatched by the bare name.

<!-- fr:journal kind=decision scope=debug id=65087cb3f1f0 created=2026-10-11T23:07:27+00:00 -->
### 65087cb3f1f0 · decision · Three independent causes in one batch: proceed, not stop

The batch rule says stop if investigation finds more than one root cause. The batch's own text already lists three independent mechanisms (hook race, preflight, allowlist) grouped by surface (install hygiene), so finding three is the stated premise, not a surprise. Proceeding with three fixes in one PR; flagged in the PR body for the operator.

<!-- fr:journal kind=root-cause scope=debug id=01276c66ed28 created=2026-10-11T23:07:37+00:00 -->
### 01276c66ed28 · root-cause · #1124: agent-* path of fr-worktree-create.sh is unserialised

The hook's per-repo+branch mkdir lock wraps only the `fr isolation up` path. `case agent-*) mimic_default` runs before the lock, so two concurrent copies both see no dir and both run `git worktree add --detach` on the same path: index.lock collision + disturbed checkout. Exactly the paths in the issue's error. The double registration is deliberate (CC 2.1.281 skipped the plugin WorktreeCreate for `claude --worktree`); the defect is that one branch of the hook is not safe under it.

<!-- fr:journal kind=root-cause scope=debug id=d6fd32c98720 created=2026-10-11T23:07:47+00:00 -->
### d6fd32c98720 · root-cause · #1105: allowlist script treats the bare name as stale

ensure-phase-executor-allowlist.sh was written when only the plugin-qualified id was ever dispatched; it strips the bare name. Since cloud-triage §H, `fr init agents` renders .claude/agents/fr-{phase-executor,spec-reviewer}.md, which Claude Code dispatches by the BARE name, so both spellings are legitimate.

<!-- fr:journal kind=root-cause scope=debug id=b61fd4ac175a created=2026-10-11T23:07:57+00:00 -->
### b61fd4ac175a · root-cause · #1087: preflight is first-miss, OS-blind

R19 (cloud-triage) already made a Claude-Code home without installed_plugins.json/settings.json exit non-zero. What remains: install.sh's `for cmd in jq uv rsync git` and bootstrap.sh's `for cmd in git uv jq` (no rsync) exit on the first missing command with no install command. Fix: collect every missing prerequisite and print the install command for the detected OS / package manager.
