"""`fr triage origins collect|check|render` (wave-driver R10, R12, R20; Test Plan 9, 13).

Fifteen fictional issues; every expected figure below was computed by hand from
`triage_origins_fixtures.ROWS`, not by the code under test.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.triage_origins_fixtures import (
    REPO,
    SINCE,
    OriginsForge,
    classification_yaml,
)

CAUSES = """causes:
  - title: Feature work lands half-done
    categories: [new-feature, leftover]
    batches: [finish-widgets, ghost-batch]
    process_change: Require a follow-up checklist before merge
  - title: Nothing guards the happy path
    categories: [latent]
    batches: []
    process_change: Add a regression test per fix
"""

JUDGEMENTS = """schema: 3
tiers:
  - {n: 1, title: Now, description: first}
issues:
  'widgets#3': {tier: 1}
batches:
  - id: finish-widgets
    title: Finish the widgets
    ids: ['widgets#3']
    rationale: close the gaps
"""


def _run(monkeypatch: pytest.MonkeyPatch, verb: str, d: Path, *args: str, forge: Any = None) -> Any:
    import fr.commands.triage_cmd as triage_cmd

    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge or OriginsForge())
    return CliRunner().invoke(
        app, ["triage", "origins", verb, "--repo", REPO, "--dir", str(d), *args]
    )


def _collect(monkeypatch: pytest.MonkeyPatch, d: Path) -> dict[str, Any]:
    r = _run(monkeypatch, "collect", d, "--since", SINCE)
    assert r.exit_code == 0, r.output
    data: dict[str, Any] = json.loads((d / "origins-facts.json").read_text(encoding="utf-8"))
    return data


def _page(monkeypatch: pytest.MonkeyPatch, d: Path, *, causes: str = CAUSES) -> str:
    _collect(monkeypatch, d)
    (d / "origins.yaml").write_text(classification_yaml(causes=causes), encoding="utf-8")
    (d / "judgements.yaml").write_text(JUDGEMENTS, encoding="utf-8")
    r = _run(monkeypatch, "render", d)
    assert r.exit_code == 0, r.output
    return (d / "origins.html").read_text(encoding="utf-8")


def _section(page: str, sid: str) -> str:
    m = re.search(rf'<section[^>]*id="{sid}".*?</section>', page, flags=re.S)
    assert m, f"no section {sid}"
    return m.group(0)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()


# ----------------------------------------------------------------- collect


def test_collect_since_keeps_only_issues_created_in_the_window(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    facts = _collect(monkeypatch, tmp_path)
    assert [i["number"] for i in facts["issues"]] == list(range(1, 16))
    assert facts["since"] == SINCE


def test_collect_records_state_reason_closing_prs_and_hours_to_close(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    by_n = {i["number"]: i for i in _collect(monkeypatch, tmp_path)["issues"]}
    # #2 created 09-01 10:00, closed 09-02 10:00: 24h, closed by merged PR 302.
    assert by_n[2]["state"] == "closed" and by_n[2]["reason"] == "completed"
    assert by_n[2]["hours_to_close"] == 24.0
    assert [p["number"] for p in by_n[2]["closing_prs"]] == [302]
    assert [p["number"] for p in by_n[10]["closing_prs"]] == [302]
    assert [p["number"] for p in by_n[1]["closing_prs"]] == [301]
    assert by_n[1]["hours_to_close"] == 6.0
    # an unmerged PR never counts as the one that closed it
    assert by_n[4]["closing_prs"] == [] and by_n[4]["hours_to_close"] == 2.0
    # #6 closed as not planned; #3 still open: no hours, no reason
    assert by_n[6]["reason"] == "not_planned"
    assert by_n[3]["state"] == "open" and by_n[3]["reason"] is None
    assert by_n[3]["hours_to_close"] is None and by_n[3]["closed_at"] is None
    assert by_n[3]["labels"] == ["bug"] and by_n[3]["title"] == "Widget defect 3"


def test_collect_needs_a_valid_since(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    r = _run(monkeypatch, "collect", tmp_path, "--since", "last tuesday")
    assert r.exit_code == 2
    assert not (tmp_path / "origins-facts.json").exists()


# ------------------------------------------------------------------- check


def test_check_lists_issues_with_no_classification_and_always_exits_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _collect(monkeypatch, tmp_path)
    stray = (
        "  widgets#500:\n    category: gap\n    source: hand\n    severity: low\n"
        "    reason: not in the facts\n"
    )
    (tmp_path / "origins.yaml").write_text(
        classification_yaml(skip=(7, 13), extra=stray), encoding="utf-8"
    )
    r = _run(monkeypatch, "check", tmp_path)
    assert r.exit_code == 0
    assert "unclassified (2)" in r.output
    assert "widgets#7" in r.output and "widgets#13" in r.output
    assert "not in the facts (1)" in r.output and "widgets#500" in r.output
    # the stray classification is never pruned
    assert "widgets#500" in (tmp_path / "origins.yaml").read_text(encoding="utf-8")


def test_check_without_any_classification_lists_everything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _collect(monkeypatch, tmp_path)
    r = _run(monkeypatch, "check", tmp_path)
    assert r.exit_code == 0 and "unclassified (15)" in r.output


def test_check_and_render_without_facts_name_the_collect_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for verb in ("check", "render"):
        r = _run(monkeypatch, verb, tmp_path)
        assert r.exit_code == 2 and "origins collect" in r.output.replace("\n", " ")


def test_a_bad_classification_is_refused_with_its_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _collect(monkeypatch, tmp_path)
    (tmp_path / "origins.yaml").write_text(
        "schema: 1\nissues:\n  widgets#1: {category: nonsense, source: hand, severity: low,"
        " reason: x}\n",
        encoding="utf-8",
    )
    r = _run(monkeypatch, "check", tmp_path)
    assert r.exit_code == 2 and "origins.yaml" in r.output.replace("\n", "")


# ------------------------------------------------------------------ render


def test_render_counts_by_category_and_source_with_shares(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _page(monkeypatch, tmp_path)
    counts = _section(page, "origin-counts")
    cat = dict(re.findall(r'data-category-count="([a-z-]+)">(\d+)<', counts))
    assert cat == {
        "latent": "3", "regression": "2", "new-feature": "3",
        "leftover": "3", "gap": "2", "duplicate": "2",
    }  # fmt: skip
    src = dict(re.findall(r'data-source-count="([a-z]+)">(\d+)<', counts))
    assert src == {"pipeline": "8", "recording": "3", "hand": "4"}
    shares = dict(re.findall(r'data-source-share="([a-z]+)">(\d+)%<', counts))
    assert shares == {"pipeline": "53", "recording": "20", "hand": "27"}


def test_render_buckets_filings_per_day_and_draws_them_to_scale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _page(monkeypatch, tmp_path)
    chart = _section(page, "filings-per-day")
    bars = re.findall(r'data-day="([\d-]+)" data-count="(\d+)"[^>]*height="([\d.]+)"', chart)
    assert [(d, int(c)) for d, c, _ in bars] == [
        ("2026-09-01", 3), ("2026-09-02", 3), ("2026-09-03", 0),
        ("2026-09-04", 3), ("2026-09-05", 6),
    ]  # fmt: skip
    h = {d: float(x) for d, _c, x in bars}
    assert h["2026-09-05"] == pytest.approx(2 * h["2026-09-01"])
    assert h["2026-09-03"] == 0
    # labels and bars take their colour from theme tokens, never a literal
    assert "var(--" in chart and not re.search(r"#[0-9a-fA-F]{3,6}", chart)


def test_render_median_hours_to_fix_counts_completed_closes_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _page(monkeypatch, tmp_path)
    rows = {
        m[0]: m[1:]
        for m in re.findall(
            r'data-ttf="([a-z-]+)"[^>]*>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>([^<]*)</td>\s*'
            r"<td[^>]*>([^<]*)</td>\s*<td[^>]*>([^<]*)</td>",
            _section(page, "time-to-fix"),
        )
    }
    # by hand: latent 6,6,24 -> 6; regression 24,3 -> 13.5; new-feature 12 (+2 open);
    # leftover 2,24 -> 13 (+1 open); gap 48 (+1 open); duplicate: none completed
    assert rows["latent"] == ("6.0 h", "0", "0")
    assert rows["regression"] == ("13.5 h", "0", "0")
    assert rows["new-feature"] == ("12.0 h", "2", "0")
    assert rows["leftover"] == ("13.0 h", "1", "0")
    assert rows["gap"] == ("48.0 h", "1", "0")
    assert rows["duplicate"] == ("—", "0", "2")


def test_render_per_pr_leaderboards_list_the_producers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _page(monkeypatch, tmp_path)
    boards = _section(page, "pr-leaderboards")

    def board(category: str) -> list[tuple[str, str]]:
        m = re.search(rf'data-board="{category}".*?</table>', boards, flags=re.S)
        assert m
        return re.findall(r'data-pr="([^"]+)" data-n="(\d+)"', m.group(0))

    assert board("new-feature") == [
        ("example-org/widgets#102", "2"),
        ("example-org/widgets#103", "1"),
    ]
    assert board("leftover") == [
        ("example-org/widgets#103", "2"),
        ("example-org/widgets#102", "1"),
    ]


def test_render_issue_table_is_filterable_by_category(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _page(monkeypatch, tmp_path)
    table = _section(page, "issue-table")
    rows = re.findall(r'<tr data-category="([a-z-]+)" data-key="([^"]+)"', table)
    assert len(rows) == 15 and ("regression", "widgets#2") in rows
    assert page.count("<script") == 1
    assert 'data-filter="regression"' in page
    # with scripts off every row shows: the filter bar starts hidden, no row does
    assert re.search(r'<div class="bar"[^>]*\bhidden\b', page)
    assert not re.search(r"<tr [^>]*\bhidden\b", table)


def test_render_ends_in_a_conclusion_linking_each_cause_to_its_batch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _page(monkeypatch, tmp_path)
    sections = re.findall(r'<section[^>]*id="([a-z-]+)"', page)
    assert sections[-1] == "conclusion"
    assert page.rindex('id="conclusion"') > page.rindex('id="issue-table"')
    concl = _section(page, "conclusion")
    assert "Feature work lands half-done" in concl
    assert "Require a follow-up checklist before merge" in concl
    assert 'href="triage.html#batch-finish-widgets"' in concl
    # a batch the judgements do not hold is shown as unresolved, never dropped
    assert re.search(r'class="unresolved"[^>]*>[^<]*ghost-batch', concl)
    # a cause with no batch says so
    assert "no batch yet" in _text(concl)


def test_every_batch_is_unresolved_when_there_is_no_judgements_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _collect(monkeypatch, tmp_path)
    (tmp_path / "origins.yaml").write_text(classification_yaml(causes=CAUSES), encoding="utf-8")
    assert _run(monkeypatch, "render", tmp_path).exit_code == 0
    concl = _section((tmp_path / "origins.html").read_text(encoding="utf-8"), "conclusion")
    assert len(re.findall(r'class="unresolved"', concl)) == 2 and "href=" not in concl


def test_render_is_a_proper_page_on_the_shared_components(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fr.triage.components import GUTTER_CSS, TOKENS_CSS

    page = _page(monkeypatch, tmp_path)
    assert re.search(r"<title>[^<]*widgets[^<]*</title>", page)
    assert TOKENS_CSS.strip() in page and GUTTER_CSS.strip() in page
    assert ':root[data-theme="dark"]' in page


def test_a_missing_figure_is_an_em_dash_never_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _collect(monkeypatch, tmp_path)
    (tmp_path / "origins.yaml").write_text("schema: 1\nissues: {}\n", encoding="utf-8")
    assert _run(monkeypatch, "render", tmp_path).exit_code == 0
    page = (tmp_path / "origins.html").read_text(encoding="utf-8")
    assert "15 unclassified" in _text(page)
    ttf = _text(_section(page, "time-to-fix"))
    assert "—" in ttf
    shares = _text(_section(page, "origin-counts"))
    assert "0%" not in shares and "—" in shares


def test_render_escapes_untrusted_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    forge = OriginsForge()
    forge.issues[0]["title"] = "<script>alert(1)</script>"
    r = _run(monkeypatch, "collect", tmp_path, "--since", SINCE, forge=forge)
    assert r.exit_code == 0
    (tmp_path / "origins.yaml").write_text(classification_yaml(), encoding="utf-8")
    assert _run(monkeypatch, "render", tmp_path).exit_code == 0
    page = (tmp_path / "origins.html").read_text(encoding="utf-8")
    assert "<script>alert" not in page and page.count("<script") == 1


def test_origins_classification_vocabulary_is_closed() -> None:
    from fr.triage.origins import CATEGORIES, SOURCES

    assert CATEGORIES == ("latent", "regression", "new-feature", "leftover", "gap", "duplicate")
    assert SOURCES == ("pipeline", "recording", "hand")
    assert yaml.safe_load(classification_yaml())["schema"] == 1


def test_a_regression_without_its_pr_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _collect(monkeypatch, tmp_path)
    (tmp_path / "origins.yaml").write_text(
        "schema: 1\nissues:\n  widgets#2: {category: regression, source: pipeline,"
        " severity: low, reason: x}\n",
        encoding="utf-8",
    )
    r = _run(monkeypatch, "check", tmp_path)
    assert r.exit_code == 2 and "must name the PR" in r.output.replace("\n", " ")
