"""#286 — bridge-owned dedicated checkout + self-healing sync.

The bridge stops sharing VK's checkout: it maintains its OWN checkout per
managed repo (sole writer → no out-of-band desync), and syncs it each tick
with `fetch origin` + `reset --hard origin/main` (idempotent/self-healing).

These tests build a real bare origin + clones so the git plumbing
(`_ensure_bridge_checkout`, `_pull_managed_repo`) is exercised end-to-end,
not mocked.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )


def _init_bare_with_clone(tmp_path: Path) -> Path:
    """Bare origin (branch `main`, seeded) + a clone at `<tmp>/repos/foo`.

    The clone's `origin` points at the bare, so a bridge checkout cloned
    from the clone's origin URL also tracks the same bare — `fetch origin`
    + `reset --hard origin/main` reach true head-of-main.
    """
    bare = tmp_path / "origin.git"
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    clone = repos_dir / "foo"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True
    )

    seed = tmp_path / "_seed"
    seed.mkdir()
    _git(seed, "init", "-b", "main")
    _git(seed, "config", "user.email", "test@example.com")
    _git(seed, "config", "user.name", "test")
    (seed / "README.md").write_text("seed\n")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(bare))
    _git(seed, "push", "origin", "main")

    subprocess.run(["git", "clone", str(bare), str(clone)], check=True, capture_output=True)
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "test")
    return clone


def _advance_origin(tmp_path: Path, *, plan: str = "new-plan") -> None:
    """Push a new plan dir to origin/main via the seed working tree."""
    seed = tmp_path / "_seed"
    plan_dir = seed / "docs" / "superpowers" / "plans" / plan
    plan_dir.mkdir(parents=True)
    (plan_dir / "_meta.yaml").write_text(f"plan: {plan}\ntarget_repo: example/foo\n")
    (plan_dir / "_prose.md").write_text(f"# {plan}\n")
    _git(seed, "add", ".")
    _git(seed, "commit", "-m", f"add {plan}")
    _git(seed, "push", "origin", "main")


# --- Task 1: _bridge_checkout_base ---------------------------------------


def test_base_honours_env(monkeypatch, tmp_path):
    monkeypatch.setenv("FR_BRIDGE_CHECKOUT_DIR", str(tmp_path / "co"))
    from fr_vk import bridge_cli

    assert bridge_cli._bridge_checkout_base() == (tmp_path / "co")


def test_base_default(monkeypatch):
    monkeypatch.delenv("FR_BRIDGE_CHECKOUT_DIR", raising=False)
    monkeypatch.delenv("VK_BRIDGE_CHECKOUT_DIR", raising=False)
    from fr_vk import bridge_cli

    assert bridge_cli._bridge_checkout_base() == Path("~/.cache/fr/bridge-checkouts").expanduser()


# --- Task 2: _ensure_bridge_checkout (clone-if-missing) ------------------


def test_ensure_clones_when_missing(tmp_path):
    clone = _init_bare_with_clone(tmp_path)  # the configured shared checkout
    base = tmp_path / "bridge-co"
    from fr_vk import bridge_cli

    dest = bridge_cli._ensure_bridge_checkout(clone, "foo", base)
    assert dest == base / "foo"
    assert (dest / ".git").exists()
    # Cloned from the real origin, so origin/main resolves.
    out = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "origin/main"], capture_output=True, text=True
    )
    assert out.returncode == 0


def test_ensure_returns_existing_without_reclone(tmp_path):
    clone = _init_bare_with_clone(tmp_path)
    base = tmp_path / "bridge-co"
    from fr_vk import bridge_cli

    first = bridge_cli._ensure_bridge_checkout(clone, "foo", base)
    # Marker file survives only if the second call does NOT re-clone.
    (first / ".bridge-marker").write_text("x")
    second = bridge_cli._ensure_bridge_checkout(clone, "foo", base)
    assert second == first
    assert (first / ".bridge-marker").exists()


def test_ensure_returns_none_on_unresolvable_origin(tmp_path, caplog):
    no_origin = tmp_path / "no-origin"
    _git_init(no_origin)  # a git repo with no `origin` remote
    base = tmp_path / "bridge-co"
    from fr_vk import bridge_cli

    dest = bridge_cli._ensure_bridge_checkout(no_origin, "foo", base)
    assert dest is None


def _git_init(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "test")


# --- Task 3: _pull_managed_repo self-healing sync ------------------------


def _head(repo: Path, ref: str = "HEAD") -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _porcelain(repo: Path) -> str:
    return _git(repo, "status", "--porcelain").stdout.strip()


def test_clean_advance_fast_forwards_and_not_flagged(tmp_path):
    clone = _init_bare_with_clone(tmp_path)
    _advance_origin(tmp_path)  # origin/main now ahead; clone is clean but behind
    from fr_vk import bridge_cli

    desynced = bridge_cli._pull_managed_repo(clone)
    assert desynced is False  # clean-but-behind is a normal fast-forward, not a desync
    assert _porcelain(clone) == ""
    assert (clone / "docs" / "superpowers" / "plans" / "new-plan" / "_meta.yaml").exists()
    assert _head(clone) == _head(clone, "origin/main")


def test_dirty_tree_at_head_is_healed_and_flagged(tmp_path):
    """Reproduce the #286 signature: HEAD == origin/main but the index/tree
    is frozen at the pre-merge parent (VK force-moved the ref out-of-band).
    `reset --soft origin/main` reproduces exactly that state."""
    clone = _init_bare_with_clone(tmp_path)
    _advance_origin(tmp_path)
    _git(clone, "fetch", "origin")
    # HEAD/main := origin/main, but index + worktree stay at the old tree →
    # git reports the merged-in plan as a staged deletion. The bug signature.
    _git(clone, "reset", "--soft", "origin/main")
    assert _head(clone) == _head(clone, "origin/main")
    assert _porcelain(clone) != ""  # dirty despite HEAD already at origin/main
    from fr_vk import bridge_cli

    desynced = bridge_cli._pull_managed_repo(clone)
    assert desynced is True
    assert _porcelain(clone) == ""  # tree reconciled
    assert _head(clone) == _head(clone, "origin/main")
    assert (clone / "docs" / "superpowers" / "plans" / "new-plan" / "_meta.yaml").exists()


def test_git_failure_logs_and_returns_false(tmp_path, caplog):
    no_origin = tmp_path / "no-origin"
    _git_init(no_origin)  # git repo with no `origin` remote → fetch origin fails
    (no_origin / "f.txt").write_text("x")
    _git(no_origin, "add", "f.txt")
    _git(no_origin, "commit", "-m", "c")
    from fr_vk import bridge_cli

    with caplog.at_level(logging.WARNING):
        desynced = bridge_cli._pull_managed_repo(no_origin)  # no raise
    assert desynced is False
    assert any("sync failed" in r.message or "stale checkout" in r.message for r in caplog.records)
