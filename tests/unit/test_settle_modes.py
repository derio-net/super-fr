"""`fr.settle.modes.effective_modes`: the repo setting, then one feature's override (spec
2026-11-23-pr-readiness-wait R6, Test Plan 6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, append_journal_entry
from fr.settle.model import SettleRefused
from fr.settle.modes import effective_modes

from tests.unit.settings_repo import land_on_main, make_repo

SPEC_REL = "docs/superpowers/specs/2026-11-23-x-design.md"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = make_repo(tmp_path)
    land_on_main(root, "git:\n  settle:\n    conflicts: report\n")
    return root


def _spec(root: Path, *lines: str) -> str:
    path = root / SPEC_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(lines)
    path.write_text(f"# X\n\n## Verification\n\n{body}\n\n## Test Plan\n\n1. y\n")
    return SPEC_REL


def _journal(root: Path, *entries: tuple[str, str, str, str]) -> Path:
    path = root / "docs" / "superpowers" / "journals" / "debug" / "2026-11-23-bug.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    for kind, eid, title, body in entries:
        append_journal_entry(
            path,
            "2026-11-23-bug",
            JournalEntry(
                kind=kind,  # type: ignore[arg-type]
                scope="debug",
                id=eid,
                created="2026-11-23T10:00:00+00:00",
                title=title,
                body=body,
            ),
        )
    return path


def test_the_repo_setting_applies_with_no_override(repo: Path) -> None:
    modes = effective_modes(repo)

    assert (modes.conflicts.mode, modes.conflicts.source) == ("report", "repo")
    assert (modes.ci.mode, modes.ci.source) == ("fix", "default")


def test_a_spec_settle_line_overrides_the_setting(repo: Path) -> None:
    spec = _spec(repo, "strategy: candidate", "settle.ci: report — the forge's CI is down")

    modes = effective_modes(repo, spec=spec)

    assert (modes.ci.mode, modes.ci.source, modes.ci.reason) == (
        "report",
        "spec",
        "the forge's CI is down",
    )
    assert (modes.conflicts.mode, modes.conflicts.source) == ("report", "repo")


def test_a_spec_with_no_settle_line_gets_the_setting(repo: Path) -> None:
    spec = _spec(repo, "strategy: candidate")

    modes = effective_modes(repo, spec=spec)

    assert modes.ci.source == "default"
    assert modes.conflicts.source == "repo"


def test_a_malformed_spec_settle_line_refuses_naming_it(repo: Path) -> None:
    spec = _spec(repo, "settle.ci: report")

    with pytest.raises(SettleRefused, match=r"line 5.*settle\.ci: report"):
        effective_modes(repo, spec=spec)


def test_with_no_spec_a_debug_journal_decision_overrides(repo: Path) -> None:
    journal = _journal(repo, ("decision", "settle-conflicts", "off", "the base is frozen"))

    modes = effective_modes(repo, debug_journal=journal)

    assert (modes.conflicts.mode, modes.conflicts.source, modes.conflicts.reason) == (
        "off",
        "journal",
        "the base is frozen",
    )
    assert modes.ci.source == "default"


def test_a_spec_takes_the_place_of_the_journal(repo: Path) -> None:
    spec = _spec(repo, "strategy: candidate")
    journal = _journal(repo, ("decision", "settle-ci", "off", "ignored"))

    modes = effective_modes(repo, spec=spec, debug_journal=journal)

    assert modes.ci.source == "default"


def test_other_journal_entries_change_nothing(repo: Path) -> None:
    journal = _journal(
        repo,
        ("decision", "something-else", "off", "x"),
        ("discovery", "settle-ci", "off", "not a decision"),
    )

    modes = effective_modes(repo, debug_journal=journal)

    assert modes.ci.source == "default"
    assert modes.conflicts.source == "repo"


@pytest.mark.parametrize(
    ("title", "body"),
    [("maybe", "a reason"), ("off", ""), ("off", "   ")],
)
def test_a_bad_journal_decision_refuses_naming_the_entry(
    repo: Path, title: str, body: str
) -> None:
    journal = _journal(repo, ("decision", "settle-ci", title, body))

    with pytest.raises(SettleRefused, match="settle-ci"):
        effective_modes(repo, debug_journal=journal)


def test_a_missing_journal_or_spec_gets_the_setting(repo: Path) -> None:
    modes = effective_modes(
        repo, spec="docs/superpowers/specs/nope.md", debug_journal=repo / "nope.md"
    )

    assert modes.ci.source == "default"
    assert modes.conflicts.source == "repo"
