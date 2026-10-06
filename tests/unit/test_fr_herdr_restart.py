"""fr_herdr.restart — live-fixture smoke test first, then the engine (spec 2026-10-06 §A)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr_herdr import restart
from fr_herdr._herdr import HerdrError

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "herdr" / "restart"


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text())
    return data


def test_live_fixtures_load() -> None:
    agents = _load("agent-list.json")["result"]["agents"]
    claude = [a for a in agents if a["agent"] == "claude"]
    assert claude
    for a in claude:
        assert a["agent_status"] in {"idle", "working", "done", "blocked"}
        assert a["agent_session"]["value"]
        assert a["pane_id"]
    assert any("name" in a for a in claude) and any("name" not in a for a in claude)

    for name in ("process-info.json", "process-info-model-flag.json"):
        procs = _load(name)["result"]["process_info"]["foreground_processes"]
        assert any(p.get("argv", [""])[0] == "claude" for p in procs)
        assert any("argv" not in p for p in procs) or name.endswith("flag.json")
        assert all("cwd" in p for p in procs)

    for name in (
        "screen-suggestion.json",
        "screen-placeholder.json",
        "screen-empty.json",
        "screen-draft.json",
        "screen-background.json",
    ):
        raw = _load(name)["raw"]
        assert any(line.startswith("❯") for line in raw.splitlines()), name

    taken = _load("agent-start-name-taken.json")
    assert taken["error"]["code"] == "agent_name_taken"
    reuse = _load("agent-start-reuse.json")["result"]["agent"]
    assert reuse["name"] and reuse["agent_session"]["value"]


# --- T2: pure classify / kept_args ------------------------------------------------


def _agent(**over: Any) -> dict[str, Any]:
    agent: dict[str, Any] = {
        "agent": "claude",
        "agent_status": "idle",
        "agent_session": {"value": "sess-1"},
        "pane_id": "w2:p9",
        "name": None,
    }
    agent.update(over)
    return agent


def _screen(name: str) -> str:
    return str(_load(name)["raw"])


def _classify(**over: Any) -> restart.Skip | restart.Plan:
    args: dict[str, Any] = {
        "agent": _agent(),
        "screen": _screen("screen-empty.json"),
        "argv": ["claude", "--resume", "sess-1"],
        "cwd": "/home/user/proj",
        "transcript_exists": True,
        "self_pane": "w9:p9",
        "excluded": frozenset(),
    }
    args.update(over)
    return restart.classify(**args)


def _reason(result: restart.Skip | restart.Plan) -> str:
    assert isinstance(result, restart.Skip), result
    return result.reason


def test_an_idle_pane_with_an_empty_prompt_is_planned() -> None:
    plan = _classify()
    assert isinstance(plan, restart.Plan)
    assert plan.session_id == "sess-1"
    assert plan.pane_id == "w2:p9"
    assert plan.kept == ()


@pytest.mark.parametrize("status", ["working", "blocked", "unknown"])
def test_a_busy_status_is_skipped_first(status: str) -> None:
    assert _reason(_classify(agent=_agent(agent_status=status), argv=None)) == f"status {status}"


def test_done_counts_as_idle() -> None:
    assert isinstance(_classify(agent=_agent(agent_status="done")), restart.Plan)


def test_no_session_no_transcript_and_the_order_of_checks() -> None:
    assert _reason(_classify(agent=_agent(agent_session=None))) == "no-session"
    assert _reason(_classify(transcript_exists=False)) == "no-transcript"
    # no-transcript outranks a draft and an unknown flag
    both = _classify(
        transcript_exists=False, argv=["claude", "--bogus"], screen=_screen("screen-draft.json")
    )
    assert _reason(both) == "no-transcript"
    # an unknown flag outranks a draft; a draft outranks background work
    assert _reason(_classify(argv=["claude", "--bogus"], screen=_screen("screen-draft.json"))) == (
        "unknown-flag --bogus"
    )
    assert _reason(_classify(screen=_screen("screen-draft.json"))) == "draft"


def test_a_process_with_no_claude_argv_is_skipped() -> None:
    assert _reason(_classify(argv=None)) == "no-process"


def test_a_faint_suggestion_is_not_a_draft_but_typed_text_is() -> None:
    assert not restart.has_draft(_screen("screen-suggestion.json"))
    assert not restart.has_draft(_screen("screen-placeholder.json"))
    assert not restart.has_draft(_screen("screen-empty.json"))
    assert restart.has_draft(_screen("screen-draft.json"))
    # the same pane, suggestion on screen, restarts
    assert isinstance(_classify(screen=_screen("screen-suggestion.json")), restart.Plan)


def test_background_work_comes_from_shells_monitors_and_the_agent_panel() -> None:
    assert restart.has_background_work(_screen("screen-background.json"))
    for clean in ("screen-suggestion.json", "screen-empty.json", "screen-draft.json"):
        # `← 1 agent` is on every idle claude; it is not evidence of work
        assert not restart.has_background_work(_screen(clean)), clean
    assert _reason(_classify(screen=_screen("screen-background.json"))) == "background-work"


def test_self_and_excluded_panes_are_skipped_last() -> None:
    assert _reason(_classify(self_pane="w2:p9")) == "self"
    assert _reason(_classify(excluded=frozenset({"w2:p9"}))) == "excluded"
    assert _reason(_classify(self_pane="w2:p9", screen=_screen("screen-background.json"))) == (
        "background-work"
    )


def test_kept_args_keeps_the_launch_flags_and_drops_the_session_ones() -> None:
    argv = [
        "claude",
        "--model",
        "m",
        "--permission-mode=plan",
        "--dangerously-skip-permissions",
        "--add-dir",
        "/a",
        "/b",
        "--settings",
        "s.json",
        "--mcp-config",
        "m.json",
        "--plugin-dir",
        "/p",
        "--agent",
        "x",
        "--resume",
        "old",
        "-c",
        "--session-id",
        "sid",
    ]
    assert restart.kept_args(argv) == [
        "--model",
        "m",
        "--permission-mode=plan",
        "--dangerously-skip-permissions",
        "--add-dir",
        "/a",
        "/b",
        "--settings",
        "s.json",
        "--mcp-config",
        "m.json",
        "--plugin-dir",
        "/p",
        "--agent",
        "x",
    ]
    assert restart.kept_args(["claude", "-r", "old"]) == []
    assert restart.kept_args(
        _load("process-info-model-flag.json")["result"]["process_info"]["foreground_processes"][-1][
            "argv"
        ]
    ) == ["--model", "claude-opus-5-5"]


def test_kept_args_refuses_an_unknown_flag_or_a_positional() -> None:
    assert restart.kept_args(["claude", "--chrome"]) == restart.UnknownFlag("--chrome")
    assert restart.kept_args(["claude", "do the thing"]) == restart.UnknownFlag("do the thing")
    assert restart.kept_args(["claude", "--bogus=1"]) == restart.UnknownFlag("--bogus")


def test_transcript_path_slugs_the_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    path = restart.transcript_path("/home/user/.cache/a b/c", "sid")
    assert path == tmp_path / "projects" / "-home-user--cache-a-b-c" / "sid.jsonl"
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert (
        restart.transcript_path("/x", "s") == tmp_path / ".claude" / "projects" / "-x" / "s.jsonl"
    )


def test_a_truecolour_operand_of_two_is_not_faint() -> None:
    typed = "❯\xa0\x1b[0m\x1b[38;2;177;185;249mhello\x1b[0m\r"  # operator text, coloured
    faint = "❯\xa0\x1b[0m\x1b[2m\x1b[38;2;1;2;3mhint\x1b[0m\r"  # faint, then a colour
    assert restart.has_draft(typed)
    assert not restart.has_draft(faint)


# --- T3: the restart sequence and restart_idle -----------------------------------

DIALOG = "You have 1 unsent feedback draft · Enter to review & send · Esc to discard and exit"


class FakeHerdr:
    """`_run_herdr` replaced by a script: per `<noun> <verb>`, a list of answers consumed
    in order (the last repeats). An answer is a dict, a HerdrError to raise, or a callable
    taking the argv. Time is a fake clock advanced by the injected sleep."""

    def __init__(self, script: dict[str, list[Any]]) -> None:
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[list[str]] = []
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self, args: list[str]) -> dict[str, Any]:
        self.calls.append(list(args))
        answers = self.script.get(" ".join(args[:2]))
        assert answers is not None, f"unscripted herdr call {args}"
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if callable(answer):
            answer = answer(args)
        if isinstance(answer, Exception):
            raise answer
        assert isinstance(answer, dict)
        return answer

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now

    def verbs(self) -> list[str]:
        return [" ".join(c[:2]) for c in self.calls]

    def keys_sent(self) -> list[list[str]]:
        return [c for c in self.calls if c[:2] in (["pane", "send-text"], ["pane", "send-keys"])]


def _procs(*argvs: list[str]) -> dict[str, Any]:
    return {
        "result": {
            "process_info": {
                "foreground_processes": [
                    {"argv": a, "argv0": a[0], "cwd": "/home/user/proj"} for a in argvs
                ]
            }
        }
    }


CLAUDE_UP = _procs(["node", "mcp"], ["claude", "--resume", "sess-1"])
SHELL_ONLY = _procs(["-zsh"])
EMPTY_SCREEN = {"raw": _screen("screen-empty.json")}


def _agents(*agents: dict[str, Any]) -> dict[str, Any]:
    return {"result": {"agents": list(agents)}}


def _back(pane: str = "w2:p9", session: str = "sess-1") -> dict[str, Any]:
    return _agents(_agent(pane_id=pane, agent_session={"value": session}))


def _install(monkeypatch: pytest.MonkeyPatch, script: dict[str, list[Any]]) -> FakeHerdr:
    fake = FakeHerdr(script)
    monkeypatch.setattr(restart, "_run_herdr", fake)
    monkeypatch.setattr(restart, "_sleep", fake.sleep)
    monkeypatch.setattr(restart, "_clock", fake.clock)
    return fake


PLAN = restart.Plan("w2:p9", "b-demo-1234", "sess-1", "/home/user/proj", ("--model", "m"))
OK_SCRIPT: dict[str, list[Any]] = {
    "pane send-text": [{}],
    "pane send-keys": [{}],
    "pane process-info": [CLAUDE_UP, SHELL_ONLY],
    "pane read": [EMPTY_SCREEN],
    "agent start": [{}],
    "agent list": [_back()],
}


def test_restart_sends_exit_then_enter_and_relaunches_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _install(monkeypatch, OK_SCRIPT)
    outcome = restart.restart(PLAN)
    assert outcome == restart.Outcome("w2:p9", True, "restarted", None)
    assert fake.calls[0] == ["pane", "send-text", "w2:p9", "/exit"]
    assert fake.calls[1] == ["pane", "send-keys", "w2:p9", "enter"]
    assert [
        "agent",
        "start",
        "b-demo-1234",
        "--kind",
        "claude",
        "--pane",
        "w2:p9",
        "--",
        "--model",
        "m",
        "--resume",
        "sess-1",
    ] in fake.calls
    assert fake.verbs()[-1] == "agent list"


def test_an_exit_dialog_fails_at_once_and_sends_nothing_further(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _install(
        monkeypatch,
        {**OK_SCRIPT, "pane process-info": [CLAUDE_UP], "pane read": [{"raw": DIALOG}]},
    )
    outcome = restart.restart(PLAN)
    assert (outcome.ok, outcome.reason) == (False, "exit-dialog")
    assert outcome.resume == "claude --model m --resume sess-1"
    assert len(fake.keys_sent()) == 2 and fake.now == 0.0
    assert "agent start" not in fake.verbs()


def test_the_exit_wait_gives_up_after_thirty_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install(monkeypatch, {**OK_SCRIPT, "pane process-info": [CLAUDE_UP]})
    outcome = restart.restart(PLAN)
    assert (outcome.ok, outcome.reason) == (False, "exit-timeout")
    assert 30 <= fake.now < 32
    assert len(fake.keys_sent()) == 2 and "agent start" not in fake.verbs()
    assert outcome.resume == "claude --model m --resume sess-1"


def test_a_taken_name_falls_back_to_send_text(monkeypatch: pytest.MonkeyPatch) -> None:
    taken = HerdrError("agent name b-demo-1234 is already used", code="agent_name_taken")
    fake = _install(monkeypatch, {**OK_SCRIPT, "agent start": [taken]})
    assert restart.restart(PLAN).ok
    assert fake.keys_sent()[2:] == [
        ["pane", "send-text", "w2:p9", "claude --model m --resume sess-1"],
        ["pane", "send-keys", "w2:p9", "enter"],
    ]


def test_an_unnamed_pane_is_relaunched_by_send_text(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install(monkeypatch, OK_SCRIPT)
    plan = restart.Plan("w2:p9", None, "sess-1", "/home/user/proj", ())
    assert restart.restart(plan).ok
    assert "agent start" not in fake.verbs()
    assert fake.keys_sent()[2] == ["pane", "send-text", "w2:p9", "claude --resume sess-1"]


def test_the_resume_wait_gives_up_after_ninety_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    other = _agents(_agent(pane_id="w2:p9", agent_session={"value": "other"}))
    fake = _install(monkeypatch, {**OK_SCRIPT, "agent list": [other]})
    outcome = restart.restart(PLAN)
    assert (outcome.ok, outcome.reason) == (False, "resume-timeout")
    assert 90 <= fake.now < 92
    assert outcome.resume == "claude --model m --resume sess-1"


def test_a_herdr_error_becomes_a_step_failure_with_the_resume_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        {**OK_SCRIPT, "agent start": [HerdrError("agent_not_ready: blocked", code="x")]},
    )
    outcome = restart.restart(PLAN)
    assert not outcome.ok
    assert outcome.reason == "agent start: agent_not_ready: blocked"
    assert outcome.resume == "claude --model m --resume sess-1"


def test_a_failure_before_exit_was_sent_has_no_resume_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, {**OK_SCRIPT, "pane send-text": [HerdrError("gone")]})
    outcome = restart.restart(PLAN)
    assert (outcome.ok, outcome.resume) == (False, None)
    assert outcome.reason == "send /exit: gone"


# --- restart_idle ----------------------------------------------------------------


def _world(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, panes: dict[str, str], **script: Any
) -> FakeHerdr:
    """Claude panes `panes` (pane id -> screen fixture), each idle, session `s-<pane>`,
    transcripts present, cwd /home/user/proj; every restart succeeds unless scripted."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    slug = tmp_path / "projects" / "-home-user-proj"
    slug.mkdir(parents=True)
    agents = []
    for pane in panes:
        (slug / f"s-{pane}.jsonl").write_text("{}\n")
        agents.append(
            _agent(
                pane_id=pane, agent_session={"value": f"s-{pane}"}, tab_id=f"t-{pane}", name=None
            )
        )
    agents.append({"agent": "opencode", "agent_status": "idle", "pane_id": "w9:p1"})
    state = {"left": set()}  # panes whose claude has exited

    def process_info(args: list[str]) -> dict[str, Any]:
        pane = args[3]
        if pane in state["left"]:
            return SHELL_ONLY
        return _procs(["claude", "--resume", f"s-{pane}"])

    def read(args: list[str]) -> dict[str, Any]:
        return {"raw": _screen(panes[args[2]])}

    def keys(args: list[str]) -> dict[str, Any]:
        if args[1] == "send-text" and args[3] == "/exit":
            state["left"].add(args[2])
        return {}

    def listing(args: list[str]) -> dict[str, Any]:
        return _agents(*agents)

    fake = _install(
        monkeypatch,
        {
            "agent list": [listing],
            "tab list": [
                {"result": {"tabs": [{"tab_id": f"t-{p}", "label": f"tab {p}"} for p in panes]}}
            ],
            "pane process-info": [process_info],
            "pane read": [read],
            "pane send-text": [keys],
            "pane send-keys": [{}],
            "agent start": [{}],
            **script,
        },
    )
    return fake


