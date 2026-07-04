"""Phase 1 — fr.acceptance.model: ref grammar, archive twins, matrix load.

Pins spec traps 3 (ref fragments) and 5 (unknown level keys / bool-typed id)
from docs/superpowers/specs/2026-07-04-acceptance-matrix-design.md §4.
"""

from pathlib import Path

import pytest
from fr.acceptance.model import (
    LEVELS,
    AcceptanceError,
    archive_twin,
    load_matrix,
    split_ref,
)

# ── ref grammar (trap 3: fragments kept for URLs, split out for checks) ────


def test_split_ref_plain() -> None:
    assert split_ref("fr:docs/a.md") == ("fr", "docs/a.md", "")


def test_split_ref_line_fragment() -> None:
    assert split_ref("fr:pkg/x.py#L12") == ("fr", "pkg/x.py", "L12")


def test_split_ref_anchor_fragment() -> None:
    assert split_ref("fr:docs/spec.md#anchor") == ("fr", "docs/spec.md", "anchor")


@pytest.mark.parametrize("bad", ["no-colon", "repo/slash:path", "fr:"])
def test_split_ref_rejects_malformed(bad: str) -> None:
    with pytest.raises(AcceptanceError, match=r"<repo>:<path>"):
        split_ref(bad)


# ── archive twins (trap 1: specs move specs/ ↔ implemented/specs/) ─────────


def test_archive_twin_live_to_done() -> None:
    assert archive_twin("docs/superpowers/specs/x.md") == "docs/superpowers/implemented/specs/x.md"


def test_archive_twin_done_to_live() -> None:
    assert archive_twin("docs/superpowers/implemented/specs/x.md") == "docs/superpowers/specs/x.md"


def test_archive_twin_other_paths_have_none() -> None:
    assert archive_twin("scripts/x.sh") is None


# ── load_matrix ────────────────────────────────────────────────────────────

HEADER = "# header comment — must survive\nrows:\n"

ROW = """\
  - id: {id}
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["fr:docs/superpowers/specs/x.md"]
    levels:
      unit: ["fr:tests/unit/test_x.py"]
    status: {status}
    notes: "n"
"""


def _write_matrix(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "docs" / "acceptance" / "matrix.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(text)
    return p


def test_load_happy_row_defaults_missing_levels(tmp_path: Path) -> None:
    m = load_matrix(_write_matrix(tmp_path, HEADER + ROW.format(id="a", status="ci")))
    (row,) = m.rows
    assert row.id == "a"
    assert row.status == "ci"
    assert set(row.levels) == set(LEVELS)
    assert row.levels["unit"] == ("fr:tests/unit/test_x.py",)
    assert row.levels["api"] == ()


def test_load_row_without_levels_key(tmp_path: Path) -> None:
    """A row may omit `levels:` entirely — all four levels default to ()."""
    text = (
        HEADER
        + "\n".join(
            line
            for line in ROW.format(id="a", status="ci").splitlines()
            if "levels:" not in line and "unit:" not in line
        )
        + "\n"
    )
    m = load_matrix(_write_matrix(tmp_path, text))
    assert dict(m.rows[0].levels) == {lv: () for lv in LEVELS}


def test_load_preserves_row_order(tmp_path: Path) -> None:
    text = HEADER + ROW.format(id="b", status="ci") + ROW.format(id="a", status="ci")
    m = load_matrix(_write_matrix(tmp_path, text))
    assert [r.id for r in m.rows] == ["b", "a"]


def test_load_top_level_identity_keys(tmp_path: Path) -> None:
    text = "org: derio-net\nrepo: super-fr\n" + HEADER + ROW.format(id="a", status="ci")
    m = load_matrix(_write_matrix(tmp_path, text))
    assert (m.org, m.repo) == ("derio-net", "super-fr")


def test_load_identity_keys_default_none(tmp_path: Path) -> None:
    m = load_matrix(_write_matrix(tmp_path, HEADER + ROW.format(id="a", status="ci")))
    assert (m.org, m.repo) == (None, None)


def test_load_duplicate_ids_rejected(tmp_path: Path) -> None:
    text = HEADER + ROW.format(id="a", status="ci") + ROW.format(id="a", status="ci")
    with pytest.raises(AcceptanceError, match=r"duplicate.*a"):
        load_matrix(_write_matrix(tmp_path, text))


def test_load_bad_status_rejected(tmp_path: Path) -> None:
    with pytest.raises(AcceptanceError, match="sheduled"):
        load_matrix(_write_matrix(tmp_path, HEADER + ROW.format(id="a", status="sheduled")))


def test_load_unknown_level_key_rejected(tmp_path: Path) -> None:
    """Trap 5: a typo'd level key must not silently drop refs."""
    text = HEADER + ROW.format(id="a", status="ci").replace("unit:", "unti:")
    with pytest.raises(AcceptanceError, match=r"unti"):
        load_matrix(_write_matrix(tmp_path, text))


def test_load_bool_id_rejected(tmp_path: Path) -> None:
    """Trap 5 class: YAML `yes` parses as bool — ids must be strings."""
    with pytest.raises(AcceptanceError, match="id"):
        load_matrix(_write_matrix(tmp_path, HEADER + ROW.format(id="yes", status="ci")))


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AcceptanceError, match="matrix"):
        load_matrix(tmp_path / "nope.yaml")
