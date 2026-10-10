"""Restart idle Claude panes in place (spec 2026-10-06-driver-sessions-design §A).

`post_merge` rebuilds the tool env, so every other Claude session keeps the plugins it
loaded at start-up. This module restarts the idle ones on `--resume`, in the same pane,
with the same herdr agent name and launch flags.

The decisions are pure and kept apart from the herdr calls: `classify` (R2, the first
failing check names the reason), `kept_args` (which launch flags survive a restart),
`has_draft` and `has_background_work` (what the screen says), `transcript_path`.

The herdr surfaces parsed here are recorded from live herdr 0.9.1 under
`tests/fixtures/herdr/restart/` (see its README). Two things it found that the spec's
first draft did not know: `← N agent` is on the status line of every idle Claude, so it
is not evidence of background work (`N shells`, `N monitors` and the agent panel are);
and herdr accepts the pane's own agent name again right after `/exit`.
"""

from __future__ import annotations

import os
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from fr_herdr import managed, opencode
from fr_herdr._herdr import HerdrError, _run_herdr, poll, start_agent

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

EXIT_TIMEOUT = 30.0
"""Seconds `claude` gets to leave the pane's foreground after `/exit` (R3)."""
RESUME_TIMEOUT = 90.0
"""Seconds the relaunched `claude` gets to report the same session id (R3)."""
POLL_INTERVAL = 1.0

_sleep = time.sleep
_clock = time.monotonic

IDLE_STATUSES = frozenset({"idle", "done"})

# flag -> how many values follow it: 0, 1, or "*" (every following non-flag token)
_KEPT: dict[str, int | str] = {
    "--model": 1,
    "--permission-mode": 1,
    "--dangerously-skip-permissions": 0,
    "--add-dir": "*",
    "--settings": 1,
    "--mcp-config": "*",
    "--plugin-dir": 1,
    "--agent": 1,
}
# The flags a restart replaces: the relaunch carries its own `--resume <id>`.
_DROPPED: dict[str, int | str] = {
    "--resume": "?",
    "-r": "?",
    "--continue": 0,
    "-c": 0,
    "--session-id": 1,
}


@dataclass(frozen=True)
class Skip:
    """A pane that is not restarted, and why (R2). No key is ever sent to it."""

    pane_id: str
    reason: str


@dataclass(frozen=True)
class Plan:
    """A pane that will be restarted."""

    pane_id: str
    name: str | None
    session_id: str
    cwd: str
    kept: tuple[str, ...]


@dataclass(frozen=True)
class UnknownFlag:
    """A launch argument a restart cannot carry over (a flag outside the kept set, or a
    positional): the pane is skipped rather than resumed without it (sr-14)."""

    flag: str


def kept_args(argv: list[str]) -> list[str] | UnknownFlag:
    """The launch flags (with their values) a relaunch repeats; `argv[0]` is `claude`."""
    kept: list[str] = []
    rest = argv[1:]
    i = 0
    while i < len(rest):
        token = rest[i]
        i += 1
        flag, eq, _value = token.partition("=")
        if not token.startswith("-"):
            return UnknownFlag(token)
        table = _KEPT if flag in _KEPT else _DROPPED if flag in _DROPPED else None
        if table is None:
            return UnknownFlag(flag)
        arity = table[flag]
        values: list[str] = []
        if not eq:
            if arity == 1 and i < len(rest):
                values, i = [rest[i]], i + 1
            elif arity in ("*", "?"):
                while i < len(rest) and not rest[i].startswith("-"):
                    values.append(rest[i])
                    i += 1
                    if arity == "?":
                        break
        if table is _KEPT:
            kept.append(token)
            kept.extend(values)
    return kept


def transcript_path(cwd: str, session_id: str) -> Path:
    """`<CLAUDE_CONFIG_DIR or ~/.claude>/projects/<slug>/<id>.jsonl`, where the slug is
    the cwd with every character outside `[A-Za-z0-9]` replaced by `-`: the one
    directory `claude --resume` searches from that cwd (never a glob over projects)."""
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    root = Path(config) if config else Path.home() / ".claude"
    return root / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd) / f"{session_id}.jsonl"


