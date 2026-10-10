"""Actual initialized Claude/MCP process capture; synthetic negative perturbations."""

import copy
import json
from pathlib import Path

import pytest
from fr_herdr import managed, replacement

FIXTURES = Path(__file__).parents[1] / "fixtures/herdr/restart"


@pytest.fixture
def captured_source(tmp_path, monkeypatch):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "socket"))
    monkeypatch.setenv("HERDR_PANE_ID", "caller")
    d = managed.Descriptor(
        server=managed.server_identity(),
        pane="p",
        name="b",
        item="org/repo/run/batch-test",
        role="batch",
        branch="feat/test",
        checkout="/disposable/base",
        harness="claude",
        model="haiku",
    )
    info = json.loads((FIXTURES / "claude-mcp-process.json").read_text())
    screen = json.loads((FIXTURES / "screen-empty.json").read_text())
    calls = []

    def run(args):
        calls.append(args)
        if args[:2] == ["agent", "list"]:
            # Synthetic roster joins captured process identity to this sandbox descriptor.
            return {
                "result": {
                    "agents": [
                        {
                            "pane_id": "p",
                            "name": "b",
                            "agent": "claude",
                            "agent_status": "idle",
                            "interactive_ready": True,
                        }
                    ]
                }
            }
        if args[:2] == ["pane", "process-info"]:
            return info
        if args[:2] == ["pane", "read"]:
            return screen
        pytest.fail("observer sent input")

    monkeypatch.setattr(replacement, "_run_herdr", run)
    return d, info, calls


def test_captured_native_mcp_sidecar_does_not_hide_the_unique_claude_root(captured_source):
    d, _, calls = captured_source
    observed = replacement.observe(d)
    assert observed["process"]["argv"] == ["claude", "--model", "haiku"]
    assert observed["process"]["pid"] == 100
    assert all(
        c[:2] in (["agent", "list"], ["pane", "process-info"], ["pane", "read"]) for c in calls
    )


@pytest.mark.parametrize(
    "defect", ["other-node", "extra-args", "other-cwd", "other-group", "second-claude"]
)
def test_synthetic_unrecognized_or_ambiguous_foreground_children_still_refuse(
    captured_source, defect
):
    d, info, _ = captured_source
    group = info["result"]["process_info"]
    child = next(p for p in group["foreground_processes"] if p["argv"][0] == "node")
    root = next(p for p in group["foreground_processes"] if p["argv"][0] == "claude")
    if defect == "other-node":
        child["argv"][1] = "/unrecognized/other.cjs"
    elif defect == "extra-args":
        child["argv"].append("unrecognized")
    elif defect == "other-cwd":
        child["cwd"] = "/other/base"
    elif defect == "other-group":
        group["foreground_process_group_id"] = 999
    else:
        group["foreground_processes"].append(copy.deepcopy(root))
    with pytest.raises(managed.ManagedError):
        replacement.observe(d)
