"""Version reservations (spec 2026-09-25-triage-batches §3.D; Test Plan 11, 17).

The pure half (`fr.triage.batch_version`) with no I/O, and the one read that
touches git — the source manifest at `origin/<default>` — against a real
throwaway clone, so "not the working tree" is proven rather than assumed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.triage.batch_version import (
    all_version_files,
    bump_version,
    read_source,
    reserve,
    slot_versions,
)
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout, repo_of_url
from fr.triage.model import VersionSource


@pytest.mark.parametrize(
    ("bump", "want"), [("patch", "4.21.2"), ("minor", "4.22.0"), ("major", "5.0.0")]
)
def test_bump_levels(bump: str, want: str) -> None:
    assert bump_version("4.21.1", bump) == want  # type: ignore[arg-type]


def test_a_non_semver_version_is_refused() -> None:
    with pytest.raises(TriageError, match="MAJOR.MINOR.PATCH"):
        bump_version("4.21", "patch")


def test_the_source_is_read_by_key_from_toml_and_json() -> None:
    toml = '[project]\nname = "x"\nversion = "1.2.3"\n[tool.other]\nversion = "9.9.9"\n'
    assert read_source(toml, VersionSource(file="pyproject.toml", key="project.version")) == "1.2.3"
    js = '{"name": "x", "version": "2.0.1", "dependencies": {"version": "9.9.9"}}'
    assert read_source(js, VersionSource(file="package.json", key="version")) == "2.0.1"


def test_a_missing_key_is_refused_by_name() -> None:
    with pytest.raises(TriageError, match="project.version"):
        read_source("[tool]\n", VersionSource(file="pyproject.toml", key="project.version"))


def test_the_reservation_follows_the_highest_live_reservation() -> None:
    """Dispatch sequence: each reservation is the next after every live one."""
    assert reserve("4.21.1", [], "minor") == "4.22.0"
    assert reserve("4.21.1", ["4.22.0"], "patch") == "4.22.1"
    assert reserve("4.21.1", ["4.22.1", "4.22.0"], "major") == "5.0.0"
    assert reserve("4.30.0", ["4.22.0"], "patch") == "4.30.1"  # origin moved past them


def test_slots_follow_merge_order_and_each_batchs_bump() -> None:
    """Explicit order then sequence decides the queue; each slot is the previous
    one bumped by that batch's level (§3.D Reconcile)."""
    assert slot_versions("4.21.1", ["minor", "patch", "patch"]) == ["4.22.0", "4.22.1", "4.22.2"]
    assert slot_versions("4.21.1", ["patch", "minor"]) == ["4.21.2", "4.22.0"]


def test_version_file_globs_are_repo_relative() -> None:
    globs = ["pyproject.toml", "packages/*/pyproject.toml", "uv.lock"]
    assert all_version_files(["uv.lock", "packages/fr/pyproject.toml"], globs)
    assert not all_version_files(["uv.lock", "packages/fr/src/fr/cli.py"], globs)


@pytest.mark.parametrize(
    ("url", "repo"),
    [
        ("https://github.com/derio-net/super-fr.git", "derio-net/super-fr"),
        ("https://github.com/derio-net/super-fr", "derio-net/super-fr"),
        ("git@github.com:derio-net/super-fr.git", "derio-net/super-fr"),
        ("ssh://git@github.com/derio-net/super-fr.git", "derio-net/super-fr"),
        ("/tmp/origin.git", None),
    ],
)
def test_origin_urls_resolve_to_owner_repo(url: str, repo: str | None) -> None:
    assert repo_of_url(url) == repo


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def test_the_source_is_read_from_origin_not_the_working_tree(tmp_path: Path) -> None:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=trunk", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "--quiet", str(origin), str(seed))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com")):
        _git(seed, "config", k, v)
    (seed / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    _git(seed, "add", ".")
    _git(seed, "commit", "--quiet", "-m", "seed")
    _git(seed, "push", "--quiet", "origin", "HEAD:trunk")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    (clone / "pyproject.toml").write_text('[project]\nversion = "9.9.9"\n')  # local edit

    checkout = Checkout.at(clone / ".")
    checkout.fetch()
    default = checkout.default_branch()
    assert default == "trunk"
    text = checkout.show(f"origin/{default}", "pyproject.toml")
    assert text is not None
    assert read_source(text, VersionSource(file="pyproject.toml", key="project.version")) == "1.0.0"
    assert checkout.show(f"origin/{default}", "absent.toml") is None
    assert not checkout.remote_branch_exists("feat/batch-x")


@pytest.mark.parametrize(
    ("base", "head", "want"),
    [
        ('[project]\nversion = "1.0.0"\n', '[project]\nversion = "1.0.2"\n', True),
        ('{"version": "1.0.0"}\n', '{"version": "1.0.2"}\n', True),
        ('version = "1.0.0"\n', 'version = "1.0.0"\n', True),
        (
            '[project]\nversion = "1.0.0"\n',
            '[project]\nversion = "1.0.2"\ndependencies = ["requests"]\n',
            False,
        ),
        ('deps = ["demo>=1.0.0"]\n', 'deps = ["demo>=1.0.2"]\n', False),
        ('name = "a"\nversion = "1.0.0"\n', 'name = "b"\nversion = "1.0.2"\n', False),
    ],
    ids=["toml", "json", "unchanged", "added-dependency", "a-pin-is-not-a-version", "renamed"],
)
def test_only_version_changed(base: str, head: str, want: bool) -> None:
    from fr.triage.batch_version import only_version_changed

    assert only_version_changed(base, head, "1.0.0", "1.0.2") is want


@pytest.mark.parametrize(
    ("path", "want"),
    [("uv.lock", True), ("web/package-lock.json", True), ("Cargo.lock", True),
     ("package.json", False), ("pyproject.toml", False)],
)  # fmt: skip
def test_lockfiles_are_known_by_name(path: str, want: bool) -> None:
    from fr.triage.batch_version import is_lockfile

    assert is_lockfile(path) is want
