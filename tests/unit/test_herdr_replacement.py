"""Synthetic operation/crash tests; not evidence of interactive client safety."""

from contextlib import contextmanager

import pytest
from fr_dispatch.protocols import ReplacementRequest, SessionReplacer
from fr_herdr import managed, replacement
from fr_herdr.runner import HerdrRunner

REAL_LOCK = managed.pane_lock


@pytest.fixture
def operation(tmp_path, monkeypatch):
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "server"))
    monkeypatch.setenv("FR_HERDR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_PANE_ID", "caller")
    monkeypatch.setattr(replacement, "stable_checkout", lambda p: p)
    monkeypatch.setattr(
        managed, "reconstruct", lambda d: "Recover durable cursor; HOLD if delivered"
    )
    calls = []
    source = {
        "pane_id": "p",
        "name": "b",
        "agent": "claude",
        "agent_status": "idle",
        "interactive_ready": True,
    }
    monkeypatch.setattr(replacement, "observe", lambda d, safe=True, **kwargs: dict(source))
    monkeypatch.setattr(replacement, "source_eligible", lambda d: dict(source))
    monkeypatch.setattr(replacement, "exit_to_shell", lambda d: calls.append(("exit", d.harness)))
    monkeypatch.setattr(
        replacement, "launch_target", lambda d: calls.append(("start", d.harness, d.model))
    )
    monkeypatch.setattr(replacement, "submit", lambda d, brief: calls.append(("prompt", brief)))

    @contextmanager
    def lock(pane):
        calls.append(("lock", pane))
        yield

    monkeypatch.setattr(managed, "pane_lock", lock)
    req = ReplacementRequest(
        "org/repo/run/batch-one",
        "p",
        "b",
        "feat/original",
        str(tmp_path),
        "claude",
        "old",
        "opencode",
        "openai/new",
        "a1",
    )
    return replacement.Operation(req), calls, source


def test_optional_protocol():
    assert isinstance(HerdrRunner(), SessionReplacer)


@pytest.mark.parametrize(
    "old,new", [("claude", "opencode"), ("opencode", "claude"), ("opencode", "opencode")]
)
def test_fresh_both_directions_and_model_only(operation, old, new):
    op, calls, source = operation
    from dataclasses import replace

    op = replacement.Operation(replace(op.request, old_harness=old, harness=new))
    source["agent"] = old
    with op.ownership():
        op.inspect()
        op.prepare()
        result = op.execute()
        assert result.ok
        d = managed.load("p")
        assert d.checkpoint == "uptake-confirmed"
        assert (d.pane, d.name, d.branch, d.item) == ("p", "b", "feat/original", op.request.item)
        op.activate(success=True)
        assert managed.load("p").checkpoint == "active"
    assert calls[1:] == [
        ("exit", old),
        ("start", new, "openai/new"),
        ("prompt", "Recover durable cursor; HOLD if delivered"),
    ]


def test_preview_writes_and_sends_nothing(operation):
    op, calls, _ = operation
    op.inspect()
    assert not calls
    assert managed.load("p") is None
    with pytest.raises(managed.ManagedError, match="owner"):
        op.prepare()


@pytest.mark.parametrize(
    "checkpoint",
    ["prepared", "source-exited", "target-ready", "submission-started", "submission-uncertain"],
)
def test_repair_never_replays_or_certifies_uncertain_submission(operation, checkpoint):
    op, calls, source = operation
    with op.ownership():
        op.prepare()
        d = managed.load("p").model_copy(update={"checkpoint": checkpoint})
        managed.save(d)
        source["agent"] = "opencode"
        with pytest.raises(managed.ManagedError, match="uptake"):
            op.reconcile()
    assert calls == [("lock", "p")]


@pytest.mark.parametrize("checkpoint", ["uptake-confirmed", "batch-committed", "active"])
def test_repair_confirmed_target_no_input(operation, checkpoint):
    op, calls, source = operation
    with op.ownership():
        op.prepare()
        managed.save(managed.load("p").model_copy(update={"checkpoint": checkpoint}))
        source["agent"] = "opencode"
        assert op.reconcile().ok
        op.activate(success=True)
    assert calls == [("lock", "p")]


def test_submission_failure_retains_uncertain_checkpoint(operation, monkeypatch):
    op, calls, _ = operation

    def fail(*args):
        raise RuntimeError("uptake timeout")

    monkeypatch.setattr(replacement, "submit", fail)
    with op.ownership():
        op.prepare()
        assert not op.execute().ok
    assert managed.load("p").checkpoint == "submission-uncertain"
    assert not any(c[0] == "prompt" for c in calls)


def test_pending_blocks_ordinary_restart_and_new_replacement(operation):
    op, _, _ = operation
    with op.ownership():
        op.prepare()
        with pytest.raises(managed.ManagedError, match="repair"):
            op.inspect()


@pytest.mark.parametrize(
    "checkpoint", ["source-exited", "target-ready", "submission-started", "uptake-confirmed"]
)
def test_checkpoint_write_crashes_never_replay(operation, monkeypatch, checkpoint):
    op, calls, _ = operation
    save = managed.save

    def crash(d):
        if d.checkpoint == checkpoint:
            raise OSError("injected crash boundary")
        save(d)

    with op.ownership():
        op.prepare()
        monkeypatch.setattr(managed, "save", crash)
        assert not op.execute().ok
        persisted = managed.load("p")
        assert persisted.checkpoint != "uptake-confirmed"
        with pytest.raises(managed.ManagedError, match="uptake"):
            op.reconcile()
    assert sum(c[0] == "prompt" for c in calls) <= 1


