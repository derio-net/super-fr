"""The pure issue-intake rule (spec 2026-11-17-triage-intake R2, R6)."""

from __future__ import annotations

from typing import Any

from fr.triage.intake import (
    NOT_COLLECTED,
    intake_reason,
    issue_reason,
    rejected_members,
    untrusted_issues,
)
from fr.triage.model import Batch, Facts, Issue, TriageConfig

REPO = "derio-net/super-fr"
TRUSTED = frozenset({"alice"})


def _issue(number: int, **kw: Any) -> Issue:
    return Issue(
        repo=REPO,
        number=number,
        title=f"issue {number}",
        state=kw.pop("state", "open"),
        url=f"https://github.com/{REPO}/issues/{number}",
        **kw,
    )


def _facts(*issues: Issue, **kw: Any) -> Facts:
    return Facts(
        schema=13,
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-11-17T00:00:00+00:00",
        repos=[REPO],
        issues=list(issues),
        **kw,
    )


def test_a_trusted_login_is_eligible_case_insensitively_without_an_association() -> None:
    assert intake_reason("Alice", None, [], TRUSTED) is None


def test_a_trusted_association_is_eligible() -> None:
    for assoc in ("OWNER", "MEMBER", "COLLABORATOR"):
        assert intake_reason("bob", assoc, [], TRUSTED) is None


def test_the_ready_fr_label_admits() -> None:
    assert intake_reason("bob", "NONE", ["bug", "ready-fr"], TRUSTED) is None


def test_an_outside_author_is_ineligible_with_a_reason_naming_author_and_association() -> None:
    for assoc in ("CONTRIBUTOR", "NONE"):
        assert intake_reason("bob", assoc, [], TRUSTED) == f"author bob is {assoc}"


def test_an_unread_author_or_association_never_admits() -> None:
    assert intake_reason(None, "OWNER", [], TRUSTED) is None  # association admits on its own
    assert intake_reason(None, None, [], TRUSTED) == "author not read"
    assert intake_reason("bob", None, [], TRUSTED) == "author bob: association not read"
    assert intake_reason(None, "NONE", [], TRUSTED) == "author not read"


def test_issue_reason_trusts_the_viewer_and_the_pr_authors_of_the_issues_repo() -> None:
    facts = _facts(
        _issue(1, author="operator"),
        _issue(2, author="Bot"),
        _issue(3, author="eve", author_association="NONE"),
        viewer="operator",
        config={REPO: TriageConfig(pr_authors=["bot"])},
    )
    one, two, three = facts.issues
    assert issue_reason(one, facts) is None
    assert issue_reason(two, facts) is None
    assert issue_reason(three, facts) == "author eve is NONE"


def _batch(*ids: str) -> Batch:
    return Batch(id="b", title="t", ids=list(ids))


def test_rejected_members_flags_ineligible_open_or_closed_and_uncollected() -> None:
    facts = _facts(
        _issue(1, author="eve", author_association="NONE"),
        _issue(2, author="eve", author_association="NONE", state="closed"),
        _issue(3, author="eve", author_association="MEMBER"),
        viewer="operator",
    )
    got = rejected_members(_batch("super-fr#1", "super-fr#2", "super-fr#3", "super-fr#9"), facts)
    assert got == [
        ("super-fr#1", "author eve is NONE"),
        ("super-fr#2", "author eve is NONE"),
        ("super-fr#9", NOT_COLLECTED),
    ]


def test_an_eligible_batch_has_no_rejected_members() -> None:
    facts = _facts(_issue(1, author="operator"), viewer="operator")
    assert rejected_members(_batch("super-fr#1"), facts) == []


def test_untrusted_issues_lists_open_ineligible_ones_only() -> None:
    facts = _facts(
        _issue(1, author="eve", author_association="NONE"),
        _issue(2, author="eve", author_association="NONE", state="closed"),
        _issue(3, author="eve", author_association="NONE", labels=["ready-fr"]),
        _issue(4, author="operator"),
        viewer="operator",
    )
    assert [(i.number, r) for i, r in untrusted_issues(facts)] == [(1, "author eve is NONE")]


def test_the_debt_workflows_bot_is_admitted_so_its_digest_body_survives() -> None:
    facts = _facts(_issue(1, author="app/github-actions"), viewer="operator")
    assert issue_reason(facts.issues[0], facts) is None
