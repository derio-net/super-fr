"""A refused forge host never crashes the isolation lifecycle (review p2-r1,
spec 2026-10-06-forge-remainder §4.B/§4.E).

The adapter fails closed on a declared GitHub host gh is not logged into
(`GhHostRefusedError`): fr must not point gh, or its tokens, at it. The
lifecycle turns that into its own `IsolationError`, so the commands that guard
work (`down`, `verify-merge`) refuse cleanly, and the read-only commands that
cover many workspaces (`status`, the gc sweep) degrade per workspace instead
of failing them all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.gh import GhHostRefusedError
from fr.isolation import local as local_mod
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.isolation.types import IsolationError

from tests.unit.test_isolation import FakeRunner, make_repo_with_origin

_REFUSAL = (
    "GitHub host 'ghe.example' is not one gh is logged into; "
    "run `gh auth login --hostname ghe.example`"
)


class _RefusingClient:
    def default_branch(self, **_: Any) -> str | None:
        raise GhHostRefusedError(_REFUSAL)

    def pr_for_branch(self, *_: Any, **__: Any) -> dict[str, Any] | None:
        raise GhHostRefusedError(_REFUSAL)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    runner = FakeRunner(stdout={"docker": "cid running"})
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    state = target.up(None, "feat/r")
    monkeypatch.setattr(local_mod, "client_for", lambda _root: _RefusingClient())
    return target, state


def test_the_pr_lookup_turns_the_refusal_into_an_isolation_error(workspace) -> None:
    target, state = workspace
    with pytest.raises(IsolationError, match="gh auth login --hostname ghe.example"):
        target._pr_from(state.worktree, state.branch)


def test_the_default_branch_lookup_turns_the_refusal_into_an_isolation_error(
    workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, _state = workspace
    real_run = target.run

    def no_symbolic_ref(argv: list[str], **kw: Any):  # noqa: ANN202
        if argv[:2] == ["git", "symbolic-ref"]:
            import subprocess

            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        return real_run(argv, **kw)

    monkeypatch.setattr(target, "run", no_symbolic_ref)
    with pytest.raises(IsolationError, match="gh auth login --hostname ghe.example"):
        target._resolve_default_branch()


def test_status_shows_no_pr_and_warns_instead_of_crashing(
    workspace, capsys: pytest.CaptureFixture[str]
) -> None:
    target, state = workspace
    row = target.status(state)
    assert row["pr"] is None
    assert "gh auth login --hostname ghe.example" in capsys.readouterr().err


def test_gc_skips_the_refused_workspace_and_finishes_the_sweep(workspace) -> None:
    target, _state = workspace
    actions = {a.branch: a for a in target.gc()}
    action = actions["feat/r"]
    assert (action.verdict, action.action) == ("unverifiable", "skipped")
    assert "gh auth login --hostname ghe.example" in action.detail


def test_verify_merge_refuses_rather_than_guessing(workspace) -> None:
    target, state = workspace
    with pytest.raises(IsolationError, match="gh auth login --hostname ghe.example"):
        target.verify_merge(state, "dev")


_LOGIN_PAGE = "<!doctype html><html><head><title>Sign in</title></head><body></body></html>\n"


@pytest.mark.parametrize(
    "stderr",
    [
        "HTTP/2 200 OK\ncontent-type: text/html\n",
        "HTTP/2 302\nlocation: https://sso.example.com/login\n",
    ],
    ids=["html-200", "redirect-302"],
)
def test_a_gitea_login_page_is_refused_by_name_not_read_as_main_or_no_pr(
    workspace, monkeypatch: pytest.MonkeyPatch, stderr: str
) -> None:
    """R7 (spec 2026-11-19-consumer-followups, gh#1554): the tea adapter re-raises a
    login page, so `up`'s default-branch read and the PR lookup of gc/down/status
    refuse naming it, where they used to base on `main` or read "no PR"."""
    import subprocess

    from fr.real_teaclient import RealTeaClient

    target, state = workspace
    real_run = target.run

    def login_page(argv: list[str], **kw: Any):  # noqa: ANN202
        if argv[:2] == ["git", "symbolic-ref"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        if argv[:3] == ["tea", "api", "-i"]:
            return subprocess.CompletedProcess(argv, 0, stdout=_LOGIN_PAGE, stderr=stderr)
        return real_run(argv, **kw)

    monkeypatch.setattr(target, "run", login_page)
    monkeypatch.setattr(local_mod, "client_for", lambda _root: RealTeaClient())
    with pytest.raises(IsolationError, match="cannot ask the forge: .*SSO or forward-auth"):
        target._resolve_default_branch()
    with pytest.raises(IsolationError, match="cannot ask the forge: .*SSO or forward-auth"):
        target._pr_from(state.worktree, state.branch)
