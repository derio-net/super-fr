"""`fr run start` ensures isolation itself — spec §4.B, review fix r2-f5.

"A run is born in its workspace." The run file is written inside the
isolation worktree, never in the base clone, because every later step runs
from the worktree: `advance` resolves its repo root there (so a run file in
the base clone is invisible), `cli` steps run with `cwd` at the workspace
root (so `fr plan self-review {{ artifacts.plan }}` finds a plan that only
exists there), and the file has to be ON the feature branch to reach the PR
that makes the run reviewable.

The alternative — an `isolate` STEP inside the shape — is what the first
draft shipped: the run's own first step moved the ground out from under it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fr.cli import app
from fr.run.model import run_path
from fr.run.workspace import RunWorkspaceError, ensure_run_workspace
from typer.testing import CliRunner

runner_cli = CliRunner()

_SHAPE = """
workflow: tiny
schema: 1
unit: run
steps:
  - id: hello
    kind: cli
    run: "true"
"""


def _shipped(tmp_path: Path) -> Path:
    d = tmp_path / "shipped"
    d.mkdir(parents=True, exist_ok=True)
    (d / "tiny.yaml").write_text(_SHAPE)
    return d


def _marker(root: Path, branch: str, *, toplevel: Path | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".fr-isolation").write_text(
        json.dumps(
            {
                "toplevel": str((toplevel or root).resolve()),
                "branch": branch,
                "mode": "worktree",
                "created_at": "2026-08-27T00:00:00+00:00",
            }
        )
    )


def _start(repo: Path, shipped: Path, branch: str = "feat/x"):
    return runner_cli.invoke(
        app,
        ["run", "start", "tiny", "--branch", branch, "--run-id", "r1"],
        env={**os.environ, "VK_REPO_ROOT": str(repo), "FR_SHIPPED_WORKFLOWS_DIR": str(shipped)},
    )


class _FakeTarget:
    def __init__(self, worktree: Path) -> None:
        self.worktree = worktree
        self.calls: list[str] = []

    def up(self, *, profile=None, branch: str, **kwargs):
        self.calls.append(branch)
        self.worktree.mkdir(parents=True, exist_ok=True)
        _marker(self.worktree, branch)

        class _State:
            pass

        st = _State()
        st.worktree = self.worktree
        return st


def _real_worktree(tmp_path: Path, branch: str = "feat/x") -> Path:
    """A genuine linked worktree with a valid marker.

    FIXTURE CHANGE, assertion unchanged (review r5-e3): `ensure_run_workspace`
    now corroborates the marker's `mode`, and `mode: worktree` means "this IS a
    linked worktree" — `git rev-parse --git-dir` != `--git-common-dir`, the
    same structural check the `fr-isolation-required` PreToolUse hook makes. A
    marker written into a bare directory is the forgery that check refuses, so
    the "inside a workspace" fixture must be the real thing. The forged case
    now has its own test below.
    """
    import subprocess

    base = tmp_path / "base"
    base.mkdir(parents=True, exist_ok=True)

    def git(root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    subprocess.run(["git", "init", "-q", "-b", "main", str(base)], check=True)
    git(base, "config", "user.email", "t@example.com")
    git(base, "config", "user.name", "T")
    (base / "seed.md").write_text("seed\n")
    git(base, "add", "-A")
    git(base, "commit", "-qm", "seed")
    wt = tmp_path / "wt"
    git(base, "worktree", "add", "-q", "-b", branch, str(wt))
    _marker(wt, branch)
    return wt


def test_a_run_started_inside_a_workspace_is_written_there(tmp_path: Path) -> None:
    repo = _real_worktree(tmp_path)
    result = _start(repo, _shipped(tmp_path))
    assert result.exit_code == 0, result.output
    assert run_path(repo, "r1").is_file()


def test_a_forged_worktree_marker_in_a_plain_directory_is_refused(tmp_path: Path) -> None:
    """A `.fr-isolation` file is text anyone can write, and its `toplevel` can
    simply be edited to match wherever it sits. Without the mode check
    (review r5-e3), dropping one into a base clone made `fr run start` write
    the run file THERE — the exact failure §4.B's "a run is born in its
    workspace" exists to prevent, reached through a file with no privileges."""
    repo = tmp_path / "plain"
    _marker(repo, "feat/x")

    result = _start(repo, _shipped(tmp_path))

    assert result.exit_code == 2, result.output
    assert "not a linked git worktree" in result.output
    assert not (repo / "docs" / "superpowers" / "runs").exists()


