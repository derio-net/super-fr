"""Captured screens with labelled synthetic roster/process inputs; no live mutation."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fr.triage.operation_lock import replacement_scope_lock
from fr_herdr import managed, replacement

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/herdr"


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "server"))
    monkeypatch.delenv("HERDR_PANE_ID", raising=False)
    d = managed.Descriptor(
        server=managed.server_identity(),
        pane="p",
        name="b",
        item="org/repo/run/batch-one",
        role="batch",
        branch="feat/one",
        checkout=str(tmp_path),
        model="openai/model",
    )
    agent = {
        "pane_id": "p",
        "name": "b",
        "agent": "opencode",
        "agent_status": "done",
        "interactive_ready": True,
    }
    responses = {
        "list": {"result": {"agents": [agent]}},
        "process-info": {
            "result": {
                "process_info": {
                    "foreground_processes": [
                        {
                            "pid": 2,
                            "argv": ["opencode", "--model", "openai/model"],
                            "cwd": d.checkout,
                        }
                    ]
                }
            }
        },
        "read": json.loads((FIXTURES / "opencode/final-idle.json").read_text()),
    }
    calls = []

    def run(args):
        calls.append(args)
        assert args[1] in responses, "inspection sent input"
        return responses[args[1]]

    monkeypatch.setattr(replacement, "_run_herdr", run)
    return d, responses, calls


def test_captured_completed_history_has_safe_empty_prompt(source):
    d, _, calls = source
    assert replacement.source_eligible(d)["process"]["pid"] == 2
    assert len(calls) == 3


def test_activation_can_observe_a_confirmed_busy_target_without_sending_input(source):
    d, responses, _ = source
    responses["list"]["result"]["agents"][0].update(agent_status="working", interactive_ready=False)
    assert replacement.observe(d, safe=False)["agent_status"] == "working"
    with pytest.raises(managed.ManagedError):
        replacement.observe(d)


def test_legacy_source_checkout_is_validated_but_target_must_use_primary(source, monkeypatch):
    d, responses, _ = source
    responses["process-info"]["result"]["process_info"]["foreground_processes"][0]["cwd"] = (
        "/repo/worktree"
    )
    monkeypatch.setattr(replacement, "stable_checkout", lambda p: d.checkout)
    assert replacement.source_eligible(d)["process"]["cwd"] == "/repo/worktree"
    with pytest.raises(managed.ManagedError):
        replacement.observe(d)


@pytest.mark.parametrize("screen", ["draft.json", "dialog.json"])
def test_captured_draft_and_overlay_refuse_before_input(source, screen):
    d, responses, _ = source
    responses["read"] = json.loads((FIXTURES / "opencode" / screen).read_text())
    with pytest.raises(managed.ManagedError):
        replacement.source_eligible(d)


@pytest.mark.parametrize("defect", ["model", "cwd", "multiple", "self", "ambiguous", "unknown"])
def test_unknown_identity_or_foreground_refuses(source, monkeypatch, defect):
    d, responses, _ = source
    procs = responses["process-info"]["result"]["process_info"]["foreground_processes"]
    if defect == "model":
        procs[0]["argv"][-1] = "different"
    elif defect == "cwd":
        procs[0]["cwd"] = "/elsewhere"
    elif defect == "multiple":
        procs.append(dict(procs[0]))
    elif defect == "self":
        monkeypatch.setenv("HERDR_PANE_ID", d.pane)
    elif defect == "ambiguous":
        responses["list"]["result"]["agents"].append(dict(responses["list"]["result"]["agents"][0]))
    else:
        responses["list"]["result"]["agents"][0]["agent_status"] = "unknown"
    with pytest.raises(managed.ManagedError):
        replacement.source_eligible(d)


@pytest.mark.parametrize(
    "screen", ["screen-draft.json", "screen-background.json", "screen-subagent.json"]
)
def test_claude_uses_existing_input_and_background_rules(source, screen):
    d, responses, _ = source
    d = d.model_copy(update={"harness": "claude"})
    responses["list"]["result"]["agents"][0]["agent"] = "claude"
    responses["process-info"]["result"]["process_info"]["foreground_processes"][0]["argv"][0] = (
        "claude"
    )
    responses["read"] = json.loads((FIXTURES / "restart" / screen).read_text())
    with pytest.raises(managed.ManagedError):
        replacement.source_eligible(d)


def test_scope_lock_excludes_independent_writer_and_releases(
    tmp_path, native_herdr_cache, monkeypatch
):
    monkeypatch.setenv("FR_TRIAGE_LOCK_DIR", str(native_herdr_cache))
    script = (
        "from pathlib import Path; import sys\n"
        "from fr.triage.operation_lock import replacement_scope_lock\n"
        "from fr.triage.errors import TriageError\ntry:\n"
        " with replacement_scope_lock(Path(sys.argv[1])): sys.exit(0)\n"
        "except TriageError: sys.exit(3)\n"
    )
    with replacement_scope_lock(tmp_path):
        result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], timeout=20)
        assert result.returncode == 3
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], timeout=20)
    assert result.returncode == 0
