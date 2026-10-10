"""Captured input grounding plus explicitly synthetic operation/failure tests."""

import base64
import gzip
import hashlib
import json
from pathlib import Path

import pytest
from fr_herdr import managed, opencode

FIXTURES = Path(__file__).parents[1] / "fixtures/herdr/opencode"


def test_captured_process_identity_and_exited_shell():
    active = json.loads((FIXTURES / "final-idle-process.json").read_text())
    exited = json.loads((FIXTURES / "exited-process.json").read_text())
    assert opencode.process(active)["argv"] == ["opencode", "--model", "openai/gpt-6.1-sol"]
    assert opencode.shell_cwd(active) is None
    assert opencode.shell_cwd(exited) == "/Users/example/projects/super-fr"


@pytest.mark.parametrize("auto", [False, True])
def test_managed_model_identity_accepts_sessions_from_before_and_after_auto(auto):
    d = managed.Descriptor(
        server="server",
        pane="w1:p1",
        name="b-test",
        item="example/alpha/run/batch-test",
        role="batch",
        branch="feat/test",
        checkout="/work/alpha",
        model="openai/test",
    )
    argv = ["opencode", "--model", d.model]
    if auto:
        argv.append("--auto")
    assert opencode.model_matches({"argv": argv}, d)


@pytest.mark.parametrize(
    "name,reason",
    [
        ("idle-ready", None),
        ("final-idle", None),
        ("draft", "draft"),
        ("dialog", "dialog-or-unfocused"),
        ("subagent-working", "background-work"),
    ],
)
def test_captured_input_contract(name, reason):
    screen = json.loads((FIXTURES / f"{name}.json").read_text())["raw"]
    if name == "idle-ready":
        # Restore the original ANSI line from the SAME capture, not an invented layout.
        original = json.loads((FIXTURES / "placeholder-line.json").read_text())["raw"]
        screen = "\n".join(
            original if "Ask anything" in line else line for line in screen.splitlines()
        )
    assert opencode.input_reason(screen) == reason


def wide_capture(kind):
    data = json.loads((FIXTURES / f"wide-{kind}.json").read_text())
    raw = gzip.decompress(base64.b64decode(data["raw_gzip_base64"]))
    assert hashlib.sha256(raw).hexdigest() == data["sha256"]
    return raw.decode()


def test_real_wide_session_sidebar_is_outside_empty_input():
    assert opencode.input_reason(wide_capture("idle")) is None


def test_real_wide_session_draft_remains_a_refusal():
    assert opencode.input_reason(wide_capture("draft")) == "draft"


def test_real_wide_session_palette_remains_a_refusal():
    assert opencode.input_reason(wide_capture("palette")) is not None


def test_synthetic_unknown_wide_footer_is_not_accepted():
    # Deliberate negative mutation of a capture, never a claimed live observation.
    raw = wide_capture("idle")
    changed = raw.replace("•", "?")  # unknown wide-session footer marker
    assert changed != raw
    assert opencode.input_reason(changed) is not None


@pytest.mark.parametrize(
    "screen",
    ["", "synthetic blank startup", "synthetic permission dialog", "synthetic unknown layout"],
)
def test_unobserved_layouts_fail_closed(screen):
    assert opencode.input_reason(screen) is not None


def test_synthetic_transcript_box_is_not_current_input():
    screen = json.loads((FIXTURES / "final-idle.json").read_text())["raw"]
    assert opencode.input_reason(screen + "\nsynthetic new prompt not yet rendered") is not None


