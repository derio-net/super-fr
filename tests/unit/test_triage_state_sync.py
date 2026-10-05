"""`fr triage state export|import` (spec 2026-10-05-triage-pages-goal, R12, §H).

The durable state travels between the triage state directory and a repo-side copy;
facts files and rendered pages never do. Import never overwrites a newer state file
unless forced, and both verbs say what they copied and what they skipped.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.cli import app
from fr.triage.state_sync import (
    DURABLE_DIRS,
    DURABLE_FILES,
    SyncReport,
    export_state,
    import_state,
)
from typer.testing import CliRunner

SCOPE = "example-org/widgets"
SCOPE_NAME = "example-org--widgets"


def _state(root: Path) -> Path:
    """A state directory holding every kind of file: durable and not."""
    files = {
        "judgements.yaml": "schema: 3\n",
        "origins.yaml": "schema: 2\n",
        "subsystems.yaml": "subsystems: []\n",
        "facts.json": "{}\n",
        "origins-facts.json": "{}\n",
        "triage.html": "<html></html>\n",
        "history.html": "<html></html>\n",
        "drive.lock": "123\n",
        "board/manifest.yaml": "sections: []\n",
        "board/note.html": "<p>note</p>\n",
        "origins/manifest.yaml": "sections: []\n",
        "architecture/manifest.yaml": "sections: []\n",
        "architecture/hurts.html": "<p>hurts</p>\n",
        "history/manifest.yaml": "sections: []\n",
        "snapshots/2026-10-01T00-00-00Z.json": "{}\n",
        "authored-src/build.py": "print('x')\n",
        "authored-src/__pycache__/build.cpython-313.pyc": "bytes\n",
        "merge/feat/x/a.txt": "scratch\n",
        "export/3/a.txt": "scratch\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


DURABLE = sorted(
    [
        "judgements.yaml",
        "origins.yaml",
        "subsystems.yaml",
        "board/manifest.yaml",
        "board/note.html",
        "origins/manifest.yaml",
        "architecture/manifest.yaml",
        "architecture/hurts.html",
        "history/manifest.yaml",
        "snapshots/2026-10-01T00-00-00Z.json",
        "authored-src/build.py",
    ]
)


def _files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_the_durable_set_is_the_specs() -> None:
    assert DURABLE_FILES == ("judgements.yaml", "origins.yaml", "subsystems.yaml")
    assert DURABLE_DIRS == (
        "board",
        "origins",
        "architecture",
        "history",
        "snapshots",
        "authored-src",
    )


def test_export_copies_the_durable_state_and_nothing_else(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    dest = tmp_path / "repo" / "docs" / "triage" / SCOPE_NAME

    report = export_state(state, dest)

    assert _files(dest) == DURABLE
    assert sorted(report.copied) == DURABLE
    assert report.skipped == ()
    # mtimes travel (`shutil.copy2`), so a later import compares like with like
    src = state / "judgements.yaml"
    assert os.stat(dest / "judgements.yaml").st_mtime == pytest.approx(src.stat().st_mtime)


def test_export_overwrites_and_never_deletes_a_destination_file(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    dest = tmp_path / "dest"
    (dest / "board").mkdir(parents=True)
    (dest / "board" / "manifest.yaml").write_text("old\n", encoding="utf-8")
    (dest / "board" / "gone.html").write_text("kept\n", encoding="utf-8")

    export_state(state, dest)

    assert (dest / "board" / "manifest.yaml").read_text(encoding="utf-8") == "sections: []\n"
    assert (dest / "board" / "gone.html").read_text(encoding="utf-8") == "kept\n"


def test_import_copies_the_durable_state_back(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), src)
    (src / "facts.json").write_text("{}\n", encoding="utf-8")  # never travels back either
    state = tmp_path / "state"

    report = import_state(src, state, force=False)

    assert _files(state) == DURABLE
    assert sorted(report.copied) == DURABLE
    assert report.skipped == ()


def _age(path: Path, seconds: int) -> None:
    st = path.stat()
    os.utime(path, (st.st_atime - seconds, st.st_mtime - seconds))


def test_import_skips_a_state_file_newer_than_the_repo_copy(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), src)
    state = tmp_path / "state"
    import_state(src, state, force=False)
    (state / "judgements.yaml").write_text("schema: 3\n# edited here\n", encoding="utf-8")
    _age(src / "judgements.yaml", 60)

    report = import_state(src, state, force=False)

    assert report.skipped == ("judgements.yaml",)
    assert "judgements.yaml" not in report.copied
    assert "edited here" in (state / "judgements.yaml").read_text(encoding="utf-8")


def test_import_force_overwrites_a_newer_state_file(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), src)
    state = tmp_path / "state"
    import_state(src, state, force=False)
    (state / "judgements.yaml").write_text("schema: 3\n# edited here\n", encoding="utf-8")
    _age(src / "judgements.yaml", 60)

    report = import_state(src, state, force=True)

    assert report.skipped == ()
    assert "judgements.yaml" in report.copied
    assert (state / "judgements.yaml").read_text(encoding="utf-8") == "schema: 3\n"


def test_a_missing_source_copies_nothing(tmp_path: Path) -> None:
    report = import_state(tmp_path / "absent", tmp_path / "state", force=False)
    assert report == SyncReport(copied=(), skipped=())


def _invoke(*args: str) -> object:
    return CliRunner().invoke(app, ["triage", "state", *args], catch_exceptions=False)


def test_the_export_verb_prints_what_it_copied(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    out = tmp_path / "docs" / "triage"

    result = _invoke("export", "--to", str(out), "--repo", SCOPE, "--dir", str(state))

    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert _files(out / SCOPE_NAME) == DURABLE
    text = result.output  # type: ignore[attr-defined]
    for rel in DURABLE:
        assert f"copied {rel}" in text
    assert "facts.json" not in text


def test_the_import_verb_prints_copied_and_skipped(tmp_path: Path) -> None:
    out = tmp_path / "docs" / "triage"
    export_state(_state(tmp_path / "old"), out / SCOPE_NAME)
    state = tmp_path / "state"
    _invoke("import", "--from", str(out), "--repo", SCOPE, "--dir", str(state))
    (state / "origins.yaml").write_text("schema: 2\n# mine\n", encoding="utf-8")
    _age(out / SCOPE_NAME / "origins.yaml", 60)

    result = _invoke("import", "--from", str(out), "--repo", SCOPE, "--dir", str(state))

    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    text = result.output  # type: ignore[attr-defined]
    assert "skipped origins.yaml" in text
    assert "copied judgements.yaml" in text

    forced = _invoke("import", "--from", str(out), "--repo", SCOPE, "--dir", str(state), "--force")
    assert "copied origins.yaml" in forced.output  # type: ignore[attr-defined]
    assert "skipped origins.yaml" not in forced.output  # type: ignore[attr-defined]
