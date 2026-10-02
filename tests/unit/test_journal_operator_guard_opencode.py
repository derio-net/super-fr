"""The out-of-scope operator guard on OpenCode (spec 2026-10-02-opencode-observe-2
§F, R9; review p3-r3): `--answered-by operator` on a fix of an out-of-scope
finding is checked against the `question` parts of the run session in the
committed run-tree fixture (`tests/unit/opencode_fixture.py`), moved in time
relative to the out-of-scope record — the same claim `verify_operator_claim`
checks against a Claude Code transcript."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from tests.unit import test_journal_cmd as jc
from tests.unit.opencode_fixture import opencode_env, shifted
from tests.unit.test_journal_cmd import _init_repo, _journal_file

# Referenced through the module so pytest does not collect the class twice.
_Guard = jc.TestOperatorGuard


def _out_of_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "repo").mkdir()
    root = _init_repo(tmp_path / "repo")
    _Guard()._out_of_scope(root, monkeypatch)
    return root


def _fix(env: dict[str, str | None], path: str):
    guard = _Guard()
    fix = guard._fix_by_resolve if path == "resolve" else guard._fix_by_add
    return fix(env, "--answered-by", "operator")  # type: ignore[arg-type]


@pytest.mark.parametrize("path", ["resolve", "add"])
def test_no_answered_round_since_the_out_of_scope_record_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    root = _out_of_scope(tmp_path, monkeypatch)
    # The run tree's answered rounds all sit long BEFORE the out-of-scope
    # record: they answered something else.
    db = shifted(tmp_path, _dt.datetime(2000, 1, 1, tzinfo=_dt.UTC))
    before = _journal_file(root, "S").read_text()

    res = _fix(opencode_env(db), path)

    assert res.exit_code == 2, res.output
    assert "no answered question" in " ".join(res.output.split())
    assert _journal_file(root, "S").read_text() == before


@pytest.mark.parametrize("path", ["resolve", "add"])
def test_an_answered_round_since_the_out_of_scope_record_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    root = _out_of_scope(tmp_path, monkeypatch)
    db = shifted(tmp_path, _dt.datetime(2099, 1, 1, tzinfo=_dt.UTC))

    res = _fix(opencode_env(db), path)

    assert res.exit_code == 0, res.output
    assert "advisory" not in res.output
    assert "answered_by=operator" in _journal_file(root, "S").read_text()
    assert _Guard()._check().exit_code == 0


def test_an_unreadable_store_says_why_without_claiming_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The advisory names what fr could not read (the `_why_unobservable`
    wording), never the parity row's scope_note — which describes the
    verification that just failed to happen."""
    from fr.harness import load_matrix

    root = _out_of_scope(tmp_path, monkeypatch)
    env = opencode_env(tmp_path / "no-such.db")

    res = _fix(env, "resolve")

    assert res.exit_code == 0, res.output
    flat = " ".join(res.output.split())
    assert "advisory" in flat
    assert "FR_OPENCODE_DB" in flat
    (row,) = [s for s in load_matrix().surfaces if s.id == "out-of-scope-operator-guard"]
    note = row.harnesses["opencode"].scope_note
    assert note and " ".join(note.split()) not in flat
    assert "answered_by=operator" in _journal_file(root, "S").read_text()


def test_no_exported_session_names_the_missing_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _out_of_scope(tmp_path, monkeypatch)

    res = _fix(opencode_env(tmp_path / "no-such.db", session=None), "resolve")

    assert res.exit_code == 0, res.output
    assert "FR_OPENCODE_SESSION_ID is unset" in " ".join(res.output.split())
