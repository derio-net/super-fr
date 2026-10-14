"""Recovery observations derived from captured global rosters; no clients launch."""

import copy
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from fr_dispatch.protocols import ReplacementRequest
from fr_herdr import managed
from fr_herdr.runner import agent_name

CAPTURES = Path(__file__).parents[1] / "fixtures/herdr/recovery-capture"


@pytest.fixture
def recovery_env(tmp_path, monkeypatch, native_herdr_cache):
    from fr_herdr import recovery, replacement

    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_PANE_ID", "caller")
    monkeypatch.setenv("HERDR_WORKSPACE_ID", "w1T")
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "server"))
    monkeypatch.setattr(recovery, "stable_checkout", lambda p: p)
    monkeypatch.setattr(replacement, "stable_checkout", lambda p: p)
    monkeypatch.setattr(managed, "branch_workspace", lambda d: tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    runs = tmp_path / "docs/superpowers/runs"
    runs.mkdir(parents=True)
    (runs / "run.yaml").write_text(
        "run: fixture\nbranch: feat/original\ncursor: brainstorm\n"
        "steps:\n  brainstorm: {state: running}\n"
    )
    responses = {
        "pane": json.loads((CAPTURES / "pane-list.json").read_text()),
        "tab": json.loads((CAPTURES / "tab-list.json").read_text()),
        "agent": {"result": {"agents": []}},
    }
    calls = []

    def run(argv):
        calls.append(argv)
        assert argv[1] == "list", argv
        return copy.deepcopy(responses[argv[0]])

    monkeypatch.setattr(recovery, "_run_herdr", run)
    item = "example/alpha/run/batch-one"
    request = ReplacementRequest(
        item,
        "closed",
        agent_name(item),
        "feat/original",
        str(tmp_path),
        "claude",
        "old",
        "opencode",
        "openai/new",
        "attempt-1",
        recover=True,
    )
    return recovery.Operation(request), responses, calls, runs


def test_absent_preview_is_read_only(recovery_env):
    op, _, calls, _ = recovery_env
    assert op.inspect().status == "absent"
    assert calls == [["pane", "list"], ["tab", "list"], ["agent", "list"]]
    assert managed.load("closed") is None
    assert not list(managed.cache_dir().glob("*.json"))


@pytest.mark.parametrize("kind", ["pane", "tab", "agent"])
@pytest.mark.parametrize(
    "bad", [{}, {"result": {}}, {"result": {"panes": None, "tabs": None, "agents": None}}]
)
def test_unknown_rosters_refuse(recovery_env, kind, bad):
    op, responses, _, _ = recovery_env
    responses[kind] = bad
    with pytest.raises(managed.ManagedError, match="roster"):
        op.inspect()
    assert not list(managed.cache_dir().glob("*.json"))


@pytest.mark.parametrize("match", ["pane", "label", "name", "count"])
def test_survivors_reused_panes_and_incomplete_join_refuse(recovery_env, match):
    op, responses, _, _ = recovery_env
    if match == "pane":
        responses["pane"]["result"]["panes"][0]["pane_id"] = "closed"
    elif match == "label":
        responses["tab"]["result"]["tabs"][0]["label"] = op.request.item
    elif match == "count":
        responses["tab"]["result"]["tabs"][0]["pane_count"] = 2
    else:
        responses["agent"]["result"]["agents"] = [
            {"pane_id": "w9:pR", "tab_id": "w9:tG", "name": op.name}
        ]
    with pytest.raises(managed.ManagedError):
        op.inspect()
    assert not list(managed.cache_dir().glob("*.json"))


@pytest.mark.parametrize("case", ["missing", "ambiguous", "unreadable", "wrong-branch"])
def test_cursor_truth_refuses_before_effects(recovery_env, case):
    op, _, _, runs = recovery_env
    path = runs / "run.yaml"
    if case == "missing":
        path.unlink()
    elif case == "ambiguous":
        (runs / "other.yaml").write_text(path.read_text())
    elif case == "unreadable":
        path.write_text("[")
    else:
        path.write_text(path.read_text().replace("feat/original", "feat/other"))
    with pytest.raises(managed.ManagedError, match="cursor"):
        op.inspect()


def test_self_and_missing_workspace_refuse(recovery_env, monkeypatch):
    from fr_herdr import recovery

    op, _, _, _ = recovery_env
    with pytest.raises(managed.ManagedError, match="caller-self"):
        recovery.Operation(replace(op.request, pane="caller")).inspect()
    monkeypatch.setattr(
        managed,
        "branch_workspace",
        lambda d: (_ for _ in ()).throw(managed.ManagedError("missing workspace")),
    )
    with pytest.raises(managed.ManagedError, match="workspace"):
        op.inspect()


def test_dirty_work_is_preserved(recovery_env):
    op, _, _, runs = recovery_env
    path = runs.parent.parent.parent / "dirty.txt"
    path.write_text("uncommitted work")
    op.inspect()
    assert path.read_text() == "uncommitted work"


@pytest.fixture
def execution(recovery_env, monkeypatch):
    from fr_herdr import recovery, replacement

    op, responses, calls, runs = recovery_env
    original = recovery._run_herdr
    effects = []

    def allocate(argv):
        if argv[:2] != ["tab", "create"]:
            return original(argv)
        intent = recovery.load_intent(op.request.item, op.request.pane)
        assert intent and intent.checkpoint == "allocation-pending"
        assert intent.request == op.request
        effects.append("allocate")
        pane = copy.deepcopy(responses["pane"]["result"]["panes"][-2])
        pane.update(pane_id="w1T:pNEW", tab_id="w1T:tNEW")
        tab = copy.deepcopy(responses["tab"]["result"]["tabs"][-2])
        tab.update(tab_id="w1T:tNEW", label=op.request.item)
        responses["pane"]["result"]["panes"].append(pane)
        responses["tab"]["result"]["tabs"].append(tab)
        # Captured workspace-create's root_pane shape; derived allocation variant.
        return {"result": {"root_pane": pane, "tab": tab}}

    monkeypatch.setattr(recovery, "_run_herdr", allocate)
    monkeypatch.setattr(replacement, "launch_target", lambda d: effects.append("launch"))
    monkeypatch.setattr(replacement, "submit", lambda d, brief: effects.append("prompt"))
    monkeypatch.setattr(
        replacement,
        "observe",
        lambda d, **kw: {"agent_session": {"agent": "opencode", "kind": "id", "value": "ses_new"}},
    )
    return op, effects, responses, runs


def test_allocation_intent_and_single_input(execution):
    from fr_herdr import recovery

    op, effects, _, _ = execution
    with op.ownership():
        op.inspect()
        op.prepare()
        assert op.target_pane == "w1T:pNEW"
        assert managed.load(op.target_pane).checkpoint == "prepared"
        assert op.execute().ok
        assert managed.load(op.target_pane).session == "ses_new"
        op.activate(success=True)
        assert recovery.load_intent(op.request.item, op.request.pane).checkpoint == "active"
        with pytest.raises(managed.ManagedError):
            op.execute()
    assert effects == ["allocate", "launch", "prompt"]


@pytest.mark.parametrize(
    "boundary", ["lost-response", "invalid-response", "descriptor-save", "intent-target-save"]
)
def test_uncertain_allocation_discovered_without_reallocation(execution, monkeypatch, boundary):
    from fr_herdr import recovery

    op, effects, _, _ = execution
    allocate = recovery._run_herdr
    save = managed.save
    save_intent = recovery.save_intent

    def lost(argv):
        result = allocate(argv)
        if argv[:2] == ["tab", "create"]:
            if boundary == "lost-response":
                raise OSError("lost response")
            if boundary == "invalid-response":
                return {"result": {}}
        return result

    def fail_descriptor(d):
        if boundary == "descriptor-save":
            raise OSError("descriptor write failed")
        save(d)

    def fail_intent(intent):
        if boundary == "intent-target-save" and intent.target:
            raise OSError("target write failed")
        save_intent(intent)

    with op.ownership():
        op.inspect()
        monkeypatch.setattr(recovery, "_run_herdr", lost)
        monkeypatch.setattr(managed, "save", fail_descriptor)
        monkeypatch.setattr(recovery, "save_intent", fail_intent)
        with pytest.raises((OSError, managed.ManagedError)):
            op.prepare()
    monkeypatch.setattr(managed, "save", save)
    monkeypatch.setattr(recovery, "save_intent", save_intent)
    pending = recovery.pending(op.request.item, op.request.pane)
    assert pending.attempt == op.request.attempt
    repair = recovery.Operation(pending)
    with repair.ownership():
        # Shell confirmation is a derived process-info observation, not an input.
        monkeypatch.setattr(
            replacement_observer := __import__("fr_herdr.replacement", fromlist=["observe"]),
            "observe",
            lambda *a, **kw: (_ for _ in ()).throw(managed.ManagedError("no agent")),
        )
        shell = json.loads((CAPTURES / "shell-process-info.json").read_text())
        monkeypatch.setattr(replacement_observer, "_run_herdr", lambda argv: shell)
        result = repair.reconcile()
        assert not result.ok and result.pane == "w1T:pNEW"
        repair.activate(success=False)
    assert effects == ["allocate"]


@pytest.mark.parametrize(
    "checkpoint",
    [
        "target-ready",
        "submission-started",
        "submission-uncertain",
        "uptake-confirmed",
        "batch-committed",
        "active",
    ],
)
def test_crash_checkpoints_never_replay_input(execution, monkeypatch, checkpoint):
    from fr_herdr import recovery

    op, effects, _, _ = execution
    with op.ownership():
        op.prepare()
        op._checkpoint(checkpoint)
        if checkpoint in {"uptake-confirmed", "batch-committed", "active"}:
            op.target = op.target.model_copy(update={"session": "ses_new"})
            managed.save(op.target)
        repair = recovery.Operation(
            recovery.pending(op.request.item, op.request.pane) or op.request
        )
        if checkpoint in {"uptake-confirmed", "batch-committed", "active"}:
            assert repair.reconcile().ok
        else:
            with pytest.raises(managed.ManagedError, match="uptake"):
                repair.reconcile()
    assert effects == ["allocate"]


@pytest.mark.parametrize("state", ["running", "done", "pending"])
def test_recovery_hold_precedes_all_continuation(execution, monkeypatch, state):
    op, _, _, runs = execution
    (runs / "run.yaml").write_text(
        "run: fixture\nbranch: feat/original\ncursor: brainstorm\nsteps:\n"
        f"  brainstorm: {{state: {state}}}\n  deliver: {{state: {state}}}\n"
    )
    monkeypatch.setattr(
        managed, "conflict_current", lambda d: pytest.fail("HOLD must precede conflict truth")
    )
    d = op.target.model_copy(
        update={"conflict_head": "abc", "conflict_brief": "Resume the conflict now"}
    )
    brief = managed.reconstruct(d)
    assert brief.startswith("HOLD") and "fixture" in brief
    assert "acknowledge/report" in brief
    assert "fr run advance" not in brief and "claim --abandoned" not in brief
    assert "Resume the conflict now" not in brief


def test_observed_autonomy_and_session_required(recovery_env, monkeypatch):
    from fr_herdr import opencode, replacement

    op, _, _, _ = recovery_env
    agent = {
        "pane_id": op.target.pane,
        "name": op.name,
        "agent": "opencode",
        "agent_status": "done",
        "interactive_ready": True,
    }
    proc = {"pid": 5, "cwd": op.target.checkout, "argv": ["opencode", "--model", "openai/new"]}

    def run(argv):
        if argv[:2] == ["agent", "list"]:
            return {"result": {"agents": [agent]}}
        if argv[:2] == ["pane", "process-info"]:
            return {"result": {"process_info": {"foreground_processes": [proc]}}}
        return {"raw": ""}

    monkeypatch.setattr(replacement, "_run_herdr", run)
    with pytest.raises(managed.ManagedError, match="autonomous"):
        replacement.observe(op.target, safe=False)
    with pytest.raises(managed.ManagedError, match="autonomous"):
        opencode.eligible(op.target.model_copy(update={"checkpoint": "active"}), set(), run=run)
    proc["argv"].append("--auto")
    with pytest.raises(managed.ManagedError, match="session"):
        op._target_identity()
    agent["agent_session"] = {"agent": "opencode", "kind": "id", "value": "ses_new"}
    op._target_identity()
    assert op.target.session == "ses_new"


def test_intent_write_failure_precedes_allocation(execution, monkeypatch):
    from fr_herdr import recovery

    op, effects, _, _ = execution
    monkeypatch.setattr(
        recovery, "save_intent", lambda d: (_ for _ in ()).throw(OSError("disk full"))
    )
    with op.ownership(), pytest.raises(OSError):
        op.prepare()
    assert effects == []


def test_absence_rechecked_under_owner(execution):
    op, effects, responses, _ = execution
    op.inspect()
    responses["pane"]["result"]["panes"][0]["pane_id"] = op.request.pane
    with op.ownership(), pytest.raises(managed.ManagedError, match="survives"):
        op.prepare()
    assert effects == []


@pytest.mark.parametrize(
    "boundary", ["launch", "prompt", "target-ready", "submission-started", "uptake-confirmed"]
)
def test_effect_and_checkpoint_failures_preserve_pending_no_replay(
    execution, monkeypatch, boundary
):
    from fr_herdr import recovery, replacement

    op, effects, _, _ = execution
    save = managed.save

    def fail_save(d):
        if d.checkpoint == boundary:
            raise OSError("injected checkpoint failure")
        save(d)

    with op.ownership():
        op.prepare()
        monkeypatch.setattr(managed, "save", fail_save)
        if boundary in {"launch", "prompt"}:

            def fail(*args):
                effects.append(boundary)
                raise OSError("injected effect failure")

            monkeypatch.setattr(
                replacement, "launch_target" if boundary == "launch" else "submit", fail
            )
        result = op.execute()
        assert not result.ok
    monkeypatch.setattr(managed, "save", save)
    repair = recovery.Operation(recovery.pending(op.request.item, op.request.pane))
    with repair.ownership(), pytest.raises(managed.ManagedError, match="uptake"):
        repair.reconcile()
    assert (
        effects.count("allocate") == 1
        and effects.count("launch") <= 1
        and effects.count("prompt") <= 1
    )


def test_changed_session_cannot_certify_repair(execution, monkeypatch):
    from fr_herdr import recovery, replacement

    op, effects, _, _ = execution
    with op.ownership():
        op.prepare()
        assert op.execute().ok
    repair = recovery.Operation(recovery.pending(op.request.item, op.request.pane))
    monkeypatch.setattr(
        replacement,
        "observe",
        lambda *a, **k: {
            "agent_session": {"agent": "opencode", "kind": "id", "value": "different"}
        },
    )
    monkeypatch.setattr(replacement, "_run_herdr", lambda argv: {})
    with repair.ownership(), pytest.raises(managed.ManagedError, match="session"):
        repair.reconcile()
    assert effects == ["allocate", "launch", "prompt"]


def test_empty_complete_rosters_are_positive_absence(recovery_env):
    op, responses, _, _ = recovery_env
    for kind in ("pane", "tab", "agent"):
        responses[kind]["result"][kind + "s"] = []
    assert op.inspect().status == "absent"


def test_failed_roster_read_never_means_absence(execution, monkeypatch):
    from fr_herdr import recovery

    op, effects, _, _ = execution
    monkeypatch.setattr(
        recovery, "_run_herdr", lambda argv: (_ for _ in ()).throw(OSError("read failed"))
    )
    with op.ownership(), pytest.raises(OSError, match="read failed"):
        op.prepare()
    assert effects == []


def test_source_owner_contention_sends_nothing(execution):
    op, effects, _, _ = execution
    with managed.pane_lock(op.request.pane), pytest.raises(managed.ManagedError, match="locked"):
        with op.ownership():
            op.prepare()
    assert effects == []


def test_activation_write_failure_repair_is_input_free(execution, monkeypatch):
    from fr_herdr import recovery

    op, effects, _, _ = execution
    save = recovery.save_intent
    with op.ownership():
        op.prepare()
        assert op.execute().ok
        monkeypatch.setattr(
            recovery,
            "save_intent",
            lambda intent: (_ for _ in ()).throw(OSError("activation write failed")),
        )
        with pytest.raises(OSError):
            op.activate(success=True)
    monkeypatch.setattr(recovery, "save_intent", save)
    from fr_herdr.runner import HerdrRunner

    # A committed batch success uses the new effective handle even if activation failed.
    assert HerdrRunner().replacement_pending(op.request.item, op.target_pane).recover
    repair = recovery.Operation(recovery.pending(op.request.item, op.request.pane))
    with repair.ownership():
        assert repair.reconcile().ok
        repair.activate(success=True)
    assert effects == ["allocate", "launch", "prompt"]


def test_uncertain_allocation_ambiguous_roster_refuses_repair(execution, monkeypatch):
    from fr_herdr import recovery

    op, effects, responses, _ = execution
    with op.ownership():
        op.prepare()
    responses["tab"]["result"]["tabs"][0]["label"] = op.request.item
    repair = recovery.Operation(recovery.pending(op.request.item, op.request.pane))
    with repair.ownership(), pytest.raises(managed.ManagedError, match="ambiguous"):
        repair.reconcile()
    assert effects == ["allocate"]
