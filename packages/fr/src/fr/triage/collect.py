"""Collect the facts a triage board is built from (spec §3.B–C).

Pure: every function returns data. No Typer, no printing, no filesystem writes
— the command layer (`fr.commands.triage_cmd`) owns I/O.

`Forge` is the whole of decision d2's seam. `GhForge` is its one
implementation and the ONLY place `fr.triage` touches a forge; a second forge
is a second class, not an edit to the collector.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Protocol

from fr import gh
from fr.triage.errors import ForgeError
from fr.triage.model import (
    SCHEMA,
    Facts,
    Issue,
    IssueState,
    PullRequest,
    Scope,
    Skipped,
    Truncation,
    Unviewed,
    issue_key,
    normalize_key,
)
from fr.triage.stage import pr_rank

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


GH_MISSING = (
    "gh (the GitHub CLI) was not found on PATH: install it from https://cli.github.com "
    "and run `gh auth login`"
)


@contextmanager
def _forge_errors() -> Iterator[None]:
    """Translate every way a `gh` call fails into triage's own `ForgeError`."""
    try:
        yield
    except gh.GhError as exc:
        raise ForgeError(str(exc)) from exc
    except FileNotFoundError as exc:  # subprocess could not exec `gh` at all
        raise ForgeError(GH_MISSING) from exc


class GhForge:
    """`Forge` backed by `fr.gh` (the `gh` CLI). Raises only `ForgeError`."""

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]:
        # Archived repos included: the caller counts the raw list against its limit
        # before dropping them, or a full list with archived repos would not warn.
        with _forge_errors():
            return gh.list_repos(owner=owner, limit=limit, include_archived=True)

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        with _forge_errors():
            return gh.list_issues(repo=repo, state=state, limit=limit)

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        with _forge_errors():
            return gh.list_prs(repo=repo, state=state, limit=limit)

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]:
        with _forge_errors():
            return gh.view_issue(repo, number)


def scope_repos(
    forge: Forge, scope: Scope, *, repo_limit: int = REPO_LIMIT
) -> tuple[list[str], list[Truncation]]:
    """The non-archived `OWNER/REPO` slugs in *scope*, sorted, plus any truncation.

    `list_repos` returns archived repos too, so a list that came back exactly
    at its limit is detected on the raw count (review r-p1-repo-cap).
    """
    if scope.kind == "repo":
        return [scope.target], []
    raw = forge.list_repos(owner=scope.owner, limit=repo_limit)
    warnings = (
        [Truncation(source="repos", target=scope.owner, limit=repo_limit)]
        if len(raw) == repo_limit
        else []
    )
    repos = sorted(f"{scope.owner}/{r['name']}" for r in raw if not r.get("isArchived", False))
    return repos, warnings


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
        linked.sort(key=lambda p: (pr_rank(p), -p.number))
    return links


def _issue(repo: str, raw: dict[str, Any], prs: list[PullRequest], *, state: IssueState) -> Issue:
    return Issue(
        repo=repo,
        number=raw["number"],
        title=raw["title"],
        state=state,
        labels=[label["name"] for label in raw.get("labels") or []],
        url=raw["url"],
        created_at=raw.get("createdAt"),
        updated_at=raw.get("updatedAt"),
        closed_at=raw.get("closedAt"),
        body=(raw.get("body") or "")[:BODY_LIMIT],
        prs=prs,
    )


def _judged_elsewhere(
    judged: Iterable[str], open_keys: set[str], repos: list[str]
) -> list[tuple[str, int]]:
    """(repo, number) for each judgement key not in the open set, in a collected repo.

    A key naming no collected repo is left for `check` to call orphaned.
    """
    by_name = {repo.split("/", 1)[1].lower(): repo for repo in repos}
    wanted: list[tuple[str, int]] = []
    for key in sorted({normalize_key(k) for k in judged} - open_keys):
        name, _, number = key.rpartition("#")
        repo = by_name.get(name)
        if repo is not None and number.isdigit():
            wanted.append((repo, int(number)))
    return wanted


def collect_facts(
    forge: Forge,
    scope: Scope,
    *,
    now: datetime,
    judged: Iterable[str] = (),
    issue_limit: int = ISSUE_LIMIT,
    pr_limit: int = PR_LIMIT,
    repo_limit: int = REPO_LIMIT,
) -> Facts:
    """Build the facts for *scope*: two bulk calls per repo, inverted.

    In org scope a repo whose lists fail is recorded under `skipped` and the
    rest still collect; in repo scope the one repo failing is the error, and
    in org scope so is collecting no repo at all (review r-p2-empty).
    Each *judged* key no longer open costs one `view_issue`, so the extra
    calls are bounded by the judgements, never by the backlog.
    """
    repos, warnings = scope_repos(forge, scope, repo_limit=repo_limit)
    skipped: list[Skipped] = []
    collected: list[str] = []
    raw_issues: list[tuple[str, dict[str, Any]]] = []
    parsed_prs: list[tuple[PullRequest, list[IssueRef]]] = []
    for repo in repos:
        try:
            issues = forge.list_issues(repo=repo, state="open", limit=issue_limit)
            prs = forge.list_prs(repo=repo, state="all", limit=pr_limit)
        except ForgeError as exc:
            if scope.kind == "repo":
                raise
            skipped.append(Skipped(repo=repo, reason=str(exc)))
            continue
        collected.append(repo)
        if len(issues) == issue_limit:
            warnings.append(Truncation(source="issues", target=repo, limit=issue_limit))
        if len(prs) == pr_limit:
            warnings.append(Truncation(source="prs", target=repo, limit=pr_limit))
        raw_issues.extend((repo, i) for i in issues)
        parsed_prs.extend(parse_prs(repo, prs))
    if not collected:
        # Nothing to show is an error, never an empty board: an empty facts.json
        # would render as a clean backlog (spec §3.C, review r-p2-empty). Repo
        # scope already raised above; this is org scope.
        if skipped:
            reasons = "; ".join(f"{s.repo}: {s.reason}" for s in skipped)
            raise ForgeError(f"no repo of {scope.owner} could be read — {reasons}")
        raise ForgeError(f"{scope.owner} has no non-archived repos to triage")
    links = invert(parsed_prs, scope)

    def linked(repo: str, number: int) -> list[PullRequest]:
        owner, name = repo.split("/", 1)
        return links.get(_ref(owner, name, number), [])

    out = [_issue(repo, i, linked(repo, i["number"]), state="open") for repo, i in raw_issues]
    open_keys = {i.key for i in out}
    unviewed: list[Unviewed] = []
    for repo, number in _judged_elsewhere(judged, open_keys, collected):
        try:
            raw = forge.view_issue(repo=repo, number=number)
        except ForgeError as exc:
            # Deleted, rate-limited, 5xx or no access — indistinguishable here, so
            # recorded, never dropped: `check` must not call it orphaned (r-p2-unviewed).
            unviewed.append(Unviewed(key=issue_key(repo, number), reason=str(exc)))
            continue
        state: IssueState = "open" if str(raw.get("state", "")).upper() == "OPEN" else "closed"
        out.append(_issue(repo, {"number": number, **raw}, linked(repo, number), state=state))
    return Facts(
        schema=SCHEMA,
        scope=scope.name,
        kind=scope.kind,
        collected_at=now.isoformat(timespec="seconds"),
        repos=repos,
        issues=out,
        skipped=skipped,
        unviewed=unviewed,
        warnings=warnings,
    )
