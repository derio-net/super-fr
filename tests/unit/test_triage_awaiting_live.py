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


def test_an_awaiting_live_issue_still_in_progress_is_not_a_stale_dispatch() -> None:
    """p4-r1: its fix merged through a Refs PR, so no closing PR links it and the
    `fr:in-progress` label may outlive the merge; it is awaiting live, not stale."""
    from fr.triage.check import stale_dispatches

    old = "2026-09-01T09:00:00Z"
    f = facts(
        [
            issue(1, labels=[LIVE, "fr:in-progress"], dispatch_marker_at=old),
            issue(2, labels=["fr:in-progress"], dispatch_marker_at=old),
        ]
    )
    jd = judgements({"widgets#1": j(), "widgets#2": j()})

    assert [s.key for s in stale_dispatches(f)] == ["widgets#2"]
    assert [s.key for s in classify(f, jd).stale] == ["widgets#2"]
    assert [n.ref for n in needs_you(f, jd) if n.kind == "stale-dispatch"] == ["widgets#2"]


def test_the_driver_holds_an_awaiting_live_batch_and_next_up_reads_its_hold() -> None:
    """p4-r2: one rule. The driver holds a wholly-awaiting batch (never dispatches it)
    and the board's Next up derives from that same action list."""
    from fr.triage.batch_drive import drive_pass
    from fr.triage.views import drive_snapshot

    f, jd = _batches()

    plan = drive_pass(drive_snapshot(f, jd))

    assert [(a.kind, a.batch) for a in plan.actions] == [
        ("dispatch", "a-ordinary"),
        ("held", "b-live"),
    ]
    assert [r.ref for r in next_up(f, jd) if r.kind == "batch"] == ["a-ordinary"]


def test_the_kanban_card_says_why_an_awaiting_live_batch_is_held() -> None:
    from fr.triage.kanban import action_phrase, first_actions

    f, jd = _batches()

    assert action_phrase(first_actions(f, jd)["b-live"]) == "held: its members await a live walk"


def _refs_merged(*, dependent: bool = True):
    """Wave 1: `a-plain` merged with its member closed. Wave 2: `b-refs` merged through
    a Refs PR, so its member stays open and awaits live; `c-after` depends on it."""
    from tests.unit.triage_board_fixtures import dispatch, pr

    merged = {"state": "MERGED", "merged_at": "2026-10-01T12:00:00Z"}
    pa = pr(20, "feat/batch-a-plain", **merged)
    pb = pr(21, "feat/batch-b-refs", **merged)
    f = facts(
        [
            issue(1, state="closed", prs=[pa]),
            issue(2, labels=[LIVE]),  # Refs'd, not closed: no linked closing PR
            issue(3),
        ],
        batch_prs=[pa, pb],
    )
    jd = judgements(
        {"widgets#1": j(), "widgets#2": j(), "widgets#3": j()},
        [
            batch("a-plain", [1], wave=1, events=[dispatch("a-plain")]),
            batch("b-refs", [2], wave=2, events=[dispatch("b-refs")]),
            *([batch("c-after", [3], wave=3, after=["b-refs"])] if dependent else []),
        ],
    )
    return f, jd


def test_a_batch_merged_through_a_refs_pr_derives_merged_not_partial() -> None:
    """p4-r3: an awaiting-live member counts as closed, so the batch is `merged`."""
    from fr.triage.batch import derive_batch_stage

    f, jd = _refs_merged()

    assert derive_batch_stage(jd.batches[1], f) == "merged"


def test_a_batch_after_a_refs_merged_batch_is_not_blocked() -> None:
    from fr.triage.batch_drive import drive_pass
    from fr.triage.views import drive_snapshot

    f, jd = _refs_merged()

    kinds = [(a.kind, a.batch) for a in drive_pass(drive_snapshot(f, jd)).actions]

    assert ("dispatch", "c-after") in kinds
    assert not [k for k in kinds if k[0] == "blocked"]


def test_a_wave_of_merged_but_awaiting_batches_is_preselected_like_any_merged_wave() -> None:
    f, jd = _refs_merged(dependent=False)

    assert preselected_wave(f, jd) == 2
