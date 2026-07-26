# Journal: 2026-07-26-fr-goal-isolation-deadlocks

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-07-26T15:30:27 -->
### d1 · decision · Batched Q&A unavailable — decisions taken under stated assumptions

This run is a non-interactive vibe-kanban dispatch: no AskUserQuestion tool is exposed, so fr-goal §1's operator touchpoint cannot execute. Both issues are unusually prescriptive (recommended options, plus a 'this settles it' follow-up comment on #420), so the four operator-owned decisions below are taken explicitly and surfaced in the PR body for override rather than blocking the run.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-07-26T15:30:28 -->
### d2 · decision · #420 backstop ships as a super-fr plugin hook, not an org-hook mutation

The issue comment argues the fix must ride a *universally reachable, versioned* lever and rejects prose because 'agent-worktree-default.md has no canonical copy in any repo'. plugins/super-fr/hooks/hooks.json satisfies that reasoning strictly better than mutating ~/.claude/hooks/agent-worktree-required.sh: it is versioned in-repo, unit-testable, and already the delivery path for fr-isolation-guard.sh / fr-isolation-required.sh on every host. Claude Code runs every matching PreToolUse hook and a deny wins, so a super-fr-owned refusal overrides the org hook's early 'exit 0' without editing a file super-fr does not own. The org hook still gets the checklist's stderr repair via ensure-phase-executor-allowlist.sh.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-07-26T15:30:28 -->
### d3 · decision · The refusal is unconditional, not gated on a live pipeline sentinel

#420's checklist says 'while a pipeline sentinel is live'. Gating on the sentinel would not fire in the reported scenario's own generalisation: fr-pipeline-sentinel.sh deliberately writes NO sentinel when the session cwd is a linked worktree ('this IS the isolation workspace'), which is exactly where an fr-goal run lives after §1. A sentinel-gated backstop would therefore stay silent for worktree-launched fr-goal sessions — reproducing the silent poisoning it exists to stop. The combination super-fr:fr-phase-executor + isolation=worktree is never valid (the agent is defined as running inside an already-active fr workspace), so the refusal is unconditional.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-07-26T15:30:28 -->
### d4 · decision · #421: bless the chained-cd escape; do not build per-repo sentinels

The known circumvention 'cd /tmp && cd <other-repo> && …' is the same shape an existing test already blesses by name — test_cd_then_back_into_repo_allowed_by_design, whose docstring cites the guard's own axiom 'discipline backstop, not a security boundary'. Closing it would flip that test and re-characterise the hook. So it is blessed EXPLICITLY (comment + deny message + a named test) rather than closed. Per-repo sentinels are declined: the issue itself flags a multi-repo fr workspace as not yet designed and warns against scope creep.

<!-- fr:journal kind=decision scope=spec id=d5 created=2026-07-26T15:30:28 -->
### d5 · decision · Version bump: minor (3.19.0)

AGENTS.md: minor = 'user-visible workflow additions (new subcommand/skill/mandatory behavior)'. This PR ships a NEW hook that can refuse a previously-succeeding dispatch, plus a new allowance in an existing hook — mandatory behaviour on both counts, not a skill-copy patch.

<!-- fr:journal kind=discovery scope=spec id=x1 created=2026-07-26T15:30:28 -->
### x1 · discovery · docs/audits/2026-07-24-open-issue-triage.md does not exist on main

The task brief points at it for triage rationale. Neither docs/audits/ nor docs/superpowers/ carries that file at a63c180; docs/audits/ holds only 2026-06-10-repo-audit.md and 2026-07-24-scope-289-harness-neutral-decision.md. Proceeding from the issue bodies, which are self-contained.

<!-- fr:journal kind=review scope=spec id=r1 created=2026-07-26T15:33:14 -->
### r1 · review · Spec review vs codebase: three claims corrected

1) Hook delivery is the marketplace 'rsync -a --delete <repo root>' into $MARKETPLACE_DIR resolved via ${CLAUDE_PLUGIN_ROOT}, not a per-file hook copy in install.sh; corrected, and test_plugin_hooks.py::test_hooks_json_parses identified as an EXACT-set assertion that the new Agent matcher will break. 2) Neither .opencode/ nor .hermes/ carries an agents/ tree, so agents/fr-phase-executor.md has no generated mirror — only skills/fr-goal/SKILL.md does. 3) The Hermes guard sibling is marker-based, already computes an effective_dir from a leading cd, and allows non-fr repos via fr_isolation_decide_cwd — #421 is Claude-Code-only, and Hermes has no isolation flag on delegate_task so #420 is unrepresentable there. Spec updated on all three.
