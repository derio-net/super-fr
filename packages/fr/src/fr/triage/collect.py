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

import yaml
from pydantic import ValidationError

from fr import gh
from fr.labels import FR_IN_PROGRESS
from fr.real_ghclient import RealGhClient
from fr.triage.errors import ForgeError, TriageError
from fr.triage.model import (
    BATCH_MARKER_PREFIX,
    FACTS_SCHEMA,
    Facts,
    Issue,
    IssueState,
    PullRequest,
    Scope,
    Skipped,
    TriageConfig,
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
CONFIG_PATH = ".fr/triage.yaml"
# GitHub's contents API resolves HEAD to the default branch (verified live
# 2026-09-25), so the config read needs no default-branch lookup first.
DEFAULT_BRANCH_REF = "HEAD"
_NOT_FOUND = "HTTP 404"

# (owner login, repo name, issue number), lowercased — the key a closing reference names.
IssueRef = tuple[str, str, int]


class Forge(Protocol):
    """The forge calls triage needs — nothing more."""

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]: ...

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]: ...

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]: ...
    def list_open_prs(self, *, repo: str, limit: int) -> list[dict[str, Any]]: ...

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]: ...

    def read_file_at_ref(self, *, repo: str, path: str, ref: str) -> str: ...

    def list_issue_comments(self, *, repo: str, number: int) -> list[dict[str, Any]]: ...

    def list_prs_by_head(self, *, repo: str, branch: str) -> list[dict[str, Any]]: ...


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

    def list_open_prs(self, *, repo: str, limit: int) -> list[dict[str, Any]]:
        with _forge_errors():
            return gh.list_open_prs(repo=repo, limit=limit)

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]:
        with _forge_errors():
            return gh.view_issue(repo, number)

    def read_file_at_ref(self, *, repo: str, path: str, ref: str) -> str:
        with _forge_errors():
            return gh.read_file_at_ref(repo=repo, path=path, ref=ref)

    # The two batch reads delegate to the forge adapter's own methods (spec
    # 2026-09-25-triage-batches §3.F), so each has ONE GitHub implementation
    # whether collect or a batch verb calls it.

    def list_issue_comments(self, *, repo: str, number: int) -> list[dict[str, Any]]:
        with _forge_errors():
            return RealGhClient().list_issue_comments(repo, number)

    def list_prs_by_head(self, *, repo: str, branch: str) -> list[dict[str, Any]]:
        with _forge_errors():
            return RealGhClient().list_prs_by_head(repo, branch)


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
            head_oid=r.get("headRefOid") or "",
            files=[f["path"] for f in r.get("files") or [] if "path" in f],
            checks=_checks(r.get("statusCheckRollup") or []),
            mergeable=r.get("mergeable") or "UNKNOWN",
            merge_state=r.get("mergeStateStatus") or "UNKNOWN",
            review=r.get("reviewDecision") or None,
        )
        refs = [
            _ref(ref["repository"]["owner"]["login"], ref["repository"]["name"], ref["number"])
            for ref in r["closingIssuesReferences"]
        ]
        out.append((pr, refs))
    return out


def _checks(raw: Iterable[dict[str, Any]]) -> dict[str, int]:
    result = {"pass": 0, "fail": 0, "pending": 0}
    for check in raw:
        state = str(check.get("conclusion") or check.get("state") or "").upper()
        bucket = (
            "pass"
            if state in {"SUCCESS", "SUCCEEDED", "PASS", "PASSED", "SKIPPED", "NEUTRAL"}
            else "fail"
            if state in {"FAILURE", "FAILED", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}
            else "pending"
        )
        result[bucket] += 1
    return result


def _anchor_file(paths: Iterable[str]) -> tuple[str, str] | None:
    """First spec-like or debug path in anchor priority order, independent of diff order."""
    paths = list(paths)
    for path in paths:
        if path.startswith("docs/superpowers/specs/") and path.endswith(".md"):
            return "spec", path
        if path.startswith("docs/superpowers/journals/specs/") and path.endswith(".md"):
            return "spec", path
        if path.startswith("docs/superpowers/plans/") and path.endswith("/_meta.yaml"):
            return "spec-meta", path
    for path in paths:
        if path.startswith("docs/superpowers/journals/debug/") and path.endswith(".md"):
            return "debug", path
    return None