_SGR = re.compile(r"\x1b\[([0-9;:]*)m")
_ANSI = re.compile(r"\x1b\[[0-9;:?]*[A-Za-z]")
_PROMPT = re.compile(r"^(?:\x1b\[[0-9;:]*m|\s)*❯")
_LINES = re.compile(r"\r?\n")


def _is_rule(line: str) -> bool:
    return _ANSI.sub("", line).strip().startswith("─")


def _live_prompt_index(lines: list[str]) -> int | None:
    """The input box's `❯` line: the last one that sits right under a horizontal rule.
    An earlier `❯` is the echo of a past message in the conversation, and a screen with
    no box at all (an overlay, a dialog) has no live prompt: None."""
    for idx in range(len(lines) - 1, 0, -1):
        if _PROMPT.match(lines[idx]) and _is_rule(lines[idx - 1]):
            return idx
    return None


def has_prompt(screen: str) -> bool:
    """True when the screen shows Claude's input box (so a draft can be judged at all)."""
    return _live_prompt_index(_LINES.split(screen)) is not None


def has_draft(screen: str) -> bool:
    """True when the input box holds text that is not rendered faint (SGR 2): on the
    prompt line, or on any continuation line down to the rule that closes the box.

    Claude draws its prompt suggestion faint right after the prompt
    (`❯\\xa0ESC[0mESC[2m<text>`), which a plain-text read cannot tell from typed input.
    A screen with no input box reports False; `classify` skips it as `no-prompt` first.
    """
    lines = _LINES.split(screen)
    idx = _live_prompt_index(lines)
    if idx is None:
        return False
    faint = False
    for n in range(idx, len(lines)):
        line = lines[n]
        if n > idx and _is_rule(line):
            break
        rest = line[_PROMPT.match(line).end() :] if n == idx else line  # type: ignore[union-attr]
        pos = 0
        for match in _SGR.finditer(rest):
            if _visible(rest[pos : match.start()]) and not faint:
                return True
            faint = _next_faint(faint, match.group(1))
            pos = match.end()
        if _visible(rest[pos:]) and not faint:
            return True
    return False


def _visible(text: str) -> str:
    return _ANSI.sub("", text).replace("\xa0", "").strip()


def _next_faint(faint: bool, params: str) -> bool:
    """The faint (SGR 2) state after one `ESC[<params>m`; a colour's operands are skipped,
    so the `2` in `38;2;r;g;b` is never read as "faint"."""
    codes = re.split(r"[;:]", params)
    i = 0
    while i < len(codes):
        code = codes[i] or "0"
        i += 1
        if code in ("38", "48"):
            mode = codes[i] if i < len(codes) else ""
            i += 1 + (3 if mode == "2" else 1 if mode == "5" else 0)
        elif code in ("0", "22"):
            faint = False
        elif code == "2":
            faint = True
    return faint


_SHELLS = re.compile(r"\b\d+ (?:shells?|monitors?)\b")
_AGENTS = re.compile(r"← (\d+) agents?\b")
_PANEL_ROW = re.compile(r"^\s*◯\s")


def has_background_work(screen: str) -> bool:
    """The status line under the prompt names running shells or monitors, or the agent
    panel lists a subagent. `← 1 agent` alone is on every idle Claude, so only a count
    above one counts."""
    lines = _LINES.split(screen)
    idx = _live_prompt_index(lines)
    if idx is None:
        return False
    below = [_ANSI.sub("", line) for line in lines[idx:]]
    for line in below:
        if _SHELLS.search(line) or _PANEL_ROW.match(line):
            return True
        found = _AGENTS.search(line)
        if found and int(found.group(1)) > 1:
            return True
    return False


