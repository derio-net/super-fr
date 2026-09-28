# Requirements traceability (#759) — implementation plan

Spec: `docs/superpowers/specs/2026-09-28-requirements-traceability-design.md`.
Operator decisions d0–d13 live in the spec journal
(`docs/superpowers/journals/specs/2026-09-28-requirements-traceability.md`).

## Shape

Four layered phases (operator-approved "Approach A"). Each phase owns one layer, and
dependencies run one way:

1. **Skeleton**: the pure `fr/requirements.py` module (parse the §B tables, §C checks,
   §D coverage partition) behind `fr spec requirements`. No artifact shape moves, so CI
   goes green on real logic before anything touches a closed-world model.
2. **Artifact shapes**: the journal tokens (`input`, `unconfirmed`), record 2→3 and
   matrix 1→2 (the matrix kind's first move past 1, so `Matrix.schema_version` lands
   too), the verbs, and `fr migrate artifacts --yes` over this repo's own artifacts.
3. **Run gates**: `requirements`, `coverage` and `requirement-rows` as derived
   evidence; the manifest (`spec-review` at `tier: hard` and emitting `acceptance`);
   three new required PR-body sections and the `unconfirmed` bucket.
4. **Prose**: fr-spec-reviewer (traceability first), fr-brainstorming / fr-goal /
   fr-acceptance, both mirror generators, the explainer, AGENTS.md, and row status moves.

Phases 1 and 2 are independent. Phase 3 needs both.

## Things an executor must not miss

- **Both mirror generators** after any skill or agent edit: `sync-opencode.py` AND
  `sync-hermes.py` (AGENTS.md: three sessions have hit this).
- **Resolution state has three gatekeepers** (review s1): `journal_cmd.RESOLUTION_STATES`,
  `record/apply._journal_writes`, `record/model.ResolutionState`. Move them together.
- **This run crosses its own gate change.** Phase 3 edits `fr-goal.yaml` while run
  `2026-09-28-feat-gh-759` is using it. Step ids don't change, so there is no drift, and
  this run's brainstorm carries no `requirements` evidence, so §G's "predates the
  requirements gate" path is what this run itself will record at spec-review and
  deliver. That path is exercised live by delivering this PR.
- **The `.html` explainer is generated, not hand-edited** — follow
  `.claude/rules/explainers-currency.md` byte-for-byte check first.
- Always `uv run fr …` inside the worktree, never the global `fr`.
