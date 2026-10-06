"""The post-merge consumers ask the strategy, never compare a string (spec
2026-10-06-verification-strategies §B): the PR body's owed list, visual
evidence, `set-status --verify` and the record template hint.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import Matrix, Row, Visual
from fr.verification.rows import SpecVerification, spec_verification

SPEC = "docs/superpowers/specs/s.md"
SPEC_REF = f"super-fr:{SPEC}"


def _row(rid: str, *, verify: str | None = None, visual: bool = False) -> Row:
    return Row(
        id=rid,
        capability="c",
        acceptance=f"{rid} acceptance",
        origin=(f"{SPEC_REF}#R1",),
        status="not-implemented",
        verify=verify,
        visual=Visual(states=("s",)) if visual else None,
    )


def _spec(root: Path, section: str | None) -> SpecVerification:
    path = root / SPEC
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# S\n\n## Requirements\n\nR1.\n" + (section or ""))
    return spec_verification(root, SPEC, shape_default="candidate")


_SECTION = """
## Verification

strategy: candidate
- by-spec: live — needs the released build on a real forge
- ruled-out: none — unit tests cover it
"""


# --- PR body -------------------------------------------------------------------


def test_the_pr_body_lists_live_rows_with_their_reason_or_a_legacy_note(tmp_path: Path) -> None:
    from fr.record.pr_body import post_merge_owed_lines

    v = _spec(tmp_path, _SECTION)
    matrix = Matrix(
        rows=(
            _row("legacy", verify="live"),
            _row("by-spec"),
            _row("ruled-out"),
            _row("pre-merge"),
        )
    )

    lines = post_merge_owed_lines(matrix, SPEC_REF, v)

    assert lines == [
        "- `legacy` — legacy acceptance — no reason recorded (legacy)",
        "- `by-spec` — by-spec acceptance — needs the released build on a real forge",
    ]


def test_a_spec_with_no_section_lists_only_rows_whose_own_verify_is_post_merge(
    tmp_path: Path,
) -> None:
    from fr.record.pr_body import post_merge_owed_lines

    v = _spec(tmp_path, None)
    matrix = Matrix(rows=(_row("a", verify="live"), _row("b"), _row("c", verify="candidate")))

    assert [ln.split("`")[1] for ln in post_merge_owed_lines(matrix, SPEC_REF, v)] == ["a"]


def test_an_unresolvable_strategy_is_listed_not_hidden(tmp_path: Path) -> None:
    from fr.record.pr_body import post_merge_owed_lines

    v = _spec(tmp_path, None)
    (line,) = post_merge_owed_lines(Matrix(rows=(_row("x", verify="bogus"),)), SPEC_REF, v)
    assert "`x`" in line and "bogus" in line


# --- visual evidence -------------------------------------------------------------


def test_a_live_row_does_not_owe_visual_evidence(tmp_path: Path) -> None:
    from fr.run.visual import owed_rows

    v = _spec(tmp_path, _SECTION)
    matrix = Matrix(
        rows=(
            _row("legacy", verify="live", visual=True),
            _row("by-spec", visual=True),
            _row("owes", visual=True),
        )
    )

    rows = owed_rows(matrix, phase_rows=("legacy", "by-spec", "owes"), verification=v)

    assert [r.id for r in rows] == ["owes"]


# --- the template hint -----------------------------------------------------------


def test_the_template_hint_names_a_strategy_not_post_merge() -> None:
    import inspect

    from fr.record import template

    source = inspect.getsource(template)
    assert "verify: post-merge" not in source
    assert "verify: <strategy|none>" in source


# --- set-status --verify ----------------------------------------------------------


@pytest.fixture
def matrix_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from tests.unit.test_record_apply import _matrix_repo

    root = _matrix_repo(tmp_path)
    monkeypatch.chdir(root)
    return root


def _set_status(*args: str):
    from fr.cli import app
    from typer.testing import CliRunner

    return CliRunner().invoke(
        app,
        [
            "acceptance",
            "set-status",
            "--id",
            "target",
            "--status",
            "skipped",
            "--notes",
            "n",
            *args,
        ],
    )


def test_set_status_accepts_a_resolving_strategy(matrix_repo: Path) -> None:
    from fr.acceptance.model import load_matrix

    out = _set_status("--verify", "live")

    assert out.exit_code == 0, out.output
    matrix = load_matrix(matrix_repo / "docs" / "acceptance" / "matrix.yaml")
    assert next(r for r in matrix.rows if r.id == "target").verify == "live"


def test_set_status_accepts_none(matrix_repo: Path) -> None:
    assert _set_status("--verify", "none").exit_code == 0


def test_set_status_refuses_a_strategy_that_does_not_resolve(matrix_repo: Path) -> None:
    out = _set_status("--verify", "bogus")

    assert out.exit_code == 2
    assert "bogus" in out.output