def classify(
    *,
    agent: dict[str, Any],
    screen: str,
    argv: list[str] | None,
    cwd: str,
    transcript_exists: bool,
    self_pane: str | None,
    excluded: Collection[str],
) -> Skip | Plan:
    """R2 in a fixed order; the first failing check names the reason."""
    pane = str(agent["pane_id"])
    status = str(agent.get("agent_status"))
    if status not in IDLE_STATUSES:
        return Skip(pane, f"status {status}")
    session = agent.get("agent_session") or {}
    session_id = session.get("value")
    if not session_id:
        return Skip(pane, "no-session")
    if argv is None:
        return Skip(pane, "no-process")
    if not transcript_exists:
        return Skip(pane, "no-transcript")
    kept = kept_args(argv)
    if isinstance(kept, UnknownFlag):
        return Skip(pane, f"unknown-flag {kept.flag}")
    if not has_prompt(screen):
        return Skip(pane, "no-prompt")
    if has_draft(screen):
        return Skip(pane, "draft")
    if has_background_work(screen):
        return Skip(pane, "background-work")
    if self_pane and pane == self_pane:
        return Skip(pane, "self")
    if pane in excluded:
        return Skip(pane, "excluded")
    return Plan(pane, agent.get("name") or None, str(session_id), cwd, tuple(kept))


@dataclass(frozen=True)
class Outcome:
    """How one pane's restart ended. *resume* is the command that resumes the pane by
    hand, set on every failure after `/exit` was sent."""

    pane_id: str
    ok: bool
    reason: str
    resume: str | None = None


@dataclass(frozen=True)
class PaneLine:
    """One report line: `ok|skip|fail`, the detail, the pane id and its tab label."""

    pane_id: str
    tab: str
    verdict: str
    detail: str
    resume: str | None = None

    def render(self) -> str:
        reason = f" {self.detail}" if self.detail and self.verdict != "ok" else ""
        return f"{self.verdict}{reason}  {self.pane_id}  {self.tab}".rstrip()


@dataclass
class RestartReport:
    lines: list[PaneLine] = field(default_factory=list)
    dry_run: bool = True

    @property
    def failed(self) -> bool:
        return any(line.verdict == "fail" for line in self.lines)

    def summary(self) -> str:
        done = sum(1 for line in self.lines if line.verdict == "ok")
        skipped = sum(1 for line in self.lines if line.verdict == "skip")
        failed = sum(1 for line in self.lines if line.verdict == "fail")
        verb = "would restart" if self.dry_run else "restarted"
        return f"{done} {verb}, {skipped} skipped, {failed} failed"


_T = TypeVar("_T")


def _poll(check: Callable[[], _T | None], *, timeout: float) -> _T | None:
    """Call *check* until it answers something other than None, or *timeout* runs out.
    The one wait both the exit and the resume use."""
    return poll(check, timeout=timeout, clock=_clock, sleep=_sleep, interval=POLL_INTERVAL)


def _claude_process(info: dict[str, Any]) -> dict[str, Any] | None:
    procs = info.get("result", {}).get("process_info", {}).get("foreground_processes", [])
    for proc in procs:
        argv = proc.get("argv") or []
        if argv and Path(str(argv[0])).name == "claude":
            found: dict[str, Any] = proc
            return found
    return None


def _shell_cwd(info: dict[str, Any]) -> str | None:
    """The pane shell's cwd: the foreground process that is the shell itself (its pid is
    `shell_pid`), else the first foreground process that reports a cwd."""
    pinfo = info.get("result", {}).get("process_info", {})
    procs = [p for p in pinfo.get("foreground_processes", []) if p.get("cwd")]
    for proc in procs:
        if proc.get("pid") is not None and proc.get("pid") == pinfo.get("shell_pid"):
            return str(proc["cwd"])
    return str(procs[0]["cwd"]) if procs else None


_EXIT_DIALOG = re.compile(r"unsent feedback draft|Enter to review & send")


def _exit_state(pane: str) -> tuple[str, str | None] | None:
    """`("gone", shell cwd)` once no claude runs in the foreground, `("dialog", None)` if
    Claude's exit dialog is up (an unsent feedback draft), else None."""
    info = _run_herdr(["pane", "process-info", "--pane", pane])
    if _claude_process(info) is None:
        return "gone", _shell_cwd(info)
    text = str(_run_herdr(["pane", "read", pane, "--source", "visible"]).get("raw", ""))
    return ("dialog", None) if _EXIT_DIALOG.search(text) else None