def test_an_external_marker_without_container_evidence_is_refused(tmp_path: Path) -> None:
    """`mode: external` is a preparer's hand-off from inside a container; a
    bare host cannot claim it."""
    import json as _json

    repo = tmp_path / "ext"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".fr-isolation").write_text(
        _json.dumps({"toplevel": str(repo.resolve()), "branch": "feat/x", "mode": "external"})
    )

    result = _start(repo, _shipped(tmp_path))

    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        assert result.exit_code == 0, result.output  # we ARE in a container
    else:
        assert result.exit_code == 2, result.output
        assert "container evidence" in result.output


def test_an_unknown_marker_mode_fails_closed(tmp_path: Path) -> None:
    import json as _json

    repo = tmp_path / "weird"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".fr-isolation").write_text(
        _json.dumps({"toplevel": str(repo.resolve()), "branch": "feat/x", "mode": "vibes"})
    )

    result = _start(repo, _shipped(tmp_path))

    assert result.exit_code == 2, result.output
    assert "unknown mode" in result.output


def test_a_run_started_outside_a_workspace_enters_isolation_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The base clone must come away with no run file at all — a run file
    there is not on the feature branch and never reaches the PR."""
    import fr.run.workspace as workspace

    base = tmp_path / "base"
    base.mkdir()
    wt = tmp_path / "worktree"
    target = _FakeTarget(wt)
    monkeypatch.setattr(workspace, "_select_target", lambda _root: target)

    result = _start(base, _shipped(tmp_path))

    assert result.exit_code == 0, result.output
    assert target.calls == ["feat/x"]
    assert run_path(wt, "r1").is_file()
    assert not run_path(base, "r1").exists()
    assert str(wt) in result.output


def test_an_existing_workspace_for_the_branch_is_reused_not_re_entered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.run.workspace as workspace

    base = tmp_path / "base"
    base.mkdir()
    wt = tmp_path / "worktree"
    wt.mkdir()

    class _State:
        worktree = wt

    monkeypatch.setattr(workspace, "load_state", lambda _root, _branch: _State())

    def _boom(_root):
        raise AssertionError("an existing workspace must not be re-entered")

    monkeypatch.setattr(workspace, "_select_target", _boom)

    result = _start(base, _shipped(tmp_path))

    assert result.exit_code == 0, result.output
    assert run_path(wt, "r1").is_file()


def test_starting_a_run_for_another_branch_from_inside_a_workspace_is_refused(
    tmp_path: Path,
) -> None:
    """Silently writing the run into a workspace cut for a different branch
    would put it on the wrong PR."""
    repo = tmp_path / "wt"
    _marker(repo, "feat/other")

    result = _start(repo, _shipped(tmp_path), branch="feat/x")

    assert result.exit_code == 2
    assert "feat/other" in result.output
    assert not run_path(repo, "r1").exists()


def test_a_marker_copied_from_another_checkout_is_not_a_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same identity rule the `fr-isolation-required` hook uses: a marker
    whose recorded toplevel is not this checkout proves nothing."""
    import fr.run.workspace as workspace

    base = tmp_path / "base"
    _marker(base, "feat/x", toplevel=tmp_path / "somewhere-else")
    wt = tmp_path / "worktree"
    target = _FakeTarget(wt)
    monkeypatch.setattr(workspace, "_select_target", lambda _root: target)

    assert ensure_run_workspace(base, "feat/x") == wt


def test_isolation_failure_is_a_clean_error_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.run.workspace as workspace
    from fr.isolation.types import IsolationError

    class _Failing:
        def up(self, **kwargs):
            raise IsolationError("no devcontainer profile")

    monkeypatch.setattr(workspace, "_select_target", lambda _root: _Failing())
    base = tmp_path / "base"
    base.mkdir()

    with pytest.raises(RunWorkspaceError) as e:
        ensure_run_workspace(base, "feat/x")
    assert "no devcontainer profile" in str(e.value)

    result = _start(base, _shipped(tmp_path))
    assert result.exit_code == 2
    assert "no devcontainer profile" in result.output
