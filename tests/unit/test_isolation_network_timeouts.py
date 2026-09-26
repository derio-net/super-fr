"""`_run_network` takes an optional cwd and stays bounded (isolation timeouts)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.isolation.types import IsolationError, IsolationState

from tests.unit.test_isolation import make_repo


class _Recorder:
    def __init__(self) -> None:
        self.cwds: list[Path | None] = []
        self.kwargs: list[dict[str, Any]] = []

    def __call__(
        self,
        argv: list[str],
        cwd: Path | None = None,
        check: bool = False,
        capture: bool = True,
        **kw: Any,
    ) -> subprocess.CompletedProcess[str]:
        # Select by argv: `_network_env` may probe `git config` first, which is
        # not the call under test (and is skipped when GIT_SSH* is set).
        if argv[:2] == ["git", "status"]:
            self.cwds.append(cwd)
            self.kwargs.append(kw)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


def test_run_network_uses_given_cwd_and_a_timeout(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    rec = _Recorder()
    target = LocalWorktreeDevcontainerTarget(repo, runner=rec)
    target._run_network(["git", "status"], cwd=other)
    assert rec.cwds == [other]
    assert rec.kwargs[0]["timeout"] > 0


def test_run_network_defaults_to_repo_root(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    rec = _Recorder()
    target = LocalWorktreeDevcontainerTarget(repo, runner=rec)
    target._run_network(["git", "status"])
    assert rec.cwds == [target.repo_root]
    assert rec.kwargs[0]["timeout"] > 0


# --- phase 2: forge lookup and verify-merge fetches are bounded --------------


class _Scripted:
    """Records every call; answers by argv prefix. Never selects by position."""

    def __init__(self, answers: dict[tuple[str, ...], subprocess.CompletedProcess[str]]) -> None:
        self.answers = answers
        self.calls: list[tuple[list[str], Path | None, dict[str, Any]]] = []

    def __call__(
        self,
        argv: list[str],
        cwd: Path | None = None,
        check: bool = False,
        capture: bool = True,
        **kw: Any,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(argv), cwd, kw))
        for prefix, res in self.answers.items():
            if tuple(argv[: len(prefix)]) == prefix:
                return res
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def select(self, *prefix: str) -> list[tuple[list[str], Path | None, dict[str, Any]]]:
        return [c for c in self.calls if tuple(c[0][: len(prefix)]) == prefix]


def _cp(rc: int = 0, out: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], rc, stdout=out, stderr="")


@pytest.mark.parametrize(
    ("backend", "prefix"),
    [
        ("github", ("gh", "repo", "view")),
        ("gitlab", ("glab", "repo", "view")),
        ("gitea", ("tea", "repos")),
    ],
)
def test_default_branch_lookup_is_bounded_and_falls_back_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str, prefix: tuple[str, ...]
) -> None:
    import fr.isolation.local as local

    monkeypatch.setattr(local, "detect_backend", lambda _p: backend)
    repo = make_repo(tmp_path)
    rec = _Scripted({("git", "symbolic-ref"): _cp(1), prefix: _cp(124)})
    target = LocalWorktreeDevcontainerTarget(repo, runner=rec)
    assert target._resolve_default_branch() == "main"
    (call,) = rec.select(*prefix)
    assert call[1] == target.repo_root
    assert call[2]["timeout"] > 0
    # the local symbolic-ref carries no timeout
    (sym,) = rec.select("git", "symbolic-ref")
    assert "timeout" not in sym[2]


def _state(repo: Path, tmp_path: Path) -> IsolationState:
    wt = tmp_path / "wt"
    wt.mkdir()
    return IsolationState(
        repo_root=repo,
        branch="feat/x",
        worktree=wt,
        profile="dev",
        created_at="2026-01-01T00:00:00",
    )


def _merged_answers(fetch_default: subprocess.CompletedProcess[str]) -> dict:
    return {
        ("gh", "pr", "view"): _cp(0, json.dumps({"state": "MERGED", "url": "u"})),
        ("git", "merge-base"): _cp(0, "abc\n"),
        ("git", "diff"): _cp(0, ""),
        ("git", "rev-parse"): _cp(0, "sha\n"),
        ("git", "fetch", "origin", "main"): fetch_default,
    }


def test_verify_merge_fetch_is_bounded_and_a_timeout_is_not_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.isolation.local as local

    monkeypatch.setattr(local, "detect_backend", lambda _p: "github")
    repo = make_repo(tmp_path)
    st = _state(repo, tmp_path)
    ok = _Scripted(_merged_answers(_cp(0)))
    res = LocalWorktreeDevcontainerTarget(repo, runner=ok).verify_merge(st, "main")
    assert res["verified"] is True and res["fetched"] is True
    (fetch,) = ok.select("git", "fetch", "origin", "main")
    assert fetch[2]["timeout"] > 0
    assert fetch[1] == st.worktree

    slow = _Scripted(_merged_answers(_cp(124)))
    res = LocalWorktreeDevcontainerTarget(repo, runner=slow).verify_merge(st, "main")
    assert res["fetched"] is False and res["verified"] is False


def test_verify_merge_reaped_fetches_are_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.isolation.local as local

    monkeypatch.setattr(local, "detect_backend", lambda _p: "github")
    repo = make_repo(tmp_path)
    rec = _Scripted(_merged_answers(_cp(0)))
    target = LocalWorktreeDevcontainerTarget(repo, runner=rec)
    res = target.verify_merge_reaped("feat/x", "main")
    assert res["verified"] is True
    (dflt,) = rec.select("git", "fetch", "origin", "main")
    (br,) = rec.select("git", "fetch", "origin", "feat/x")
    assert dflt[2]["timeout"] > 0 and br[2]["timeout"] > 0
    assert dflt[1] == target.repo_root and br[1] == target.repo_root

    slow = _Scripted({**_merged_answers(_cp(0)), ("git", "fetch", "origin", "feat/x"): _cp(124)})
    res = LocalWorktreeDevcontainerTarget(repo, runner=slow).verify_merge_reaped("feat/x", "main")
    assert res["verified"] is True  # a timed-out branch fetch changes nothing

    dead = _Scripted(
        {
            **_merged_answers(_cp(0)),
            ("git", "fetch", "origin", "feat/x"): _cp(124),
            ("git", "rev-parse"): _cp(1),
        }
    )
    with pytest.raises(IsolationError):
        LocalWorktreeDevcontainerTarget(repo, runner=dead).verify_merge_reaped("feat/x", "main")


def test_verify_merge_reaped_default_fetch_timeout_is_not_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.isolation.local as local

    monkeypatch.setattr(local, "detect_backend", lambda _p: "github")
    repo = make_repo(tmp_path)
    rec = _Scripted(_merged_answers(_cp(124)))
    res = LocalWorktreeDevcontainerTarget(repo, runner=rec).verify_merge_reaped("feat/x", "main")
    assert res["fetched"] is False and res["verified"] is False
