# Issue Label Lifecycle Fix, Color Registry, and Project-Board Excision

**Status:** Draft
**Date:** 2026-04-27
**Repos affected:** `derio-net/superpowers-for-vk`, all `derio-net/*` repos (operator-driven label sync)

## Goal

Close three related issues in dispatch / lifecycle plumbing:

**A. Make the 4-state kanban actually work.** The spec at
`docs/superpowers/specs/2026-04-14-archive-and-unified-descriptions-design.md:70-75`
defines the lifecycle as `vk-ready → in-progress → pr-ready → closed`. In
practice, only `vk-ready` is reliably set (by `vk dispatch create`). The
labels `in-progress` and `pr-ready` have **zero code-level producers** —
audit commit `e14348b` confirms `pr-ready`, and code review during this
spec confirms `in-progress` is the same: nothing in any repo applies it
as an Issue label. The `vk-execute` skill's post-`gh pr create` swap is
best-effort, so it silently skips when the labels don't exist on the
target repo. Real-world incident: agent in `derio-net/agent-images`
opened PR #14 against Issue #8; the swap failed; #8 was stuck on
`vk-ready` until the operator hand-fixed it.

**B. Stop creating ad-hoc label colors per-repo.** Today the same label can be
gray in one repo (`vk-ready` at `aaaaaa` in `agent-images`) and absent in another.
There is no canonical color or description for any of the lifecycle labels,
so the GitHub board view is visually inconsistent across repos.

**C. Excise the vestigial `project_board` config field and its dead-code
satellites.** The "Derio Ops" Project board is now used only for Frank-cluster
feature-level health, not for tracking superpowers-for-vk plan execution.
The original toolchain spec (`2026-04-12-vk-cli-toolchain-design.md:548-550`)
intended `vk` to manage board membership, lifecycle-field transitions, and
board-aware audits. Reality: only `vk progress audit`'s dispatch-mode block
ever made it past spec, and even that reads from a board this project no
longer tracks. Six `gh.py` helpers, the `vk dispatch --project` flag, the
`vk progress create --lifecycle` flag, the `vk progress transition` dispatch
branch (returns "not yet implemented"), and the entire
`_run_dispatch_audit` function are dead or near-dead. Remove them. ~250-350
lines deleted, one config field gone, one less concept in the mental model.

The fix moves both halves of the lifecycle into `vk execute` (one skill, one
code path, no harness coupling), centralises label colors and descriptions in
a label registry, ships a one-shot `vk admin labels-sync` to bring existing
repos into line, and deletes the project-board config surface.

## Non-goals

- **Changing the 4-state model.** The states stay
  `vk-ready → in-progress → pr-ready → closed`. This spec only fixes who
  applies them, when, and what they look like.
- **VK board sync** (the `update_issue` MCP call at vk-execute step 7).
  Unrelated; left as-is.
- **Backfilling stuck Issues.** Issues currently sitting on stale labels
  (e.g. `derio-net/agent-images#8` was, before the manual fix) are not
  retroactively transitioned by this work. `vk dispatch create` is idempotent
  on labels for new dispatches; existing in-flight Issues are operator-fixed
  if needed.
- **Replacing the `vk-synced` label or any of the bridge's concerns.** The
  bridge sets a Project-board "Lifecycle" *field* (single-select), not an
  Issue label — different surface entirely. See the "Lifecycle surfaces"
  section below. Nothing in this spec touches the bridge or any
  cross-repo code.
- **A recurring label-policing job.** `vk admin labels-sync` is a one-shot
  command run by an operator, not a cron-driven sweeper.

## Cross-cutting principle: fail loud on real failures, retry only on transient ones

The current "best-effort: failure does not block PR creation" comment in
`skills/vk-execute/SKILL.md:35` was load-bearing only because the labels
genuinely didn't exist on most repos — silent skip avoided derailing real
work. Once dispatch bootstraps every lifecycle label at create time, the
remaining failure modes are:

| Failure | Behavior |
|---|---|
| Network / 5xx / connection reset | Retry with backoff (1s, 2s, 4s; ≤3 attempts; total ≤7s). Hard-fail if all retries exhausted. |
| Auth / 401 / 403 / token-scope | Hard-fail immediately. No retry — these don't recover. |
| Repo / Issue 404 | Hard-fail immediately. |
| Already in target state | Success (idempotent), no API call. Print info-level note. |
| `gh` not found / not authenticated | Hard-fail with install/auth instructions. |

