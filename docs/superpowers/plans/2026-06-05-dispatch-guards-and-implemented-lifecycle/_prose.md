# Dispatch guards + implemented/ lifecycle — implementation plan

Spec: `docs/superpowers/specs/2026-06-05-dispatch-guards-and-implemented-lifecycle-design.md`
(read it first — it carries the full postmortem, the audit findings with
file:line references, and every operator decision).

## Why

On 2026-06-05 `vk apply --yes` dispatched two already-implemented plans,
creating 13 spurious GitHub Issues. Root causes, confirmed by reading
`vk.bridge.*` and the apply path end-to-end: (1) step ticks are invisible to
dispatch — `_phase_complete` needs gh evidence that can't exist before an
Issue does, so `diff()` unconditionally emits `IssueCreate` for undispatched
phases; (2) `_drift_warnings` skips undispatched phases entirely, so the
dry-run was silent; (3) `RenderedState.archive_decision` is computed and
consumed by nothing — there is no archive step in the lifecycle.

## What ships

- `plan_locally_complete()` — the local-only completion predicate (steps all
  ticked OR `completion.at`), shared by render warnings, diff guard, spec
  roll-up, and the archive gate.
- `diff(force_create=False)` suppresses `IssueCreate` for locally-complete
  undispatched phases; suppressions are data (`Diff.suppressed`), rendered by
  apply and status; `vk apply --yes` exits 2 when everything was suppressed
  (`--force` overrides).
- `vk status <plan-dir>` — read-only, allowlistable report (factual header
  line with created-age/ticks/dispatch state; per-phase table; all rendered
  warnings including reverse drift; archive nudge). Never calls a mutation —
  there is a test asserting that.
- `docs/superpowers/implemented/{plans,specs}/` taxonomy; `vk archive`
  (single + `--all`) moves finished plans and, when a spec's rows all resolve
  as implemented (gh contents lookup for cross-repo rows, operator
  confirmation as fallback), the spec; `vk migrate dirs` converts legacy
  `archived-plans/` layouts; every other verb hard-stops (exit 2) on a legacy
  layout.
- `vk undispatch <plan-dir>` — close created Issues with a comment, null
  `tracking_issue` fields; idempotent; apply-style failure accumulation.
- Skill-doc updates (vk-dispatch gh-evidence pre-flight + Issue URLs in
  writeback commit bodies; layout references) and a minor version bump.

## Invariants to preserve

- **Renderer purity.** No I/O, no clock in `render.py`/`diff.py`. Age
  formatting lives in the CLI layer.
- **`_phase_complete` is untouched.** It encodes "operator accepted the
  work" (merged-PR evidence); weakening it reintroduces the 2026-05-18
  premature-close incident.
- **Bridge untouched.** Zero changes under `src/vk/bridge/`; the bridge
  suite must pass as-is (Phase 2 has an explicit step for this). Issue
  creation stays operator-only.
- **Exit codes**: 0 success/report, 2 refusal/usage, 4 gh failures,
  5 parse errors.
- **Mixed plans dispatch.** The guard suppresses only locally-complete
  phases; mid-plan resume is never blocked.

## Order

Phases 1 → 2 are the core guard (ship-worthy alone). Phase 3 is independent
(taxonomy + migration). Phases 4/5 consume 1+2 and 1+3 respectively. Phase 6
is independent. Phase 7 (docs + bump) last. Work the numeric order; the
`depends_on` graph allows it.

## Verification

Per step: the test command named in the step. Per phase: `uv run pytest -q
--no-cov && uv run ruff format src/ tests/ && uv run ruff check src/ tests/
&& uv run mypy src/`. Phase 7 ends with the full CI mirror plus
`scripts/bump-version.py minor`.
