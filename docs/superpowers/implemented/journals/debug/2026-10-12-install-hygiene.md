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

<!-- fr:journal kind=finding scope=debug id=f3c800abbac1 created=2026-10-11T23:11:29+00:00 state=fixed -->
### f3c800abbac1 · finding [fixed] · #1124 fixed: WorktreeCreate lock now precedes the agent-* branch

fr-worktree-create.sh takes its mkdir lock (keyed repo+name) before `case agent-*) mimic_default`, so the second registered copy waits and then returns the existing path. Pinned by tests/unit/test_hooks_worktree.py#test_two_concurrent_agent_worktree_creations_both_succeed (slow git worktree add shim; red before: 'already exists'). Both registrations are kept: dropping settings.json's would re-break `claude --worktree` on the CC versions that skip the plugin hook, and this cannot be verified for every version. WorktreeRemove's agent-* path stays unlocked: a losing copy's `git worktree remove` failure already falls back to rm -rf and exits 0, so it never fails the event.

<!-- fr:journal kind=finding scope=debug id=13d399eb572e created=2026-10-11T23:12:51+00:00 state=fixed -->
### 13d399eb572e · finding [fixed] · #1105 fixed: allowlist script manages qualified + bare spellings

scripts/ensure-phase-executor-allowlist.sh now inserts the qualified id and its bare name into the case arm and the Exempt message, each probed as a whole member (position-independent), and no longer strips the bare name. Pinned by tests/unit/test_ensure_phase_executor_allowlist.py#test_the_bare_project_agent_name_is_allowlisted and #test_a_hook_with_only_the_qualified_name_gains_the_bare_one (red before). Dry-run against a copy of a live host hook: both spellings added to arm + message, rationale comment untouched, third run a no-op.

<!-- fr:journal kind=finding scope=debug id=cfc0c820f4a7 created=2026-10-11T23:19:35+00:00 state=fixed -->
### cfc0c820f4a7 · finding [fixed] · #1087 fixed: preflight names every missing prerequisite with an OS install command

require_prereqs (identical block in scripts/install.sh and scripts/bootstrap.sh, pinned by tests/integration/test_install_prereqs.py#test_the_two_copies_of_the_preflight_are_identical) collects every missing command and prints brew / apt-get / dnf / yum / apk / pacman / zypper install lines, plus uv's own installer. bootstrap now checks rsync too, before cloning. Pinned by TestEveryMissingPrerequisiteIsNamedWithItsInstallCommand (red before). The half-install half of #1087 was already closed by cloud-triage R19 (a Claude-Code home without installed_plugins.json/settings.json exits 1 naming them, tests/integration/test_install_sh.py#TestInstallRefusesWithoutRegistrationFiles); that refusal is kept rather than auto-seeding, as that spec decided.

<!-- fr:journal kind=review scope=debug id=a9956f032653 created=2026-10-11T23:20:08+00:00 -->
### a9956f032653 · review · Milestone review: self-review of the full diff, no findings

Reviewed inline rather than by subagent: the org agent-worktree hook forces a general-purpose reviewer into a worktree cut from main, where this branch's diff is invisible. Checked: lock placement covers both creating paths and is released by the EXIT trap on mimic_default's exit; ids interpolated into grep/sed contain only [a-z:-]; the message probe is whole-member; fr-phase-executor-guard.sh already matched both spellings (so the bare name was previously undispatchable either way: refused WITH the flag by the guard, WITHOUT it by the org hook). Out of scope, noted: WorktreeRemove's agent-* path stays unlocked (tolerant: rm -rf fallback, exit 0).
