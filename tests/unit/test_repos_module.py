"""Unit tests for fr.repos — manifest model, checkout resolver, template, append.

The module backs `fr repos sync` (instrument already-checked-out repos with a
docs/superpowers/plan-config.yaml). It lives in the base `fr` package and must
never import fr_dispatch (layering: fr_dispatch -> fr).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# --- load_manifest -----------------------------------------------------------


def test_load_manifest_missing_returns_empty(tmp_path: Path) -> None:
    from fr.repos import load_manifest

    assert load_manifest(tmp_path / "nope.yaml") == []


def test_load_manifest_string_and_mapping_entries(tmp_path: Path) -> None:
    from fr.repos import RepoEntry, load_manifest

    m = tmp_path / "repos.yaml"
    m.write_text(
        "repos:\n"
        "  - derio-net/super-fr\n"
        "  - owner/other\n"
        "  - repo: owner/custom\n"
        "    path: /abs/custom\n"
    )
    entries = load_manifest(m)
    assert entries == [
        RepoEntry(repo="derio-net/super-fr"),
        RepoEntry(repo="owner/other"),
        RepoEntry(repo="owner/custom", path="/abs/custom"),
    ]


def test_load_manifest_empty_file_returns_empty(tmp_path: Path) -> None:
    from fr.repos import load_manifest

    m = tmp_path / "repos.yaml"
    m.write_text("")
    assert load_manifest(m) == []


def test_load_manifest_rejects_non_mapping_top_level(tmp_path: Path) -> None:
    from fr.repos import ManifestError, load_manifest

    m = tmp_path / "repos.yaml"
    m.write_text("- just\n- a\n- list\n")
    with pytest.raises(ManifestError):
        load_manifest(m)


def test_load_manifest_rejects_non_list_repos(tmp_path: Path) -> None:
    from fr.repos import ManifestError, load_manifest

    m = tmp_path / "repos.yaml"
    m.write_text("repos: not-a-list\n")
    with pytest.raises(ManifestError):
        load_manifest(m)


def test_load_manifest_rejects_mapping_without_repo_key(tmp_path: Path) -> None:
    from fr.repos import ManifestError, load_manifest

    m = tmp_path / "repos.yaml"
    m.write_text("repos:\n  - path: /abs/only\n")
    with pytest.raises(ManifestError):
        load_manifest(m)


# --- checkout_root -----------------------------------------------------------


def test_checkout_root_uses_explicit_path() -> None:
    from fr.repos import RepoEntry, checkout_root

    entry = RepoEntry(repo="owner/name", path="/abs/elsewhere")
    assert checkout_root(entry) == Path("/abs/elsewhere")


def test_checkout_root_uses_fr_repos_dir_env(monkeypatch) -> None:
    from fr.repos import RepoEntry, checkout_root

    monkeypatch.setenv("FR_REPOS_DIR", "/srv/checkouts")
    entry = RepoEntry(repo="derio-net/super-fr")
    assert checkout_root(entry) == Path("/srv/checkouts/super-fr")


def test_checkout_root_defaults_to_home_repos(monkeypatch) -> None:
    from fr.repos import RepoEntry, checkout_root

    monkeypatch.delenv("FR_REPOS_DIR", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/op")))
    entry = RepoEntry(repo="derio-net/super-fr")
    assert checkout_root(entry) == Path("/home/op/repos/super-fr")


def test_checkout_root_explicit_repos_dir_kwarg_wins_over_env(monkeypatch) -> None:
    from fr.repos import RepoEntry, checkout_root

    monkeypatch.setenv("FR_REPOS_DIR", "/srv/checkouts")
    entry = RepoEntry(repo="owner/name")
    assert checkout_root(entry, repos_dir=Path("/tmp/r")) == Path("/tmp/r/name")


# --- render_plan_config ------------------------------------------------------


def test_render_plan_config_is_live_profile_only() -> None:
    from fr.repos import render_plan_config

    text = render_plan_config()  # no args — the dispatch stub is gone
    data = yaml.safe_load(text)
    assert data["plan"]["filename"] == "YYYY-MM-DD-{name}.md"
    assert "Spec" in data["header"]["required"]
    assert "Status" in data["header"]["required"]
    assert "Not Started" in data["header"]["status_values"]
    # No dead keys emitted (neither dispatch nor save_to, commented or live).
    assert "dispatch" not in text
    assert "save_to" not in text


# --- append_to_manifest ------------------------------------------------------


def test_append_to_manifest_creates_file_and_parents(tmp_path: Path) -> None:
    from fr.repos import append_to_manifest, load_manifest

    m = tmp_path / "nested" / "repos.yaml"
    assert append_to_manifest(m, "owner/new") is True
    assert [e.repo for e in load_manifest(m)] == ["owner/new"]


def test_append_to_manifest_is_idempotent(tmp_path: Path) -> None:
    from fr.repos import append_to_manifest, load_manifest

    m = tmp_path / "repos.yaml"
    m.write_text("repos:\n  - owner/exists\n")
    assert append_to_manifest(m, "owner/exists") is False
    assert [e.repo for e in load_manifest(m)] == ["owner/exists"]


def test_append_to_manifest_idempotent_against_mapping_entry(tmp_path: Path) -> None:
    from fr.repos import append_to_manifest, load_manifest

    m = tmp_path / "repos.yaml"
    m.write_text("repos:\n  - repo: owner/exists\n    path: /abs\n")
    assert append_to_manifest(m, "owner/exists") is False
    assert len(load_manifest(m)) == 1


def test_append_to_manifest_preserves_existing(tmp_path: Path) -> None:
    from fr.repos import append_to_manifest, load_manifest

    m = tmp_path / "repos.yaml"
    m.write_text("repos:\n  - owner/a\n")
    append_to_manifest(m, "owner/b")
    assert [e.repo for e in load_manifest(m)] == ["owner/a", "owner/b"]