def _anchor_pr(forge: Forge, pr: PullRequest, raw: dict[str, Any]) -> PullRequest:
    """Attach a file-derived intent anchor, degrading forge failures to unanchored."""
    if pr.anchor == "issue":
        return pr
    match = _anchor_file(f["path"] for f in raw.get("files") or [] if "path" in f)
    if match is None:
        return pr.model_copy(update={"anchor_reason": "no matching intent file"})
    kind, path = match
    try:
        body = forge.read_file_at_ref(repo=pr.repo, path=path, ref=pr.head_ref)
        if kind == "spec-meta":
            spec = yaml.safe_load(body).get("spec")
            if not isinstance(spec, str):
                raise ForgeError("plan metadata has no spec reference")
            return pr.model_copy(
                update={"anchor": "spec", "anchor_path": spec, "anchor_body": body[:BODY_LIMIT]}
            )
        return pr.model_copy(
            update={"anchor": kind, "anchor_path": path, "anchor_body": body[:BODY_LIMIT]}
        )
    except (ForgeError, yaml.YAMLError, AttributeError) as exc:
        return pr.model_copy(update={"anchor_reason": str(exc)})


def _in_scope(ref: IssueRef, scope: Scope) -> bool:
    owner, name, _ = ref
    if scope.kind == "repo":
        return f"{owner}/{name}" == scope.target.lower()
    return owner == scope.owner.lower()


def _issue_anchored(
    prs: Iterable[tuple[PullRequest, list[IssueRef]]], scope: Scope
) -> list[tuple[PullRequest, list[IssueRef]]]:
    """Mark a PR whose closing reference is in scope with the highest-priority anchor."""
    out: list[tuple[PullRequest, list[IssueRef]]] = []
    for pr, refs in prs:
        ref = next((candidate for candidate in refs if _in_scope(candidate, scope)), None)
        if ref is not None:
            owner, name, number = ref
            pr = pr.model_copy(
                update={"anchor": "issue", "anchor_path": f"{owner}/{name}#{number}"}
            )
        out.append((pr, refs))
    return out


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
    batch_branches: Iterable[tuple[str, str]] = (),
    issue_limit: int = ISSUE_LIMIT,
    pr_limit: int = PR_LIMIT,
    repo_limit: int = REPO_LIMIT,
) -> Facts:
    """Build the facts for *scope*: two bulk calls per repo, inverted.

    In org scope a repo whose lists fail is recorded under `skipped` and the
    rest still collect; in repo scope the one repo failing is the error, and
    in org scope so is collecting no repo at all (review r-p2-empty).
    Each *judged* key no longer open costs one `view_issue`, so the extra
    calls are bounded by the judgements, never by the backlog. The batch
    extras are bounded the same way (spec 2026-09-25-triage-batches §3.F): one
    config read per repo, one comment read per `fr:in-progress` issue, and one
    head-branch lookup per *batch_branches* entry — `(repo name, branch)` of
    each batch whose last event is a dispatch — that no collected PR is on.
    """
    repos, warnings = scope_repos(forge, scope, repo_limit=repo_limit)
    skipped: list[Skipped] = []
    collected: list[str] = []
    raw_issues: list[tuple[str, dict[str, Any]]] = []
    parsed_prs: list[tuple[PullRequest, list[IssueRef]]] = []
    open_prs: list[tuple[PullRequest, list[IssueRef]]] = []
    config: dict[str, TriageConfig] = {}
    for repo in repos:
        try:
            issues = forge.list_issues(repo=repo, state="open", limit=issue_limit)
            prs = forge.list_prs(repo=repo, state="all", limit=pr_limit)
            current = forge.list_open_prs(repo=repo, limit=pr_limit)
            repo_config = read_config(forge, repo)
        except ForgeError as exc:
            if scope.kind == "repo":
                raise
            skipped.append(Skipped(repo=repo, reason=str(exc)))
            continue
        collected.append(repo)
        if repo_config is not None:
            config[repo] = repo_config
        if len(issues) == issue_limit:
            warnings.append(Truncation(source="issues", target=repo, limit=issue_limit))
        if len(prs) == pr_limit:
            warnings.append(Truncation(source="prs", target=repo, limit=pr_limit))
        raw_issues.extend((repo, i) for i in issues)
        parsed_prs.extend(_issue_anchored(parse_prs(repo, prs), scope))
        parsed_open = _issue_anchored(parse_prs(repo, current), scope)
        open_prs.extend(
            (_anchor_pr(forge, pr, raw), refs)
            for (pr, refs), raw in zip(parsed_open, current, strict=True)
        )
    if not collected:
        # Nothing to show is an error, never an empty board: an empty facts.json
        # would render as a clean backlog (spec §3.C, review r-p2-empty). Repo
        # scope already raised above; this is org scope.
        if skipped:
            reasons = "; ".join(f"{s.repo}: {s.reason}" for s in skipped)
            raise ForgeError(f"no repo of {scope.owner} could be read — {reasons}")
        raise ForgeError(f"{scope.owner} has no non-archived repos to triage")
    parsed_prs = join_open(parsed_prs, [pr for pr, _ in open_prs])
    links = invert(parsed_prs, scope)

    def linked(repo: str, number: int) -> list[PullRequest]:
        owner, name = repo.split("/", 1)
        return links.get(_ref(owner, name, number), [])

    out = [
        _with_marker(forge, _issue(repo, i, linked(repo, i["number"]), state="open"))
        for repo, i in raw_issues
    ]
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
    linked_prs = {(p.repo, p.number) for issue in out for p in issue.prs}
    unlinked = [
        p
        for p, refs in open_prs
        if not any(_in_scope(ref, scope) for ref in refs) and (p.repo, p.number) not in linked_prs
    ]
    on_branches = {(p.repo, p.head_ref) for p in [*linked_prs_all(out), *unlinked]}
    batch_prs = _batch_prs(forge, batch_branches, collected, on_branches)
    return Facts(
        schema=FACTS_SCHEMA,
        scope=scope.name,
        kind=scope.kind,
        collected_at=now.isoformat(timespec="seconds"),
        repos=repos,
        issues=out,
        prs=unlinked,
        skipped=skipped,
        unviewed=unviewed,
        warnings=warnings,
        batch_prs=batch_prs,
        config=config,
    )


