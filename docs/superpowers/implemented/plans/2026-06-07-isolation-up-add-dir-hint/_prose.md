# `fr isolation up` `/add-dir` hint — plan

Implements [#281](https://github.com/derio-net/super-fr/issues/281), the
deferred "Out of scope" item from #279. Spec:
`docs/superpowers/specs/2026-06-07-isolation-up-add-dir-hint-design.md`.

## Why this shape

Research (in the spec) established that **mid-session automation is
impossible**: only a live `/add-dir <path>` typed by the operator registers an
additional working directory in the running session, and the agent cannot
invoke slash commands. So the durable fix is a **suggestion** — `fr isolation
up` prints a copy-pasteable `/add-dir <worktree>` line, gated on the
`CLAUDECODE` env var so a plain shell (where the slash command is meaningless)
sees nothing.

The whole change is one cohesive, fully-agentic unit, so it is a single phase.
The only operator-driven work is the post-merge **Test Plan** in the spec
(verifying tip → `/add-dir` → cwd-persists in a live session) — back-loaded by
nature, not a plan phase.

## Phase 1 — Emit the gated hint

TDD throughout:

- **Task 1 (test-first):** two `CliRunner` tests pin the gate — `env={"CLAUDECODE":
  "1"}` ⇒ output carries `/add-dir ` and the worktree path; `env={"CLAUDECODE":
  None}` ⇒ summary only, no `/add-dir`. Then the minimal implementation: add
  `import os` and one conditional `typer.echo` after the existing summary line
  in `up()`. The hint lives at the CLI layer, not the `Target` lifecycle object
  — UX copy and session-awareness belong with the CLI's existing summary echo.
- **Task 2 (docs + release):** fold one sentence into the fr-isolation SKILL.md
  exec-bridge bullet documenting the `/add-dir` escape hatch, then
  `scripts/bump-version.py patch` (3.1.2 → 3.1.3 — `src/` and `skills/` are
  installer-shipped) and run the local gate (ruff + pytest).

Existing isolation_cmd tests pass unchanged: their assertions are substring
checks the purely-additive hint cannot break.
