"""`fr triage state export|import` (spec 2026-10-05-triage-pages-goal, R12, §H).

The durable state travels between the triage state directory and a repo-side copy;
facts files and rendered pages never do. Import never overwrites a newer state file
unless forced, and both verbs say what they copied and what they skipped.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from fr.cli import app
from fr.triage.errors import TriageError
from fr.triage.state_sync import (
    DURABLE_DIRS,
    DURABLE_FILES,
    OWNER_FILE,
    RECORD_FILE,
    SYMLINK,
    SYMLINK_DEST,
    BadRecord,
    Drift,
    ExportDrift,
    SyncReport,
    contained,
    export_state,
    import_state,
    read_record,
)
from typer.testing import CliRunner

SCOPE = "example-org/widgets"
SCOPE_NAME = "example-org--widgets"
HOST, CLOUD = "s-11111111", "s-22222222"  # two scope ids of one scope name (gh#1101)


def _state(root: Path) -> Path:
    """A state directory holding every kind of file: durable and not."""
    files = {
        "judgements.yaml": "schema: 3\n",
        "origins.yaml": "schema: 2\n",
        "subsystems.yaml": "subsystems: []\n",
        "facts.json": "{}\n",
        "origins-facts.json": "{}\n",
        "backlog.html": "<html></html>\n",
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
# a repo-side root also holds the scope id stamp and the record of what the export wrote
EXPORTED = sorted([*DURABLE, OWNER_FILE, RECORD_FILE])


def _at(root: Path) -> tuple[Path, str]:
    """A repo-side root as the (base, relative part) the engine takes."""
    return root.parent, root.name


def _files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_the_durable_set_is_the_specs() -> None:
    assert DURABLE_FILES == ("judgements.yaml", "origins.yaml", "subsystems.yaml")
    assert DURABLE_DIRS == (
        "board",
        "backlog",
        "issues",
        "origins",
        "architecture",
        "history",
        "snapshots",
        "authored-src",
    )


def test_export_copies_the_durable_state_and_nothing_else(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    dest = tmp_path / "repo" / "docs" / "triage" / SCOPE_NAME

    report = export_state(state, *_at(dest), owner=HOST)

    assert _files(dest) == EXPORTED
    assert sorted(report.copied) == EXPORTED
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

    export_state(state, *_at(dest), owner=HOST)

    assert (dest / "board" / "manifest.yaml").read_text(encoding="utf-8") == "sections: []\n"
    assert (dest / "board" / "gone.html").read_text(encoding="utf-8") == "kept\n"


def test_import_copies_the_durable_state_back(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), *_at(src), owner=HOST)
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
    export_state(_state(tmp_path / "old"), *_at(src), owner=HOST)
    state = tmp_path / "state"
    import_state(*_at(src), state, force=False)
    (state / "judgements.yaml").write_text("schema: 3\n# edited here\n", encoding="utf-8")
    _age(src / "judgements.yaml", 60)

    report = import_state(*_at(src), state, force=False)

    newer = [s for s in report.skipped if s.reason != "identical"]
    assert [s.path for s in newer] == ["judgements.yaml"] and "newer" in newer[0].reason
    assert "judgements.yaml" not in report.copied
    assert "edited here" in (state / "judgements.yaml").read_text(encoding="utf-8")


def test_import_force_overwrites_a_newer_state_file(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), *_at(src), owner=HOST)
    state = tmp_path / "state"
    import_state(*_at(src), state, force=False)
    (state / "judgements.yaml").write_text("schema: 3\n# edited here\n", encoding="utf-8")
    _age(src / "judgements.yaml", 60)

    report = import_state(*_at(src), state, force=True)

    assert [s for s in report.skipped if s.reason != "identical"] == []
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
    assert _files(out / SCOPE_NAME) == EXPORTED
    text = result.output  # type: ignore[attr-defined]
    for rel in DURABLE:
        assert f"copied {rel}" in text
    assert "facts.json" not in text


def test_the_import_verb_prints_copied_and_skipped(tmp_path: Path) -> None:
    out = tmp_path / "docs" / "triage"
    export_state(_state(tmp_path / "old"), *_at(out / SCOPE_NAME), owner=HOST)
    state = tmp_path / "state"
    _invoke("import", "--from", str(out), "--repo", SCOPE, "--dir", str(state))
    (state / "origins.yaml").write_text("schema: 2\n# mine\n", encoding="utf-8")
    _age(out / SCOPE_NAME / "origins.yaml", 60)

    result = _invoke("import", "--from", str(out), "--repo", SCOPE, "--dir", str(state))

    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    text = result.output  # type: ignore[attr-defined]
    assert "skipped origins.yaml" in text
    assert "skipped judgements.yaml (identical" in text  # p4-r5

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

    report = export_state(state, *_at(dest), owner=HOST)

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

    report = export_state(state, *_at(tmp_path / "dest"), owner=HOST)

    assert not (tmp_path / "dest" / "history").exists()
    assert not (tmp_path / "dest" / "board" / "deep").exists()
    skipped = _skipped(report)
    assert skipped["history"] == "symlink, not followed"
    assert skipped["board/deep"] == "symlink, not followed"


def test_import_never_follows_a_symlink_in_the_repo_copy(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), *_at(src), owner=HOST)
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

    report = export_state(state, *_at(dest), owner=HOST)

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
    report = export_state(state, base, "docs/triage/scope", owner=HOST)
    assert sorted(report.copied) == EXPORTED
    assert _files(real / "repo" / "docs/triage/scope") == EXPORTED


def test_import_refuses_a_symlinked_repo_side_scope_dir_and_reads_nothing(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    export_state(_state(tmp_path / "old"), *_at(elsewhere), owner=HOST)
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
        export_state(_state(tmp_path / "state"), repo, f"docs/triage/{SCOPE_NAME}", owner=HOST)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("name", ["..", ".", "", "a/b", "a\\b"])
def test_a_scope_name_must_be_one_plain_part(name: str) -> None:
    from fr.triage.state_sync import check_scope_name

    with pytest.raises(TriageError, match="scope"):
        check_scope_name(name)
    assert check_scope_name(SCOPE_NAME) == SCOPE_NAME


def test_a_byte_identical_file_is_neither_copied_nor_overwritten(tmp_path: Path) -> None:
    """p4-r5: git keeps no mtime, so a fresh checkout looks newer than everything;
    an identical file is skipped as identical, whatever the mtimes say."""
    state = _state(tmp_path / "state")
    dest = tmp_path / "dest"
    export_state(state, *_at(dest), owner=HOST)
    _age(dest / "judgements.yaml", 3600)
    before = (dest / "judgements.yaml").stat().st_mtime

    again = export_state(state, *_at(dest), owner=HOST)
    back = import_state(*_at(dest), state, force=True)

    assert again.copied == () and back.copied == ()
    assert {s.reason for s in again.skipped} == {"identical"}
    assert sorted(s.path for s in back.skipped) == DURABLE
    assert (dest / "judgements.yaml").stat().st_mtime == before  # never rewritten


def test_the_newer_check_is_documented_as_mtime_based() -> None:
    """p4-r5: the docs say what the check reads, and that a fresh checkout looks newer."""
    from fr.commands import triage_state_cmd
    from fr.triage import state_sync

    for doc in (state_sync.__doc__ or "", triage_state_cmd.import_command.__doc__ or ""):
        flat = " ".join(doc.split())
        assert "mtime" in flat and "fresh checkout" in flat


def test_a_filesystem_error_is_a_clean_triage_error(tmp_path: Path) -> None:
    """p4-r10: an OSError mid-copy is reported by name, never as a traceback."""
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "board").write_text("a file where a directory goes\n", encoding="utf-8")

    with pytest.raises(TriageError, match="board/manifest.yaml"):
        export_state(_state(tmp_path / "state"), *_at(dest), owner=HOST)

    out = tmp_path / "docs"
    (out / SCOPE_NAME).mkdir(parents=True)
    (out / SCOPE_NAME / "board").write_text("x\n", encoding="utf-8")
    result = CliRunner().invoke(
        app,
        ["triage", "state", "export", "--to", str(out), "--repo", SCOPE,
         "--dir", str(tmp_path / "state")],
    )  # fmt: skip
    assert result.exit_code == 2
    assert "board/manifest.yaml" in result.output
    assert "Traceback" not in result.output


# ------------------------------------------------ check-to-write race (gh#1003)
# The checks above read the tree once; the copy must not resolve the names again.
# Each test swaps a path for a symlink the instant the destination check returns,
# which is the window a path-based copy leaves open.


def _swap_after_check(monkeypatch: pytest.MonkeyPatch, rel: str, swap: Callable[[], None]) -> None:
    from fr.triage import state_sync

    check = state_sync._symlinked_dest

    def racing(dest: Path, path: str) -> bool:
        verdict = check(dest, path)
        if path == rel:
            swap()
        return verdict

    monkeypatch.setattr(state_sync, "_symlinked_dest", racing)


def _relink(path: Path, to: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    path.symlink_to(to)


def test_a_destination_file_swapped_for_a_symlink_is_not_written_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "judgements.yaml").write_text("old\n", encoding="utf-8")
    victim = tmp_path / "victim"
    victim.write_text("ORIGINAL\n", encoding="utf-8")
    _swap_after_check(
        monkeypatch, "judgements.yaml", lambda: _relink(dest / "judgements.yaml", victim)
    )

    report = export_state(_state(tmp_path / "state"), *_at(dest), owner=HOST)

    assert victim.read_text(encoding="utf-8") == "ORIGINAL\n"
    assert _skipped(report)["judgements.yaml"] == SYMLINK_DEST
    assert "judgements.yaml" not in report.copied


def test_a_destination_directory_swapped_for_a_symlink_is_not_written_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "dest"
    (dest / "board").mkdir(parents=True)
    victim_dir = tmp_path / "victim-dir"
    victim_dir.mkdir()
    _swap_after_check(
        monkeypatch, "board/manifest.yaml", lambda: _relink(dest / "board", victim_dir)
    )

    report = export_state(_state(tmp_path / "state"), *_at(dest), owner=HOST)

    assert list(victim_dir.iterdir()) == []
    assert _skipped(report)["board/manifest.yaml"] == SYMLINK_DEST


def test_a_source_swapped_for_a_symlink_is_neither_followed_nor_copied_as_a_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state(tmp_path / "state")
    secret = tmp_path / "secret"
    secret.write_text("SECRET\n", encoding="utf-8")
    dest = tmp_path / "dest"
    _swap_after_check(
        monkeypatch, "judgements.yaml", lambda: _relink(state / "judgements.yaml", secret)
    )

    report = export_state(state, *_at(dest), owner=HOST)

    target = dest / "judgements.yaml"
    assert not target.is_symlink()
    assert not target.exists()
    assert _skipped(report)["judgements.yaml"] == SYMLINK


def test_a_copy_keeps_the_source_mtime_and_mode(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    source = state / "judgements.yaml"
    os.chmod(source, 0o640)
    os.utime(source, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
    dest = tmp_path / "dest"

    export_state(state, *_at(dest), owner=HOST)

    copy = (dest / "judgements.yaml").stat()
    assert copy.st_mtime_ns == 1_000_000_000_000_000_000
    assert copy.st_mode & 0o777 == 0o640


def test_a_source_directory_swapped_for_a_symlink_is_not_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state(tmp_path / "state")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "manifest.yaml").write_text("SECRET\n", encoding="utf-8")
    dest = tmp_path / "dest"
    _swap_after_check(monkeypatch, "board/manifest.yaml", lambda: _relink(state / "board", outside))

    report = export_state(state, *_at(dest), owner=HOST)

    assert not (dest / "board" / "manifest.yaml").exists()
    assert _skipped(report)["board/manifest.yaml"] == SYMLINK


# ------------------------------------------------ one exporting scope per directory (gh#1101)


def test_an_export_stamps_the_directory_with_its_scope_id(tmp_path: Path) -> None:
    """gh#1101: the directory is `<path>/<scope name>/`, the same for every host's scope
    of one repo, so the export records which scope id wrote it."""
    dest = tmp_path / "dest"

    report = export_state(_state(tmp_path / "state"), *_at(dest), owner=HOST)

    assert (dest / OWNER_FILE).read_text(encoding="utf-8") == f"{HOST}\n"
    assert OWNER_FILE in report.copied


def test_an_export_refuses_a_directory_another_scope_exported(tmp_path: Path) -> None:
    """gh#1101: a second scope's export would replace the first's judgements, origins and
    snapshots. Refused before a byte moves."""
    dest = tmp_path / "dest"
    export_state(_state(tmp_path / "host"), *_at(dest), owner=HOST)
    (dest / "judgements.yaml").write_text("host's\n", encoding="utf-8")

    with pytest.raises(TriageError, match=f"{HOST}.*{CLOUD}|{CLOUD}.*{HOST}"):
        export_state(_state(tmp_path / "cloud"), *_at(dest), owner=CLOUD)

    assert (dest / "judgements.yaml").read_text(encoding="utf-8") == "host's\n"
    assert (dest / OWNER_FILE).read_text(encoding="utf-8") == f"{HOST}\n"


def test_take_over_hands_the_directory_to_another_scope(tmp_path: Path) -> None:
    dest = tmp_path / "dest"
    export_state(_state(tmp_path / "host"), *_at(dest), owner=HOST)

    export_state(_state(tmp_path / "cloud"), *_at(dest), owner=CLOUD, take_over=True)

    assert (dest / OWNER_FILE).read_text(encoding="utf-8") == f"{CLOUD}\n"


def test_the_same_scope_exports_again_and_an_unstamped_directory_is_claimed(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "dest"
    (dest / "board").mkdir(parents=True)  # exported before the stamp existed
    export_state(_state(tmp_path / "state"), *_at(dest), owner=HOST)

    again = export_state(_state(tmp_path / "state"), *_at(dest), owner=HOST)

    assert OWNER_FILE not in again.copied  # unchanged stamp: nothing to commit
    assert (dest / OWNER_FILE).read_text(encoding="utf-8") == f"{HOST}\n"


def test_a_symlinked_stamp_is_refused_and_never_followed(tmp_path: Path) -> None:
    dest = tmp_path / "dest"
    dest.mkdir()
    outside = tmp_path / "outside"
    outside.write_text(f"{HOST}\n", encoding="utf-8")
    (dest / OWNER_FILE).symlink_to(outside)

    with pytest.raises(TriageError, match="symlink"):
        export_state(_state(tmp_path / "state"), *_at(dest), owner=HOST)
    assert outside.read_text(encoding="utf-8") == f"{HOST}\n"


def test_import_never_carries_the_stamp_into_the_state_directory(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), *_at(src), owner=HOST)
    state = tmp_path / "new"

    import_state(*_at(src), state, force=False)

    assert not (state / OWNER_FILE).exists()


def test_the_export_verb_refuses_another_scopes_directory_until_take_over(
    tmp_path: Path,
) -> None:
    from fr.triage.scope_config import scope_id

    state = _state(tmp_path / "state")
    out = tmp_path / "docs" / "triage"
    export_state(_state(tmp_path / "other"), out, SCOPE_NAME, owner=CLOUD)
    args = ("export", "--to", str(out), "--repo", SCOPE, "--dir", str(state))

    refused = CliRunner().invoke(app, ["triage", "state", *args])
    assert refused.exit_code == 2, refused.output
    assert "--take-over" in refused.output
    assert (out / SCOPE_NAME / OWNER_FILE).read_text(encoding="utf-8") == f"{CLOUD}\n"

    taken = _invoke(*args, "--take-over")
    assert taken.exit_code == 0, taken.output  # type: ignore[attr-defined]
    stamp = (out / SCOPE_NAME / OWNER_FILE).read_text(encoding="utf-8")
    assert stamp == f"{scope_id(SCOPE_NAME)}\n"


# ------------------------------------------------ the export record (spec 2026-11-27 R1)


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_an_export_records_every_durable_file_the_root_holds(tmp_path: Path) -> None:
    import json

    state = _state(tmp_path / "state")
    odd = "board/we\nird\\name.html"  # a newline and a backslash in one file name
    (state / odd).write_text("odd\n", encoding="utf-8")
    dest = tmp_path / "dest"
    (dest / "origins.yaml").parent.mkdir(parents=True)
    (dest / "origins.yaml").write_text("schema: 2\n", encoding="utf-8")  # skipped: identical

    report = export_state(state, *_at(dest), owner=HOST)

    body = json.loads((dest / RECORD_FILE).read_text(encoding="utf-8"))
    assert body["schema"] == 1
    assert sorted(body["files"]) == sorted([*DURABLE, odd])
    assert body["files"]["origins.yaml"] == _sha(dest / "origins.yaml")
    assert body["files"][odd] == _sha(dest / odd)
    assert read_record(dest) == body["files"]
    assert RECORD_FILE in report.copied and "origins.yaml" not in report.copied


def test_an_unchanged_record_is_not_copied_again(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    dest = tmp_path / "dest"
    export_state(state, *_at(dest), owner=HOST)

    again = export_state(state, *_at(dest), owner=HOST)

    assert again.copied == ()  # nothing new: the driver records no PR
    (state / "origins.yaml").write_text("schema: 2\n# more\n", encoding="utf-8")
    third = export_state(state, *_at(dest), owner=HOST)
    assert sorted(third.copied) == sorted(["origins.yaml", RECORD_FILE])


def test_import_never_carries_the_record_into_the_state(tmp_path: Path) -> None:
    src = tmp_path / "repo-copy"
    export_state(_state(tmp_path / "old"), *_at(src), owner=HOST)
    state = tmp_path / "new"

    report = import_state(*_at(src), state, force=True)

    assert not (state / RECORD_FILE).exists()
    assert RECORD_FILE not in report.copied
    assert read_record(tmp_path / "nowhere") is None


# ------------------------------------------- drift: refuse a repo-side edit (R2, R3)


def _bytes(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.is_symlink()
    }


def _drifted(tmp_path: Path) -> tuple[Path, Path]:
    """A state exported once, then the repo copy edited in each of R2's ways."""
    state = _state(tmp_path / "state")
    dest = tmp_path / "repo" / SCOPE_NAME
    export_state(state, *_at(dest), owner=HOST)
    (state / "judgements.yaml").write_text("schema: 3\n# newer\n", encoding="utf-8")
    (dest / "board" / "manifest.yaml").write_text("edited in the repo\n", encoding="utf-8")
    (dest / "origins" / "manifest.yaml").unlink()
    (state / "architecture" / "both.html").write_text("state\n", encoding="utf-8")
    (dest / "architecture" / "both.html").write_text("repo\n", encoding="utf-8")
    (dest / "history" / "repo-only.html").write_text("repo\n", encoding="utf-8")
    return state, dest


