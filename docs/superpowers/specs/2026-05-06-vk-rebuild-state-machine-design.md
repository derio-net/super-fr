# VK v2 — single state machine rebuild

**Status:** Draft
**Date:** 2026-05-06
**Repos affected:** `derio-net/superpowers-for-vk` (primary), `derio-net/willikins` (bridge),
all consumer repos with VK plans (frank, kid-laptops, agent-images, etc.)
**Supersedes:** large portions of `2026-04-12-vk-cli-toolchain-design.md`,
`2026-04-27-label-lifecycle-fix-design.md`, and `2026-04-29-vk-cli-hygiene-and-issue-authoring-design.md`
(architectural assumptions of those specs no longer hold)
**Audit:** `docs/superpowers/audits/2026-05-06-vk-system-audit.md` is the
grounding document — read it first if you need the "why."

## Goal

Replace the regex-parser, two-paths-no-reconciler architecture with a
**single state machine + deterministic projections** model.

Concretely:
1. Plan files become the *only* canonical state. Every other surface
   (Issue body, Issue labels, Issue open/closed, PR body, spec-index
   row, VK card status) is a deterministic projection computed from the
   plan.
2. The plan file format becomes a closed-world YAML schema — no more
   regex-scraping of free-form markdown.
3. The CLI's many state-mutation commands collapse into one verb:
   `vk apply` (render + observe + diff + mutate). `--dry-run` is
   the audit. Drift becomes a free observation.
4. The 4 unreconciled state axes from §5 of the audit go away by
   construction (the parallel paths cease to exist).

Success criteria:
- ~60% reduction in source LOC (estimated 2,000 → 800)
- ~80% reduction in state-mutation surfaces (8 reconciler/mutator pairs → 1)
- The plan parser stops being the most-fixed component in the repo
- `vk progress sync`, `vk progress audit`, `vk dispatch migrate`,
  `vk admin labels-sync`, `vk execute claim`, `vk execute pr-opened`,
  and several others are deleted (folded into `vk apply`)
- The bridge in `willikins` becomes a thin wrapper that imports `vk`
  and never writes to any consumer repo

## Non-goals

- **Not a fork.** Same plugin name, same skill names (`vk-plan`,
  `vk-execute`, etc.), same conceptual workflow.
- **Not a feature add.** No new capabilities; strictly architectural.
- **Not changing dispatch/execute UX significantly.** Operator and
  agent flows look similar from the outside; what changes is the
  internals and the CLI surface that maps to them.
- **Not redesigning VK board integration.** Bridge contract preserved;
  bridge becomes thinner.
- **Not adding LLM-powered "smart" anything.** Spec status, completion
  detection, dispatch decisions — all purely mechanical.
- **Not a backwards-compatible upgrade.** Hard cutover to v2.0.0; v1
  code deleted in the same release window. No two-format support.
- **Not retroactive on archived plans' historical accuracy.** The
  migration is mechanical; if a v1 plan had ambiguous state, the v2
  output reflects what the parser could determine, not a re-derivation
  from history.

## The single invariant

> The plan file is canonical. Every other surface is a deterministic
> projection. `vk apply` is the only function authorized to mutate
> any non-canonical surface.

Three corollaries the rest of the design enforces:

1. **No agent decides whether state has changed.** State changes are
   *observed* (file diff, GH event, label diff) by the system, not
   *asserted* by an agent. Agents push commits, open PRs, tick
   checkboxes — they do not transition state.
2. **No two paths derive the same fact independently.** Anywhere a
   value can be computed from canonical state, it MUST be computed,
   not stored. Stored copies of derivable values are forbidden by
   construction (this is the entire content of Family A in the audit).
3. **No regex-scraping of free-form prose.** Structured data lives in
   YAML; markdown body is for human prose only and is never read by
   tooling.

## Architecture

### Plan-as-folder

```
docs/superpowers/plans/<YYYY-MM-DD>-<slug>/
├── _meta.yaml          # plan-level metadata (frozen post-dispatch)
├── _prose.md           # human-readable prose (frozen post-dispatch except via rework)
├── 01.yaml             # Phase 1: structure + state
├── 02.yaml             # Phase 2: structure + state
├── 03.yaml
└── ...
```

Filename convention: zero-padded two-digit phase number with `.yaml`
extension (`01.yaml`, not `phase-01.yaml` or `01-renderer.yaml`). Phase
title lives inside the YAML; filename is just an index. This avoids
the rename-on-title-change footgun and makes `ls` output sortable.

Plans nest under `docs/superpowers/plans/`. Archived plans move
wholesale to `docs/superpowers/archived-plans/<YYYY-MM-DD>-<slug>/`.
Symlinks are not used.

### `_meta.yaml` schema

```yaml
schema_version: 2
plan: <slug>                                  # matches folder slug
spec: docs/superpowers/specs/<file>.md        # path relative to repo root
target_repo: derio-net/<repo>                 # the plan's target repo — one repo per plan, no per-phase override
vk_version: ">=2.0.0,<3.0.0"                  # CLI version constraint
created: 2026-05-06                           # date the plan was first scaffolded

# For rework plans only (absent for normal plans):
parent_plan: docs/superpowers/archived-plans/<parent-slug>/   # what this rework descends from
prior_rework: docs/superpowers/archived-plans/<earlier-rework-slug>/  # optional, only if N > 1
origin_items:                                 # see "Rework plans" section below
  - id: 1
    item: <text>
    source: <text>
    track: development                        # one of: development | operations | decision
```

