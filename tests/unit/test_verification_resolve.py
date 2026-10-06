"""`fr.verification.resolve` — repo > env > wheel > marketplace (spec §A, R1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr._shipped import MARKETPLACE_ROOT
from fr.verification import resolve as vresolve
from fr.verification.model import StrategyError
from fr.verification.resolve import (
    PLUGIN_VERIFICATIONS_REL,
    REPO_VERIFICATIONS_REL,
    list_strategies,
    resolve_strategy,
)


def _manifest(name: str, description: str = "") -> str:
    return (
        f"verification: {name}\nschema: 1\ndescription: {description}\n"
        "when: pre-merge\ndriver: agent\n"
    )


def _put(root: Path, rel: Path, name: str, description: str) -> None:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(_manifest(name, description))


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("FR_SHIPPED_VERIFICATIONS_DIR", raising=False)
    monkeypatch.setattr(vresolve, "packaged_shipped_verifications_dir", lambda: None)
    repo = tmp_path / "repo"
    repo.mkdir()
    return {"home": home, "repo": repo, "tmp": tmp_path}


def test_a_repo_file_wins_wholesale_over_a_shipped_one(env, monkeypatch) -> None:
    shipped = env["tmp"] / "shipped"
    _put(shipped, Path("."), "candidate", "shipped")
    monkeypatch.setenv("FR_SHIPPED_VERIFICATIONS_DIR", str(shipped))
    _put(env["repo"], REPO_VERIFICATIONS_REL, "candidate", "repo")

    assert resolve_strategy("candidate", env["repo"]).description == "repo"


def test_the_env_dir_is_consulted_before_the_wheel_and_the_clone(env, monkeypatch) -> None:
    envdir = env["tmp"] / "envdir"
    wheel = env["tmp"] / "wheel"
    _put(envdir, Path("."), "x", "env")
    _put(wheel, Path("."), "x", "wheel")
    _put(env["home"], MARKETPLACE_ROOT / PLUGIN_VERIFICATIONS_REL, "x", "clone")
    monkeypatch.setenv("FR_SHIPPED_VERIFICATIONS_DIR", str(envdir))
    monkeypatch.setattr(vresolve, "packaged_shipped_verifications_dir", lambda: wheel)

    assert resolve_strategy("x", env["repo"]).description == "env"


def test_the_wheel_beats_the_marketplace_clone(env, monkeypatch) -> None:
    wheel = env["tmp"] / "wheel"
    _put(wheel, Path("."), "x", "wheel")
    _put(env["home"], MARKETPLACE_ROOT / PLUGIN_VERIFICATIONS_REL, "x", "clone")
    monkeypatch.setattr(vresolve, "packaged_shipped_verifications_dir", lambda: wheel)

    assert resolve_strategy("x", env["repo"]).description == "wheel"


def test_the_marketplace_clone_is_the_last_resort(env) -> None:
    _put(env["home"], MARKETPLACE_ROOT / PLUGIN_VERIFICATIONS_REL, "x", "clone")

    assert resolve_strategy("x", env["repo"]).description == "clone"


def test_an_unknown_name_names_every_place_looked(env, monkeypatch) -> None:
    monkeypatch.setenv("FR_SHIPPED_VERIFICATIONS_DIR", str(env["tmp"] / "envdir"))

    with pytest.raises(StrategyError) as e:
        resolve_strategy("ghost", env["repo"])

    msg = str(e.value)
    assert "ghost" in msg
    assert str(env["repo"] / REPO_VERIFICATIONS_REL / "ghost.yaml") in msg
    assert str(env["tmp"] / "envdir" / "ghost.yaml") in msg
    assert str(env["home"] / MARKETPLACE_ROOT / PLUGIN_VERIFICATIONS_REL / "ghost.yaml") in msg


def test_the_reserved_name_none_never_resolves(env) -> None:
    with pytest.raises(StrategyError, match="none"):
        resolve_strategy("none", env["repo"])


def test_a_manifest_whose_name_disagrees_with_its_file_is_refused(env) -> None:
    d = env["repo"] / REPO_VERIFICATIONS_REL
    d.mkdir(parents=True)
    (d / "a.yaml").write_text(_manifest("b"))

    with pytest.raises(StrategyError, match="a.yaml"):
        resolve_strategy("a", env["repo"])


def test_list_returns_every_name_once_with_its_source(env, monkeypatch) -> None:
    shipped = env["tmp"] / "shipped"
    _put(shipped, Path("."), "candidate", "shipped")
    _put(shipped, Path("."), "live", "shipped")
    monkeypatch.setenv("FR_SHIPPED_VERIFICATIONS_DIR", str(shipped))
    _put(env["repo"], REPO_VERIFICATIONS_REL, "candidate", "repo")
    _put(env["repo"], REPO_VERIFICATIONS_REL, "staging", "repo")

    assert list_strategies(env["repo"]) == [
        ("candidate", "repo"),
        ("live", "env"),
        ("staging", "repo"),
    ]


def test_list_labels_wheel_and_clone(env, monkeypatch) -> None:
    wheel = env["tmp"] / "wheel"
    _put(wheel, Path("."), "a", "")
    _put(env["home"], MARKETPLACE_ROOT / PLUGIN_VERIFICATIONS_REL, "b", "")
    monkeypatch.setattr(vresolve, "packaged_shipped_verifications_dir", lambda: wheel)

    assert list_strategies(env["repo"]) == [("a", "wheel"), ("b", "marketplace")]
