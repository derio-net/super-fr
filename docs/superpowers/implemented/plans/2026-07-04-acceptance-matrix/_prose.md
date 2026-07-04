# 2026-07-04-acceptance-matrix

Implements `docs/superpowers/specs/2026-07-04-acceptance-matrix-design.md`
(PR #352, operator-approved): the `fr acceptance` CLI group, pipeline
integration (plan linkage, self-review lints, status surfaces), the
three-channel nag, init/backfill scaffolding, and super-fr's own dog-food
matrix.

## Reference implementation

Generalizes `cnc-fr`'s `scripts/acceptance/build_report.py` (366 LOC, shipped
2026-07-04). A local checkout lives at `/Users/derio/Docs/projects/STOA/cnc-fr`
for consultation; every ported semantic and all seven review-caught traps are
restated in the spec §4, so the plan is executable without that checkout.

## Approach decisions (implementation-owned)

- **`fr.acceptance` subpackage** under `packages/fr/src/fr/acceptance/`
  (`model.py`, `check.py`, `report.py`, `scaffold.py`) + a Typer sub-app
  `commands/acceptance_cmd.py` — mirrors the `fr.plan` / `fr.isolation`
  subpackage precedent. Pydantic models (`frozen=True`, `extra="forbid"`)
  per repo style, replacing the reference's ad-hoc dict validation.
- **Org/repo genericization** (spec-review finding): the reference hardcodes
  `ORG`/`OWN_REPO`. Port reads optional top-level `org:` / `repo:` keys in
  `matrix.yaml` (written explicitly by `fr acceptance init`), falling back to
  parsing `git remote get-url origin`. Deterministic in CI, portable to any
  repo.
- **`add` appends textually** to `matrix.yaml` (a load→dump cycle would
  destroy the header comment block), then re-validates via a full
  `load_matrix` before leaving the file changed (write-then-validate with
  rollback on error).
- **`--added-since <ref>`** reads the base matrix via
  `git show <ref>:docs/acceptance/matrix.yaml`; a base without a matrix means
  every row is an addition.
- **Digest is a dedicated verb** (`fr acceptance digest`, markdown to stdout
  with an idempotence marker comment) rather than a `check` flag — `check`
  owns an exit-code contract the digest must not inherit. Spec §6.3 says
  "may reuse the check output with a --digest formatter"; a sibling verb
  reusing the same row-classification code satisfies that intent.
- **Trap 7 code-enforced** (per #328 "invariants get a gate, not prose"):
  `check` parses the repo's `acceptance-report.yml` workflow when present and
  warns for any own-repo ref whose path is not covered by the PR-time path
  filters.
- **Self-review adoption path**: the zero-linked-rows lint is an **error**
  when `docs/acceptance/matrix.yaml` exists, a **warning** (nudging
  `fr acceptance init`) when it doesn't — existing matrix-less repos keep
  passing until they adopt.
- **`fr plan edit --complete-phase` nudge**: completing a phase whose
  `acceptance:` rows are still `not-implemented` prints a warning naming the
  unflipped ids (completion proceeds — leaving `skipped` debt is legitimate,
  silence is not).
- **Plan-linkage validation in `check`** (live plans' `acceptance:` ids must
  exist) lands in Phase 6 with the schema field, not Phase 2 — `check` reads
  phase YAMLs via `yaml.safe_load` (tolerant of unparseable plans, mirroring
  the bridge's skip-gracefully doctrine).
- **PhaseHeader schema event**: `acceptance: tuple[str, ...] = ()` on the
  closed-world `PhaseHeader` is the intentional "new field ⇒ new logic"
  version event the types.py docstring describes; ships with the minor bump
  (Phase 8). Round-trip is cheap: plan edits mutate raw YAML dicts, so only
  parse (types.py) and create (`PhaseSpec`/`_build_phase_doc`) change.
- **Skill line caps**: `fr-goal` (120/120) and `fr-execute` (119/120) are at
  the test-enforced ceiling — their Phase 7 additions must compress existing
  text, verified by the existing `test_under_120_lines`.

- **Sibling github links pin literal `main`** (not "their default branch" —
  spec §4 report). A master-defaulted sibling gets stale links; v1 shortcut,
  per-repo override deferred to demand. (Recorded post-review, #352.)
- **Digest upsert keys on the body marker** (`fr-acceptance-digest` via
  `in:body` search), not the issue title — a pre-existing issue titled
  "Acceptance debt" must not be hijacked. (Review finding, #352.)
- **super-fr's own workflow installs fr from the checkout**
  (`uv tool install ./packages/fr`), deviating from the scaffolded template's
  git+https install — installing from `@main` would gate every PR that
  changes `fr acceptance` behavior with the pre-PR fr (version skew; review
  finding, #352). Downstream repos keep the template's remote install.

## Chicken-and-egg notes (dog food, §9)

super-fr's own matrix is born in Phase 8: `fr acceptance init`, then backfill
rows for all 10 specs carrying `## Test Plan` (4 live + 6 archived — the
archive-twin guard is exercised for real), with this spec's rows as the first
entries. The same phase links row ids into THIS plan's phase YAMLs
(`acceptance:` field exists from Phase 6), so `fr plan self-review` and
`fr acceptance check` both pass on the delivered branch.

## Mid-flight row additions (spec decision 6)

Any acceptance row added during implementation beyond the brainstormed set is
listed with a one-line defense in the PR body ("rows added since brainstorm"),
generated via `fr acceptance check --added-since origin/main`.

## Out of scope

Cross-repo live CI verification, `check --live`, report theming (spec §8).
