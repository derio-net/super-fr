"""`WorkItem` — the unit-agnostic dispatch value, and its stable identity.

Spec 2026-08-14-workflow-shapes-and-workitem-dispatch §4.D: `Runner.dispatch`
is generalized from `(plan, phase, repo, issue_number)` to a single
`WorkItem`, because the decomposition granularity (`run` | `phase` | `spec`,
§4.E) is now a shape's declared `unit`, not a hardcoded assumption.

**Identity replaces title-string dedup.** Today dedup is
`build_card_title(repo, issue_number)` — a card *title*, keyed on an Issue
number that exists only because granularity was hardcoded to one Issue per
phase. Under this design some items have no tracker artifact at creation
time, so identity must be derivable from the item's position in the graph
alone. Four levels (corrected during Phase 2 review — a `unit: run` item is
dispatched *before* its spec and plan exist, both are its §4.E *outputs*, so
it cannot be keyed on a spec/plan slug it doesn't have yet):

    run    <repo>/run/<run-id>                        unit: run
    spec   <repo>/<spec-slug>                          unit: spec
    plan   <repo>/<spec-slug>/<plan-slug>              (parent level only — not a unit)
    phase  <repo>/<spec-slug>/<plan-slug>/phase/<n>    unit: phase

`item_id`/`run_item_id` are pure string composition — no I/O, no tracker
calls — so identity is computable before any Issue, card, spec, or plan
exists. `parent_id` walks back up that same string, one level at a time, to
`None` at a root (spec level for the spec/plan/phase branch; a run item is
*also* a root — it has no spec yet, and per spec §6/Phase 8 a shape that
emits only a document may never gain one). `WorkItem.parent` seeds from
`parent_id`, mirroring `PlanMeta.parent_plan`.

`repo` is always `owner/name` (2 segments), which is what pins the segment
counts above; slugs may not contain `/` and both are **checked at
construction** rather than assumed, since an embedded `/` silently changes
which level the composed id parses as. Classification is by shape — length
first, marker second — so a repo literally named `phase` or `run` does not
capture a level it isn't. The run form and the plan form are both
"`<owner>/<repo>` plus two segments"; the literal `run/` marker
disambiguates them, and `item_id` rejects a spec slug of `"run"` so a
spec-level id can never collide with a run-level one.

**Two items with the same `id` ARE the same item**: `__eq__` and `__hash__`
both key on `id` alone. `payload` is incidental cargo (it carries a `Plan`
and a `PhaseDoc` on the phase path), so letting it participate in equality
would make a set hold two copies of one graph position.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

Unit = Literal["run", "phase", "spec"]

# The fourth grammar level ("plan") is a parent only — no `unit` value pairs
# with it. `_id_level` returns this in addition to `Unit`'s three members.
_Level = Literal["run", "spec", "plan", "phase"]

# Reserved: collides with the run-item form (`<repo>/run/<run-id>`), both
# being "<owner>/<repo>" plus two segments.
_RESERVED_SPEC_SLUG = "run"


def _check_repo(repo: str) -> None:
    """`repo` must be exactly `owner/name`.

    Every segment count `_id_level` classifies by assumes it. A repo that is
    not two segments therefore composes an id of the WRONG LEVEL — silently,
    since composition is just string joining. Fail where the caller is.
    """
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f'repo must be "owner/name", got {repo!r}')


def _check_segment(name: str, value: str) -> None:
    """One id segment: non-empty and free of `/`.

    A `/` inside a slug forges an extra segment and changes the id's level
    (`_id_level` reads segment counts), so it is rejected at construction
    rather than surfacing later as a mysteriously misclassified id.
    """
    if not value or "/" in value:
        raise ValueError(f"{name} must be a single non-empty path segment, got {value!r}")


def item_id(
    repo: str,
    spec_slug: str,
    plan_slug: str | None = None,
    phase: int | None = None,
) -> str:
    """Deterministic identity string for a spec/plan/phase graph position.

    Pure string composition — no I/O, no tracker calls. A phase cannot exist
    outside a plan, so `phase` without `plan_slug` raises. `spec_slug="run"`
    raises — that name is reserved for `run_item_id`. `repo` and every slug
    are checked for shape, because composition alone cannot notice that an
    embedded `/` has changed which grammar level the result parses as.
    """
    _check_repo(repo)
    _check_segment("spec_slug", spec_slug)
    if plan_slug is not None:
        _check_segment("plan_slug", plan_slug)
    if spec_slug == _RESERVED_SPEC_SLUG:
        raise ValueError(
            f'spec_slug cannot be "{_RESERVED_SPEC_SLUG}" — reserved for run-item '
            "identity (see run_item_id), which would otherwise collide with it"
        )
    if phase is not None and plan_slug is None:
        raise ValueError("a phase cannot exist outside a plan (plan_slug is required)")
    parts = [repo, spec_slug]
    if plan_slug is not None:
        parts.append(plan_slug)
        if phase is not None:
            parts.append("phase")
            parts.append(str(phase))
    return "/".join(parts)


def run_item_id(repo: str, run_id: str) -> str:
    """Deterministic identity string for a `unit: run` item.

    A run item is dispatched before its spec and plan exist (§4.E — both are
    its outputs), so its only stable name at creation is the run id assigned
    by `fr run start` (§4.B). Pure string composition, like `item_id`.

    `run_id` is constrained to a single non-empty segment: `fr run start`
    (Phase 7) is what mints it, and a `/` in it would compose a 5-segment
    string that `_id_level` rejects as malformed — long after the caller
    that could have said what went wrong.
    """
    _check_repo(repo)
    _check_segment("run_id", run_id)
    return "/".join((repo, "run", run_id))


def _id_level(some_item_id: str) -> _Level:
    """Which of the four id shapes `some_item_id` is, or raise.

    Classified by SHAPE — segment count first, marker second. `repo` is
    always `owner/name`, so each level has an exact length: 3 (spec), 4 (run
    or plan, disambiguated by the literal `run` marker), 6 (phase). Testing
    a marker before the length is what let `owner/phase/my-spec` — a spec in
    a repo named `phase` — classify as a phase-level id.
    """
    segments = some_item_id.split("/")
    if len(segments) == 6 and segments[4] == "phase":
        return "phase"
    if len(segments) == 4:
        return "run" if segments[2] == "run" else "plan"
    if len(segments) == 3:
        return "spec"
    raise ValueError(f"not a well-formed item id: {some_item_id!r}")


def parent_id(some_item_id: str) -> str | None:
    """The id one level up the graph, or `None` at a root.

    Both `spec` and `run` are roots — a run item has no spec yet (and may
    never gain one; see the module docstring).
    """
    segments = some_item_id.split("/")
    level = _id_level(some_item_id)
    if level == "phase":
        return "/".join(segments[:-2])
    if level == "plan":
        return "/".join(segments[:3])
    return None


@dataclass(frozen=True)
class ArtifactRef:
    """A reference to one input artifact (plan, spec, report, …).

    `path` is repo-relative and normalized: a leading `./` is stripped so
    two refs to the same file never compare unequal over presentation noise.
    """

    kind: str
    repo: str
    path: str

    def __post_init__(self) -> None:
        if self.path.startswith("./"):
            object.__setattr__(self, "path", self.path[2:])


@dataclass(frozen=True, eq=False)
class WorkItem:
    """One unit of dispatch — a run, a phase, or a per-repo spec item.

    `id` and `unit` must agree: `id`'s shape (see module docstring) is
    derived independently via `item_id`, and `__post_init__` checks the two
    were not constructed out of sync.
    """

    id: str
    unit: Unit
    workflow: str
    repo: str
    parent: str | None
    inputs: tuple[ArtifactRef, ...]
    payload: Mapping[str, object] = field(default_factory=dict)
    tracking: str | None = None

    def __post_init__(self) -> None:
        level = _id_level(self.id)
        if level != self.unit:
            raise ValueError(
                f"unit {self.unit!r} does not match id {self.id!r} (id looks like {level!r})"
            )

    def __eq__(self, other: object) -> bool:
        # Identity IS the id (`item_id` — see module docstring), so equality
        # is too. The generated field-wise `__eq__` disagreed with
        # `__hash__`: two items for the same graph position but different
        # `payload` hashed equal and compared unequal, so a set held both
        # and every dict lookup ran a deep `Plan.__eq__` to answer "no".
        if not isinstance(other, WorkItem):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        # Matches `__eq__` above. `payload` is an opaque `Mapping` that may
        # not be hashable (e.g. a plain dict) — hashing the id alone is what
        # keeps WorkItem usable as a set/dict key regardless.
        return hash(self.id)
