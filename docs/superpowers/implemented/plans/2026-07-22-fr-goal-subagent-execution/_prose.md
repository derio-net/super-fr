# fr-goal subagent execution — journal-fed, tier-selected phase dispatch

Implements `docs/superpowers/specs/2026-07-22-fr-goal-subagent-execution-design.md`.

Three harness-agnostic components, built bottom-up so each rests on tested code
beneath it:

- **A — the `fr journal` primitive** (Phases 1–3): a scope-keyed
  (`spec|plan|debug`), append-only, CLI-only durable log under
  `docs/superpowers/journals/`, plus its lifecycle wiring (`fr plan create`
  initializes a plan journal; `fr archive` moves journals with their plan/spec).
- **B — fr-goal subagent-per-phase execution** (Phases 4–5): a harness-neutral
  `tier` on each phase + a `fr models` resolver that binds `tier → model` per
  harness; then the fr-goal skill rewrite that dispatches each phase serially to
  a subagent fed by `fr journal render`, and derives its PR body from the
  journal.
- **C — fr-debugging adopts the journal** (Phase 6): upgrades fr-debugging's
  hand-written step-3 log to the continuously-flushed `debug`-scope journal.

Phase 7 packages: OpenCode mirror sync, the minor version bump, and docs.

## Build order and why

`fr journal` is the spine — everything writes or reads it — so Phases 1–3 land
first (model → CLI → lifecycle). Phase 4 (`tier` + `fr models`) is independent
of the journal and is a second root, but both must exist before Phase 5, which
consumes them. Phase 6 needs only the journal CLI + lifecycle (Phases 2–3).
Phase 7 waits on both skill rewrites (5, 6).

## Key decisions carried from the brainstorm

- **Serial, shared workspace (spec §B.1).** Phase subagents run one-at-a-time in
  the plan's single fr-isolation worktree — never parallel private worktrees.
  Parallelism is `fr apply --to <runner>`'s job, out of scope here.
- **The org worktree hook (option 3).** `~/.claude/hooks/agent-worktree-required.sh`
  blocks a code-writing subagent that lacks its own worktree. Rather than fight
  it or require a manual edit, super-fr ships a dedicated, narrow
  **`fr-phase-executor`** agent type and `install.sh` idempotently ensures that
  type is in the hook's allowlist (safe no-op if the hook is absent). fr-goal
  dispatches phase work as `fr-phase-executor`; if a dispatch is still blocked,
  it **falls back to inline execution** for that phase — correctness and the
  journal are never sacrificed, only the context-isolation optimization.
- **`tier` is harness-neutral (spec §B.2).** The plan never names a model; the
  `tier → model` binding lives in `~/.config/fr/models.yaml` (primary), an
  optional repo override, or a runtime Q&A that persists the choice.
- **No compaction-safety hooks.** Continuous CLI flush is the whole durability
  guarantee; it needs no `PreCompact`/`SessionStart` machinery and stays
  portable across all three harnesses.

## Hard constraints verified at plan time

- **fr-goal SKILL.md is at 120/120 lines** (the `test_skill_validation.py`
  `test_under_120_lines` cap). Phase 5 must compress existing prose to fit the
  new dispatch/tiering/journal content; fr-execute is also at 120, so detail
  can't simply move there. Fallback if it won't fit: push mechanics into the
  spec (which the skill already references), never past the cap.
- **`PhaseHeader` is `frozen=True, extra="forbid"`.** Adding `tier` is an
  intentional schema change — old tooling fails loud on new plans, which the
  minor version bump plus the plan's `fr_version` constraint cover. No data
  migration: existing plans (no `tier`) parse unchanged.
