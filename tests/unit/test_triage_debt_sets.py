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
from tests.unit.triage_debt_fixtures import LEGACY, body, digest, figures


def _state():
    f = facts(
        [
            digest(1, figures()),  # current marker
            digest(2, None, marker=LEGACY),  # legacy digest, no figures
            issue(3, labels=["fr:owed"]),  # owed
            issue(4, body="see <!-- fr-technical-debt --> inline, not its own line"),
            digest(5, figures(), state="closed"),
            issue(6),  # ordinary
            digest(7, figures()),  # judged
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
    f = facts([])
    kw = {"repo": REPO, "number": 9, "title": "t", "state": "open", "url": "u"}
    kw["author"] = "github-actions[bot]"
    inline = Issue(**kw, body="x <!-- fr-technical-debt --> y")
    crlf = Issue(**kw, body="a\r\n<!-- fr-technical-debt -->\r\nb")

    assert not is_debt_digest(inline, f)
    assert is_debt_digest(crlf, f)
    assert not is_owed(inline)


def test_check_json_carries_figures_or_none() -> None:
    f, jd = _state()

    out = classify(f, jd).to_json()

    rows = {r["key"]: r for r in out["debt_digests"]}
    assert rows["widgets#1"]["figures"]["acceptance"]["not-implemented"] == 30
    assert rows["widgets#2"]["figures"] is None  # a legacy body yields None
    assert [r["key"] for r in out["owed"]] == ["widgets#3"]


def test_hostile_figures_are_shown_as_numbers_only() -> None:
    f = facts([digest(1, figures(acceptance={"<b>x</b>": "<script>", "ci": 2}, owed="<i>"))])

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


def test_a_marker_by_anyone_else_is_ignored_and_listed_apart() -> None:
    f = facts(
        [
            digest(1, figures(), author="stranger"),
            digest(2, figures(), author="app/github-actions"),
            digest(3, figures(), author="Operator"),  # the viewer, case-insensitive
            digest(4, figures(), author=None),  # facts from before authors were read
        ]
    )

    r = classify(f, judgements({}))

    assert [i.key for i in r.debt_digests] == ["widgets#2", "widgets#3"]
    assert [i.key for i in r.untrusted_digests] == ["widgets#1", "widgets#4"]
    # an untrusted marker stays an ordinary issue: it is not hidden from ranking
    assert [i.key for i in r.unranked] == ["widgets#1", "widgets#4"]
    assert [u["key"] for u in r.to_json()["untrusted_digests"]] == ["widgets#1", "widgets#4"]


def test_the_repos_own_trusted_logins_count() -> None:
    f = facts(
        [digest(1, figures(), author="maintainer")],
        config={"example-org/widgets": {"pr_authors": ["Maintainer"]}},
    )

    assert [i.key for i in classify(f, judgements({})).debt_digests] == ["widgets#1"]


def test_collect_keeps_the_author_and_a_digests_whole_body() -> None:
    from fr.triage.collect import ISSUE_FIELDS, _issue

    assert "author" in ISSUE_FIELDS.split(",")
    long = body(figures()).replace("some table", "row\n" * 3000)
    raw = {
        "number": 1,
        "title": "t",
        "url": "u",
        "body": long,
        "author": {"login": "github-actions[bot]"},
    }

    kept = _issue("example-org/widgets", raw, [], state="open")
    plain = _issue("example-org/widgets", {**raw, "body": "x" * 5000}, [], state="open")

    assert kept.author == "github-actions[bot]"
    assert kept.body == long  # the figures sit at the end, past BODY_LIMIT
    assert len(plain.body) == 2000