`target_repo` is plan-level and immutable. Per-phase target overrides
are NOT allowed by the schema — multi-target plans must be split into
one plan per target repo at the spec level (existing convention; v1's
`**Target repo:**` per-phase warning becomes structurally impossible
in v2).

Mutated by:
- `vk plan create` at scaffolding time.
- `vk plan rework` at rework scaffolding time (sets `parent_plan`,
  `prior_rework`, initial empty `origin_items`).
- `vk plan rework-add` (appends to `origin_items` only).
- Never otherwise mutated. Editing the structural fields requires
  `vk plan rework` (which creates a sibling plan rather than mutating
  an existing one).

### `_prose.md` schema

Free-form markdown. Contains:
- Plan title and brief
- Per-phase prose: title, goal, runbook commands (for manual phases),
  rationale, etc.

Generated at `vk plan create` time from the operator's brainstormed
spec. Mutated by:
- `vk plan create` at scaffolding (initial generation).
- `vk plan rework` (creates a *new* plan folder; the original prose is
  not mutated).
- Never directly edited by tooling after creation.

Tooling never reads `_prose.md`. It exists for humans.

### Per-phase YAML schema (`NN.yaml`)

```yaml
schema_version: 2

# IMMUTABLE post-dispatch (changes only via `vk plan rework`)
phase:
  number: 2
  title: Renderer
  tag: agentic                              # or "manual"
  depends_on: [1]                           # phase numbers within this plan
  tracking_issue: https://github.com/derio-net/superpowers-for-vk/issues/142
  # tracking_issue is null until `vk apply` dispatches the phase
  # NOTE: no target_repo here — it's plan-level only (in _meta.yaml)

tasks:
  - number: 1
    title: Define RenderedState dataclass
    steps:
      - id: P2.T1.S1
        text: Write pydantic model for RenderedState
      - id: P2.T1.S2
        text: Add render_issue projection function
  - number: 2
    title: Wire spec-index projection
    steps:
      - id: P2.T2.S1
        text: Replace spec_index.upsert_entry call sites

# MUTATED during execution (per-branch writes; lands on main via PR merge)
state:
  steps:
    P2.T1.S1:
      state: " "                            # one of: " ", "x", "-"
      ticked_at: null                       # ISO 8601, set when state != " "
      note: null                            # required when state == "-"
    P2.T1.S2:
      state: " "
      ticked_at: null
      note: null
    P2.T2.S1:
      state: " "
      ticked_at: null
      note: null
  completion:
    at: null                                # ISO 8601 when phase considered complete
    note: null                              # required for manual-tag phases
    observed_prs: []                        # PR URLs that contributed (informational)
```

The two halves are visually adjacent in one file but their *update
surfaces* are disjoint:
- The `phase`, `tasks` blocks are touched only by `vk plan create` and
  `vk plan rework`. No other code path is allowed to write them.
- The `state` block is touched only by `vk plan edit --tick` and
  `vk plan edit --complete-phase`, both of which write to whatever
  branch the operator is on. State changes ride to main via normal
  PR merges.

`step.id` format is `P<n>.T<n>.S<n>` (preserved from v1 for operator
muscle memory). Step IDs are immutable post-dispatch.

### The single invariant, restated as code

```python
# canonical state lives in the plan folder
plan: Plan = vk.parse(plan_dir)

# every other surface is a function of (plan, observed_world)
observed: GhState = vk.observe(plan, gh_client)
projected: RenderedState = vk.render(plan, observed)

# bring the world to match the projection
diff: Diff = vk.diff(projected, observed)
vk.apply(diff, gh_client)            # the only mutation path
```

`vk.parse` is a pure file read. `vk.observe` is read-only API queries.
`vk.render` is a pure function. `vk.apply` is the only place writes
happen. Drift detection is `vk.apply(..., dry_run=True)`.

## Library API (`vk` package)

The library is the source of truth. Bridge, CLI, GHA workflow all
import the same functions. Wire-protocol drift between contexts (audit
Family C) is impossible because there is no wire protocol — there is
one Python package.

### Parsing — `vk.parse`

```python
def parse(plan_dir: pathlib.Path) -> Plan: ...
```

- Loads `_meta.yaml` and all `[0-9][0-9].yaml` files via pydantic.
- Schema-validates everything. Invalid yaml → `vk.errors.PlanSchemaError`
  with structured details (file, field, expected vs actual).
- Returns immutable `Plan` dataclass:

```python
@dataclass(frozen=True)
class Plan:
    dir: Path
    meta: PlanMeta
    phases: tuple[Phase, ...]              # sorted by number
    prose_path: Path                        # for human reference; not parsed

@dataclass(frozen=True)
class Phase:
    number: int
    title: str
    tag: Literal["agentic", "manual"]
    depends_on: tuple[int, ...]
    tracking_issue: str | None
    tasks: tuple[Task, ...]
    state: PhaseState
    # No target_repo — plan-level (Plan.meta.target_repo) is the only one
```

