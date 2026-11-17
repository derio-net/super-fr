"""A workspace's identity comes from what identifies it, never a stand-in.

Three defects batched as `workspace-identity`:

- gh#1419: the branch slug (`/` -> `__`) is not injective, so `feat/a__b` and
  `feat__a/b` share one worktree directory and one state file. `up` must refuse
  the second branch, and a lookup must never hand one branch the other's record.
- gh#1166: `up` on an existing workspace is a resume, and it must use the
  workspace's recorded mode, not `FR_ISOLATION_TARGET` (gh#569).
- gh#1243: `fr init scaffold` run from a linked worktree must name the container
  and the secrets path after the repo, not the worktree's folder.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.scaffold import scaffold_profile
from fr.isolation.types import IsolationError, delete_state, load_state, state_path
from typer.testing import CliRunner

from tests.unit.test_isolation import FakeRunner, make_repo_with_origin

# ---------- gh#1419: colliding branch slugs ----------


def test_up_refuses_a_branch_whose_slug_another_workspace_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    first = HostWorktreeTarget(repo, runner=FakeRunner()).up(None, "feat/a__b")
    with pytest.raises(IsolationError) as err:
        HostWorktreeTarget(repo, runner=FakeRunner()).up(None, "feat__a/b")
    assert "feat/a__b" in str(err.value) and "feat__a/b" in str(err.value)
    # the first workspace's record is untouched
    kept = load_state(repo, "feat/a__b")
    assert kept is not None and kept.branch == "feat/a__b" and kept.worktree == first.worktree


def test_a_lookup_never_returns_another_branchs_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo, _origin = make_repo_with_origin(tmp_path)
    HostWorktreeTarget(repo, runner=FakeRunner()).up(None, "feat/a__b")
    assert load_state(repo, "feat__a/b") is None
    delete_state(repo, "feat__a/b")  # must not remove the other branch's record
    assert state_path(repo, "feat/a__b").is_file()


# ---------- gh#1166: resume uses the recorded mode ----------


def test_up_on_an_existing_workspace_resumes_in_its_recorded_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    repo, _origin = make_repo_with_origin(tmp_path, ["dev"], default="dev")
    fake = FakeRunner()
    HostWorktreeTarget(repo, runner=fake).up(None, "feat/h")
    monkeypatch.setattr(isolation_cmd, "_runner", fake)
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root, _mode: None)
    result = CliRunner().invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/h"])
    assert result.exit_code == 0, result.output
    st = load_state(repo, "feat/h")
    assert st is not None and st.target == "worktree" and st.profile == "host"
    assert not any(c and c[0] == "devcontainer" for c in fake.calls)


# ---------- gh#1243: scaffold from a linked worktree ----------


def test_scaffold_from_a_linked_worktree_names_the_repo_not_the_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr("fr.services.init.issues_enabled_for", lambda *a, **k: False)
    main = tmp_path / "myrepo"
    main.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(main), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (main / "README.md").write_text("seed\n")
    git("add", "README.md")
    git("commit", "-qm", "seed")
    wt = tmp_path / "feat__x"
    git("worktree", "add", "-q", "-b", "feat/x", str(wt))

    cfg_path = scaffold_profile(wt, "dev", "test", [], ["FOO"], commit=False, tracking="none")
    cfg = json.loads(cfg_path.read_text())
    assert cfg["name"].startswith("myrepo ")
    assert "/.config/fr/secrets/myrepo/dev.env" in cfg["runArgs"][1]
    assert (tmp_path / "home" / ".config" / "fr" / "secrets" / "myrepo" / "dev.env").is_file()
    assert not (tmp_path / "home" / ".config" / "fr" / "secrets" / "feat__x").exists()
