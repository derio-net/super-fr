"""The acceptance fragment model (spec 2026-11-04-repo-feature-settings R16, §3.D).

A fragment is `docs/acceptance/features/<spec-slug>.yaml`: the rows a feature
created, plus the amendments it makes to rows other features own.
"""

from __future__ import annotations

import pytest
from fr.acceptance.fragment import (
    AMENDMENT_OPS,
    FRAGMENTS_DIR,
    Fragment,
    fragment_slug_for_spec,
    parse_fragment,
)
from fr.acceptance.model import AcceptanceError, Row

SRC = f"{FRAGMENTS_DIR}/2026-11-04-widget.yaml"

ROW = """\
  - id: widget-spins
    capability: widget
    acceptance: The widget spins.
    origin: [spec:2026-11-04-widget#R1]
    status: ci
"""


def _text(*, rows: str = ROW, amendments: str | None = "amendments: []\n", head: str = "") -> str:
    out = "schema_version: 1\nfeature: 2026-11-04-widget\nrepo: derio-net/super-fr\n" + head
    out += "rows:\n" + rows if rows else ""
    if amendments is not None:
        out += amendments
    return out


def _amend(body: str) -> str:
    return "amendments:\n  - {row: other-row, base: 0, why: because, " + body + "}\n"


def test_a_fragment_with_rows_and_no_amendments_parses() -> None:
    frag = parse_fragment(_text(), source=SRC)
    assert isinstance(frag, Fragment)
    assert frag.feature == "2026-11-04-widget"
    assert frag.repo == "derio-net/super-fr"
    assert frag.schema_version == 1
    assert [r.id for r in frag.rows] == ["widget-spins"]
    assert isinstance(frag.rows[0], Row), "the fragment reuses the matrix's one row model"
    assert frag.amendments == ()


def test_absent_amendments_read_as_empty() -> None:
    assert parse_fragment(_text(amendments=None), source=SRC).amendments == ()


def test_every_op_parses_with_its_own_fields() -> None:
    text = _text(
        amendments=(
            "amendments:\n"
            "  - {row: r1, op: reword, base: 0, why: w, acceptance: New words.}\n"
            "  - {row: r1, op: reword, base: 1, why: w, capability: other}\n"
            "  - {row: r1, op: set-status, base: 2, why: w, status: unwired, notes: n,"
            " issues: [derio-net/super-fr#1]}\n"
            "  - {row: r1, op: add-level, base: 3, why: w, level: unit,"
            " ref: 'super-fr:tests/unit/test_x.py#test_y'}\n"
            "  - {row: r1, op: drop-level, base: 4, why: w, level: unit,"
            " ref: 'super-fr:tests/unit/test_x.py#test_y'}\n"
            "  - {row: r1, op: retire, base: 5, why: w, notes: gone}\n"
        )
    )
    frag = parse_fragment(text, source=SRC)
    assert [a.op for a in frag.amendments] == [
        "reword",
        "reword",
        "set-status",
        "add-level",
        "drop-level",
        "retire",
    ]
    assert set(AMENDMENT_OPS) == {a.op for a in frag.amendments}


def test_set_status_takes_an_optional_walk() -> None:
    text = _text(
        amendments=(
            "amendments:\n"
            "  - row: r1\n    op: set-status\n    base: 0\n    why: walked it\n"
            "    status: walked\n    notes: n\n"
            "    walk: {strategy: live, harness: claude-code, model: m, outcome: pass,"
            " at: '2026-11-12T00:00:00', evidence: log}\n"
        )
    )
    (amendment,) = parse_fragment(text, source=SRC).amendments
    assert amendment.walk is not None and amendment.walk.outcome == "pass"


@pytest.mark.parametrize(
    ("text", "names"),
    [
        (_text(head="color: blue\n"), "color"),
        (_text(amendments=_amend("op: bend")), "bend"),
        (_text(amendments=_amend("op: retire, notes: n, acceptance: x")), "acceptance"),
        (_text(amendments=_amend("op: set-status, status: ci, notes: n, level: unit")), "level"),
        (_text(amendments=_amend("op: add-level, level: unit, ref: 'r:x', notes: n")), "notes"),
        (
            _text(amendments=_amend("op: retire, notes: n").replace("base: 0", "base: -1")),
            "base",
        ),
        (_text(amendments=_amend("op: retire, notes: n").replace(", why: because", "")), "why"),
        (
            _text(amendments=_amend("op: retire, notes: n").replace("why: because", "why: ''")),
            "why",
        ),
        (_text(rows=ROW + ROW), "widget-spins"),
        (_text().replace("feature: 2026-11-04-widget", "feature: 2026-11-04-gadget"), "feature"),
        (_text().replace("repo: derio-net/super-fr", "repo: super-fr"), "repo"),
        (_text(amendments=_amend("op: reword")), "reword"),
    ],
)
def test_refusals_name_the_file_and_the_key(text: str, names: str) -> None:
    with pytest.raises(AcceptanceError) as e:
        parse_fragment(text, source=SRC)
    message = str(e.value)
    assert "2026-11-04-widget.yaml" in message, message
    assert names in message, message


def test_the_legacy_fragment_is_named_legacy() -> None:
    text = _text().replace("feature: 2026-11-04-widget", "feature: legacy")
    assert parse_fragment(text, source=f"{FRAGMENTS_DIR}/legacy.yaml").feature == "legacy"
    with pytest.raises(AcceptanceError, match="feature"):
        parse_fragment(_text(), source=f"{FRAGMENTS_DIR}/legacy.yaml")


def test_a_bare_rows_key_is_empty() -> None:
    frag = parse_fragment(_text(rows="").replace("amendments: []\n", "rows:\n"), source=SRC)
    assert frag.rows == ()


def test_parses_are_independent_copies() -> None:
    a = parse_fragment(_text(), source=SRC)
    b = parse_fragment(_text(), source=SRC)
    assert a == b and a is not b
    a.rows[0].levels["unit"] = ("mutated",)  # type: ignore[index]
    assert b.rows[0].levels["unit"] == ()


@pytest.mark.parametrize(
    "path",
    [
        "docs/superpowers/specs/2026-11-04-repo-feature-settings-design.md",
        "docs/superpowers/implemented/specs/2026-11-04-repo-feature-settings-design.md",
        "docs/superpowers/specs/2026-11-04-repo-feature-settings.md",
    ],
)
def test_the_fragment_slug_of_a_spec_is_its_stem_without_design(path: str) -> None:
    assert fragment_slug_for_spec(path) == "2026-11-04-repo-feature-settings"
