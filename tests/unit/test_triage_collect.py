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


# ------------------------------------------------- P2.T4 org scope, skipped


def _org_forge(**kw: Any) -> FakeForge:
    """example-org with three fictional repos, one issue each, no PRs."""
    names = ["alpha", "beta", "gamma"]
    return FakeForge(
        repos=[{"name": n, "isArchived": False} for n in names],
        issues={f"example-org/{n}": [_issue(i + 1, title=n)] for i, n in enumerate(names)},
        prs={f"example-org/{n}": [] for n in names},
        **kw,
    )


ORG = Scope(kind="org", target="example-org")


def test_a_repo_whose_issue_list_fails_is_skipped_and_the_rest_collect() -> None:
    forge = _org_forge(failing={"example-org/beta": "issues are disabled for this repository"})

    facts = collect_facts(forge, ORG, now=NOW)

    assert [(s.repo, s.reason) for s in facts.skipped] == [
        ("example-org/beta", "issues are disabled for this repository")
    ]
    assert sorted(i.repo for i in facts.issues) == ["example-org/alpha", "example-org/gamma"]
    # Nothing more is asked of a skipped repo.
    assert "example-org/beta" not in {kw["repo"] for kw in forge.called("list_prs")}


def test_a_repo_whose_pr_list_fails_is_skipped_too() -> None:
    forge = _org_forge()
    real = forge.list_prs

    def list_prs(*, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        if repo == "example-org/gamma":
            raise ForgeError("HTTP 403")
        return real(repo=repo, state=state, limit=limit)

    forge.list_prs = list_prs  # type: ignore[method-assign]

    facts = collect_facts(forge, ORG, now=NOW)

    assert [(s.repo, s.reason) for s in facts.skipped] == [("example-org/gamma", "HTTP 403")]
    assert sorted(i.repo for i in facts.issues) == ["example-org/alpha", "example-org/beta"]


def test_in_repo_scope_a_failing_repo_is_an_error_not_an_empty_board() -> None:
    forge = FakeForge(issues={}, prs={}, failing={"derio-net/super-fr": "no access"})

    with pytest.raises(ForgeError, match="no access"):
        collect_facts(forge, SUPER_FR, now=NOW)


def test_the_repo_list_is_asked_for_its_limit_and_archived_repos_are_dropped() -> None:
    forge = _org_forge()
    forge.repos = [*forge.repos, {"name": "old", "isArchived": True}]

    facts = collect_facts(forge, ORG, now=NOW)

    assert REPO_LIMIT == 200
    assert forge.called("list_repos") == [{"owner": "example-org", "limit": 200}]
    assert facts.repos == ["example-org/alpha", "example-org/beta", "example-org/gamma"]
    assert facts.warnings == []


def test_a_repo_list_returning_exactly_its_limit_warns_even_with_archived_repos() -> None:
    # The warning counts what the forge returned, BEFORE archived repos are dropped:
    # 200 returned, 5 of them archived, is still a list that may have been cut short.
    names = [f"repo-{n:03d}" for n in range(REPO_LIMIT)]
    forge = FakeForge(
        repos=[{"name": n, "isArchived": i < 5} for i, n in enumerate(names)],
        issues={f"example-org/{n}": [] for n in names},
        prs={f"example-org/{n}": [] for n in names},
    )

    facts = collect_facts(forge, ORG, now=NOW)

    assert len(facts.repos) == REPO_LIMIT - 5
    assert [(w.source, w.target, w.limit) for w in facts.warnings] == [
        ("repos", "example-org", REPO_LIMIT)
    ]


# ------------------------------------------------ P2.T4 judged but closed


def _closed_view(number: int) -> dict[str, Any]:
    """What `gh issue view --json number,title,body,labels,state,url,closedAt` returns."""
    return {
        "number": number,
        "title": f"closed #{number}",
        "body": "x" * 3000,
        "labels": [{"name": "bug"}],
        "state": "CLOSED",
        "url": f"https://github.com/derio-net/super-fr/issues/{number}",
        "closedAt": "2026-09-20T10:00:00Z",
    }


def test_a_judged_issue_no_longer_open_is_viewed_and_appears_closed() -> None:
    forge = _super_fr_forge()
    forge.closed = {("derio-net/super-fr", 430): _closed_view(430)}
    open_key = f"super-fr#{ISSUES[0]['number']}"

    facts = collect_facts(forge, SUPER_FR, now=NOW, judged=["super-fr#430", open_key])

    assert forge.called("view_issue") == [{"repo": "derio-net/super-fr", "number": 430}]
    closed = next(i for i in facts.issues if i.key == "super-fr#430")
    assert closed.state == "closed"
    assert closed.stage == "closed"
    assert closed.closed_at == "2026-09-20T10:00:00Z"
    assert closed.url == "https://github.com/derio-net/super-fr/issues/430"
    assert len(closed.body) == BODY_LIMIT
    # Its PRs come from the same inversion as the open issues'.
    assert [p.number for p in closed.prs] == [508, 517]


def test_no_view_for_open_keys_or_keys_outside_the_scope() -> None:
    forge = _super_fr_forge()

    collect_facts(
        forge,
        SUPER_FR,
        now=NOW,
        judged=[f"super-fr#{i['number']}" for i in ISSUES] + ["other-repo#1"],
    )

    assert forge.called("view_issue") == []


@pytest.mark.parametrize(
    "reason", ["Could not resolve to an issue", "HTTP 502", "API rate limit exceeded"]
)
def test_every_failed_view_is_recorded_as_unviewed_never_dropped(reason: str) -> None:
    """Review r-p2-unviewed: a rate limit must not make a live judgement look orphaned."""
    forge = _super_fr_forge()
    forge.closed = {("derio-net/super-fr", 430): _closed_view(430)}
    real = forge.view_issue

    def view_issue(*, repo: str, number: int) -> dict[str, Any]:
        if number == 99999:
            raise ForgeError(reason)
        return real(repo=repo, number=number)

    forge.view_issue = view_issue  # type: ignore[method-assign]

    facts = collect_facts(forge, SUPER_FR, now=NOW, judged=["super-fr#99999", "Super-FR#430"])

    assert "super-fr#99999" not in {i.key for i in facts.issues}
    assert [(u.key, u.reason) for u in facts.unviewed] == [("super-fr#99999", reason)]
    # The view that succeeded is unaffected.
    assert "super-fr#430" in {i.key for i in facts.issues}


def test_unviewed_round_trips_through_facts_json(tmp_path: Path) -> None:
    from fr.triage.model import load_facts

    forge = _super_fr_forge()

    def view_issue(*, repo: str, number: int) -> dict[str, Any]:
        raise ForgeError("HTTP 502")

    forge.view_issue = view_issue  # type: ignore[method-assign]
    facts = collect_facts(forge, SUPER_FR, now=NOW, judged=["super-fr#99999"])
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(facts.to_json()), encoding="utf-8")

    loaded = load_facts(path)

    assert facts.to_json()["schema"] == 1
    assert [(u.key, u.reason) for u in loaded.unviewed] == [("super-fr#99999", "HTTP 502")]


