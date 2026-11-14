"""The debt surfaces count and list `local` (spec 2026-11-14-acceptance-local-status R1,
R3, R5, §B): a fresh `local` row is listed with its stamp date, never debt; a stale,
unstamped or promote-to-ci one is debt, shown with its reason."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fr.acceptance.model import LocalStamp, Matrix, Row

from tests.unit.test_acceptance_local_writers import _fr
from tests.unit.test_acceptance_local_writers import no_ci as no_ci  # noqa: F401  (fixture)
from tests.unit.test_acceptance_local_writers import repo as repo  # noqa: F401  (fixture)
from tests.unit.test_record_apply import commit_all, git

STAMP = LocalStamp(at="2026-11-14", tree="a" * 40, log="suite.log@0123456789ab", files={"tests/test_a.py": "b" * 40})


def _matrix() -> Matrix:
    rows = (
        Row(id="fresh", capability="c", acceptance="a", status="local", local=STAMP),
        Row(id="stale", capability="c", acceptance="a", status="local", local=STAMP),
        Row(id="owed", capability="c", acceptance="a", status="unwired"),
        Row(id="done", capability="c", acceptance="a", status="ci"),
    )
    return Matrix(org="o", repo="r", rows=rows)


LOCAL = {"stale": "stale: tests/test_a.py"}


def test_open_rows_counts_a_local_reason_as_debt() -> None:
    from fr.acceptance.check import open_rows

    ids = [r.id for r in open_rows(_matrix(), local=LOCAL)]
    assert sorted(ids) == ["owed", "stale"]


def test_status_tag_shows_the_local_reason() -> None:
    from fr.debt.render import status_tag

    assert status_tag("local", local="stale: x.py") == "local, stale: x.py"
    assert status_tag("local") == "local"


def test_the_debt_section_lists_local_rows_and_counts_their_debt() -> None:
    from fr.debt.engine import acceptance_from_matrix

    acc = acceptance_from_matrix(_matrix(), local=LOCAL)
    rows = {r.id: r for r in acc.rows}
    assert rows["fresh"].local_at == "2026-11-14" and not rows["fresh"].is_debt
    assert rows["stale"].local_debt == "stale: tests/test_a.py" and rows["stale"].is_debt
    assert acc.local_debt == 1
    assert acc.debt_count() == 2  # owed (unwired) + stale


def test_the_digest_section_shows_the_local_reason() -> None:
    from fr.debt.engine import acceptance_from_matrix
    from fr.debt.render import acceptance_section

    acc = acceptance_from_matrix(_matrix(), local=LOCAL)
    section = acceptance_section(acc)
    assert "local, stale: tests/test_a.py" in section
    assert "fresh" not in section  # listed, not debt: the digest lists only debt


def test_the_figures_carry_local_debt_through_parse_figures() -> None:
    from fr.debt.engine import acceptance_from_matrix
    from fr.debt.model import DebtReport
    from fr.debt.render import _encode, figures, parse_figures

    acc = acceptance_from_matrix(_matrix(), local=LOCAL)
    report = DebtReport(acceptance=acc, generated_at="2026-11-14T00:00:00+00:00")
    fig = figures(report)
    assert fig["acceptance_local_debt"] == 1
    assert parse_figures(f"body\n{_encode(report)}") == fig


def test_the_board_counts_local_debt() -> None:
    from fr.triage.render import render

    from tests.unit.triage_board_fixtures import facts, judgements
    from tests.unit.triage_debt_fixtures import digest, figures

    fig = figures(acceptance={"ci": 4, "local": 3}, acceptance_local_debt=2)
    page = render(facts([digest(1, fig)]), judgements({}), None)
    sect = page[page.index('id="debt"') :]
    assert "local debt 2" in sect
    assert "local 3" in sect  # listed beside walked and manual


def test_the_report_shows_local_with_its_date_or_reason(tmp_path: Path) -> None:
    from fr.acceptance.report import LinkBuilder, render, render_markdown

    links = LinkBuilder(
        mode="local", ref="main", root=tmp_path, out_dir=tmp_path, sibling_root="..",
        org="o", own_repo="r", probe=False,
    )  # fmt: skip
    for renderer in (render, render_markdown):
        page = renderer(_matrix(), links, "stamp", local=LOCAL)
        assert "local 2026-11-14" in page
        assert "local, stale: tests/test_a.py" in page


def test_gate_backfill_treats_a_local_row_with_a_reason_as_debt() -> None:
    from fr.gatebackfill.close import _positive_evidence

    reader = SimpleNamespace(
        statuses={"stale": "local", "fresh": "local"},
        local_debt={"stale": "unstamped"},
        fixed_keys=frozenset(),
    )
    assert _positive_evidence(reader, "row:stale") is None  # type: ignore[arg-type]
    assert _positive_evidence(reader, "row:fresh") is not None  # type: ignore[arg-type]


# --- the CLI surfaces over a real repo with no CI --------------------------------------


def _set_local(root: Path) -> None:
    out = _fr("set-status", "--id", "target", "--status", "local", "--notes", "n")
    assert out.exit_code == 0, out.output


def _stamp(root: Path) -> None:
    """Stamp `target` as `deliver` would (phase 2): the HEAD blobs of its refs."""
    from fr.acceptance.edit import stamp_local

    files = {
        p: git(root, "rev-parse", f"HEAD:{p}").strip()
        for p in ("tests/test_a.py", "tests/test_b.py")
    }
    stamp = LocalStamp(at="2026-11-14", tree="a" * 40, log="suite.log@0123456789ab", files=files)
    for path in sorted((root / "docs" / "acceptance" / "features").glob("*.yaml")):
        text = path.read_text()
        if "status: local" in text:
            path.write_text(stamp_local(text, "target", stamp))
            commit_all(root, "stamp")
            return
    raise AssertionError("no fragment sets target local")


def test_status_and_check_list_an_unstamped_local_row_as_debt(no_ci: Path) -> None:  # noqa: F811
    _set_local(no_ci)
    status = _fr("status")
    assert status.exit_code == 0, status.output
    assert "target [local, unstamped]" in status.output
    check = _fr("check", "--no-fetch")
    assert check.exit_code == 0, check.output
    assert "target is local, unstamped" in check.output


def test_a_fresh_local_row_is_listed_not_debt_until_its_test_changes(no_ci: Path) -> None:  # noqa: F811
    _set_local(no_ci)
    _stamp(no_ci)
    status = _fr("status")
    assert "target [local 2026-11-14]" in status.output
    assert "no acceptance debt." in status.output

    (no_ci / "tests" / "test_a.py").write_text("def test_a(): assert 1\n")
    commit_all(no_ci, "edit")
    status = _fr("status")
    assert "target [local, stale: tests/test_a.py]" in status.output
    check = _fr("check", "--no-fetch")
    assert check.exit_code == 0, check.output
    assert "target is local, stale: tests/test_a.py" in check.output


def test_fr_status_counts_local_debt(no_ci: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    from fr.commands.status_cmd import _acceptance_section

    _set_local(no_ci)
    line = _acceptance_section(no_ci)
    assert line is not None and "1 open" in line
