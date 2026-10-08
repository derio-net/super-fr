"""Contract: `github-rest` returns the GraphQL backend's records (spec
2026-10-07-cloud-triage R2, §A field map; Test Plan 1).

The REST side is the `gh api` capture in `tests/fixtures/github_rest/` (a cloud
session, 2026-10-08). The GraphQL side is the `gh --json` capture already in the
repo (`tests/fixtures/triage/`, `tests/fixtures/gh/`, 2026-09-21 to 2026-10-06):
no host session was available to capture GraphQL at the same moment, so each
comparison states why its two captures describe the same forge state, and
narrows to the records or fields for which that holds. Nothing on either side is
hand-written.

Each §A exception is asserted on its own: the sidebar-only closing link (and the
node ids) REST cannot carry, `workflowName`, `startedAt` and `mergeable: null`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr import gh as fr_gh
from fr.gh import ISSUE_LIST_FIELDS
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import (
    RealGhRestClient,
    _closing_refs,
    _issue_record,
    _merge_state,
    _pr_record,
    _project,
)
from fr.triage import collect

from tests.unit.github_rest_support import REPO, FixtureGh, R, load

GRAPHQL = Path(__file__).resolve().parent.parent / "fixtures"
SHA_1038 = "f1919d411a43841293202aacdee44e29c1cf94e7"
OWNER, NAME = REPO.split("/")


def _graphql(name: str) -> Any:
    return json.loads((GRAPHQL / name).read_text())


def _graphql_client(monkeypatch: pytest.MonkeyPatch, answer: Any) -> RealGhClient:
    """The GraphQL-backed client, its one `gh` call answered by a capture."""
    monkeypatch.setattr(fr_gh, "_run_gh", lambda _args: json.dumps(answer))
    return RealGhClient()


def _ref_keys(refs: list[dict[str, Any]]) -> set[tuple[str, str, int]]:
    return {(r["repository"]["owner"]["login"], r["repository"]["name"], r["number"]) for r in refs}


# ---- pull requests: closed and merged ones, whose state no longer moves ----

_CLOSED_PRS = [p for p in _graphql("triage/super-fr-prs.json") if p["state"] != "OPEN"]


def test_the_captures_share_closed_and_merged_prs() -> None:
    assert len(_CLOSED_PRS) >= 10
    assert {p["state"] for p in _CLOSED_PRS} == {"CLOSED", "MERGED"}


@pytest.mark.parametrize("graphql_pr", _CLOSED_PRS, ids=lambda p: f"pr{p['number']}")
def test_a_closed_pr_record_matches_field_for_field(
    graphql_pr: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    graphql = {
        p["number"]: p
        for p in _graphql_client(monkeypatch, _graphql("triage/super-fr-prs.json")).list_prs(
            REPO, "all", 200
        )
    }[graphql_pr["number"]]
    rest = _pr_record(REPO, load(f"{R}/pulls/{graphql_pr['number']}"))
    for field in graphql:
        if field == "closingIssuesReferences":
            continue
        assert rest[field] == graphql[field], field
    # closingIssuesReferences: owner, repo and number agree. The GraphQL node ids
    # (`id`, `repository.id`, `owner.id`) are a §A gap: REST parses the text and
    # carries none; collect reads none.
    assert _ref_keys(rest["closingIssuesReferences"]) == _ref_keys(
        graphql["closingIssuesReferences"]
    )
    assert all("id" not in r for r in rest["closingIssuesReferences"])
    # And collect parses both into the same PullRequest and issue refs: the REST
    # record narrowed to the fields this older GraphQL capture asked for
    # (`author`, `createdAt`, `headRefOid` and `isCrossRepository` postdate it),
    # the refs as a set (REST lists them in text order, GraphQL in its own).
    [(pr_rest, refs_rest)] = collect.parse_prs(REPO, [{f: rest[f] for f in graphql}])
    [(pr_graphql, refs_graphql)] = collect.parse_prs(REPO, [graphql])
    assert pr_rest == pr_graphql
    assert set(refs_rest) == set(refs_graphql)


def test_the_sidebar_closing_link_is_the_one_gap_rest_cannot_see() -> None:
    """§A row 1's gap, stated on captured records: REST finds a closing issue
    only through the PR's text. In this capture every GraphQL closing reference
    is in its PR's title or body (none was linked by hand in the sidebar); the
    same PR with its text emptied would close nothing for REST, while GraphQL's
    link would stand."""
    for graphql in _CLOSED_PRS:
        pull = load(f"{R}/pulls/{graphql['number']}")
        textual = _ref_keys(_closing_refs(REPO, pull["title"], pull["body"]))
        assert _ref_keys(graphql["closingIssuesReferences"]) - textual == set()
        assert _closing_refs(REPO, "", "") == []


# ---- PR 1044, closed straight after its gh capture ----


def test_pr_1044_view_matches_the_gh_capture() -> None:
    graphql = _graphql("gh/pr-view-adopt.json")
    rest = RealGhRestClient(run=FixtureGh()).pr_view(REPO, 1044)
    record = _pr_record(REPO, load(f"{R}/pulls/1044"))
    assert rest["state"] == graphql["state"]
    assert rest["draft"] == graphql["isDraft"]
    assert rest["head_ref"] == graphql["headRefName"]
    assert rest["base_ref"] == graphql["baseRefName"]
    assert rest["title"] == graphql["title"]
    assert rest["body"] == graphql["body"]
    assert (record["number"], record["url"]) == (graphql["number"], graphql["url"])


# ---- checks: PR 1038's head, a finished commit ----


def _graphql_moment(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The REST rollup narrowed to the GraphQL capture's moment (2026-10-06): a
    finished commit's check runs never change, but one more ran on 2026-10-07
    (the post-merge `status / status`), after the GraphQL capture."""
    return [e for e in entries if str(e.get("startedAt") or "") < "2026-10-07"]


