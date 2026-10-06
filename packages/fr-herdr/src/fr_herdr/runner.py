"""`HerdrRunner` — run-unit work in a herdr tab (spec 2026-09-25-triage-batches §3.C).

A batch is launched as one interactive `/fr-goal` or `/fr-debugging` session,
by the batch's skill (spec 2026-09-27-triage-batch-launch §B): a new tab
labelled with the item id, the harness started in its root pane with the
batch's model, and the engine-rendered brief submitted as the first prompt. fr
makes no model call and does not wait on the run; `dispatch` returns once the
agent has taken the prompt up (it left `idle`), not merely once it was typed.

- **Confirmed handoffs** (gh#931, gh#956). A new tab's shell may still be
  starting, so `agent start` retries herdr's `agent_pane_busy` a bounded number
  of times. The brief is submitted with `agent prompt --wait --until working
  --until blocked`; on herdr's `agent_prompt_stalled` the runner presses Enter
  once (never re-sends the brief, which may already sit in the input box) and
  waits again, then fails the dispatch loudly rather than report a session that
  never started.

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
- **Session state and focus.** `session_statuses` reads one `tab list` for
  all items and reports a session's most urgent tab (`blocked` > `working` >
  `idle` > `done`; a value herdr adds later is `unknown`; no tab is `absent`);
  `focus` selects the item's workspace, then its tab (`workspace focus`, `tab
  focus`), and is False when there is no tab.
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
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from fr_dispatch.protocols import CloseOutcome, SessionStatus
    from fr_dispatch.work_item import WorkItem


class HerdrError(Exception):
    """A herdr CLI call failed; the message carries herdr's own words, and *code* the
    `.error.code` of herdr's JSON envelope when it printed one."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


PANE_BUSY_TRIES = 15
"""`agent start` attempts against a pane whose shell is not up yet (`agent_pane_busy`)."""
PANE_BUSY_WAIT = 2.0
"""Seconds between them: 28s in all, for rc files and a slow prompt."""
PROMPT_TIMEOUT_MS = 30000
"""How long `agent prompt --wait` may take to see the agent leave `idle`."""
ENTER_TIMEOUT_MS = 10000
"""How long the agent may take to start once Enter re-submits a stalled brief."""
_STARTED = ("--until", "working", "--until", "blocked")
"""The states that prove a turn began: never the default `--wait`, which waits for
the turn to settle, i.e. for the whole run."""

_sleep = time.sleep


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
        raise HerdrError(
            f"herdr {' '.join(args[:2])} failed: {detail}", code=_error_code(detail)
        ) from exc
    out = done.stdout.strip()
    if not out:
        return {}
    try:
        parsed: dict[str, Any] = json.loads(out)
    except ValueError:
        return {"raw": out}
    return parsed