- Refuses to load v1 plans. `PlanSchemaError("plan_dir is not a v2
  plan; run `vk migrate v1-to-v2` first")`.
- Refuses to load plans whose `_meta.vk_version` constraint isn't
  satisfied by the running library. Fail-loud.

### Observing — `vk.observe`

```python
def observe(plan: Plan, gh: GhClient) -> GhState: ...
```

- Read-only API queries. No mutations.
- For each phase with `tracking_issue`:
  - Issue current open/closed state
  - Issue current labels (full set)
  - Issue assignees
  - Linked PRs: search via GraphQL `closingIssuesReferences` plus
    title-pattern fallback (`[<repo>] <plan-slug> · Phase N/M ·`)
  - For each linked PR: open/closed/merged, draft state, CI conclusion
- Batches gh API calls (single GraphQL query for all phases of a plan
  when possible).
- Returns:

```python
@dataclass(frozen=True)
class GhState:
    phases: dict[int, PhaseObservation]    # keyed by phase.number

@dataclass(frozen=True)
class PhaseObservation:
    issue_state: Literal["OPEN", "CLOSED"] | None  # None = not yet dispatched
    issue_labels: frozenset[str]
    issue_assignees: tuple[str, ...]
    linked_prs: tuple[PrObservation, ...]
```

- Cross-repo: queries each repo independently (no cross-repo joins
  needed at this layer).

### Rendering — `vk.render`

```python
def render(plan: Plan, observed: GhState) -> RenderedState: ...
```

Pure function. No I/O. Same input → same output, every time.

```python
@dataclass(frozen=True)
class RenderedState:
    issue_per_phase: dict[int, RenderedIssue]
    archive_decision: bool                  # True iff plan is complete

@dataclass(frozen=True)
class RenderedIssue:
    body: str                               # static template (see §"Issue body")
    labels: frozenset[str]                  # full desired label set
    state: Literal["OPEN", "CLOSED"]
```

Projection rules:

