"""Tracker Protocol + per-instance mapping config — spec §4.G.

`Tracker` is a small, tracker-neutral seam onto one tracker *instance* (a
GitHub repo, a Jira project): `supports`/`observe`/`create_item`/
`transition`/`link_parent`. Nothing here builds a Jira adapter — the
Protocol and the config loader are the whole deliverable.

**Mappings are per instance, not per tracker type.** Two Jira projects on
the same server can expose different transitions, so a `jira: {...}` block
in `trackers.yaml` keys on project, not on "jira" once. `load_trackers`
parses the file; `resolve_instance_mapping` picks repo over user, exactly
`fr.models.resolve`'s precedent (a whole per-instance mapping wins or loses
together — the same granularity `fr.models` resolves at, one config wins
per lookup, never a field-by-field merge of two files).

**Mappings are partial by design.** A tracker instance may be unable to
express some `ItemState` (a Jira project with no "in review" status, a
GitHub board with no review column). `state_supported` reports `False` for
both an explicit `null` and an absent key — spec §4.G's example uses `null`
for "unsupported by this project's workflow"; treating an omitted state the
same way lets an author write a short partial mapping without spelling out
every unsupported state as `null`.

**Live validation is NOT implemented here.** Spec §4.G's other half — "a
mapping must be validated against the live server's actually-available
transitions" — needs a live tracker to validate against, and this phase
ships no adapter that reaches one. `check_tracker_mapping_shape` is named
for exactly what it does (config *shape*, not server truth) so nobody reads
it as the real guard; that guard is future work for whoever builds the
Jira adapter.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import yaml

from fr.item_state import ITEM_STATES, ItemState

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

# One instance's mapping: ItemState -> opaque tracker-specific detail, or
# `None` when this instance cannot express that state.
TrackerMapping = dict[str, dict[str, object] | None]

# tracker_type -> instance -> TrackerMapping
TrackersConfig = dict[str, dict[str, TrackerMapping]]


class TrackerConfigError(Exception):
    """Raised when a `trackers.yaml`-shaped config is structurally invalid."""


class TrackedItem(Protocol):
    """The minimal shape `Tracker` methods need from a dispatch item.

    Structural on purpose, NOT `fr_dispatch.work_item.WorkItem` itself:
    `fr` never imports `fr_dispatch` — enforced by
    `tests/unit/test_import_direction.py`, the base/framework split the
    2026-06-05 super-fr split exists to keep — so this Protocol names the
    two fields `Tracker` implementations actually touch (`id`, `tracking`)
    rather than the concrete dispatch type. Every real `WorkItem` satisfies
    this by construction (`fr_dispatch` depends on `fr`, so it can pass its
    own `WorkItem`s to a `Tracker` without either side importing the other);
    nothing has to be done for that to keep working.
    """

    id: str
    tracking: str | None


class Tracker(Protocol):
    """One tracker instance, as seen by the seams this phase defines.

    Designed against the HIERARCHICAL case — Jira's Epic -> Story ->
    Sub-task nests onto spec -> plan -> phase almost exactly — and degraded
    for the flat one: GitHub has no native parent link and must synthesise
    hierarchy from links or task lists, which is why `link_parent` exists
    as its own method rather than being folded into `create_item`.
    """

    name: str
    """Tracker TYPE (`trackers.yaml`'s top-level key, e.g. "github" or
    "jira") — NOT the per-project instance. The instance lives on the
    concrete implementation (e.g. `GithubTracker.instance`), not on this
    Protocol, because a Tracker object already speaks for one instance."""

    def supports(self, state: ItemState) -> bool:
        """Can THIS instance express `state`?

        False for a partial mapping's unsupported state (spec §4.G) — the
        fact this can legitimately be False is the entire reason the
        refusal-at-preflight path exists (`fr_dispatch._tracker_blocker`).
        """
        ...

    def observe(self, items: Sequence[TrackedItem]) -> Mapping[str, ItemState]:
        """Current `ItemState` per item id, for items this tracker can see."""
        ...

    def create_item(self, item: TrackedItem) -> str:
        """Create the tracker artifact for `item`; return its URL/key."""
        ...

    def transition(self, item: TrackedItem, to: ItemState) -> None:
        """Move `item`'s tracker artifact to state `to`."""
        ...

    def link_parent(self, child: TrackedItem, parent: TrackedItem) -> None:
        """Record `child`'s place under `parent` in tracker-native terms."""
        ...


