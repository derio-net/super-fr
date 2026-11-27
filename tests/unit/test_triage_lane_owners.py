"""Who owns a Needs-you lane (spec 2026-11-27-board-session-state R4, §C).

`lane_owners` in a repo's `.fr/triage.yaml` is display-only: a typo never refuses the
repo's other keys, and the key is not one fr guards under quiet or stealth.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.config.protection import GUARDED_TRIAGE_KEYS
from fr.triage.kanban import build_board
from fr.triage.kanban_render import render_board
from fr.triage.model import FACTS_SCHEMA, Facts, Judgements, TriageConfig, parse_triage_config

from tests.unit.triage_board_fixtures import REPO, batch, dispatch, facts, issue, j, judgements, pr

AT = datetime(2026, 10, 5, 21, 30, tzinfo=UTC)
SCOPE = ["--repo", REPO]
DELIVERED_PR = pr(
    11,
    "feat/batch-a",
    cursor={"run": "r1", "step": "deliver", "kind": "deliver-done", "unit": None},
    cursor_read="read",
)


def test_the_facts_schema_is_21() -> None:
    assert FACTS_SCHEMA == 21


def test_lane_owners_parse_and_default_to_empty_lists() -> None:
    cfg = TriageConfig.model_validate({"lane_owners": {"reviewer": ["a", "b"]}})
    owners = cfg.lane_owners
    assert owners.reviewer == ["a", "b"]
    assert (owners.developer, owners.tester, owners.devops, owners.ignored) == ([], [], [], [])
    assert TriageConfig().lane_owners.reviewer == []


def test_an_unknown_lane_key_is_ignored_and_never_refuses_the_config() -> None:
    cfg, ignored = parse_triage_config(
        {"lane_owners": {"review": ["x"], "reviewer": ["a"]}, "stale_dispatch_days": 5}
    )
    assert cfg.lane_owners.reviewer == ["a"]
    assert cfg.lane_owners.ignored == ["review"]
    assert cfg.stale_dispatch_days == 5 and ignored == ()


def test_the_config_round_trips_through_json_with_its_ignored_keys() -> None:
    cfg = TriageConfig.model_validate({"lane_owners": {"review": ["x"], "tester": ["t"]}})
    again = TriageConfig.model_validate(json.loads(cfg.model_dump_json()))
    assert again.lane_owners == cfg.lane_owners


def test_lane_owners_is_not_a_guarded_key() -> None:
    assert "lane_owners" not in GUARDED_TRIAGE_KEYS


# ---------------------------------------------------------------- the column view


def _world(owners: dict[str, Any] | None, *, two_repos: bool = False) -> tuple[Facts, Judgements]:
    issues = [issue(1, prs=[DELIVERED_PR])]
    config: dict[str, Any] = {REPO: {"lane_owners": owners}} if owners is not None else {}
    kw: dict[str, Any] = {"config": config}
    if two_repos:
        other = "example-org/gadgets"
        kw["repos"] = [REPO, other]
        kw["config"] = {**config, other: {"lane_owners": {"reviewer": ["z"]}}}
    f = facts(issues, **kw)
    jd = judgements({"widgets#1": j(1)}, [batch("a", [1], events=[dispatch("a")])])
    return f, jd


def _page(f: Facts, jd: Judgements) -> str:
    board = build_board(f, jd, {})
    return render_board(board, scope_args=SCOPE, rendered_at=AT, refresh=30, notes=[])


def _column(page: str, key: str) -> str:
    m = re.search(rf'<section class="col[^"]*" data-column="{key}">.*?</section>', page, re.S)
    assert m, key
    return m.group(0)


def test_a_needs_you_column_holds_each_repos_owners() -> None:
    f, jd = _world({"reviewer": ["a", "b"]})
    board = build_board(f, jd, {})
    assert board.column("needs-reviewer").owners == {REPO: ("a", "b")}
    assert board.column("needs-tester").owners == {REPO: ()}
    assert board.column("running").owners == {} and board.column("pr-open").owners == {}


def test_the_header_names_the_owners_or_says_unassigned() -> None:
    f, jd = _world({"reviewer": ["a", "b"]})
    page = _page(f, jd)
    assert "owner: @a, @b" in _column(page, "needs-reviewer")
    assert "owner: unassigned" in _column(page, "needs-tester")
    assert "owner:" not in _column(page, "running")


def test_a_scope_of_two_repos_with_different_owners_shows_one_line_per_repo() -> None:
    f, jd = _world({"reviewer": ["a"]}, two_repos=True)
    header = _column(_page(f, jd), "needs-reviewer")
    assert "example-org/widgets: @a" in header and "example-org/gadgets: @z" in header
    same = _column(_page(f, jd), "needs-devops")
    assert same.count("owner: unassigned") == 1  # equal owners collapse to one line


def test_a_lane_card_names_the_lanes_owners_in_its_wait_line() -> None:
    f, jd = _world({"reviewer": ["a", "b"]})
    board = build_board(f, jd, {})
    assert board.card("a").column == "needs-reviewer"
    card = re.search(r'<details class="card[^"]*" id="card-a".*?</details>', _page(f, jd), re.S)
    assert card and "waits for you · reviewer (@a, @b)" in card.group(0)


def test_owner_logins_are_escaped() -> None:
    f, jd = _world({"reviewer": ['<img src=x onerror=1>"']})
    page = _page(f, jd)
    assert "<img src=x" not in page and "&lt;img src=x" in page


def test_ignored_lane_keys_get_one_note_per_repo(tmp_path: Path) -> None:
    from fr.commands.triage_kanban_cmd import lane_owner_notes

    f, _ = _world({"review": ["x"], "reviewer": ["a"], "chief": []})
    (note,) = lane_owner_notes(f)
    assert REPO in note and "chief" in note and "review" in note and "lane_owners" in note
    quiet, _ = _world({"reviewer": ["a"]})
    assert lane_owner_notes(quiet) == []


@pytest.mark.parametrize("below", [20, 3])
def test_a_facts_file_below_21_reads_lane_owners_as_empty(below: int) -> None:
    f = facts([issue(1)])
    data = f.to_json()
    data["schema"] = below
    for cfg in data.get("config", {}).values():
        cfg.pop("lane_owners", None)
    assert Facts.model_validate(data).config_for(REPO).lane_owners.reviewer == []
