"""`HerdrRunner` — run-unit work in a herdr tab (spec 2026-09-25-triage-batches §3.C).

A batch is launched as one interactive `/fr-goal` or `/fr-debugging` session,
by the batch's skill (spec 2026-09-27-triage-batch-launch §B): a new tab
labelled with the item id, the harness started in its root pane with the
batch's model, and the engine-rendered brief submitted as the first prompt. fr
makes no model call and does not wait on the run; `dispatch` returns once the
prompt is in.

- **One subprocess seam.** Every herdr call goes through `_run_herdr`, which
  parses herdr's JSON envelope and raises `HerdrError` on failure; tests
  replace it.
- **One harness table.** `HARNESSES` maps a harness to herdr's agent kind and
  the argv that selects a model. Only `claude` is verified; others are added
  as they are verified live.
- **Identity.** The tab label is the full item id (`<repo>/run/batch-<id>`,
  unique across repos), so `existing_dispatches` matches live tabs by label.
  The agent name only has to satisfy herdr's `[a-z][a-z0-9_-]{0,31}`:
  `b-<first 20 chars of the batch id>-<4 hex of sha1(item id)>`.
- **Groups.** An item whose payload carries `group` is opened in the herdr
  workspace of that label (created, with the tab renamed to the item id, when
  none exists); an item without one goes to the runner's own workspace.
  Because a group's workspace is not the runner's, `existing_dispatches` lists
  the tabs of EVERY workspace and matches the item id wherever it is.
- **Inside herdr only.** `preflight` refuses unless `HERDR_ENV=1` and `herdr`
  is on PATH: herdr's own rule is never to drive a session from outside it.

`fr_herdr` never imports `fr.triage`, and `fr` never imports `fr_herdr`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from fr_dispatch.work_item import WorkItem


class HerdrError(Exception):
    """A herdr CLI call failed; the message carries herdr's own words."""


@dataclass(frozen=True)
class Harness:
    kind: str  # herdr `agent start --kind`
    model_flag: str  # the harness CLI flag that selects a model

    def model_args(self, model: str) -> list[str]:
        return [self.model_flag, model]


HARNESSES: dict[str, Harness] = {
    "claude": Harness(kind="claude", model_flag="--model"),
}

_NAME_UNSAFE = re.compile(r"[^a-z0-9_-]")


