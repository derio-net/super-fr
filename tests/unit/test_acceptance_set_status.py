"""Phase 7 (spec §3.G.2) — `fr acceptance set-status`.

The matrix is a registry of CURRENT state, not a log, so this verb mutates the
row in place and regenerates the committed report set. The asymmetry with
`fr journal resolve` (append-only) is deliberate: `fr acceptance check` and
every report read today's status, and provenance lives in git history.

What the tests pin: the status moves, the reason lands, the reports stay in
sync without a separate `report` call, an unknown id or status creates NOTHING,
and no other row in the file is disturbed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()

TWO_ROWS = row(id="first", status="ci") + row(id="target", status="not-implemented")


def _invoke(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", *args])


def _matrix(root: Path) -> Path:
    return root / "docs" / "acceptance" / "matrix.yaml"


def _row(root: Path, row_id: str):
    from fr.acceptance.model import load_matrix

    return next(r for r in load_matrix(_matrix(root)).rows if r.id == row_id)


def test_set_status_moves_the_row_in_place(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, TWO_ROWS)
    result = _invoke(
        root,
        monkeypatch,
        "set-status",
        "--id",
        "target",
        "--status",
        "ci",
        "--notes",
        "pinned by tests/test_a.py",
    )
    assert result.exit_code == 0, result.output
    assert _row(root, "target").status == "ci"
    assert "target" in result.output


def test_set_status_records_the_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A status that moved for no recorded reason is the silent change
    `.claude/rules/acceptance-matrix.md` forbids."""
    root = make_repo(tmp_path, TWO_ROWS)
    result = _invoke(
        root,
        monkeypatch,
        "set-status",
        "--id",
        "target",
        "--status",
        "skipped",
        "--notes",
        "walked live once, CI backfill owed",
    )
    assert result.exit_code == 0, result.output
    assert _row(root, "target").notes == "walked live once, CI backfill owed"


def test_set_status_requires_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, TWO_ROWS)
    before = _matrix(root).read_text()
    result = _invoke(root, monkeypatch, "set-status", "--id", "target", "--status", "ci")
    assert result.exit_code == 2
    assert _matrix(root).read_text() == before


def test_set_status_keeps_the_reports_in_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`check` gates report drift, so a flip that did not regenerate the set
    would turn the next check red — the hand-edit trap, one layer on."""
    root = make_repo(tmp_path, TWO_ROWS)
    result = _invoke(
        root, monkeypatch, "set-status", "--id", "target", "--status", "ci", "--notes", "why"
    )
    assert result.exit_code == 0, result.output
    d = root / "docs" / "acceptance"
    for name in ("report_local.html", "report_linked.html", "report_linked.md"):
        assert (d / name).exists(), f"set-status must regenerate {name}"
    check = _invoke(root, monkeypatch, "check")
    assert check.exit_code == 0, check.output


def test_set_status_refreshes_reports_that_already_existed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, TWO_ROWS)
    assert _invoke(root, monkeypatch, "report", "--deterministic").exit_code == 0
    stale = (root / "docs" / "acceptance" / "report_linked.md").read_text()
    assert "not-implemented" in stale
    result = _invoke(
        root, monkeypatch, "set-status", "--id", "target", "--status", "ci", "--notes", "why"
    )
    assert result.exit_code == 0, result.output
    fresh = (root / "docs" / "acceptance" / "report_linked.md").read_text()
    assert fresh != stale
    assert _invoke(root, monkeypatch, "report", "--check").exit_code == 0


def test_unknown_id_creates_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Silently creating a row on a typo'd id is how a row gets orphaned; that
    is `add`'s job, and this verb refuses."""
    root = make_repo(tmp_path, TWO_ROWS)
    before = _matrix(root).read_text()
    result = _invoke(
        root, monkeypatch, "set-status", "--id", "targett", "--status", "ci", "--notes", "why"
    )
    assert result.exit_code != 0
    assert "targett" in result.output
    assert _matrix(root).read_text() == before
    from fr.acceptance.model import load_matrix

    assert [r.id for r in load_matrix(_matrix(root)).rows] == ["first", "target"]


def test_unknown_status_is_refused_with_the_valid_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, TWO_ROWS)
    before = _matrix(root).read_text()
    result = _invoke(
        root, monkeypatch, "set-status", "--id", "target", "--status", "sheduled", "--notes", "why"
    )
    assert result.exit_code != 0
    for valid in ("ci", "scheduled", "skipped", "not-implemented", "failing"):
        assert valid in result.output
    assert _matrix(root).read_text() == before