def test_org_scope_views_a_judged_closed_issue_in_its_own_repo() -> None:
    forge = _org_forge()
    forge.closed = {("example-org/beta", 40): {**_closed_view(40), "url": "u"}}

    facts = collect_facts(forge, ORG, now=NOW, judged=["beta#40"])

    assert forge.called("view_issue") == [{"repo": "example-org/beta", "number": 40}]
    assert "beta#40" in {i.key for i in facts.issues}


# ------------------------------------------------------------ P2.T4 GhForge


def test_gh_forge_raises_the_triage_forge_error_not_gh_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr import gh
    from fr.triage.collect import GhForge

    def boom(args: list[str]) -> str:
        raise gh.GhError("HTTP 404: Not Found", stderr="HTTP 404", returncode=1)

    monkeypatch.setattr(gh, "_run_gh", boom)

    for call in (
        lambda f: f.list_repos(owner="example-org", limit=200),
        lambda f: f.list_issues(repo="example-org/alpha", state="open", limit=1000),
        lambda f: f.list_prs(repo="example-org/alpha", state="all", limit=200),
        lambda f: f.view_issue(repo="example-org/alpha", number=1),
    ):
        with pytest.raises(ForgeError, match="HTTP 404") as exc:
            call(GhForge())
        assert not isinstance(exc.value, gh.GhError)


