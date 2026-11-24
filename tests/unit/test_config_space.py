"""The configuration space resolver (spec 2026-11-19-event-driven-a-la-carte §A, R1-R4)."""

from __future__ import annotations

import json
from pathlib import Path

import fr.config.space as space_mod
import pytest
from fr.config.space import ConfigSpace, config_space

from tests.unit.settings_repo import git, make_repo


def test_the_resolver_names_its_spec() -> None:
    assert "2026-11-19-event-driven-a-la-carte" in (space_mod.__doc__ or "")


# --- ConfigSpace under repo, quiet and stealth (R1, R2) ---------------------------------

QUIET = "schema: 1\nplacement: quiet\nforge:\n  labels: off\n"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _push_orphan(root: Path, branch: str, files: dict[str, str]) -> None:
    """An orphan *branch* on origin holding *files*; the local branch is deleted again."""
    back = git(root, "symbolic-ref", "--short", "HEAD").strip()
    git(root, "checkout", "-q", "--orphan", branch)
    git(root, "rm", "-rfq", ".")
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    git(root, "add", "-A")
    git(root, "commit", "-qm", branch)
    git(root, "push", "-q", "origin", branch)
    git(root, "checkout", "-q", back)
    git(root, "branch", "-q", "-D", branch)


def _commit(root: Path, rel: str, text: str, *, push: bool = True) -> str:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text)
    git(root, "add", "-A")
    git(root, "commit", "-qm", rel)
    if push:
        git(root, "push", "-q", "origin", "HEAD")
    return git(root, "rev-parse", "HEAD").strip()


def quiet_repo(tmp_path: Path) -> Path:
    root = make_repo(tmp_path)
    _push_orphan(root, "fr", {"settings.yaml": QUIET})
    git(root, "checkout", "-q", "-b", "feat/q")
    return root


def stealth_repo(tmp_path: Path, home: Path) -> tuple[Path, Path]:
    """A product checkout with a stealth marker, and its configuration clone (on
    `main-config`, the tracking branch `main`'s configuration branch)."""
    root = make_repo(tmp_path)
    git(root, "checkout", "-q", "-b", "feat/s")
    track = tmp_path / "track.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(track))
    marker = {
        "toplevel": str(root),
        "branch": "feat/s",
        "mode": "worktree",
        "placement": "stealth",
        "tracking": {"ref": f"{track}@main", "target": "local--work"},
    }
    (root / ".fr-isolation").write_text(json.dumps(marker))
    clone = home / ".cache" / "fr" / "worktrees" / "work" / "stealth--local--track--main-config"
    return root, clone


def test_repo_space_is_the_product_checkout(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    space = config_space(root)
    assert isinstance(space, ConfigSpace)
    assert space.placement == "repo"
    assert space.dir == root / ".fr"
    assert space.checkout == root
    assert space.default_ref == "origin/main"


def test_repo_at_default_reads_the_default_branch_never_the_working_tree(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    assert config_space(root).at_default(".fr/ci.yaml") is None
    _commit(root, ".fr/ci.yaml", "gate_checks: [a]\n")
    (root / ".fr" / "ci.yaml").write_text("gate_checks: [local]\n")
    assert config_space(root).at_default(".fr/ci.yaml") == "gate_checks: [a]\n"
    assert config_space(root).at_default("ci.yaml") == "gate_checks: [a]\n"


def test_quiet_space_is_the_fr_config_worktree(tmp_path: Path, _home: Path) -> None:
    root = quiet_repo(tmp_path)
    space = config_space(root)
    assert space.placement == "quiet"
    checkout = _home / ".cache" / "fr" / "worktrees" / "work" / "fr-config"
    assert space.checkout == checkout
    assert space.dir == checkout / ".fr"
    assert space.default_ref == "origin/fr-config"


def test_quiet_at_default_reads_the_fr_config_tip(tmp_path: Path) -> None:
    root = quiet_repo(tmp_path)
    _commit(root, ".fr/ci.yaml", "gate_checks: [product]\n", push=False)
    assert config_space(root).at_default(".fr/ci.yaml") is None
    _push_orphan(root, "fr-config", {".fr/ci.yaml": "gate_checks: [config]\n"})
    assert config_space(root).at_default(".fr/ci.yaml") == "gate_checks: [config]\n"


def test_stealth_space_is_the_configuration_clone(tmp_path: Path, _home: Path) -> None:
    root, clone = stealth_repo(tmp_path, _home)
    space = config_space(root)
    assert space.placement == "stealth"
    assert space.checkout == clone
    assert space.dir == clone / "local--work" / ".fr"
    assert space.default_ref == "origin/main-config"


def test_stealth_at_default_reads_the_config_branch_in_the_clone(
    tmp_path: Path, _home: Path
) -> None:
    root, clone = stealth_repo(tmp_path, _home)
    assert config_space(root).at_default(".fr/ci.yaml") is None
    track = tmp_path / "track.git"
    seed = tmp_path / "seed"
    git(tmp_path, "init", "-q", "-b", "main-config", str(seed))
    git(seed, "remote", "add", "origin", str(track))
    _commit(seed, "local--work/.fr/ci.yaml", "gate_checks: [stealth]\n")
    git(tmp_path, "clone", "-q", "-b", "main-config", str(track), str(clone))
    assert config_space(root).at_default(".fr/ci.yaml") == "gate_checks: [stealth]\n"
