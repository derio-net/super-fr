"""Synthetic startup timing replay with captured input screens; never live verdicts.

Real diagnostic: title readiness at +4.406s, eligible rendered textarea at +9.741s.
All three entry points must wait before a single prompt; no uncertain replay.
"""

import itertools
import json
from pathlib import Path

import pytest
from fr_dispatch.protocols import ReplacementRequest
from fr_dispatch.testing import run_item
from fr_herdr import managed, opencode, replacement, runner

FIXTURES = Path(__file__).parents[1] / "fixtures/herdr"


@pytest.fixture
def timeline(tmp_path, monkeypatch, native_herdr_cache):
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_PANE_ID", "caller")
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "socket"))
    monkeypatch.setattr(runner, "stable_checkout", lambda p: p)
    monkeypatch.setattr(replacement, "stable_checkout", lambda p: p)
    monkeypatch.setattr(managed, "reconstruct", lambda d: "HOLD, never replay the goal")
    monkeypatch.setattr(opencode, "_sleep", lambda seconds: None)
    monkeypatch.setattr(opencode, "_clock", lambda counter=itertools.count(): next(counter))
    created = json.loads((FIXTURES / "tab-create.json").read_text())
    pane = created["result"]["root_pane"]["pane_id"]
    screen = json.loads((FIXTURES / "opencode/final-idle.json").read_text())["raw"]
    d = managed.Descriptor(
        server=managed.server_identity(),
        pane=pane,
        name="b-test",
        item="example/alpha/run/batch-test",
        role="batch",
        branch="feat/test",
        checkout=str(tmp_path),
        harness="opencode",
        model="openai/old",
    )

    class Timeline:
        phase = "source"
        reads = 0
        name = d.name
        model = d.model
        calls = []
        refusal_screen = None
        wrong_model = False

        def __init__(self):
            self.calls = []

        def __call__(self, args):
            self.calls.append(args)
            if args[:2] == ["tab", "create"]:
                return created
            if args[:2] == ["agent", "list"]:
                return {
                    "result": {
                        "agents": [
                            {
                                "pane_id": pane,
                                "name": self.name,
                                "agent": "opencode",
                                "agent_status": "idle",
                                "interactive_ready": True,
                            }
                        ]
                    }
                }
            if args[:2] == ["pane", "process-info"]:
                proc = {
                    "pid": 2,
                    "argv": [
                        "opencode",
                        "--model",
                        "other/model" if self.wrong_model else self.model,
                    ],
                    "cwd": d.checkout,
                }
                if self.phase == "shell":
                    proc = {"pid": 1, "argv": ["zsh"], "cwd": d.checkout}
                return {
                    "result": {"process_info": {"shell_pid": 1, "foreground_processes": [proc]}}
                }
            if args[:2] == ["pane", "read"]:
                if self.phase == "startup":
                    self.reads += 1
                    return {
                        "raw": self.refusal_screen
                        if self.refusal_screen is not None
                        else ""
                        if self.reads < 3
                        else screen
                    }
                return {"raw": screen}
            if args[:2] == ["pane", "send-keys"]:
                self.phase = "shell"
            if args[:2] == ["agent", "start"]:
                self.name = args[2]
                self.model = args[args.index("--model") + 1]
                self.phase = "startup"
            if args[:2] == ["agent", "prompt"] and self.reads < 3:
                raise runner.HerdrError(
                    "title ready but input not rendered", code="agent_prompt_stalled"
                )
            return {}

    fake = Timeline()
    for module in (runner, opencode, replacement):
        monkeypatch.setattr(module, "_run_herdr", fake)
    return d, fake


def test_initial_dispatch_waits_for_rendered_prompt_before_single_submission(timeline):
    d, fake = timeline
    item = run_item(
        "example/alpha",
        "batch-test",
        harness="opencode",
        model=d.model,
        checkout=d.checkout,
        branch=d.branch,
        brief="HOLD",
    )
    assert runner.HerdrRunner("w2").dispatch(item) == d.pane
    assert fake.reads >= 3
    assert sum(c[:2] == ["agent", "prompt"] for c in fake.calls) == 1
    assert not any(c[:2] in (["agent", "send-keys"], ["pane", "send-keys"]) for c in fake.calls)


def test_managed_restart_waits_for_new_rendered_prompt(timeline):
    d, fake = timeline
    managed.save(d)
    assert opencode.restart_pane(d.pane, yes=True, exclude=set())[0] == "ok"
    assert fake.reads >= 3
    assert sum(c[:2] == ["agent", "prompt"] for c in fake.calls) == 1


def test_replacement_target_waits_for_rendered_prompt(timeline):
    d, fake = timeline
    managed.save(d)
    request = ReplacementRequest(
        d.item,
        d.pane,
        d.name,
        d.branch,
        d.checkout,
        d.harness,
        d.model,
        "opencode",
        "openai/new",
        "attempt",
    )
    op = replacement.Operation(request)
    with op.ownership():
        op.prepare()
        assert op.execute().ok
    assert fake.reads >= 3
    assert sum(c[:2] == ["agent", "prompt"] for c in fake.calls) == 1
    start = next(c for c in fake.calls if c[:2] == ["agent", "start"])
    assert start[start.index("--") + 1 :] == ["--model", request.model, "--auto"]


@pytest.mark.parametrize("failure", ["timeout", "draft", "dialog", "model", "name"])
def test_startup_readiness_refuses_unsafe_or_unrendered_target_without_prompt(timeline, failure):
    d, fake = timeline
    fake.phase = "startup"
    if failure == "timeout":
        fake.refusal_screen = ""
    elif failure in {"draft", "dialog"}:
        fake.refusal_screen = json.loads((FIXTURES / f"opencode/{failure}.json").read_text())["raw"]
    elif failure == "model":
        fake.wrong_model = True
    else:
        fake.name = "different-name"
    pending = d.model_copy(update={"checkpoint": "prepared"})
    managed.save(pending)
    with pytest.raises((managed.ManagedError, runner.HerdrError)):
        opencode.wait_ready(pending)
    assert managed.load(d.pane) == pending
    assert not any(c[:2] in (["agent", "prompt"], ["pane", "send-keys"]) for c in fake.calls)
