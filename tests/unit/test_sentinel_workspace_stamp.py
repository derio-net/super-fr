"""stamp_sentinel_workspace — the sentinel records its bound workspace (cache-relative)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.isolation import sessions
from fr.isolation.types import IsolationState, save_state, stamp_sentinel_workspace


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FR_SENTINEL_DIR", str(home / "s"))
    monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
    (home / "s").mkdir()
    return home


def _sentinel(home: Path, sid: str = "sess") -> Path:
    p = home / "s" / f"{sid}.json"
    p.write_text(json.dumps({"repo_root": "/r", "skill": "fr-goal", "started_at": "t"}))
    return p


def _wt(home: Path, rel: str = "worktrees/repo/feat__x") -> Path:
    wt = home / ".cache" / "fr" / rel
    wt.mkdir(parents=True)
    return wt


def test_stamps_relative_workspace_and_keeps_keys(env: Path) -> None:
    p = _sentinel(env)
    stamp_sentinel_workspace("sess", _wt(env))
    data = json.loads(p.read_text())
    assert data["workspace"] == "worktrees/repo/feat__x"
    assert str(env) not in p.read_text()
    assert data["repo_root"] == "/r" and data["skill"] == "fr-goal" and data["started_at"] == "t"


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


def test_restamp_on_different_workspace(env: Path) -> None:
    p = _sentinel(env)
    stamp_sentinel_workspace("sess", _wt(env))
    stamp_sentinel_workspace("sess", _wt(env, "worktrees/repo/other"))
    assert json.loads(p.read_text())["workspace"] == "worktrees/repo/other"


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


def test_attach_stamps_sentinel(env: Path, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
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
    assert json.loads(p.read_text())["workspace"] == "worktrees/repo/feat__x"
