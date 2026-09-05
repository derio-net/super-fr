"""Crash-safe writes and the cross-process migration lock (review r5-e7).

The migration framework runs **automatically, before the command the operator
typed**, over files an agent may have open. Two hazards follow, and both have
the same failure signature — a tree left in a state nobody chose:

- a truncate-then-write interrupted halfway leaves a `_meta.yaml` that reads
  as version 1, so the next `fr` command tries to migrate it again and refuses
  everything until a human notices;
- two `fr` processes migrating one tree both apply and both commit.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from fr.artifacts.atomic import migration_lock, write_text_atomic


def test_a_failing_write_leaves_the_original_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The property the whole module exists for. `path.write_text` truncates
    first, so the same failure left an empty file."""
    target = tmp_path / "_meta.yaml"
    original = "schema_version: 2\nplan: p\n"
    target.write_text(original)

    real_fsync = os.fsync

    def boom(fd):  # type: ignore[no-untyped-def]
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", boom)

    with pytest.raises(OSError):
        write_text_atomic(target, "schema_version: 3\nplan: p\n")

    monkeypatch.setattr(os, "fsync", real_fsync)

    assert target.read_text() == original
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "_meta.yaml"]
    assert leftovers == [], f"temp file left behind: {leftovers}"


def test_the_replacement_is_visible_all_at_once(tmp_path: Path) -> None:
    target = tmp_path / "a.yaml"
    target.write_text("old\n")

    write_text_atomic(target, "new\n")

    assert target.read_text() == "new\n"
    assert [p.name for p in tmp_path.iterdir()] == ["a.yaml"]


def test_permission_bits_survive_the_replacement(tmp_path: Path) -> None:
    """`os.replace` of a fresh temp file would otherwise reset an artifact the
    operator deliberately `chmod`ed."""
    target = tmp_path / "a.yaml"
    target.write_text("old\n")
    os.chmod(target, 0o640)

    write_text_atomic(target, "new\n")

    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_crlf_and_a_missing_trailing_newline_are_preserved(tmp_path: Path) -> None:
    """`newline=""` — this is a byte-level replacement of somebody else's
    file, not a normaliser."""
    target = tmp_path / "a.yaml"

    write_text_atomic(target, "one\r\ntwo\r\nno-trailing-newline")

    assert target.read_bytes() == b"one\r\ntwo\r\nno-trailing-newline"


def test_a_read_only_file_raises_rather_than_corrupting(tmp_path: Path) -> None:
    """A read-only ARTIFACT is still replaceable (the directory is writable),
    which is the honest answer — but a read-only DIRECTORY is not, and that
    must be an ordinary exception the runner records per artifact."""
    d = tmp_path / "locked"
    d.mkdir()
    target = d / "a.yaml"
    target.write_text("old\n")
    os.chmod(d, 0o500)
    try:
        with pytest.raises(OSError):
            write_text_atomic(target, "new\n")
        assert target.read_text() == "old\n"
    finally:
        os.chmod(d, 0o700)


# --- the advisory lock ----------------------------------------------------


def test_the_lock_is_exclusive_within_one_process(tmp_path: Path) -> None:
    lock = tmp_path / "fr-migrate.lock"

    with migration_lock(lock) as first:
        assert first is True
        with migration_lock(lock) as second:
            assert second is False

    with migration_lock(lock) as again:
        assert again is True, "the lock must be released on the way out"


def test_the_lock_is_exclusive_across_processes(tmp_path: Path) -> None:
    """A barrier, not a sleep: the child signals that it holds the lock by
    creating a file, and waits for a file this process creates."""
    import subprocess
    import sys
    import textwrap
    import time

    lock = tmp_path / "fr-migrate.lock"
    held = tmp_path / "held"
    release = tmp_path / "release"
    src = textwrap.dedent(
        f"""
        import sys, time
        from pathlib import Path
        sys.path.insert(0, {str(Path("packages/fr/src").resolve())!r})
        from fr.artifacts.atomic import migration_lock
        with migration_lock(Path({str(lock)!r})) as ok:
            assert ok
            Path({str(held)!r}).write_text("x")
            while not Path({str(release)!r}).exists():
                time.sleep(0.01)
        """
    )
    child = subprocess.Popen([sys.executable, "-c", src])
    try:
        deadline = time.monotonic() + 30
        while not held.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert held.exists(), "child never took the lock"

        with migration_lock(lock) as ours:
            assert ours is False
    finally:
        release.write_text("x")
        child.wait(timeout=30)

    with migration_lock(lock) as after:
        assert after is True


def test_no_lock_file_means_no_lock_and_no_refusal(tmp_path: Path) -> None:
    """A repo with no git directory has no concurrent-commit hazard; an
    unlocked migration is exactly what happened before this existed."""
    with migration_lock(None) as ok:
        assert ok is True


def test_an_unwritable_lock_directory_does_not_block_migration(tmp_path: Path) -> None:
    d = tmp_path / "ro"
    d.mkdir()
    os.chmod(d, 0o500)
    try:
        with migration_lock(d / "sub" / "fr-migrate.lock") as ok:
            assert ok is True
    finally:
        os.chmod(d, 0o700)