| Question | Rule |
|---|---|
| Issue body | Static template at dispatch time. Re-rendered identically thereafter. The body never carries state. |
| Lifecycle label (mutually exclusive) | • `manual` if `phase.tag == "manual"` AND not complete<br>• `vk-ready` if no assignee AND no open linked PR AND not complete<br>• `in-progress` if has assignee OR has open draft PR (and not pr-ready)<br>• `pr-ready` if has open non-draft linked PR<br>• (no lifecycle label) if Issue closed |
| Taxonomy labels | Always: `spec:<spec-slug>`, `plan:<plan-slug>`, `phase:<n>` |
| Issue open/closed | OPEN until phase complete; CLOSED when complete |
| Phase complete | `state.completion.at is not None`, OR all `state.steps[*].state in ("x", "-")` AND at least one observed PR is merged AND no open linked PR remains |
| Manual phase complete | `state.completion.at is not None` AND `state.completion.note is not None`. Steps may or may not be ticked (operator's call). |
| Plan complete | All phases complete |
| Archive decision | Plan complete AND all Issues observed CLOSED |

Drift cases the renderer surfaces (returned in a separate `Warnings`
field, not blocking apply):
- Steps all ticked but no observed PR merged → operator may have
  ticked prematurely
- Observed PR merged but steps unticked → agent forgot to tick
- Issue closed but plan says incomplete → manual close; flag for
  reconciliation

### Diffing and applying — `vk.diff` and `vk.apply`

```python
def diff(rendered: RenderedState, observed: GhState) -> Diff: ...
def apply(diff: Diff, gh: GhClient, *, dry_run: bool, yes: bool) -> ApplyResult: ...
```

`Diff` is a list of typed mutations:

```python
@dataclass(frozen=True)
class IssueLabelChange:
    repo: str
    issue_number: int
    add: frozenset[str]
    remove: frozenset[str]

@dataclass(frozen=True)
class IssueStateChange:
    repo: str
    issue_number: int
    new_state: Literal["OPEN", "CLOSED"]
    close_reason: str | None

@dataclass(frozen=True)
class IssueBodyChange:
    repo: str
    issue_number: int
    new_body: str

@dataclass(frozen=True)
class IssueCreate:
    repo: str
    title: str
    body: str
    labels: frozenset[str]
    phase_number: int                       # for back-linking after creation

@dataclass(frozen=True)
class RepoLabelEnsure:
    repo: str
    labels: frozenset[LabelDef]
```

Apply rules:
- Idempotent. Re-running with the same inputs is a no-op.
- Atomic per mutation. If one fails, others continue; failures are
  collected and surfaced.
- **Managed labels only.** The applier touches only labels in the
  managed set: `vk-ready`, `manual`, `in-progress`, `pr-ready`,
  `spec:*`, `plan:*`, `phase:*`. Operator-added labels (`bug`,
  `good-first-issue`, etc.) are never touched.
- `dry_run=True` returns a `Diff` with no execution.
- `yes=False` (default) confirms before destructive operations
  (closing Issues, deleting labels). `yes=True` skips confirmation.

### Plan editing — `vk.plan.*`

```python
def vk.plan.create(spec: Path, slug: str, target_repo: str,
                   phases: list[PhaseSpec]) -> Plan: ...
def vk.plan.tick(plan_dir: Path, step_id: str, *, state: str, note: str | None) -> None: ...
def vk.plan.complete_phase(plan_dir: Path, phase: int, note: str) -> None: ...
def vk.plan.rework_create(parent_plan_dir: Path) -> Plan: ...
def vk.plan.rework_add_origin(rework_dir: Path, item: str, source: str,
                              track: Literal["development", "operations", "decision"]) -> int: ...
def vk.plan.rework_list(repo_root: Path, *,
                        include_archived: bool = False) -> list[ReworkRecord]: ...
def vk.plan.self_review(plan: Plan) -> list[ReviewIssue]: ...
```

All editing functions:
- Write to per-phase yaml (or `_meta.yaml` for `rework_*` calls) on
  the *current branch* (feature branch during execution, main when
  operator is doing state-only edits).
- Stage the change (`git add`); do not commit. Caller decides commit
  cadence and message.
- Validate after writing (re-parse to confirm schema still passes).

`vk.plan.create` and `vk.plan.rework_create` additionally:
- **Append a row to the spec's `## Implementation Plans` table** for
  the new plan (one row, idempotent — re-running with an existing
  row is a no-op). The spec edit is staged in the same change so
  it lands in the same PR. This eliminates the v1 "scaffold then
  manually update the spec" two-step.
- Refuse if the spec doesn't exist or doesn't have an
  `## Implementation Plans` section.

`vk.plan.self_review` v2 lints:
- Schema validation already happened in `parse`; this surfaces softer
  issues (cyclic dependencies, undeclared `tracking_issue` on a
  phase that's been worked, missing `completion.note` for a manual
  phase whose steps are all ticked, etc.).
- The v1 multi-target-repo warning is removed — v2 schema makes
  multi-target plans structurally impossible.

`tick`:
- `state` must be one of `" "`, `"x"`, `"-"`
- `note` is required when `state == "-"`
- Sets `ticked_at` to current UTC ISO 8601 when state changes from `" "`
- Idempotent: ticking an already-ticked step is a no-op

`complete_phase`:
- Sets `completion.at` to current UTC ISO 8601
- Sets `completion.note` (required for manual phases, optional for
  agentic — agentic phases derive completion from observed PR state
  primarily)
- Refuses if any step has state `" "` AND phase is agentic (use
  observed-PR-merge as the trigger instead, or explicitly tick steps
  first)

### Spec status — `vk.spec.*`

```python
def vk.spec.parse(spec_path: Path) -> SpecMeta: ...
def vk.spec.compute_status(spec: SpecMeta, gh: GhClient) -> SpecStatus: ...
def vk.spec.render_status_md(status: SpecStatus) -> str: ...
```

`vk.spec.parse`:
- Reads the spec markdown
- Extracts the `## Implementation Plans` table (now without `Status` column)
- Returns:

```python
@dataclass(frozen=True)
class SpecMeta:
    path: Path
    title: str
    plans: tuple[PlanRef, ...]

@dataclass(frozen=True)
class PlanRef:
    name: str
    repo: str                               # "derio-net/<repo>" or "—" for cross-repo manual rows
    file: str                               # "docs/superpowers/plans/<slug>/" or "—"
    depends_on: str                         # free-form text from the table cell
```

`vk.spec.compute_status`:
- For each `PlanRef`:
  - Resolve plan folder (local fs if same repo, else `gh api .../contents`)
  - Walk phase yamls
  - Compute aggregate (steps ticked, phases complete, plan status)
- Returns:

```python
@dataclass(frozen=True)
class SpecStatus:
    spec: SpecMeta
    plans: tuple[PlanStatus, ...]
    aggregate: SpecAggregate
    warnings: tuple[str, ...]               # broken refs, unreachable repos, etc.

@dataclass(frozen=True)
class PlanStatus:
    plan_ref: PlanRef
    state: Literal["Not Started", "In Progress", "Complete", "Missing", "Unreachable"]
    phases_complete: int
    phases_total: int
    steps_ticked: int
    steps_total: int

@dataclass(frozen=True)
class SpecAggregate:
    plans_complete: int
    plans_total: int
    steps_ticked: int
    steps_total: int
    percent_complete: float
```

`vk.spec.render_status_md` formats the result as the markdown comment
shown in the GitHub Action output (see §"GitHub Action").

### Bridge integration — `vk.bridge.*`

Used only by `willikins/scripts/vk-issue-bridge.py`. Not part of the
operator-facing CLI.

```python
def vk.bridge.discover_plans(repo: str, gh: GhClient) -> list[Plan]: ...
def vk.bridge.tick(plan: Plan, gh: GhClient, vk_mcp: VkMcpClient) -> TickResult: ...
```

`tick` is the one-cron-iteration function: observe, render, diff,
apply (GH-side only — never touches the consumer repo), update VK
board cards from the rendered state. Returns counts for logging.

The bridge does NOT have its own parser. It does NOT have its own
renderer. It calls into `vk.parse`, `vk.render`, etc. like any other
caller.

## CLI surface

### v2.0.0 commands

```
vk apply <plan-dir> [--dry-run] [--yes]
  Render + observe + diff + apply for one plan.
  Default: prompt before destructive ops.

vk apply --all [--dry-run] [--yes]
  Walk docs/superpowers/plans/ in current repo, apply each.

vk plan create [--from-spec <spec-path>] [--slug <slug>] [--target-repo <owner/repo>]
  Scaffold new plan folder from spec. Prompts for phase structure.
  Atomically appends row to spec's Implementation Plans table.

vk plan edit <plan-dir> --tick <step-id> [--state x|-] [--note <text>]
vk plan edit <plan-dir> --complete-phase <n> [--note <text>]
  Mutate state on current branch. Stages, doesn't commit.

vk plan rework <parent-plan-dir>
  Scaffold a sibling rework folder (parent stays Complete and untouched).
  Atomically appends row to spec's Implementation Plans table.
  Convention preserved from v1; mechanics simplified (YAML, not markdown surgery).

vk plan rework-add <rework-dir> --item <text> --source <text> --track development|operations|decision
  Append a row to the rework plan's _meta.origin_items list.

vk plan rework-list [--include-archived]
  List rework plans in repo, with derived status from phase yamls.

vk plan self-review <plan-dir>
  Schema validation + soft lints (cycles, missing manual-phase completion notes, etc.)

vk pickup <plan-dir> --phase <n>
  Output phase scope (markdown) for an agent. No state mutation.
  Returns: phase title, all step text, PR title template, dependency reminder.

vk spec status <spec-path>
  Compute and print spec status.

vk spec status --all
  All specs in current repo's docs/superpowers/specs/

vk migrate v1-to-v2 [--dry-run] [--yes]
  One-shot mechanical conversion of every v1 plan in the repo.
  Writes new folders, removes Status column from spec tables.
  Converts v1 *-rework-*.md sibling files to <slug>-rework-N/ folders
  with Origin tables migrated to _meta.origin_items.
  Survives as a CLI tool for future use (rare, but possible).
```

### Commands deleted in v2.0.0

| v1 command | v2 replacement |
|---|---|
| `vk progress sync` | `vk apply` (covers everything sync did and more) |
| `vk progress audit` | `vk apply --dry-run` |
| `vk progress transition` | `vk plan edit` for state changes; nothing else needed |
| `vk progress board` | `vk spec status --all` (boards are spec-rooted, not plan-rooted) |
| `vk progress create` | `vk plan create` |
| `vk dispatch create` | `vk apply` (first apply on an undispatched plan dispatches it) |
| `vk dispatch migrate` | `vk apply` (idempotent — converges to the rendered state) |
| `vk admin labels-sync` | `vk apply` (managed labels are part of the projection) |
| `vk execute claim` | Deleted — no claim verb. Picking up an Issue is `gh issue edit --add-assignee @me` (or the bridge does it at workspace spawn). |
| `vk execute pr-opened` | Deleted — PR open is observed by the next `vk apply` tick. |
| `vk execute pr-body` | `vk pickup` outputs the PR title template; agent constructs body. `Closes #N` is included by the template. |
| `vk execute check-step` | `vk plan edit --tick` |
| `vk execute check-deps` | `vk pickup` includes a depends-on satisfaction check; standalone command unnecessary. |
| `vk execute scope` | `vk pickup` |
| `vk issue create` | Retired. Bridge-routable Issue authoring becomes a separate concern; if needed, a v2.x feature, not v2.0. |
| `vk issue convert` | Same as above. |
| `vk plan convert` | Deleted (v1 ↔ v2 migration is `vk migrate v1-to-v2` only). |
| `vk plan spec-index` | Deleted — folded into `vk plan create` / `vk plan rework` (atomic spec-row writes at scaffold time). |

### Skill surface

Skills (`vk-plan`, `vk-execute`, `vk-dispatch`, `vk-progress`) keep
their names and high-level intent but their internal CLI calls are
rewritten:
- `vk-plan` calls `vk plan create`, `vk plan rework`, `vk plan self-review`
- `vk-execute` calls `vk pickup`, `vk plan edit`
- `vk-dispatch` calls `vk apply`
- `vk-progress` calls `vk apply --dry-run`, `vk spec status`

`vk-issue` skill (recently shipped) is retired in v2.0 alongside its
commands.

## Bridge contract

The bridge in `willikins/scripts/vk-issue-bridge.py` becomes a thin
wrapper:

```python
# bridge cron tick (every 2 minutes, per consumer repo)
import vk

for repo in CONSUMER_REPOS:
    plans = vk.bridge.discover_plans(repo, gh_client)
    for plan in plans:
        result = vk.bridge.tick(plan, gh_client, vk_mcp_client)
        log.info("tick", repo=repo, plan=plan.meta.plan, **result.counts)
```

Properties:
- Bridge **never writes to any consumer repo**. All bridge mutations
  are GH-side (Issues, labels) or VK-side (cards, workspaces).
- Bridge has its own pod-local sqlite for cron state (last tick
  timestamp, dedup window). This is the only state outside the
  canonical plan files.
- Bridge installs `vk` at `--user` scope in the pod. Same package, same
  version constraints, as the operator's laptop install.
- The two contexts (pod + laptop) share library version via the
  `_meta.vk_version` constraint in each plan. If pod has `vk==2.1.0`
  and a plan declares `vk_version: ">=2.0.0,<2.1.0"`, the bridge
  refuses to operate on that plan and logs a clear "version drift"
  warning.

## Rework plans

Plans frequently spawn follow-up work after the parent PR merges and
the parent is archived: code-review punch-list items, demo
smoke-test findings, decisions deferred during execution. The v1
convention — sibling plan with an `## Origin` table, parent stays
Complete and is NEVER reopened — is preserved. The implementation
collapses to YAML.

### Folder layout

```
docs/superpowers/archived-plans/2026-04-08-kid-laptops-7-vscode-dev-env/   # parent (archived)
docs/superpowers/plans/2026-04-08-kid-laptops-7-vscode-dev-env-rework-1/   # sibling rework
docs/superpowers/plans/2026-04-08-kid-laptops-7-vscode-dev-env-rework-2/   # second rework
```

The folder slug is `<parent-date>-<parent-slug>-rework-<N>/`. N is
auto-incremented by scanning *both* `plans/` and `archived-plans/`
(refuses with a clear diagnostic if the same N exists in both — same
collision rule as v1).

### Rework-only `_meta.yaml` fields

Rework plans have everything a normal plan has, plus:

```yaml
parent_plan: docs/superpowers/archived-plans/2026-04-08-kid-laptops-7-vscode-dev-env/
prior_rework: docs/superpowers/archived-plans/2026-04-08-kid-laptops-7-vscode-dev-env-rework-0/  # optional, only if N > 1
origin_items:
  - id: 1
    item: "Parental controls demo: VS Code can launch unrestricted shell"
    source: "PR #51 review by @ioannis"
    track: development          # one of: development | operations | decision
  - id: 2
    item: "Update operator runbook for the new lockfile path"
    source: "post-demo smoke test"
    track: operations
  - id: 3
    item: "Decide whether vscode dev container gets the same hardening"
    source: "demo discussion 2026-04-09"
    track: decision
```

`origin_items` ids are auto-incremented at insertion time and are
immutable thereafter (operator-visible references in commit messages
and discussion).

### What scaffolding does atomically (single-PR contract)

`vk plan rework <parent-plan-dir>`:

1. Validates `parent_plan_dir` exists and lives under `plans/` or
   `archived-plans/`.
2. Computes next N (cross-directory collision check).
3. Creates the rework folder with:
   - `_meta.yaml`: standard fields (slug, spec, target_repo,
     vk_version, created) + `parent_plan`, `prior_rework` (if
     applicable), `origin_items: []`.
   - `_prose.md`: short stub with the rework's title and a pointer
     to the parent's prose.
   - No phase yamls. (Operator authors phases later — the rework
     items in `origin_items` inform the phase structure but don't
     dictate it.)
4. **Appends a row to the spec's `## Implementation Plans` table**
   (Plan column gets the rework slug, Repo column gets
   `_meta.target_repo`, File column gets the new folder path,
   Depends on column gets the parent plan slug). Idempotent —
   re-running on an existing rework folder is a no-op for the spec
   edit.

All file writes are staged but not committed; operator commits and
opens a single PR. Reviewers see: new folder, spec row, in one
diff.

### Spec-doc updates

`vk plan rework` and `vk plan create` both update the spec — this
collapses the v1 two-step "scaffold then `vk plan spec-index`" flow
into one atomic operation. The spec row update follows the spec
table's static schema (Plan / Repo / File / Depends on; no Status
column).

