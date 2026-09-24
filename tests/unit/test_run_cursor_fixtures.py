"""The captured run cursors stay captured.

`tests/fixtures/run_cursors/` holds real cursors `fr` wrote, copied byte for
byte (see its `NOTE.md`). They are the fixtures the `run` 4 -> 5 migration is
tested against, and their whole value is that nobody authored them — so the
one thing worth pinning is that nobody has SINCE. An edited capture is a
constructed fixture with a misleading provenance note, which is worse than an
honestly constructed one.

Deliberately NOT asserted here: that any of them parses with the live
`RunState`. Phase 3 of the unit-record plan replaces that model, and the v1-v4
files must then be read by the frozen legacy reader instead; a parse assertion
here would have to be deleted by the very change it was guarding.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "run_cursors"
_ROW = re.compile(r"^\| `(v\d/[^`]+\.yaml)` \|.*\| `([0-9a-f]{64})` \|", re.MULTILINE)


def _recorded() -> dict[str, str]:
    return dict(_ROW.findall((FIXTURES / "NOTE.md").read_text()))


def _on_disk() -> list[str]:
    return sorted(str(p.relative_to(FIXTURES)) for p in FIXTURES.glob("v*/*.yaml"))


def test_every_fixture_has_a_provenance_row_and_every_row_a_fixture() -> None:
    assert _on_disk(), "no captured cursors found — the glob is wrong, not the fixtures"
    assert sorted(_recorded()) == _on_disk()


def test_no_captured_cursor_has_been_edited() -> None:
    edited = {
        name: sha
        for name, sha in _recorded().items()
        if hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() != sha
    }
    assert not edited, (
        f"{sorted(edited)} no longer match the SHA-256 recorded in NOTE.md. These are "
        "CAPTURES: re-capture from git and update the row, never hand-edit the YAML."
    )


def test_each_cursor_declares_the_version_its_directory_claims() -> None:
    """`v1/` means NO stamp — the key did not exist yet — not `schema_version: 1`."""
    for name in _on_disk():
        declared = yaml.safe_load((FIXTURES / name).read_text()).get("schema_version")
        expected = int(name[1])
        assert declared == (None if expected == 1 else expected), name


def test_every_version_before_the_current_one_is_represented() -> None:
    assert {name.split("/")[0] for name in _on_disk()} == {"v1", "v2", "v3", "v4", "v5"}
