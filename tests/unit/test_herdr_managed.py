"""Synthetic durable-state tests; herdr wire captures are tested separately."""

import json
import subprocess
import sys

import pytest
from fr_herdr import managed


@pytest.fixture
def descriptor(tmp_path, monkeypatch, native_herdr_cache):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "herdr.sock"))
    return managed.Descriptor(
        server=managed.server_identity(),
        pane="w1:p1",
        name="b-test",
        item="example/alpha/run/batch-test",
        role="batch",
        branch="feat/test",
        checkout=str(tmp_path),
        model="openai/test",
    )


def test_atomic_descriptor_roundtrip_and_corruption(descriptor):
    assert managed.load(descriptor.pane) is None
    managed.save(descriptor)
    assert managed.load(descriptor.pane) == descriptor
    managed.path_for(descriptor.pane).write_text("broken")
    with pytest.raises(managed.ManagedError):
        managed.load(descriptor.pane)


def test_server_identity_separates_same_pane(descriptor, monkeypatch):
    managed.save(descriptor)
    monkeypatch.setenv("HERDR_SOCKET_PATH", "/other/server.sock")
    assert managed.load(descriptor.pane) is None


def test_missing_checkpoint_is_not_active(descriptor):
    managed.save(descriptor)
    path = managed.path_for(descriptor.pane)
    raw = json.loads(path.read_text())
    del raw["checkpoint"]
    path.write_text(json.dumps(raw))
    with pytest.raises(managed.ManagedError, match="checkpoint"):
        managed.load(descriptor.pane)


def test_pane_lock_is_exclusive_and_released(descriptor):
    with managed.pane_lock(descriptor.pane):
        with pytest.raises(managed.ManagedError, match="locked"):
            with managed.pane_lock(descriptor.pane):
                pytest.fail("loser entered")
    with managed.pane_lock(descriptor.pane):
        pass


def test_pane_lock_excludes_an_independent_process(descriptor):
    script = (
        "import sys; from fr_herdr import managed\n"
        "try:\n"
        " with managed.pane_lock(sys.argv[1]): sys.exit(0)\n"
        "except managed.ManagedError: sys.exit(3)\n"
    )
    with managed.pane_lock(descriptor.pane):
        result = subprocess.run([sys.executable, "-c", script, descriptor.pane], timeout=20)
        assert result.returncode == 3
    result = subprocess.run([sys.executable, "-c", script, descriptor.pane], timeout=20)
    assert result.returncode == 0


def test_unenforced_os_lock_is_refused_before_entering(descriptor, monkeypatch):
    """Synthetic probe result models the actually observed host-share flock defect."""
    monkeypatch.setattr(
        managed.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0)
    )
    with pytest.raises(managed.ManagedError, match="does not enforce"):
        with managed.pane_lock(descriptor.pane):
            pytest.fail("unsafe filesystem admitted an owner")


def test_delivered_hold_and_unfinished_cursor(descriptor, monkeypatch, tmp_path):
    monkeypatch.setattr(managed, "branch_workspace", lambda d: tmp_path)
    runs = tmp_path / "docs/superpowers/runs"
    runs.mkdir(parents=True)
    (runs / "run.yaml").write_text(
        "run: run\nbranch: feat/test\ncursor: deliver\nsteps:\n  deliver:\n    state: done\n"
    )
    assert "HOLD" in managed.reconstruct(descriptor)
    (runs / "run.yaml").write_text(
        "run: run\nbranch: feat/test\ncursor: implement-phase\n"
        "steps:\n  implement-phase:\n    state: running\n"
    )
    brief = managed.reconstruct(descriptor)
    assert "reconcile" in brief and "implement-phase" in brief
    assert "/fr-goal" not in brief


def test_current_handback_precedes_hold_but_obsolete_does_not(descriptor, monkeypatch, tmp_path):
    monkeypatch.setattr(managed, "branch_workspace", lambda d: tmp_path)
    current = descriptor.model_copy(update={"conflict_head": "abc", "conflict_brief": "six steps"})
    monkeypatch.setattr(managed, "conflict_current", lambda d: True)
    assert "six steps" in managed.reconstruct(current)
    monkeypatch.setattr(managed, "conflict_current", lambda d: False)
    assert "six steps" not in managed.reconstruct(current)


def test_closeout_reuses_pickup_gate(descriptor, monkeypatch):
    d = descriptor.model_copy(update={"role": "closeout", "brief": "pickup original"})
    monkeypatch.setattr(managed, "pickup", lambda d: "merge-gated pickup")
    assert managed.reconstruct(d) == "merge-gated pickup"

    def refuse(d):
        raise managed.ManagedError("not merged")

    monkeypatch.setattr(managed, "pickup", refuse)
    with pytest.raises(managed.ManagedError, match="not merged"):
        managed.reconstruct(d)


@pytest.mark.parametrize(
    "state,mergeable,expected",
    [
        ("OPEN", "CONFLICTING", True),
        ("OPEN", "MERGEABLE", False),
        ("MERGED", "CONFLICTING", False),
    ],
)
def test_live_conflict_reads_the_forge_adapter(descriptor, monkeypatch, state, mergeable, expected):
    """Synthetic GhClient protocol answers, not fabricated wire captures."""
    d = descriptor.model_copy(update={"conflict_head": "abc"})
    monkeypatch.setattr(managed, "_git", lambda d, *args: "abc")

    class Client:
        def list_prs_by_head(self, repo, branch):
            assert repo == "example/alpha" and branch == "feat/test"
            return [{"number": 1}]

        def pr_view(self, repo, number):
            return {"state": state, "mergeable": mergeable, "head_oid": "abc"}

    monkeypatch.setattr(managed, "client_for", lambda root: Client())
    assert managed.conflict_current(d) is expected