def test_gh_forge_with_no_gh_binary_raises_a_one_line_forge_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.collect import GhForge

    monkeypatch.setenv("PATH", str(tmp_path))  # an empty dir: no gh anywhere

    with pytest.raises(ForgeError) as exc:
        GhForge().list_issues(repo="example-org/alpha", state="open", limit=1000)

    message = str(exc.value)
    assert "\n" not in message
    assert "gh" in message and "install" in message.lower()


def test_gh_forge_asks_gh_for_archived_repos_too_so_the_limit_is_countable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr import gh
    from fr.triage.collect import GhForge

    captured: list[list[str]] = []

    def fake(args: list[str]) -> str:
        captured.append(args)
        return json.dumps([{"name": "a", "isArchived": False}, {"name": "b", "isArchived": True}])

    monkeypatch.setattr(gh, "_run_gh", fake)

    repos = GhForge().list_repos(owner="example-org", limit=7)

    assert [r["name"] for r in repos] == ["a", "b"]
    assert captured[0][captured[0].index("--limit") + 1] == "7"


def test_fr_triage_touches_gh_only_in_collect() -> None:
    """Nothing above collect.py knows gh exists (decision d2, review r-p1-gherror-leak)."""
    import fr.commands.triage_cmd as cmd
    import fr.triage as pkg

    sources = {Path(cmd.__file__): Path(cmd.__file__).read_text(encoding="utf-8")}
    for path in Path(pkg.__file__).parent.glob("*.py"):
        sources[path] = path.read_text(encoding="utf-8")
    offenders = [
        p.name
        for p, text in sources.items()
        if p.name != "collect.py"
        and ("fr.gh" in text or "GhError" in text or "from fr import gh" in text)
    ]
    assert offenders == []


# ------------------------------------------------ review r-p2-case


def test_a_judged_key_differing_only_by_case_is_not_held_twice() -> None:
    """The reviewer's repro: open issue #5 judged as `Repo#5` appeared twice."""
    scope = Scope(kind="repo", target="o/repo")
    forge = FakeForge(
        issues={"o/repo": [_issue(5)]},
        prs={"o/repo": []},
        closed={("o/repo", 5): {**_closed_view(5), "url": "u"}},
    )

    facts = collect_facts(forge, scope, now=NOW, judged=["Repo#5"])

    assert [i.key for i in facts.issues] == ["repo#5"]
    assert forge.called("view_issue") == []


# ------------------------------------------------ review r-p2-empty


def test_org_scope_with_every_repo_skipped_is_an_error_naming_each_reason() -> None:
    forge = _org_forge(
        failing={
            "example-org/alpha": "HTTP 403",
            "example-org/beta": "issues are disabled",
            "example-org/gamma": "HTTP 502",
        }
    )

    with pytest.raises(ForgeError) as exc:
        collect_facts(forge, ORG, now=NOW)

    message = str(exc.value)
    for repo, reason in [
        ("example-org/alpha", "HTTP 403"),
        ("example-org/beta", "issues are disabled"),
        ("example-org/gamma", "HTTP 502"),
    ]:
        assert f"{repo}: {reason}" in message


def test_org_scope_with_no_repos_at_all_is_an_error_not_a_clean_board() -> None:
    forge = FakeForge(repos=[{"name": "old", "isArchived": True}], issues={}, prs={})

    with pytest.raises(ForgeError, match="example-org"):
        collect_facts(forge, ORG, now=NOW)