def test_the_check_rollup_matches_entry_for_entry() -> None:
    graphql = _graphql("triage/super-fr-rerun-checks.json")
    rest_all = RealGhRestClient(run=FixtureGh())._rollup_for(REPO, SHA_1038)
    later = [e for e in rest_all if e not in _graphql_moment(rest_all)]
    assert [(e["name"], e["startedAt"][:10]) for e in later] == [("status / status", "2026-10-07")]
    rest = _graphql_moment(rest_all)
    by_url = {e["detailsUrl"]: e for e in rest}
    assert len(rest) == len(graphql) == len(by_url)
    for entry in graphql:
        assert by_url[entry["detailsUrl"]] == entry  # every field, workflowName included
    assert collect._checks(rest) == collect._checks(graphql)


def test_workflow_name_comes_from_the_actions_run_of_the_check_suite() -> None:
    """§A row 3: each check run's `workflowName` is the name of the Actions run
    whose `check_suite_id` is its suite — the names GraphQL gave."""
    graphql = _graphql("triage/super-fr-rerun-checks.json")
    rest = _graphql_moment(RealGhRestClient(run=FixtureGh())._rollup_for(REPO, SHA_1038))
    assert sorted({e["workflowName"] for e in rest}) == sorted({e["workflowName"] for e in graphql})
    assert {(e["workflowName"], e["name"]) for e in collect._latest_runs(rest)} == {
        (e["workflowName"], e["name"]) for e in collect._latest_runs(graphql)
    }


def test_started_at_empty_and_graphql_zero_time_read_the_same() -> None:
    """§A row 2: REST never produces GraphQL's `0001-` zero time — a run not yet
    started has an empty `startedAt` — and `collect._latest_runs` ranks the two
    spellings identically. Neither capture holds an unstarted run, so the case
    is a captured completed run with its start and finish blanked both ways (a
    derived variant for this one assertion, not a fixture)."""
    rest = RealGhRestClient(run=FixtureGh())._rollup_for(REPO, SHA_1038)
    assert not any(str(e.get("startedAt")).startswith("0001-") for e in rest)
    base = dict(rest[0])
    unstarted_rest = {**base, "startedAt": "", "status": "QUEUED", "conclusion": ""}
    unstarted_graphql = {**unstarted_rest, "startedAt": "0001-01-01T00:00:00Z"}
    for variant in (unstarted_rest, unstarted_graphql):
        latest = collect._latest_runs([base, variant])
        assert latest == [variant]
        assert collect._checks([base, variant]) == {"pass": 0, "fail": 0, "pending": 1}


