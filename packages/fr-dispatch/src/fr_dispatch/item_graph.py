"""`build_items` — the item graph a shape decomposes into (spec §4.E).

The decomposition granularity is the shape's declared `unit`, not something
the dispatcher hardcodes:

| unit    | items created            | source            |
|---------|--------------------------|-------------------|
| `run`   | 1 per workflow run       | none needed       |
| `phase` | 1 per plan phase         | a `Plan`          |
| `spec`  | 1 per distinct target repo | a `SpecMeta`    |

**This is the only item builder.** `fr_dispatch._eligible_items` is a
tracker-state *filter* over it — the phase-unit construction that used to
live there moved here whole. Two builders is how an id grammar drifts.

`inputs` is derived, not assumed: an item declares an `ArtifactRef` for
exactly the repo-tracked artifacts its shape `needs` and never `emits`
(`fr.workflow.artifacts.required_inputs`). That is what makes a `unit: run`
item carry no plan or spec ref — both are its outputs (§4.E) — and
therefore what makes the reachability gate not apply to it.

Nothing here assumes a tracker item, a PR, or even a plan exists: an
untracked phase is an item without an Issue, and a run item can be built
with no source artifact at all (the shape that emits only a document).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from fr._urls import is_cross_repo_spec, parse_issue_url
from fr.parser import Plan
from fr.types import PhaseDoc
from fr.workflow.artifacts import required_inputs

from fr_dispatch.work_item import ArtifactRef, WorkItem, item_id, parent_id, run_item_id

if TYPE_CHECKING:
    from fr.spec import SpecMeta
    from fr.workflow.model import WorkflowManifest

__all__ = ["PayloadError", "build_items", "phase_payload"]

# `item_id` needs a spec segment, but `PlanMeta.spec` is optional. A plan
# without one still needs a deterministic, collision-free identity, so the
# segment degrades to this sentinel rather than raising — identity is pure
# string composition and must never depend on an artifact existing.
NO_SPEC_SLUG = "_no-spec"

# A dispatchable Repo cell is `owner/name` and nothing else. Spec tables
# also carry rows whose Repo cell is `—`, an operator-action sentence, or a
# bare repo name with no owner (pre-v2 specs); none of those names a repo an
# item id could be composed for, so they are skipped rather than guessed at.
_REPO_CELL_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

# The Repo-cell shapes `fr.spec.PlanRef` documents as DELIBERATE markers for
# a non-repo row (§4.E: manual-action / placeholder). A cell that fails
# `_REPO_CELL_RE` for any OTHER reason — a typo'd owner/name, a stray
# character, a bare legacy name with no owner — is not one of these and is
# reported instead of silently dropped (see `_spec_items`): "doesn't parse
# as a repo" must never be indistinguishable from "wasn't meant to be one".
_INTENTIONAL_NON_REPO_CELLS = frozenset({"—", "-", ""})


def _is_intentional_non_repo_cell(cell: str) -> bool:
    return cell in _INTENTIONAL_NON_REPO_CELLS or (cell.startswith("(") and cell.endswith(")"))


class PayloadError(Exception):
    """A `WorkItem`'s payload is not the shape its `unit` promises.

    Raised by `phase_payload` only. An adapter that reaches it has been
    handed an item its `can_dispatch` should have refused, so the message
    names the unit and the item — `tick` accumulates it against that one
    item and the rest of the tick survives.
    """


def phase_payload(item: WorkItem) -> tuple[Plan, PhaseDoc, int]:
    """The `(plan, phase, issue_number)` a phase item carries — narrowed once.

    `WorkItem.payload` is deliberately `Mapping[str, Any]` (§4.D: runners
    treat it as opaque), which left every adapter doing its own
    `item.payload["plan"]` plus a `# type: ignore[attr-defined]` per
    attribute reach — six in `fr_cncd.runner.build_ingest_payload` alone.
    Six ignores are six places a wrong payload becomes a `KeyError` or an
    `AttributeError` at dispatch time; one accessor is one place, and it
    raises something an operator can act on.

    Refuses a non-phase item outright (review r5-a2): before `can_dispatch`
    learned to check `unit`, a run- or spec-unit item reached
    `item.payload["plan"]` and surfaced through `tick` as the bare string
    `"<id>: 'plan'"` under `reason=backend_error` — a KeyError's `repr`,
    naming neither the unit nor the mismatch.
    """
    if item.unit != "phase":
        raise PayloadError(
            f"{item.id}: expected a phase item, got unit {item.unit!r} "
            "(a runner that only dispatches phases must say so in `can_dispatch`)"
        )
    try:
        plan = item.payload["plan"]
        phase = item.payload["phase"]
        raw_issue = item.payload["issue_number"]
    except KeyError as e:
        raise PayloadError(f"{item.id}: phase payload is missing {e.args[0]!r}") from e
    # `payload` is `Mapping[str, object]` by design, so the types are asserted
    # here rather than assumed by every adapter. A wrong type is the same class
    # of bug as a missing key and gets the same actionable error.
    if not isinstance(plan, Plan):
        raise PayloadError(f"{item.id}: payload['plan'] is {type(plan).__name__}, not a Plan")
    if not isinstance(phase, PhaseDoc):
        raise PayloadError(f"{item.id}: payload['phase'] is {type(phase).__name__}, not a PhaseDoc")
    try:
        issue_number = int(raw_issue)  # type: ignore[call-overload]
    except (TypeError, ValueError) as e:
        raise PayloadError(
            f"{item.id}: payload['issue_number'] is not an int: {raw_issue!r}"
        ) from e
    return plan, phase, issue_number


def spec_slug(plan: Plan) -> str:
    """Identity segment for the plan's spec — its filename stem.

    Mirrors the derivation `render.py` already uses for the `spec:` label,
    so an item id and an Issue label name the same spec. Falls back to
    `NO_SPEC_SLUG` when the plan declares no spec.
    """
    spec = plan.spec_path or plan.meta.spec
    return Path(spec).stem if spec else NO_SPEC_SLUG


def plan_artifact_refs(plan: Plan) -> tuple[ArtifactRef, ...]:
    """Every artifact of this plan an item could reference (§4.D `inputs`).

    Each ref is a *coordinate*: `repo` plus a path relative to THAT repo.
    A cross-repo spec (`<owner>/<repo>:<path>` notation) is therefore split
    rather than passed through — `plan.spec_path` is deliberately None for
    one (the parser can't resolve a path in a checkout it doesn't have), so
    the raw notation would otherwise land in `path` and be attributed to
    `target_repo`, the one repo the file is not in. Same split
    `render.spec_url` and `repair` already do.

    Returns everything available; `build_items` keeps only the kinds the
    shape actually needs.
    """
    refs = [ArtifactRef(kind="plan", repo=plan.meta.target_repo, path=str(plan.repo_relative_dir))]
    spec_rel = plan.spec_path or plan.meta.spec
    if spec_rel:
        if is_cross_repo_spec(spec_rel):
            spec_repo, spec_rel = spec_rel.split(":", 1)
        else:
            spec_repo = plan.meta.target_repo
        refs.append(ArtifactRef(kind="spec", repo=spec_repo, path=spec_rel))
    return tuple(refs)


def phase_item_ref(plan: Plan, phase_number: int, tracking: str | None = None) -> str:
    """The would-be `WorkItem.id` for a phase, for FAILURE STRINGS only.

    Every failure the tick accumulates is prefixed with the item it
    concerns, because the id also names the plan — on a bridge running many
    plans, `"phase 3: …"` says nothing about which phase 3. The failures
    raised *instead of* a `WorkItem` (item construction, tracking-issue
    writeback) have no item to read an id off, so the ref is composed
    segment-wise here.

    Deliberately does NOT call `item_id`: this runs on the failure path, and
    `item_id` raising (a reserved slug, a `/` in one) is one of the things
    that lands here. Composition must never be the reason a failure string
    can't be produced.
    """
    repo = plan.meta.target_repo
    if tracking:
        try:
            repo = parse_issue_url(tracking)[0]
        except ValueError:
            pass  # keep target_repo — a malformed URL is likely the failure itself
    return f"{repo}/{spec_slug(plan)}/{plan.meta.plan}/phase/{phase_number}"


def _repo_relative_spec_path(path: Path) -> str:
    """A spec's path relative to its repo root.

    `SpecMeta.path` is whatever the caller opened — usually absolute. Specs
    live under `docs/superpowers/specs/`, so the last `docs` segment is the
    repo-relative anchor. Falls back to the bare filename when the path has
    no `docs` segment at all (a spec read from somewhere unconventional);
    an `ArtifactRef.path` is documented repo-relative, so guessing an
    absolute path into it would be worse than a name.
    """
    parts = path.parts
    if "docs" in parts:
        anchor = len(parts) - 1 - parts[::-1].index("docs")
        return str(Path(*parts[anchor:]))
    return path.name


def _keep(refs: tuple[ArtifactRef, ...], kinds: frozenset[str]) -> tuple[ArtifactRef, ...]:
    return tuple(ref for ref in refs if ref.kind in kinds)


def _accumulate(failures: list[str] | None, message: str) -> list[WorkItem]:
    """Honour the `failures` sink for an argument-shaped failure.

    `tick`'s docstring promises "all failure paths accumulate", and
    `_eligible_items` calls `build_items` outside any `try` — so a raise
    here escapes `tick` entirely and takes a whole cron iteration with it.
    `_phase_items`/`_spec_items` already honoured the sink for a malformed
    row; the unit-level argument checks did not, which is the inconsistency
    this closes.

    With NO sink the error still propagates, unchanged: a caller that wants
    to know does. The line the split falls on is data vs. programming error
    — a bad plan/shape combination accumulates, while handing a `SpecMeta`
    to a phase-unit shape (`_as_plan`/`_as_spec`) still raises `TypeError`
    regardless, because that is the caller being wrong, not one plan.
    """
    if failures is None:
        raise ValueError(message)
    failures.append(message)
    return []


def _run_item_ref(repo: str | None, run_id: str | None) -> str:
    """A run item's would-be id, for FAILURE STRINGS only — same doctrine as
    `phase_item_ref`: the failure is about a MISSING coordinate, so the ref
    is composed segment-wise and never through `run_item_id` (which raises
    on exactly the inputs that land here)."""
    return f"{repo or '<no-repo>'}/run/{run_id or '<no-run-id>'}"


def _run_items(
    workflow: WorkflowManifest,
    source: Plan | None,
    repo: str | None,
    run_id: str | None,
    required: frozenset[str],
    failures: list[str] | None,
) -> list[WorkItem]:
    if run_id is None:
        return _accumulate(
            failures,
            f"{_run_item_ref(repo, run_id)}: a run-unit shape needs a run_id (see `fr run start`)",
        )
    if repo is None:
        if source is None:
            return _accumulate(
                failures,
                f"{_run_item_ref(repo, run_id)}: a run-unit shape needs a repo when no "
                "source artifact is given",
            )
        repo = source.meta.target_repo
    inputs = _keep(plan_artifact_refs(source), required) if source is not None else ()
    payload: dict[str, object] = {"run_id": run_id}
    if source is not None:
        payload["plan"] = source
    try:
        iid = run_item_id(repo, run_id)
    except ValueError as e:
        return _accumulate(failures, f"{_run_item_ref(repo, run_id)}: {e}")
    return [
        WorkItem(
            id=iid,
            unit="run",
            workflow=workflow.workflow,
            repo=repo,
            parent=None,
            inputs=inputs,
            payload=payload,
            tracking=None,
        )
    ]


def _phase_repos(plan: Plan) -> dict[int, str]:
    """Which repo each phase's item is keyed on — the Issue's repo when the
    phase is tracked, else `target_repo`.

    Computed for the WHOLE plan up front because `depends_on` needs it: a
    dependency edge must name the DEPENDENCY's id, and that id is keyed on
    the dependency's own repo, which need not be the depending phase's
    (`render.py` builds cross-repo Issue URLs, so this is a supported plan
    shape, not a hypothetical). Composing the edge from the current phase's
    repo produced an id no item has.

    A dependency whose tracking URL is malformed degrades to `target_repo`
    rather than failing the phase that merely depends on it — that phase
    fails itself, once, in `_phase_items`.
    """
    repos: dict[int, str] = {}
    for phase in plan.phases:
        repo = plan.meta.target_repo
        tracking = phase.phase.tracking_issue
        if tracking:
            try:
                repo = parse_issue_url(tracking)[0]
            except ValueError:
                pass
        repos[phase.phase.number] = repo
    return repos


def _phase_items(
    workflow: WorkflowManifest,
    plan: Plan,
    required: frozenset[str],
    failures: list[str] | None,
) -> list[WorkItem]:
    slug = spec_slug(plan)
    plan_slug = plan.meta.plan
    inputs = _keep(plan_artifact_refs(plan), required)
    repo_by_phase = _phase_repos(plan)
    items: list[WorkItem] = []
    for phase in plan.phases:
        n = phase.phase.number
        tracking = phase.phase.tracking_issue
        try:
            payload: dict[str, object] = {"plan": plan, "phase": phase}
            repo = plan.meta.target_repo
            if tracking:
                # The ISSUE's repo, not `target_repo`: `can_dispatch(item)`
                # reads `item.repo`, so a cross-repo phase must carry the
                # repo it actually executes in.
                repo, issue_number = parse_issue_url(tracking)
                payload["issue_number"] = issue_number
            iid = item_id(repo, slug, plan_slug, phase=n)
            # Each edge is the DEPENDENCY's id, so it is keyed on the
            # dependency's repo — not on `repo`, which is this phase's.
            payload["depends_on"] = tuple(
                item_id(repo_by_phase.get(d, plan.meta.target_repo), slug, plan_slug, phase=d)
                for d in phase.phase.depends_on
            )
            items.append(
                WorkItem(
                    id=iid,
                    unit="phase",
                    workflow=workflow.workflow,
                    repo=repo,
                    parent=parent_id(iid),
                    inputs=inputs,
                    payload=payload,
                    tracking=tracking,
                )
            )
        except Exception as e:  # noqa: BLE001 — one bad phase mustn't kill the graph
            if failures is None:
                raise
            failures.append(f"{phase_item_ref(plan, n, tracking)}: {e}")
            continue
    return items


def _spec_items(
    workflow: WorkflowManifest,
    spec: SpecMeta,
    repo: str | None,
    required: frozenset[str],
    failures: list[str] | None,
) -> list[WorkItem]:
    if repo is None:
        return _accumulate(
            failures,
            f"{spec.path.stem}: a spec-unit shape needs the repo the spec itself lives in",
        )
    slug = spec.path.stem
    try:
        home = item_id(repo, slug)
    except ValueError as e:
        # `item_id` rejects the reserved slug `run` (it would collide with
        # the run-item form). A spec file literally named `run.md` is
        # therefore un-addressable — and this call sat OUTSIDE the sink, so
        # it raised straight through `tick` (review r5-a4). Route it through
        # `_accumulate` like every other argument-shaped failure: with a
        # sink it is one bad spec, without one it still raises.
        return _accumulate(failures, f"{repo}/{slug}: {e}")
    inputs = (
        (ArtifactRef(kind="spec", repo=repo, path=_repo_relative_spec_path(spec.path)),)
        if "spec" in required
        else ()
    )
    items: list[WorkItem] = []
    seen: set[str] = set()
    for row in spec.plans:
        target = row.repo
        if not _REPO_CELL_RE.match(target):
            if failures is not None and not _is_intentional_non_repo_cell(target):
                # A cell that doesn't look like `owner/name` and doesn't
                # look like a deliberate marker either is most likely a
                # typo of a real repo — report it so the operator can fix
                # the table row, rather than silently dropping that repo
                # from the fan-out (indistinguishable from an omitted one).
                failures.append(
                    f"{home}: row {row.name!r} has Repo cell {target!r} — not an owner/name repo"
                )
            continue
        if target in seen:
            # A repo named on more than one plan row is a normal spec shape
            # (one repo, several plans) — dedup silently. Not an error;
            # do not start reporting this as a failure.
            continue
        seen.add(target)
        try:
            iid = item_id(target, slug)
        except ValueError as e:
            if failures is None:
                raise
            failures.append(f"{target}/{slug}: {e}")
            continue
        items.append(
            WorkItem(
                id=iid,
                unit="spec",
                workflow=workflow.workflow,
                repo=target,
                # Units compose recursively (§4.E): a per-repo item is
                # decomposed further by that repo's own shape, and its
                # parent is the spec item in the repo the spec lives in.
                # The home repo's own item IS that item, and nothing is its
                # own parent — it is a root, like `parent_id` says.
                parent=None if iid == home else home,
                inputs=inputs,
                payload={
                    "spec": spec,
                    "plan_refs": tuple(r for r in spec.plans if r.repo == target),
                },
                tracking=None,
            )
        )
    return items


def build_items(
    workflow: WorkflowManifest,
    source: Plan | SpecMeta | None = None,
    *,
    repo: str | None = None,
    run_id: str | None = None,
    failures: list[str] | None = None,
) -> list[WorkItem]:
    """The `WorkItem` graph `workflow` decomposes `source` into.

    `source` is unit-dependent: a `Plan` for `unit: phase`, a `SpecMeta` for
    `unit: spec`, and *optional* for `unit: run` — a run may precede every
    artifact it will eventually emit, which is the whole point of §4.E's
    "the reachability gate does not apply to a run".

    `repo` names the repo the work belongs to. It is required for
    `unit: spec` (the repo the spec itself lives in, which its plan table
    never states) and for a `unit: run` with no source; a `Plan` source
    supplies it from `meta.target_repo`.

    `failures` is an optional sink: when given, an item that cannot be
    constructed (a malformed tracking URL, an un-composable id) is
    accumulated as `"<item-ref>: <error>"` and the rest of the graph is
    still returned — one bad phase fails only itself. When `None`, the
    error propagates, so a caller that wants to know does.

    **With a sink, no argument-shaped failure raises** (review fix r2-f9) —
    a missing `run_id`, a missing `repo`, a missing source. `tick` promises
    "all failure paths accumulate" and calls this outside any `try`, so a
    raise there killed the whole cron iteration rather than one shape. The
    one class that still raises regardless is a wrong source TYPE
    (`_as_plan`/`_as_spec`): that is the caller being wrong, not the data.
    """
    required = required_inputs(workflow)
    if workflow.unit == "run":
        return _run_items(workflow, _as_plan(source), repo, run_id, required, failures)
    if workflow.unit == "phase":
        plan = _as_plan(source)
        if plan is None:
            return _accumulate(
                failures, f"{workflow.workflow}: a phase-unit shape needs a Plan to decompose"
            )
        return _phase_items(workflow, plan, required, failures)
    spec = _as_spec(source)
    if spec is None:
        return _accumulate(
            failures, f"{workflow.workflow}: a spec-unit shape needs a SpecMeta to decompose"
        )
    return _spec_items(workflow, spec, repo, required, failures)


def _as_plan(source: Plan | SpecMeta | None) -> Plan | None:
    if source is None or isinstance(source, Plan):
        return source
    raise TypeError(f"expected a Plan source, got {type(source).__name__}")


def _as_spec(source: Plan | SpecMeta | None) -> SpecMeta | None:
    from fr.spec import SpecMeta

    if source is None or isinstance(source, SpecMeta):
        return source
    raise TypeError(f"expected a SpecMeta source, got {type(source).__name__}")
