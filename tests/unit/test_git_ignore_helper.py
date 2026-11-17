"""One `git check-ignore` helper (super-fr#1154, spec
`2026-11-17-batch-acceptance-edits` R8).

`fr.git.ignored_paths` answers "which of these paths does git ignore" and
`fr.git.is_ignored` "is this one path ignored". The four non-triage call sites use
them; each site's error behaviour is pinned here as it was before the switch.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr import git as frgit

SPACED = "ign dir/a b.txt"
NON_ASCII = "ign dir/é.txt"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("ign dir/\n*.log\n")
    (root / "ign dir").mkdir()
    for rel in (SPACED, NON_ASCII, "kept.txt", "x.log"):
        (root / rel).write_text("x\n")
    return root


def _no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*_a: object, **_k: object) -> object:
        raise frgit.GitUnavailableError("git is not installed or not on PATH")

    monkeypatch.setattr(frgit, "git_answer", missing)


# --- the helper ---------------------------------------------------------------


def test_ignored_paths_names_ignored_inputs_as_given(repo: Path) -> None:
    paths = [SPACED, NON_ASCII, "kept.txt", "x.log", str(repo / "x.log")]
    assert frgit.ignored_paths(repo, paths) == {SPACED, NON_ASCII, "x.log", str(repo / "x.log")}


def test_ignored_paths_is_empty_when_nothing_is_ignored(repo: Path) -> None:
    assert frgit.ignored_paths(repo, ["kept.txt"]) == set()
    assert frgit.ignored_paths(repo, []) == set()


def test_ignored_paths_is_empty_outside_a_repository(tmp_path: Path) -> None:
    (tmp_path / "x.log").write_text("x\n")
    assert frgit.ignored_paths(tmp_path, ["x.log"]) == set()


def test_ignored_paths_is_empty_when_git_is_missing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_git(monkeypatch)
    assert frgit.ignored_paths(repo, ["x.log"]) == set()


def test_is_ignored_answers_true_false_and_false_on_error(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert frgit.is_ignored(repo, SPACED) is True
    assert frgit.is_ignored(repo, "kept.txt") is False
    outside = tmp_path / "plain"
    outside.mkdir()
    assert frgit.is_ignored(outside, "x.log") is False
    _no_git(monkeypatch)
    assert frgit.is_ignored(repo, "x.log") is False


def test_only_fr_git_and_the_triage_seam_run_check_ignore() -> None:
    src = Path(frgit.__file__).parent
    hits = sorted(
        p.relative_to(src).as_posix()
        for p in src.rglob("*.py")
        if '"check-ignore"' in p.read_text(encoding="utf-8")
    )
    assert hits == ["git.py", "triage/gitseam.py"]


# --- each call site, its behaviour unchanged -----------------------------------


def test_committable_drops_ignored_paths_and_keeps_all_on_error(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands.acceptance_cmd import _committable

    assert _committable(repo, ["kept.txt", "x.log", SPACED]) == ["kept.txt"]
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _committable(plain, ["kept.txt", "x.log"]) == ["kept.txt", "x.log"]
    _no_git(monkeypatch)
    assert _committable(repo, ["kept.txt", "x.log"]) == ["kept.txt", "x.log"]


def test_commit_filter_drops_ignored_paths_and_keeps_all_on_error(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts.commit import _without_ignored

    paths = [repo / "kept.txt", repo / "x.log", repo / SPACED]
    assert _without_ignored(repo, paths) == (repo / "kept.txt",)
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _without_ignored(plain, [plain / "x.log"]) == (plain / "x.log",)
    _no_git(monkeypatch)
    assert _without_ignored(repo, paths) == tuple(paths)


def test_visual_git_ignored_probes_one_path(repo: Path, tmp_path: Path) -> None:
    from fr.run.visual import git_ignored

    assert git_ignored(repo)(repo / "x.log") is True
    assert git_ignored(repo)(repo / "kept.txt") is False
    plain = tmp_path / "plain"
    plain.mkdir()
    assert git_ignored(plain)(plain / "x.log") is False


def test_scaffold_commit_leaves_an_ignored_agent_out_and_warns_on_ignored_devcontainer(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.isolation.scaffold import _commit_profile

    (repo / ".gitignore").write_text(".devcontainer/\n")
    (repo / ".devcontainer" / "dev").mkdir(parents=True)
    (repo / ".devcontainer" / "dev" / "devcontainer.json").write_text("{}\n")
    _commit_profile(repo, "dev")
    assert "git-ignored" in capsys.readouterr().err


@pytest.mark.parametrize("ignored", [True, False], ids=["ignored-agent", "tracked-agent"])
def test_scaffold_commit_carries_an_agent_only_when_git_does_not_ignore_it(
    repo: Path, capsys: pytest.CaptureFixture[str], ignored: bool
) -> None:
    """l-tests-r1: an ignored agent file is left out (one ignored path would make
    `git add` refuse every path, so the profile would not commit); a tracked one is
    committed with the profile. Neither warns: `.devcontainer` is not ignored."""
    from fr.isolation.scaffold import _commit_profile

    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    agent = ".claude/agents/fr-phase-executor.md"
    (repo / ".gitignore").write_text(f"{agent}\n" if ignored else "")
    (repo / ".claude" / "agents").mkdir(parents=True)
    (repo / agent).write_text("agent\n")
    (repo / ".devcontainer" / "dev").mkdir(parents=True)
    (repo / ".devcontainer" / "dev" / "devcontainer.json").write_text("{}\n")
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text("profiles: {}\n")
    _commit_profile(repo, "dev")
    assert "git-ignored" not in capsys.readouterr().err
    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert ".devcontainer/dev/devcontainer.json" in committed
    assert (agent in committed) is not ignored
