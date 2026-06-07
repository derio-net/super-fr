# Isolation guard + fr-spelling rename

Spec: docs/superpowers/specs/2026-06-07-isolation-guard-fr-rename-design.md
Closes #265 and #272 in one branch, one PR (fr-goal local mode).

## Why

A real fr-goal run proceeded without isolation (#265) — skill prose left
read-only/cluster ops in a gray zone and nothing deterministic guards inline
Bash. And the v3 rebrand deliberately left four `vk` spellings in place
(#272); exploration found four more (state dir, cache dir, vk-init strings,
`VK_BRIDGE_*` env vars), all now in scope per the operator's Q&A.

## Shape

- **P1** closes the prose gray zone (isolation precedes *everything*; "start
  with X" reorders work items, never the first action).
- **P2** ships the deterministic backstop as plugin hooks: a PostToolUse
  sentinel writer keyed by `session_id` (set when fr-goal / fr-brainstorming /
  fr-execute is invoked) and a PreToolUse Bash guard that denies base-repo-cwd
  commands other than `fr isolation …` while the sentinel lives. Strict mode
  per Q&A: host-side git/gh ops run from the worktree cwd. Same philosophy as
  `~/.claude/hooks/agent-worktree-required.sh`, extended to inline Bash. It is
  a discipline backstop, not a security boundary.
- **P3** does every rename as fr-first dual-read with a loud legacy warning —
  the same playbook as the label cutover (#270). `VK_DERIO_OPS_PROJECT_ID`
  stays: it names the VibeKanban board (product domain), not the old brand.
- **P4** adds `fr init migrate` (dry-run default, `--yes` writes), runs it on
  this repo, and sweeps the docs to the new spellings.
- **P5** bumps minor → 3.1.0 (new mandatory behavior: the guard; new
  subcommand: `fr init migrate`).
- **P6 [manual]** back-loaded operator work: host secrets move (printed
  block, never auto-executed), pod relics (`vk-issue-bridge.py`, checkout
  rename + VK board entry + `FR_BRIDGE_*` env in willikins), fleet sweep of
  `fr init migrate` across frank / willikins / omada-controller.

## Sequencing

P1, P2, P3 are independent roots. P4 needs P3 (migrate writes what the
dual-read reads). P5 gates on everything agentic. P6 is post-merge operator
work and depends on the released 3.1.0.

A follow-up issue to remove the vk fallbacks one minor version later gets
filed at close-out (mirrors #270's removal of the label dual-read).

## Test Plan

Carried in the spec (post-merge, operator-driven): hooks live-fire in a
scratch repo, self-migration check, pod bridge lock + env verification after
the next upgrade.
