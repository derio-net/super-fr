"""`collect`: PR -> issue inversion, limits, truncation, org scope (spec §3.C).

Plan 2026-09-21-fr-triage, P2.T2 and P2.T4. Repo-scope cases run over the
captured super-fr fixtures. The cross-repo and org-scope cases use fictional
repo names, and any synthetic PR is a deep copy of a captured record with only
the reference's `repository.name`/`owner.login`/`number` changed, so the
reference shape is always the captured one.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.triage.collect import (
    BODY_LIMIT,
    ISSUE_LIMIT,
    PR_LIMIT,
    REPO_LIMIT,
    collect_facts,
    invert,
    parse_prs,
)
from fr.triage.errors import ForgeError
from fr.triage.model import Facts, Scope

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "triage"
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
SUPER_FR = Scope(kind="repo", target="derio-net/super-fr")


def _load(name: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


ISSUES = _load("super-fr-issues.json")
PRS = _load("super-fr-prs.json")


def _captured_pr_with_refs() -> dict[str, Any]:
    """A captured PR record that carries at least one closing reference."""
    return next(p for p in PRS if p["closingIssuesReferences"])


def _pr_closing(*, owner: str, name: str, number: int, pr_number: int) -> dict[str, Any]:
    """A deep copy of a captured PR whose single reference names owner/name#number."""
    pr = copy.deepcopy(_captured_pr_with_refs())
    ref = pr["closingIssuesReferences"][0]
    ref["repository"]["owner"]["login"] = owner
    ref["repository"]["name"] = name
    ref["number"] = number
    pr["closingIssuesReferences"] = [ref]
    pr["number"] = pr_number
    return pr


def _issue(number: int, *, title: str = "t") -> dict[str, Any]:
    """A deep copy of a captured issue record, renumbered."""
    issue = copy.deepcopy(ISSUES[0])
    issue["number"] = number
    issue["title"] = title
    return issue


class FakeForge:
    """A Forge serving per-repo canned data and recording every call."""

    def __init__(
        self,
        *,
        issues: dict[str, list[dict[str, Any]]],
        prs: dict[str, list[dict[str, Any]]],
        repos: list[dict[str, Any]] | None = None,
        failing: dict[str, str] | None = None,
        closed: dict[tuple[str, int], dict[str, Any]] | None = None,
    ) -> None:
        self.issues = issues
        self.prs = prs
        self.repos = repos or []
        self.failing = failing or {}
        self.closed = closed or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_repos", {"owner": owner, "limit": limit}))
        return self.repos

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_issues", {"repo": repo, "state": state, "limit": limit}))
        if repo in self.failing:
            raise ForgeError(self.failing[repo])
        return self.issues[repo]

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_prs", {"repo": repo, "state": state, "limit": limit}))
        return self.prs[repo]

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]:
        self.calls.append(("view_issue", {"repo": repo, "number": number}))
        return self.closed[(repo, number)]

    def called(self, name: str) -> list[dict[str, Any]]:
        return [kw for n, kw in self.calls if n == name]


def _super_fr_forge() -> FakeForge:
    return FakeForge(
        issues={"derio-net/super-fr": ISSUES},
        prs={"derio-net/super-fr": PRS},
        closed={},
    )


# ------------------------------------------------------------ P2.T2 inversion


def test_each_open_issue_carries_the_prs_that_close_it() -> None:
    facts = collect_facts(_super_fr_forge(), SUPER_FR, now=NOW)

    assert isinstance(facts, Facts)
    by_number = {i.number: i for i in facts.issues}
    expected: dict[int, set[int]] = {}
    for pr in PRS:
        for ref in pr["closingIssuesReferences"]:
            expected.setdefault(ref["number"], set()).add(pr["number"])
    for issue in ISSUES:
        got = {p.number for p in by_number[issue["number"]].prs}
        assert got == expected.get(issue["number"], set()), issue["number"]
    # The fixture has real links: #432, #472 and #529 are all closed by draft PR #534.
    assert [p.number for p in by_number[432].prs] == [534]


