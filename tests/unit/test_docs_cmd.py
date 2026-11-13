"""`fr docs check` and `status` over real tmp git repos (docs-currency R1, R3, R6-R8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()

PAGE = "---\ntitle: A\ncovers:\n  - src/*.py\nreviewed: 2026-11-11 first\n---\n# A\n"
CONFIG = "pages:\n  - docs/*.md\n"


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def commit(root: Path, msg: str = "c") -> None:
    git(root, "add", "-A")
    git(root, "commit", "-qm", msg)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo on `main` with a bare origin, a config, one page and one covered file."""
    origin = tmp_path / "origin.git"
    root = tmp_path / "work"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    git(root, "remote", "add", "origin", str(origin))
    (root / ".fr").mkdir()
    (root / ".fr" / "docs.yaml").write_text(CONFIG)
    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text(PAGE)
    (root / "src").mkdir()
    (root / "src" / "x.py").write_text("x = 1\n")
    commit(root, "base")
    git(root, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    git(root, "remote", "set-head", "origin", "main")
    git(root, "checkout", "-q", "-b", "feature")
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    return root


def porcelain(root: Path) -> str:
    return git(root, "status", "--porcelain")


def test_no_config_is_nothing_to_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setenv("FR_REPO_ROOT", str(tmp_path))
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 0, r.output
    assert "nothing to check" in r.output


def test_a_bad_config_exits_2(repo: Path) -> None:
    (repo / ".fr" / "docs.yaml").write_text("pages: [a]\nbogus: 1\n")
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 2, r.output
    assert ".fr/docs.yaml" in r.output


def test_a_stale_page_exits_1_with_both_fixes(repo: Path) -> None:
    (repo / "src" / "x.py").write_text("x = 2\n")
    commit(repo)
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 1, r.output
    assert "docs/a.md" in r.output and "src/x.py" in r.output
    assert "edit the page" in r.output and "reviewed" in r.output


def test_touching_the_page_passes(repo: Path) -> None:
    (repo / "src" / "x.py").write_text("x = 2\n")
    (repo / "docs" / "a.md").write_text(PAGE.replace("first", "second"))
    commit(repo)
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 0, r.output


def test_a_rename_counts_both_sides(repo: Path) -> None:
    git(repo, "mv", "src/x.py", "other.py")
    commit(repo)
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 1, r.output
    assert "src/x.py" in r.output


def test_a_rename_into_a_covered_path_counts_the_new_side(repo: Path) -> None:
    (repo / "other.txt").write_text("o\n")
    commit(repo)
    git(repo, "branch", "mid")
    git(repo, "mv", "other.txt", "src/new.py")
    commit(repo)
    r = runner.invoke(app, ["docs", "check", "--base", "mid"])
    assert r.exit_code == 1, r.output
    assert "src/new.py" in r.output


def test_a_deleted_covered_file_makes_its_page_stale(repo: Path) -> None:
    git(repo, "rm", "-q", "src/x.py")
    commit(repo)
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 1, r.output
    assert "src/x.py" in r.output


def test_a_config_that_selects_no_page_exits_2(repo: Path) -> None:
    (repo / ".fr" / "docs.yaml").write_text("pages:\n  - dcos/*.md\n")
    commit(repo)
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 2, r.output
    assert "selects no page" in r.output


def test_unpushed_commits_on_the_default_branch_are_structure_only(repo: Path) -> None:
    git(repo, "checkout", "-q", "main")
    (repo / "src" / "x.py").write_text("x = 2\n")
    commit(repo)
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 0, r.output
    assert "structure only" in r.output
    r = runner.invoke(app, ["docs", "check", "--base", "origin/main"])
    assert r.exit_code == 1, r.output


def test_base_is_honoured(repo: Path) -> None:
    (repo / "src" / "x.py").write_text("x = 2\n")
    commit(repo)
    git(repo, "branch", "mid")
    r = runner.invoke(app, ["docs", "check", "--base", "mid"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["docs", "check", "--base", "main"])
    assert r.exit_code == 1, r.output


def test_an_unresolvable_base_exits_2(repo: Path) -> None:
    r = runner.invoke(app, ["docs", "check", "--base", "no-such-ref"])
    assert r.exit_code == 2, r.output
    git(repo, "remote", "remove", "origin")
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 2, r.output


def test_on_the_default_branch_only_structure_is_checked(repo: Path) -> None:
    git(repo, "checkout", "-q", "main")
    (repo / "src" / "x.py").write_text("x = 2\n")
    commit(repo)
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 0, r.output
    (repo / "docs" / "a.md").write_text("# no front matter\n")
    commit(repo)
    r = runner.invoke(app, ["docs", "check"])
    assert r.exit_code == 1 and "front matter" in r.output


def test_status_lists_pages_and_json_matches(repo: Path) -> None:
    r = runner.invoke(app, ["docs", "status"])
    assert r.exit_code == 0, r.output
    assert "docs/a.md" in r.output and "src/*.py" in r.output and "2026-11-11 first" in r.output
    j = runner.invoke(app, ["docs", "status", "--json"])
    data = json.loads(j.output)
    assert data["pages"] == [
        {"path": "docs/a.md", "covers": ["src/*.py"], "reviewed": "2026-11-11 first"}
    ]
    assert data["errors"] == []


def test_the_commands_write_nothing(repo: Path) -> None:
    (repo / "src" / "x.py").write_text("x = 2\n")
    commit(repo)
    before = porcelain(repo)
    heads = git(repo, "for-each-ref")
    for args in (["docs", "check"], ["docs", "status"], ["docs", "status", "--json"]):
        runner.invoke(app, args)
    assert porcelain(repo) == before
    assert git(repo, "for-each-ref") == heads