def _same_session(pane: str, session_id: str) -> bool | None:
    """True once the pane runs a claude in the foreground AND `agent list` reports it on
    *session_id*. The process check matters: `agent list` can still show the pre-exit
    registration for a moment, which says nothing about the relaunch."""
    if _claude_process(_run_herdr(["pane", "process-info", "--pane", pane])) is None:
        return None
    agents = _run_herdr(["agent", "list"]).get("result", {}).get("agents", [])
    for agent in agents:
        if agent.get("pane_id") == pane and agent.get("agent") == "claude":
            if (agent.get("agent_session") or {}).get("value") == session_id:
                return True
    return None


def _start_named(plan: Plan) -> bool:
    """`agent start` on the pane under its own name: that keeps `HerdrRunner.message`
    working, which addresses agents by name. False when herdr refuses the name
    (`agent_name_taken`: another pane holds it), so the caller types the command.
    A pane whose shell is not up yet is retried, as the runner's own starts are."""
    argv = ["agent", "start", str(plan.name), "--kind", "claude", "--pane", plan.pane_id]
    try:
        start_agent(
            [*argv, "--", *plan.kept, "--resume", plan.session_id],
            run=_run_herdr,
            sleep=_sleep,
        )
    except HerdrError as exc:
        if exc.code == "agent_name_taken":
            return False
        raise
    return True


def restart(plan: Plan) -> Outcome:
    """Restart one pane in place (R3): `/exit`, wait for claude to leave, relaunch on
    `--resume` from the cwd claude had, wait for the same session id. Never raises: any
    failure is an Outcome."""
    pane = plan.pane_id
    command = shlex.join(["claude", *plan.kept, "--resume", plan.session_id])
    cd = f"cd {shlex.quote(plan.cwd)}" if plan.cwd else ""
    # The by-hand line is correct from wherever the pane's shell is, so it carries the cd
    # unless the shell is known to be in claude's cwd already.
    hand = [command]
    step = "send /exit"
    sent = False

    def fail(reason: str) -> Outcome:
        return Outcome(pane, False, reason, hand[0] if sent else None)

    try:
        if cd:
            hand[0] = f"{cd} && {command}"
        _run_herdr(["pane", "send-text", pane, "/exit"])
        sent = True
        _run_herdr(["pane", "send-keys", pane, "enter"])
        step = "wait for exit"
        state = _poll(lambda: _exit_state(pane), timeout=EXIT_TIMEOUT)
        if state is None:
            return fail("exit-timeout")
        if state[0] == "dialog":
            return fail("exit-dialog")
        shell_cwd = state[1]
        if cd and shell_cwd and shell_cwd != plan.cwd:
            # claude ran in a directory the shell is no longer in (it `cd`ed, or was
            # started from elsewhere): `--resume` only finds the transcript from claude's.
            step = "cd to the session's directory"
            _run_herdr(["pane", "send-text", pane, cd])
            _run_herdr(["pane", "send-keys", pane, "enter"])
        elif shell_cwd == plan.cwd:
            hand[0] = command
        step = "agent start"
        if not plan.name or not _start_named(plan):
            step = "send claude command"
            _run_herdr(["pane", "send-text", pane, command])
            _run_herdr(["pane", "send-keys", pane, "enter"])
        step = "wait for resume"
        if not _poll(lambda: _same_session(pane, plan.session_id), timeout=RESUME_TIMEOUT):
            return fail("resume-timeout")
    except Exception as exc:  # noqa: BLE001  one pane's failure never stops the run (R4)
        return fail(f"{step}: {exc}")
    return Outcome(pane, True, "restarted")