def _error_code(detail: str) -> str | None:
    """`.error.code` of herdr's JSON error envelope, if *detail* is one."""
    try:
        envelope = json.loads(detail)
    except ValueError:
        return None
    error = envelope.get("error") if isinstance(envelope, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return str(code) if code is not None else None


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
        labels = {t.get("label") for t in _list_tabs()}
        return {item.id for item in items if item.id in labels}

    def close(self, item: WorkItem) -> CloseOutcome:
        """Close the item's tabs, unless one is working or blocked (spec §B; R8, R9).

        A lone tab is closed by closing its workspace only when that
        workspace's label is the item's group and it is not this runner's own
        workspace; every other tab goes with `tab close`.
        """
        tabs = _list_tabs()
        mine = _tabs_labelled(tabs, item.id)
        if not mine:
            return "absent"
        if any(t.get("agent_status") in _BUSY for t in mine):
            return "busy"
        group = item.payload.get("group")
        for tab in mine:
            workspace = tab.get("workspace_id")
            lone = sum(1 for t in tabs if t.get("workspace_id") == workspace) == 1
            if (
                group
                and lone
                and workspace
                and workspace != self.workspace_id
                and _workspace_label(str(workspace)) == group
            ):
                _run_herdr(["workspace", "close", str(workspace)])
            else:
                _run_herdr(["tab", "close", str(tab["tab_id"])])
        return "closed"

    def session_statuses(self, items: Sequence[WorkItem]) -> dict[str, SessionStatus]:
        """Each item's most urgent tab status, from one `tab list` (spec §B; R9)."""
        tabs = _list_tabs()
        return {item.id: _status_of(_tabs_labelled(tabs, item.id)) for item in items}

    def focus(self, item: WorkItem) -> bool:
        """Select the item's workspace, then its tab; False when it has no tab (spec §B)."""
        mine = _tabs_labelled(_list_tabs(), item.id)
        if not mine:
            return False
        tab = mine[0]
        _run_herdr(["workspace", "focus", str(tab["workspace_id"])])
        _run_herdr(["tab", "focus", str(tab["tab_id"])])
        return True

    def can_dispatch(self, item: WorkItem) -> bool:
        return item.unit in self.units and item.payload.get("harness") in HARNESSES

    def dispatch(self, item: WorkItem) -> str:
        """Open the tab, start the harness with the model, submit the brief.

        Returns the root pane id as the handle once the agent has left `idle`.
        Each step raises `HerdrError` on failure, and nothing later runs. A
        failure after the tab exists closes it before re-raising (review r2p-f9):
        a labelled tab left behind would read as a live dispatch to
        `existing_dispatches` forever.
        """
        payload = item.payload
        harness = HARNESSES[str(payload["harness"])]
        checkout = str(payload.get("checkout") or os.getcwd())
        pane, cleanup = self._open_tab(item, checkout)
        try:
            name = agent_name(item.id)
            _start_agent(
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
            _submit(name, str(payload["brief"]))
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


def _start_agent(argv: list[str]) -> None:
    """`agent start`, retried while the new tab's shell is not up yet (gh#931).

    herdr needs the pane at its interactive shell prompt and refuses at once with
    `agent_pane_busy` otherwise; any other refusal (`agent_not_ready` is a dialog
    the operator must answer) is raised as it is.
    """
    for attempt in range(1, PANE_BUSY_TRIES + 1):
        try:
            _run_herdr(argv)
            return
        except HerdrError as exc:
            if exc.code != "agent_pane_busy" or attempt == PANE_BUSY_TRIES:
                raise
        _sleep(PANE_BUSY_WAIT)


def _submit(name: str, brief: str) -> None:
    """Submit *brief* and confirm the agent took it up (gh#956).

    Without `--wait`, `agent prompt` reports success once the text and Enter are
    written, so a brief left in the input box read as a started session. On
    `agent_prompt_stalled` the brief may already be there: herdr's guidance is not to
    send it again, so one Enter submits what is there, and a turn must then begin.
    """
    try:
        _run_herdr(["agent", "prompt", name, brief, "--wait", *_STARTED,
                    "--timeout", str(PROMPT_TIMEOUT_MS)])  # fmt: skip
        return
    except HerdrError as exc:
        if exc.code != "agent_prompt_stalled":
            raise
    _run_herdr(["agent", "send-keys", name, "enter"])
    try:
        _run_herdr(["agent", "wait", name, *_STARTED, "--timeout", str(ENTER_TIMEOUT_MS)])
    except HerdrError as exc:
        raise HerdrError(
            f"the brief to agent {name} was not submitted: no turn began after the "
            f"prompt or after Enter ({exc})",
            code=exc.code,
        ) from exc


def _root_pane(created: dict[str, Any], what: str) -> str:
    try:
        return str(created["result"]["root_pane"]["pane_id"])
    except (KeyError, TypeError) as exc:
        raise HerdrError(f"herdr {what} returned no root pane: {created!r}") from exc


_BUSY = frozenset({"working", "blocked"})
"""`agent_status` values that mean a session is mid-work: never closed."""


def _list_tabs() -> list[dict[str, Any]]:
    """Every tab of every workspace (`herdr tab list`, no `--workspace`)."""
    result = _run_herdr(["tab", "list"]).get("result")
    tabs = result.get("tabs", []) if isinstance(result, dict) else []
    return [t for t in tabs if isinstance(t, dict)]


_PRECEDENCE: tuple[SessionStatus, ...] = ("blocked", "working", "idle", "done", "unknown")
"""Most urgent first: what a session in several tabs reports."""


def _tabs_labelled(tabs: list[dict[str, Any]], item_id: str) -> list[dict[str, Any]]:
    return [t for t in tabs if t.get("label") == item_id]


def _status_of(tabs: list[dict[str, Any]]) -> SessionStatus:
    if not tabs:
        return "absent"
    seen = {t.get("agent_status") for t in tabs}
    for status in _PRECEDENCE:
        if status in seen:
            return status
    return "unknown"


def _list_workspaces() -> list[dict[str, Any]]:
    result = _run_herdr(["workspace", "list"]).get("result")
    workspaces = result.get("workspaces", []) if isinstance(result, dict) else []
    return [w for w in workspaces if isinstance(w, dict)]


def _workspace_label(workspace_id: str) -> str | None:
    for ws in _list_workspaces():
        if ws.get("workspace_id") == workspace_id:
            label = ws.get("label")
            return str(label) if label is not None else None
    return None


def _group_workspace(label: str) -> str | None:
    """The id of the first workspace labelled *label*, if any."""
    for ws in _list_workspaces():
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
    from fr_dispatch.protocols import Runner, SessionCloser, SessionFocuser, SessionInspector

    # Conformance check: `Runner` is not runtime-checkable, so this assignment is
    # what makes CI's mypy fail when a signature here drifts from the protocol.
    _conforms: Runner = HerdrRunner()
    _closes: SessionCloser = HerdrRunner()
    _inspects: SessionInspector = HerdrRunner()
    _focuses: SessionFocuser = HerdrRunner()