If you author a new plan or rework outside of the `vk plan create` /
`vk plan rework` commands (e.g., by manually copying a folder), the
spec row will be missing. `vk plan self-review` flags this so it
surfaces at review time.

### Library API

```python
def vk.plan.rework_create(parent_plan_dir: Path) -> Plan:
    """Scaffold a rework folder + append spec row. Returns the new Plan.
    Stages all file writes; does not commit."""

def vk.plan.rework_add_origin(
    rework_dir: Path,
    item: str,
    source: str,
    track: Literal["development", "operations", "decision"],
) -> int:
    """Append to _meta.origin_items. Returns assigned id."""

def vk.plan.rework_list(
    repo_root: Path,
    *,
    include_archived: bool = False,
) -> list[ReworkRecord]:
    """Glob plan folders, filter where _meta.parent_plan is set.
    Status derived from phase yamls (same code path as everything else)."""

@dataclass(frozen=True)
class ReworkRecord:
    parent_slug: str
    rework_number: int
    status: Literal["Not Started", "In Progress", "Complete"]
    open_steps: int
    origin_item_count: int
    by_track: dict[str, int]   # {"development": 2, "operations": 1, ...}
    folder_path: Path
    spec_path: Path | None
```

### LOC reduction

`src/vk/plan/rework.py` shrinks from ~450 lines to an estimated ~80
lines. The deletions:

