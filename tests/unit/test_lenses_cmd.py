"""`fr lenses list|show|check` over a tmp git repo (spec 2026-11-12-review-lenses R3)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()

BROKEN = "bogus: 1\ndisable: [nope]\n"


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "work"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "README.md").write_text("x\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    return root


def _config(root: Path, text: str) -> None:
    (root / ".fr").mkdir(exist_ok=True)
    (root / ".fr" / "lenses.yaml").write_text(text)


def test_list_prints_the_effective_lenses(repo: Path) -> None:
    r = runner.invoke(app, ["lenses", "list"])

    assert r.exit_code == 0, r.output
    lines = [ln for ln in r.output.splitlines() if ln.strip()]
    assert len(lines) == 4
    assert any("security" in ln and "Security" in ln and "shipped" in ln for ln in lines)


def test_list_json_is_the_same_as_data(repo: Path) -> None:
    _config(repo, "disable: [errors]\nlenses:\n  a11y:\n    title: A11y\n    brief: b\n")

    r = runner.invoke(app, ["lenses", "list", "--json"])

    assert r.exit_code == 0, r.output
    rows = {row["id"]: row for row in json.loads(r.output)}
    assert set(rows) == {"security", "tests", "simplicity", "a11y"}
    assert rows["a11y"] == {"id": "a11y", "title": "A11y", "source": "repo"}


def test_show_prints_the_brief(repo: Path) -> None:
    r = runner.invoke(app, ["lenses", "show", "security"])

    assert r.exit_code == 0, r.output
    assert "ordinary finding" in r.output
    assert "shell" in r.output


def test_show_an_unknown_lens_exits_2_naming_the_effective_ids(repo: Path) -> None:
    r = runner.invoke(app, ["lenses", "show", "nope"])

    assert r.exit_code == 2
    assert "nope" in r.output
    for lens_id in ("security", "tests", "simplicity", "errors"):
        assert lens_id in r.output


def test_check_is_clean_with_no_config_and_fails_a_broken_one(repo: Path) -> None:
    assert runner.invoke(app, ["lenses", "check"]).exit_code == 0

    _config(repo, "disable: [nope]\n")
    r = runner.invoke(app, ["lenses", "check"])

    assert r.exit_code == 1
    assert "nope" in r.output


def test_an_unreadable_config_makes_list_and_show_exit_2(repo: Path) -> None:
    _config(repo, BROKEN)

    assert runner.invoke(app, ["lenses", "list"]).exit_code == 2
    assert runner.invoke(app, ["lenses", "show", "security"]).exit_code == 2


def test_an_undecodable_config_makes_list_and_show_exit_2_without_a_traceback(
    repo: Path,
) -> None:
    (repo / ".fr").mkdir()
    (repo / ".fr" / "lenses.yaml").write_bytes(b"\xff\xfe\x00bad")

    for args in (["lenses", "list"], ["lenses", "show", "security"]):
        r = runner.invoke(app, args)
        assert r.exit_code == 2, r.output
        assert not isinstance(r.exception, UnicodeDecodeError)


def test_none_of_the_three_writes(repo: Path) -> None:
    _config(repo, "disable: [errors]\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "cfg")
    before = git(repo, "status", "--porcelain")

    for args in (["list"], ["list", "--json"], ["show", "security"], ["check"]):
        runner.invoke(app, ["lenses", *args])

    assert git(repo, "status", "--porcelain") == before == ""