@pytest.fixture
def operation(tmp_path, monkeypatch, native_herdr_cache):
    """Explicitly synthetic state machine; no session or repo is controlled."""
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "herdr.sock"))
    monkeypatch.delenv("HERDR_PANE_ID", raising=False)
    d = managed.Descriptor(
        server=managed.server_identity(),
        pane="w1:p1",
        name="b-test",
        item="example/alpha/run/batch-test",
        role="batch",
        branch="feat/test",
        checkout=str(tmp_path),
        model="openai/test",
    )
    managed.save(d)
    monkeypatch.setattr(managed, "reconstruct", lambda d: "HOLD for operator review")
    screen = json.loads((FIXTURES / "final-idle.json").read_text())["raw"]

    class Synthetic:
        phase = "source"
        status = "done"
        prompt_screen = screen
        failure = ""
        calls = []

        def __init__(self):
            self.calls = []

        def __call__(self, args):
            self.calls.append(args)
            verb = " ".join(args[:2])
            if self.failure == verb:
                raise opencode.HerdrError("synthetic failure")
            if verb == "agent list":
                return {
                    "result": {
                        "agents": [
                            {
                                "agent": "opencode",
                                "pane_id": d.pane,
                                "name": d.name,
                                "agent_status": self.status,
                                "interactive_ready": True,
                            }
                        ]
                    }
                }
            if verb == "pane process-info":
                proc = {"argv": ["opencode", "--model", d.model], "pid": 2, "cwd": d.checkout}
                if self.phase == "shell":
                    proc = {"argv": ["-zsh"], "pid": 1, "cwd": d.checkout}
                return {
                    "result": {"process_info": {"shell_pid": 1, "foreground_processes": [proc]}}
                }
            if verb == "pane read":
                return {"raw": self.prompt_screen}
            if verb == "pane send-keys":
                self.phase = "shell"
            if verb == "agent start":
                self.phase = "target"
            return {}

    fake = Synthetic()
    monkeypatch.setattr(opencode, "_run_herdr", fake)
    return d, fake


def test_fresh_restart_preserves_pane_name_model_and_hold(operation):
    d, fake = operation
    assert opencode.restart_pane(d.pane, yes=True, exclude=set())[0] == "ok"
    assert ["pane", "send-text", d.pane, "exit"] in fake.calls
    start = next(c for c in fake.calls if c[:2] == ["agent", "start"])
    assert start == [
        "agent",
        "start",
        d.name,
        "--kind",
        "opencode",
        "--pane",
        d.pane,
        "--",
        "--model",
        d.model,
        "--auto",
    ]
    assert "--resume" not in str(fake.calls)
    assert "HOLD for operator review" in str(fake.calls)
    assert managed.load(d.pane).checkpoint == "active"


@pytest.mark.parametrize(
    "kind",
    [
        "self",
        "excluded",
        "working",
        "blocked",
        "unknown",
        "draft",
        "dialog",
        "blank",
        "pending",
        "missing",
    ],
)
def test_synthetic_unsafe_restart_sends_nothing(operation, monkeypatch, kind):
    d, fake = operation
    exclude = set()
    if kind == "self":
        monkeypatch.setenv("HERDR_PANE_ID", d.pane)
    elif kind == "excluded":
        exclude.add(d.pane)
    elif kind in {"working", "blocked", "unknown"}:
        fake.status = kind
    elif kind in {"draft", "dialog"}:
        fake.prompt_screen = json.loads((FIXTURES / f"{kind}.json").read_text())["raw"]
    elif kind == "blank":
        fake.prompt_screen = ""
    elif kind == "pending":
        managed.save(d.model_copy(update={"checkpoint": "uptake-confirmed"}))
    elif kind == "missing":
        managed.path_for(d.pane).unlink()
    assert opencode.restart_pane(d.pane, yes=True, exclude=exclude)[0] == "skip"
    assert not any(
        c[:2] in [["pane", "send-text"], ["pane", "send-keys"], ["agent", "start"]]
        for c in fake.calls
    )


@pytest.mark.parametrize(
    "failure", ["pane send-text", "pane send-keys", "agent start", "agent prompt"]
)
def test_synthetic_failure_leaves_nonactive_checkpoint_without_cleanup(operation, failure):
    d, fake = operation
    fake.failure = failure
    verdict, detail, recovery = opencode.restart_pane(d.pane, yes=True, exclude=set())
    assert verdict == "fail" and "synthetic failure" in detail and recovery
    assert " --auto;" in recovery
    assert managed.load(d.pane).checkpoint != "active"
    assert "close" not in str(fake.calls)
    count = len(fake.calls)
    assert opencode.restart_pane(d.pane, yes=True, exclude=set())[0] == "skip"
    assert not any(c[:2] == ["pane", "send-text"] for c in fake.calls[count:])


