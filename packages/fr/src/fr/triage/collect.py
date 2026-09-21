"""Collect the facts a triage board is built from (spec §3.B–C).

Pure: every function returns data. No Typer, no printing, no filesystem writes
— the command layer (`fr.commands.triage_cmd`) owns I/O.

`Forge` is the whole of decision d2's seam. `GhForge` is its one
implementation and the ONLY place `fr.triage` touches a forge; a second forge
is a second class, not an edit to the collector.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Protocol

from fr import gh
from fr.triage.model import Facts, Issue, PullRequest, Scope, Truncation

ISSUE_LIMIT = 1000
PR_LIMIT = 200
REPO_LIMIT = 200
BODY_LIMIT = 2000

# (owner login, repo name, issue number), lowercased — the key a closing reference names.
IssueRef = tuple[str, str, int]


class Forge(Protocol):
    """The forge calls triage needs — nothing more."""

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]: ...

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]: ...

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]: ...

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]: ...


class GhForge:
    """`Forge` backed by `fr.gh` (the `gh` CLI)."""

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]:
        return gh.list_repos(owner=owner)

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        return gh.list_issues(repo=repo, state=state, limit=limit)

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        return gh.list_prs(repo=repo, state=state, limit=limit)

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]:
        return gh.view_issue(repo, number)


def scope_repos(forge: Forge, scope: Scope) -> list[str]:
    """The `OWNER/REPO` slugs in *scope*, sorted."""
    if scope.kind == "repo":
        return [scope.target]
    repos = forge.list_repos(owner=scope.owner, limit=REPO_LIMIT)
    return sorted(f"{scope.owner}/{r['name']}" for r in repos)


def _ref(owner: str, name: str, number: int) -> IssueRef:
    """The normalised key: GitHub matches owner and repo names case-insensitively."""
    return (owner.lower(), name.lower(), number)


def parse_prs(repo: str, raw: Iterable[dict[str, Any]]) -> list[tuple[PullRequest, list[IssueRef]]]:
    """Parse `gh pr list` records from *repo* into PRs plus the issues each closes."""
    out: list[tuple[PullRequest, list[IssueRef]]] = []
    for r in raw:
        pr = PullRequest(
            repo=repo,
            number=r["number"],
            title=r["title"],
            state=r["state"],
            is_draft=r["isDraft"],
            merged_at=r.get("mergedAt"),
            url=r["url"],
            head_ref=r.get("headRefName") or "",
        )
        refs = [
            _ref(ref["repository"]["owner"]["login"], ref["repository"]["name"], ref["number"])
            for ref in r["closingIssuesReferences"]
        ]
        out.append((pr, refs))
    return out


def _in_scope(ref: IssueRef, scope: Scope) -> bool:
    owner, name, _ = ref
    if scope.kind == "repo":
        return f"{owner}/{name}" == scope.target.lower()
    return owner == scope.owner.lower()


def _pr_rank(pr: PullRequest) -> int:
    """Lower is more advanced: merged, open non-draft, open draft, closed unmerged."""
    if pr.state == "MERGED":
        return 0
    if pr.state == "OPEN":
        return 2 if pr.is_draft else 1
    return 3


def invert(
    prs: Iterable[tuple[PullRequest, list[IssueRef]]], scope: Scope
) -> dict[IssueRef, list[PullRequest]]:
    """Issue -> PRs, keyed on the REFERENCE's repository, never the PR's (review r2).

    References outside *scope* are dropped. Each issue's PRs are ordered most
    advanced first, ties broken by PR number, newest first. Pure: no forge.
    """
    links: dict[IssueRef, list[PullRequest]] = {}
    for pr, refs in prs:
        for ref in refs:
            if _in_scope(ref, scope):
                links.setdefault(ref, []).append(pr)
    for linked in links.values():
        linked.sort(key=lambda p: (_pr_rank(p), -p.number))
    return links


def _open_issue(repo: str, raw: dict[str, Any], prs: list[PullRequest]) -> Issue:
    return Issue(
        repo=repo,
        number=raw["number"],
        title=raw["title"],
        state="open",
        labels=[label["name"] for label in raw.get("labels") or []],
        url=raw["url"],
        created_at=raw.get("createdAt"),
        updated_at=raw.get("updatedAt"),
        body=(raw.get("body") or "")[:BODY_LIMIT],
        prs=prs,
    )


def collect_facts(
    forge: Forge,
    scope: Scope,
    *,
    now: datetime,
    issue_limit: int = ISSUE_LIMIT,
    pr_limit: int = PR_LIMIT,
) -> Facts:
    """Build the facts for *scope*: two bulk calls per repo, inverted."""
    repos = scope_repos(forge, scope)
    warnings: list[Truncation] = []
    raw_issues: list[tuple[str, dict[str, Any]]] = []
    parsed_prs: list[tuple[PullRequest, list[IssueRef]]] = []
    for repo in repos:
        issues = forge.list_issues(repo=repo, state="open", limit=issue_limit)
        if len(issues) == issue_limit:
            warnings.append(Truncation(source="issues", target=repo, limit=issue_limit))
        prs = forge.list_prs(repo=repo, state="all", limit=pr_limit)
        if len(prs) == pr_limit:
            warnings.append(Truncation(source="prs", target=repo, limit=pr_limit))
        raw_issues.extend((repo, i) for i in issues)
        parsed_prs.extend(parse_prs(repo, prs))
    links = invert(parsed_prs, scope)
    return Facts(
        scope=scope.name,
        kind=scope.kind,
        collected_at=now.isoformat(timespec="seconds"),
        repos=repos,
        issues=[
            _open_issue(repo, i, links.get(_ref(*repo.split("/", 1), i["number"]), []))
            for repo, i in raw_issues
        ],
        warnings=warnings,
    )
