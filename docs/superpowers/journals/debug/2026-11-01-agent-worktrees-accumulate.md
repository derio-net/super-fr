<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-agent-worktrees-accumulate

<!-- fr:journal kind=repro scope=debug id=60a8a809f57d created=2026-11-01T19:51:00+00:00 -->
### 60a8a809f57d · repro · agent-* worktrees accumulate in-repo, unlocked, never removed

Observed 2026-11-01 in super-fr's own base clone (Claude Code 2.1.316): 19 `.claude/worktrees/agent-*` linked worktrees, all clean, detached, none with a `locked` file in `.git/worktrees/<name>/`; 3 created today by live goal runs, so the leak is ongoing. Same shape as frank's 31 (gh#1270). Repro: dispatch any Agent with `isolation: "worktree"` in an fr-enabled repo with super-fr installed; after the subagent finishes, `git worktree list` still lists `<repo>/.claude/worktrees/agent-<id>`.

<!-- fr:journal kind=hypothesis scope=debug id=h1-remove-not-fired created=2026-11-01T19:52:51+00:00 -->
### h1-remove-not-fired · hypothesis · H1: Claude Code never fires WorktreeRemove for hook-created subagent worktrees

Tested 2026-11-01 (Claude Code 2.1.316) in a throwaway repo with project-only settings (--setting-sources project) and logging WorktreeCreate/WorktreeRemove probe hooks. One isolated general-purpose subagent, read-only commands, clean worktree. CREATE logged (input: session_id, transcript_path, cwd, prompt_id, hook_event_name, name=agent-<id>; no agent_id). REMOVE never logged, through subagent completion and session exit; worktree left behind. CONFIRMED.

<!-- fr:journal kind=ruled-out scope=debug id=h2-outside-path-rejected created=2026-11-01T19:52:57+00:00 -->
### h2-outside-path-rejected · ruled-out · Ruled out: Claude Code rejects a WorktreeCreate path outside the repo for a subagent

Same probe: the hook printed <scratch>/outside/agent-<id> (not under the repo). The subagent ran there: pwd = that path, --show-toplevel = that path, --git-common-dir = <repo>/.git. Claude's checkout verification is git-identity based, not location based. Moving agent-* out of the repo is safe.

<!-- fr:journal kind=root-cause scope=debug id=c0932134179b created=2026-11-01T19:53:02+00:00 -->
### c0932134179b · root-cause · agent-* worktrees leak because spec 2026-09-04 d2 assumed Claude's lifecycle survives a WorktreeCreate takeover

d2 kept agent-* in Claude's default SHAPE and the spec's table calls them 'Claude-internal, swept by cleanupPeriodDays'. But a registered WorktreeCreate replaces native creation, so the native lifecycle is gone: no lock while running, and (H1, confirmed live) WorktreeRemove is never fired for these subagents, so fr-worktree-remove.sh's agent-* branch never runs. Nothing else removes them. In-repo, a subagent that dispatches its own isolated subagent nests them (frank: 4 nested), until Claude refuses new isolated dispatches as unverifiable.

<!-- fr:journal kind=finding scope=debug id=f1-agent-worktrees-owned-by-fr created=2026-11-01T20:08:03+00:00 state=fixed -->
### f1-agent-worktrees-owned-by-fr · finding [fixed] · agent-* worktrees move out of the repo, locked; fr isolation gc reaps them

fr-worktree-create.sh: agent-* now go to ~/.cache/fr/agent-worktrees/<main-checkout-key>/<name> (sibling of ~/.cache/fr/worktrees, whose <repo>/<child> gc reads as workspaces), detached at Claude's default base, locked 'fr-agent pid=$PPID session=<id>' (the hook's parent is the Claude process, measured live). A name that exists for a different repo fails closed. fr-worktree-remove.sh recognises the new path and unlocks first. New fr.isolation.agent_worktrees sweep, run by every LocalTarget.gc: reaps only when no live fr lock pid, no foreign lock, >= 24h old (even with a dead pid), git status clean, and HEAD reachable from a branch/tag/remote (ancestry, not PR state); legacy in-repo ones included, deepest first; every removal logged to ~/.cache/fr/agent-worktrees/reap.log; dirty/unreachable reported as warned. Failing tests first: tests/unit/test_hooks_worktree.py (8 RED -> 22 green), tests/unit/test_isolation_agent_worktrees.py (14), test_isolation_gc_hygiene.py::test_gc_runs_the_agent_worktree_sweep. LIVE 2026-11-01, Claude Code 2.1.316: a throwaway repo registering this branch's create hook; the subagent ran in ~/.cache/fr/agent-worktrees/repo/agent-<id>, locked with the Claude pid; WorktreeRemove again not fired; the sweep skipped it as young, then (clock +25h, pid dead) reaped and logged it.

<!-- fr:journal kind=review scope=debug id=f6dacdc9e9c6 created=2026-11-01T20:31:53+00:00 -->
### f6dacdc9e9c6 · review · Code review (medium, independent context): 10 findings, 8 fixed, 2 refuted

Fixed: (1) a locked worktree whose dir vanished stayed forever; now unlocked + pruned. (2)+(3) the lock pid is the PARENT session's, so a days-long session or a reused pid protected finished worktrees indefinitely; a live lock now protects for 72h only. (4) non-fr repos never ran gc; every agent dispatch now fires a detached `fr isolation gc --agent-worktrees` (new flag, this sweep only, flock'd). (6) remove hook used the common dir's parent, wrong for bare / --separate-git-dir repos; now --git-dir, with a bare-repo test. (7) docstring said invoking-repo legacy only; the sweep is host-wide like gc, docstring corrected. (8) emptied repo-key dir compared unresolved paths; resolved. (10) dry run said skipped; now would-skip, matching gc. Refuted: (5) guard cd-prefix: a cd into an agent worktree was denied before (it sat under the base clone) and is denied now, so no regression, and cd'ing into a subagent's checkout is not workspace work. (9) duplicate pid_alive: the existing copies are a file-lock predicate (isolation.types._abandoned) and fr.triage.drive_lock, which isolation must not import; no shared helper to reuse. Tests: 169 passed across hook, sweep, gc hygiene, isolation cmd, plugin hooks, parity, install wiring.
