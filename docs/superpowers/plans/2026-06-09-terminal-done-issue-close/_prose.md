# Terminal-Done Issue close (#294)

## Why

#290 closes a phase's tracking Issue only when `pr_state` itself transitions
the card to Done. A card moved to Done out-of-band (operator manual move, or
VK auto-move on merge) is never scanned by `pr_state`; `reap_orphans` reaps its
workspace but doesn't close the Issue. So the Issue stays OPEN, the phase reads
incomplete, and downstream phases stay blocked — exactly what wedged
`runs-fr` phase 4 (#5).

## What

Per the spec (`docs/superpowers/specs/2026-06-09-terminal-done-issue-close-design.md`),
**reconcile the backlog** with one bounded sweep:

`reconcile_done_issues` (in `pr_state.py`, reusing the idempotent close helper —
no circular import with `workspaces`) lists `status="Done"` cards and closes
each card's linked Issue, derived from the **title** (`gh#N: [owner/repo]` —
the Issue's own coordinates, independent of any PR url). Bounded by a persisted
seen-set of `"<owner/repo>#<n>"` keys: the first post-deploy tick closes the
whole open backlog, every later tick is ~0 gh calls, new Done cards close once.
Wired into `bridge_cli.main()` after `reap_orphans`, inside a guard.

A single Done-card sweep subsumes the reap-time case (a just-reaped card is
still a Done card) — so `reap_orphans` stays purely workspace-focused.

## How (phases)

1. **Sweep** — `reconcile_done_issues` (TDD): title-based close, seen-set
   bound, defensive.
2. **Wire + persist** — `_DONE_CLOSED_PATH` + load/store (mirroring
   `_seen_plans`), call after `reap_orphans` guarded; E2E + regression sweep.
3. **Version bump + gates.**

Fully agentic, TDD. The live repro (manual-Done card → tick → Issue closed +
dependent unblocks) is a post-merge Test Plan in the spec and PR body.
