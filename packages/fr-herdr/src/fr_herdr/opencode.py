"""Fail-closed OpenCode 1.18.35/default-theme input observation and fresh restart.

Grounding: tests/fixtures/herdr/opencode/README.md. Unknown versions, themes,
overlays or foreground layouts are skipped, never treated as empty input.
"""

from __future__ import annotations

import os
import re
import shlex
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from fr_herdr import managed
from fr_herdr._herdr import HerdrError, _run_herdr, poll, start_agent

_ANSI = re.compile(r"\x1b\[[0-9;:?]*[A-Za-z]")
_FOCUSED = re.compile(r"\x1b\[38;2;92;156;245m(?:\x1b\[[0-9;]*m)*╹")
_clock = time.monotonic
_sleep = time.sleep
TIMEOUT = 30.0


def input_reason(screen: str) -> str | None:
    """Only the FINAL focused, bounded textarea proves empty input (not history)."""
    raw = screen.splitlines()
    lines = [_ANSI.sub("", line).rstrip() for line in raw]
    if not lines:
        return "unknown-layout"
    if any("esc interrupt" in line for line in lines):
        return "background-work"
    borders = [
        (i, match)
        for i, line in enumerate(lines)
        if (match := re.fullmatch(r"(\s*)╹(▀+)(?:\s+(.*))?", line))
    ]
    if not borders:
        return "unknown-layout"
    end, border = borders[-1]
    if not _FOCUSED.search(raw[end]):
        return "dialog-or-unfocused"
    # Footer must be current: a prior transcript box is not evidence of today's input.
    below = [line for line in lines[end + 1 :] if line.strip()]
    if (
        not below
        or not re.search(r"(?:^|\s)1\.18\.35\s*$", below[-1])
        or not any("ctrl+p commands" in line for line in below)
    ):
        return "unknown-layout"
    # Captured wide-session sidebar text can share the closing-border row. It is
    # outside the textarea, but only the captured wide-session footer permits it.
    if border.group(3) and not re.search(r"• OpenCode 1\.18\.35\s*$", below[-1]):
        return "unknown-layout"
    x = len(border.group(1))
    width = 1 + len(border.group(2))
    if end < 2 or not re.match(r"^\s*┃  (Build|Plan) · .+", lines[end - 1]):
        return "unknown-layout"
    begin = end - 2
    while begin >= 0 and len(lines[begin]) > x and lines[begin][x] == "┃":
        begin -= 1
    region = lines[begin + 1 : end - 1]
    if not region:
        return "unknown-layout"
    for index, line in enumerate(region, start=begin + 1):
        value = line[x + 1 : x + width].strip()
        if value:
            ghost = re.fullmatch(r'Ask anything… "[^"]*"', value)
            if not ghost or not re.search(
                r'\x1b\[38;2;128;128;128m(?:\x1b\[[0-9;]*m)*Ask anything… "[^"]*"\x1b\[0m',
                raw[index],
            ):
                return "draft"
    # Known blank prompt layout only; arbitrary overlay controls or active spinners
    # fail closed. Completed ✓ task history does NOT mean active background work.
    if re.search(
        r"Commands\s+esc|[\u2800-\u28ff].*Task|permission required|allow once",
        "\n".join(lines),
        re.I,
    ):
        return "unknown-dialog-or-background"
    return None


def process(info: dict[str, Any]) -> dict[str, Any] | None:
    procs = info.get("result", {}).get("process_info", {}).get("foreground_processes", [])
    if len(procs) != 1:
        return None
    proc = procs[0]
    argv = proc.get("argv", [])
    return proc if argv and Path(str(argv[0])).name == "opencode" else None


def launch_args(model: str) -> list[str]:
    """Arguments for an autonomous managed OpenCode session."""
    return ["--model", model, "--auto"]


def model_matches(proc: dict[str, Any], d: managed.Descriptor) -> bool:
    argv = proc.get("argv", [])
    return argv[1:] in (
        ["--model", d.model],
        ["-m", d.model],
        ["--model", d.model, "--auto"],
        ["-m", d.model, "--auto"],
    )


def shell_cwd(info: dict[str, Any]) -> str | None:
    data = info.get("result", {}).get("process_info", {})
    procs = data.get("foreground_processes", [])
    if len(procs) != 1:
        return None
    proc = procs[0]
    executable = Path(str((proc.get("argv") or [""])[0])).name.lstrip("-")
    if (
        proc.get("pid") != data.get("shell_pid")
        or not data.get("shell_pid")
        or executable not in {"zsh", "bash", "fish", "sh"}
    ):
        return None
    return str(proc["cwd"]) if proc.get("cwd") else None


def _fresh(
    pane: str, *, run: Callable[[list[str]], dict[str, Any]] | None = None
) -> dict[str, Any]:
    agents = (run or _run_herdr)(["agent", "list"]).get("result", {}).get("agents", [])
    found = [a for a in agents if a.get("pane_id") == pane]
    if len(found) != 1:
        raise managed.ManagedError("missing or ambiguous live agent")
    agent: dict[str, Any] = found[0]
    return agent