def test_an_export_over_a_repo_side_edit_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    state, dest = _drifted(tmp_path)
    before = _bytes(dest)

    with pytest.raises(ExportDrift) as caught:
        export_state(state, *_at(dest), owner=HOST)

    assert caught.value.drift == (
        Drift("architecture/both.html", "added"),
        Drift("board/manifest.yaml", "changed"),
        Drift("history/repo-only.html", "added"),
        Drift("origins/manifest.yaml", "deleted"),
    )
    text = str(caught.value)
    for d in caught.value.drift:
        assert f"{d.kind} {d.path}" in text
    assert f"fr triage state import --from {dest.parent} --only architecture/both.html" in text
    assert "--only origins/manifest.yaml" in text
    assert "fr triage state export" in text and "--force" in text
    assert _bytes(dest) == before  # no file, no stamp, no record


def test_force_overwrites_the_drifted_files_and_rewrites_the_record(tmp_path: Path) -> None:
    state, dest = _drifted(tmp_path)

    report = export_state(state, *_at(dest), owner=HOST, force=True)

    assert (dest / "board" / "manifest.yaml").read_text(encoding="utf-8") == "sections: []\n"
    assert (dest / "origins" / "manifest.yaml").exists()
    assert (dest / "architecture" / "both.html").read_text(encoding="utf-8") == "state\n"
    record = read_record(dest)
    assert record is not None
    assert record["board/manifest.yaml"] == _sha(dest / "board" / "manifest.yaml")
    # the state has no copy of it: kept as the repo has it, and recorded so
    assert record["history/repo-only.html"] == _sha(dest / "history" / "repo-only.html")
    assert RECORD_FILE in report.copied
    export_state(state, *_at(dest), owner=HOST)  # the forced export settled it: no drift


