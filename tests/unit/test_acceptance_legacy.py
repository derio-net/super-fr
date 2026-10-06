"""The frozen v1–v3 matrix reader (spec 2026-10-06-verification-strategies §B).

The 3 -> 4 hop rewrites `verify: post-merge` to `verify: live` and the live
`Row` stops accepting the old spelling, so per
`.claude/rules/artifact-versioning.md` every matrix hop reads through
`fr.acceptance.legacy.MatrixV3` — never the live model.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from fr.acceptance import legacy
from fr.artifacts.matrix_verify import UnreadableMatrixError, guard_matrix

_ROW = """\
  - id: a
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["widget:docs/x.md"]
    levels:
      unit: ["widget:tests/test_x.py"]
    status: ci
    notes: "n"
"""

_V1 = "org: acme\nrepo: widget\nrows:\n" + _ROW
_V2 = "schema_version: 2\norg: acme\nrepo: widget\nrows:\n" + _ROW + "    verify: post-merge\n"
_V3 = (
    "schema_version: 3\norg: acme\nrepo: widget\nrows:\n"
    + _ROW
    + "    verify: post-merge\n    visual:\n      states: [empty]\n"
)


@pytest.mark.parametrize(("text", "version"), [(_V1, 1), (_V2, 2), (_V3, 3)])
def test_the_frozen_reader_reads_every_older_version(text: str, version: int) -> None:
    m = legacy.parse_matrix_v3(text)
    assert m.schema_version == version
    assert [r.id for r in m.rows] == ["a"]


def test_the_frozen_reader_reads_the_old_verify_spelling() -> None:
    assert legacy.parse_matrix_v3(_V2).rows[0].verify == "post-merge"


def test_the_frozen_reader_refuses_a_v4_only_field_and_duplicates() -> None:
    with pytest.raises(legacy.MatrixV3Error):
        legacy.parse_matrix_v3(_V3 + "    scenario: tests/s.sh\n")
    with pytest.raises(legacy.MatrixV3Error, match="duplicate"):
        legacy.parse_matrix_v3(_V1 + _ROW)


def test_the_frozen_matrix_reader_has_not_been_edited() -> None:
    frozen = {
        name for name, obj in vars(legacy).items() if inspect.isclass(obj) and name.endswith("V3")
    }
    assert frozen == set(legacy.FROZEN_CLASS_SHA256)
    drifted = {
        name
        for name in frozen
        if hashlib.sha256(inspect.getsource(getattr(legacy, name)).encode()).hexdigest()
        != legacy.FROZEN_CLASS_SHA256[name]
    }
    assert not drifted, f"{sorted(drifted)} changed; freeze a `…V4` beside them instead"


def test_guard_matrix_reads_through_the_frozen_model_not_the_live_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every hop's guard must accept an old body the LIVE model refuses."""
    import fr.acceptance.model as live

    def _refuse(_text: str) -> object:
        raise live.AcceptanceError("live model refuses this body")

    monkeypatch.setattr(live, "parse_matrix", _refuse)
    path = tmp_path / "matrix.yaml"
    path.write_text(_V2)
    guard_matrix(path)  # no raise


def test_guard_matrix_still_refuses_an_unreadable_matrix(tmp_path: Path) -> None:
    path = tmp_path / "matrix.yaml"
    path.write_text(_V2.replace("status: ci", "status: sheduled"))
    with pytest.raises(UnreadableMatrixError):
        guard_matrix(path)
