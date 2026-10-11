"""Discharging owed actions and the Owed section's journal source (spec
2026-10-11-debt-engine §E Discharge, R23, R24)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.debt.engine import compute, journal_owed
from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    archived_journal_path,
    journal_path,
    open_owed_ids,
    owed_body,
    parse_journal,
    resolution_entry,
)
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient, FakeGhError
from tests.unit.test_debt_engine import NOW, FakeForge
from tests.unit.test_merge_evidence import _add_remote, _init

SLUG = "2026-10-11-widget"
OWN = "acme/widgets"
KEY = f"spec:{SLUG}#step4"

runner = CliRunner()


def _owed(eid: str = "test-plan-step-4", key: str = KEY, scope: str = "spec") -> JournalEntry:
    return JournalEntry(
        kind="owed",
        scope=scope,  # type: ignore[arg-type]
        id=eid,
        created="2026-10-11T10:00:00+00:00",
        title="Test Plan step 4 owed",
        body=owed_body(what="walk it", why="needs main", how="resolve it", key=key),
    )


def _filed(owed: JournalEntry, ref: str) -> JournalEntry:
    return resolution_entry(
        target=owed,
        scope=owed.scope,
        taken={owed.id},
        created="2026-10-11T11:00:00+00:00",
        state="open",
        body="filed",
        filed_as=ref,
    )


def _journal(root: Path, entries: list[JournalEntry], *, archived: bool = False) -> Path:
    path = (archived_journal_path if archived else journal_path)(root, "spec", SLUG)
    for e in entries:
        append_journal_entry(path, SLUG, e)
    return path


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "docs/acceptance").mkdir(parents=True)
    (tmp_path / "docs/acceptance/matrix.yaml").write_text(
        "schema_version: 5\norg: acme\nrepo: widgets\nrows: []\n"
    )
    return tmp_path


def _resolve(monkeypatch: pytest.MonkeyPatch, root: Path, gh: FakeGhClient, *extra: str):  # noqa: ANN202
    from fr.commands import journal_cmd

    monkeypatch.setattr(journal_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.chdir(root)
    return runner.invoke(
        app,
        [
            "journal",
            "resolve",
            "--scope",
            "spec",
            "--slug",
            SLUG,
            "--id",
            "test-plan-step-4",
            "--state",
            "fixed",
            "--note",
            "walked live: issue #9 renamed",
            *extra,
        ],
    )


def _calls(gh: FakeGhClient, name: str) -> list[dict]:
    return [kw for n, kw in gh.calls if n == name]


# --- R24: discharge -------------------------------------------------------


@pytest.mark.parametrize("archived", [False, True], ids=["live", "archived"])
def test_resolve_discharges_an_owed_entry_and_closes_its_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, archived: bool
) -> None:
    root = _repo(tmp_path)
    owed = _owed()
    path = _journal(root, [owed, _filed(owed, f"{OWN}#12")], archived=archived)
    gh = FakeGhClient()
    gh.add_issue(OWN, 12)
    res = _resolve(monkeypatch, root, gh)
    assert res.exit_code == 0, res.output
    assert open_owed_ids(parse_journal(path.read_text())) == []
    (comment,) = _calls(gh, "comment_issue")
    assert comment["repo"] == OWN and comment["number"] == 12
    assert "walked live: issue #9 renamed" in comment["body"]
    (close,) = _calls(gh, "edit_issue_state")
    assert close["number"] == 12 and close["state"] == "CLOSED"
    assert gh.issues[(OWN, 12)].state == "CLOSED"
    assert "close it yourself" not in res.output


def test_an_unreachable_forge_prints_the_close_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    owed = _owed()
    path = _journal(root, [owed, _filed(owed, f"{OWN}#12")])

    class Down(FakeGhClient):
        def comment_issue(self, repo: str, number: int, body: str) -> None:
            raise FakeGhError("network down")

    res = _resolve(monkeypatch, root, Down())
    assert res.exit_code == 0, res.output
    assert open_owed_ids(parse_journal(path.read_text())) == [], "the discharge is recorded"
    assert "close it yourself" in res.output
    assert "12" in res.output and "close" in res.output


def test_tracking_none_prints_the_close_command_and_asks_no_forge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    (root / ".devcontainer").mkdir()
    (root / ".devcontainer/fr-profiles.yaml").write_text(
        "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\ntracking: {type: none}\n"
    )
    owed = _owed()
    _journal(root, [owed, _filed(owed, f"{OWN}#12")])
    gh = FakeGhClient()
    res = _resolve(monkeypatch, root, gh)
    assert res.exit_code == 0, res.output
    assert gh.calls == []
    assert "close it yourself" in res.output


def test_an_unfiled_owed_entry_discharges_without_the_forge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    path = _journal(root, [_owed()])
    gh = FakeGhClient()
    res = _resolve(monkeypatch, root, gh)
    assert res.exit_code == 0, res.output
    assert gh.calls == []
    assert open_owed_ids(parse_journal(path.read_text())) == []


def test_an_owed_entry_resolves_only_to_fixed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import journal_cmd

    root = _repo(tmp_path)
    _journal(root, [_owed()])
    monkeypatch.setattr(journal_cmd, "_make_gh_client", lambda: FakeGhClient())
    monkeypatch.chdir(root)
    res = runner.invoke(
        app,
        [
            "journal",
            "resolve",
            "--scope",
            "spec",
            "--slug",
            SLUG,
            "--id",
            "test-plan-step-4",
            "--state",
            "refuted",
            "--note",
            "n",
        ],
    )
    assert res.exit_code == 2, res.output


# --- R23: the Owed section's journal source -------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    r = _init(tmp_path / "r")
    _add_remote(r, tmp_path / "o.git")
    return r


def test_debt_lists_open_owed_entries_from_live_and_archived_journals_once(
    git_repo: Path,
) -> None:
    live = _owed()
    archived_key = "plan:2026-09-01-old#p3"
    _journal(git_repo, [live, _filed(live, f"{OWN}#12")])
    old = archived_journal_path(git_repo, "plan", "2026-09-01-old")
    append_journal_entry(old, "2026-09-01-old", _owed("manual-phase-3", archived_key, "plan"))
    issues = [
        {"ref": f"{OWN}#12", "title": "Owed: x", "body": f"x\n<!-- fr-owed:{KEY} -->"},
    ]
    report = compute(git_repo, forge=FakeForge(issues=issues), now=NOW, stale_days=14)
    owed = {o.key: o for o in report.owed}
    assert set(owed) == {KEY, archived_key}
    assert owed[KEY].source == "journal"
    assert owed[KEY].ref == f"{OWN}#12"
    assert owed[archived_key].source == "journal"
    assert report.owed_counted() == 2


def test_a_discharged_owed_entry_drops_out_even_while_its_issue_is_open(
    git_repo: Path,
) -> None:
    owed = _owed()
    filed = _filed(owed, f"{OWN}#12")
    fixed = resolution_entry(
        target=owed,
        scope="spec",
        taken={owed.id, filed.id},
        created="2026-10-11T12:00:00+00:00",
        state="fixed",
        body="walked",
    )
    _journal(git_repo, [owed, filed, fixed])
    issues = [{"ref": f"{OWN}#12", "title": "Owed: x", "body": f"<!-- fr-owed:{KEY} -->"}]
    report = compute(git_repo, forge=FakeForge(issues=issues), now=NOW, stale_days=14)
    assert [o.key for o in report.owed] == []


def test_journal_owed_reads_an_unparseable_journal_as_nothing(tmp_path: Path) -> None:
    path = journal_path(tmp_path, "spec", "bad")
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal kind=owed scope=spec id=x created=c state=open -->\n")
    items, discharged, unreadable = journal_owed(tmp_path)
    assert items == [] and discharged == set()
    assert unreadable == ["docs/superpowers/journals/specs/bad.md"]
