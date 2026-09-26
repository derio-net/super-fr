# fr-goal: findings in scope, proportionality, per-step cost, independent spec review

Implements `docs/superpowers/specs/2026-09-24-fr-goal-scope-proportion-cost-design.md`
(gh#597 §1 and §4, gh#593 options 0 and 2).

The plan is phased by spec section, because the sections touch mostly disjoint
modules. Phase 1 opens with the walking skeleton: a real, small fix (the
shared `message.id` dedupe) that exercises the telemetry and test path the
rest of §D builds on. At the operator's request, §D's core and its OpenCode
reader stay in one phase to keep the phase count, and so the handoff cost,
down.

| Phase | Section | Depends on |
|---|---|---|
| 1 | D: dedupe skeleton, run v6 `main_session`, Claude Code and OpenCode readers, `fr run cost` | none |
| 2 | A: out-of-scope fold state, `review_scope`, operator guard, render | 1 |
| 3 | C: plan `files` and `estimate_lines`, `fr plan proportionality`, deliver evidence | 1 |
| 4 | E: `fr-spec-reviewer`, flat-step evidence; skill prose, mirrors, explainer, 4.20.0 | 2, 3 |
| 5 | Manual: live post-merge `/fr-goal` on Claude Code and OpenCode | 4 |

## Invariants every phase keeps

- Telemetry never raises. An unmeasurable window is recorded as absent,
  never as zero.
- The journal parser projects header tokens **by name**. New tokens
  (`out_of_scope`, `review_scope`, `answered_by`) are ignored by an older
  `fr`, which reads the finding as open (fail closed). The journal kind stays
  at stamp 1.
- Plans stay `schema_version: 2`. The new `PhaseHeader` fields follow the
  `tier`/`skeleton` precedent: optional, omitted when unset, and gated by an
  `fr_version` floor.
- Only the run kind moves (5 → 6), with a registered migration, a validator,
  and the every-hop chain assertion.
- The two `fr-goal.yaml` copies (`plugins/super-fr/workflows/` and
  `packages/fr/src/fr/workflows/`) stay identical.
- After any skill or agent edit, run BOTH `scripts/sync-opencode.py` and
  `scripts/sync-hermes.py`.
- Nothing weakens `deliver`'s `--evidence tests=<log>` gate.
