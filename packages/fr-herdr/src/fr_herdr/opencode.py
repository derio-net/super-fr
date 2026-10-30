"""Fail-closed OpenCode 1.18.35/default-theme input observation and fresh restart.

Grounding: tests/fixtures/herdr/opencode/README.md. Unknown versions, themes,
overlays or foreground layouts are skipped, never treated as empty input.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
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
    joined = "\n".join(lines).casefold()
    if re.search(
        r"permission required|allow once|allow this action|search provider setup|"
        r"web search setup|plugin (?:error|failed)|failed plugin|plugin must export|"
        r"herdr-agent-state\.js.{0,80}(?:failed|error)",
        joined,
    ):
        return "unknown-dialog-or-background"
    if not borders:
        return "unknown-layout"
    end, border = borders[-1]
    if not _FOCUSED.search(raw[end]):
        return "dialog-or-unfocused"
    # Footer must be current: a prior transcript box is not evidence of today's input.
    below = [line for line in lines[end + 1 :] if line.strip()]
    if not below:
        return "unknown-layout"
    legacy_footer = bool(
        re.search(r"(?:^|\s)1\.18\.35\s*$", below[-1])
        and any("ctrl+p commands" in line for line in below)
    )
    # V2.1.4 changed the footer, not the focused prompt border or textarea.
    # Require the full captured footer fingerprint; a version string alone is
    # never sufficient evidence of an empty prompt.
    v2_footer = bool(
        re.search(r"shift\+tab agents", below[-1])
        and re.search(r"ctrl\+p commands", below[-1])
        and re.search(r"[^ ]+:main\s+main\s+·\s+no fr-isolation", below[-1])
    )
    if not (legacy_footer or v2_footer):
        return "unknown-layout"
    if border.group(3) and not (
        re.search(r"• OpenCode 1\.18\.35\s*$", below[-1]) and legacy_footer
    ):
        return "unknown-layout"
    x = len(border.group(1))
    width = 1 + len(border.group(2))
    if end < 2 or not re.match(r"^\s*┃  (Build(?: auto)?|Plan) · .+", lines[end - 1]):
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
    if re.search(r"[\u2800-\u28ff].*Task", joined, re.I):
        return "unknown-dialog-or-background"
    return None


def _startup_metadata_pending(screen: str) -> bool:
    """Recognize only the captured V2 empty, not-yet-resolved metadata frame.

    This is a reason to WAIT before the first prompt, never input admission.
    Whitelist the whole visible layout: an unknown overlay, transcript, draft,
    complete-but-muted prompt or different theme must not become a startup retry.
    V2's border blends agent metadata colour; it is not a direct focus flag.
    """
    raw = screen.splitlines()
    lines = [_ANSI.sub("", line).rstrip() for line in raw]
    if any("\x1b" in line for line in lines):
        return False
    borders = [i for i, line in enumerate(lines) if re.fullmatch(r"  ╹▀{20,}", line)]
    if len(borders) != 1:
        return False
    end = borders[0]
    begin = end - 4
    if begin < 3 or lines[begin:end] != ["  ┃"] * 4:
        return False
    grey = r"\x1b\[38;2;72;72;72m(?:\x1b\[[0-9;]*m)*"
    if any(
        not re.search(grey + glyph, raw[i])
        for i, glyph in [*((i, "┃") for i in range(begin, end)), (end, "╹")]
    ):
        return False
    # Only the default timestamp title is visible above the empty composer.
    # It may wrap in the right sidebar; no arbitrary history/dialog text is allowed.
    sidebar = len(lines[end]) + 4
    heading = [(i, line) for i, line in enumerate(lines[:begin]) if line.strip()]
    if not heading or [i for i, _ in heading] != list(range(1, 1 + len(heading))):
        return False
    if any(line[:sidebar].strip() for _, line in heading):
        return False
    title = "".join(line[sidebar:] for _, line in heading)
    if not re.fullmatch(r"New session - \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", title):
        return False
    below = [line for line in lines[end + 1 :] if line.strip()]
    return len(below) == 1 and bool(
        re.fullmatch(
            r"  \S+  main · no fr-isolation  shift\+tab agents  ctrl\+p commands    \S+",
            below[0],
        )
    )


def process(info: dict[str, Any]) -> dict[str, Any] | None:
    procs = info.get("result", {}).get("process_info", {}).get("foreground_processes", [])
    if len(procs) != 1:
        return None
    proc = procs[0]
    argv = proc.get("argv", [])
    return proc if argv and Path(str(argv[0])).name == "opencode" else None


def create_session(model: str, checkout: str) -> str:
    """Create a model-pinned session through the OpenCode v2 API.

    OpenCode 2.1.4 accepts ``--model`` on ``run`` and ``mini``, not on the
    interactive root command. Creating the session through the server API
    stores the selection durably; the root TUI can then attach with ``--session``.
    """
    provider, model_ref = model.split("/", 1)
    model_id, separator, variant = model_ref.partition("#")
    model_ref_payload: dict[str, str] = {"providerID": provider, "id": model_id}
    if separator:
        model_ref_payload["variant"] = variant
    payload = json.dumps(
        {
            "model": model_ref_payload,
            "location": {"directory": checkout},
        },
        separators=(",", ":"),
    )
    try:
        result = subprocess.run(
            ["opencode", "api", "POST", "/api/session", "--data", payload],
            cwd=checkout,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        response = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise HerdrError("could not create an explicitly model-selected OpenCode session") from exc
    data = response.get("data") if isinstance(response, dict) else None
    selected = data.get("model") if isinstance(data, dict) else None
    session_id = data.get("id") if isinstance(data, dict) else None
    if (
        not isinstance(session_id, str)
        or not session_id
        or not isinstance(selected, dict)
        or selected.get("providerID") != provider
        or selected.get("id") != model_id
        # OpenCode 2.1.4 resolves an omitted variant to its default in the response.
        # The provider and model id must always match; a variant is strict only when
        # the request explicitly selected one. Validate any returned optional variant.
        or (
            selected.get("variant") != variant
            if separator
            else ("variant" in selected and not isinstance(selected.get("variant"), str))
        )
    ):
        raise HerdrError("OpenCode did not confirm the requested session model")
    return session_id


def launch_args(session: str) -> list[str]:
    """Attach the interactive root TUI to a session and retain auto-approval."""
    return ["--session", session, "--auto"]


def model_matches(proc: dict[str, Any], d: managed.Descriptor) -> bool:
    raw_argv = proc.get("argv", [])
    if not isinstance(raw_argv, list) or any(not isinstance(arg, str) for arg in raw_argv):
        return False
    argv: list[str] = raw_argv
    if d.session:
        return argv[1:] == ["--session", d.session, "--auto"]
    # Pre-session descriptors and captured OpenCode 1.x processes have no
    # durable session ID. Keep recognizing only the launch forms we supported
    # before session pinning; every newly launched v2 session takes the strict
    # session-ID branch above.
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


def _eligible_process(
    d: managed.Descriptor,
    exclude: set[str],
    *,
    run: Callable[[list[str]], dict[str, Any]] | None = None,
    restart: bool = True,
) -> dict[str, Any]:
    observe = run or _run_herdr
    if d.checkpoint != "active":
        raise managed.ManagedError(f"unresolved managed checkpoint {d.checkpoint}; repair owed")
    if restart:
        managed.restart_admission(d)
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
    if d.recovery_hold and proc and "--auto" not in proc.get("argv", []):
        raise managed.ManagedError("recovered OpenCode is not autonomous (--auto missing)")
    if (
        not proc
        or not proc.get("pid")
        or not model_matches(proc, d)
        or proc.get("cwd") != d.checkout
    ):
        raise managed.ManagedError("foreground process/model is unknown or changed")
    return proc


def eligible(
    d: managed.Descriptor,
    exclude: set[str],
    *,
    run: Callable[[list[str]], dict[str, Any]] | None = None,
    restart: bool = True,
) -> dict[str, Any]:
    observe = run or _run_herdr
    proc = _eligible_process(d, exclude, run=observe, restart=restart)
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

    Unknown layout and the captured incomplete-metadata startup frame are retried
    within the existing deadline. Drafts/dialogs, status or exact live identity/model/cwd
    mismatches refuse. The active projection is read-only: pending durable checkpoints
    are never promoted before submission/uptake confirmation.
    """
    observation = d.model_copy(update={"checkpoint": "active"})
    observe = run or _run_herdr
    initial_pid: object = None

    def ready() -> dict[str, Any] | None:
        nonlocal initial_pid
        # Startup readiness is inside the owned pending transaction, not restart admission.
        proc = _eligible_process(observation, set(), run=observe, restart=False)
        if initial_pid is None:
            initial_pid = proc["pid"]
        elif proc["pid"] != initial_pid:
            raise managed.ManagedError("startup foreground process changed")
        screen = str(
            observe(["pane", "read", d.pane, "--source", "visible", "--ansi"]).get("raw", "")
        )
        reason = input_reason(screen)
        if reason == "unknown-layout" or (
            reason == "dialog-or-unfocused" and _startup_metadata_pending(screen)
        ):
            return None
        if reason:
            raise managed.ManagedError(reason)
        return proc

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
                "create a fresh OpenCode session with the recorded provider/model, then "
                f"attach the interactive root with --session <id> --auto; reconstruct {d.item} "
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
                session = create_session(d.model, d.checkout)
                d = d.model_copy(update={"session": session})
                managed.save(d)
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
                        *launch_args(session),
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
