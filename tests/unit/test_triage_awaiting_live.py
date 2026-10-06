"""The awaiting-live set (spec 2026-10-06-verification-strategies §F, R18): open
issues carrying `fr:awaiting-live` are neither ranked nor proposed as work; the
board shows them in a group of their own."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fr.cli import app
from fr.triage.check import classify
from fr.triage.render import render
from fr.triage.views import needs_you, next_up, preselected_wave
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import batch, facts, issue, j, judgements

LIVE = "fr:awaiting-live"


def _state():
    f = facts(
        [
            issue(1, labels=[LIVE]),  # judged, in no batch
            issue(2, labels=[LIVE]),  # unjudged
            issue(3, labels=[LIVE], state="closed"),  # closed: not in the set
            issue(4),  # ordinary, unjudged
            issue(5, labels=["fr:ready"]),  # ordinary, judged
        ]
    )
    return f, judgements({"widgets#1": j(), "widgets#5": j()})


def test_check_lists_open_labelled_issues_and_keeps_them_out_of_unranked_and_unplaced() -> None:
    f, jd = _state()

    result = classify(f, jd)

    assert [i.key for i in result.awaiting_live] == ["widgets#1", "widgets#2"]
    assert [i.key for i in result.unranked] == ["widgets#4"]
    assert [i.key for i in result.unplaced] == ["widgets#4", "widgets#5"]
    assert [row["key"] for row in result.to_json()["awaiting_live"]] == [
        "widgets#1",
        "widgets#2",
    ]


def test_check_json_carries_the_set(tmp_path: Path) -> None:
    f, _ = _state()
    (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), encoding="utf-8")

    out = CliRunner().invoke(
        app,
        ["triage", "check", "--repo", "example-org/widgets", "--dir", str(tmp_path), "--json"],
    )

    assert out.exit_code == 0, out.output
    assert [i["key"] for i in json.loads(out.output)["awaiting_live"]] == [
        "widgets#1",
        "widgets#2",
    ]
    text = CliRunner().invoke(
        app, ["triage", "check", "--repo", "example-org/widgets", "--dir", str(tmp_path)]
    )
    assert "awaiting live" in text.output


def test_needs_you_never_calls_one_unplaced() -> None:
    f, jd = _state()

    assert [n.ref for n in needs_you(f, jd) if n.kind == "unplaced"] == [
        "widgets#4",
        "widgets#5",
    ]


def _batches():
    """Wave 1 holds an ordinary proposed batch; wave 2's only member awaits live."""
    f = facts([issue(1), issue(2, labels=[LIVE])])
    jd = judgements(
        {"widgets#1": j(), "widgets#2": j()},
        [
            batch("a-ordinary", [1], wave=1),
            batch("b-live", [2], wave=2),
        ],
    )
    return f, jd


def test_an_awaiting_live_batch_is_not_next_up_and_holds_no_wave_open() -> None:
    f, jd = _batches()

    assert [r.ref for r in next_up(f, jd) if r.kind == "batch"] == ["a-ordinary"]
    assert preselected_wave(f, jd) == 1


def test_an_awaiting_live_feature_member_is_not_next_up() -> None:
    f = facts([issue(1, labels=[LIVE]), issue(2)])
    jd = judgements(
        {"widgets#1": j(), "widgets#2": j()},
        features=[
            {"title": "Live only", "rank": 1, "ids": ["widgets#1"]},
            {"title": "Real work", "rank": 2, "ids": ["widgets#2"]},
        ],
    )

    assert [r.ref for r in next_up(f, jd) if r.kind == "feature"] == ["Real work"]


def test_the_board_shows_them_in_one_collapsed_group_and_nowhere_else() -> None:
    f, jd = _state()

    page = render(f, jd)

    group = re.search(
        r'<details id="awaiting-live" class="fold">.*?</section></details>', page, re.S
    )
    assert group is not None
    keys = re.findall(r'data-key="(widgets#\d+)"', group.group(0))
    assert keys == ["widgets#1", "widgets#2"]
    outside = page.replace(group.group(0), "")
    assert 'data-key="widgets#1"' not in outside and 'data-key="widgets#2"' not in outside
    assert 'data-key="widgets#4"' in outside  # an ordinary issue still renders
    assert "open" not in re.match(r"<details[^>]*>", group.group(0)).group(0).split()
