"""R19: `_Driver._fetched_reader` fetches each repo at most once per pass, a failed fetch
included: the failure is recorded and every later read of that repo in the pass raises the
same `GitError` again, so each caller's own handler decides."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.commands import triage_batch_cmd
from fr.triage.errors import TriageError
from fr.triage.gitseam import GitError

REPO = "derio-net/super-fr"


class _Clone:
    def __init__(self, fail: bool) -> None:
        self.fail = fail
        self.fetches = 0

    def fetch(self) -> None:
        self.fetches += 1
        if self.fail:
            raise GitError("could not read from remote repository")


def _driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clone: _Clone
) -> triage_batch_cmd._Driver:
    driver = triage_batch_cmd._Driver(
        triage_batch_cmd._scope(REPO, None), tmp_path, named=None, checkouts={}, max_inflight=4,
        yes=True,
    )  # fmt: skip
    monkeypatch.setattr(driver, "_reader", lambda repo: clone)
    return driver


def test_a_failed_fetch_is_made_once_and_every_read_raises_the_same_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = _Clone(fail=True)
    driver = _driver(tmp_path, monkeypatch, clone)
    with pytest.raises(GitError) as first:
        driver._fetched_reader(REPO)
    with pytest.raises(GitError) as second:
        driver._fetched_reader(REPO)
    assert second.value is first.value and clone.fetches == 1
    assert isinstance(first.value, TriageError)  # `_ci_none` still degrades to False on it


def test_a_new_pass_fetches_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clone = _Clone(fail=True)
    driver = _driver(tmp_path, monkeypatch, clone)
    with pytest.raises(GitError):
        driver._fetched_reader(REPO)
    driver._forget_fetches()  # what `run_pass` does first
    clone.fail = False
    assert driver._fetched_reader(REPO) is clone
    assert driver._fetched_reader(REPO) is clone
    assert clone.fetches == 2  # one per pass, success included


def test_a_successful_fetch_is_still_made_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = _Clone(fail=False)
    driver = _driver(tmp_path, monkeypatch, clone)
    driver._fetched_reader(REPO)
    driver._fetched_reader(REPO)
    assert clone.fetches == 1