# ---- mergeable ----


def test_mergeable_null_is_unknown() -> None:
    """§A row 4: REST's `mergeable: null` (GitHub still computing, or a closed
    PR) is GraphQL's `UNKNOWN`, which collect reads as GraphQL's null."""
    pull = load(f"{R}/pulls/508")
    assert pull["mergeable"] is None
    assert _merge_state(pull) == ("UNKNOWN", "UNKNOWN")


def test_mergeable_false_is_the_graphql_conflicting_enum() -> None:
    """Both captures hold a conflicting open PR (GraphQL: #560 on 2026-09-22;
    REST: #1080 now); both read CONFLICTING / DIRTY."""
    graphql = _graphql("triage/super-fr-open-prs.json")[0]
    rest = RealGhRestClient(run=FixtureGh()).list_open_prs(REPO, 1)[0]
    assert (rest["mergeable"], rest["mergeStateStatus"]) == (
        graphql["mergeable"],
        graphql["mergeStateStatus"],
    )
    assert sorted(rest) == sorted(
        {*graphql, "author", "createdAt", "headRefOid", "isCrossRepository"}
    )


# ---- issues ----

_ISSUES = _graphql("triage/super-fr-issues.json")


@pytest.mark.parametrize("graphql_issue", _ISSUES, ids=lambda i: f"issue{i['number']}")
def test_an_issue_record_matches(
    graphql_issue: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    graphql = {
        i["number"]: i
        for i in _graphql_client(monkeypatch, _ISSUES).list_issues(REPO, "open", 1000)
    }[graphql_issue["number"]]
    rest = _project(_issue_record(load(f"{R}/issues/{graphql['number']}")), ISSUE_LIST_FIELDS)
    assert sorted(rest) == sorted(graphql)
    if rest["updatedAt"] == graphql["updatedAt"]:
        # The same moment: every field, labels' node ids and colours included.
        assert rest == graphql
        return
    # Updated since the GraphQL capture: a later moment. What cannot move agrees,
    # and only what an update moves (its stamp, its labels) differs.
    assert rest["updatedAt"] > graphql["updatedAt"]
    for field in ("number", "url", "createdAt"):
        assert rest[field] == graphql[field], field
    assert {f for f in graphql if rest[f] != graphql[f]} <= {"updatedAt", "labels"}


def test_at_least_one_issue_is_at_the_same_moment() -> None:
    same = [i for i in _ISSUES if load(f"{R}/issues/{i['number']}")["updated_at"] == i["updatedAt"]]
    assert same, "no unchanged issue left to compare whole"


@pytest.mark.parametrize(
    "graphql_issue",
    _graphql("triage/dedupe-calibration.json"),
    ids=lambda i: f"issue{i['number']}",
)
def test_an_issue_view_matches_the_dedupe_capture(graphql_issue: dict[str, Any]) -> None:
    """`gh issue view --json number,title,body,state` (2026-10-06, bodies cut to
    collect's 2,000 characters) against REST. An issue closed on or after that
    day may have closed after the capture: its state is the one field allowed
    to differ."""
    raw = load(f"{R}/issues/{graphql_issue['number']}")
    rest = _issue_record(raw)
    assert rest["title"] == graphql_issue["title"]
    assert rest["body"][: collect.BODY_LIMIT] == graphql_issue["body"]
    if rest["state"] != graphql_issue["state"]:
        assert graphql_issue["state"] == "OPEN"
        assert raw["closed_at"] >= "2026-10-06"
