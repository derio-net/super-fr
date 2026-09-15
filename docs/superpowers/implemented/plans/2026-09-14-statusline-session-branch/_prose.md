# Status line v2: session branch and fr-isolation worktree

Spec: `docs/superpowers/specs/2026-09-14-statusline-session-branch-design.md`

## Why

The v1 status-line segment shows the cwd's branch, an `iso: ?` hint that
lists workspaces of *other* sessions, and a gauge of unrelated worktrees. The
operator cannot tell which branch this session works on, or whether it is in
fr-isolation. v2 answers exactly those two questions, colour-coded (green =
fr, purple = not fr), and gives every supported harness a way to render them.

## Shape of the change

**Segment v2 (`plugins/super-fr/scripts/fr-statusline-segment.sh`).** One
shell script, shell + jq + git, never the fr CLI. Input: Claude Code JSON on
stdin, or `--cwd <dir>` with no stdin. Resolution: a live session binding
wins; else the cwd's branch, and fr state when the cwd's toplevel is an fr
workspace; else `none`. Output formats: `plain` (state, branch row,
worktree row), `ansi` (the two rows coloured), `oneline` (≤ 40 chars for
Hermes' pending custom field).

**Claude Code reference status line
(`plugins/super-fr/scripts/fr-statusline-claude.sh`).** Model/context/rate
line, then `branch: … | ~/cwd`, then the worktree row. It finds the segment
next to itself.

**Docs.** fr-isolation SKILL "Session bindings" (plus the generated
`.hermes` / `.opencode` mirrors), README "Isolation", a pointer from the
2026-09-04 spec, and the acceptance matrix.

## Phases

1. **Walking skeleton** — v2 test harness + the no-repo path of the segment
   (`plain` output), CI green. Proves the new three-line contract end to end.
2. **Segment resolution + formats** — bound / stale / cwd-fr / plain /
   detached rules, `--cwd`, `ansi`, `oneline`, timing and no-fr-CLI guards.
3. **Claude Code reference status line** — `fr-statusline-claude.sh` with
   golden tests.
4. **Docs + acceptance** — skill wiring, mirrors, README, spec pointer,
   matrix rows flipped/updated, reports regenerated.
5. **[manual] Operator rollout** — update the plugin, rewire
   `~/.claude/statusline.sh`, look at the footer in a bound and an unbound
   session. Back-loaded: nothing agentic depends on it.

## Approach chosen

Rewrite the segment in place under the same file name (the operator's script
and the plugin cache path already reference it) rather than adding a v2 file
beside v1: the only consumer is the operator's own script, and two segments
would drift. The contract break is called out in the PR body and the skill.
