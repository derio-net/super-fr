"""The state ref: a scope's durable copy, `refs/fr/triage/<scope-id>` (spec
2026-10-07-cloud-triage R5, §B, Test Plan 5).

Every remote is a bare repo under `tmp_path`; no ref is ever pushed anywhere else.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.triage import state_sync
from fr.triage.model import Scope
from fr.triage.state_ref import (
    REF_FILES,
    StateRefConflict,
    fetch_state,
    push_state,
    read_base,
    ref_name,
)

SCOPE_ID = "s-0123abcd"


class _Private:
    """A forge that answers every repo private: the privacy guard lets every push through."""

    def repo_visibility(self, repo: str) -> str:
        return "private"


PRIVATE: dict[str, Any] = {
    "scope": Scope(kind="repo", target="o/r"),
    "state_repo": "o/r",
    "client": _Private(),
}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _clone(tmp_path: Path, name: str, origin: Path) -> Path:
    path = tmp_path / name
    _git(tmp_path, "clone", "--quiet", str(origin), str(path))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(path, "config", k, v)
    return path


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(bare))
    seed = _clone(tmp_path, "seed", bare)
    (seed / "README").write_text("r\n")
    _git(seed, "add", ".")
    _git(seed, "commit", "--quiet", "-m", "seed")
    _git(seed, "push", "--quiet", "origin", "HEAD:main")
    return bare


def _state(clone: Path) -> Path:
    state = clone / ".fr" / "triage-state" / "scope"
    state.mkdir(parents=True)
    _git(clone, "rev-parse", "--git-dir")  # it is a clone
    (clone / ".git" / "info" / "exclude").write_text(".fr/triage-state/\n")
    return state


EVERY = {
    "judgements.yaml": b"schema: 6\nissues: {}\n",
    "origins.yaml": b"schema: 2\n",
    "subsystems.yaml": b"subsystems: []\n",
    "board/manifest.yaml": b"fragments: []\n",
    "board/fragments/a.html": b"<p>a</p>\n",
    "origins/manifest.yaml": b"o\n",
    "architecture/manifest.yaml": b"a\n",
    "history/manifest.yaml": b"h\n",
    "snapshots/2026-10-08.json": b"{}\n",
    "authored-src/notes.md": b"# notes\n",
    "merge-stops.json": b'{"stops": []}\n',
    "lease.yaml": b"holder: s-0123abcd host:abc\n",
    "scope-durable.yaml": b"state_repo: derio-net/super-fr\nforge_api: rest\n",
    "requests.yaml": b"requests: []\n",
    "sessions.yaml": b"sessions: []\n",
    "rehomes.yaml": b"rehomes: []\n",
}
NEVER = {
    "facts.json": b"{}\n",
    "board.html": b"<html></html>\n",
    "origins.html": b"<html></html>\n",
    "scope.yaml": b"claim_expiry_hours: 24\n",
    "origins-facts.json": b"{}\n",
}


def _fill(state: Path, files: dict[str, bytes]) -> None:
    for rel, content in files.items():
        path = state / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _tree(origin: Path, ref: str) -> list[str]:
    return sorted(_git(origin, "ls-tree", "-r", "--name-only", ref).split())


def test_ref_files_is_the_one_list_and_names_the_durable_export_set() -> None:
    assert REF_FILES == (
        "judgements.yaml",
        "origins.yaml",
        "subsystems.yaml",
        "board/",
        "origins/",
        "architecture/",
        "history/",
        "snapshots/",
        "authored-src/",
        "merge-stops.json",
        "lease.yaml",
        "scope-durable.yaml",
        "requests.yaml",
        "sessions.yaml",
        "rehomes.yaml",
    )
    files = {e for e in REF_FILES if not e.endswith("/")}
    dirs = tuple(e.rstrip("/") for e in REF_FILES if e.endswith("/"))
    assert set(state_sync.DURABLE_FILES) <= files
    assert state_sync.DURABLE_DIRS == dirs
    assert ref_name(SCOPE_ID) == "refs/fr/triage/s-0123abcd"


def test_push_writes_exactly_the_ref_files_that_exist(tmp_path: Path, origin: Path) -> None:
    clone = _clone(tmp_path, "a", origin)
    state = _state(clone)
    _fill(state, {**EVERY, **NEVER})

    sha = push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)

    assert _git(origin, "rev-parse", ref_name(SCOPE_ID)).strip() == sha
    assert _tree(origin, ref_name(SCOPE_ID)) == sorted(EVERY)
    assert read_base(state) == sha
    assert _git(clone, "status", "--porcelain", "--untracked-files=all") == ""


def test_a_partial_state_pushes_only_what_exists(tmp_path: Path, origin: Path) -> None:
    clone = _clone(tmp_path, "a", origin)
    state = _state(clone)
    _fill(state, {"judgements.yaml": EVERY["judgements.yaml"], "facts.json": b"{}\n"})

    push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)

    assert _tree(origin, ref_name(SCOPE_ID)) == ["judgements.yaml"]


def test_fetch_into_a_fresh_clone_restores_every_entry_byte_for_byte(
    tmp_path: Path, origin: Path
) -> None:
    a = _clone(tmp_path, "a", origin)
    state_a = _state(a)
    _fill(state_a, EVERY)
    sha = push_state(state_a, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)

    b = _clone(tmp_path, "b", origin)
    state_b = b / ".fr" / "triage-state" / "scope"

    assert fetch_state(state_b, str(origin), SCOPE_ID) == sha
    for rel, content in EVERY.items():
        assert (state_b / rel).read_bytes() == content, rel
    assert read_base(state_b) == sha


def test_fetch_with_no_ref_returns_none_and_writes_nothing(tmp_path: Path, origin: Path) -> None:
    b = _clone(tmp_path, "b", origin)
    state_b = b / ".fr" / "triage-state" / "scope"

    assert fetch_state(state_b, str(origin), SCOPE_ID) is None
    assert not state_b.exists()


def test_a_second_push_from_the_same_base_moves_the_ref(tmp_path: Path, origin: Path) -> None:
    a = _clone(tmp_path, "a", origin)
    state = _state(a)
    _fill(state, {"judgements.yaml": b"one\n"})
    first = push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    (state / "judgements.yaml").write_bytes(b"two\n")

    second = push_state(state, str(origin), SCOPE_ID, expected_old=first, **PRIVATE)

    assert second != first
    assert _git(origin, "show", f"{ref_name(SCOPE_ID)}:judgements.yaml") == "two\n"
    assert _git(origin, "rev-parse", f"{second}^").strip() == first  # history kept


def test_a_stale_expected_old_fails_and_changes_nothing(tmp_path: Path, origin: Path) -> None:
    a = _clone(tmp_path, "a", origin)
    state_a = _state(a)
    _fill(state_a, {"judgements.yaml": b"a\n"})
    base = push_state(state_a, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)

    b = _clone(tmp_path, "b", origin)
    state_b = b / ".fr" / "triage-state" / "scope"
    fetch_state(state_b, str(origin), SCOPE_ID)
    (state_b / "judgements.yaml").write_bytes(b"b\n")
    winner = push_state(state_b, str(origin), SCOPE_ID, expected_old=base, **PRIVATE)

    (state_a / "judgements.yaml").write_bytes(b"a2\n")
    with pytest.raises(StateRefConflict, match=ref_name(SCOPE_ID)):
        push_state(state_a, str(origin), SCOPE_ID, expected_old=base, **PRIVATE)

    assert _git(origin, "rev-parse", ref_name(SCOPE_ID)).strip() == winner
    assert read_base(state_a) == base


def test_creating_a_ref_that_already_exists_is_a_conflict(tmp_path: Path, origin: Path) -> None:
    a = _clone(tmp_path, "a", origin)
    state_a = _state(a)
    _fill(state_a, {"judgements.yaml": b"a\n"})
    push_state(state_a, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)

    b = _clone(tmp_path, "b", origin)
    state_b = _state(b)
    _fill(state_b, {"judgements.yaml": b"b\n"})
    with pytest.raises(StateRefConflict):
        push_state(state_b, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)


def test_the_ref_is_no_branch(tmp_path: Path, origin: Path) -> None:
    a = _clone(tmp_path, "a", origin)
    state = _state(a)
    _fill(state, {"judgements.yaml": b"a\n"})
    push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    _git(a, "fetch", "--quiet", "origin")

    assert "triage" not in _git(a, "branch", "-a")
    assert "triage" not in _git(origin, "branch", "-a")


def test_a_symlink_in_the_state_is_never_pushed(tmp_path: Path, origin: Path) -> None:
    a = _clone(tmp_path, "a", origin)
    state = _state(a)
    secret = tmp_path / "secret"
    secret.write_text("do not leak\n")
    (state / "board").mkdir()
    (state / "board" / "manifest.yaml").symlink_to(secret)
    (state / "judgements.yaml").symlink_to(secret)
    (state / "origins.yaml").write_text("o\n")

    push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)

    assert _tree(origin, ref_name(SCOPE_ID)) == ["origins.yaml"]


def test_fetch_never_writes_a_path_outside_the_ref_files(tmp_path: Path, origin: Path) -> None:
    """A ref someone else wrote may carry anything; only REF_FILES entries come back."""
    seed = _clone(tmp_path, "w", origin)
    _git(seed, "checkout", "--quiet", "--orphan", "x")
    _git(seed, "rm", "-rf", "--quiet", ".")
    (seed / "judgements.yaml").write_text("ok\n")
    (seed / "facts.json").write_text("{}\n")
    (seed / "evil.sh").write_text("rm -rf /\n")
    _git(seed, "add", ".")
    _git(seed, "commit", "--quiet", "-m", "foreign")
    _git(seed, "push", "--quiet", "origin", f"HEAD:{ref_name(SCOPE_ID)}")

    b = _clone(tmp_path, "b", origin)
    state_b = b / ".fr" / "triage-state" / "scope"
    fetch_state(state_b, str(origin), SCOPE_ID)

    assert sorted(p.name for p in state_b.iterdir() if not p.name.startswith(".")) == [
        "judgements.yaml"
    ]


# ------------------------------------------- the base: remote, ref and sha (p3-r4)


def _bare(tmp_path: Path, name: str) -> Path:
    bare = tmp_path / name
    _git(tmp_path, "init", "--quiet", "--bare", str(bare))
    return bare


def test_the_base_records_the_remote_and_ref_it_came_from(tmp_path: Path, origin: Path) -> None:
    a = _clone(tmp_path, "a", origin)
    state = _state(a)
    _fill(state, {"judgements.yaml": b"a\n"})
    ref = ref_name(SCOPE_ID)

    sha = push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)

    assert read_base(state, remote=str(origin), ref=ref) == sha
    assert read_base(state, remote=str(tmp_path / "elsewhere.git"), ref=ref) is None
    assert read_base(state, remote=str(origin), ref=ref_name("s-ffffffff")) is None


def test_a_base_for_another_remote_is_discarded_not_called_another_writer(
    tmp_path: Path, origin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI push takes its expected_old from the base for THIS remote and ref."""
    from fr.cli import app
    from fr.commands import triage_cmd, triage_state_cmd
    from typer.testing import CliRunner

    other = _bare(tmp_path, "other.git")
    a = _clone(tmp_path, "a", origin)
    state = _state(a)
    _fill(state, {"judgements.yaml": b"a\n", "scope-durable.yaml": b"state_repo: o/r\n"})
    push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    monkeypatch.setattr(triage_cmd, "make_visibility_client", lambda: _Private())
    monkeypatch.setattr(triage_state_cmd, "scope_id", lambda scope: SCOPE_ID)

    result = CliRunner().invoke(
        app,
        ["triage", "state", "push", "--repo", "o/r", "--dir", str(state), "--remote", str(other)],
    )

    assert result.exit_code == 0, result.output
    assert _git(other, "rev-parse", ref_name(SCOPE_ID)).strip() != ""