def restart_idle(*, yes: bool, exclude: Collection[str] = ()) -> RestartReport:
    """List every claude pane, classify each, and restart the eligible ones serially
    (R1-R4). A dry run (`yes=False`) sends no key. One pane's failure never stops the next;
    the caller's own pane is `HERDR_PANE_ID`."""
    agents = _run_herdr(["agent", "list"]).get("result", {}).get("agents", [])
    tabs = {
        t.get("tab_id"): str(t.get("label", ""))
        for t in _run_herdr(["tab", "list"]).get("result", {}).get("tabs", [])
    }
    self_pane = os.environ.get("HERDR_PANE_ID") or None
    report = RestartReport(dry_run=not yes)
    for listed in agents:
        if listed.get("agent") == "opencode":
            pane = str(listed["pane_id"])
            oc_verdict, detail, recovery = opencode.restart_pane(
                pane, yes=yes, exclude=set(exclude)
            )
            report.lines.append(
                PaneLine(pane, tabs.get(listed.get("tab_id"), ""), oc_verdict, detail, recovery)
            )
            continue
        if listed.get("agent") != "claude":
            continue
        pane = str(listed["pane_id"])
        tab = tabs.get(listed.get("tab_id"), "")
        try:
            # The listing above is only the roster: a pane that turned `working` while
            # an earlier pane was being restarted is judged on its status now.
            descriptor = managed.load(pane) if os.environ.get("HERDR_SOCKET_PATH") else None
            if descriptor and descriptor.checkpoint != "active":
                report.lines.append(
                    PaneLine(pane, tab, "skip", "pending managed operation; repair owed")
                )
                continue
            agent = _fresh(pane)
            if agent is None:
                report.lines.append(PaneLine(pane, tab, "skip", "gone"))
                continue
            verdict = classify(**_inputs(agent, self_pane, exclude))
        except Exception as exc:  # noqa: BLE001  an unreadable pane is skipped, never fatal
            report.lines.append(PaneLine(pane, tab, "skip", f"unreadable: {exc}"))
            continue
        if isinstance(verdict, Skip):
            report.lines.append(PaneLine(pane, tab, "skip", verdict.reason))
        elif not yes:
            report.lines.append(PaneLine(pane, tab, "ok", "would restart"))
        else:
            try:
                with managed.pane_lock(pane):
                    descriptor = managed.load(pane)
                    if descriptor and descriptor.checkpoint != "active":
                        report.lines.append(
                            PaneLine(pane, tab, "skip", "pending managed operation; repair owed")
                        )
                        continue
                    current = _fresh(pane)
                    if (
                        current is None
                        or classify(**_inputs(current, self_pane, exclude)) != verdict
                    ):
                        report.lines.append(PaneLine(pane, tab, "skip", "changed before mutation"))
                        continue
                    outcome = restart(verdict)
            except Exception as exc:  # noqa: BLE001 - lock losers/unknown observations send nothing
                report.lines.append(PaneLine(pane, tab, "skip", str(exc)))
                continue
            if outcome.ok:
                report.lines.append(PaneLine(pane, tab, "ok", ""))
            else:
                report.lines.append(PaneLine(pane, tab, "fail", outcome.reason, outcome.resume))
    return report


def _fresh(pane: str) -> dict[str, Any] | None:
    """The pane's `agent list` entry as it is now, or None when it is gone."""
    agents = _run_herdr(["agent", "list"]).get("result", {}).get("agents", [])
    for agent in agents:
        if agent.get("pane_id") == pane and agent.get("agent") == "claude":
            found: dict[str, Any] = agent
            return found
    return None


def _inputs(
    agent: dict[str, Any], self_pane: str | None, exclude: Collection[str]
) -> dict[str, Any]:
    """What `classify` needs, read from herdr. A pane that is not idle is not read at all."""
    pane = str(agent["pane_id"])
    inputs: dict[str, Any] = {
        "agent": agent,
        "screen": "",
        "argv": None,
        "cwd": str(agent.get("foreground_cwd") or agent.get("cwd") or ""),
        "transcript_exists": False,
        "self_pane": self_pane,
        "excluded": frozenset(exclude),
    }
    session_id = (agent.get("agent_session") or {}).get("value")
    if agent.get("agent_status") not in IDLE_STATUSES or not session_id:
        return inputs
    proc = _claude_process(_run_herdr(["pane", "process-info", "--pane", pane]))
    if proc is None:
        return inputs
    inputs["argv"] = [str(a) for a in proc["argv"]]
    inputs["cwd"] = str(proc.get("cwd") or inputs["cwd"])
    inputs["transcript_exists"] = transcript_path(inputs["cwd"], str(session_id)).is_file()
    inputs["screen"] = str(
        _run_herdr(["pane", "read", pane, "--source", "visible", "--ansi"]).get("raw", "")
    )
    return inputs
