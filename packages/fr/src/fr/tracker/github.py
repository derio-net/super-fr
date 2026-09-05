"""`GithubTracker` — the Tracker seam built from today's label behavior.

Delegates the state <-> label mapping to `fr.item_state` (`project_github`,
`state_from_labels`) rather than reimplementing it — the same module
`fr_dispatch._is_dispatchable` already reads. This is not a second
GitHub-tracker implementation; it is the existing label vocabulary wrapped
in the `fr.tracker.model.Tracker` shape.

No Jira adapter exists; this is the one concrete `Tracker` this phase ships,
and its job is to prove the Protocol is satisfiable against real code, not
to add GitHub behavior that does not already exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fr._urls import parse_issue_url
from fr.item_state import ITEM_STATES, ItemState, project_github, state_from_labels
from fr.tracker.model import TrackedItem, TrackerMapping, state_supported

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from fr.ghclient import GhClient


@dataclass(frozen=True)
class GithubTracker:
    """The GitHub tracker instance (spec §4.G).

    `instance` is an `owner/repo` string. GitHub has no per-project
    transition config the way Jira does, but the *shape* of "one mapping
    per tracker instance" still holds — a fork could in principle be
    configured with different label names — so the field is real rather
    than decorative.

    `mapping` is the resolved per-instance override
    (`fr.tracker.model.resolve_instance_mapping`'s result), `None` when the
    instance has no entry in `trackers.yaml`. Absent a mapping,
    `GithubTracker` supports every `ItemState`: `fr.item_state`'s default
    label projection already covers all five states, which IS "the
    existing label behavior" this class delegates to.
    """

    instance: str
    gh: GhClient
    mapping: TrackerMapping | None = None
    name: str = "github"

    def supports(self, state: ItemState) -> bool:
        if self.mapping is None:
            return True
        return state_supported(self.mapping, state)

    def observe(self, items: Sequence[TrackedItem]) -> Mapping[str, ItemState]:
        """Read each item's current state off its tracking Issue.

        Delegates the label -> state inversion to
        `fr.item_state.state_from_labels` — the same function
        `fr_dispatch._is_dispatchable` uses — instead of re-deriving it.
        Items with no tracking URL yet are absent from the result, as are
        items whose Issue carries no recognised lifecycle label (nothing
        to report, mirroring `state_from_labels` returning `None`).
        """
        result: dict[str, ItemState] = {}
        for item in items:
            if item.tracking is None:
                continue
            repo, number = parse_issue_url(item.tracking)
            issue = self.gh.view_issue(repo, number)
            if issue.get("state") == "CLOSED":
                result[item.id] = "done"
                continue
            names = set(issue.get("labels") or [])
            state = state_from_labels(names)
            if state is not None:
                result[item.id] = state
        return result

    def create_item(self, item: TrackedItem) -> str:
        """Refuses — GitHub Issue creation stays operator-only.

        `fr apply --yes` is the one sanctioned creation path
        (`apply(skip_issue_create=True)` in `fr_dispatch.tick`; the
        2026-05-18 incident). The tracker seam does not grow a second,
        automatic creation path alongside it.
        """
        raise NotImplementedError(
            f"GithubTracker.create_item({item.id!r}): GitHub Issue creation is "
            "operator-only (fr apply --yes; see the 2026-05-18 incident). The "
            "tracker seam does not bypass that invariant."
        )

    def transition(self, item: TrackedItem, to: ItemState) -> None:
        """Move `item`'s Issue to `to` by editing its lifecycle labels
        (`fr.item_state.project_github`) and, for `done`, closing the
        Issue — the same two primitives `fr.apply` already uses, called
        directly rather than reimplemented.
        """
        if item.tracking is None:
            raise ValueError(f"{item.id}: cannot transition an item with no tracking Issue")
        if not self.supports(to):
            raise ValueError(
                f"{self.name!r} instance {self.instance!r} cannot express state {to!r}"
            )
        repo, number = parse_issue_url(item.tracking)
        add = {label.name for label in project_github(to)}
        all_lifecycle = {label.name for state in ITEM_STATES for label in project_github(state)}
        remove = all_lifecycle - add
        self.gh.edit_issue_labels(repo, number, add=frozenset(add), remove=frozenset(remove))
        if to == "done":
            self.gh.edit_issue_state(repo, number, state="closed")

    def link_parent(self, child: TrackedItem, parent: TrackedItem) -> None:
        """Refuses — GitHub has no native parent/epic link.

        Spec §4.G: "GitHub is the tracker that must synthesize hierarchy
        from links [or task lists]." That synthesis is real, unbuilt work
        — a `NotImplementedError` says so honestly rather than silently
        no-op'ing and pretending the link was recorded.
        """
        raise NotImplementedError(
            f"GithubTracker.link_parent({child.id!r}, {parent.id!r}): GitHub has no "
            "native parent link; hierarchy must be synthesized (task lists, "
            "cross-references), which this phase does not build."
        )