def test_synthetic_shell_must_be_foreground_and_cwd_known():
    info = {
        "result": {
            "process_info": {
                "shell_pid": 1,
                "foreground_processes": [{"argv": ["zsh"], "pid": 2, "cwd": "/base"}],
            }
        }
    }
    assert opencode.shell_cwd(info) is None


def test_lock_loser_writes_and_sends_nothing(operation):
    d, fake = operation
    before = managed.path_for(d.pane).read_bytes()
    with managed.pane_lock(d.pane):
        assert opencode.restart_pane(d.pane, yes=True, exclude=set())[0] == "skip"
    assert managed.path_for(d.pane).read_bytes() == before
    assert not any(c[:2] == ["pane", "send-text"] for c in fake.calls)


def test_synthetic_literal_placeholder_draft_is_not_empty():
    screen = json.loads((FIXTURES / "idle-ready.json").read_text())["raw"]
    # The plaintext projection cannot distinguish typed placeholder from ghost text.
    assert opencode.input_reason(screen) is not None


def test_synthetic_foreground_shell_timeout_is_bounded(operation, monkeypatch):
    d, fake = operation
    original = fake.__call__

    def stuck(args):
        result = original(args)
        if args[:2] == ["pane", "send-keys"]:
            fake.phase = "source"
        return result

    monkeypatch.setattr(opencode, "_run_herdr", stuck)
    ticks = iter(range(100))
    monkeypatch.setattr(opencode, "_clock", lambda: float(next(ticks)))
    monkeypatch.setattr(opencode, "_sleep", lambda seconds: None)
    result = opencode.restart_pane(d.pane, yes=True, exclude=set())
    assert result[0] == "fail" and "exit-timeout" in result[1]
    assert not any(c[:2] == ["agent", "start"] for c in fake.calls)


def test_synthetic_exit_dialog_is_left_untouched(operation, monkeypatch):
    d, fake = operation
    original = fake.__call__

    def dialog(args):
        answer = original(args)
        if args[:2] == ["pane", "send-keys"]:
            fake.phase = "source"
            fake.prompt_screen = json.loads((FIXTURES / "dialog.json").read_text())["raw"]
        return answer

    monkeypatch.setattr(opencode, "_run_herdr", dialog)
    verdict, detail, recovery = opencode.restart_pane(d.pane, yes=True, exclude=set())
    assert verdict == "fail" and "exit-dialog" in detail
    assert sum(c[:2] == ["pane", "send-keys"] for c in fake.calls) == 1


def test_synthetic_metadata_failure_after_uptake_never_retries(operation, monkeypatch):
    d, fake = operation
    save = managed.save

    def fail_active(current):
        if current.checkpoint == "active":
            raise OSError("synthetic disk full")
        save(current)

    monkeypatch.setattr(managed, "save", fail_active)
    assert opencode.restart_pane(d.pane, yes=True, exclude=set())[0] == "fail"
    assert managed.load(d.pane).checkpoint == "uptake-confirmed"
    assert opencode.restart_pane(d.pane, yes=True, exclude=set())[0] == "skip"


def test_per_pane_failure_does_not_stop_roster(monkeypatch):
    from fr_herdr import restart

    def roster(args):
        if args[:2] == ["agent", "list"]:
            return {
                "result": {"agents": [{"agent": "opencode", "pane_id": p} for p in ("one", "two")]}
            }
        return {"result": {"tabs": []}}

    seen = []

    def attempt(pane, **kwargs):
        seen.append(pane)
        return (
            ("fail", "synthetic startup failure", "inspect") if pane == "one" else ("ok", "", None)
        )

    monkeypatch.setattr(restart, "_run_herdr", roster)
    monkeypatch.setattr(opencode, "restart_pane", attempt)
    report = restart.restart_idle(yes=True)
    assert seen == ["one", "two"] and report.failed
