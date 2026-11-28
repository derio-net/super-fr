# Spec requirements as a table — implementation plan

Spec: `docs/superpowers/specs/2026-11-26-spec-requirements-table-design.md` (R1–R8).

## Shape

One agentic phase, by operator decision: the reader, the validator, the `spec` 1 → 2
rewrite migration, this repo's own migrated specs, the candidate scenario and the prose
all land together. The phase is `hard` because the migration rewrites operator-authored
specs in every consumer repo on the release that ships it, and one refusal turns into a
whole-repo CLI refusal there.

## Order inside the phase

1. Reader table form (R1, R2), then continuation lines and the id-like prefix check (R3)
   behind one `list_layout` walk that the migration reuses — the reader and the rewrite
   must agree on which lines belong to a requirement, or the round trip is meaningless.
2. The validator (R7), so the migrated files have a structural check before they exist.
3. The migration (R4–R6), test-first, with the failure text checked from the CLI.
4. This repo's specs migrated by `fr migrate artifacts --yes` (dogfood; never by hand).
   A refusal on another feature's live spec stops for the operator rather than editing
   that feature's requirements.
5. The candidate scenario, the prose and mirrors, the fragment and the rows.

## Risks

- Continuation joining changes what phase sizing and proportionality read for wrapped
  specs (they read the whole requirement now, not its first line). Plan-review and
  proportionality fixtures that relied on first-line text are fixed in P1.T2.S2.
- `validate_spec` imports from the registry, which imports `structure` at load: the
  import is function-local.