def linked_prs_all(issues: Iterable[Issue]) -> list[PullRequest]:
    """Every PR linked to one of *issues*."""
    return [p for issue in issues for p in issue.prs]


def join_open(
    prs: Iterable[tuple[PullRequest, list[IssueRef]]], open_prs: Iterable[PullRequest]
) -> list[tuple[PullRequest, list[IssueRef]]]:
    """Fill each PR from the open-PR record with the same (repo, number) (spec §3.F).

    A linked PR comes from `list_prs(state=all)`, whose fields carry no files,
    head oid, checks or merge state; the open-PR list carries all of them. A
    batch PR is always linked, so without this join it would have none.
    """
    by_id = {(p.repo, p.number): p for p in open_prs}
    out: list[tuple[PullRequest, list[IssueRef]]] = []
    for pr, refs in prs:
        rec = by_id.get((pr.repo, pr.number))
        if rec is not None:
            pr = pr.model_copy(
                update={
                    "files": rec.files,
                    "head_oid": rec.head_oid,
                    "checks": rec.checks,
                    "mergeable": rec.mergeable,
                    "merge_state": rec.merge_state,
                    "review": rec.review,
                }
            )
        out.append((pr, refs))
    return out


def read_config(forge: Forge, repo: str) -> TriageConfig | None:
    """*repo*'s `.fr/triage.yaml` at its default branch; None when it has none.

    Absent (404) is the common case and means the defaults. Any other forge
    failure propagates like the list calls' do; a file that is not valid config
    is refused naming the repo and the file, never half-read.
    """
    try:
        body = forge.read_file_at_ref(repo=repo, path=CONFIG_PATH, ref=DEFAULT_BRANCH_REF)
    except ForgeError as exc:
        if _NOT_FOUND in str(exc):
            return None
        raise
    try:
        return TriageConfig.model_validate(yaml.safe_load(body) or {})
    except (yaml.YAMLError, ValidationError) as exc:
        raise TriageError(f"{repo}: {CONFIG_PATH} is not valid triage config: {exc}") from exc


def _with_marker(forge: Forge, issue: Issue) -> Issue:
    """Date an `fr:in-progress` issue's dispatch by its latest fr-batch marker (§3.E)."""
    if FR_IN_PROGRESS.name not in issue.labels:
        return issue
    comments = forge.list_issue_comments(repo=issue.repo, number=issue.number)
    stamps = [
        stamp
        for c in comments
        if str(c.get("body") or "").lstrip().startswith(BATCH_MARKER_PREFIX)
        and (stamp := str(c.get("created_at") or ""))  # no stamp is no time (r2p-f13)
    ]
    if not stamps:
        return issue
    return issue.model_copy(update={"dispatch_marker_at": max(stamps)})


def _batch_prs(
    forge: Forge,
    branches: Iterable[tuple[str, str]],
    collected: list[str],
    on_branches: set[tuple[str, str]],
) -> list[PullRequest]:
    """One head-branch lookup per dispatched batch no collected PR is on (§3.A)."""
    by_name = {repo.split("/", 1)[1].lower(): repo for repo in collected}
    found: list[PullRequest] = []
    for name, branch in sorted(set(branches)):
        repo = by_name.get(name.lower())
        if repo is None or (repo, branch) in on_branches:
            continue
        raw = forge.list_prs_by_head(repo=repo, branch=branch)
        found.extend(pr for pr, _ in parse_prs(repo, raw))
    return found