def load_trackers(path: Path) -> TrackersConfig:
    """Parse a `<tracker> -> <instance> -> <ItemState> -> mapping|null` file.

    A missing file yields `{}` (mirrors `fr.models.load_models`: no config
    is a legal, empty config, not an error). Raises `TrackerConfigError`
    for a non-mapping top level, a non-mapping instance value, or a state
    key outside `ITEM_STATES` — fail loud rather than silently drop an
    author's typo into "unsupported."
    """
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    if not isinstance(raw, dict):
        raise TrackerConfigError(f"{path}: top level must be a tracker→instance→state mapping")
    out: TrackersConfig = {}
    for tracker_type, instances in raw.items():
        if not isinstance(instances, dict):
            raise TrackerConfigError(
                f"{path}: tracker {tracker_type!r} must map instances to state mappings"
            )
        out[tracker_type] = {}
        for instance, states in instances.items():
            if not isinstance(states, dict):
                raise TrackerConfigError(
                    f"{path}: {tracker_type}/{instance} must map states to mapping details"
                )
            unknown = set(states) - set(ITEM_STATES)
            if unknown:
                raise TrackerConfigError(
                    f"{path}: {tracker_type}/{instance} declares unknown state(s) "
                    f"{sorted(unknown)!r} (valid: {', '.join(ITEM_STATES)})"
                )
            out[tracker_type][str(instance)] = dict(states)
    return out


def default_trackers_path() -> Path:
    """User-level trackers config, honoring `$XDG_CONFIG_HOME` then `$HOME`.

    Mirrors `fr.models.default_models_path` exactly — same env precedence,
    same `fr/<file>.yaml` shape."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "fr" / "trackers.yaml"


REPO_TRACKERS_REL = Path("docs/superpowers/trackers.yaml")
"""Repo-level override path (spec §4.G), read the same way `fr.models`
reads `docs/superpowers/models.yaml` — resolution is repo over user."""


def resolve_instance_mapping(
    tracker_type: str,
    instance: str,
    *,
    repo_cfg: TrackersConfig,
    user_cfg: TrackersConfig,
) -> TrackerMapping | None:
    """Resolve one instance's mapping: repo over user, whole-instance
    granularity (mirrors `fr.models.resolve`'s repo-over-user order, but at
    the instance level rather than fr.models' per-tier level — a tracker
    mapping is authored as one coherent per-project workflow, not assembled
    field-by-field from two files).

    `None` when neither config declares the instance — a real gap the
    caller must decide how to handle (`GithubTracker` treats it as "use the
    default label behavior"; a hypothetical Jira adapter would have nothing
    to fall back to and should refuse to construct).
    """
    for cfg in (repo_cfg, user_cfg):
        mapping = cfg.get(tracker_type, {}).get(instance)
        if mapping is not None:
            return mapping
    return None


def state_supported(mapping: TrackerMapping | None, state: ItemState) -> bool:
    """False for no mapping, an explicit `null` entry, or an absent state
    key; True otherwise (spec §4.G: "a null mapping means that instance
    cannot express that state" — an omitted key means the same thing, so a
    partial mapping doesn't have to spell out every unsupported state)."""
    if mapping is None:
        return False
    return mapping.get(state) is not None


def missing_states(required: Iterable[ItemState], tracker: Tracker) -> tuple[ItemState, ...]:
    """The sorted shortfall: states `required` but `tracker` cannot express.

    Pure — no I/O beyond `tracker.supports` calls. Mirrors
    `fr.capabilities.missing_capabilities`'s shape exactly, the function
    Phase 5 built the refusal path around; `fr_dispatch._tracker_blocker`
    is this function's `_capability_blocker`.
    """
    return tuple(sorted(s for s in required if not tracker.supports(s)))


def check_tracker_mapping_shape(
    tracker_type: str,
    instance: str,
    *,
    repo_cfg: TrackersConfig,
    user_cfg: TrackersConfig,
) -> list[str]:
    """Config-*shape* validation only — NOT validation against a live
    server. Reports an instance that resolves to no mapping at all in
    either config. `load_trackers` (called upstream, before this function
    ever runs) is what catches an unknown state key.

    Spec §4.G's other requirement — "a mapping must be validated against
    the project's actually-available transitions" — needs a live tracker to
    ask, and this phase ships no adapter that reaches one (no Jira adapter
    exists). That half is NOT done by this function or by anything else in
    this module; flagging it here rather than naming this function as
    though it already does it.
    """
    mapping = resolve_instance_mapping(tracker_type, instance, repo_cfg=repo_cfg, user_cfg=user_cfg)
    if mapping is None:
        return [
            f"no mapping configured for {tracker_type}/{instance} in repo or user "
            f"config (config-shape check only — this does not confirm the instance "
            f"exists on a live server)"
        ]
    return []