For `vk execute pr-opened` specifically (runs *after* `gh pr create`
succeeded), the hard-fail message must include the PR URL that was created
and the manual remediation command, so the operator can recover without
hunting for state.

No silent paths.

## Design

### 1. Label registry — single source of truth

New module: `src/vk/labels.py`. Defines every label `vk` knows about with its
canonical color and description.

```python
@dataclass(frozen=True)
class LabelDef:
    name: str           # the GitHub label string
    color: str          # 6-char hex, no leading #
    description: str    # human-readable, surfaces in the GitHub UI


# Lifecycle labels (mutually exclusive states an Issue can be in)
VK_READY    = LabelDef("vk-ready",    "0E8AE6", "Queued for an agent to pick up")
MANUAL      = LabelDef("manual",      "BFBFBF", "Human-only; not routable to an agent")
IN_PROGRESS = LabelDef("in-progress", "D93F0B", "An agent is actively working on this")
PR_READY    = LabelDef("pr-ready",    "0E8A16", "PR is open; awaiting review")

# Bridge-managed (set by vk-issue-bridge after VK board sync)
VK_SYNCED   = LabelDef("vk-synced",   "6A630D", "Synced to VK board")

# Templated labels — name is dynamic, color/description are canonical
SPEC_LABEL_COLOR  = "B60205"  # spec:<spec-slug>
PLAN_LABEL_COLOR  = "1D76DB"  # plan:<plan-name>
PHASE_LABEL_COLOR = "FBCA04"  # phase:<n>


def spec_label(spec_slug: str) -> LabelDef:
    return LabelDef(f"spec:{spec_slug}", SPEC_LABEL_COLOR, f"Part of spec {spec_slug}")


def plan_label(plan_name: str) -> LabelDef:
    return LabelDef(f"plan:{plan_name}", PLAN_LABEL_COLOR, f"Plan: {plan_name}")


def phase_label(n: int) -> LabelDef:
    return LabelDef(f"phase:{n}", PHASE_LABEL_COLOR, f"Plan phase {n}")
```

**Identifier hierarchy** (each Issue carries all three for dispatched work):

- `spec:<spec-slug>` — the design spec the work belongs to. Derived from the
  plan's `**Spec:**` field's filename (date prefix and `-design` suffix
  stripped). Lets `gh issue list --label spec:<x>` return every Issue across
  every plan rolling up under one spec.
- `plan:<plan-name>` — which plan within the spec. Derived from the plan
  filename's tail after stripping the spec slug and any `phase-N-` infix
  (e.g. `2026-04-27-label-lifecycle-fix-phase-3-labels-sync.md` →
  `labels-sync`). Falls back to `phase-N` when the filename has no
  descriptive tail (e.g. `…-phase-1.md` → `plan:phase-1`).
- `phase:<n>` — the *internal* phase number within the plan (unchanged from
  prior behavior).

Color logic — the lifecycle reads visually as a gradient when the operator
scans a board: blue (queued) → orange (active) → green (review) → closed.
Yellow stays for `phase:N` because it's an *attribute*, not a *state*.
`B60205` red stays for `spec:<spec-slug>` (the heaviest-weight identifier).
`1D76DB` blue distinguishes `plan:<plan-name>` from the lifecycle's lighter
queued-blue and from `phase:N` yellow.

**Backward compatibility:** plans without a `**Spec:**` field fall back to
the legacy single-label `plan:<full-slug>` scheme — preserves behavior for
spec-less plans without forcing every dispatched repo to migrate at once.

### 2. Configurability

Existing pattern: `DispatchConfig.labels` (in `src/vk/config.py:45-47`) is a
dict whose keys are role-names and whose values are the actual label strings.
Extend with two new keys, defaults from the registry:

```python
labels: dict[str, str] = field(
    default_factory=lambda: {
        "agentic":     "vk-ready",     # = labels.VK_READY.name
        "manual":      "manual",       # = labels.MANUAL.name
        "in_progress": "in-progress",  # NEW = labels.IN_PROGRESS.name
        "pr_ready":    "pr-ready",     # NEW = labels.PR_READY.name
    }
)
```