def eligible(
    d: managed.Descriptor,
    exclude: set[str],
    *,
    run: Callable[[list[str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    observe = run or _run_herdr
    if d.checkpoint != "active":
        raise managed.ManagedError(f"unresolved managed checkpoint {d.checkpoint}; repair owed")
    if d.pane == os.environ.get("HERDR_PANE_ID") or d.pane in exclude:
        raise managed.ManagedError("self or excluded")
    agent = _fresh(d.pane, run=observe)
    if (
        agent.get("agent") != "opencode"
        or agent.get("name") != d.name
        or agent.get("agent_status") not in {"idle", "done"}
        or agent.get("interactive_ready") is not True
    ):
        raise managed.ManagedError("live identity/status/readiness mismatch")
    proc = process(observe(["pane", "process-info", "--pane", d.pane]))
    if (
        not proc
        or not proc.get("pid")
        or not model_matches(proc, d)
        or proc.get("cwd") != d.checkout
    ):
        raise managed.ManagedError("foreground process/model is unknown or changed")
    screen = str(observe(["pane", "read", d.pane, "--source", "visible", "--ansi"]).get("raw", ""))
    reason = input_reason(screen)
    if reason:
        raise managed.ManagedError(reason)
    return proc


_T = TypeVar("_T")


def _poll(check: Callable[[], _T | None]) -> _T | None:
    return poll(check, timeout=TIMEOUT, clock=_clock, sleep=_sleep)


def wait_ready(
    d: managed.Descriptor, *, run: Callable[[list[str]], dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Title readiness precedes rendered input. Wait boundedly, before ONE prompt.

    Only unknown startup layout is retried. Drafts/dialogs, status or exact live
    identity/model/cwd mismatches refuse. The active projection is read-only: pending
    durable checkpoints are never promoted before submission/uptake confirmation.
    """
    observation = d.model_copy(update={"checkpoint": "active"})

    def ready() -> dict[str, Any] | None:
        try:
            return eligible(observation, set(), run=run)
        except managed.ManagedError as exc:
            if str(exc) == "unknown-layout":
                return None
            raise

    proc = _poll(ready)
    if proc is None:
        raise HerdrError("rendered-input-timeout; no prompt sent; inspect the target")
    return proc


def restart_pane(pane: str, *, yes: bool, exclude: set[str]) -> tuple[str, str, str | None]:
    """Lock, reobserve, checkpoint, exit to a verified shell, launch fresh, confirm uptake.

    Every uncertain outcome retains a non-active descriptor; subsequent restart skips
    it. Never clears drafts, answers dialogs, closes tabs or resumes a session id.
    """
    try:
        loaded = managed.load(pane)
        if not loaded or loaded.harness != "opencode":
            return "skip", "no managed OpenCode descriptor", None
        d: managed.Descriptor = loaded
        original = eligible(d, exclude)
        brief = managed.reconstruct(d)
        if not yes:
            return "ok", "would restart fresh", None
        with managed.pane_lock(pane):
            if managed.load(pane) != d or eligible(d, exclude) != original:
                return "skip", "identity/process changed before mutation", None
            # Construct recovery before writing/sending anything.
            recovery = (
                f"Inspect {pane} and {d.name}; do not blindly resubmit. "
                f"From a confirmed shell: cd {shlex.quote(d.checkout)} && "
                f"opencode --model {shlex.quote(d.model)} --auto; reconstruct {d.item} "
                "from durable fr state and explicitly reconcile the descriptor."
            )

            def checkpoint(state: str) -> None:
                nonlocal d
                d = d.model_copy(update={"checkpoint": state})
                managed.save(d)

            checkpoint("prepared")
            try:
                _run_herdr(["pane", "send-text", pane, "exit"])
                _run_herdr(["pane", "send-keys", pane, "enter"])

                def exited() -> str | None:
                    info = _run_herdr(["pane", "process-info", "--pane", pane])
                    cwd = shell_cwd(info)
                    if cwd:
                        return cwd
                    if process(info):
                        screen = str(
                            _run_herdr(["pane", "read", pane, "--source", "visible", "--ansi"]).get(
                                "raw", ""
                            )
                        )
                        if input_reason(screen) == "dialog-or-unfocused":
                            raise HerdrError("exit-dialog: left untouched")
                    return None

                cwd = _poll(exited)
                if cwd is None:
                    raise HerdrError("exit-timeout: foreground shell not confirmed")
                checkpoint("source-exited")
                if cwd != d.checkout:
                    if not Path(d.checkout).is_dir():
                        raise HerdrError("stable checkout is unavailable")
                    _run_herdr(["pane", "send-text", pane, f"cd {shlex.quote(d.checkout)}"])
                    _run_herdr(["pane", "send-keys", pane, "enter"])
                if not _poll(
                    lambda: (
                        True
                        if shell_cwd(_run_herdr(["pane", "process-info", "--pane", pane]))
                        == d.checkout
                        else None
                    )
                ):
                    raise HerdrError("shell-cwd-timeout")
                start_agent(
                    [
                        "agent",
                        "start",
                        d.name,
                        "--kind",
                        "opencode",
                        "--pane",
                        pane,
                        "--",
                        *launch_args(d.model),
                    ],
                    run=_run_herdr,
                    sleep=_sleep,
                )
                wait_ready(d)
                checkpoint("target-ready")
                checkpoint("submission-started")
                try:
                    _run_herdr(
                        [
                            "agent",
                            "prompt",
                            d.name,
                            brief,
                            "--wait",
                            "--until",
                            "working",
                            "--until",
                            "blocked",
                            "--timeout",
                            "30000",
                        ]
                    )
                except Exception:
                    checkpoint("submission-uncertain")
                    raise
                checkpoint("uptake-confirmed")
                checkpoint("active")
                return "ok", "", None
            except Exception as exc:  # noqa: BLE001 - one pane never stops the next
                return (
                    "fail",
                    f"{d.checkpoint}: {exc}; source/target/shell must be inspected",
                    recovery,
                )
    except Exception as exc:  # noqa: BLE001 - unreadable observation is a skip, not input
        return "skip", str(exc), None