def test_a_repo_only_file_at_the_first_export_is_recorded_not_drift_forever(
    tmp_path: Path,
) -> None:
    """p1-bootstrap-repo-only-files-drift-forever: a durable file the repo copy holds and
    the state never had, present at the no-record export, is recorded as it stands; only
    a later repo edit of it is drift."""
    state = _state(tmp_path / "state")
    dest = tmp_path / "repo" / SCOPE_NAME
    (dest / "architecture").mkdir(parents=True)
    (dest / "architecture" / "closing-order.html").write_text("repo\n", encoding="utf-8")

    export_state(state, *_at(dest), owner=HOST)  # bootstrap: no record yet

    record = read_record(dest)
    assert record is not None and "architecture/closing-order.html" in record
    export_state(state, *_at(dest), owner=HOST)  # unchanged since: no drift
    (dest / "architecture" / "closing-order.html").write_text("edited\n", encoding="utf-8")
    with pytest.raises(ExportDrift) as caught:
        export_state(state, *_at(dest), owner=HOST)
    assert caught.value.drift == (Drift("architecture/closing-order.html", "changed"),)


def test_a_repo_file_equal_to_the_states_copy_is_not_drift(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    dest = tmp_path / "dest"
    export_state(state, *_at(dest), owner=HOST)
    for root in (state, dest):  # added on both sides, the same bytes
        (root / "architecture" / "same.html").write_text("same\n", encoding="utf-8")
    (state / "board" / "manifest.yaml").write_text("state moved on\n", encoding="utf-8")

    report = export_state(state, *_at(dest), owner=HOST)

    assert "board/manifest.yaml" in report.copied  # the state's own change is no drift
    assert read_record(dest) is not None and "architecture/same.html" in (read_record(dest) or {})


def test_with_no_record_nothing_is_drift(tmp_path: Path) -> None:
    state, dest = _drifted(tmp_path)
    (dest / RECORD_FILE).unlink()

    report = export_state(state, *_at(dest), owner=HOST)

    assert "board/manifest.yaml" in report.copied
    assert (dest / "board" / "manifest.yaml").read_text(encoding="utf-8") == "sections: []\n"
    assert read_record(dest) is not None  # the first record is written


def test_a_repo_side_symlink_at_a_durable_path_is_skipped_not_drift(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    dest = tmp_path / "dest"
    export_state(state, *_at(dest), owner=HOST)
    victim = tmp_path / "victim"
    victim.write_text("ORIGINAL\n", encoding="utf-8")
    (dest / "board" / "manifest.yaml").unlink()
    (dest / "board" / "manifest.yaml").symlink_to(victim)

    report = export_state(state, *_at(dest), owner=HOST)

    assert _skipped(report)["board/manifest.yaml"] == SYMLINK_DEST
    assert victim.read_text(encoding="utf-8") == "ORIGINAL\n"


@pytest.mark.parametrize("bad", ["not json\n", '{"schema": 2, "files": {}}\n', "link"])
def test_a_bad_record_is_refused_and_force_rewrites_it(tmp_path: Path, bad: str) -> None:
    state = _state(tmp_path / "state")
    dest = tmp_path / "dest"
    export_state(state, *_at(dest), owner=HOST)
    outside = tmp_path / "outside"
    outside.write_text("{}\n", encoding="utf-8")
    (dest / RECORD_FILE).unlink()
    if bad == "link":
        (dest / RECORD_FILE).symlink_to(outside)
    else:
        (dest / RECORD_FILE).write_text(bad, encoding="utf-8")

    with pytest.raises(BadRecord, match=RECORD_FILE):
        export_state(state, *_at(dest), owner=HOST)

    export_state(state, *_at(dest), owner=HOST, force=True)
    assert not (dest / RECORD_FILE).is_symlink()
    assert read_record(dest) is not None
    assert outside.read_text(encoding="utf-8") == "{}\n"  # never written through


def test_the_export_verb_refuses_drift_with_exit_2_until_force(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    out = tmp_path / "docs" / "triage"
    args = ("export", "--to", str(out), "--repo", SCOPE, "--dir", str(state))
    assert _invoke(*args).exit_code == 0  # type: ignore[attr-defined]
    edited = out / SCOPE_NAME / "board" / "manifest.yaml"
    edited.write_text("edited in the repo\n", encoding="utf-8")

    refused = CliRunner().invoke(app, ["triage", "state", *args])
    assert refused.exit_code == 2, refused.output
    assert "changed board/manifest.yaml" in refused.output
    assert edited.read_text(encoding="utf-8") == "edited in the repo\n"

    forced = _invoke(*args, "--force")
    assert forced.exit_code == 0, forced.output  # type: ignore[attr-defined]
    assert edited.read_text(encoding="utf-8") == "sections: []\n"


# ------------------------------------------------- the targeted import (R5)


def _imported(tmp_path: Path) -> tuple[Path, Path]:
    """A repo copy and a state imported from it, the state's copies then made newer."""
    src = tmp_path / "repo" / SCOPE_NAME
    export_state(_state(tmp_path / "old"), *_at(src), owner=HOST)
    state = tmp_path / "state"
    import_state(*_at(src), state, force=False)
    for rel in DURABLE:
        _age(src / rel, 60)  # every repo copy older than the state's
    return src, state


def _stats(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        rel: (p.read_bytes(), p.stat().st_mtime_ns)
        for rel in _files(root)
        if (p := root / rel).is_file()
    }


def test_only_copies_a_named_file_over_a_newer_state_copy_and_nothing_else(
    tmp_path: Path,
) -> None:
    src, state = _imported(tmp_path)
    (src / "board" / "manifest.yaml").write_text("repo edit\n", encoding="utf-8")
    _age(src / "board" / "manifest.yaml", 120)
    (src / "judgements.yaml").write_text("schema: 3\n# repo\n", encoding="utf-8")  # unnamed
    before = _stats(state)

    report = import_state(*_at(src), state, force=False, only=["board/manifest.yaml"])

    assert report.copied == ("board/manifest.yaml",)
    assert (state / "board" / "manifest.yaml").read_text(encoding="utf-8") == "repo edit\n"
    after = _stats(state)
    del before["board/manifest.yaml"], after["board/manifest.yaml"]
    assert after == before  # unnamed state files: bytes and mtime untouched


def test_only_a_directory_takes_every_durable_file_under_it(tmp_path: Path) -> None:
    src, state = _imported(tmp_path)
    (src / "architecture" / "hurts.html").write_text("new\n", encoding="utf-8")
    (src / "architecture" / "fresh.html").write_text("fresh\n", encoding="utf-8")

    report = import_state(*_at(src), state, force=False, only=["architecture"])

    assert sorted(report.copied) == ["architecture/fresh.html", "architecture/hurts.html"]
    assert (state / "architecture" / "fresh.html").read_text(encoding="utf-8") == "fresh\n"


def test_only_removes_a_named_path_the_repo_lacks(tmp_path: Path) -> None:
    src, state = _imported(tmp_path)
    (src / "origins" / "manifest.yaml").unlink()

    report = import_state(*_at(src), state, force=False, only=["origins/manifest.yaml"])

    assert report.removed == ("origins/manifest.yaml",)
    assert not (state / "origins" / "manifest.yaml").exists()


def test_only_skips_a_named_symlink_on_either_side(tmp_path: Path) -> None:
    src, state = _imported(tmp_path)
    secret = tmp_path / "secret"
    secret.write_text("PRIVATE\n", encoding="utf-8")
    (src / "board" / "planted.html").symlink_to(secret)  # repo side
    (state / "origins" / "kept.html").symlink_to(secret)  # state side, repo lacks it

    report = import_state(
        *_at(src), state, force=False, only=["board/planted.html", "origins/kept.html"]
    )

    assert report.copied == () and report.removed == ()
    assert _skipped(report) == {"board/planted.html": SYMLINK, "origins/kept.html": SYMLINK_DEST}
    assert (state / "origins" / "kept.html").is_symlink()
    assert secret.read_text(encoding="utf-8") == "PRIVATE\n"


@pytest.mark.parametrize("bad", ["../x", "/abs", "board/../judgements.yaml", "nothing/here"])
def test_only_refuses_a_bad_or_unmatched_path_before_any_write(tmp_path: Path, bad: str) -> None:
    src, state = _imported(tmp_path)
    (src / "board" / "manifest.yaml").write_text("repo edit\n", encoding="utf-8")
    before = _stats(state)

    with pytest.raises(TriageError):
        import_state(*_at(src), state, force=False, only=["board/manifest.yaml", bad])

    assert _stats(state) == before


def test_the_import_verb_takes_only_and_prints_removed(tmp_path: Path) -> None:
    out = tmp_path / "docs" / "triage"
    src, state = _imported(tmp_path / "w")
    shutil.copytree(src, out / SCOPE_NAME)
    (out / SCOPE_NAME / "origins" / "manifest.yaml").unlink()
    (out / SCOPE_NAME / "board" / "manifest.yaml").write_text("repo edit\n", encoding="utf-8")
    args = ("import", "--from", str(out), "--repo", SCOPE, "--dir", str(state))

    result = _invoke(*args, "--only", "origins/manifest.yaml", "--only", "board/manifest.yaml")

    text = result.output  # type: ignore[attr-defined]
    assert result.exit_code == 0, text  # type: ignore[attr-defined]
    assert "removed origins/manifest.yaml" in text and "copied board/manifest.yaml" in text
    refused = CliRunner().invoke(app, ["triage", "state", *args, "--only", "../x"])
    assert refused.exit_code == 2, refused.output


# ------------------------------------- phase 1 review: hostile records and recovery


@pytest.mark.parametrize(
    "key", ["history/a\0b", "../judgements.yaml", "/abs/judgements.yaml", "facts.json"]
)
def test_a_hostile_record_key_is_a_bad_record_never_a_path(tmp_path: Path, key: str) -> None:
    """p1-r1: a record key from a cloned repo is validated before it reaches a descriptor
    open; a NUL, a `..`, an absolute or a non-durable key is a refusal, not a traceback."""
    import json

    state = _state(tmp_path / "state")
    dest = tmp_path / "repo" / SCOPE_NAME
    export_state(state, *_at(dest), owner=HOST)
    (dest / RECORD_FILE).write_text(
        json.dumps({"schema": 1, "files": {key: "0" * 64}}), encoding="utf-8"
    )
    before = _bytes(dest)

    with pytest.raises(BadRecord):
        export_state(state, *_at(dest), owner=HOST)
    assert _bytes(dest) == before


def test_a_record_named_path_that_is_a_repo_side_symlink_is_not_drift(tmp_path: Path) -> None:
    state = _state(tmp_path / "state")
    dest = tmp_path / "repo" / SCOPE_NAME
    export_state(state, *_at(dest), owner=HOST)
    secret = tmp_path / "secret"
    secret.write_text("PRIVATE\n", encoding="utf-8")
    (dest / "board" / "manifest.yaml").unlink()
    (dest / "board" / "manifest.yaml").symlink_to(secret)  # recorded path, now a link

    report = export_state(state, *_at(dest), owner=HOST)

    assert _skipped(report)["board/manifest.yaml"] == SYMLINK_DEST
    assert secret.read_text(encoding="utf-8") == "PRIVATE\n"


def test_a_directory_record_is_refused_and_force_names_the_hand_fix(tmp_path: Path) -> None:
    """p1-r2: `--force` writes only a regular file, so a directory at the record is named
    with the hand fix, in both the refusal and the forced run; nothing is written."""
    state = _state(tmp_path / "state")
    dest = tmp_path / "repo" / SCOPE_NAME
    export_state(state, *_at(dest), owner=HOST)
    (dest / RECORD_FILE).unlink()
    (dest / RECORD_FILE).mkdir()
    (state / "judgements.yaml").write_text("schema: 3\n# newer\n", encoding="utf-8")
    before = _bytes(dest)

    with pytest.raises(BadRecord) as caught:
        export_state(state, *_at(dest), owner=HOST)
    assert not caught.value.forceable and "remove it by hand" in str(caught.value)
    with pytest.raises(TriageError, match="not a regular file; remove it by hand"):
        export_state(state, *_at(dest), owner=HOST, force=True)
    assert (dest / RECORD_FILE).is_dir()
    assert (dest / "judgements.yaml").read_text(encoding="utf-8") == "schema: 3\n"
    assert {k: v for k, v in _bytes(dest).items() if k != "judgements.yaml"} == {
        k: v for k, v in before.items() if k != "judgements.yaml"
    }


def test_only_reports_a_state_only_path_under_a_repo_side_symlinked_dir(tmp_path: Path) -> None:
    """p1-r4: a named path the repo cannot be judged on (it lies under a repo-side
    symlink) is skipped and reported, never removed from the state."""
    src, state = _imported(tmp_path)
    shutil.rmtree(src / "architecture")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (src / "architecture").symlink_to(elsewhere, target_is_directory=True)

    report = import_state(*_at(src), state, force=False, only=["architecture/hurts.html"])

    assert report.removed == ()
    assert _skipped(report)["architecture/hurts.html"] == SYMLINK
    assert (state / "architecture" / "hurts.html").exists()


def test_the_remedy_the_refusal_prints_clears_the_drift(tmp_path: Path) -> None:
    """p1-r7: the recovery R3 advertises, end to end: `import --only` each drifted path
    (copying the repo's edits and additions, removing what the repo deleted), then export
    again, which now finds no drift and keeps every repo edit."""
    state, dest = _drifted(tmp_path)
    with pytest.raises(ExportDrift) as caught:
        export_state(state, *_at(dest), owner=HOST)

    report = import_state(*_at(dest), state, force=False, only=[d.path for d in caught.value.drift])

    assert sorted(report.removed) == ["origins/manifest.yaml"]
    assert "history/repo-only.html" in report.copied  # the state lacked it
    again = export_state(state, *_at(dest), owner=HOST)
    assert "board/manifest.yaml" not in again.copied
    assert (dest / "board" / "manifest.yaml").read_text(encoding="utf-8") == "edited in the repo\n"
    assert (dest / "architecture" / "both.html").read_text(encoding="utf-8") == "repo\n"
    assert not (dest / "origins" / "manifest.yaml").exists()


def test_the_export_verbs_remedy_carries_its_own_scope_options(tmp_path: Path) -> None:
    """p1-r3: the hand command's refusal prints commands with the scope options it was
    given, so they paste as printed."""
    state = _state(tmp_path / "state")
    out = tmp_path / "docs" / "triage"
    args = ("export", "--to", str(out), "--repo", SCOPE, "--dir", str(state))
    assert _invoke(*args).exit_code == 0  # type: ignore[attr-defined]
    (out / SCOPE_NAME / "board" / "manifest.yaml").write_text("edited\n", encoding="utf-8")

    refused = CliRunner().invoke(app, ["triage", "state", *args])

    assert refused.exit_code == 2, refused.output
    flat = " ".join(refused.output.split())
    scope = f"--repo {SCOPE} --dir {state.resolve()}"
    assert f"fr triage state import {scope} --from {out}" in flat, flat
    assert f"fr triage state export {scope} --to {out} --force" in flat, flat
