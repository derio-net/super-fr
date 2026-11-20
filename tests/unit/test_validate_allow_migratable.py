"""`fr validate artifacts --allow-migratable` (spec 2026-11-19-wave-merge-queue R21).

A stale stamp that a registered migration moves passes and is listed as `stale, migratable`.
It still fails one whose migration refuses it, one no migration reaches, and one newer than
this `fr`. The migrations are tried on a scratch copy: the checkout is never written.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts.validate import validate_repo
from fr.cli import app
from typer.testing import CliRunner

runner_cli = CliRunner()

BODY = (
    "# Journal: p\n\n"
    "<!-- fr:journal kind=discovery scope=plan id=d1 created=2026-01-01T00:00:00 -->\n"
    "### d1 · discovery · t\n\nbody\n"
)
LENS_ENTRY = (
    "<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-01-01T00:00:00 "
    "lens=security step=implement-phase -->\n### lens-security-1 · lens · why\n"
)


def _journal(root: Path, text: str, name: str = "p") -> Path:
    path = root / "docs/superpowers/journals/plans" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _only_journals(root: Path, **kw: bool):
    return validate_repo(root, kind_name="journal", **kw)


def test_without_the_flag_a_stale_stamp_fails_as_before(tmp_path: Path) -> None:
    _journal(tmp_path, "<!-- fr:journal-schema=3 -->\n" + BODY)
    report = _only_journals(tmp_path)
    assert not report.ok and "stale" in report.issues[0].message and not report.migratable


def test_a_stale_stamp_a_migration_moves_passes_and_prints_stale_migratable(
    tmp_path: Path,
) -> None:
    path = _journal(tmp_path, "<!-- fr:journal-schema=3 -->\n" + BODY)
    before = path.read_bytes()
    report = _only_journals(tmp_path, allow_migratable=True)
    assert report.ok and report.checked == 1
    (note,) = report.migratable
    assert note.message.startswith("stale, migratable") and note.path == path
    assert path.read_bytes() == before, "the checkout is never written: a scratch copy is tried"


def test_a_migration_that_refuses_the_file_still_fails(tmp_path: Path) -> None:
    path = _journal(tmp_path, "<!-- fr:journal-schema=3 -->\n# Journal: p\n\n" + LENS_ENTRY)
    before = path.read_bytes()
    report = _only_journals(tmp_path, allow_migratable=True)
    assert not report.ok and "refuses" in report.issues[0].message
    assert path.read_bytes() == before


def test_a_stamp_no_migration_reaches_still_fails(tmp_path: Path) -> None:
    from fr.artifacts.registry import ARTIFACT_KINDS

    stale = ARTIFACT_KINDS["plan"].current_version - 1
    plan = tmp_path / "docs/superpowers/plans/p/_meta.yaml"
    plan.parent.mkdir(parents=True)
    plan.write_text(f"schema_version: {stale}\nplan: p\ntarget_repo: o/r\n")
    report = validate_repo(tmp_path, kind_name="plan", allow_migratable=True)
    assert not report.ok and "no registered migration reaches" in report.issues[0].message


def test_a_stamp_newer_than_this_fr_still_fails(tmp_path: Path) -> None:
    _journal(tmp_path, "<!-- fr:journal-schema=99 -->\n" + BODY)
    report = _only_journals(tmp_path, allow_migratable=True)
    assert not report.ok and "upgrade fr" in report.issues[0].message


def test_one_refused_file_does_not_hide_a_migratable_one(tmp_path: Path) -> None:
    _journal(tmp_path, "<!-- fr:journal-schema=3 -->\n" + BODY, "good")
    _journal(tmp_path, "<!-- fr:journal-schema=3 -->\n# Journal: p\n\n" + LENS_ENTRY, "bad")
    report = _only_journals(tmp_path, allow_migratable=True)
    assert [i.path.name for i in report.issues] == ["bad.md"]
    assert [i.path.name for i in report.migratable] == ["good.md"]


def test_the_cli_flag_exits_zero_and_names_stale_migratable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _journal(tmp_path, "<!-- fr:journal-schema=3 -->\n" + BODY)
    monkeypatch.setenv("FR_REPO_ROOT", str(tmp_path))
    failing = runner_cli.invoke(app, ["validate", "artifacts", "--kind", "journal"])
    assert failing.exit_code == 1
    ok = runner_cli.invoke(app, ["validate", "artifacts", "--kind", "journal",
                                 "--allow-migratable"])  # fmt: skip
    assert ok.exit_code == 0, ok.output
    assert "stale, migratable" in ok.output