def test_no_other_row_is_touched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Byte-stability outside the edited row: the header comments and every
    other row survive verbatim, so a flip is reviewable as a one-row diff."""
    root = make_repo(tmp_path, TWO_ROWS)
    marker = "  - id: target"
    before = _matrix(root).read_text()
    head, _, rest = before.partition(marker)
    result = _invoke(
        root, monkeypatch, "set-status", "--id", "target", "--status", "ci", "--notes", "why"
    )
    assert result.exit_code == 0, result.output
    after = _matrix(root).read_text()
    assert after.startswith(head), "everything above the edited row must be byte-identical"
    # `target` is the last row, so the remainder IS its block: the only change.
    tail_after = after[len(head) :]
    assert tail_after.startswith(marker)
    assert tail_after != marker + rest
    assert "not-implemented" not in tail_after
    assert "status: ci" in tail_after


def test_the_edited_row_keeps_its_other_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, TWO_ROWS)
    before = _row(root, "target")
    _invoke(root, monkeypatch, "set-status", "--id", "target", "--status", "ci", "--notes", "why")
    after = _row(root, "target")
    assert after.capability == before.capability
    assert after.acceptance == before.acceptance
    assert after.origin == before.origin
    assert after.levels == before.levels


def test_set_status_can_add_level_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`.claude/rules/acceptance-matrix.md` describes ONE transition: add the
    ref to `levels`, move `status` up. Splitting it would leave the evidence
    half of it to the hand-edit this verb exists to end."""
    root = make_repo(tmp_path, row(id="target", status="not-implemented", unit=""))
    result = _invoke(
        root,
        monkeypatch,
        "set-status",
        "--id",
        "target",
        "--status",
        "ci",
        "--notes",
        "now pinned",
        "--level",
        "unit=own:tests/test_a.py",
    )
    assert result.exit_code == 0, result.output
    target = _row(root, "target")
    assert target.levels["unit"] == ("own:tests/test_a.py",)
    assert target.status == "ci"


def test_set_status_does_not_duplicate_an_existing_level_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="target", status="skipped"))
    result = _invoke(
        root,
        monkeypatch,
        "set-status",
        "--id",
        "target",
        "--status",
        "ci",
        "--notes",
        "n",
        "--level",
        "unit=own:tests/test_a.py",
    )
    assert result.exit_code == 0, result.output
    assert _row(root, "target").levels["unit"] == ("own:tests/test_a.py",)


def test_set_status_rejects_a_malformed_level_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, TWO_ROWS)
    before = _matrix(root).read_text()
    result = _invoke(
        root,
        monkeypatch,
        "set-status",
        "--id",
        "target",
        "--status",
        "ci",
        "--notes",
        "n",
        "--level",
        "unit=no-colon-ref",
    )
    assert result.exit_code == 2
    assert _matrix(root).read_text() == before


# --- Review r7-i1: `_row_span`'s load-bearing invariant, pinned. -------------
#
# `edit.py` locates a row by PARSING each list item and comparing its `id`,
# never by pattern-matching an `id:` line — and says so, because a row whose
# `notes` quote another row's id would otherwise hijack the span. That is
# silent data corruption in the registry this PR exists to keep honest, and
# until now the fixtures were two trivial rows that could not have caught it.

_HOSTILE = """\
  - id: alpha
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["own:docs/superpowers/specs/s.md"]
    levels:
      unit: ["own:tests/test_a.py"]
    status: ci
    notes: |-
      Supersedes the work tracked under beta. A reviewer reading
      docs/acceptance/matrix.yaml will see a block that looks like a row:
        - id: beta
          status: not-implemented
      but it is prose inside this row's notes, not a row.
  - id: beta
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["own:docs/superpowers/specs/s.md"]
    levels:
      unit: ["own:tests/test_a.py"]
    status: not-implemented
    notes: "n"
"""


def test_a_row_id_quoted_inside_another_rows_notes_does_not_hijack_the_span(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`alpha`'s notes contain a literal `- id: beta` at deeper indent. Flipping
    `beta` must edit `beta`, leaving `alpha` byte-identical."""
    root = make_repo(tmp_path, _HOSTILE)
    matrix = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix.read_text()

    result = _invoke(
        root, monkeypatch, "set-status", "--id", "beta", "--status", "ci", "--notes", "moved"
    )
    assert result.exit_code == 0, result.output

    after = matrix.read_text()
    loaded = {r["id"]: r for r in yaml.safe_load(after)["rows"]}
    assert loaded["beta"]["status"] == "ci"
    assert loaded["alpha"]["status"] == "ci"
    # The decoy text survives untouched — the span never crossed into `alpha`.
    assert "- id: beta\n          status: not-implemented" in after
    assert before.split("  - id: beta\n")[0] == after.split("  - id: beta\n")[0]


_PREFIX_PAIR = row(id="foo", status="ci") + row(id="foo-2", status="not-implemented")


def test_an_id_that_is_a_prefix_of_another_edits_only_the_exact_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`foo` is a prefix of `foo-2`. Real ids in this repo have this shape
    (`acceptance-nag-channels` beside `acceptance-nag-*`), so a substring match
    would silently edit the wrong row — or both."""
    root = make_repo(tmp_path, _PREFIX_PAIR)
    matrix = root / "docs" / "acceptance" / "matrix.yaml"

    result = _invoke(
        root, monkeypatch, "set-status", "--id", "foo-2", "--status", "ci", "--notes", "moved"
    )
    assert result.exit_code == 0, result.output

    loaded = {r["id"]: r for r in yaml.safe_load(matrix.read_text())["rows"]}
    assert loaded["foo-2"]["status"] == "ci"
    assert loaded["foo"]["status"] == "ci"
    assert loaded["foo"]["notes"] == "n", "the prefix row's notes were rewritten"
