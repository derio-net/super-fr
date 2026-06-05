# Dispatch guards + implemented/ lifecycle — Design

## Problem

On 2026-06-05 two plans were dispatched via `vk apply --yes` and both were
already implemented. 13 spurious GitHub Issues were created, closed by hand,
and both plans archived by hand (postmortem: this spec's origin).

| Plan | Actual state at dispatch | What apply did |
|---|---|---|
| `2026-05-25-bookmarks-review-tui` | All 15 steps ticked, PR willikins#204 merged | Created 4 OPEN issues (#217–220) |
| `2026-05-02-stoa-company-creation` | Implemented outside vk (15 merged PRs in target repo), 0/59 steps ticked | Created 9 OPEN issues (#16–24) |

Three distinct failure modes, confirmed by reading `vk.bridge.*` end-to-end
plus the full apply path (per the CLAUDE.md bridge-audit rule):

1. **Completion is invisible to dispatch.** For a never-dispatched phase,
   `observe()` returns nothing (`obs is None`), `_phase_complete()`
   (render.py) requires `completion.at` AND an observed merged PR — so it is
   structurally `False` before an Issue exists, *regardless of step ticks*.
   `diff()` then hits `tracking is None or obs is None → IssueCreate`,
   unconditionally. Worse, `_drift_warnings()` does `if obs is None:
   continue`, so the dry-run printed zero warnings for a fully-ticked,
   never-dispatched plan.
2. **Work done outside the plan flow leaves no plan-side signal.** The stoa
   plan was honestly "Not Started" to vk. The evidence lived in the target
   repo (merged PRs, the deliverable tree) — nobody checked.
3. **No archive step in the lifecycle.** `render()` computes
   `RenderedState.archive_decision` (all phases complete) but *nothing
   consumes it* — grep confirms only two unit tests reference it. Completed
   plans linger in `docs/superpowers/plans/` and stay dispatchable forever.

Secondary usability findings from the same session:

- `vk apply <dir>` (read-only dry-run) and `vk apply <dir> --yes` (mutating)
  are indistinguishable to permission classifiers — the audit path gets
  blocked along with the mutation path.
- Reconciliation is one-directional: gh→plan drift (Issue closed upstream,
  plan header still "Not Started") is only discoverable by reading Issues.
  (The renderer already emits the error-severity "Issue closed but plan is
  incomplete" warning; it just needs a read-only surface to print it.)
- Un-dispatching is N manual `gh issue close` calls plus hand-editing yaml.
- Dispatch commits carry bare messages; the created Issue URLs aren't in the
  commit body. (`vk apply` never commits — the dispatching agent does — so
  this is a skill-doc fix, not CLI.)

## Design overview

Four layers, innermost first. Data flow stays the canonical
`parse → observe → render → diff → apply`; nothing new is stored in plan
files ("if it can be derived, don't store it").

### 1. Pure projection layer: `plan_locally_complete`

New public helper in `render.py`:

```python
def plan_locally_complete(phase: PhaseDoc) -> bool:
    """Local-only completion signal: completion.at set, OR steps non-empty
    and all ticked ('x' or '-'). No gh observation involved."""
```

Deliberately a *different* predicate from `_phase_complete()`, which encodes
"operator accepted the work" via merged-PR signals and stays untouched (the
2026-05-18 premature-close incident is why that one must keep requiring gh
evidence). `spec.py:229-235` already implements this exact OR inline; it is
refactored to call the helper — two call sites, one definition.

### 2. Guarded diff: `force_create`

`diff()` gains `force_create: bool = False`. For an undispatched phase
(`tracking is None or obs is None`) that is `plan_locally_complete`, no
`IssueCreate` is emitted unless `force_create=True`. Suppression is data,
not a log line: `Diff` grows `suppressed: tuple[SuppressedCreate, ...]`
(`phase_number`, `reason`) so every consumer (status, apply dry-run, JSON
output) renders it.

| Undispatched phase state | Today | After |
|---|---|---|
| Locally incomplete | IssueCreate | IssueCreate (unchanged) |
| Locally complete | IssueCreate ← the bug | suppressed, reported |
| Locally complete + `--force` | — | IssueCreate |

Mixed plans (some phases complete, some not) dispatch the incomplete phases
and report the suppressions — the normal mid-plan resume case is never
blocked.

The bridge needs zero changes: its call site passes nothing (guard active by
default) and is doubly protected by `apply(skip_issue_create=True)` —
Issue creation was already operator-only.

### 3. Warnings without the blind spot

`_drift_warnings()` keeps `obs is None → skip` only for PR-based checks; a
new warning fires for undispatched phases that are locally complete:
`"Phase N: M/M steps ticked but never dispatched — refusing to create"`.

Staleness is **information, not heuristics**: no thresholds, no slug scans,
no new render parameters. `vk status` and the `vk apply` header always print
one factual line per plan:

```
plan: stoa-company-creation · created 2026-05-02 (34 days ago) · 0/59 steps · never dispatched
```

Age formatting happens in the CLI layer; render stays pure. A month-old
never-dispatched plan announces itself to the human or agent reading it.

The stoa-class gap (work done outside the plan flow) is covered
procedurally, where the information actually lives:
`skills/vk-dispatch/SKILL.md` pre-flight gains a mandatory item — before
dispatching a plan with zero dispatched phases, search the target repo via
gh for evidence the work already landed (merged PRs mentioning the plan/spec
slug, the plan's deliverable paths). Evidence found → stop and reconcile
with the operator instead of dispatching.

### 4. Directory taxonomy: `implemented/` mirror

```
docs/superpowers/
  specs/                  ← active
  plans/                  ← active
  implemented/
    specs/                ← vk archive moves specs here
    plans/                ← vk archive moves plans here
```

Archival is a pure prefix change (`plans/X` → `implemented/plans/X`);
relative tails stay identical. The legacy name `archived-plans/` is
recognized read-only for resolution fallbacks but is otherwise a hard-stop
(see Migration).

Spec tables are never rewritten on archive: `spec.py::_resolve_local_plan_dir`
falls back `plans/<X>` → `implemented/plans/<X>` → legacy
`archived-plans/<X>` when the recorded path doesn't resolve.

## New CLI verbs

All thin typer wrappers in `src/vk/commands/`, registered in `cli.py`,
following apply_cmd's conventions (factory-hook gh client, text+json output,
shared exit codes). The read path of `_apply_one` (parse → observe → render
→ diff → format) is extracted into a shared helper that both `apply` and
`status` call, so the two can never drift.

### `vk status <plan-dir>` — read-only, allowlistable

Same pipeline as apply's dry-run, but no mutation vocabulary and no `--yes`
to misfire. Prints: the factual header line, a per-phase table (steps
ticked, tracking issue, lifecycle label, would-create / would-refuse), all
rendered warnings (including the reverse-drift error "Issue closed but plan
is incomplete" — the content-factory case), and the archive hint when
`archive_decision` is true. `--format json` mirrors apply's. Exit 0 even
when drift exists (a report, not a gate); 5 on parse error. Safely
allowlistable as `vk status*`.

### `vk archive [<plan-dir> | --all]`

Gate per plan: every phase `_phase_complete` OR (undispatched AND
`plan_locally_complete`) — done from both gh's and the plan's view.
`--force` overrides (single-plan only). Then:

1. `git mv docs/superpowers/plans/X docs/superpowers/implemented/plans/X`.
2. Spec decision: if every local plan row of the owning spec now resolves
   under `implemented/plans/`, and cross-repo rows resolve as done via the
   gh contents API (operator confirmation when unresolvable), `git mv` the
   spec → `implemented/specs/`.
3. Print what moved + "commit and PR this" hint. Committing is the
   operator's.

`--all` walks `docs/superpowers/plans/`, applies the same gate per plan,
archives every plan that passes, reports skipped plans with reasons, and
runs the spec decision once at the end of the sweep (a spec may become fully
implemented only after several of its plans archive in one sweep —
evaluating after the walk avoids order dependence). `--force` with `--all`
is refused (exit 2): blanket-forcing is how the incident happens in reverse.

Refuses on a dirty worktree at the affected paths. Exit 2 on gate failure.

`vk apply` and `vk status` print "plan complete — run `vk archive <dir>`"
whenever the archive **gate** (not the narrower `archive_decision`) passes —
otherwise a bookmarks-class plan (ticked but never dispatched) would be
refused dispatch yet never nudged to archive. The gate lives in one shared
library function consumed by archive, apply, and status;
`RenderedState.archive_decision` stays as the renderer's strict
all-`_phase_complete` signal and gains its first real consumer (the gate
uses it for the dispatched-phase arm).

### `vk undispatch <plan-dir>`

The inverse of dispatch, for "these Issues were created in error". For each
phase with a `tracking_issue`:

1. Close the Issue with comment `vk undispatch: dispatched in error from
   <plan-slug>` and reason `not_planned`.
2. Null the `tracking_issue` field in `NN.yaml` via new
   `plan_ops.clear_tracking_issue` (sibling of `set_tracking_issue`).

Dry-run by default, `--yes` to execute. Idempotent: re-running skips
already-closed Issues and already-nulled fields. Failures accumulate
per-phase (exit 4 if any), like apply. Deliberately does NOT touch VK cards
or workspaces (`reap_orphans` handles those once cards lack live Issues) and
does not revert the dispatch commit — it makes new state, not history
surgery.

### `vk migrate dirs` — eager legacy migration

New subcommand under the existing migrate app (dry-run by default, `--yes`
to write):

1. `git mv docs/superpowers/archived-plans docs/superpowers/implemented/plans`
   (when present; v1 flat `.md` archives move along untouched — `dirs`
   relocates, never converts; conversion stays `v1-to-v2`'s job).
2. Create `docs/superpowers/implemented/specs/`; move every spec whose
   `## Implementation Plans` rows all resolve to implemented plans, using
   the same resolution logic as `vk archive` (gh lookup for cross-repo rows,
   operator confirmation when unresolvable).
3. Print the `git mv` operations performed; commit/PR is the operator's.

**Hard-stop enforcement:** every vk verb — read or mutating — exits 2 when
`docs/superpowers/archived-plans/` exists, with the message "legacy layout
detected — run `vk migrate dirs --yes`, then commit". The only exemptions
are `vk migrate dirs` itself and verbs that don't resolve a superpowers tree
(`vk --version`, `vk skills`, `vk isolation …`, `vk init …`). No
banner-that-gets-overlooked: migration happens at the first use of the new
version in each repo.

## Skill-doc changes (same PR)

- `skills/vk-dispatch/SKILL.md` pre-flight: (a) the gh-evidence check for
  never-dispatched plans (stoa); (b) instruct the dispatching agent to
  include the created Issue URLs in the writeback commit body (forensics /
  undispatch trail).
- `skills/vk-progress/SKILL.md`, `skills/vk-execute/SKILL.md`,
  `skills/vk-goal/SKILL.md`: archived-plans references → the new
  `implemented/` layout + the new verbs.
- `vk skills` overview: add status / archive / undispatch / migrate dirs.

## Error handling

- All verbs accumulate per-phase failures rather than short-circuiting
  (apply's doctrine).
- `archive` re-checks its gate between the plan mv and the spec mv; a failed
  spec resolution leaves the plan archived and says so — re-running the
  command later completes the spec move. gh-API failures degrade to the
  operator-confirmation prompt, never to silent guessing.
- `undispatch` partial failure: already-closed/already-nulled work is
  skipped on retry.
- Exit codes (existing conventions): 0 success / clean report; 2 usage,
  guard refusal, archive gate failure, legacy-layout hard-stop, dirty-tree
  refusal, `--force --all`; 4 gh/network failures during undispatch/apply;
  5 parse error.

## Testing

Mirrors existing patterns: `FakeGhClient`, fixture plan folders, typer
`CliRunner`.

1. **Pure layer:** `plan_locally_complete` truth table (ticked/unticked ×
   completion.at × `-` skips × empty steps); `diff(force_create=)`
   suppression matrix including the mixed-plan case; `_drift_warnings`
   fires for undispatched-complete phases — the bookmarks regression test,
   asserting the old `obs is None` blind spot stays dead.
2. **Spec layer:** `spec.py` on the shared predicate keeps existing tests
   green; `_resolve_local_plan_dir` fallback chain
   (`plans/` → `implemented/plans/` → `archived-plans/`).
3. **CLI:** `status` never calls a mutation method (asserted against the
   FakeGhClient call log — the allowlistability guarantee as a test);
   `apply --yes` exits 2 when every create was suppressed; `--force`
   end-to-end; `undispatch` close + null + idempotency; `archive` gate,
   both mvs, dirty-tree refusal, `--all` sweep with end-of-sweep spec
   decision, `--force --all` refusal; `migrate dirs` rename + spec moves;
   legacy hard-stop on every verb that resolves the tree.
4. **Bridge regression:** the existing bridge suite passes untouched —
   proving `diff()`'s new parameter default leaves `tick()` semantics
   identical (B2-style guarantee).

## Versioning

Minor bump (new verbs + new mandatory behavior), per CLAUDE.md. The
hard-stop on legacy layouts is the "new mandatory behavior" — release notes
must lead with `vk migrate dirs`.

## Out of scope

- Full cross-repo plan resolution for `vk spec status` (the `Unreachable`
  state) — the gh contents lookup ships here only as the narrow
  spec-archival resolver in `vk archive` / `vk migrate dirs`. Generalizing
  it to status reporting is its own feature.
- A `deliverable:` path field in `_meta.yaml` (deliverable-existence
  staleness check) — rejected as new schema surface for a weak heuristic;
  the vk-dispatch pre-flight covers the gap procedurally.
- VK card/workspace cleanup in `undispatch` — `reap_orphans` already
  archives workspaces for Done/missing cards.
- Threshold-based staleness warnings — replaced by the always-on factual
  header line.

## Implementation Plans

(added by vk-plan)