def test_the_most_advanced_linked_pr_comes_first() -> None:
    links = invert(parse_prs("derio-net/super-fr", PRS), SUPER_FR)

    # #429: open #480 and #478, draft #479 -> non-draft open PRs before the draft.
    ranked = [(p.state, p.is_draft) for p in links[("derio-net", "super-fr", 429)]]
    assert ranked[-1] == ("OPEN", True)
    assert all(r == ("OPEN", False) for r in ranked[:-1])
    # #430: merged #508 beats closed-unmerged #517.
    assert [p.number for p in links[("derio-net", "super-fr", 430)]] == [508, 517]


def test_bodies_are_truncated_to_2000_characters() -> None:
    assert BODY_LIMIT == 2000
    assert max(len(i["body"]) for i in ISSUES) > BODY_LIMIT  # the fixture exercises it

    facts = collect_facts(_super_fr_forge(), SUPER_FR, now=NOW)

    raw = {i["number"]: i["body"] for i in ISSUES}
    for issue in facts.issues:
        assert issue.body == raw[issue.number][:BODY_LIMIT]


def test_both_limits_are_passed_explicitly() -> None:
    forge = _super_fr_forge()

    collect_facts(forge, SUPER_FR, now=NOW)

    assert (ISSUE_LIMIT, PR_LIMIT) == (1000, 200)
    assert forge.called("list_issues") == [
        {"repo": "derio-net/super-fr", "state": "open", "limit": 1000}
    ]
    assert forge.called("list_prs") == [
        {"repo": "derio-net/super-fr", "state": "all", "limit": 200}
    ]


def test_a_list_returning_exactly_its_limit_warns_possibly_truncated() -> None:
    facts = collect_facts(
        _super_fr_forge(), SUPER_FR, now=NOW, issue_limit=len(ISSUES), pr_limit=len(PRS)
    )

    warned = {(w.source, w.target, w.limit) for w in facts.warnings}
    assert warned == {
        ("issues", "derio-net/super-fr", len(ISSUES)),
        ("prs", "derio-net/super-fr", len(PRS)),
    }


def test_no_warning_below_the_limit() -> None:
    assert collect_facts(_super_fr_forge(), SUPER_FR, now=NOW).warnings == []


def test_a_cross_repo_reference_attaches_to_the_referenced_repos_issue() -> None:
    scope = Scope(kind="org", target="example-org")
    cross = _pr_closing(owner="example-org", name="beta", number=7, pr_number=900)
    forge = FakeForge(
        repos=[{"name": "alpha", "isArchived": False}, {"name": "beta", "isArchived": False}],
        issues={"example-org/alpha": [_issue(7)], "example-org/beta": [_issue(7)]},
        prs={"example-org/alpha": [cross], "example-org/beta": []},
    )

    facts = collect_facts(forge, scope, now=NOW)

    by_key = {i.key: i for i in facts.issues}
    assert [p.number for p in by_key["beta#7"].prs] == [900]
    assert by_key["beta#7"].prs[0].repo == "example-org/alpha"  # where the PR lives
    assert by_key["alpha#7"].prs == []


@pytest.mark.parametrize(
    ("scope", "owner", "name"),
    [
        # repo scope: any other repo is outside it, even the same owner's
        (Scope(kind="repo", target="example-org/alpha"), "example-org", "beta"),
        # org scope: any other owner is outside it
        (Scope(kind="org", target="example-org"), "someone-else", "alpha"),
    ],
)
def test_a_reference_outside_the_scope_is_dropped(scope: Scope, owner: str, name: str) -> None:
    stray = _pr_closing(owner=owner, name=name, number=7, pr_number=901)

    links = invert(parse_prs("example-org/alpha", [stray]), scope)

    assert links == {}