def _run_herdr(args: list[str]) -> dict[str, Any]:
    """Run `herdr <args>` and return its parsed JSON (`{}` for empty output)."""
    try:
        done = subprocess.run(["herdr", *args], capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise HerdrError("herdr is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or f"exit {exc.returncode}"
        raise HerdrError(f"herdr {' '.join(args[:2])} failed: {detail}") from exc
    out = done.stdout.strip()
    if not out:
        return {}
    try:
        parsed: dict[str, Any] = json.loads(out)
    except ValueError:
        return {"raw": out}
    return parsed


def agent_name(item_id: str) -> str:
    """herdr agent name for *item_id*: `b-<20 chars of batch id>-<4 hex>`."""
    run_id = item_id.rsplit("/", 1)[-1]
    batch_id = run_id.removeprefix("batch-")
    stem = _NAME_UNSAFE.sub("-", batch_id.lower())[:20]
    digest = hashlib.sha1(item_id.encode("utf-8")).hexdigest()[:4]
    return f"b-{stem}-{digest}"


class HerdrRunner:
    """The herdr runner: takes `unit="run"` items for a harness in `HARNESSES`."""

    name = "herdr"
    capabilities: frozenset[str] = frozenset({"git", "tests", "scm", "devcontainer"})
    units: frozenset[str] = frozenset({"run"})

    def __init__(self, workspace_id: str | None = None) -> None:
        self.workspace_id = workspace_id

    @classmethod
    def from_env(cls) -> HerdrRunner:
        """Built from the environment alone (`fr_dispatch.registry.load_runner`)."""
        return cls(workspace_id=os.environ.get("HERDR_WORKSPACE_ID") or None)

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        if shutil.which("herdr") is None:
            return "herdr is not on PATH"
        if os.environ.get("HERDR_ENV") != "1":
            return (
                "not inside a herdr session (HERDR_ENV=1 is unset): herdr is never "
                "driven from outside it"
            )
        if not self.workspace_id and any(not i.payload.get("group") for i in items):
            return "HERDR_WORKSPACE_ID is unset, so there is no workspace to open a tab in"
        return None

    def refresh(self) -> None:
        return None  # no cache

    def slot_budget(self) -> int:
        # Batch dispatch sends one item per invocation and never consults this;
        # it exists for `tick` compatibility.
        return 1

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]:
        listing = _run_herdr(["tab", "list"])
        labels = {t.get("label") for t in listing.get("result", {}).get("tabs", [])}
        return {item.id for item in items if item.id in labels}

    def can_dispatch(self, item: WorkItem) -> bool:
        return item.unit in self.units and item.payload.get("harness") in HARNESSES

    def dispatch(self, item: WorkItem) -> str:
        """Open the tab, start the harness with the model, submit the brief.

        Returns the root pane id as the handle. Each step raises `HerdrError`
        on failure, and nothing later runs. A failure after the tab exists
        closes it before re-raising (review r2p-f9): a labelled tab left behind
        would read as a live dispatch to `existing_dispatches` forever.
        """
        payload = item.payload
        harness = HARNESSES[str(payload["harness"])]
        checkout = str(payload.get("checkout") or os.getcwd())
        pane, cleanup = self._open_tab(item, checkout)
        try:
            name = agent_name(item.id)
            _run_herdr(
                [
                    "agent",
                    "start",
                    name,
                    "--kind",
                    harness.kind,
                    "--pane",
                    pane,
                    "--",
                    *harness.model_args(str(payload["model"])),
                ]
            )
            _run_herdr(["agent", "prompt", name, str(payload["brief"])])
        except BaseException:
            cleanup()
            raise
        return pane

    def _open_tab(self, item: WorkItem, checkout: str) -> tuple[str, Callable[[], None]]:
        """Open the item's tab: `(root pane id, cleanup to undo what this opened)`."""
        group = item.payload.get("group")
        if group:
            workspace = _group_workspace(str(group))
            if workspace is None:
                return self._create_group_workspace(item, str(group), checkout)
        else:
            workspace = str(self.workspace_id)
        created = _run_herdr(
            [
                "tab",
                "create",
                "--workspace",
                workspace,
                "--cwd",
                checkout,
                "--label",
                item.id,
                "--no-focus",
            ]
        )
        tab = _created_tab_id(created)
        try:
            return _root_pane(created, "tab create"), lambda: _close_tab(tab)
        except HerdrError:
            _close_tab(tab)
            raise

    def _create_group_workspace(
        self, item: WorkItem, group: str, checkout: str
    ) -> tuple[str, Callable[[], None]]:
        """Create the group's workspace; its first tab is renamed to the item id."""
        created = _run_herdr(
            ["workspace", "create", "--label", group, "--cwd", checkout, "--no-focus"]
        )
        result = created.get("result")
        workspace = None
        if isinstance(result, dict):
            holder = result.get("workspace")
            if isinstance(holder, dict) and holder.get("workspace_id"):
                workspace = str(holder["workspace_id"])

        def cleanup() -> None:
            _close_workspace(workspace)

        try:
            pane = _root_pane(created, "workspace create")
            tab = _created_tab_id(created)
            if tab is None:
                raise HerdrError(f"herdr workspace create returned no tab: {created!r}")
            _run_herdr(["tab", "rename", tab, item.id])
        except BaseException:
            cleanup()
            raise
        return pane, cleanup


def _root_pane(created: dict[str, Any], what: str) -> str:
    try:
        return str(created["result"]["root_pane"]["pane_id"])
    except (KeyError, TypeError) as exc:
        raise HerdrError(f"herdr {what} returned no root pane: {created!r}") from exc


def _group_workspace(label: str) -> str | None:
    """The id of the first workspace labelled *label*, if any."""
    listing = _run_herdr(["workspace", "list"])
    result = listing.get("result")
    workspaces = result.get("workspaces", []) if isinstance(result, dict) else []
    for ws in workspaces:
        if isinstance(ws, dict) and ws.get("label") == label and ws.get("workspace_id"):
            return str(ws["workspace_id"])
    return None


def _created_tab_id(created: dict[str, Any]) -> str | None:
    """The id of the tab `herdr tab create` opened, from `.result.tab` or the root pane."""
    result = created.get("result")
    if not isinstance(result, dict):
        return None
    for holder in (result.get("tab"), result.get("root_pane")):
        if isinstance(holder, dict) and holder.get("tab_id"):
            return str(holder["tab_id"])
    return None


def _close_tab(tab: str | None) -> None:
    """Best-effort close of a tab this dispatch opened; never masks the real error."""
    if tab is None:
        return
    try:
        _run_herdr(["tab", "close", tab])
    except HerdrError:
        pass


def _close_workspace(workspace: str | None) -> None:
    """Best-effort close of a workspace this dispatch created."""
    if workspace is None:
        return
    try:
        _run_herdr(["workspace", "close", workspace])
    except HerdrError:
        pass


if TYPE_CHECKING:
    from fr_dispatch.protocols import Runner

    # Conformance check: `Runner` is not runtime-checkable, so this assignment is
    # what makes CI's mypy fail when a signature here drifts from the protocol.
    _conforms: Runner = HerdrRunner()