- ~80 LOC of markdown table editing (pipe escaping, byte-offset
  surgery, blank-line skipping, header validation) — replaced by
  `yaml.safe_load → list.append → yaml.safe_dump`.
- ~60 LOC of regex-based plan parsing for status / spec extraction
  — replaced by the standard `vk.parse` flow.
- The `_SCAFFOLD_TEMPLATE` markdown blob — replaced by a small
  pydantic model and `yaml.safe_dump`.

What stays:
- `next_rework_number` (cross-directory N-collision logic) — same
  shape, different filename glob.
- The cross-directory collision diagnostic message.
- The `prior_rework` lookup helper.

## GitHub Action

A reusable workflow lives in this repo at
`.github/workflows/vk-spec-status.yml` (and is referenced from each
consumer repo's own `.github/workflows/vk-spec-status.yml` via
`uses:`).

Triggers: PR merged to `main`.

Steps:
1. Detect plan folders touched in the merged PR (`git diff` against
   the merge-base).
2. For each touched plan: find which specs reference it (grep across
   `docs/superpowers/specs/*.md` for the plan's relative path).
3. For each affected spec: `vk spec status <spec>`, format as markdown.
4. Post a comment on the merged PR with the rendered status block.

Cross-repo plan references work via a PAT or GitHub App token with
read access to all consumer repos. The `vk spec status` command
handles cross-repo reads via the `gh api` contents endpoint.

Sample comment output:

```markdown
**Spec progress** — `docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md`

This PR completed **Phase 2** of `plan-rebuild-renderer`.

| Plan | Repo | Status |
|---|---|---|
| plan-rebuild-grammar | derio-net/superpowers-for-vk | ✅ Complete (4/4 phases, 12/12 steps) |
| plan-rebuild-renderer | derio-net/superpowers-for-vk | 🟡 In Progress (2/3 phases, 8/12 steps) |
| plan-rebuild-bridge-rewire | derio-net/willikins | ⚪ Not Started (0/2 phases) |

**Spec aggregate:** 1/3 plans complete (45% of total steps).

**Drift warnings:** none.
```

The GHA is optional. Operators who prefer to run `vk spec status`
manually can skip installing it. Default recommendation: install it.

## Migration

### Mechanical sweep

The migration is a single command per consumer repo:

```
vk migrate v1-to-v2 [--dry-run] [--yes]
```

For each `.md` plan in `docs/superpowers/plans/` and
`docs/superpowers/archived-plans/`:
1. Parse via the (about-to-be-deleted) v1 parser.
2. Extract: plan slug, spec ref, target_repo (plan-level — if v1
   plan had per-phase target_repo overrides that disagree, FAIL
   LOUD with a clear message; operator must split the plan
   manually before re-running the migration), and per-phase data
   (number, title, tag, depends_on, tracking_issue, tasks, steps,
   current checkbox state).
3. Write `<slug>/_meta.yaml`.
4. Write `<slug>/_prose.md` — synthesized from phase titles, task
   titles, and step text. The prose is regenerated, not preserved
   literally; the YAML is the truth.
5. Write `<slug>/01.yaml` ... `<slug>/0N.yaml` with `state.steps`
   populated from current checkbox state. `tracking_issue` preserved
   if the plan had a `<!-- Tracking: URL -->` comment. No `target_repo`
   field on phases (plan-level only).
6. **For rework plans** (filename matches `*-rework-*.md`):
   - Detect parent plan from the `**Parent plan:** ...` header line.
   - Detect prior rework from `**Prior rework:** ...` if present.
   - Parse the `## Origin` table; convert each row to an
     `origin_items` entry in `_meta.yaml`.
   - Set `_meta.parent_plan` and (optionally) `_meta.prior_rework`.
7. `git mv` the original `.md` to `.v1-archive` (keeps git history;
   doesn't pollute v2 listings).

For each spec file:
1. Locate `## Implementation Plans` section.
2. Drop the `Status` column from the table header and every row.
3. Update `File` cells to point to plan folders instead of `.md` files.

The migration opens **one PR per consumer repo** with all changes.
Operator reviews, merges. No special bot needed.

### v1 code retirement

Same release window (likely the migration PR or an immediate follow-up):

| File / module | Action |
|---|---|
| `src/vk/plan/parser.py` | Replaced with `src/vk/parse.py` (pydantic loader) |
| `src/vk/plan/models.py` | Replaced with `src/vk/types.py` (new dataclasses) |
| `src/vk/plan/format.py` | Deleted (no flat/phased distinction in v2) |
| `src/vk/plan/writer.py` | Replaced with `src/vk/plan/edit.py` (write functions) |
| `src/vk/plan/convert.py` | Deleted |
| `src/vk/plan/validate.py` | Replaced with pydantic validation in parse |
| `src/vk/plan/rework.py` | Replaced — ~450 LOC → ~80 LOC (markdown table editing → YAML) |
| `src/vk/plan/filename.py` | Updated for folder-based slugs |
| `src/vk/spec_index.py` | Replaced with `src/vk/spec.py` (compute_status only — no upsert, no reconcile) |
| `src/vk/labels.py` | Mostly preserved — registry stays |
| `src/vk/gh.py` | Mostly preserved — wrapper stays |
| `src/vk/commands/progress_cmd.py` | Deleted |
| `src/vk/commands/dispatch_cmd.py` | Replaced with `src/vk/commands/apply_cmd.py` |
| `src/vk/commands/admin_cmd.py` | Deleted |
| `src/vk/commands/execute_cmd.py` | Reduced to `pickup` only |
| `src/vk/commands/issue_cmd.py` | Deleted |
| `src/vk/commands/plan_cmd.py` | Updated for v2 commands |
| `src/vk/commands/dispatch_body_validator.py` | Deleted (v2 bodies are templated; no validator needed) |
| `tests/unit/test_plan_parser.py` | Replaced with `test_parse.py` (much shorter) |
| `tests/unit/test_dispatch_*` | Replaced with `test_apply.py` |
| `tests/unit/test_progress_*` | Deleted |
| `tests/unit/test_admin_*` | Deleted |

Estimated final LOC: ~800 source + ~2,000 tests (down from ~2,000
source + ~8,000 tests).

### Migration order across repos

Phase A — `superpowers-for-vk`:
1. Implement v2 library and CLI (Plan 1)
2. Run `vk migrate v1-to-v2` on this repo's own plans (operator action,
   one PR)
3. Delete v1 code (in the same PR or follow-up)
4. Tag and release v2.0.0

Phase B — `willikins`:
5. Update `vk-issue-bridge.py` to import `vk` v2 (Plan 2)
6. Deploy updated bridge image to pod
7. Confirm cron loop healthy

Phase C — Each consumer repo (frank, kid-laptops, agent-images, etc.):
8. Operator runs `vk migrate v1-to-v2` (Plan 3a, 3b, ...)
9. PR per consumer, reviewed and merged
10. Install `.github/workflows/vk-spec-status.yml`

## Testing strategy

### Unit tests

- `test_parse.py`: every YAML schema variant — valid plans, invalid
  field types, missing required fields, version mismatches, missing
  files in folder. Pydantic gives most of this for free.
- `test_render.py`: pure function. Table-driven: `(plan, observed) →
  expected_rendered`. Cover every projection rule from the table
  in §"Rendering."
- `test_diff.py`: pure function. `(rendered, observed) → expected_diff`.
  Cover idempotency (re-diff after apply produces no-op).
- `test_apply.py`: with mocked `GhClient`, assert correct mutations
  emitted for each diff type. Cover dry-run mode (no mutations).
- `test_plan_edit.py`: tick, complete_phase, validation after write.
- `test_spec_status.py`: aggregation across plans, broken refs,
  unreachable repos, percent calculation correctness.
- `test_bridge.py`: with mocked `GhClient` and `VkMcpClient`, assert
  correct GH and VK mutations per tick scenario.

### Integration tests

- `test_apply_e2e.py`: fixture repo with a plan folder; full
  dispatch → tick → apply → archive cycle, asserting on real file
  contents and mocked GH state at each step.
- `test_migrate_e2e.py`: fixture repo with v1 plans of every known
  format (flat, phased, with rework, with multi-target-warning,
  with tracking comments, with various step states); migration
  produces v2 plans that round-trip through `vk parse` and
  `vk apply --dry-run`.
- `test_cross_repo_spec.py`: spec referencing plans in two different
  repos; `vk spec status` correctly aggregates with mocked
  cross-repo reads.

### What's not tested

- The bridge's actual cron loop wiring (smoke test only — the
  business logic lives in `vk.bridge.tick` and is unit-tested there).
