"""The `visual` acceptance-row field (spec `2026-09-28-ui-visual-evidence-design.md`
§A/§B): a UI requirement is identified structurally by its acceptance row,
which names the states and interactions visual evidence must cover.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.acceptance.model import AcceptanceError, load_matrix
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

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


# ── P1.T1: round-trip ───────────────────────────────────────────────────────


def test_row_visual_round_trips(tmp_path: Path) -> None:
    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: [a]\n      interactions: ['20 cap']\n"
    )
    (row,) = load_matrix(_write_matrix(tmp_path, text)).rows
    assert row.visual is not None
    assert row.visual.states == ("a",)
    assert row.visual.interactions == ("20 cap",)


def test_row_visual_defaults_to_none(tmp_path: Path) -> None:
    (row,) = load_matrix(_write_matrix(tmp_path, HEADER + ROW.format(id="a", status="ci"))).rows
    assert row.visual is None


# ── P1.T2: validation ───────────────────────────────────────────────────────


def test_visual_both_lists_empty_is_refused(tmp_path: Path) -> None:
    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: []\n      interactions: []\n"
    )
    with pytest.raises(AcceptanceError, match="states|interactions"):
        load_matrix(_write_matrix(tmp_path, text))


def test_visual_one_empty_list_is_accepted(tmp_path: Path) -> None:
    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: [a]\n      interactions: []\n"
    )
    (row,) = load_matrix(_write_matrix(tmp_path, text)).rows
    assert row.visual is not None
    assert row.visual.states == ("a",)
    assert row.visual.interactions == ()


def test_visual_duplicate_name_within_a_list_is_refused(tmp_path: Path) -> None:
    text = HEADER + ROW.format(id="a", status="ci") + "    visual:\n      states: [a, a]\n"
    with pytest.raises(AcceptanceError, match="a"):
        load_matrix(_write_matrix(tmp_path, text))


def test_visual_duplicate_name_across_lists_is_refused(tmp_path: Path) -> None:
    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: [a]\n      interactions: [a]\n"
    )
    with pytest.raises(AcceptanceError, match="a"):
        load_matrix(_write_matrix(tmp_path, text))


def test_a_row_with_visual_dumped_and_reparsed_is_identical(tmp_path: Path) -> None:
    from fr.acceptance.model import parse_matrix

    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: [a, b]\n      interactions: ['20 cap']\n"
    )
    matrix = load_matrix(_write_matrix(tmp_path, text))
    dumped = yaml.safe_dump(matrix.model_dump(mode="json"), sort_keys=False)
    reparsed = parse_matrix(dumped)
    assert reparsed == matrix


# ── P1.T2: CLI — `fr acceptance add --visual-state / --visual-interaction` ─

cli_runner = CliRunner()

ADD_ARGS = [
    "add",
    "--id",
    "new-row",
    "--capability",
    "Caps",
    "--acceptance",
    "Operator can add rows",
    "--origin",
    "own:docs/superpowers/specs/s.md",
    "--level",
    "unit=own:tests/test_a.py",
    "--status",
    "not-implemented",
    "--notes",
    "born in a test",
]


def _invoke(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return cli_runner.invoke(app, ["acceptance", *args])


def test_add_visual_state_and_interaction_writes_the_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.acceptance.model import load_matrix

    root = make_repo(tmp_path, row())
    result = _invoke(
        root,
        monkeypatch,
        *ADD_ARGS,
        "--visual-state",
        "a",
        "--visual-interaction",
        "20 cap",
    )
    assert result.exit_code == 0, result.output
    (added,) = [
        r for r in load_matrix(root / "docs" / "acceptance" / "matrix.yaml").rows
        if r.id == "new-row"
    ]
    assert added.visual is not None
    assert added.visual.states == ("a",)
    assert added.visual.interactions == ("20 cap",)


def test_add_visual_state_repeatable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.acceptance.model import load_matrix

    root = make_repo(tmp_path, row())
    result = _invoke(
        root,
        monkeypatch,
        *ADD_ARGS,
        "--visual-state",
        "a",
        "--visual-state",
        "b",
    )
    assert result.exit_code == 0, result.output
    (added,) = [
        r for r in load_matrix(root / "docs" / "acceptance" / "matrix.yaml").rows
        if r.id == "new-row"
    ]
    assert added.visual is not None
    assert added.visual.states == ("a", "b")


def test_add_without_visual_writes_no_visual_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row())
    assert _invoke(root, monkeypatch, *ADD_ARGS).exit_code == 0
    assert "visual" not in (root / "docs" / "acceptance" / "matrix.yaml").read_text()


def test_add_visual_refuses_a_name_duplicated_across_state_and_interaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row())
    before = (root / "docs" / "acceptance" / "matrix.yaml").read_text()
    result = _invoke(
        root,
        monkeypatch,
        *ADD_ARGS,
        "--visual-state",
        "a",
        "--visual-interaction",
        "a",
    )
    assert result.exit_code == 2, result.output
    assert (root / "docs" / "acceptance" / "matrix.yaml").read_text() == before


def test_set_status_preserves_visual(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.acceptance.model import load_matrix

    root = make_repo(tmp_path, row())
    assert (
        _invoke(root, monkeypatch, *ADD_ARGS, "--visual-state", "a").exit_code == 0
    )
    moved = _invoke(
        root,
        monkeypatch,
        "set-status",
        "--id",
        "new-row",
        "--status",
        "skipped",
        "--notes",
        "verified live once",
    )
    assert moved.exit_code == 0, moved.output
    (row_after,) = [
        r for r in load_matrix(root / "docs" / "acceptance" / "matrix.yaml").rows
        if r.id == "new-row"
    ]
    assert row_after.visual is not None
    assert row_after.visual.states == ("a",)
