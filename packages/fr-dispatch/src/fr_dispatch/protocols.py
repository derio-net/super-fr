"""Public runner contract — the fr-dispatch / adapter seam.

A *runner* is whatever consumes queued work items and executes them:
VibeKanban (`fr_vk.VkRunner`, the first implementation), the cncd control
plane (`fr_cncd.CncdRunner`), a future GitHub-Actions runner, a headless
agent daemon. `fr_dispatch.tick` orchestrates the queue against this
Protocol and nothing else — no adapter types, no board vocabulary, no VK
strings (2026-06-05 super-fr split design, §Runner registry; promoted from
the duck-typed MCP seam the bridge tests already used).

**v2 (2026-08-14 workflow-shapes-and-workitem-dispatch spec §4.D).** The
unit of dispatch is a `WorkItem`, not a `(plan, phase, repo, issue_number)`
tuple: the decomposition granularity (`run` | `phase` | `spec`, §4.E) is
now a workflow shape's declared `unit`, not a hardcoded assumption. Six
methods, down from seven — `dedup_key` is gone because identity lives on
the item (`WorkItem.id`), so `existing_dispatches(items)` returns item ids
and `can_dispatch_repo(repo)` widens to `can_dispatch(item)`. Hard cutover,
no compatibility shim.

Implementations are duck-typed (`Protocol`): no inheritance required.
Every method may raise — `tick` accumulates failures per item and never
lets one bad call kill the loop (apply's doctrine).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from fr_dispatch.work_item import WorkItem


class Runner(Protocol):
    """One dispatch backend, as seen by `fr_dispatch.tick`."""

    name: str
    """Registry name (`runner:<name>` label value; e.g. ``vk``)."""

    capabilities: frozenset[str]
    """What this backend can provide (§4.F).

    Drawn from the closed capability set (`git`, `tests`, `scm`, `browser`,
    `network`, `devcontainer`). A workflow shape declares `requires`; the
    mismatch is refused in `preflight`, which is why that method receives
    the items. The *negotiation* itself is not implemented here — declaring
    the attribute is.
    """

    units: frozenset[str]
    """The decomposition units this backend takes (`run` | `phase` | `spec`).

    A CLASS attribute, readable without building the runner: `fr apply --to`
    reads it off the registered class (`registry.runner_units`) and refuses a
    runner that takes no phases before it touches the forge (super-fr#644),
    because vk and cncd cannot be built outside their bridge. `can_dispatch`
    still makes the per-item decision and must refuse any unit not named
    here; `tick` reports that refusal as the unit, not as a repo problem.
    """

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        """Config/capability check before any dispatch this tick.

        Return an error string (every eligible item fails cleanly with it,
        and none is dispatched) or None when ready. Examples: the VK runner
        requires a project id outside workspace contexts; a shape requiring
        `browser` on a headless runner is refused here rather than dying
        mid-flight (§4.F).
        """
        ...

    def refresh(self) -> None:
        """Per-tick cache reset so config drift propagates."""
        ...

    def slot_budget(self) -> int:
        """Remaining dispatch capacity for this tick (0 = defer all)."""
        ...

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]:
        """Dedup snapshot: which of `items` this runner is already holding.

        Item ids, not backend-native keys — identity is the item's position
        in the graph (`work_item.item_id`), computable before any tracker
        artifact exists. An adapter whose board stores something else (a VK
        card title, say) maps back to ids here; the title stays that
        backend's *presentation* of an item and stops being its identity.

        `items` is the same sequence `preflight` receives. An adapter that
        has to invert board state into ids needs the candidate items to
        invert *against*, and passing them is what keeps that from becoming
        an undocumented "call `preflight` first" ordering contract — one
        whose failure mode (an empty snapshot) is silent duplicate
        dispatch. Returning ids outside `items` is harmless: `tick` only
        tests membership for the items it is about to dispatch.
        """
        ...

    def can_dispatch(self, item: WorkItem) -> bool:
        """Routing gate — refuse early when this backend can't take `item`.

        Replaces `can_dispatch_repo(repo)`: the repo is still the usual
        reason to refuse (`item.repo`), but the item carries its unit,
        workflow and payload too, so a runner that only handles some units
        can say so without a second protocol method.
        """
        ...

    def dispatch(self, item: WorkItem) -> str | None:
        """Hand one item to the backend (create card/job/workspace…).

        Raising marks the item failed for this tick; the dispatch stamp is
        NOT written, so the next tick retries. May return an opaque handle
        for the dispatched work (herdr returns the pane id; spec
        2026-09-25-triage-batches §3.C records it in the batch's dispatch
        event); `tick` ignores it, and a runner with none returns None.
        """
        ...


CloseOutcome = Literal["closed", "busy", "absent"]
"""What `SessionCloser.close` did: sessions gone, still working, or none held."""


@runtime_checkable
class SessionCloser(Protocol):
    """An optional second protocol: a runner that can close what it dispatched.

    Beside `Runner`, never part of it, so a runner without live sessions (vk,
    cncd) needs no edit. `closed`: the item's sessions are gone now. `busy`:
    at least one is still working; nothing was closed. `absent`: the runner
    holds nothing for the item. Raising is a failed close.
    """

    def close(self, item: WorkItem) -> CloseOutcome:
        """Close the item's sessions, unless one is still working."""
        ...


SessionStatus = Literal["working", "blocked", "idle", "done", "unknown", "absent"]
"""One item's live session state: `absent` when the runner holds none."""


@runtime_checkable
class SessionInspector(Protocol):
    """An optional protocol beside `Runner`, never part of it: report session state.

    One read for all *items* (a runner lists its sessions once); every item
    is a key of the result. A session in several parts reports the most urgent
    one. Raising is a failed read.
    """

    def session_statuses(self, items: Sequence[WorkItem]) -> dict[str, SessionStatus]:
        """Each item's id mapped to its session's status (`absent` when none)."""
        ...


@runtime_checkable
class SessionNotes(Protocol):
    """An optional protocol beside `Runner`, never part of it: why a session is blocked
    (spec 2026-10-07-cloud-triage R15). `SessionStatus` stays the closed six-value
    Literal; a runner whose sessions say what they need (a cloud session's
    `needs_action`) reports it here, and the board and Needs-you-now show it."""

    def session_notes(self, items: Sequence[WorkItem]) -> dict[str, str]:
        """Each blocked item's note, by item id; an item with none is left out."""
        ...


@runtime_checkable
class SessionFocuser(Protocol):
    """An optional protocol beside `Runner`, never part of it: bring a session forward."""

    def focus(self, item: WorkItem) -> bool:
        """Focus the item's session; False when there is none. Raising is a failed focus."""
        ...


@runtime_checkable
class SessionMessenger(Protocol):
    """An optional protocol beside `Runner`, never part of it and never a capability:
    send text to a session the runner dispatched (spec 2026-10-06-verification-
    strategies §G, R23). The wave driver hands a merge conflict back through it, and
    only to an `idle` session; a runner without it always gets a fresh session."""

    def message(self, item: WorkItem, text: str) -> None:
        """Submit *text* to the item's session as a prompt. Raising is a failed send."""
        ...


@dataclass(frozen=True)
class RestartSummary:
    """What `SessionRestarter.restart_idle` did: sessions restarted, left alone, and the
    (pane, reason) of each that failed."""

    ok: int
    skipped: int
    failed: tuple[tuple[str, str], ...] = ()


@runtime_checkable
class SessionRestarter(Protocol):
    """An optional protocol beside `Runner`, never part of it: restart the runner's idle
    sessions so they load what a merge installed (spec 2026-10-06-driver-sessions §B).
    The wave driver calls it once per pass; *exclude* names panes never to touch."""

    def restart_idle(self, *, exclude: Sequence[str] = ()) -> RestartSummary:
        """Restart every idle session. Raising is a failed restart."""


@dataclass(frozen=True)
class AdoptTarget:
    """One live session a runner could adopt (spec 2026-10-06-triage-batch-adopt §E).

    *label* is the runner's raw label: parsing issue refs out of it is triage
    vocabulary and lives in `fr.triage`. *agent* is the session's single agent,
    None when it has none or several; *group* the label of what holds it.
    """

    tab: str
    label: str
    group: str | None
    agent: str | None
    status: str


@runtime_checkable
class SessionAdopter(Protocol):
    """An optional protocol beside `Runner`, never part of it: put a session the
    runner did not launch under an item's identity (`fr triage batch adopt`).

    `adopt` relabels the session and its agent as the runner's own dispatch of
    *item* would have, and returns the handle; already adopted, it changes
    nothing and returns the same handle. Raising is a failed adoption.
    """

    def describe(self, tab: str) -> AdoptTarget | None:
        """The session *tab*, or None when the runner has no such session."""
        ...

    def list_sessions(self) -> list[AdoptTarget]:
        """Every session the runner can see, one read."""
        ...

    def adopt(self, item: WorkItem, tab: str) -> str:
        """Label *tab* and its agent as *item*'s session; return the handle."""
        ...


class Source(Protocol):
    """Where `WorkItem`s come from — the seam the future poller consumes
    (spec §4.H, guides part (b) of the brainstorm). **Nothing is extracted
    in this phase**; this Protocol exists solely so that extraction, when
    it happens, is mechanical rather than a redesign.

    `discover_plans` (this module) is `Source`'s first intended
    implementation, once (b) extracts it into a `PlansSource`. A Jira
    query becomes another; a run-state watcher (watching branches, or
    being handed runs explicitly) becomes a third — see spec §4.H for why
    that third one is where the "in-flight runs not on main" cost noted in
    §4.B eventually gets paid.

    The one standing obligation this Protocol's existence creates: `tick`
    must never acquire a new coupling to `discover_plans` specifically —
    pinned by `tests/unit/test_tripwire_tick_source_neutral.py`, not left
    as a promise. `tick` already takes a `Plan | SpecMeta | None` directly;
    a `Source` is what will one day hand it that value, not something
    `tick` reaches for itself.
    """

    name: str
    """Registry name for this source (mirrors `Runner.name`)."""

    def discover(self) -> Iterable[WorkItem]:
        """Yield the work items this source currently knows about."""
        ...
