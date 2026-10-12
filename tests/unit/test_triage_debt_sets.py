"""The debt-digest and owed sets (debt-engine spec §C, R14, R16): neither is ranked,
unranked or unplaced, and figures come from the body the facts already hold."""

from __future__ import annotations

import json
from pathlib import Path

from fr.cli import app
from fr.triage.check import classify, is_debt_digest, is_owed
from fr.triage.model import Issue
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import REPO, facts, issue, j, judgements
from tests.unit.triage_debt_fixtures import LEGACY, body, figures


def _state():
    f = facts(
        [
            issue(1, body=body(figures())),  # current marker
            issue(2, body=body(None, LEGACY)),  # legacy digest, no figures
            issue(3, labels=["fr:owed"]),  # owed
            issue(4, body="see <!-- fr-technical-debt --> inline, not its own line"),
            issue(5, body=body(figures()), state="closed"),
            issue(6),  # ordinary
            issue(7, body=body(figures())),  # judged
        ]
    )
    return f, judgements({"widgets#7": j(), "widgets#3": j()})


def test_either_marker_lands_in_the_debt_set_and_owed_in_its_own() -> None:
    f, jd = _state()

    r = classify(f, jd)

    assert [i.key for i in r.debt_digests] == ["widgets#1", "widgets#2", "widgets#7"]
    assert [i.key for i in r.owed] == ["widgets#3"]


def test_neither_is_unranked_unplaced_or_unseverity() -> None:
    f, jd = _state()

    r = classify(f, jd)

    assert [i.key for i in r.unranked] == ["widgets#4", "widgets#6"]
    assert [i.key for i in r.unplaced] == ["widgets#4", "widgets#6"]
    assert r.no_severity == []


def test_the_marker_counts_only_as_its_own_line() -> None:
    inline = Issue(
        repo=REPO, number=9, title="t", state="open", url="u", body="x <!-- fr-technical-debt --> y"
    )
    crlf = Issue(
        repo=REPO,
        number=9,
        title="t",
        state="open",
        url="u",
        body="a\r\n<!-- fr-technical-debt -->\r\nb",
    )

    assert not is_debt_digest(inline)
    assert is_debt_digest(crlf)
    assert not is_owed(inline)


def test_check_json_carries_figures_or_none() -> None:
    f, jd = _state()

    out = classify(f, jd).to_json()

    rows = {r["key"]: r for r in out["debt_digests"]}
    assert rows["widgets#1"]["figures"]["acceptance"]["not-implemented"] == 30
    assert rows["widgets#2"]["figures"] is None  # a legacy body yields None
    assert [r["key"] for r in out["owed"]] == ["widgets#3"]


def test_hostile_figures_are_shown_as_numbers_only() -> None:
    f = facts(
        [issue(1, body=body(figures(acceptance={"<b>x</b>": "<script>", "ci": 2}, owed="<i>")))]
    )

    row = classify(f, judgements({})).to_json()["debt_digests"][0]

    assert row["figures"]["acceptance"] == {"ci": 2}
    assert row["figures"]["owed"] is None


def test_the_text_report_names_both_sets(tmp_path: Path) -> None:
    f, _ = _state()
    (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), encoding="utf-8")

    out = CliRunner().invoke(
        app, ["triage", "check", "--repo", "example-org/widgets", "--dir", str(tmp_path)]
    )

    assert out.exit_code == 0, out.output
    assert "debt digests" in out.output and "owed" in out.output
