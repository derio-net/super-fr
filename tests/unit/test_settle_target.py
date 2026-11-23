"""`fr.settle.target.committed_at`: the PR head's commit time, and what is said when it
cannot be read (review l-errors-r7, l-tests-r2)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fr.settle.target import HeadTime, committed_at

from tests.unit.settings_repo import git, make_repo

PAST = 1_700_000_000  # 2023-11-14


def _old_commit(repo: Path) -> str:
    (repo / "old.txt").write_text("old\n")
    git(repo, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": f"{PAST} +0000", "GIT_AUTHOR_DATE": f"{PAST} +0000"}
    subprocess.run(["git", "commit", "-qm", "old"], cwd=repo, env=env, check=True)
    return git(repo, "rev-parse", "HEAD").strip()


def test_a_local_head_reads_its_committer_date(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    sha = _old_commit(repo)

    assert committed_at(repo, sha) == HeadTime(float(PAST))


def test_an_unknown_sha_is_estimated_from_local_head(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _old_commit(repo)

    got = committed_at(repo, "f" * 40)

    assert got == HeadTime(float(PAST), estimated=True)


def test_nothing_readable_is_unknown_never_now(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "bare-dir"
    not_a_repo.mkdir()

    assert committed_at(not_a_repo, "f" * 40) == HeadTime(None)


def test_a_malformed_head_sha_reaches_no_git_call_and_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review sec-r1: a forge-supplied head never reaches git as an option."""
    import fr.settle.target as target

    repo = make_repo(tmp_path)
    calls: list[list[str]] = []
    real = subprocess.run

    def spy(argv: list[str], *a: object, **kw: object) -> object:
        calls.append(list(argv))
        return real(argv, *a, **kw)  # type: ignore[call-overload]

    monkeypatch.setattr(target.subprocess, "run", spy)
    for bad in ("--upload-pack=x", "abc", "F" * 40, "a" * 39, "a" * 40 + "\n"):
        assert committed_at(repo, bad) == HeadTime(None), bad
    assert calls == []


def test_every_git_call_ends_options_before_the_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.settle.target as target

    repo = make_repo(tmp_path)
    calls: list[list[str]] = []
    real = subprocess.run

    def spy(argv: list[str], *a: object, **kw: object) -> object:
        calls.append(list(argv))
        return real(argv, *a, **kw)  # type: ignore[call-overload]

    monkeypatch.setattr(target.subprocess, "run", spy)
    committed_at(repo, "f" * 40)

    assert {c[1] for c in calls} == {"log", "fetch"}
    for argv in calls:
        assert argv.index("--end-of-options") < len(argv) - 1