def test_a_base_the_remote_no_longer_has_is_discarded(tmp_path: Path, origin: Path) -> None:
    a = _clone(tmp_path, "a", origin)
    state = _state(a)
    _fill(state, {"judgements.yaml": b"a\n"})
    ref = ref_name(SCOPE_ID)
    first = push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    _git(origin, "update-ref", "-d", ref)  # the remote's ref is gone (recreated repo, prune)
    (state / "judgements.yaml").write_bytes(b"a2\n")

    second = push_state(state, str(origin), SCOPE_ID, expected_old=first, **PRIVATE)

    assert _git(origin, "rev-parse", ref).strip() == second


def test_a_fetch_over_unpushed_local_changes_refuses_and_writes_nothing(
    tmp_path: Path, origin: Path
) -> None:
    a = _clone(tmp_path, "a", origin)
    state_a = _state(a)
    _fill(state_a, {"judgements.yaml": b"v1\n"})
    v1 = push_state(state_a, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    b = _clone(tmp_path, "b", origin)
    state_b = b / ".fr" / "triage-state" / "scope"
    fetch_state(state_b, str(origin), SCOPE_ID)
    (state_a / "judgements.yaml").write_bytes(b"v2\n")
    push_state(state_a, str(origin), SCOPE_ID, expected_old=v1, **PRIVATE)
    (state_b / "judgements.yaml").write_bytes(b"mine, unpushed\n")

    with pytest.raises(StateRefConflict, match="not pushed"):
        fetch_state(state_b, str(origin), SCOPE_ID)

    assert (state_b / "judgements.yaml").read_bytes() == b"mine, unpushed\n"
    assert read_base(state_b, remote=str(origin), ref=ref_name(SCOPE_ID)) == v1


def test_discard_local_lets_a_fetch_overwrite_unpushed_changes(
    tmp_path: Path, origin: Path
) -> None:
    a = _clone(tmp_path, "a", origin)
    state_a = _state(a)
    _fill(state_a, {"judgements.yaml": b"v1\n"})
    push_state(state_a, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    b = _clone(tmp_path, "b", origin)
    state_b = _state(b)
    _fill(state_b, {"judgements.yaml": b"mine\n"})

    fetch_state(state_b, str(origin), SCOPE_ID, discard_local=True)

    assert (state_b / "judgements.yaml").read_bytes() == b"v1\n"


def test_a_fetch_removes_the_files_the_ref_no_longer_carries(tmp_path: Path, origin: Path) -> None:
    a = _clone(tmp_path, "a", origin)
    state_a = _state(a)
    _fill(state_a, {"judgements.yaml": b"j\n", "board/manifest.yaml": b"m\n", "lease.yaml": b"l\n"})
    v1 = push_state(state_a, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    b = _clone(tmp_path, "b", origin)
    state_b = b / ".fr" / "triage-state" / "scope"
    fetch_state(state_b, str(origin), SCOPE_ID)
    (state_b / "facts.json").write_bytes(b"{}\n")  # not a ref file: never touched
    (state_a / "lease.yaml").unlink()
    (state_a / "board" / "manifest.yaml").unlink()
    push_state(state_a, str(origin), SCOPE_ID, expected_old=v1, **PRIVATE)

    fetch_state(state_b, str(origin), SCOPE_ID)

    assert not (state_b / "lease.yaml").exists()
    assert not (state_b / "board" / "manifest.yaml").exists()
    assert (state_b / "judgements.yaml").read_bytes() == b"j\n"
    assert (state_b / "facts.json").read_bytes() == b"{}\n"


def test_fetch_ref_fetches_first_and_never_asks_ls_remote(
    tmp_path: Path, origin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p3-r5: one round trip, and no window between reading the sha and fetching it."""
    from fr.triage import gitseam

    a = _clone(tmp_path, "a", origin)
    state = _state(a)
    _fill(state, {"judgements.yaml": b"a\n"})
    sha = push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    b = _clone(tmp_path, "b", origin)
    seen: list[list[str]] = []
    real = gitseam._run

    def spy(argv: list[str], cwd: Path, **kw: Any) -> Any:
        seen.append(argv)
        return real(argv, cwd, **kw)

    monkeypatch.setattr(gitseam, "_run", spy)

    assert gitseam.fetch_ref(b, str(origin), ref_name(SCOPE_ID)) == sha
    assert not any("ls-remote" in argv for argv in seen), seen
    assert seen[0][:2] == ["git", "fetch"]


def test_fetch_ref_of_a_ref_the_remote_dropped_is_none_and_drops_the_local_copy(
    tmp_path: Path, origin: Path
) -> None:
    from fr.triage import gitseam

    a = _clone(tmp_path, "a", origin)
    state = _state(a)
    _fill(state, {"judgements.yaml": b"a\n"})
    push_state(state, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)
    b = _clone(tmp_path, "b", origin)
    ref = ref_name(SCOPE_ID)
    assert gitseam.fetch_ref(b, str(origin), ref) is not None
    _git(origin, "update-ref", "-d", ref)

    assert gitseam.fetch_ref(b, str(origin), ref) is None
    assert _git(b, "for-each-ref", ref) == ""


# ------------------------------------------------------------- modes (p3-r12)


def test_an_executable_keeps_its_mode_across_the_ref_and_restores_honour_the_umask(
    tmp_path: Path, origin: Path
) -> None:
    import os
    import stat

    a = _clone(tmp_path, "a", origin)
    state_a = _state(a)
    _fill(state_a, {"judgements.yaml": b"j\n", "authored-src/build.sh": b"#!/bin/sh\n"})
    (state_a / "authored-src" / "build.sh").chmod(0o755)
    push_state(state_a, str(origin), SCOPE_ID, expected_old=None, **PRIVATE)

    modes = {
        line.split("\t")[1]: line.split()[0]
        for line in _git(origin, "ls-tree", "-r", ref_name(SCOPE_ID)).splitlines()
    }
    assert modes == {"authored-src/build.sh": "100755", "judgements.yaml": "100644"}

    b = _clone(tmp_path, "b", origin)
    state_b = b / ".fr" / "triage-state" / "scope"
    old = os.umask(0o027)
    try:
        fetch_state(state_b, str(origin), SCOPE_ID)
    finally:
        os.umask(old)

    assert stat.S_IMODE((state_b / "judgements.yaml").stat().st_mode) == 0o640
    assert stat.S_IMODE((state_b / "authored-src" / "build.sh").stat().st_mode) == 0o750
