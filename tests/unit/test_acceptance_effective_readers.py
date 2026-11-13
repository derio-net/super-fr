"""Every reader of acceptance rows reads the effective matrix — the fold over the
fragments — and none needs `docs/acceptance/matrix.yaml` (spec
2026-11-04-repo-feature-settings R17, R19).

Each test builds a repo holding fragments and NO matrix, and asks one reader
family for the rows; the rows cite their spec logically (`spec:<slug>#R<n>`, R18).
The PR-body, visual, close-out, gate-backfill and verification-exit readers keep
their own behaviour tests (`test_pr_body_*`, `test_record_visual`,
`test_closeout_*`, `test_gatebackfill_*`, `test_verification_*`), which write
their rows through the same `write_fragments` helper.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.fold import clear_fold_cache, fold, has_fragments, load_effective
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import FRAGMENTS_REL, write_fragments

runner = CliRunner()
SLUG = "2026-01-01-widget"
LIVE = f"docs/superpowers/specs/{SLUG}-design.md"
ARCHIVED = f"docs/superpowers/implemented/specs/{SLUG}-design.md"

ROWS = [
    {
        "id": "w-built",
        "capability": "Widget",
        "acceptance": "The widget is built",
        "origin": [f"spec:{SLUG}#R1"],
        "levels": {"unit": ["widget:tests/test_w.py#test_w"]},
        "status": "ci",
        "notes": "n",
    },
    {
        "id": "w-owed",
        "capability": "Widget",
        "acceptance": "The widget is walked",
        "origin": [f"spec:{SLUG}#R2"],
        "status": "not-implemented",
        "notes": "owed",
    },
]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)


def _repo(tmp_path: Path, *, archived: bool = False) -> Path:
    root = tmp_path / "widget"
    spec = root / (ARCHIVED if archived else LIVE)
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "# Widget\n\n## Requirements\n\nR1. Built.\nR2. Walked.\n\n## Test Plan\n\n1. x\n"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_w.py").write_text("def test_w():\n    pass\n")
    write_fragments(root, ROWS, repo="acme/widget")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    clear_fold_cache()
    assert not (root / "docs" / "acceptance" / "matrix.yaml").exists()
    return root


def _cli(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", *args])


def test_load_effective_folds_the_fragments(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    matrix = load_effective(root)

    assert [r.id for r in matrix.rows] == ["w-built", "w-owed"]
    assert (matrix.org, matrix.repo) == ("acme", "widget")
    assert has_fragments(root)


def test_load_effective_outside_a_work_tree_folds_in_memory(tmp_path: Path) -> None:
    root = tmp_path / "bare"
    write_fragments(root, ROWS, repo="acme/widget")

    assert [r.id for r in load_effective(root).rows] == ["w-built", "w-owed"]


def test_no_fragment_is_an_empty_matrix(tmp_path: Path) -> None:
    (tmp_path / FRAGMENTS_REL).mkdir(parents=True)
    assert not has_fragments(tmp_path)
    assert load_effective(tmp_path).rows == ()


def test_acceptance_check_status_summary_and_digest_read_the_fragments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)

    check = _cli(root, monkeypatch, "check")
    assert check.exit_code == 0, check.output
    assert "2 rows OK" in check.output
    status = _cli(root, monkeypatch, "status")
    assert "w-owed [not-implemented]" in status.output
    assert "ci: 1" in status.output
    summary = _cli(root, monkeypatch, "summary")
    assert "| not-implemented | 1 |" in summary.output
    digest = _cli(root, monkeypatch, "digest")
    assert "w-owed" in digest.output


def test_check_reports_a_logical_origin_that_does_not_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    write_fragments(
        root,
        [{**ROWS[0], "id": "ghost", "origin": ["spec:2026-01-09-ghost#R1"]}],
        repo="acme/widget",
        feature="2026-01-09-ghost",
    )

    check = _cli(root, monkeypatch, "check")

    assert check.exit_code == 1
    assert "no spec '2026-01-09-ghost'" in check.output


def test_the_staleness_guard_counts_a_logical_citation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Test-Plan spec cited only by `spec:<slug>` is cited, live or archived."""
    for archived in (False, True):
        root = _repo(tmp_path / str(archived), archived=archived)
        check = _cli(root, monkeypatch, "check")
        assert "staleness" not in check.output, check.output


def test_debt_reads_the_fragments(tmp_path: Path) -> None:
    from fr.debt.engine import acceptance_debt

    debt, matrix, source = acceptance_debt(_repo(tmp_path))

    assert source.state == "read"
    assert matrix is not None and len(matrix.rows) == 2
    assert [r.id for r in debt.rows] == ["w-owed"]


def test_fr_status_reads_the_fragments(tmp_path: Path) -> None:
    from fr.commands.status_cmd import _acceptance_section

    section = _acceptance_section(_repo(tmp_path))

    assert section is not None and "1 open" in section


def test_triage_snapshot_rows_read_the_fragments(tmp_path: Path) -> None:
    from fr.triage.snapshot import acceptance_rows

    assert acceptance_rows(_repo(tmp_path)) == {"w-built": "ci", "w-owed": "not-implemented"}
    assert acceptance_rows(tmp_path / "nothing") is None


def test_rows_citing_matches_a_logical_origin_live_and_archived(tmp_path: Path) -> None:
    from fr.requirements import is_cited, load_spec_matrix, rows_citing

    for archived, rel in ((False, LIVE), (True, ARCHIVED)):
        root = _repo(tmp_path / str(archived), archived=archived)
        matrix, spec_ref = load_spec_matrix(root, rel)
        assert spec_ref == f"widget:{rel}"
        assert [r.id for r in rows_citing(matrix, spec_ref)] == ["w-built", "w-owed"]
        assert is_cited("R2", matrix, spec_ref)
        assert not is_cited("R3", matrix, spec_ref)
        # its twin path names the same spec
        twin = ARCHIVED if rel == LIVE else LIVE
        assert len(rows_citing(matrix, f"widget:{twin}")) == 2


def test_proportionality_folds_at_head(tmp_path: Path) -> None:
    """`fr plan proportionality` reads the rows committed at HEAD only."""
    root = _repo(tmp_path)
    write_fragments(root, [{**ROWS[0], "id": "uncommitted"}], repo="acme/widget", feature="x")

    at_head = fold(root, ref="HEAD", include_pending=False).matrix

    assert [r.id for r in at_head.rows] == ["w-built", "w-owed"]


def test_plan_self_review_links_rows_from_the_fragments(tmp_path: Path) -> None:
    from fr.parser import parse as parse_plan
    from fr.plan_ops import self_review

    from tests.unit.test_plan_acceptance_links import _create_plan, _spec
    from tests.unit.test_plan_acceptance_links import _repo as plan_repo

    def review(where: Path, row_id: str) -> list:
        where.mkdir()
        root = plan_repo(where, matrix=False)
        _spec(root)
        write_fragments(
            root,
            [{**ROWS[1], "id": "row-a", "origin": []}],
            repo="derio-net/own",
            feature="legacy",
        )
        return self_review(parse_plan(_create_plan(root, acceptance=(row_id,))))

    ok = review(tmp_path / "ok", "row-a")
    assert not [i for i in ok if "acceptance" in i.message and i.severity == "error"]
    bad = review(tmp_path / "bad", "row-zzz")
    assert any("unknown acceptance row id 'row-zzz'" in i.message for i in bad)