def test_interleaved_pane_owner_loser_sends_and_writes_nothing(
    operation, native_herdr_cache, monkeypatch
):
    op, calls, _ = operation
    monkeypatch.setenv("FR_HERDR_CACHE_DIR", str(native_herdr_cache))
    monkeypatch.setattr(managed, "pane_lock", REAL_LOCK)
    other = replacement.Operation(op.request)
    with op.ownership():
        with pytest.raises(managed.ManagedError, match="locked"):
            with other.ownership():
                other.prepare()
                other.execute()
        assert managed.load("p") is None
        op.prepare()
        assert op.execute().ok
    assert [c[0] for c in calls] == ["exit", "start", "prompt"]


@pytest.mark.parametrize("harness,exit_text", [("claude", "/exit"), ("opencode", "exit")])
def test_graceful_exit_requires_shell_and_cwd(operation, monkeypatch, harness, exit_text):
    op, _, _ = operation
    d = op.source.model_copy(update={"harness": harness})
    sent = []

    def run(args):
        sent.append(args)
        if args[:2] == ["pane", "process-info"]:
            return {
                "result": {
                    "process_info": {
                        "shell_pid": 1,
                        "foreground_processes": [{"pid": 1, "argv": ["zsh"], "cwd": d.checkout}],
                    }
                }
            }
        return {}

    monkeypatch.setattr(replacement, "_run_herdr", run)
    # Restore the real helper (operation fixture only mocks exit, not this reference).
    real_exit(d)
    assert sent[:2] == [["pane", "send-text", "p", exit_text], ["pane", "send-keys", "p", "enter"]]
    assert not any(a[:2] in (["tab", "close"], ["agent", "start"]) for a in sent)


real_exit = replacement.exit_to_shell


@pytest.mark.parametrize("status", ["working", "blocked", "unknown", "absent"])
def test_real_observer_refuses_nonidle_without_input(operation, monkeypatch, status):
    op, calls, _ = operation

    def run(args):
        assert args == ["agent", "list"]
        return {
            "result": {
                "agents": [
                    {
                        "pane_id": "p",
                        "name": "b",
                        "agent": "claude",
                        "agent_status": status,
                        "interactive_ready": True,
                    }
                ]
            }
        }

    monkeypatch.setattr(replacement, "_run_herdr", run)
    with pytest.raises(managed.ManagedError, match="status"):
        real_observe(op.source)
    assert not calls


real_observe = replacement.observe


def test_missing_caller_identity_refuses_before_inspection(operation, monkeypatch):
    op, calls, _ = operation
    monkeypatch.delenv("HERDR_PANE_ID")
    with pytest.raises(managed.ManagedError, match="caller"):
        replacement.Operation(op.request)
    assert not calls


def test_aborted_source_preserves_conflict_reconstruction(operation, monkeypatch):
    op, _, _ = operation
    managed.save(
        op.source.model_copy(update={"conflict_head": "abc", "conflict_brief": "six steps"})
    )
    with op.ownership():
        op.prepare()

        def not_target(*args, **kwargs):
            raise managed.ManagedError("original source remains")

        monkeypatch.setattr(replacement, "observe", not_target)
        op.activate(success=False)
    restored = managed.load("p")
    assert restored.checkpoint == "active" and restored.harness == "claude"
    assert restored.conflict_head == "abc" and restored.conflict_brief == "six steps"


def test_pending_descriptor_excludes_ordinary_claude_restart(operation, monkeypatch):
    from fr_herdr import restart

    op, _, _ = operation
    with op.ownership():
        op.prepare()
    reads = []

    def run(args):
        reads.append(args)
        if args == ["agent", "list"]:
            return {"result": {"agents": [{"agent": "claude", "pane_id": "p"}]}}
        assert args == ["tab", "list"]
        return {"result": {"tabs": []}}

    monkeypatch.setattr(restart, "_run_herdr", run)
    report = restart.restart_idle(yes=True)
    assert report.lines[0].verdict == "skip" and "pending" in report.lines[0].detail
    assert reads == [["agent", "list"], ["tab", "list"]]


@pytest.mark.parametrize("model", ["plain-model", "/model", "provider/", "provider/a model"])
def test_direct_replacement_malformed_model_never_creates_descriptor_or_sends(operation, model):
    from dataclasses import replace

    op, calls, _ = operation
    with pytest.raises(managed.ManagedError, match="provider/model"):
        replacement.Operation(replace(op.request, model=model))
    assert managed.load("p") is None
    assert not calls


def test_source_restoration_write_fault_remains_repairable_and_idempotent(operation, monkeypatch):
    op, calls, _ = operation
    save = managed.save

    def not_target(*args, **kwargs):
        raise managed.ManagedError("source remains")

    monkeypatch.setattr(replacement, "observe", not_target)
    with op.ownership():
        op.prepare()

        def fault(d):
            if d.checkpoint == "active" and d.attempt is None:
                raise OSError("source descriptor restoration failed")
            save(d)

        monkeypatch.setattr(managed, "save", fault)
        with pytest.raises(OSError):
            op.activate(success=False)
    assert managed.load("p").checkpoint == "prepared"
    monkeypatch.setattr(managed, "save", save)
    retry = replacement.Operation(op.request)
    with retry.ownership():
        assert not retry.reconcile().ok
        retry.activate(success=False)
        restored = managed.load("p")
        assert restored.checkpoint == "active" and restored.attempt is None
        assert not retry.reconcile().ok
        retry.activate(success=False)
        assert managed.load("p") == restored
    assert all(c[0] == "lock" for c in calls), "repair launched or replayed input"
