"""Deterministic startup deadline regressions: no live calls or wall-clock sleeps."""

import json
import subprocess

import pytest
from fr_herdr import _herdr, managed, opencode

from tests.unit.test_opencode_rendered_readiness import metadata_capture


@pytest.fixture
def deadline_env(tmp_path, monkeypatch, native_herdr_cache):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "socket"))
    monkeypatch.setenv("HERDR_PANE_ID", "caller")
    d = managed.Descriptor(
        server=managed.server_identity(),
        pane="w1:p1",
        name="b-deadline",
        item="example/alpha/run/batch-deadline",
        role="batch",
        branch="feat/test",
        checkout=str(tmp_path),
        model="openai/test",
        session="ses-pinned",
        checkpoint="prepared",
    )

    class Clock:
        now = 0.0
        sleeps = None

        def __init__(self):
            self.sleeps = []

        def __call__(self):
            return self.now

        def sleep(self, seconds):
            self.sleeps.append(seconds)
            self.now += seconds

    clock = Clock()
    monkeypatch.setattr(opencode, "_clock", clock)
    monkeypatch.setattr(opencode, "_sleep", clock.sleep)
    calls = []
    ready = metadata_capture("ready")

    def observe(args, **kwargs):
        calls.append((args, kwargs))
        if args[:2] == ["agent", "list"]:
            return {
                "result": {
                    "agents": [
                        {
                            "agent": "opencode",
                            "pane_id": d.pane,
                            "name": d.name,
                            "agent_status": "idle",
                            "interactive_ready": True,
                        }
                    ]
                }
            }
        if args[:2] == ["pane", "process-info"]:
            return {
                "result": {
                    "process_info": {
                        "foreground_processes": [
                            {
                                "pid": 42,
                                "cwd": d.checkout,
                                "argv": ["opencode", "--session", d.session, "--auto"],
                            }
                        ]
                    }
                }
            }
        assert args[:2] == ["pane", "read"]
        return {"raw": ready}

    return d, clock, calls, observe


def test_pending_then_overslept_deadline_never_starts_another_observation(
    deadline_env, monkeypatch
):
    d, clock, calls, observe = deadline_env
    pending = metadata_capture("startup")
    reads = []

    def responses(args, **kwargs):
        answer = observe(args, **kwargs)
        if args[:2] == ["pane", "read"]:
            reads.append(clock.now)
            clock.now += 29.5 if len(reads) == 1 else 1.0
            return {"raw": pending} if len(reads) == 1 else answer
        return answer

    def oversleep(seconds):
        clock.sleeps.append(seconds)
        clock.now += 1.0  # Scheduler overrun: not an increment on reading the clock.

    monkeypatch.setattr(opencode, "_sleep", oversleep)
    with pytest.raises(opencode.HerdrError, match="rendered-input-timeout; no prompt sent"):
        opencode.wait_ready(d, run=responses)
    assert len(reads) == 1
    assert len(calls) == 3  # No identity/process/screen calls after expiry.
    assert clock.sleeps == [0.5]


@pytest.mark.parametrize("phase", ["agent", "process", "screen"])
@pytest.mark.parametrize("finished_at", [30.0, 30.5])
def test_observation_at_or_after_deadline_never_admits_ready(deadline_env, phase, finished_at):
    d, clock, calls, observe = deadline_env
    commands = {
        "agent": ["agent", "list"],
        "process": ["pane", "process-info"],
        "screen": ["pane", "read"],
    }

    def slow(args, **kwargs):
        answer = observe(args, **kwargs)
        if args[:2] == commands[phase]:
            clock.now = finished_at
        return answer

    with pytest.raises(opencode.HerdrError, match="rendered-input-timeout; no prompt sent"):
        opencode.wait_ready(d, run=slow)
    assert len(calls) == {"agent": 1, "process": 2, "screen": 3}[phase]


@pytest.mark.parametrize("budget", [0.0, -1.0])
def test_expired_deadline_before_first_observation_sends_nothing(deadline_env, monkeypatch, budget):
    d, _, calls, observe = deadline_env
    monkeypatch.setattr(opencode, "TIMEOUT", budget)
    with pytest.raises(opencode.HerdrError, match="rendered-input-timeout; no prompt sent"):
        opencode.wait_ready(d, run=observe)
    assert calls == []


def test_ready_just_before_deadline_is_admitted(deadline_env):
    d, clock, _, observe = deadline_env

    def slow(args, **kwargs):
        answer = observe(args, **kwargs)
        if args[:2] == ["pane", "read"]:
            clock.now = 29.999
        return answer

    assert opencode.wait_ready(d, run=slow)["pid"] == 42


def test_native_observations_each_receive_only_remaining_budget(deadline_env, monkeypatch):
    d, clock, _, observe = deadline_env
    timeouts = []
    durations = iter([0.4, 0.6, 0.1])

    def native(argv, **kwargs):
        timeouts.append(kwargs["timeout"])
        answer = observe(argv[1:])
        clock.now += next(durations)
        stdout = answer["raw"] if "raw" in answer else json.dumps(answer)
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    monkeypatch.setattr(_herdr.subprocess, "run", native)
    assert opencode.wait_ready(d)["pid"] == 42
    assert timeouts == pytest.approx([30.0, 29.6, 29.0])


def test_native_observation_timeout_never_proceeds_to_next_call(deadline_env, monkeypatch):
    d, clock, _, _ = deadline_env
    calls = []

    def native(argv, **kwargs):
        calls.append(argv)
        clock.now += kwargs["timeout"]
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr(_herdr.subprocess, "run", native)
    with pytest.raises(opencode.HerdrError, match="rendered-input-timeout; no prompt sent"):
        opencode.wait_ready(d)
    assert calls == [["herdr", "agent", "list"]]
    assert clock.now == 30.0
