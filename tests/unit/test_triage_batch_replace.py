"""Replacement CLI uses fake forge/checkout/runner; never touches live panes."""

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd as cmd
from fr.triage.batch import last_dispatch, save_batches
from fr.triage.model import DispatchEvent, load_judgements
from fr_dispatch.protocols import ReplacementRequest, ReplacementResult
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_triage_batch_dispatch import JUDGEMENTS, REPO, FakeCheckout, _state


class FakeOperation:
    name = "b-lifecycle-test"

    def __init__(self):
        self.calls = []
        self.failure = None
        self.result = ReplacementResult(True, "uptake-confirmed", "target")

    @contextmanager
    def ownership(self):
        self.calls.append("pane-lock")
        yield
        self.calls.append("unlock")

    def inspect(self):
        self.calls.append("inspect")
        if self.failure:
            raise ValueError(self.failure)

    def prepare(self):
        self.calls.append("prepare")

    def execute(self):
        self.calls.append("execute")
        return self.result

    def reconcile(self):
        self.calls.append("reconcile")
        if self.failure:
            raise ValueError(self.failure)
        return self.result

    def activate(self, *, success):
        self.calls.append("activate")


@pytest.fixture
def env(tmp_path, monkeypatch):
    target = _state(tmp_path, judgements=JUDGEMENTS.replace("runner: fake", "runner: herdr"))
    j = load_judgements(target / "judgements.yaml")
    b = j.batches[0].model_copy(
        update={
            "events": [
                DispatchEvent(
                    kind="dispatch",
                    at=datetime(2026, 9, 26, tzinfo=UTC),
                    runner="herdr",
                    handle="p1",
                    branch="feat/original",
                    reserved_version="6.0.0",
                )
            ]
        }
    )
    save_batches(target / "judgements.yaml", [b], read=j.batches)
    checkout = FakeCheckout(tmp_path)
    monkeypatch.setattr(cmd, "make_checkout", lambda p: checkout)
    gh = FakeGhClient()
    monkeypatch.setattr(cmd, "make_client", lambda url: gh)
    op = FakeOperation()

    class FakeRunner:
        def replacement_pending(self, item, pane):
            return None

        def replacement_session(self, request):
            self.request = request
            return op

    runner = FakeRunner()
    monkeypatch.setattr(cmd, "load_runner", lambda name: runner)

    @contextmanager
    def scope_lock(path):
        op.calls.append("scope-lock")
        yield

    monkeypatch.setattr(cmd, "replacement_scope_lock", scope_lock)
    return target, gh, runner, op


def invoke(env, *args):
    target = env[0]
    return CliRunner().invoke(
        app,
        [
            "triage",
            "batch",
            "replace",
            "lifecycle",
            "--repo",
            REPO,
            "--dir",
            str(target),
            "--checkout",
            str(target),
            *args,
        ],
    )


def test_preview_no_writes_or_keys(env):
    path = env[0] / "judgements.yaml"
    before = path.read_bytes()
    result = invoke(env, "--model", "new", "--reason", "cost")
    assert result.exit_code == 0, result.output
    assert path.read_bytes() == before
    assert env[3].calls == ["inspect"]


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--reason", " "],
        ["--harness", "opencode", "--reason", "change"],
        ["--harness", "unknown", "--model", "new", "--reason", "change"],
        ["--reason", "noop"],
        ["--model", "", "--reason", "blank"],
    ],
)
def test_required_reason_model_noop_and_unsupported_refused(env, args):
    result = invoke(env, *args, "--yes")
    assert result.exit_code == 2, result.output
    assert "execute" not in env[3].calls


def test_success_preserves_dispatch_identity_and_lock_order(env):
    path = env[0] / "judgements.yaml"
    original = last_dispatch(load_judgements(path).batches[0])
    result = invoke(
        env, "--harness", "opencode", "--model", "openai/new", "--reason", "change", "--yes"
    )
    assert result.exit_code == 0, result.output
    b = load_judgements(path).batches[0]
    assert last_dispatch(b) == original
    assert b.launch.harness == "opencode" and b.launch.model == "openai/new"
    assert [e.result for e in b.events[1:]] == ["attempt", "success"]
    assert env[3].calls == [
        "scope-lock",
        "pane-lock",
        "inspect",
        "prepare",
        "execute",
        "activate",
        "unlock",
    ]
    assert [name for name, _ in env[1].calls] == ["list_prs_by_head"]


@pytest.mark.parametrize("status", ["MERGED", "CLOSED", "UNKNOWN"])
def test_live_pr_gate_overrides_dispatched_cache(env, monkeypatch, status):
    monkeypatch.setattr(
        env[1],
        "list_prs_by_head",
        lambda repo, branch: [
            {"number": 42, "state": status, "headRefName": branch, "isCrossRepository": False}
        ],
    )
    monkeypatch.setattr(
        env[1], "pr_view", lambda repo, n: {"state": status, "head_ref": "feat/original"}
    )
    result = invoke(env, "--model", "new", "--reason", "change", "--yes")
    assert result.exit_code == 2, result.output
    assert "prepare" not in env[3].calls


