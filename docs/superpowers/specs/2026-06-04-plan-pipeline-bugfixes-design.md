# Plan-pipeline bugfixes: agentic-purity gate, 1-based phases, label normalization

**Date:** 2026-06-04
**Status:** Approved
**Repo:** derio-net/superpowers-for-vk
**Closes:** #252 (agentic-purity lint), plus three operator-reported defects

## Problem

Four related defects in the plan authoring/dispatch pipeline:

1. **Agentic phases aren't kept pure (#252).** The data model tags phases
   (`tag: agentic | manual`) but has no per-step tag, so a manual-by-nature
   step can be authored into an agentic phase and "escaped" via
   `state: '-'` with a note deferring it to a later manual phase. Nothing
   flags the mis-scoping. Motivating case: frank's
   `2026-05-27--auto--awx-deployment` Phase 3 (agentic) step P3.T1.S3
   ("set the AWX OIDC client secret") was deferred into Phase 5 and the
   missing SSO button was only discovered at deploy time.
2. **Phase numbering can start at 0.** `PhaseHeader.number` is an
   unconstrained int and the parser accepts `00.yaml`. Frank has a live
   plan with a phase 0 (`2026-03-25--repo--safe-update-automation`,
   dispatched as frank#387). Phase numbering must start at 1.
3. **"All phases become GH Issues" is believed but not pinned.** Verified
   true in code review (`diff()` emits `IssueCreate` for every phase
   lacking a `tracking_issue`, manual phases included), but no test pins
   it, so a regression would be silent.
4. **Broken GitHub label slugs on frank.** Spec labels render with a
   leading dash (`spec:-auto--awx-deployment-design`) because
   `render._DATE_PREFIX_RE` strips the date plus exactly one dash while
   frank's slugs use `YYYY-MM-DD--<layer>--<topic>` (double dash). Plan
   labels never strip the date at all
   (`plan:2026-05-27--auto--awx-deployment`).

## Design

### 1. Agentic-purity gate (`vk plan self-review`) — both lints are errors

Two new lints in `vk.plan_ops.self_review()`, severity `error` (the CLI
already exits 1 when any error-severity issue is present):

- **Deferred-step lint.** For each `agentic` phase, for each step whose
  state is `'-'` (skipped): if the step's note references a *later* phase
  (`[Pp]hase\s+(\d+)` with the captured number greater than the current
  phase's number) or contains a defer-phrase (`defer`, `executed in`,
  `moved to`), emit an error. The step belongs in a manual phase.
  Backward phase references ("ported from Phase 1") do not trip the lint.
- **Manual-verb lint.** For each `agentic` phase, for each step whose
  *text* matches a conservative, case-insensitive, word-boundary pattern
  list, emit an error. Initial list: `manually`, `by hand`,
  `via the UI`, `in the UI`, `click`, `SOPS`, `operator sets`,
  `operator provides`. The list is deliberately precision-over-recall:
  the deferred-step lint is the load-bearing detector; the verb lint
  catches the authoring mistake before any deferral happens.

`skills/vk-plan/SKILL.md` gains an authoring rule under **Rules**:
agentic phases must be pure agentic — collect all manual work (secrets,
UI operations, deploy actions) into a dedicated manual phase. The gate
runs at step 7 of the vk-plan procedure (`vk plan self-review`), the
authoring choke point.

### 2. 1-based phase numbering — schema-level

- `PhaseHeader.number: int = Field(ge=1)` in `vk.types`. Parse-time
  rejection: a phase 0 anywhere fails `parse()` with a clear
  `PlanSchemaError` naming the offending file.
- Pre-flight check in `vk.plan_ops.create()` raising `PlanEditError`
  *before* any file is written. Without it, pydantic would only reject at
  the post-write re-parse, stranding a half-built folder — the exact
  failure mode #133 eliminated.
- `skills/vk-plan/SKILL.md` states the 1-based rule explicitly
  (`01.yaml` is the first phase; there is no `00.yaml`).

**Deployment note (frank).** Frank's live plan
`2026-03-25--repo--safe-update-automation` has `00.yaml`. After frank's
bridge pod upgrades vk, `discover_plans` will log a warning and skip
that plan (graceful: `PlanSchemaError` → skip, no crash) and `vk apply`
on it will fail loud. Remediation — finish & archive, or renumber
0→1..N (step ids, labels, issue bodies) — is a frank-side operator
action outside this PR.

**Known limitation.** `vk migrate v1-to-v2` of a v1 plan containing
"## Phase 0" now fails loud at its re-parse step instead of producing a
phase-0 v2 folder. Migration is rare and the error message is clear;
renumber-on-migrate is deliberately out of scope.

### 3. Pin "every phase gets a GH Issue"

No behavior change. New test: a plan with one agentic and one manual
phase, neither dispatched, must produce one `IssueCreate` per phase;
the manual phase's labels contain `manual` and not `vk-ready`. This
keeps the operator dispatch surface (`vk apply --yes`) covering manual
phases (the VK-board dispatch correctly remains agentic/vk-ready-only).

### 4. Label slug normalization — single point in `vk.labels`

- New `normalize_label_slug(slug)` in `vk.labels`: strips
  `^\d{4}-\d{2}-\d{2}-+` — the date prefix **plus all** following
  dashes. Slugs without a date prefix pass through unchanged.
- `plan_label()` and `spec_label()` apply it before
  `_bounded_label_name` (normalize first, then bound, so the 50-char
  truncate+hash applies to the final shape).
- `render._spec_slug` drops its own now-redundant `_DATE_PREFIX_RE`
  date-stripping (keeps stem + `.md` handling).
- `self_review`'s over-long-plan-label lint (#249) checks the
  normalized name, so a slug that normalizes under 50 chars no longer
  warns.

Results: `plan:2026-05-27--auto--awx-deployment` →
`plan:auto--awx-deployment`; spec stem
`2026-05-27--auto--awx-deployment-design` →
`spec:auto--awx-deployment-design`. This matches the legacy label style
already on frank (`plan:agents--restart-resilience`). The `--layer--`
segment is kept verbatim.

**Churn note.** Live issues re-label once at the next apply/tick: the
old dated/dashed labels are removed and the normalized ones added —
safe, both shapes are under the vk-managed `plan:`/`spec:` prefixes.
Stale repo-level label *definitions* are not deleted by this change
(manual operator cleanup, out of scope).

## Testing (TDD)

Failing tests first, per area:

- `tests/unit/test_labels.py` — `normalize_label_slug` cases: single
  dash, double dash, no date prefix, date-only pathological slug,
  normalize-then-bound interplay with the 50-char cap.
- `tests/unit/test_v2_parse.py` — phase 0 in `NN.yaml` fails parse with
  a clear message; phase 1 still parses.
- `tests/unit/test_v2_plan_ops.py` — `create()` pre-flight rejects
  phase 0 without writing files; purity lints (deferred-step forward
  ref → error; backward ref → clean; verb hits → error; manual-phase
  steps never trip either lint); #249 length lint on normalized name.
- `tests/unit/test_v2_render.py` — `_phase_labels` emit normalized
  plan/spec labels.
- `tests/unit/test_v2_diff.py` — manual+agentic IssueCreate pinning;
  label swap (old dated label observed → removed, normalized → added).

## Versioning

`src/**` and `skills/**` change → patch bump via
`scripts/bump-version.py patch` (2.2.14 → 2.2.15), committed with the PR.

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
