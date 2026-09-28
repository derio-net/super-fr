"""`fr spec requirements` — the walking skeleton (spec 2026-09-28
requirements-traceability §C, phase 1 task 1). Wires `fr.requirements.
check_requirements` / `parse_requirements` to a spec file, its spec journal,
and the acceptance matrix; `check_requirements` itself is the only
implementation of §C, exercised directly by `test_requirements.py`.

`fr.requirements.is_input_entry` reads the `input` attribute via `getattr` —
phase 2 adds the real `JournalEntry.input` field (spec §A). Until then a real
`parse_journal`-produced entry never carries it, so this test writes a
`kind=discovery` entry whose id starts `input-` (the pre-token convention)
and monkeypatches `spec_cmd.parse_journal` to wrap any such entry in a small
stand-in exposing `.input = True` — the same idiom `test_requirements.py`'s
`_input_entry` helper uses for its pure-function tests, applied here so the
CLI's real journal-file plumbing can be exercised end to end today. This is a
test-local bridge, not a second implementation: `fr.requirements.
check_requirements` and `is_input_entry` are untouched, and phase 2 removes
the bridge once the real field lands (P2.T1.S2 switches the pure-test helper
to it; this CLI test's bridge goes with it).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fr.commands import spec_cmd
from fr.journal.model import JournalEntry, append_journal_entry, journal_path
from typer.testing import CliRunner


def _wrap_pretoken_input(real_parse_journal):
    def wrapped(text: str):
        entries = real_parse_journal(text)
        return [
            SimpleNamespace(kind=e.kind, id=e.id, body=e.body, input=True)
            if e.kind == "discovery" and e.id.startswith("input-")
            else e
            for e in entries
        ]

    return wrapped


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
    monkeypatch.setattr(spec_cmd, "parse_journal", _wrap_pretoken_input(spec_cmd.parse_journal))

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
    monkeypatch.setattr(spec_cmd, "parse_journal", _wrap_pretoken_input(spec_cmd.parse_journal))

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
