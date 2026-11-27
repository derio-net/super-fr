"""Replacement previews and lock losers never move, import or sync state.

Since S1 the state is `~/.cache/fr/triage/<scope>/` (spec 2026-11-19 R17), the cache
repository; a clone's old copy is moved only by a preparing command (R18).

The remote is a disposable bare git repository; no test reaches the real forge.
"""

from contextlib import contextmanager

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd as cmd
from fr.commands import triage_cmd
from fr.triage.gitseam import init_state_repo
from fr.triage.model import Scope, legacy_state_dir, load_judgements
from fr.triage.scope_config import scope_id
from fr.triage.state_ref import push_state
from typer.testing import CliRunner

from tests.unit.test_triage_batch_dispatch import REPO
from tests.unit.test_triage_batch_replace import env as _replacement_env_fixture
from tests.unit.test_triage_state_ref_sync import _git, _Private

env = _replacement_env_fixture


def snapshot(state, workspace):
    return (
        {
            str(p.relative_to(state)): p.read_bytes()
            for p in state.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(state).parts
        },
        (workspace / ".git/info/exclude").read_bytes(),
    )


def invoke(env, workspace, yes=False):
    return CliRunner().invoke(
        app,
        [
            "triage",
            "batch",
            "replace",
            "lifecycle",
            "--repo",
            REPO,
            "--workspace",
            str(workspace),
            "--checkout",
            str(env[0]),
            "--model",
            "new",
            "--reason",
            "state regression",
            *(["--yes"] if yes else []),
        ],
    )


@pytest.fixture
def remote_state(env, tmp_path, monkeypatch):
    scope = Scope(kind="repo", target=REPO)
    workspace = tmp_path / "workspace"
    other = tmp_path / "other"
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--quiet", str(workspace))
    _git(tmp_path, "init", "--quiet", str(other))
    _git(tmp_path, "init", "--quiet", "--bare", str(remote))
    state = legacy_state_dir(scope)
    init_state_repo(state)
    for name in ("judgements.yaml", "facts.json"):
        (state / name).write_bytes((env[0] / name).read_bytes())
    (state / "scope-durable.yaml").write_text(f"state_repo: {REPO}\n")
    first = push_state(
        state,
        str(remote),
        scope_id(scope),
        expected_old=None,
        scope=scope,
        state_repo=REPO,
        client=_Private(),
        repo=state,
    )
    updated = other / "state"
    updated.mkdir()
    (updated / "scope-durable.yaml").write_bytes((state / "scope-durable.yaml").read_bytes())
    (updated / "judgements.yaml").write_text(
        (state / "judgements.yaml")
        .read_text()
        .replace("Separate container lifecycle", "Remote updated title")
    )
    latest = push_state(
        updated,
        str(remote),
        scope_id(scope),
        expected_old=first,
        scope=scope,
        state_repo=REPO,
        client=_Private(),
        repo=other,
    )
    assert latest != first
    monkeypatch.setattr(triage_cmd, "state_remote", lambda repo: str(remote))
    monkeypatch.setattr(triage_cmd, "make_visibility_client", lambda: _Private())
    return workspace, state


@pytest.mark.parametrize("yes", [False, True])
def test_preview_and_lock_loser_leave_remote_updated_state_and_exclude_untouched(
    env, remote_state, monkeypatch, yes
):
    workspace, state = remote_state
    before = snapshot(state, workspace)
    if yes:

        @contextmanager
        def loser(path):
            raise ValueError("scope locked")
            yield

        monkeypatch.setattr(cmd, "replacement_scope_lock", loser)
    result = invoke(env, workspace, yes)
    assert result.exit_code == (2 if yes else 0), result.output
    assert snapshot(state, workspace) == before
    assert env[3].calls == ([] if yes else ["inspect"])


def test_preview_never_moves_a_clone_copy_or_creates_the_cache(env, tmp_path):
    workspace = tmp_path / "old-workspace"
    _git(tmp_path, "init", "--quiet", str(workspace))
    scope = Scope(kind="repo", target=REPO)
    old = workspace / ".fr/triage-state" / scope.name  # an fr below S1 left it here
    old.mkdir(parents=True)
    for name in ("judgements.yaml", "facts.json"):
        (old / name).write_bytes((env[0] / name).read_bytes())
    (workspace / ".git/info/exclude").write_text(".fr/triage-state/\n")
    before = snapshot(old, workspace)
    result = invoke(env, workspace)
    assert result.exit_code == 2  # preview reads the cache only, and moves nothing
    assert not legacy_state_dir(scope).exists()
    assert snapshot(old, workspace) == before
    assert not env[3].calls


def test_act_fetches_fresh_state_and_pushes_only_while_scope_owned(env, remote_state, monkeypatch):
    workspace, state = remote_state
    owned = False
    events = []

    @contextmanager
    def owner(path):
        nonlocal owned
        assert path == state
        owned = True
        events.append("lock")
        try:
            yield
        finally:
            owned = False
            events.append("unlock")

    real_sync = triage_cmd._sync_with_ref

    def sync(scope, target, *, defer_push):
        assert owned and not defer_push
        events.append("fetch")
        finish = real_sync(scope, target, defer_push=defer_push)
        assert finish is not None

        def push():
            assert owned
            events.append("push")
            finish()

        return push

    monkeypatch.setattr(cmd, "replacement_scope_lock", owner)
    monkeypatch.setattr(cmd, "_sync_with_ref", sync)
    result = invoke(env, workspace, yes=True)
    assert result.exit_code == 0, result.output
    batch = load_judgements(state / "judgements.yaml").batches[0]
    assert batch.title == "Remote updated title"
    assert batch.launch.model == "new"
    assert events == ["lock", "fetch", "push", "unlock"]
