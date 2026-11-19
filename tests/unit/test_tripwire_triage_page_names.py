"""Tripwire: a triage page's file name is written in one place, the registry
(spec 2026-11-18-triage-pages-ux R1, §A).

Every module under `fr/triage/` and every `fr/commands/triage_*cmd.py` is read as text,
docstrings and help strings included, and must not name a page file, old or new, outside
`fr.triage.components`. A docstring or help line names a page by its command or its
title instead, so a rename is one registry edit and nothing else goes stale.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "packages" / "fr" / "src" / "fr"

NAMES = (
    "triage.html",
    "board.html",
    "backlog.html",
    "issues.html",
    "batches.html",
    "origins.html",
    "architecture.html",
    "history.html",
)


def _modules() -> list[Path]:
    triage = [p for p in sorted((SRC / "triage").glob("*.py")) if p.name != "components.py"]
    commands = sorted((SRC / "commands").glob("triage_*cmd.py"))
    return [*triage, *commands]


def test_the_scan_covers_the_page_modules() -> None:
    names = {p.name for p in _modules()}
    assert {"render.py", "history.py", "triage_cmd.py", "triage_kanban_cmd.py"} <= names
    assert "components.py" not in names


def test_the_registry_names_every_scanned_file_name() -> None:
    from fr.triage.components import PAGES

    named = {p.file for p in PAGES} | {
        p.legacy.file for p in PAGES if p.legacy is not None and p.legacy.file is not None
    }
    assert named == set(NAMES)


def test_no_module_names_a_page_file_outside_the_registry() -> None:
    hits = [
        f"{path.relative_to(ROOT)}:{n}: {name}"
        for path in _modules()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for name in NAMES
        if name in line
    ]
    assert not hits, "name the page by its command or title; read the file from PAGES:\n" + (
        "\n".join(hits)
    )
