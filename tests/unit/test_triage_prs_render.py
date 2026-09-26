"""`fr triage render` — the PRs section (gh#558 follow-up).

Every unlinked open PR renders with anchor, delivery verdict and badges —
judged or not. A judged PR must not vanish from the board: the shared
`<repo>#<n>` key may name no issue at all.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fr.triage.model import Facts, Judgements, PullRequest
from fr.triage.render import render

REPO = "derio-net/super-fr"


def _pr(number: int, **kw: Any) -> PullRequest:
    return PullRequest(
        repo=kw.pop("repo", REPO),
        number=number,
        title=kw.pop("title", f"PR {number}"),
        state="OPEN",
        is_draft=False,
        url=f"https://github.com/{REPO}/pull/{number}",
        **kw,
    )


def _facts(prs: list[PullRequest]) -> Facts:
    return Facts.model_validate(
        {
            "schema": 3,
            "scope": "derio-net--super-fr",
            "kind": "repo",
            "collected_at": "2026-09-22T12:00:00+00:00",
            "repos": [REPO],
            "issues": [],
            "prs": [p.model_dump(mode="json") for p in prs],
        }
    )


def _judgements(*rows: tuple[str, dict[str, Any]]) -> Judgements:
    return Judgements.model_validate(
        {
            "schema": 1,
            "tiers": [{"n": 1, "title": "Data loss"}],
            "issues": {k: {"tier": 1, **v} for k, v in rows},
        }
    )


def _prs_section(page: str) -> str:
    m = re.search(r'<section class="prs">(.*?)</section>', page, re.S)
    assert m is not None, "no PRs section"
    return m.group(1)


def test_prs_section_lists_every_open_pr_before_unranked_issues() -> None:
    prs = [_pr(1), _pr(2)]
    page = render(_facts(prs), _judgements(("super-fr#2", {"delivery": "delivers"})))

    section = _prs_section(page)
    assert 'data-key="super-fr#1"' in section
    assert 'data-key="super-fr#2"' in section
    assert page.index('<section class="prs">') < page.index('data-tier="unranked"')


def test_judged_pr_shows_its_delivery_verdict_and_note() -> None:
    prs = [_pr(2, anchor="spec", anchor_path="docs/superpowers/specs/x-design.md")]
    judgements = _judgements(
        ("super-fr#2", {"delivery": "partial", "delivery_note": "half the spec"})
    )
    section = _prs_section(render(_facts(prs), judgements))

    assert "delivery: partial" in section
    assert "half the spec" in section
    assert "x-design.md" in section


def test_unjudged_pr_shows_unranked_delivery() -> None:
    section = _prs_section(render(_facts([_pr(1)]), _judgements()))

    assert "delivery: unranked" in section


def test_badges_cover_fail_pending_pass_and_unknown_merge_verbatim() -> None:
    prs = [
        _pr(1, checks={"pass": 0, "fail": 2, "pending": 0}, merge_state="DIRTY"),
        _pr(2, checks={"pass": 0, "fail": 0, "pending": 1}, merge_state="BEHIND"),
        _pr(3, merge_state="UNKNOWN", mergeable="UNKNOWN"),
    ]
    section = _prs_section(render(_facts(prs), _judgements()))

    assert "✗ CI fail" in section
    assert "● CI pending" in section
    assert "✓ CI pass" in section
    assert "merge: DIRTY" in section
    assert "merge: UNKNOWN" in section
    assert "collected 2026-09-22T12:00:00+00:00" in section


def test_red_ci_and_conflict_chips_match_row_attributes() -> None:
    prs = [_pr(1, checks={"pass": 0, "fail": 1, "pending": 0}, merge_state="CLEAN")]
    page = render(_facts(prs), _judgements())

    assert 'data-filter="redci"' in page
    assert 'data-filter="conflicts"' in page
    assert 'data-redci="1"' in page
    assert 'data-conflicts="0"' in page


def test_pr_rows_escape_hostile_text_and_stay_off_script() -> None:
    prs = [_pr(1, title='"><script>alert(1)</script>')]
    page = render(_facts(prs), _judgements())

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    body = page.split("<script>", 1)[1]
    assert "alert(1)" not in body


def test_render_is_deterministic_with_prs() -> None:
    prs = [_pr(1), _pr(2, anchor="debug", anchor_path="j.md")]
    judgements = _judgements(("super-fr#2", {"delivery": "delivers"}))

    assert render(_facts(prs), judgements) == render(_facts(prs), judgements)


def test_empty_prs_section_says_so(tmp_path: Path) -> None:
    del tmp_path  # no filesystem needed; kept for symmetry with the render suite
    section = _prs_section(render(_facts([]), _judgements()))

    assert "No open pull requests." in section