`_parse_dispatch` mirrors the same defaults so existing `plan-config.yaml`
files continue to work without edits. Operators who want different label
strings (e.g. for repos with conflicting label names) can override per-key
in their `plan-config.yaml`'s `dispatch.labels` map exactly as today.

The registry's `LabelDef.color` and `description` are **not** configurable.
Visual consistency across repos is the whole point of phase 4. Operators who
want a different scheme send a PR to `src/vk/labels.py`.

### 3. `vk dispatch create` bootstrap

`src/vk/commands/dispatch_cmd.py` builds `required_labels` from the
identifier hierarchy plus the lifecycle states:

```python
agentic_label     = dispatch_cfg.labels.get("agentic",     "vk-ready")
manual_label      = dispatch_cfg.labels.get("manual",      "manual")
in_progress_label = dispatch_cfg.labels.get("in_progress", "in-progress")
pr_ready_label    = dispatch_cfg.labels.get("pr_ready",    "pr-ready")

if plan.spec:
    spec_slug = derive_spec_slug(Path(plan.spec))
    plan_name = derive_plan_name(plan_path, spec_slug)
    spec_plan_labels = [f"spec:{spec_slug}", f"plan:{plan_name}"]
else:
    # Legacy: spec-less plans fall back to single-label scheme.
    spec_plan_labels = [f"plan:{derive_slug(plan_path)}"]

required_labels = sorted({
    agentic_label, manual_label, in_progress_label, pr_ready_label,
    *spec_plan_labels,
    *(f"phase:{p.number}" for p in plan.phases),
})
```

`gh.ensure_labels()` is upgraded to take colors and descriptions from the
registry (currently it accepts them as parameters but every callsite passes
the defaults). The dispatch bootstrap looks up each label string in a
`name_to_def` map built from the registry; for `spec:<spec-slug>`,
`plan:<plan-name>`, and `phase:<n>` it calls the templated helpers. Any
label that isn't in the registry (e.g. an operator-overridden custom label
string) keeps the existing default color behavior — no surprise breakage.

### 4. Two new `vk execute` subcommands

`src/vk/commands/execute_cmd.py` grows two state-transition commands. Both
take an Issue identifier and the target repo (default: profile's
`dispatch.default_repo`).

#### `vk execute claim`

```
vk execute claim --issue <N> [--repo <owner/repo>]
```

Called by the agent at the start of work, after `check-deps` passes.

Behavior:
1. Read current Issue labels via `gh issue view --json labels`.
2. If `in-progress` (or the configured equivalent) already present and
   `vk-ready` already absent → exit 0 with "already in-progress" note.