@pytest.mark.parametrize(
    "reason",
    ["working", "blocked", "unknown", "absent", "ambiguous", "draft", "self", "unreadable"],
)
def test_source_refusal_writes_no_attempt(env, reason):
    env[3].failure = reason
    before = (env[0] / "judgements.yaml").read_bytes()
    result = invoke(env, "--model", "new", "--reason", "change", "--yes")
    assert result.exit_code == 2, result.output
    assert (env[0] / "judgements.yaml").read_bytes() == before


def test_failure_stays_pending_until_explicit_repair(env):
    env[3].result = ReplacementResult(
        False, "source-exited", "shell", "startup failure; repair owed"
    )
    args = ["--model", "new", "--reason", "change", "--yes"]
    assert invoke(env, *args).exit_code == 1
    b = load_judgements(env[0] / "judgements.yaml").batches[0]
    assert b.launch.model == "claude-opus-5-5"
    assert invoke(env, *args).exit_code == 2
    assert invoke(env, "--repair", "--reason", "inspected shell", "--yes").exit_code == 0
    b = load_judgements(env[0] / "judgements.yaml").batches[0]
    assert b.events[-1].reconciled
    assert env[3].calls.count("execute") == 1


def test_batch_commit_failure_then_repair_never_executes_twice(env, monkeypatch):
    original = cmd.save_batches

    def fail_success(path, batches, **kwargs):
        if (
            batches[0].events[-1].kind == "replacement"
            and batches[0].events[-1].result == "success"
        ):
            raise OSError("disk failure")
        return original(path, batches, **kwargs)

    monkeypatch.setattr(cmd, "save_batches", fail_success)
    result = invoke(env, "--model", "new", "--reason", "change", "--yes")
    assert result.exit_code == 1 and "--repair" in result.output
    monkeypatch.setattr(cmd, "save_batches", original)
    assert invoke(env, "--repair", "--reason", "verified target", "--yes").exit_code == 0
    assert env[3].calls.count("execute") == 1
    assert load_judgements(env[0] / "judgements.yaml").batches[0].launch.model == "new"


def test_activation_failure_repairs_both_stores_without_second_success(env, monkeypatch):
    op = env[3]

    def fail(**kwargs):
        raise OSError("descriptor write")

    activate = op.activate
    monkeypatch.setattr(op, "activate", fail)
    result = invoke(env, "--model", "new", "--reason", "change", "--yes")
    assert result.exit_code == 1 and "--repair" in result.output
    monkeypatch.setattr(op, "activate", activate)
    before = (env[0] / "judgements.yaml").read_bytes()
    assert invoke(env, "--repair", "--reason", "verified target", "--yes").exit_code == 0
    assert (env[0] / "judgements.yaml").read_bytes() == before
    assert op.calls.count("execute") == 1


def test_scope_loser_cannot_inspect_or_write(env, monkeypatch):
    @contextmanager
    def loser(path):
        raise ValueError("scope locked")
        yield

    monkeypatch.setattr(cmd, "replacement_scope_lock", loser)
    before = (env[0] / "judgements.yaml").read_bytes()
    assert invoke(env, "--model", "new", "--reason", "change", "--yes").exit_code == 2
    assert not env[3].calls
    assert (env[0] / "judgements.yaml").read_bytes() == before


@pytest.mark.parametrize("raw", [None, {}, [{"number": "42"}]])
def test_unreadable_live_forge_refuses_even_without_cached_pr(env, monkeypatch, raw):
    monkeypatch.setattr(env[1], "list_prs_by_head", lambda *a: raw)
    result = invoke(env, "--model", "new", "--reason", "change", "--yes")
    assert result.exit_code == 2
    assert "inspect" not in env[3].calls


def test_prepared_before_attempt_write_can_be_reconciled_without_input(env, monkeypatch):
    pending = ReplacementRequest(
        f"{REPO}/run/batch-lifecycle",
        "p1",
        "b-lifecycle-test",
        "feat/original",
        str(env[0]),
        "claude",
        "claude-opus-5-5",
        "opencode",
        "openai/new",
        "orphan-prepared",
    )
    monkeypatch.setattr(env[2], "replacement_pending", lambda *a: pending)
    env[3].result = ReplacementResult(False, "prepared", "source", "aborted before input")
    result = invoke(env, "--repair", "--reason", "source inspected", "--yes")
    assert result.exit_code == 0, result.output
    assert "execute" not in env[3].calls and "prepare" not in env[3].calls
    b = load_judgements(env[0] / "judgements.yaml").batches[0]
    assert b.events[-1].attempt == "orphan-prepared" and b.events[-1].reconciled


def test_dispatch_repair_selects_real_dispatch_after_audit(env, monkeypatch):
    assert invoke(env, "--model", "new", "--reason", "change", "--yes").exit_code == 0
    j = load_judgements(env[0] / "judgements.yaml")
    monkeypatch.setattr(cmd, "_tracking_gate", lambda *a, **k: None)
    monkeypatch.setattr(cmd, "claim_env", lambda *a: None)
    monkeypatch.setattr(cmd, "_refuse_held", lambda *a: None)
    seen = []
    monkeypatch.setattr(cmd, "_repair", lambda b, *a, **k: seen.append(last_dispatch(b)))
    from tests.unit.test_triage_batch_dispatch import _facts

    cmd.dispatch_batch(env[0], _facts(), j, j.batches[0], repair=True)
    assert seen == [last_dispatch(j.batches[0])]
