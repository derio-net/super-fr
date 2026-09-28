"""`fr spec requirements` — the walking skeleton (spec 2026-09-28
requirements-traceability §C, phase 1 task 1). Wires `fr.requirements.
check_requirements` / `parse_requirements` to a spec file, its spec journal,
and the acceptance matrix; `check_requirements` itself is the only
implementation of §C, exercised directly by `test_requirements.py`.

The spec journal is written with a real `input=true` discovery (spec §A),
so the CLI's journal-file plumbing is exercised end to end with no stand-in.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from typer.testing import CliRunner


def _write_spec_journal(repo_root: Path, slug: str) -> None:
    path = journal_path(repo_root, "spec", slug)
    now = datetime.now(UTC).isoformat()
    append_journal_entry(
        path,
        slug,
        JournalEntry(
            kind="decision",
            scope="spec",
            id="d1",
            created=now,
            title="chose approach a",
            body="because reasons",
        ),
    )
    append_journal_entry(
        path,
        slug,
        JournalEntry(
            kind="discovery",
            scope="spec",
            id="input-1",
            created=now,
            title="raw operator input",
            body="x",
            input=True,
        ),
    )


def _write_matrix(path: Path, *, origin: str) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "org": "acme",
                "repo": "widget",
                "rows": [
                    {
                        "id": "row-0",
                        "capability": "cap",
                        "acceptance": "text",
                        "origin": [origin],
                        "status": "not-implemented",
                    }
                ],
            }
        )
    )


def test_requirements_cmd_exits_0_on_a_sound_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    Path("spec.md").write_text(
        "# Spec\n\n## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        "| R1 | x | decision d1 |\n"
    )
    _write_spec_journal(tmp_path, "spec")
    _write_matrix(Path("matrix.yaml"), origin="widget:spec.md#R1")

    from fr.cli import app

    result = CliRunner().invoke(app, ["spec", "requirements", "spec.md", "--matrix", "matrix.yaml"])
    assert result.exit_code == 0, result.output
    assert "1 requirements" in result.output


def test_requirements_cmd_exits_2_on_an_unsound_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    # R1 is never cited by any matrix row origin.
    Path("spec.md").write_text(
        "# Spec\n\n## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        "| R1 | x | decision d1 |\n"
    )
    _write_spec_journal(tmp_path, "spec")
    _write_matrix(Path("matrix.yaml"), origin="widget:other.md#R9")

    from fr.cli import app

    result = CliRunner().invoke(app, ["spec", "requirements", "spec.md", "--matrix", "matrix.yaml"])
    assert result.exit_code == 2
    assert "not cited by any matrix row" in result.output


def test_requirements_cmd_reports_a_missing_input_entry_as_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#776: before the brainstorm resolve writes the input entry, the
    pre-check says it is pending and how it gets written — not an error."""
    monkeypatch.chdir(tmp_path)
    Path("spec.md").write_text(
        "# Spec\n\n## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | x | input "not yet in any journal" |\n'
    )
    _write_matrix(Path("matrix.yaml"), origin="widget:spec.md#R1")

    from fr.cli import app

    result = CliRunner().invoke(app, ["spec", "requirements", "spec.md", "--matrix", "matrix.yaml"])
    assert result.exit_code == 0, result.output
    assert "pending" in result.output
    assert "no input entry" not in result.output
    assert "does not match" not in result.output
    assert "1 requirements" in result.output