3. Otherwise: `gh.ensure_label()` for `in-progress` (self-heal if the repo
   wasn't bootstrapped via `vk dispatch`), then add `in-progress` and remove
   `vk-ready` in a single `gh issue edit` call.
4. On network error: retry with backoff. On auth/404/permissions: hard-fail
   with the recovery hint.

If the Issue currently has `manual` instead of `vk-ready`, treat that as a
configuration error — `manual` Issues are not agent-claimable. Hard-fail
with "Issue #N has the `manual` label; agents do not claim manual work."

#### `vk execute pr-opened`

```
vk execute pr-opened --issue <N> [--repo <owner/repo>] [--pr-url <url>]
```

Called immediately after `gh pr create` succeeds.

Behavior:
1. Read current Issue labels.
2. If `pr-ready` already present and `in-progress` already absent → exit 0
   with "already pr-ready" note.
3. Otherwise: `gh.ensure_label()` for `pr-ready`, then add `pr-ready` and
   remove every prior-state label currently present from the set
   `{vk-ready, in-progress}`. Removing both (rather than only `in-progress`)
   covers the case where `claim` was skipped or never ran — the post-state
   is the same regardless of starting state.
4. On hard-fail: print the PR URL (from `--pr-url`, or queried from `gh pr
   list --search head:<branch>` if not supplied) and the exact remediation
   command. Exit non-zero so the orchestrating skill sees the failure.

### 5. New `gh.py` helper

Today `gh.edit_issue_labels()` is add-only (`src/vk/gh.py:198-208`). The
transitions need to add and remove in one call. Either:

- Extend `edit_issue_labels()` to accept an optional `remove_labels` list and
  emit `--remove-label` flags alongside `--add-label`, or
- Add a sibling `gh.swap_issue_labels(*, repo, number, add, remove)`.

Prefer the second — clearer intent at the callsite, no overloaded
parameters. The existing `edit_issue_labels` keeps its narrow contract.

### 6. Skill update

`skills/vk-execute/SKILL.md`:

- Replace the "Label lifecycle" section's raw `gh issue edit` block with
  references to the new subcommands.
- Add `vk execute claim` between current procedure steps 1 (check-deps) and
  2 (scope). Dispatched mode only — Local mode has no Issue.
- Add `vk execute pr-opened` immediately after step 6 (`gh pr create`,
  delegated to `superpowers:finishing-a-development-branch`). Dispatched
  mode only.
- `pr-opened` and the existing step 7 (VK MCP `update_issue` to `In Review`)
  are siblings — both run after `gh pr create` and target independent
  surfaces (GitHub vs VK board). Either order is fine; the skill orders
  `pr-opened` first so the GitHub label state is correct before the VK
  sync, in case any board automation reads it.

The "Best-effort: failure does not block PR creation" line is removed.
Failures now hard-fail per the cross-cutting principle.

### 7. `vk admin labels-sync` — repo-wide cleanup command

New subcommand: `src/vk/commands/admin_cmd.py` (new module — `vk` does not
yet have an `admin` command group). Wired from `src/vk/main.py` next to the
existing groups.

```
vk admin labels-sync \
    --owner <name> \
    [--repo <name>] \
    [--remove-defaults] \
    [--yes] \
    [--dry-run]
```

Behavior:

1. **Repo enumeration.**
   - With `--repo <name>`: target just `<owner>/<name>`.
   - Without: enumerate every repo under `--owner` that the authenticated
     user can administer. Implementation detail (resolved in the plan):
     either `gh repo list <owner> --limit 200 --json name,isArchived` plus a
     per-repo permission check, or `gh api` against the search/list
     endpoints with the appropriate filter. Archived repos are skipped.

2. **Per-repo plan.** For each target repo, query existing labels via
   `gh label list --repo <r> --json name,color,description --limit 200`.
   Compute three buckets:
   - **`= already correct`**: registry label name present with matching
     color and description.
   - **`+ create` / `~ update`**: registry label missing, or present with
     wrong color/description.
   - **`- remove default`** (only with `--remove-defaults`): GitHub default
     label present **and** has zero open or closed Issues using it.
     "Default labels" enumerated explicitly: `bug`, `documentation`,
     `duplicate`, `enhancement`, `good first issue`, `help wanted`,
     `invalid`, `question`, `wontfix`. A default label that has any Issues
     attached is left alone — that's user data, not garbage. The Issue-count
     check is `gh issue list --repo <r> --label <name> --state all --json id`.

3. **Dry-run is the default.** Without `--yes`, the command prints a per-repo
   table of the planned changes (one row per label, columns: `repo`,
   `action`, `label`, `details`) and exits 0 without making any API call
   that mutates state.

4. **Apply with `--yes`.** Print the same table, then execute the actions
   (create / update via `gh label create --force`, remove via
   `gh label delete --yes`). After each repo, print a one-line summary
   (`<owner>/<repo>: 4 created, 2 updated, 3 removed, 5 unchanged`).

5. **Failure.** Per-repo errors print but don't abort the run — one repo
   with a permission glitch shouldn't stop a sweep across the org. Final
   exit code is non-zero if any repo had errors.

The `--remove-defaults` "skip if used" rule is the destructive-action guard:
silently nuking labels that someone hand-applied to historical Issues is
exactly the kind of "executing with care" failure mode this command must
avoid.

## Lifecycle as it works after this spec ships

```
vk dispatch create ────► Issue #N labels: [vk-ready, plan:slug, phase:n]
                          (also bootstraps in-progress, pr-ready in repo)
                          │
agent picks up #N ──────► vk execute check-deps     (passes)
                          vk execute claim --issue N
                                            ──► [in-progress, plan:slug, phase:n]
                          vk execute scope
                          (agent does the work)
                          vk execute check-step ... (per step)
                          vk execute pr-body
                          gh pr create                 (succeeds)
                          vk execute pr-opened --issue N
                                            ──► [pr-ready, plan:slug, phase:n]
                          (PR merged) ──► Issue auto-closes (GitHub)
```

No harness involvement. Same flow in `agent-images`, in `superpowers-for-vk`,
in any future repo that adopts dispatch.

## Testing

**Unit (superpowers-for-vk):**

- `labels.py` — registry round-trips: `plan_label("foo").name == "plan:foo"`,
  colors are 6-char hex, no name collisions.
- `config.py` — `_parse_dispatch` populates `in_progress` and `pr_ready`
  defaults when YAML doesn't override; honors override when it does.
- `dispatch_cmd.py` — assert `required_labels` contains `in-progress` and
  `pr-ready` for an agentic plan; assert custom override names propagate.
- `execute_cmd.py::claim` — mock `_run_gh`. Cases: cold start
  (`vk-ready` → `in-progress`), already-claimed (no API call), self-heal
  (label missing → `ensure_label` then edit), `manual` Issue (hard-fail),
  network 5xx (retry-then-fail), 403 (no retry, hard-fail).
- `execute_cmd.py::pr_opened` — mock `_run_gh`. Cases: post-claim happy
  path (`in-progress` → `pr-ready`), missed-claim path (`vk-ready` →
  `pr-ready` directly), already-pr-ready, network retry, hard-fail prints
  PR URL and remediation command.
- `gh.py::swap_issue_labels` — args shape, error propagation.
- `admin_cmd.py::labels_sync` — mock `gh repo list`/`gh label list`/
  `gh issue list`. Cases: dry-run table generation, single-repo mode,
  org-wide mode (filtering on `viewerCanAdminister`), `--remove-defaults`
  with-issues vs without-issues bucket logic, per-repo error doesn't
  abort run.

**Integration:**

- End-to-end `vk dispatch create` against a fresh fake repo (mocked `gh`):
  assert all six labels created with canonical colors.
- End-to-end agent flow (mocked): `claim` → `pr-opened` produces correct
  label states at each step.

**Skill validation:**

- `tests/unit/test_skill_validation.py` extended: assert `vk-execute/SKILL.md`
  references `vk execute claim` and `vk execute pr-opened` in the procedure;
  assert "best-effort: failure does not block" is *not* present.

## Lifecycle surfaces: Issue label vs Project-board field

The word "lifecycle" is overloaded in this org. Two distinct surfaces use
the string `in-progress`:

| Surface | What it is | Who sets it (today / after this spec) |
|---|---|---|
| Issue *label* `in-progress` | A literal GitHub Issue label | Nothing today / `vk execute claim` after this spec |
| Project-board field "Lifecycle" = `in-progress` | A single-select custom field on the "Derio Ops" GitHub Project | The bridge calls `willikins/scripts/hooks/vk-lifecycle-transition.sh`, which `gh project item-edit`s the field. Untouched by this spec. |

The audit at `docs/superpowers/2026-04-14-unified-descriptions-audit.md:57`
described the bridge's call as "Lifecycle transition after workspace
creation" without distinguishing label from project-field. An earlier
draft of this spec misread that as "the bridge applies the `in-progress`
label," which is false. The two surfaces are complementary: the
project-field tracks where the work is in the human-facing pipeline (idea
→ spec → plan → in-progress → deployed → …); the label is for
programmatic queries like `gh issue list --label in-progress`.

**This spec only touches Issue labels.** No bridge changes. No
project-board changes. `vk execute claim` does not call `gh project
item-edit` — that remains the bridge's job.

## Project-board excision

The `dispatch.project_board` config field is vestigial. Trace through the
codebase shows it ever reaches:

| Site | Status |
|---|---|
| `vk progress audit` → `_run_dispatch_audit` (`progress_cmd.py:380-444`) | Active — but reads from a board this project no longer tracks |
| `vk dispatch --project` flag (`dispatch_cmd.py:192-220`) | Reserved-but-unused: explicit `_ = project or ...  # reserved for project board operations` |
| `vk progress create --lifecycle` (`progress_cmd.py:281-312`) | Writes lifecycle text into Issue body; never touches the board |
| `vk progress transition` dispatch branch (`progress_cmd.py:358-360`) | Returns "not yet implemented" |
| `gh.add_to_project`, `set_field`, `get_project_id`, `get_item_id`, `get_field_id`, `get_option_id` | Six helpers, ~150 LOC, only `add_to_project` has even a unit test — no callers in `src/` for any of them |
| `gh.get_project_number`, `gh.list_project_items`, `gh.BoardItem` | Used only by `_run_dispatch_audit` |
| `init_cmd.py`, `common.py`, `tests/integration/conftest.py:62`, `tests/fixtures/configs/dispatch-enabled.yaml:17` | Scaffold / fixture references |

The "Derio Ops" board is now used for Frank-cluster feature-level health.
Nothing in `superpowers-for-vk` needs to know about it. Excision scope:

| Removed | Kept |
|---|---|
| `DispatchConfig.project_board` field (`config.py:42, 89`) | All other dispatch config |
| `vk dispatch --project` flag (`dispatch_cmd.py:192-194`) and the `_ = project or dispatch_cfg.project_board` line at `:220` | `vk dispatch` itself |
| `vk progress create --lifecycle` flag (`progress_cmd.py:285`) and any body-text emission of it | `vk progress create` itself |
| `vk progress transition` dispatch branch (`progress_cmd.py:358-360`) — never worked | Local-mode `transition` |
| `_run_dispatch_audit` function and its call from `audit` (`progress_cmd.py:380-444, 533`) | Local audit checks (status drift, spec-index drift, stale plans) |
| `gh.add_to_project`, `set_field`, `get_project_id`, `get_project_number`, `get_item_id`, `get_field_id`, `get_option_id`, `list_project_items`, `BoardItem` dataclass | All Issue-related `gh` helpers |
| `tests/unit/test_audit.py` board-mocking tests, `tests/unit/test_gh.py` `add_to_project` test | Local audit tests, all other gh tests |
| `init_cmd` writes of `project_board` into YAML scaffold; `common.py` docstring reference | Scaffold itself |
| `project_board` entries in `conftest.py` and `dispatch-enabled.yaml` fixtures | Fixtures themselves |

After excision, `vk progress audit` becomes purely local — same checks it
already runs in non-dispatch mode. The dispatch-mode branch collapses.

**Side note for archival fidelity (optional):** `docs/superpowers/specs/2026-04-12-vk-cli-toolchain-design.md:548`
references "project board" in a capability table. That table describes
intent at spec time, not current contract. A one-line note ("project_board
excised on 2026-04-27, see this spec") could be added if doc fidelity
matters; otherwise leave the toolchain spec as historical record.

## Open questions

None at spec time. Phase 4 (operator-driven label sync) will surface any
edge cases in repos with hand-curated label sets; per-repo errors from
`labels-sync` are non-blocking by design.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| Phase 1 — Lifecycle in vk-execute | `derio-net/superpowers-for-vk` | `2026-04-27-label-lifecycle-fix-phase-1` | — |
| Label Lifecycle Fix Phase 2 Implementation Plan: Project-Board Excision | `derio-net/superpowers-for-vk` | `2026-04-27-label-lifecycle-fix-phase-2-project-board-excision` | — |
| Label Lifecycle Fix Phase 3 Implementation Plan: `vk admin labels-sync` | `derio-net/superpowers-for-vk` | `2026-04-27-label-lifecycle-fix-phase-3-labels-sync` | Phase 1 |
| ~~Phase 4 — Operator-driven org sweep~~ — superseded by the v2 rebuild: the one-shot `vk admin labels-sync` was removed (`admin_cmd.py` deleted) and managed labels are now ensured per-plan by `vk apply` (`RepoLabelEnsure`). There is no separate org-wide label sweep in v2; label drift is reconciled continuously on every `vk apply`. | ~~(operator action across `derio-net/*`)~~ | — | Phase 3 deployed |

Phase 1 and Phase 2 are independent — both touch `config.py`,
`dispatch_cmd.py`, and `gh.py`, but at different lines (Phase 1 adds dict
keys + new helpers; Phase 2 removes a field + dead helpers). Whichever
merges second rebases cleanly. Phase 3 depends on Phase 1's label
registry. Phase 4 is `[manual]` — an operator runs
`vk admin labels-sync --owner derio-net --remove-defaults --yes` after
reviewing the dry-run output, and archives the diff. No agent dispatch.