def test_a_dry_run_sends_no_key_and_reports_every_pane(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = _world(
        monkeypatch,
        tmp_path,
        {"a": "screen-empty.json", "b": "screen-suggestion.json", "c": "screen-draft.json"},
    )
    report = restart.restart_idle(yes=False, exclude=())
    assert [(ln.pane_id, ln.verdict, ln.detail) for ln in report.lines] == [
        ("a", "ok", "would restart"),
        ("b", "ok", "would restart"),
        ("c", "skip", "draft"),
    ]
    assert [ln.tab for ln in report.lines] == ["tab a", "tab b", "tab c"]
    assert fake.keys_sent() == [] and "agent start" not in fake.verbs()
    assert not report.failed
    assert report.summary() == "2 would restart, 1 skipped, 0 failed"


def test_one_failed_pane_does_not_stop_the_next_and_panes_go_serially(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = _world(monkeypatch, tmp_path, {"a": "screen-empty.json", "b": "screen-empty.json"})
    # pane a's exit shows the dialog (its read answers it), pane b restarts fine
    base_read = fake.script["pane read"][0]

    def read(args: list[str]) -> dict[str, Any]:
        return {"raw": DIALOG} if args[2] == "a" and fake.keys_sent() else base_read(args)

    fake.script["pane read"] = [read]

    def listing(args: list[str]) -> dict[str, Any]:
        return _agents(
            _agent(pane_id="a", agent_session={"value": "s-a"}, tab_id="t-a"),
            _agent(pane_id="b", agent_session={"value": "s-b"}, tab_id="t-b"),
        )

    fake.script["agent list"] = [listing]
    base_procs = fake.script["pane process-info"][0]
    fake.script["pane process-info"] = [
        lambda args: CLAUDE_UP if args[3] == "a" else base_procs(args)
    ]
    report = restart.restart_idle(yes=True, exclude=())
    assert [(ln.pane_id, ln.verdict) for ln in report.lines] == [("a", "fail"), ("b", "ok")]
    assert report.failed
    assert report.lines[0].detail == "exit-dialog"
    assert report.lines[0].resume == "claude --resume s-a"
    sent = [c[2] for c in fake.keys_sent()]
    assert sent == ["a", "a", "b", "b", "b", "b"]  # /exit+enter for a, then all of b


def test_the_callers_pane_non_claude_panes_and_excluded_panes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _world(
        monkeypatch,
        tmp_path,
        {"a": "screen-empty.json", "b": "screen-empty.json", "c": "screen-empty.json"},
    )
    monkeypatch.setenv("HERDR_PANE_ID", "a")
    report = restart.restart_idle(yes=False, exclude=("c",))
    assert [(ln.pane_id, ln.verdict, ln.detail) for ln in report.lines] == [
        ("a", "skip", "self"),
        ("b", "ok", "would restart"),
        ("c", "skip", "excluded"),
    ]
