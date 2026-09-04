# Workflow shapes and WorkItem dispatch — design

Status: design
Origin: operator brainstorm (2026-08-14). Framed as four parts: (a1) split
fr-goal into composable parts as data so it can eventually be "just a
workflow"; (a2) extend dispatch for the fr-goal-shaped flow; (b) generalize the
VK bridge into a generic poller service; (c) extend that poller to Jira ticket
lifecycles. **a1 and a2 are specified here in full. b and c are not built** —
they appear only as named seams, because their requirements are what make a1/a2
correct rather than merely convenient.

## 1. Goal

Make the fr-goal pipeline **data**, so that:

- **many shapes exist** — TDD feature delivery (today's fr-goal), UX work,
  marketing research — selected by `fr-goal <shape>`, with no argument
  resolving to today's shape so every existing invocation keeps working;
- **the plugin ships shapes and consumer repos define their own**;
- **dispatch is orthogonal to shape** — any shape can run inline, on VK, or on
  cncd, at a granularity the shape declares rather than one dispatch hardcodes.

Four axes must end up independently selectable: **workflow shape × runner ×
issue tracker × SCM**. Two of those (runner, SCM) already are. This spec makes
the workflow axis exist and the tracker axis *possible*.

### Non-goals

- **The generic poller service (b).** §4.H names the `Source` seam and the
  daemon frame it would consume. Nothing is extracted in this spec.
- **A Jira adapter (c).** §4.G defines the `Tracker` protocol and its
  per-instance mapping config *because a1 needs a tracker-neutral state
  vocabulary to write steps against*. No Jira code ships.
- **Retiring VK.** The roadmap has VK eventually replaced by k8s-backed
  dispatch; the operator's decision is that VK stays live for now. VK must work
  identically after this change.
- **New operator gates.** Shapes may declare gates; the shipped fr-goal shape
  declares exactly the touchpoints it has today, no more.
- **Changing what fr-goal *does*.** This is a re-expression of the pipeline as
  data plus a dispatch generalization — not a redesign of the pipeline's steps.

## 2. Background — what exists today (verified, not assumed)

Read end-to-end before drafting, per the repo's Bridge audit rule:
`fr_dispatch` (`protocols.py`, `__init__.py`, `registry.py`, `lifecycle.py`),
`fr_vk` (`bridge_cli.py`, `runner.py`, `pr_state.py`), `fr_cncd/runner.py`,
plus `fr/labels.py`, `fr/states.py`, `fr/spec.py`, `fr/types.py`,
`fr/models.py`, `fr/journal/`.

**fr-goal is prose.** `plugins/super-fr/skills/fr-goal/SKILL.md` is a 9-step
pipeline at the 120-line skill cap. Three of its parts were already extracted
into data by the 2026-07-22 subagent-execution spec: durable run-state
(`fr journal`), a harness-neutral model hint (`PhaseHeader.tier` + `fr models`),
and a unit of execution (`fr-phase-executor`). **What remains prose is the
pipeline itself, and there is no run cursor** — journals are keyed by
spec/plan/debug, never by run, so a run cannot be resumed, audited mid-flight,
or handed to anything else.

**`fr_dispatch.tick` is already a workflow engine, at one fixed granularity.**
It runs observe → render → diff → apply → dispatch against a 7-method `Runner`
protocol. But `Runner.dispatch(plan, phase, repo, issue_number)` presumes a plan
*and* a tracking Issue already exist — while the first four fr-goal steps run
before either does.

**The queue state machine is the GitHub label vocabulary.** `labels.py:47`
documents `LabelDef.name` as "the GitHub label string" and pairs it with a hex
colour; states are `fr:ready`, `fr:blocked`, `fr:in-progress`, `fr:pr-ready`,
`fr:synced`, and predicates such as `is_queued(observed_labels)` consume label
sets. The projection chain's *output type* is Issue-shaped:
`RenderedIssue(body, labels: frozenset[LabelDef], state)` (`states.py:58`). So
GitHub-Issue-shape sits in the **middle** of the chain, not at its boundary —
unlike `Runner`, which was extractable because the VK-shaped call was already at
the edge.

**Multi-repo addressing already exists.** `spec.py` parses
`## Implementation Plans` into `PlanRef(plan, repo, file, …)`; `PlanMeta` carries
`target_repo` and `parent_plan`; `compute_status` already resolves cross-repo
plans through the gh contents API, memoized on `(repo, slug)`. Multi-repo
*observation* is built and in use. Only fan-out *dispatch* is new.

**Runner and SCM are genuinely orthogonal already.** Runners register through
the `fr.runners` entry-point group (`fr-vk`, `fr-cncd`); `hostclient` dispatches
GitHub/GitLab/Gitea behind one client interface, with PR-URL parsing generalized
across `/pull/`, `/pulls/`, and `/-/merge_requests/` by the 2026-07-09
multi-backend spec.

## 3. The axes, and how real each one is

| Axis | Status today | Where it lives |
|---|---|---|
| Workflow shape | **does not exist** | — (§4.A builds it) |
| Runner | real, working | `fr.runners` entry points, `Runner` protocol |
| Issue tracker | **fused to SCM** | `labels.py`, `render.py`, `states.py` |
| SCM | real, working | `hostclient` → gh / glab / tea |
| Substrate | real, working | `FR_ISOLATION_TARGET`: devcontainer / worktree / external |

The tracker axis is the expensive one and cannot be wholly deferred to (c) —
but the reason is a2, not a1. Step definitions (§4.A) never name an item state;
`needs`, `emits`, and `gate` are artifact- and operator-scoped. What forces the
extraction now is **`WorkItem` and the generalized `tick`** (§4.D): once items
exist at three granularities and may be tracked by something that is not a
GitHub Issue, "the state of an item" has to mean something a tracker adapter can
project. §4.C extracts that vocabulary; §4.D and §4.G consume it. No adapter
beyond the existing GitHub behavior is written.

## 4. Design

### A. Workflow manifests — the shape axis (a1)

A shape is a YAML manifest declaring **steps**, the **decomposition unit** its
work dispatches at, and the **capabilities** a runner must provide.

```yaml
workflow: fr-goal
schema: 1
description: TDD feature delivery, goal to reviewed PR.

unit: run                 # run | phase | spec  (§4.E)
requires: [git, tests, scm]

# No `isolate` step: isolation is a PRECONDITION that `fr run start`
# ensures, not a step the run performs on itself (§4.B).
steps:
  - id: brainstorm
    kind: agent
    skill: super-fr:fr-brainstorming
    gate: operator                    # the batched Q&A — the sole touchpoint
    emits: [spec, journal:spec]

  - id: spec-review
    kind: agent
    needs: [spec]
    emits: [journal:spec]

  - id: plan
    kind: agent
    skill: super-fr:fr-plan
    needs: [spec]
    emits: [plan, journal:plan]

  - id: plan-review
    kind: cli                          # deterministic: exit code is the verdict
    run: fr plan self-review {{ artifacts.plan }}

  - id: implement
    kind: agent
    agent: super-fr:fr-phase-executor
    needs: [spec, plan]
    for_each: phase                    # one dispatch per phase, depends_on order
    tier: from_phase                   # model resolved via `fr models`
    emits: [journal:plan]

  - id: review
    kind: agent
    skill: superpowers:requesting-code-review
    needs: [spec, plan]
    emits: [journal:plan]

  - id: deliver
    kind: agent                        # corrected in Phase 11 — see below
    skill: superpowers:verification-before-completion
    needs: [spec, plan]
    emits: [pr]
```

**Two corrections to this illustration, made in Phase 11** once the shipped
manifest had to actually run. First, `deliver` is `kind: agent`, not a `cli` step
running `fr run deliver` — no such subcommand exists (`fr run` is
`start`/`adopt`/`status`/`advance`/`resolve`/`check`), and composing a PR body from the
journal is judgment work, not a deterministic command. Second, an `agent` step
is completed by **`fr run resolve <run-id> --step <id> --state done|failed`**,
added in Phase 7: `advance` deliberately never executes an agent step, so
without `resolve` a run wedges permanently on `brainstorm`. Any reading of this
example that implies otherwise is the example being stale, not the code.

**Step kinds implement the hybrid execution model (operator decision).**

- `kind: cli` — deterministic, fr executes it directly. Exit code is the
  verdict; stdout is captured into run state. These are exactly the steps a
  poller can drive unattended.
- `kind: agent` — judgment work, dispatched to the harness (Claude Code Agent,
  OpenCode task, Hermes `delegate_task`). fr never executes an LLM call itself,
  which keeps the `no-claude-p-batch` rule structurally satisfied rather than
  merely obeyed.
- `gate: operator` — a pause. The step ends the turn and the run does not
  advance until the operator answers. Unanswered is a stop, never a default.

**Resolution order: repo > shipped**, mirroring `fr models`:

```
docs/superpowers/workflows/<name>.yaml     # repo override / repo-authored
plugins/super-fr/workflows/<name>.yaml     # shipped (in THIS repo)
```

**Where "shipped" resolves at runtime** (clarified in Phase 6 — the paths above
read as though both were repo-relative, which is true only inside this
monorepo). The full order, corrected in review r5-b5/r5-e14, is **four**
places:

1. `docs/superpowers/workflows/<name>.yaml` — the repo's own override, which
   wins wholesale;
2. `$FR_SHIPPED_WORKFLOWS_DIR/<name>.yaml` when that variable is set — the
   explicit escape, for tests and for any harness that is not Claude Code;
3. `<the installed `fr` wheel>/fr/workflows/<name>.yaml` — a byte-identical
   copy of `plugins/super-fr/workflows/`, shipped **inside the Python
   package**;
4. `~/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/
   workflows/<name>.yaml` — the Claude Code plugin clone, the same
   marketplace-clone convention `plan_validator_wrapper.py` and
   `isolation/local.py` already use.

**Step 3 was missing and its absence was a real gap.** Steps 1, 2 and 4 are
all absent by default on a host that is not running Claude Code: a hermes pod
gets hooks and a SOUL block from `fr hermes install`, not a marketplace clone;
an OpenCode consumer never has one; and `$FR_SHIPPED_WORKFLOWS_DIR` was
documented nowhere operator-facing. Verified on a clean `uv tool install` with
an empty `HOME`: `fr run start fr-goal` failed with "unknown workflow shape",
and `fr workflow check --all` printed "no workflow shapes found" **and exited
0** — so §8.0 step 3 below passed on a host where nothing was installed.

**Step 3 comes BEFORE step 4**, deliberately: the wheel copy ships with the
`fr` that will execute the shape, so the two cannot disagree, while the
marketplace clone is updated independently — an operator who upgrades `fr`
without re-running `install.sh` would otherwise keep resolving a *stale* shape,
silently, possibly at the wrong granularity. Anyone who really wants the clone
to win has step 2, which is explicit.

Because the step-4 default is a *path built from a marketplace name*, and this
repo has already survived one marketplace rename, it is covered by a test
rather than assumed: a wrong default degrades to "unknown workflow shape" for
every lookup. The step-3 copy is covered by a tripwire asserting it is
byte-identical to `plugins/super-fr/workflows/`.

`fr-goal` with no argument resolves `fr-goal`; `fr-goal ux-research` resolves
that name through the same order. A shipped shape can be overridden wholesale by
a repo file of the same name — no merge semantics, because partial-override of a
step graph is a class of subtle breakage nobody wants to debug.

#### A.1 How a dispatched plan selects its shape

Resolution above answers *"given a name, which manifest?"*. Dispatch needs the
prior question — *"given a plan on disk, which name?"* — and nothing answered it
until this section was added (Phase 12; the omission left §1's "dispatch is
orthogonal to shape" true of the machinery and false of every shipped caller).

`tick` already takes `workflow: WorkflowManifest`, and `fr apply --to` already
derives its reachability gate from `required_inputs(<manifest>)`. Both simply
defaulted to the built-in `FR_GOAL_PHASE_DISPATCH`, because a plan folder
carries no shape reference: `_meta.yaml` records `plan`, `spec`, `target_repo`,
`fr_version`, `created`, `parent_plan` — nothing naming a workflow. One missing
field made an axis that is otherwise fully plumbed unreachable.

**A plan names its shape in `_meta.yaml`:**

```yaml
workflow: fr-goal-phase-dispatch    # optional; omitted means exactly today
```

- **Optional, and absence means the current default.** An existing plan without
  the key resolves `FR_GOAL_PHASE_DISPATCH` and behaves identically — the
  back-compat that lets a live bridge keep ticking merged plans through the
  upgrade.
- **Resolved through `resolve_workflow`**, so a repo-authored shape beats a
  shipped one of the same name. A named shape that does not resolve is an
  **error**, never a silent fallback to the default: falling back would dispatch
  a plan at the wrong granularity while reporting success, which is the failure
  mode this design has produced most often.
- **`fr plan create --workflow <name>`** writes it; `fr plan self-review`
  validates that it resolves and passes `check_workflow`.
- **`fr_version` floor.** `PlanMeta` is `extra="forbid"`, so a plan carrying
  `workflow:` is unparseable by fr < 4.0.0 — a hard failure, not a warning. A
  plan that uses the key must floor at `>=4.0.0`; one that omits it stays
  loadable by older fr.

The shape's declared `unit` then decides granularity, `requires` feeds capability
negotiation (§4.F), and `needs` feeds reachability (§4.E) — all through
parameters that already exist. This section is the datum that connects them.

**Validation is code, not prose** (`fr workflow check`): schema-valid, step ids
unique, `needs` referencing only artifacts that some earlier step `emits` **or
that the shape's `unit` already implies exist**, no cycles, declared capabilities
drawn from the closed capability set, `unit` valid for the steps present. A CI
tripwire runs it over every shipped manifest.

**That "or" is load-bearing** (corrected in Phase 8 — without it this section
contradicted §4.E and no valid manifest could exist). The two rules interlock:
if every `needs` had to be emitted by an earlier step, then `needs − emits` — the
very set §4.E derives reachability from — would be empty for *every* valid
manifest, so the derived gate could never fire. A gate that passes everything is
invisible, which is strictly worse than no gate. It also rejected `unit: phase`
shapes outright, since their `needs: [spec, plan]` are inputs no step emits.

The implied inputs follow from §4.D's grammar nesting, not from taste:
`run → {}` (a run emits its own spec and plan), `spec → {spec}`,
`phase → {spec, plan}`. Removing that seed silently disarms the reachability
gate rather than breaking a test, so it is pinned by tests rather than left to
prose.

**Fan-out for `for_each: phase` is not `build_items`' job.** `build_items`
decomposes strictly by `unit`; per-phase iteration inside a `unit: run` shape is
the orchestrating step's concern, since those phases do not exist until the plan
step has run.

### B. Run state — the cursor (a1)

Git-tracked on the feature branch (operator decision), a sibling of `journals/`:

```
docs/superpowers/runs/<run-id>.yaml
```

```yaml
run: 2026-08-14-ticket-polling
workflow: fr-goal@1
branch: feat/ticket-polling
started: 2026-08-14T09:00:00Z
cursor: implement
steps:
  brainstorm:  {state: done, emitted: {spec: docs/superpowers/specs/2026-08-14-…-design.md}}
  spec-review: {state: done}
  plan:        {state: done, emitted: {plan: docs/superpowers/plans/2026-08-14-…}}
  plan-review: {state: done, exit: 0}
  implement:   {state: running, items: [".../phase/1": done, ".../phase/2": running]}
```

Rationale for git-tracked: it is reviewable in the PR, it survives machine loss,
and it archives with the plan — the same properties that made journals
git-tracked. The accepted cost is that a poller reading a `main` checkout cannot
see in-flight runs; §4.H addresses that where it belongs, in the Source seam.

**CLI:** `fr run start <workflow> --branch <b>`,
`fr run adopt <plan-dir>` (2026-08-30 §3.E — give existing work a cursor),
`fr run status <run-id>`,
`fr run advance <run-id>` (execute the cursor's step if `kind: cli`, else emit
the dispatch brief), `fr run resolve <run-id> --step <id> --state done|failed`
(record the outcome of an `agent` step), `fr run check <run-id>`.

**`resolve` is not optional** (added in Phase 7 — the original four-command list
was a dead end). `advance` deliberately does not execute `agent` steps, so
without a way to record their outcome an agent step marked `running` can never
reach `done`, and a run wedges permanently on its first one. For the shipped
fr-goal shape, where nearly every step is `kind: agent`, that is the *second*
step. The orchestrating harness calls `resolve` when a dispatched agent returns;
it may also record `emitted` artifacts, since an agent step is how a spec or
plan comes into existence.

**A run is born in its workspace.** `fr run start` ensures isolation *itself*
(`fr isolation up --branch <b>`) and writes the run file inside the resulting
worktree — it is not a step the run later performs on itself.

The alternative, which the first draft shipped and code review caught, does not
work: `fr run start` wrote the run file at `git rev-parse --show-toplevel`, and
an `isolate` **step** then created a linked worktree. From the worktree,
`advance` resolved a different toplevel and could not find its own run; from the
base clone, `cli` steps ran with `cwd` in the base clone, so `plan-review`'s
`fr plan self-review {{ artifacts.plan }}` looked for a plan that existed only in
the worktree. The first step moved the ground out from under the run.

Writing run state to the base clone also defeats §4.B's own rationale: a file
there is not on the feature branch and never reaches the PR that is supposed to
make the run reviewable.

Making isolation a precondition rather than a step matches this repo's existing
doctrine — fr-brainstorming §0 and fr-goal both treat isolation as a hard gate
that "precedes EVERYTHING", where "start with X" changes the first work item and
never the first action. Consequently the shipped `fr-goal` manifest carries no
`isolate` step, and `cli` steps run with `cwd` at the workspace root.

**Archival keys on the emitted plan, not on a name convention.** A run and its
plan do **not** share a slug: run ids are derived from the branch
(`<date>-<flattened-branch>`, so `feat/x` yields `<date>-feat-x`) while a plan
slug is authored independently. Matching them by name silently no-ops, which is
worse than failing. `archive.py` therefore locates the run whose recorded
`emitted.plan` points at the plan directory being archived — data the run file
already carries — and mirrors the journal's move into `implemented/runs/`.

The journal is unchanged and remains the *content* log (decisions, findings,
discoveries). Run state is the *control* log (which step, what it emitted). They
are deliberately separate: one is what happened, the other is where we are.

### C. Abstract transition set — prerequisite for D and G (a2)

Lift the queue vocabulary off GitHub labels into a closed enum:

```python
ItemState = Literal["queued", "blocked", "in_progress", "in_review", "done"]
```

The **projection onto GitHub** is `queued → fr:ready`,
`blocked → fr:blocked`, `in_progress → fr:in-progress`,
`in_review → fr:pr-ready`, `done → closed`.

**Where that projection lives, corrected against what shipped.** This
section originally said "`labels.py` becomes the GitHub projection of that
enum rather than its definition". It did not: `labels.py` is
**byte-unchanged** by this spec, and the dependency runs the other way —
the new `fr/item_state.py` holds `ItemState`, `ItemDecision` and
`project_github`, and *imports* `labels.py`'s `LabelDef`s to express the
mapping. That is the better arrangement and was deliberate: `labels.py`
stays the GitHub vocabulary (names and colours, a tracker's own business),
`item_state.py` is the neutral vocabulary plus the one projection function,
and a second tracker adds a second projection without touching either. A
`labels.py` that "became the projection" would have had to import the
neutral enum, pointing the dependency at the tracker-specific module.

`render.py` continues to emit `RenderedIssue` for the GitHub tracker; what
changes is that the *decision* of which state an item is in is computed in
tracker-neutral terms first (`render.phase_item_decision`), and projected
second (`render._lifecycle_label_for_decision`, which is the only caller of
`project_github`).

**`manual` is not an `ItemState` either** (found in Phase 1, not at design time —
this mapping originally omitted it). `labels.py:101` defines
`MANUAL = LabelDef("manual", …, "Human-only; not routable to an agent")`, and in
the projection it short-circuits *ahead of* the dependency check. It is a
routing **attribute** — can an agent take this at all — orthogonal to where the
item sits in its lifecycle; a manual item is still queued, then done. §4.F's
capability negotiation and §4.G's tracker mapping must therefore carry
routability as a separate item attribute rather than a sixth state.

**Routability travels WITH the state at the neutral seam** (added in the
phases 1–4 review; the seam originally returned a bare `ItemState` and dropped
the attribute). The decision type is:

```python
@dataclass(frozen=True)
class ItemDecision:
    state: ItemState
    routable: bool = True          # False == human-only (`manual`)

    @property
    def dispatchable(self) -> bool:  # the only question a dispatcher asks
        return self.routable and self.state == "queued"
```

`render.phase_item_decision(plan, observed, phase_number)` returns it, and the
GitHub `manual` label is the *projection* of `routable=False`
(`_lifecycle_label_for_decision` takes the decision and no `PhaseDoc`), not a
second read of `PhaseDoc.tag`. Splitting them is what let the projection stay
correct while the neutral answer was wrong: a second tracker gating on
`state == "queued"` would have routed human-only work to an agent runner. A
tracker adapter maps its own vocabulary onto `ItemDecision`, both fields.

`fr:synced` is deliberately **not** an `ItemState`. It is a dispatch bookkeeping
stamp — "handed to the runner" — that happens to be stored on the Issue because
there was previously nowhere else durable to put it. It stays a tracker-side
stamp (§6 records why moving it into run state is unsafe today), but it is typed
separately so a tracker that cannot express it is not thereby unusable.

### D. WorkItem — the dispatch cutover (a2)

`Runner` is generalized to a unit-agnostic item. **Hard cutover** (operator
decision): `Runner`, `tick`, `VkRunner`, `CncdRunner`, and the fr-vk bridge all
move in one PR; no compatibility shim, because both existing runners are small
(89 and 156 lines), both are fully faked in tests, and a shim's real risk is that
the old signature never dies.

```python
@dataclass(frozen=True)
class WorkItem:
    id: str                       # stable identity — see below
    unit: Literal["run", "phase", "spec"]
    workflow: str                 # shape name
    repo: str
    parent: str | None            # item id — hierarchy (§4.E)
    inputs: tuple[ArtifactRef, ...]
    payload: Mapping[str, Any]    # unit-specific; runners treat as opaque
    tracking: str | None          # tracker item URL; None before creation
```

**Stable identity replaces title-string dedup.** Today dedup is
`build_card_title(repo, issue_number)` — a card *title*, keyed on an Issue number
that exists only because granularity was hardcoded to one-Issue-per-phase. With
configurable units some items have no tracker artifact at creation time, so
identity must derive from the item's position in the graph:

```
run    <repo>/run/<run-id>                        unit: run
spec   <repo>/<spec-slug>                         unit: spec
plan   <repo>/<spec-slug>/<plan-slug>             (parent level only — not a unit)
phase  <repo>/<spec-slug>/<plan-slug>/phase/<n>   unit: phase
```

Deterministic, computable before any tracker call, and stable across ticks.

**A run item is keyed on the run id, not on a spec or plan slug** (corrected
during Phase 2 — the original grammar here implied `<repo>/<spec-slug>/…` for
every unit, which cannot work). A `unit: run` item is dispatched *before* its
spec and plan exist: §4.E makes both outputs of the run, not inputs to it. Its
only stable name at creation is the run id assigned by `fr run start` (§4.B), so
the form carries a literal `run/` marker. `item_id` must therefore reject a
spec slug of `"run"`, which would otherwise collide with the plan-level form —
both are `<owner>/<repo>` plus two segments.

The plan level is a **parent, not a dispatchable unit**: `parent_id` of a phase
returns it, and nothing ever dispatches at that granularity. `unit` has three
values; the grammar has four levels.

**Runner protocol v2** — 6 methods, down from 7 (`dedup_key` disappears because
identity now lives on the item):

```python
class Runner(Protocol):
    name: str
    capabilities: frozenset[str]              # new — §4.F
    def preflight(self, items: Sequence[WorkItem]) -> str | None: ...
    def refresh(self) -> None: ...
    def slot_budget(self) -> int: ...
    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]: ...  # item ids
    def can_dispatch(self, item: WorkItem) -> bool: ...  # replaces can_dispatch_repo
    def dispatch(self, item: WorkItem) -> None: ...
```

`existing_dispatches` takes the tick's `items` (corrected in the phases 1–4
review; it was originally specced no-arg). An adapter whose board stores
something other than item ids — VK stores card titles — has to invert board
state *against* the candidate items, and the no-arg form left it reading them
from an attribute `preflight(items)` had stashed. That made call ORDER
load-bearing while the protocol documented none, and its failure mode is
silent: an empty snapshot, hence a duplicate card and workspace per item.

`tick` keeps its entire failure doctrine unchanged — per-item accumulation, one
bad item never kills the loop, a raising `dispatch` leaves the synced stamp
unwritten so the next tick retries, `skip_issue_create=True` preserved (the
2026-05-18 incident). Only the vocabulary it iterates changes.

**Adapter migration is mechanical.** `VkRunner.dispatch` derives
`(repo, issue_number)` from `item.tracking` + `item.payload`;
`build_card_title` stays as VK's *presentation* of an item, no longer its
identity. `CncdRunner.build_ingest_payload` already serialises a plan folder —
it gains the item envelope and keeps its server-side idempotence.

### E. Decomposition units (a2)

The unit a shape declares determines what gets an item:

| unit | items created | branches / PRs | parallel? |
|---|---|---|---|
| `run` | 1 per workflow run | 1 branch, 1 PR | n/a — single item |
| `phase` | 1 per plan phase | 1 each | yes, via `depends_on` |
| `spec` | 1 per target repo | 1 each per repo | yes, across repos |

Two consequences, both of which *remove* design surface:

**Concurrency is not a knob.** It is a consequence of the item graph —
`depends_on` already defines the DAG and dispatch already runs what is ready.
`unit: run` is serial because there is one item, not because a setting said so.
No parallelism configuration is added.

**Units compose recursively.** A `spec`-unit dispatch creates a per-repo item
that is itself decomposed by that repo's own shape — into a run, or into phases.
This is why `WorkItem.parent` exists, and why `PlanMeta.parent_plan` (already
present) is its seed.

**The reachability gate generalizes and stops being a special case.**
`fr apply --yes` currently refuses to dispatch unless plan and spec are merged to
`origin/HEAD`, because the runner works from its own checkout of main — which is
precisely why fr-goal runs inline today. Under this design the rule is derived
from data: **a step's `needs` are inputs and must be reachable; its `emits` are
outputs and need not be.** For `unit: run` the spec and plan are outputs, so the
gate correctly does not apply. For `unit: phase` it does. For `unit: spec` the
spec must be reachable in its own repo — the same cross-repo read path
`compute_status` already uses. One derived rule replaces a hardcoded refusal.

### F. Capability negotiation — what keeps four axes honest

Four axes multiply, and the failure that matters is not test-matrix size: it is a
run that dispatches cleanly and then dies mid-flight because the shape needed
something the runner cannot give — a UX shape needing a browser on a headless
pod, a research shape needing web egress and no git checkout at all.

A manifest declares `requires`; a runner declares `capabilities`; **`preflight`
refuses the mismatch before anything is dispatched**, using the method that
already exists for exactly this purpose and already fails every eligible item
cleanly with one error string. Capability names are a closed set
(`git`, `tests`, `scm`, `browser`, `network`, `devcontainer`) validated by
`fr workflow check`, so a typo is a validation error and not a silent
always-refuses.

Supported combinations are declared and fail-closed. The acceptance matrix gets
rows per *supported pair*, not per cell of a four-dimensional cube.

### G. Tracker — protocol defined, no adapter built (guides c)

Per-project Jira workflows rule out a per-tracker-*type* mapping: two Jira
projects on the same server may expose different transitions. The mapping is
therefore **per tracker instance**, resolved repo > user like `fr models`:

```yaml
# ~/.config/fr/trackers.yaml  (or docs/superpowers/trackers.yaml)
github:
  derio-net/super-fr:
    queued:      {label: "fr:ready"}
    in_progress: {label: "fr:in-progress"}
    in_review:   {label: "fr:pr-ready"}
    done:        {close: true}
jira:
  PROJ:
    queued:      {status: "To Do"}
    in_progress: {transition: "Start Progress"}
    in_review:   null            # unsupported by this project's workflow
    done:        {transition: "Resolve"}
```

```python
class TrackedItem(Protocol):        # NOT WorkItem — see below
    id: str
    tracking: str | None

class Tracker(Protocol):
    name: str
    def supports(self, state: ItemState) -> bool: ...
    def observe(self, items: Sequence[TrackedItem]) -> Mapping[str, ItemState]: ...
    def create_item(self, item: TrackedItem) -> str: ...
    def transition(self, item: TrackedItem, to: ItemState) -> None: ...
    def link_parent(self, child: TrackedItem, parent: TrackedItem) -> None: ...
```

**Why `TrackedItem` and not `WorkItem`** (corrected in Phase 10 — this block
originally said `WorkItem`, which cannot compile here). `Tracker` lives in `fr`,
`WorkItem` lives in `fr_dispatch`, and **`fr` never imports `fr_dispatch`** —
`tests/unit/test_import_direction.py` enforces that base/framework split with a
raw-text scan, so even a `TYPE_CHECKING`-only import trips it. The structural
Protocol gives the tracker exactly the two fields it needs and keeps the
dependency pointing one way. Do not "fix" this back to `WorkItem`.

**Mappings are partial by design.** A project with no "in review" status cannot
express `in_review`; that must be declarable, and a shape whose steps require the
state is refused at preflight — the same negotiation as §4.F, not a second
mechanism.

**Validation must eventually reach the live server, and today does not.** A Jira
admin can retire a transition without telling anyone, so a mapping validated only
against its own YAML is half a guard. What ships here is
`check_tracker_mapping_shape` — config-shape validation (unresolvable instance,
unknown state key), no CLI and no network. The `fr tracker check` command and
live-transition validation land **with the Jira adapter in (c)**, when there is a
server to ask. Stated plainly rather than implied, because a function named as
though it validated against a server while only reading YAML is precisely how a
gap becomes invisible.

**Hierarchy note.** Jira's Epic → Story → Sub-task maps onto spec → plan → phase
almost exactly; GitHub is the tracker that must *synthesize* hierarchy from links
or task lists. The protocol is therefore designed against the hierarchical case
and degraded for the flat one — designing it against GitHub alone would have
produced a flat model Jira could not use.

### H. Source — the seam the poller will consume (guides b)

`bridge_cli.py` is ~555 lines, of which the genuinely generic frame is: the
`flock` single-tick lock, bridge-owned checkout sync (`#286`), the per-repo
discovery loop, the per-plan error boundary (`I9`), metrics/heartbeat, and
JSON-persisted seen-state. VK-specific: MCP client construction, `project_id`,
the PR-state sweep, the workspace reaper, and Done-reconciliation.

The seam that makes (b) an extraction rather than a rewrite:

```python
class Source(Protocol):
    name: str
    def discover(self) -> Iterable[WorkItem]: ...
```

`discover_plans` becomes the first implementation (`PlansSource`); a Jira query
becomes another; a run-state watcher becomes a third — which is where the
in-flight-runs-not-on-main cost from §4.B gets paid, by a Source that watches
branches or is handed runs explicitly. **Nothing is extracted in this spec.**
The obligation it does create is a constraint: `tick` must not acquire any new
coupling to `discover_plans` specifically, so that the later extraction stays
mechanical.

## 5. Migration and compatibility

**Version: major → 4.0.0** (operator decision, from 3.19.0). `Runner` is a
published entry-point contract; even with a single known client, a signature
change to a documented extension point is what major exists for.

- `fr-goal` with no argument behaves exactly as today.
- Both shipped runners migrate in the same PR; `fr.runners` consumers outside
  this workspace would break, and the major bump is that announcement.
- Plans, specs, journals, and the acceptance matrix are untouched on disk.
- `docs/superpowers/runs/` is new; its absence is not an error (a plan or spec
  driven without a run is still valid).
- **A plan's `fr_version` constraint must span the bump.** This spec's own plan
  performs the 3.19.0 → 4.0.0 bump partway through, so phases after that point
  execute under 4.0.0. `fr plan create`'s default `>=3.0.0,<4.0.0` would trip
  the plan's own gate mid-run; the plan is authored `>=3.19.0,<5.0.0`. Any plan
  in flight across the bump needs the same widening.

## 6. Risks and mitigations

- **The cutover breaks the live bridge.** Highest-consequence risk: the VK
  bridge runs on a pod against real repos. Mitigation: adapters are faked in
  unit tests, plus a post-merge Test Plan (§8) that walks a real tick before the
  change is trusted.
- **`fr:synced` has nowhere better to live.** Moving the dispatch stamp into
  git-tracked run state would be cleaner, but a run file on a feature branch is
  invisible to a bridge reading `main`, and the bridge does not write to repos.
  Keeping the stamp on the tracker preserves crash semantics; §4.C types it
  separately so it does not contaminate `ItemState`.
- **Manifest schema churn.** Repo-authored shapes make the schema a public
  surface earlier than is comfortable. Mitigation: `schema: 1` is explicit in
  every manifest and `fr workflow check` rejects unknown versions, so a future
  migration is detectable rather than silently mis-parsed.
- **`render.py` is 22K and Issue-shaped.** §4.C changes where the state
  *decision* happens without rewriting the GitHub projection, deliberately
  keeping the blast radius off the largest module in the package.
- **Shapes that emit no PR.** A marketing-research shape has no code and no PR;
  the `deliver` step is shape-specific, so nothing in `tick` may assume a PR
  exists. Pinned by a test shape that emits only a document.

## 7. Testing and verification

- **Manifest**: schema round-trip; `fr workflow check` catches duplicate ids,
  dangling `needs`, cycles, unknown capabilities, unknown `schema:`; resolution
  order repo > shipped; unknown shape name errors cleanly; no argument resolves
  the default shape.
- **Run state**: start → advance → status → check round-trip; cursor advances
  only on step success; a `gate: operator` step halts and is resumable; archival
  moves `runs/<id>.yaml` to `implemented/runs/`.
- **Step kinds**: a `cli` step's exit code is the verdict and its stdout is
  captured; an `agent` step produces a dispatch brief and never executes an LLM
  call from `fr` (tripwire-adjacent to `test_tripwire_claude_p.py`).
- **ItemState extraction**: every current label state round-trips through the
  enum; `is_queued` and friends keep their present behavior; the GitHub
  projection is unchanged byte-for-byte for an unchanged plan.
- **WorkItem / Runner v2**: identity is deterministic and stable across ticks;
  `tick` failure doctrine preserved (per-item accumulation, retry on raising
  dispatch, no auto Issue creation); `VkRunner` and `CncdRunner` pass their
  existing suites against the new signature.
- **Units**: `run` yields one item; `phase` yields one per phase respecting
  `depends_on`; `spec` fans out one per target repo; recursion sets `parent`.
- **Reachability**: derived from `needs` — a `run`-unit shape dispatches with no
  spec on main; a `phase`-unit shape refuses when the plan is unmerged.
- **Capabilities**: a shape requiring `browser` is refused at preflight by a
  runner lacking it, with every eligible item failing cleanly on one message.
- **Tracker protocol**: mapping config resolves repo > user; a `null` state is
  reported unsupported by `supports()`; a shape needing an unsupported state is
  refused at preflight. (No Jira adapter — protocol-level tests only.)
- **Version**: `scripts/bump-version.py major` → 4.0.0 across every manifest,
  `uv.lock` committed with it.

## 8. Test Plan (post-merge, operator-driven)

Covers **every capability this spec ships**, not a sample. Ordered so the cheap
fail-fast checks run first: if §8.0 is red, nothing below it is meaningful.

**§8.0 is a smoke suite and should not stay manual.** Each step is a single
command with a binary verdict, deliberately written to be scriptable. Automating
it is tracked by the `smoke-suite-automated` row; until that lands, the operator
runs it. The other sections need a live bridge, a real VK board, or operator
judgement, and stay manual by nature.

### 8.0 Smoke — one command each, all must exit 0

1. `fr --version` → `4.0.0`.
2. `fr --help` lists `workflow`, `run`, `plan`, `apply`, `acceptance`, `journal`.
3. `fr workflow check --all` over the **installed** shipped manifests. It must
   report `fr-goal: ok` — and, when nothing is discoverable at all, **exit
   non-zero** rather than printing "no workflow shapes found" and exiting 0
   (review r5-b5: as written, this step passed against a host with no shapes
   installed, which is precisely the state it exists to detect). The shipped
   `fr-goal` is now inside the `fr` wheel (§4.A step 3), so a clean
   `uv tool install` with an empty `HOME` and no repo override satisfies this
   with no plugin installed at all.
4. `fr acceptance check` and `fr status` in a checkout.
5. `python -m fr_vk.bridge --dry-run` → banner, exit 0, no gh or MCP traffic.

Run these against a **clean `uv tool install`**, not a workspace venv. That
distinction is the point: the 4.0.0 CLI once failed to start from a clean install
because `click` — typer's transitive dependency, not one fr declares — was
imported directly, while the full local suite stayed green. A tripwire now blocks
that specific import; §8.0 is what catches the next member of the class.

### 8.1 Install and shipped files

6. Install on the bridge host; confirm `~/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows/fr-goal.yaml` exists — the shipped shape must reach the path `resolve_workflow` actually searches.
7. Confirm the OpenCode and Hermes skill mirrors regenerated in step 6 match the canonical `SKILL.md`.

### 8.2 Dispatch — the live bridge (a2)

8. One real tick: banner, per-repo discovery lines, and a `synced`/`errors`/`skipped` summary matching pre-cutover behaviour for an unchanged plan.
9. Phase-unit dispatch creates exactly one VK card per ready phase; a **second** tick creates none. Include at least one card created **before** the cutover, to exercise identity-based dedup against a card carrying no item id.
10. A plan whose `_meta.yaml` names an **unresolvable** shape fails *that plan only*: the tick logs it, `errors` increments, the next plan still ticks, and the daemon exits 0. A bad shape must never take the daemon down.
11. A plan whose shape requires a capability the runner lacks is refused before dispatch: `synced=0`, no card created, message naming the capability.
12. A plan with **no** `workflow:` key dispatches exactly as it did on 3.19.0 — the back-compat that lets the bridge keep ticking every plan in the wild.

### 8.3 Shapes and runs (a1)

13. `fr run start` with no shape argument resolves `fr-goal`; the run file appears **inside the isolation workspace** and on the feature branch — not in the base clone.
14. Walk the shipped shape past its operator gate: `advance` → `blocked`; `resolve` → gate cleared; `advance` → proceeds. This wedged permanently before review; it is the single most important step here.
15. An `agent` step prints a **valid JSON** brief carrying `for_each`, and it stays valid JSON in a narrow terminal (`COLUMNS=40`). `fr run resolve --emitted plan=<path>` records the artifact.
16. A `cli` step that exits non-zero leaves the cursor put and makes `fr run check` exit non-zero; re-running `advance` after the fix proceeds.
17. A repo-authored `docs/superpowers/workflows/fr-goal.yaml` overrides the shipped shape **wholesale**; removing it falls back to shipped.
18. `fr plan create --workflow <shape>` writes the key and floors `fr_version` at `>=4.0.0`; the same command with an explicit `--fr-version` admitting fr 3.x exits 2 rather than rewriting the operator's constraint. Without `--workflow`, `_meta.yaml` carries no `workflow` key at all.
19. `fr archive` moves the run file to `implemented/runs/`, matched by the run's recorded `emitted.plan` rather than by any name convention.
20. Drive one `fr-goal` run end-to-end and confirm the PR body's findings and decisions come from `fr journal render`, not from memory.

### 8.4 Deliberately not covered

`unit: spec` fan-out and `unit: run` dispatch have **no shipped caller** (see the
`dispatch-unit-declared-by-shape` and `multi-repo-spec-fanout` rows), so there is
nothing to exercise live. The `Tracker` protocol ships without a Jira adapter,
so only its config-shape validation is reachable. Stated here so a future reader
does not mistake absence of a step for absence of a risk.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-08-14-workflow-shapes-and-workitem-dispatch | `derio-net/super-fr` | `2026-08-14-workflow-shapes-and-workitem-dispatch` | — |

## References

- `plugins/super-fr/skills/fr-goal/SKILL.md` — the 9-step prose pipeline §4.A
  re-expresses as data.
- `docs/superpowers/implemented/specs/2026-07-22-fr-goal-subagent-execution-design.md`
  — journal, `tier`, and phase-executor extraction this spec builds on.
- `docs/superpowers/implemented/specs/2026-06-05-super-fr-split-design.md` — the
  `Runner` extraction whose shape §4.D generalizes.
- `docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md`
  — the SCM axis, already orthogonal.
- `docs/superpowers/implemented/specs/2026-05-17-dispatch-reachability-gate-design.md`
  — the hardcoded gate §4.E derives from `needs`.
- `packages/fr/src/fr/labels.py:47,95-110` — `LabelDef` as "the GitHub label
  string"; the state vocabulary §4.C lifts.
- `packages/fr/src/fr/states.py:58` — `RenderedIssue`, the Issue-shaped
  projection output.
- `packages/fr/src/fr/spec.py:34,140` + `packages/fr/src/fr/types.py:45-57` —
  `PlanRef`, `target_repo`, `parent_plan`: the multi-repo fan-out source.
- `packages/fr-dispatch/src/fr_dispatch/protocols.py`, `__init__.py` — `Runner`
  and `tick` as they stand before the cutover.
- `packages/fr-vk/src/fr_vk/bridge_cli.py` — the daemon frame §4.H would later
  extract.
- `~/.claude/rules/no-claude-p-batch.md` — why `kind: agent` dispatches to the
  harness instead of fr shelling out to an LLM.
