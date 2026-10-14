"""`fr journal file` (spec 2026-10-14 exit-gates R10): file a leftover at
`deliver` through the archive's own filers, and record where it went.

Every test uses a fake forge; nothing reaches a real tracker.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    effective_finding_states,
    journal_path,
    owed_body,
    owed_filed_as,
    parse_journal,
)
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

runner = CliRunner()
SLUG = "2026-10-14-widget"
OWN = "acme/widgets"


class ListingGh(FakeGhClient):
    def viewer_login(self) -> str:
        return "me"

    def list_issues(self, repo, state, limit, fields=None):  # noqa: ANN001, ANN201
        return []


def _entries() -> list[JournalEntry]:
    stamp = "2026-10-14T00:00:00+00:00"
    return [
        JournalEntry(
            kind="finding", scope="spec", id="f1", created=stamp, title="pre-existing bug",
            state="open", body="It was broken before.",
        ),
        JournalEntry(
            kind="finding", scope="spec", id="f1-resolved", created=stamp, title="resolves f1",
            state="open", resolves="f1", out_of_scope=True,
        ),
        JournalEntry(
            kind="owed", scope="spec", id="o1", created=stamp, title="walk it live",
            body=owed_body(what="walk it", why="needs main", how="fr journal resolve …",
                           key=f"spec:{SLUG}#step1"),
        ),
        JournalEntry(
            kind="decision", scope="spec", id="d1", created=stamp, title="ships half of #4",
            narrows=("#4",), gate="owner",
        ),
        JournalEntry(kind="discovery", scope="spec", id="x1", created=stamp, title="a note"),
        JournalEntry(
            kind="finding", scope="spec", id="f2", created=stamp, title="fixed", state="fixed",
        ),
        JournalEntry(
            kind="finding", scope="spec", id="f3", created=stamp, title="this change's bug",
            state="open", review_scope="in",
        ),
    ]  # fmt: skip


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gh: FakeGhClient) -> Path:
    root = tmp_path / "repo"
    root.mkdir()

    def git(*a: str) -> None:
        subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    git("remote", "add", "origin", f"https://github.com/{OWN}.git")
    path = journal_path(root, "spec", SLUG)
    for e in _entries():
        append_journal_entry(path, SLUG, e)
    git("add", "-A")
    git("commit", "-qm", "seed")
    git("checkout", "-qb", "feat/widget")  # fr never commits on the default branch
    from fr.commands import journal_cmd

    monkeypatch.setattr(journal_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.chdir(root)
    return root


def _file(*ids: str):
    argv = ["journal", "file", "--scope", "spec", "--slug", SLUG]
    for i in ids:
        argv += ["--id", i]
    return runner.invoke(app, argv)


def _journal(root: Path) -> list[JournalEntry]:
    return parse_journal(journal_path(root, "spec", SLUG).read_text())


def _created(gh: FakeGhClient) -> list[dict]:
    return [kw for name, kw in gh.calls if name == "create_issue"]


def test_an_out_of_scope_finding_is_filed_with_follow_up_and_deferred(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = ListingGh()
    root = _repo(tmp_path, monkeypatch, gh)
    res = _file("f1")
    assert res.exit_code == 0, res.output
    (created,) = _created(gh)
    assert created["labels"] == frozenset({"follow-up"})
    assert created["title"] == "pre-existing bug"
    entries = _journal(root)
    assert effective_finding_states(entries)["f1"] == "deferred"
    record = entries[-1]
    assert record.resolves == "f1" and record.tracked_by == f"https://github.com/{OWN}/issues/1"


def test_an_owed_entry_is_filed_with_fr_owed_and_records_filed_as(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = ListingGh()
    root = _repo(tmp_path, monkeypatch, gh)
    res = _file("o1")
    assert res.exit_code == 0, res.output
    (created,) = _created(gh)
    assert created["labels"] == frozenset({"fr:owed"})
    assert owed_filed_as(_journal(root)) == {"o1": f"{OWN}#1"}


def test_a_narrowing_decision_is_filed_and_records_tracked_by(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.journal.file import narrowing_accounted

    gh = ListingGh()
    root = _repo(tmp_path, monkeypatch, gh)
    res = _file("d1")
    assert res.exit_code == 0, res.output
    (created,) = _created(gh)
    assert created["labels"] == frozenset({"follow-up"})
    entries = _journal(root)
    decision = next(e for e in entries if e.id == "d1")
    assert narrowing_accounted(entries, decision) == f"https://github.com/{OWN}/issues/1"
    filed = entries[-1]
    assert filed.kind == "decision" and filed.narrows == ("#4",) and filed.decided_by is None
    assert filed.remainder_tracked_by == f"https://github.com/{OWN}/issues/1"
    assert filed.tracked_by is None  # never the released fr's resolution-only token


def test_all_three_in_one_call_commit_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gh = ListingGh()
    root = _repo(tmp_path, monkeypatch, gh)
    res = _file("f1", "o1", "d1")
    assert res.exit_code == 0, res.output
    assert len(_created(gh)) == 3
    log = subprocess.run(
        ["git", "-C", str(root), "log", "--oneline"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert len(log) == 2  # seed + one filing commit


@pytest.mark.parametrize(
    ("ids", "why"),
    [
        (["nope"], "no entry"),
        (["x1"], "only a finding"),
        (["f2"], "nothing to file"),
        (["f1", "nope"], "no entry"),
        # review p3-r6: an in-scope open finding is fixed, never filed
        (["f3"], "fix it, or record it out of scope"),
    ],
)
def test_an_unfileable_id_is_refused_and_nothing_is_filed_or_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ids: list[str], why: str
) -> None:
    gh = ListingGh()
    root = _repo(tmp_path, monkeypatch, gh)
    before = journal_path(root, "spec", SLUG).read_text()
    res = _file(*ids)
    assert res.exit_code == 2, res.output
    assert why in res.output
    assert _created(gh) == []
    assert journal_path(root, "spec", SLUG).read_text() == before


def test_tracking_none_refuses_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = ListingGh()
    root = _repo(tmp_path, monkeypatch, gh)
    prof = root / ".devcontainer"
    prof.mkdir()
    (prof / "fr-profiles.yaml").write_text(
        "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\ntracking: {type: none}\n"
    )
    before = journal_path(root, "spec", SLUG).read_text()
    res = _file("f1")
    assert res.exit_code == 2, res.output
    assert "tracking" in res.output and "none" in res.output
    assert _created(gh) == []
    assert journal_path(root, "spec", SLUG).read_text() == before


def test_a_filed_item_is_not_filed_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gh = ListingGh()
    _repo(tmp_path, monkeypatch, gh)
    assert _file("o1", "d1").exit_code == 0
    again = _file("o1")
    assert again.exit_code == 2 and "already filed" in again.output
    again = _file("d1")
    assert again.exit_code == 2 and "already filed" in again.output
