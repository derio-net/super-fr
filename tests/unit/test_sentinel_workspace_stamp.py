"""stamp_sentinel_workspace — the sentinel records its bound workspace (cache-relative)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.isolation import sessions
from fr.isolation.types import (
    IsolationState,
    clear_workspace_sentinels,
    save_state,
    stamp_sentinel_workspace,
)


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FR_SENTINEL_DIR", str(home / "s"))
    monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
    (home / "s").mkdir()
    return home


def _repo(home: Path, name: str = "repo") -> Path:
    repo = home / "src" / name
    if not repo.is_dir():
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@example.com", "-c", "user.name=t"]
            + ["commit", "-q", "--allow-empty", "-m", "init"],
            check=True,
        )
    return repo


def _sentinel(home: Path, sid: str = "sess", repo: str = "repo") -> Path:
    p = home / "s" / f"{sid}.json"
    root = str(_repo(home, repo))
    p.write_text(json.dumps({"repo_root": root, "skill": "fr-goal", "started_at": "t"}))
    return p


def _wt(home: Path, rel: str = "worktrees/repo/feat__x", repo: str = "repo") -> Path:
    """A REAL linked worktree of `repo`, at `~/.cache/fr/<rel>` — the stamp now
    checks ownership, so a plain directory is (correctly) never stamped."""
    wt = home / ".cache" / "fr" / rel
    wt.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(_repo(home, repo)), "worktree", "add", "-q", str(wt), "-b", wt.name],
        check=True,
    )
    return wt


def test_stamps_relative_workspace_and_keeps_keys(env: Path) -> None:
    p = _sentinel(env)
    stamp_sentinel_workspace("sess", _wt(env))
    data = json.loads(p.read_text())
    assert data["workspaces"] == ["worktrees/repo/feat__x"]
    assert all(str(env) not in w and not w.startswith("/") for w in data["workspaces"])
    assert (
        data["repo_root"].endswith("/src/repo")
        and data["skill"] == "fr-goal"
        and data["started_at"] == "t"
    )


def test_no_sentinel_is_a_noop(env: Path) -> None:
    stamp_sentinel_workspace("sess", _wt(env))
    assert list((env / "s").iterdir()) == []


def test_worktree_outside_cache_is_not_stamped(env: Path, tmp_path: Path) -> None:
    p = _sentinel(env)
    before = p.read_bytes()
    out = tmp_path / "elsewhere"
    out.mkdir()
    stamp_sentinel_workspace("sess", out)
    assert p.read_bytes() == before


def test_binding_a_second_workspace_adds_it(env: Path) -> None:
    """A session may bind several workspaces of one repo (`fr isolation exec
    --branch <other>` rebinds). The stamp is a SET: replacing it let the other
    workspace's teardown disarm this session's live pipeline (review C1)."""
    p = _sentinel(env)
    stamp_sentinel_workspace("sess", _wt(env))
    stamp_sentinel_workspace("sess", _wt(env, "worktrees/repo/other"))
    stamp_sentinel_workspace("sess", _wt(env, "worktrees/repo/third"))
    stamp_sentinel_workspace("sess", env / ".cache" / "fr" / "worktrees/repo/other")
    assert json.loads(p.read_text())["workspaces"] == [
        "worktrees/repo/feat__x",
        "worktrees/repo/other",
        "worktrees/repo/third",
    ]


def test_dead_entries_are_pruned_on_stamp(env: Path) -> None:
    import shutil as _sh

    p = _sentinel(env)
    gone = _wt(env, "worktrees/repo/gone")
    stamp_sentinel_workspace("sess", gone)
    _sh.rmtree(gone)
    stamp_sentinel_workspace("sess", _wt(env))
    assert json.loads(p.read_text())["workspaces"] == ["worktrees/repo/feat__x"]


def test_symlinked_worktrees_dir_still_stamps(env: Path, tmp_path: Path) -> None:
    """`~/.cache/fr/worktrees` symlinked to another volume: fr stores the
    unresolved path, and resolving it first left nothing relative (review L1)."""
    real = tmp_path / "volume"
    real.mkdir()
    (env / ".cache" / "fr").mkdir(parents=True)
    (env / ".cache" / "fr" / "worktrees").symlink_to(real)
    p = _sentinel(env)
    stamp_sentinel_workspace("sess", _wt(env))
    assert json.loads(p.read_text())["workspaces"] == ["worktrees/repo/feat__x"]


def test_malformed_sentinel_left_byte_identical(env: Path) -> None:
    p = env / "s" / "sess.json"
    p.write_text("{not json")
    stamp_sentinel_workspace("sess", _wt(env))
    assert p.read_text() == "{not json"


def test_write_is_atomic(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import fr.isolation.types as t

    calls: list[Path] = []
    real = t.write_text_atomic
    monkeypatch.setattr(t, "write_text_atomic", lambda p, s: (calls.append(p), real(p, s))[1])
    p = _sentinel(env)
    stamp_sentinel_workspace("sess", _wt(env))
    assert calls == [p]
    assert not [f for f in p.parent.iterdir() if f.name != p.name]


def test_attach_stamps_sentinel(env: Path) -> None:
    repo = _repo(env)
    wt = _wt(env)
    save_state(
        IsolationState(
            repo_root=repo,
            branch="feat/x",
            worktree=wt,
            profile="host",
            created_at="2026-09-05T00:00:00+00:00",
        )
    )
    p = _sentinel(env)
    sessions.attach(repo, "feat/x", "sess")
    assert json.loads(p.read_text())["workspaces"] == ["worktrees/repo/feat__x"]


def test_a_foreign_repos_worktree_never_stamps(env: Path) -> None:
    """Binding this session to repo B must not rewrite repo A's sentinel: the
    guard would read A's stamp as orphaned and retire A's live pipeline."""
    p = _sentinel(env, repo="a")
    stamp_sentinel_workspace("sess", _wt(env, "worktrees/a/feat__a", repo="a"))
    stamp_sentinel_workspace("sess", _wt(env, "worktrees/b/feat__b", repo="b"))
    assert json.loads(p.read_text())["workspaces"] == ["worktrees/a/feat__a"]


def test_unreadable_repo_root_is_not_stamped(env: Path) -> None:
    p = env / "s" / "sess.json"
    p.write_text(json.dumps({"repo_root": str(env / "gone"), "skill": "fr-goal"}))
    before = p.read_bytes()
    stamp_sentinel_workspace("sess", _wt(env))
    assert p.read_bytes() == before


class TestClearWorkspaceSentinels:
    """`fr isolation down`'s eager clear, scoped to the torn-down workspace (#472)."""

    def test_stamped_to_this_worktree_is_cleared(self, env: Path) -> None:
        wt = _wt(env)
        p = _sentinel(env)
        stamp_sentinel_workspace("sess", wt)
        assert clear_workspace_sentinels(_repo(env), wt) == 1
        assert not p.exists()

    def test_bound_but_unstamped_session_is_cleared(self, env: Path) -> None:
        p = _sentinel(env)
        assert clear_workspace_sentinels(_repo(env), _wt(env), ["sess"]) == 1
        assert not p.exists()

    def test_another_sessions_fresh_sentinel_survives(self, env: Path) -> None:
        """The third #472 mechanism: 'zero workspaces remain → clear the repo'
        disarmed a pipeline that simply had not created its workspace yet."""
        wt = _wt(env)
        mine = _sentinel(env, "mine")
        stamp_sentinel_workspace("mine", wt)
        theirs = _sentinel(env, "theirs")
        assert clear_workspace_sentinels(_repo(env), wt) == 1
        assert not mine.exists() and theirs.exists()

    def test_other_workspace_and_other_repo_survive(self, env: Path) -> None:
        wt = _wt(env)
        other = _sentinel(env, "other")
        stamp_sentinel_workspace("other", _wt(env, "worktrees/repo/feat__y"))
        foreign = _sentinel(env, "foreign", repo="b")
        assert clear_workspace_sentinels(_repo(env), wt, ["foreign"]) == 0
        assert other.exists() and foreign.exists()

    def test_session_with_another_live_workspace_keeps_its_sentinel(self, env: Path) -> None:
        """Review C1: S bound its own W_S, then `exec --branch <other>` bound W_o
        too. W_o's teardown names S (bound, stamped) — but S still has a live
        workspace, so its pipeline is live: drop the entry, keep the sentinel."""
        import shutil as _sh

        mine = _wt(env)
        theirs = _wt(env, "worktrees/repo/theirs")
        p = _sentinel(env)
        stamp_sentinel_workspace("sess", mine)
        stamp_sentinel_workspace("sess", theirs)
        _sh.rmtree(theirs)  # torn down
        assert clear_workspace_sentinels(_repo(env), theirs, ["sess"]) == 0
        assert json.loads(p.read_text())["workspaces"] == ["worktrees/repo/feat__x"]