- Real GitHub API behavior (relies on mocks; one or two manual smoke
  tests on a throwaway repo before tagging v2.0.0).
- VK MCP server behavior (similarly mocked; existing
  `FakeVkMcpClient` from v1 carries over).

## Rollout

| Step | Repo | Owner | Blocker |
|---|---|---|---|
| 1 | superpowers-for-vk | implementation agent | spec approval |
| 2 | superpowers-for-vk (this repo's own plans migrated) | operator | step 1 |
| 3 | superpowers-for-vk (v2.0.0 tagged) | operator | step 2 |
| 4 | willikins (bridge migrated, deployed) | implementation agent | step 3 |
| 5 | First consumer repo (suggest kid-laptops — small, fast feedback) | operator | step 4 |
| 6 | Remaining consumer repos | operator | step 5 (proves the process works) |

Total estimated calendar time: 2–3 weeks of focused work for steps 1
and 4; steps 2, 5, 6 are operator-driven and can be batched.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| v2 library, CLI, retire v1 (steps 1–3) | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-05-06-vk-v2-library/` | — |
| Bridge migration (step 4) | `derio-net/willikins` | `docs/superpowers/plans/2026-05-06-vk-v2-bridge-migration/` | superpowers-for-vk plan |
| Consumer repo migration sweep (steps 5–6) | (operator action across `derio-net/*`) | — | superpowers-for-vk plan |

## Open considerations (non-blocking for spec)

- **Optimistic concurrency for state mutations:** ship without it; add
  ETag-based concurrency only if real lost-update bugs appear.
- **Bridge-spawned PR linkage:** when the bridge spawns an agent for
  Phase N, the agent eventually opens a PR. The PR title convention
  `[<repo>] <plan-slug> · Phase N/M · <subject>` is what the observer
  uses to link the PR back to the phase. Existing convention; preserved.
- **Operator override path:** operator can manually edit a phase yaml's
  `state.completion.at` directly to force a phase complete (e.g., for
  "we shipped this without a real PR" cases). Since plan-yaml edits go
  through PRs, this is reviewable.
- **Plan folder rename:** discouraged. If absolutely necessary,
  `vk migrate rename <old-slug> <new-slug>` should be added in v2.x
  (handles spec-table updates and tracking-comment lookups). Out of
  scope for v2.0.
- **Multi-step PRs (one PR ticks several steps across phases):** rare
  in practice and works naturally — the PR diff touches multiple
  phase yamls, each reviewed in the same PR. The renderer doesn't
  care about PR-to-step mapping; it cares about the post-merge state
  on main.
