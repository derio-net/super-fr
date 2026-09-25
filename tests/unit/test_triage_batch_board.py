"""The board's Batches section and the in-progress stage
(spec 2026-09-25-triage-batches §3.E, §3.G; Test Plan 10, 20).

Pure render over constructed facts and judgements: no forge, no clock.
"""

from __future__ import annotations

import re
from typing import Any

from fr.triage.model import Facts, Issue, Judgements, PullRequest
from fr.triage.render import IN_FLIGHT, render

REPO = "derio-net/super-fr"
SHARED = "packages/fr/src/fr/isolation/local.py"


def _pr(number: int, head: str, files: list[str], state: str = "OPEN") -> PullRequest:
    return PullRequest(
        repo=REPO,
        number=number,
        title=f"batch pr {number}",
        state=state,  # type: ignore[arg-type]
        is_draft=False,
        url=f"https://github.com/{REPO}/pull/{number}",
        head_ref=head,
        files=files,
    )


LIFE = _pr(50, "feat/batch-lifecycle", [SHARED, "packages/fr/src/fr/isolation/cmd.py"])
DOCS = _pr(51, "feat/batch-docs", [SHARED, "README.md"])


def _issue(number: int, *, prs: list[PullRequest] = (), labels: list[str] = ()) -> Issue:
    return Issue(
        repo=REPO,
        number=number,
        title=f"issue {number}",
        state="open",
        labels=list(labels),
        url=f"https://github.com/{REPO}/issues/{number}",
        prs=list(prs),
    )


FACTS = Facts(
    schema=3,
    scope="derio-net--super-fr",
    kind="repo",
    collected_at="2026-09-26T12:00:00+00:00",
    repos=[REPO],
    issues=[
        _issue(577, prs=[LIFE]),
        _issue(575, prs=[LIFE]),
        _issue(471, prs=[DOCS]),
        _issue(438, labels=["fr:in-progress"]),
        _issue(420),
    ],
)


def _dispatch(branch: str, version: str) -> dict[str, Any]:
    return {
        "kind": "dispatch",
        "at": "2026-09-25T10:00:00Z",
        "runner": "herdr",
        "handle": "w2:p1K",
        "branch": branch,
        "reserved_version": version,
    }


JUDGEMENTS = Judgements.model_validate(
    {
        "schema": 2,
        "tiers": [{"n": 1, "title": "Now"}],
        "issues": {
            k: {"tier": 1}
            for k in (
                "super-fr#577",
                "super-fr#575",
                "super-fr#471",
                "super-fr#438",
                "super-fr#420",
            )
        },
        "batches": [
            {
                "id": "lifecycle",
                "title": "Separate lifecycles",
                "ids": ["super-fr#577", "super-fr#575"],
                "order": 1,
                "events": [_dispatch("feat/batch-lifecycle", "4.22.0")],
            },
            {
                "id": "docs",
                "title": "Docs <sweep>",
                "ids": ["super-fr#471"],
                "events": [_dispatch("feat/batch-docs", "4.23.0")],
            },
            {"id": "later", "title": "Not yet", "ids": ["super-fr#420"]},
        ],
    }
)


def _section(html: str) -> str:
    match = re.search(r'<section class="batches">.*?</section>', html, re.S)
    assert match, "no Batches section"
    return match.group(0)


def test_the_batches_section_sits_above_the_tiers() -> None:
    html = render(FACTS, JUDGEMENTS)
    assert html.index('<section class="batches">') < html.index('<section class="tier')


def test_each_batch_card_shows_members_stage_version_and_pr() -> None:
    section = _section(render(FACTS, JUDGEMENTS))
    card = re.search(r'<article class="batch" data-batch="lifecycle".*?</article>', section, re.S)
    assert card
    body = card.group(0)
    assert "super-fr#577" in body and "super-fr#575" in body
    assert 'class="pill bstage-pr-open"' in body
    assert "4.22.0" in body
    assert f'href="https://github.com/{REPO}/pull/50"' in body
    later = re.search(r'data-batch="later".*?</article>', section, re.S)
    assert later and "bstage-proposed" in later.group(0)


def test_batch_titles_are_escaped() -> None:
    section = _section(render(FACTS, JUDGEMENTS))
    assert "Docs &lt;sweep&gt;" in section
    assert "<sweep>" not in section


def test_pr_open_batches_show_the_planned_order_with_shared_files() -> None:
    section = _section(render(FACTS, JUDGEMENTS))
    plan = re.search(r'<ol class="merge-order">.*?</ol>', section, re.S)
    assert plan
    steps = re.findall(r"<li.*?</li>", plan.group(0), re.S)
    assert [re.search(r'data-batch="([^"]+)"', s).group(1) for s in steps] == [  # type: ignore[union-attr]
        "lifecycle",
        "docs",
    ]
    assert SHARED in steps[0]  # shared with a later step
    assert "4.22.0" in steps[0] and "PR #50" in steps[0]


def test_members_render_in_their_tier_with_a_batch_chip() -> None:
    html = render(FACTS, JUDGEMENTS)
    row = re.search(r'<details class="row"[^>]*data-key="super-fr#577".*?</details>', html, re.S)
    assert row
    assert '<span class="tag batch">batch lifecycle</span>' in row.group(0)


def test_in_progress_is_in_flight_with_its_own_pill() -> None:
    assert "in-progress" in IN_FLIGHT
    html = render(FACTS, JUDGEMENTS)
    row = re.search(r'<details class="row"[^>]*data-key="super-fr#438"[^>]*>', html)
    assert row and 'data-inflight="1"' in row.group(0)
    assert '<span class="pill stage-in-progress">in-progress</span>' in html
    assert ".pill.stage-in-progress" in html


def test_no_batches_renders_no_batches_section() -> None:
    plain = Judgements.model_validate({"schema": 1, "tiers": [{"n": 1, "title": "Now"}]})
    assert '<section class="batches">' not in render(FACTS, plain)


def test_the_board_is_deterministic_with_batches() -> None:
    assert render(FACTS, JUDGEMENTS) == render(FACTS, JUDGEMENTS)
