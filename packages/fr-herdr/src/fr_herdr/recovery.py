"""Absent-source mode of the optional replacement operation, not initial dispatch.

Global captured pane/tab joins include shells. Unknown reads never mean absence.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from fr.artifacts.atomic import write_text_atomic
from fr.git import git_answer
from fr_dispatch.protocols import ReplacementInspection, ReplacementRequest, ReplacementResult
from pydantic import BaseModel, ConfigDict

from fr_herdr import managed, replacement
from fr_herdr._herdr import _run_herdr
from fr_herdr.runner import agent_name, stable_checkout


def roster(kind: str, required: tuple[str, ...]) -> list[dict[str, Any]]:
    response = _run_herdr([kind, "list"])
    result = response.get("result")
    rows = result.get(kind + "s") if isinstance(result, dict) else None
    if not isinstance(rows, list) or any(
        not isinstance(row, dict)
        or any(not isinstance(row.get(key), str) or not row[key] for key in required)
        for row in rows
    ):
        raise managed.ManagedError(f"unknown {kind} roster")
    identity = required[0]
    if len({row[identity] for row in rows}) != len(rows):
        raise managed.ManagedError(f"ambiguous {kind} roster")
    return rows


def observations() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    panes = roster("pane", ("pane_id", "tab_id", "workspace_id"))
    tabs = roster("tab", ("tab_id", "workspace_id"))
    agents = roster("agent", ("pane_id", "tab_id"))
    by_tab = {tab["tab_id"]: tab for tab in tabs}
    by_pane = {pane["pane_id"]: pane for pane in panes}
    if (
        any(
            pane["tab_id"] not in by_tab
            or pane["workspace_id"] != by_tab[pane["tab_id"]]["workspace_id"]
            for pane in panes
        )
        or any(
            not isinstance(tab.get("label"), str)
            or type(tab.get("pane_count")) is not int
            or tab["pane_count"] < 1
            or sum(pane["tab_id"] == tab["tab_id"] for pane in panes) != tab["pane_count"]
            for tab in tabs
        )
        or any(
            agent["pane_id"] not in by_pane
            or agent["tab_id"] != by_pane[agent["pane_id"]]["tab_id"]
            for agent in agents
        )
    ):
        raise managed.ManagedError("incomplete/changed global roster join; inspect and retry")
    return panes, tabs, agents


def absent(request: ReplacementRequest) -> None:
    if request.pane == os.environ.get("HERDR_PANE_ID"):
        raise managed.ManagedError("caller-self session")
    panes, tabs, agents = observations()
    if any(p["pane_id"] == request.pane for p in panes):
        raise managed.ManagedError("source pane survives or was reused")
    if any(t["label"] in {request.item, request.name} for t in tabs) or any(
        a.get("name") == request.name for a in agents
    ):
        raise managed.ManagedError("item/name survives; source is not positively absent")


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    server: str
    request: ReplacementRequest
    checkpoint: Literal["allocation-pending", "allocated", "active", "aborted"] = (
        "allocation-pending"
    )
    target: managed.Descriptor | None = None


def intent_path(item: str, pane: str) -> Path:
    key = hashlib.sha256(f"{managed.server_identity()}\0{item}\0{pane}".encode()).hexdigest()
    return managed.cache_dir() / f"{key}.recovery.json"


def save_intent(intent: Intent) -> None:
    path = intent_path(intent.request.item, intent.request.pane)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, intent.model_dump_json(indent=2) + "\n")


def load_intent(item: str, pane: str) -> Intent | None:
    path = intent_path(item, pane)
    try:
        intent = Intent.model_validate_json(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise managed.ManagedError(f"unreadable recovery intent {path}") from exc
    if intent.server != managed.server_identity() or (intent.request.item, intent.request.pane) != (
        item,
        pane,
    ):
        raise managed.ManagedError("recovery intent identity mismatch")
    return intent


def pending(item: str, pane: str) -> ReplacementRequest | None:
    intent = load_intent(item, pane)
    if not intent or intent.checkpoint in {"active", "aborted"}:
        return None
    return replace(intent.request, target_pane=intent.target.pane if intent.target else None)


class Operation(replacement.Operation):
    def __init__(self, request: ReplacementRequest):
        super().__init__(request)
        if (
            not request.recover
            or request.harness != "opencode"
            or self.name != agent_name(request.item)
        ):
            raise managed.ManagedError(
                "recovery requires explicit OpenCode and canonical item identity"
            )
        # Resolve the stable primary checkout; never create another workspace.
        stable_checkout(request.checkout)
        self.target = self.target.model_copy(
            update={"recovery_hold": True, "source_pane": request.pane}
        )
        self.stack: ExitStack | None = None
        self.locked_target: str | None = None

    @property
    def target_pane(self) -> str | None:
        return self.target.pane if self.target.pane != self.request.pane else None

    @property
    def failure_context(self) -> str:
        try:
            intent = load_intent(self.request.item, self.request.pane)
            target = self.target_pane or (intent.target.pane if intent and intent.target else None)
            checkpoint = (
                self.target.checkpoint
                if target
                else intent.checkpoint
                if intent
                else "before-intent"
            )
            where = target or "uncertain allocation: discover labelled pane roster"
            return f"checkpoint {checkpoint}; source {self.request.pane}; target {where}"
        except (managed.ManagedError, OSError):
            return "unreadable recovery intent; inspect both stores; never allocate/replay"

    @contextmanager
    def ownership(self) -> Iterator[None]:
        with ExitStack() as stack:
            stack.enter_context(managed.pane_lock(self.request.pane))
            self.stack, self.owned = stack, True
            try:
                yield
            finally:
                self.stack, self.owned, self.locked_target = None, False, None

    def _lock_target(self) -> None:
        if self.owned and self.locked_target != self.target.pane:
            assert self.stack is not None
            self.stack.enter_context(managed.pane_lock(self.target.pane))
            self.locked_target = self.target.pane

    def inspect(self) -> ReplacementInspection:
        if pending(self.request.item, self.request.pane):
            raise managed.ManagedError("pending recovery; explicit repair owed")
        previous = managed.load(self.request.pane)
        if previous and previous.checkpoint not in {"active", "aborted"}:
            raise managed.ManagedError("pending source operation; explicit repair owed")
        if previous and any(
            getattr(previous, key) != getattr(self.source, key)
            for key in ("item", "name", "branch", "checkout", "harness", "model")
        ):
            raise managed.ManagedError("source descriptor identity mismatch")
        absent(self.request)
        workspace, _ = managed.recovery_cursor(self.target)
        status = git_answer(workspace, "status", "--porcelain")
        if status.returncode:
            raise managed.ManagedError("existing workspace status is unreadable")
        self.workspace = str(workspace)
        self.dirty = bool(status.stdout.strip())
        if not os.environ.get("HERDR_WORKSPACE_ID"):
            raise managed.ManagedError("HERDR_WORKSPACE_ID is missing")
        return ReplacementInspection(
            self.request.pane, self.name, self.request.old_harness, self.request.old_model, "absent"
        )

    def prepare(self) -> None:
        self._owner()
        self.inspect()  # Fresh absent-source and cursor recheck under both scope/source ownership.
        self.brief = managed.reconstruct(self.target)
        previous = load_intent(self.request.item, self.request.pane)
        if previous:
            path = intent_path(self.request.item, self.request.pane)
            write_text_atomic(
                path.with_suffix(f".{previous.request.attempt}.history"),
                previous.model_dump_json(indent=2) + "\n",
            )
        # The only pre-allocation durable point: loss of a response cannot authorize replay.
        intent = Intent(server=managed.server_identity(), request=self.request)
        save_intent(intent)
        created = _run_herdr(
            [
                "tab",
                "create",
                "--workspace",
                str(os.environ["HERDR_WORKSPACE_ID"]),
                "--cwd",
                self.target.checkout,
                "--label",
                self.request.item,
                "--no-focus",
            ]
        )
        result = created.get("result", {})
        root = result.get("root_pane") if isinstance(result, dict) else None
        if (
            not isinstance(root, dict)
            or not isinstance(root.get("pane_id"), str)
            or not root["pane_id"]
        ):
            raise managed.ManagedError(
                "allocation response unknown; discover via --repair, NEVER allocate again"
            )
        self.target = self.target.model_copy(update={"pane": root["pane_id"]})
        # Persist actual ownership even if the first pane descriptor write fails.
        save_intent(intent.model_copy(update={"checkpoint": "allocated", "target": self.target}))
        self._lock_target()
        self._discover()
        managed.save(self.target)

    def _intent(self) -> Intent:
        intent = load_intent(self.request.item, self.request.pane)
        if not intent or any(
            getattr(intent.request, key) != getattr(self.request, key)
            for key in (
                "attempt",
                "item",
                "pane",
                "name",
                "branch",
                "checkout",
                "harness",
                "model",
                "old_harness",
                "old_model",
            )
        ):
            raise managed.ManagedError("pending recovery identity mismatch; inspect both stores")
        return intent

    def _discover(self) -> bool:
        """Observe the same allocation, never allocate/launch/submit to find it."""
        intent = self._intent()
        panes, tabs, agents = observations()
        if any(p["pane_id"] == self.request.pane for p in panes):
            raise managed.ManagedError("original pane survives/reused; inspect both stores")
        matches = [t for t in tabs if t["label"] == self.request.item]
        if not matches:
            if intent.target or any(a.get("name") == self.name for a in agents):
                raise managed.ManagedError(
                    "recorded target disappeared or item name survived; inspect"
                )
            return False
        targets = [p for p in panes if p["tab_id"] in {t["tab_id"] for t in matches}]
        if len(matches) != 1 or len(targets) != 1:
            raise managed.ManagedError("ambiguous allocated item pane; never allocate again")
        pane = targets[0]["pane_id"]
        if pane == os.environ.get("HERDR_PANE_ID") or any(
            a.get("name") == self.name and a["pane_id"] != pane for a in agents
        ):
            raise managed.ManagedError("caller-self or ambiguous target identity")
        if (
            intent.target
            and intent.target.pane != pane
            or self.request.target_pane
            and self.request.target_pane != pane
        ):
            raise managed.ManagedError("allocated pane identity changed")
        target = intent.target or self.target.model_copy(update={"pane": pane})
        self.target = target
        self._lock_target()
        stored = managed.load(pane)
        if stored:
            if any(
                getattr(stored, key) != getattr(target, key)
                for key in (
                    "item",
                    "name",
                    "attempt",
                    "branch",
                    "checkout",
                    "harness",
                    "model",
                    "source_pane",
                    "recovery_hold",
                )
            ):
                raise managed.ManagedError("target descriptor identity mismatch")
            self.target = stored
        if self.owned and intent.target is None:
            save_intent(
                intent.model_copy(update={"checkpoint": "allocated", "target": self.target})
            )
            if stored is None:
                managed.save(self.target)
        return True

    def _target_identity(self) -> None:
        agent = replacement.observe(self.target, safe=False)
        session = agent.get("agent_session")
        value = (
            session.get("value")
            if isinstance(session, dict)
            and session.get("agent") == "opencode"
            and session.get("kind") == "id"
            else None
        )
        if (
            not isinstance(value, str)
            or not value
            or self.target.session
            and self.target.session != value
        ):
            raise managed.ManagedError("fresh harness session identity missing/changed")
        source = managed.load(self.request.pane)
        if source and source.session == value:
            raise managed.ManagedError("target reused source harness session identity")
        self.target = self.target.model_copy(update={"session": value})

    def execute(self) -> ReplacementResult:
        self._owner()
        self._discover()
        d = self._pending()
        if d.checkpoint != "prepared":
            raise managed.ManagedError("recovery already started; repair, NEVER replay")
        try:
            self._checkpoint("launch-started")
            return self._target_execution()
        except Exception as exc:
            return ReplacementResult(
                False,
                self.target.checkpoint,
                "unknown",
                f"{exc}; inspect pane {self.target.pane}; --repair owed; NEVER replay",
                pane=self.target.pane,
                session=self.target.session,
            )

    def reconcile(self) -> ReplacementResult:
        if not self._discover():
            return ReplacementResult(
                False,
                "allocation-pending",
                "absent",
                "confirmed absent allocation; abort, then new explicit recovery required",
            )
        try:
            self._target_identity()
        except managed.ManagedError:
            if replacement.confirmed_shell(self.target):
                return ReplacementResult(
                    False,
                    self.target.checkpoint,
                    "shell",
                    "confirmed shell; abort, no launch/input",
                    pane=self.target.pane,
                )
            raise
        stored = managed.load(self.target.pane)
        if (
            self.target.checkpoint not in {"uptake-confirmed", "batch-committed", "active"}
            or not stored
            or not stored.session
        ):
            raise managed.ManagedError(
                "no persisted uptake/session confirmation; NEVER replay brief"
            )
        return ReplacementResult(
            True,
            self.target.checkpoint,
            "target",
            pane=self.target.pane,
            session=self.target.session,
        )

    def activate(self, *, success: bool) -> None:
        self._owner()
        result = self.reconcile()
        if result.ok != success:
            raise managed.ManagedError("live recovery truth disagrees with batch outcome")
        if self.target_pane:
            if success:
                self._checkpoint("batch-committed")
                self._checkpoint("active")
            else:
                self._checkpoint("aborted")
        intent = self._intent()
        save_intent(
            intent.model_copy(
                update={
                    "checkpoint": "active" if success else "aborted",
                    "target": self.target if self.target_pane else None,
                }
            )
        )
