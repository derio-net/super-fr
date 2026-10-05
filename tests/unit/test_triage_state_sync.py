"""`fr triage state export|import` (spec 2026-10-05-triage-pages-goal, R12, §H).

The durable state travels between the triage state directory and a repo-side copy;
facts files and rendered pages never do. Import never overwrites a newer state file
unless forced, and both verbs say what they copied and what they skipped.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fr.cli import app
from fr.triage.errors import TriageError
from fr.triage.state_sync import (
    DURABLE_DIRS,
    DURABLE_FILES,
    SyncReport,
    contained,
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


def _at(root: Path) -> tuple[Path, str]:
    """A repo-side root as the (base, relative part) the engine takes."""
    return root.parent, root.name


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

    report = export_state(state, *_at(dest))

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

    export_state(state, *_at(dest))

    assert (dest / "board" / "manifest.yaml").read_text(encoding="utf-8") == "sections: []\n"
    assert (dest / "board" / "gone.html").read_text(encoding="utf-8") == "kept\n"


def test_import_copies_the_durable_state_back(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), *_at(src))
    (src / "facts.json").write_text("{}\n", encoding="utf-8")  # never travels back either
    state = tmp_path / "state"

    report = import_state(*_at(src), state, force=False)

    assert _files(state) == DURABLE
    assert sorted(report.copied) == DURABLE
    assert report.skipped == ()


def _age(path: Path, seconds: int) -> None:
    st = path.stat()
    os.utime(path, (st.st_atime - seconds, st.st_mtime - seconds))


def test_import_skips_a_state_file_newer_than_the_repo_copy(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), *_at(src))
    state = tmp_path / "state"
    import_state(*_at(src), state, force=False)
    (state / "judgements.yaml").write_text("schema: 3\n# edited here\n", encoding="utf-8")
    _age(src / "judgements.yaml", 60)

    report = import_state(*_at(src), state, force=False)

    assert [s.path for s in report.skipped] == ["judgements.yaml"]
    assert "newer" in report.skipped[0].reason
    assert "judgements.yaml" not in report.copied
    assert "edited here" in (state / "judgements.yaml").read_text(encoding="utf-8")


def test_import_force_overwrites_a_newer_state_file(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), *_at(src))
    state = tmp_path / "state"
    import_state(*_at(src), state, force=False)
    (state / "judgements.yaml").write_text("schema: 3\n# edited here\n", encoding="utf-8")
    _age(src / "judgements.yaml", 60)

    report = import_state(*_at(src), state, force=True)

    assert report.skipped == ()
    assert "judgements.yaml" in report.copied
    assert (state / "judgements.yaml").read_text(encoding="utf-8") == "schema: 3\n"


def test_a_missing_source_copies_nothing(tmp_path: Path) -> None:
    report = import_state(*_at(tmp_path / "absent"), tmp_path / "state", force=False)
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
    export_state(_state(tmp_path / "old"), *_at(out / SCOPE_NAME))
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


# ------------------------------------------------- symlinks (p4-sec-symlink-follow)
# A symlink is never followed, in either direction: export would copy whatever it
# points at into a repo the driver pushes, and import from a cloned repo would copy
# an arbitrary local file into the cache.


def _skipped(report: SyncReport) -> dict[str, str]:
    return {s.path: s.reason for s in report.skipped}


def test_export_never_follows_a_symlinked_file(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    secret = tmp_path / "id_rsa"
    secret.write_text("PRIVATE\n", encoding="utf-8")
    (state / "authored-src" / "x").symlink_to(secret)
    (state / "subsystems.yaml").unlink()
    (state / "subsystems.yaml").symlink_to(secret)
    dest = tmp_path / "dest"

    report = export_state(state, *_at(dest))

    assert not (dest / "authored-src" / "x").exists()
    assert not (dest / "subsystems.yaml").exists()
    assert "authored-src/x" not in report.copied
    skipped = _skipped(report)
    assert skipped["authored-src/x"] == "symlink, not followed"
    assert skipped["subsystems.yaml"] == "symlink, not followed"
    assert all("PRIVATE" not in p.read_text("utf-8") for p in dest.rglob("*") if p.is_file())


def test_export_never_follows_a_symlinked_durable_dir_or_subdir(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    outside = tmp_path / "home"
    (outside / "ssh").mkdir(parents=True)
    (outside / "ssh" / "key").write_text("PRIVATE\n", encoding="utf-8")
    shutil.rmtree(state / "history")
    (state / "history").symlink_to(outside / "ssh")
    (state / "board" / "deep").symlink_to(outside)

    report = export_state(state, *_at(tmp_path / "dest"))

    assert not (tmp_path / "dest" / "history").exists()
    assert not (tmp_path / "dest" / "board" / "deep").exists()
    skipped = _skipped(report)
    assert skipped["history"] == "symlink, not followed"
    assert skipped["board/deep"] == "symlink, not followed"


def test_import_never_follows_a_symlink_in_the_repo_copy(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), *_at(src))
    secret = tmp_path / "secret"
    secret.write_text("PRIVATE\n", encoding="utf-8")
    (src / "board" / "planted.html").symlink_to(secret)
    state = tmp_path / "state"

    report = import_state(*_at(src), state, force=True)

    assert not (state / "board" / "planted.html").exists()
    assert _skipped(report)["board/planted.html"] == "symlink, not followed"


def test_a_symlinked_destination_is_never_written_through(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    dest = tmp_path / "dest"
    victim = tmp_path / "victim"
    victim.write_text("ORIGINAL\n", encoding="utf-8")
    victim_dir = tmp_path / "victim-dir"
    victim_dir.mkdir()
    dest.mkdir()
    (dest / "judgements.yaml").symlink_to(victim)
    (dest / "board").symlink_to(victim_dir)

    report = export_state(state, *_at(dest))

    assert victim.read_text(encoding="utf-8") == "ORIGINAL\n"
    assert list(victim_dir.iterdir()) == []
    skipped = _skipped(report)
    assert "symlink" in skipped["judgements.yaml"]
    assert "symlink" in skipped["board/manifest.yaml"]
    assert "judgements.yaml" not in report.copied


# ------------------------------------------- roots (p4-sec-root-symlink-traversal)
# Only the parts fr appends to a base are trusted to nothing: a symlinked component or
# a `..` in them would read or write outside the base. The base itself is trusted as
# given (on macOS /var and /tmp are themselves symlinks).


@pytest.mark.parametrize("rel", ["../x", "a/../../x", "/abs", "", ".", "a/./b", "a//b"])
def test_contained_refuses_a_part_that_leaves_the_base(tmp_path: Path, rel: str) -> None:
    with pytest.raises(TriageError):
        contained(tmp_path, rel)


def test_contained_refuses_a_symlinked_component_the_last_one_included(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    base = tmp_path / "repo"
    (base / "docs").mkdir(parents=True)
    (base / "docs" / "triage").symlink_to(outside)
    with pytest.raises(TriageError, match="docs/triage"):
        contained(base, "docs/triage/scope")
    with pytest.raises(TriageError, match="docs/triage"):
        contained(base, "docs/triage")


def test_contained_trusts_a_base_reached_through_a_symlink(tmp_path: Path) -> None:
    real = tmp_path / "private" / "var"
    real.mkdir(parents=True)
    linked = tmp_path / "var"
    linked.symlink_to(real)
    base = linked / "repo"
    base.mkdir()
    assert base.resolve() != base

    assert contained(base, "docs/triage/scope") == base / "docs/triage/scope"
    state = _state(tmp_path / "state")
    report = export_state(state, base, "docs/triage/scope")
    assert sorted(report.copied) == DURABLE
    assert _files(real / "repo" / "docs/triage/scope") == DURABLE


def test_import_refuses_a_symlinked_repo_side_scope_dir_and_reads_nothing(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    export_state(_state(tmp_path / "old"), *_at(elsewhere))
    repo = tmp_path / "docs" / "triage"
    repo.mkdir(parents=True)
    (repo / SCOPE_NAME).symlink_to(elsewhere)
    state = tmp_path / "state"

    with pytest.raises(TriageError, match=SCOPE_NAME):
        import_state(repo, SCOPE_NAME, state, force=True)
    assert not state.exists()

    result = CliRunner().invoke(
        app,
        ["triage", "state", "import", "--from", str(repo), "--repo", SCOPE, "--dir", str(state)],
    )
    assert result.exit_code == 2
    assert not state.exists()


def test_export_refuses_a_symlinked_repo_side_root_and_writes_nothing(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").symlink_to(outside)

    with pytest.raises(TriageError):
        export_state(_state(tmp_path / "state"), repo, f"docs/triage/{SCOPE_NAME}")
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("name", ["..", ".", "", "a/b", "a\\b"])
def test_a_scope_name_must_be_one_plain_part(name: str) -> None:
    from fr.triage.state_sync import check_scope_name

    with pytest.raises(TriageError, match="scope"):
        check_scope_name(name)
    assert check_scope_name(SCOPE_NAME) == SCOPE_NAME
