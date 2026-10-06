"""fr_herdr.restart — live-fixture smoke test first, then the engine (spec 2026-10-06 §A)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

import pytest  # noqa: E402

from fr_herdr import restart  # noqa: E402


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
    assert restart.kept_args(_load("process-info-model-flag.json")["result"]["process_info"][
        "foreground_processes"
    ][-1]["argv"]) == ["--model", "claude-opus-5-5"]


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
    assert restart.transcript_path("/x", "s") == tmp_path / ".claude" / "projects" / "-x" / "s.jsonl"


def test_a_truecolour_operand_of_two_is_not_faint() -> None:
    typed = "❯\xa0\x1b[0m\x1b[38;2;177;185;249mhello\x1b[0m\r"  # operator text, coloured
    faint = "❯\xa0\x1b[0m\x1b[2m\x1b[38;2;1;2;3mhint\x1b[0m\r"  # faint, then a colour
    assert restart.has_draft(typed)
    assert not restart.has_draft(faint)
