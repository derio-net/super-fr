"""Collect the facts a triage board is built from (spec §3.B–C).

Pure: every function returns data. No Typer, no printing, no filesystem writes
— the command layer (`fr.commands.triage_cmd`) owns I/O.

`Forge` is the whole of decision d2's seam. `ClientForge` is its one
implementation and the ONLY place `fr.triage` touches a forge: it reads through
a `GhClient` adapter (`fr.hostclient`), so a second forge is that adapter
implementing the reads, not an edit to the collector (spec
2026-10-06-forge-remainder §4.A).
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

import yaml
from pydantic import ValidationError

from fr import real_ghclient
from fr.ghclient import GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS
from fr.labels import FR_CLAIMED, FR_IN_PROGRESS
from fr.triage.claims import read_claims, to_issue_claim
from fr.triage.errors import ForgeError, TriageError
from fr.triage.model import (
    BATCH_MARKER_PREFIX,
    FACTS_SCHEMA,
    Facts,
    Issue,
    IssueClaim,
    IssueState,
    PullRequest,
    Scope,
    Skipped,
    TriageConfig,
    Truncation,
    Unviewed,
    claim_trusted,
    issue_key,
    normalize_key,
    parse_triage_config,
)
from fr.triage.stage import pr_rank

ISSUE_LIMIT = 1000
PR_LIMIT = 200
REPO_LIMIT = 200
ORIGINS_ISSUE_LIST_FIELDS = (
    real_ghclient.ORIGINS_ISSUE_LIST_FIELDS
)  # origins' own, wider issue fields
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

    def list_issues(
        self, *, repo: str, state: str, limit: int, fields: str | None = None
    ) -> list[dict[str, Any]]: ...

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]: ...
    def list_open_prs(self, *, repo: str, limit: int) -> list[dict[str, Any]]: ...

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]: ...

    def read_file_at_ref(self, *, repo: str, path: str, ref: str) -> str: ...

    def list_issue_comments(self, *, repo: str, number: int) -> list[dict[str, Any]]: ...

    def list_prs_by_head(self, *, repo: str, branch: str) -> list[dict[str, Any]]: ...

    def viewer_login(self) -> str: ...

    def repo_visibility(self, *, repo: str) -> str | None: ...


GH_MISSING = (
    "gh (the GitHub CLI) was not found on PATH: install it from https://cli.github.com "
    "and run `gh auth login`"
)


# A forge CLI's own error, and an operation the backend does not implement.
_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, UnsupportedForgeOperation)


@contextmanager
def _forge_errors() -> Iterator[None]:
    """Translate every way a forge call fails into triage's own `ForgeError`:
    the forge CLI's error, an operation the backend does not implement, and a
    CLI that is not installed at all."""
    try:
        yield
    except _FAILURES as exc:
        raise ForgeError(str(exc)) from exc
    except FileNotFoundError as exc:  # subprocess could not exec `gh` at all
        raise ForgeError(GH_MISSING) from exc


class ClientForge:
    """`Forge` backed by a `GhClient` adapter. Raises only `ForgeError`."""

    def __init__(self, client: GhClient) -> None:
        self._client = client

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]:
        # Archived repos included: the caller counts the raw list against its limit
        # before dropping them, or a full list with archived repos would not warn.
        with _forge_errors():
            return self._client.list_repos(owner, limit)

    def list_issues(
        self, *, repo: str, state: str, limit: int, fields: str | None = None
    ) -> list[dict[str, Any]]:
        with _forge_errors():
            return self._client.list_issues(repo, state, limit, fields)

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        with _forge_errors():
            return self._client.list_prs(repo, state, limit)

    def list_open_prs(self, *, repo: str, limit: int) -> list[dict[str, Any]]:
        with _forge_errors():
            return self._client.list_open_prs(repo, limit)

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]:
        with _forge_errors():
            return self._client.view_issue_record(repo, number)

    def read_file_at_ref(self, *, repo: str, path: str, ref: str) -> str:
        with _forge_errors():
            return self._client.read_file_at_ref(repo, path, ref)

    # The two batch reads are the adapter's own methods (spec
    # 2026-09-25-triage-batches §3.F), so each has ONE GitHub implementation
    # whether collect or a batch verb calls it.

    def list_issue_comments(self, *, repo: str, number: int) -> list[dict[str, Any]]:
        with _forge_errors():
            return self._client.list_issue_comments(repo, number)

    def list_prs_by_head(self, *, repo: str, branch: str) -> list[dict[str, Any]]:
        with _forge_errors():
            return self._client.list_prs_by_head(repo, branch)

    def viewer_login(self) -> str:
        with _forge_errors():
            return self._client.viewer_login()

    def repo_visibility(self, *, repo: str) -> str | None:
        with _forge_errors():
            return self._client.repo_visibility(repo)


def scope_repos(
    forge: Forge, scope: Scope, *, repo_limit: int = REPO_LIMIT
) -> tuple[list[str], list[Truncation]]:
    """The non-archived `OWNER/REPO` slugs in *scope*, sorted, plus any truncation.

    `list_repos` returns archived repos too, so a list that came back exactly
    at its limit is detected on the raw count (review r-p1-repo-cap).
    """
    if scope.kind == "repo":
        return [scope.target], []
    if scope.kind == "group":
        return list(scope.repos), []
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
            created_at=r.get("createdAt"),
            merged_at=r.get("mergedAt"),
            url=r["url"],
            head_ref=r.get("headRefName") or "",
            head_oid=r.get("headRefOid") or "",
            files=[f["path"] for f in r.get("files") or [] if "path" in f],
            # Only a record that carries the field gets a value (super-fr#648).
            checks=_checks(r["statusCheckRollup"] or []) if "statusCheckRollup" in r else None,
            mergeable=(r["mergeable"] or "UNKNOWN") if "mergeable" in r else None,
            merge_state=((r["mergeStateStatus"] or "UNKNOWN") if "mergeStateStatus" in r else None),
            review=r.get("reviewDecision") or None,
            author=_login(r),
            cross_repo=r.get("isCrossRepository"),
        )
        refs = [
            _ref(ref["repository"]["owner"]["login"], ref["repository"]["name"], ref["number"])
            for ref in r["closingIssuesReferences"]
        ]
        out.append((pr, refs))
    return out


def _login(raw: dict[str, Any]) -> str | None:
    """The PR author's login; None when the record carries none (never read, or a
    deleted account), which no batch attribution trusts."""
    author = raw.get("author")
    login = author.get("login") if isinstance(author, dict) else None
    return str(login) if login else None


def _latest_runs(raw: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per check: the most recent run of each (super-fr#1051).

    `statusCheckRollup` lists every run on the head commit, so a check re-run
    green keeps its superseded failure beside it. A check is its workflow plus
    its name (a status context: its context), as `gh pr checks` keys it; an
    entry carrying neither is counted on its own. A run not yet started has no
    real `startedAt` and is the newest, so a queued re-run reads pending rather
    than its predecessor's result. Two runs no timestamp orders keep the worse
    state, never whichever the rollup happened to list last.
    """
    latest: dict[tuple[str, str], tuple[tuple[int, str, int], dict[str, Any]]] = {}
    anonymous: list[dict[str, Any]] = []
    for check in raw:
        name = check.get("name") or check.get("context")
        if not name:
            anonymous.append(check)
            continue
        key = (str(check.get("workflowName") or ""), str(name))
        started = str(check.get("startedAt") or "")
        if started.startswith("0001-"):  # GraphQL's zero time: never started
            started = ""
        done = str(check.get("status") or "COMPLETED").upper() == "COMPLETED"
        severity = _SEVERITY[_bucket(check)]
        rank = (1, "", severity) if not started and not done else (0, started, severity)
        if key not in latest or rank > latest[key][0]:
            latest[key] = (rank, check)
    return [check for _, check in latest.values()] + anonymous


_SEVERITY = {"pass": 0, "pending": 1, "fail": 2}


def _bucket(check: dict[str, Any]) -> str:
    state = str(check.get("conclusion") or check.get("state") or "").upper()
    if state in {"SUCCESS", "SUCCEEDED", "PASS", "PASSED", "SKIPPED", "NEUTRAL"}:
        return "pass"
    if state in {"FAILURE", "FAILED", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
        return "fail"
    return "pending"


def _checks(raw: Iterable[dict[str, Any]]) -> dict[str, int]:
    result = {"pass": 0, "fail": 0, "pending": 0}
    for check in _latest_runs(raw):
        result[_bucket(check)] += 1
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
    if scope.kind == "group":
        return f"{owner}/{name}" in {r.lower() for r in scope.repos}
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


PR_PAST_LIMIT = (
    "a pull request, not an issue, and past the PR list's limit: "
    "re-run `fr triage collect` with a higher --pr-limit"
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


@dataclass(frozen=True)
class CollectStats:
    """What one collect cost in single-issue reads (gh#911).

    *viewed* counts every `view_issue` call, failures and PR-past-limit answers
    included; *carried* counts judged closed issues taken from the previous
    facts instead of being viewed.
    """

    viewed: int = 0
    carried: int = 0
    # OWNER/REPO -> the top-level `.fr/triage.yaml` keys a lenient read dropped (gh#998)
    ignored: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


def collect_facts(
    forge: Forge,
    scope: Scope,
    *,
    now: datetime,
    judged: Iterable[str] = (),
    batch_branches: Iterable[tuple[str, str, datetime]] = (),
    known_batch_prs: Iterable[PullRequest] = (),
    issue_limit: int = ISSUE_LIMIT,
    pr_limit: int = PR_LIMIT,
    repo_limit: int = REPO_LIMIT,
) -> Facts:
    """`collect_facts_counted` without a carried set: every not-open judged key is viewed."""
    return collect_facts_counted(
        forge,
        scope,
        now=now,
        judged=judged,
        batch_branches=batch_branches,
        known_batch_prs=known_batch_prs,
        issue_limit=issue_limit,
        pr_limit=pr_limit,
        repo_limit=repo_limit,
    )[0]


def _visibility(forge: Forge, repos: Iterable[str]) -> dict[str, str]:
    """Each repo's visibility as the forge answers it (cloud-triage §B, §C); a repo whose
    read fails is left out, never guessed: the privacy guard reads a missing one live."""
    out: dict[str, str] = {}
    for repo in repos:
        try:
            value = forge.repo_visibility(repo=repo)
        except ForgeError:
            continue
        if value:
            out[repo] = value.lower()
    return out


def collect_facts_counted(
    forge: Forge,
    scope: Scope,
    *,
    now: datetime,
    judged: Iterable[str] = (),
    batch_branches: Iterable[tuple[str, str, datetime]] = (),
    known_batch_prs: Iterable[PullRequest] = (),
    issue_limit: int = ISSUE_LIMIT,
    pr_limit: int = PR_LIMIT,
    repo_limit: int = REPO_LIMIT,
    carried: Iterable[Issue] = (),
    lenient: bool = False,
) -> tuple[Facts, CollectStats]:
    """Build the facts for *scope*: two bulk calls per repo, inverted.

    *carried* is the previous facts' issues: a judged key that is not open now
    and was CLOSED there is taken from it instead of viewed (gh#911) — closed is
    terminal for the board, and its PR links are recomputed from this pass. A
    repo whose open-issue list was truncated carries nothing: a key missing from
    a cut-short list is not known to have left it, so each is viewed again.

    In org scope a repo whose lists, config or comment reads fail — or whose
    `.fr/triage.yaml` is invalid — is recorded under `skipped` and the rest
    still collect; in repo scope the one repo failing is the error, and
    in org scope so is collecting no repo at all (review r-p2-empty).
    *lenient* reads each config as the wave driver must (gh#998): an unknown
    top-level key is dropped and named in the stats' `ignored`, never refused.
    Each *judged* key no longer open costs one `view_issue`, so the extra
    calls are bounded by the judgements, never by the backlog. The batch
    extras are bounded the same way (spec 2026-09-25-triage-batches §3.F): one
    config read per repo, one comment read per `fr:in-progress` issue, and one
    head-branch lookup per *batch_branches* entry — `(repo name, branch,
    dispatched at)` of each batch whose last event is a dispatch — that no
    collected PR of that dispatch is on and that is not already terminal:
    a merged or closed PR of that dispatch in *known_batch_prs* (the previous
    facts' `batch_prs`) is carried over instead of looked up again (review
    r2p-f3), so a finished batch costs nothing on later collects.
    """
    repos, warnings = scope_repos(forge, scope, repo_limit=repo_limit)
    viewer = forge.viewer_login() or None
    skipped: list[Skipped] = []
    collected: list[str] = []
    raw_issues: list[tuple[str, dict[str, Any]]] = []
    parsed_prs: list[tuple[PullRequest, list[IssueRef]]] = []
    open_prs: list[tuple[PullRequest, list[IssueRef]]] = []
    # Every PR either list returned, by judgement key: a judged PR is not an
    # issue, and must never reach `view_issue`, which answers for PRs too (gh#902).
    listed_prs: dict[str, PullRequest] = {}
    config: dict[str, TriageConfig] = {}
    ignored: dict[str, tuple[str, ...]] = {}
    markers: dict[tuple[str, int], str] = {}
    claims: dict[tuple[str, int], list[IssueClaim]] = {}
    for repo in repos:
        try:
            issues = forge.list_issues(repo=repo, state="open", limit=issue_limit)
            prs = forge.list_prs(repo=repo, state="all", limit=pr_limit)
            current = forge.list_open_prs(repo=repo, limit=pr_limit)
            repo_config, dropped = _read_config(forge, repo, lenient=lenient)
            trusted = claim_trusted(repo_config or TriageConfig(), viewer)
            for raw in issues:
                at, found = _comment_facts(forge, repo, raw, trusted)
                if at:
                    markers[(repo, raw["number"])] = at
                if found:
                    claims[(repo, raw["number"])] = found
        except TriageError as exc:
            # A forge failure, or a config the repo's owner broke (review r2p-f4):
            # either way that one repo is skipped in org scope, never the collect.
            if scope.kind == "repo":
                raise
            skipped.append(Skipped(repo=repo, reason=str(exc)))
            continue
        collected.append(repo)
        if repo_config is not None:
            config[repo] = repo_config
        if dropped:
            ignored[repo] = dropped
        if len(issues) == issue_limit:
            warnings.append(Truncation(source="issues", target=repo, limit=issue_limit))
        if len(prs) == pr_limit:
            warnings.append(Truncation(source="prs", target=repo, limit=pr_limit))
        raw_issues.extend((repo, i) for i in issues)
        for pr, _ in [*parse_prs(repo, prs), *parse_prs(repo, current)]:
            listed_prs.setdefault(issue_key(pr.repo, pr.number), pr)
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
            of = "the group" if scope.kind == "group" else scope.owner
            raise ForgeError(f"no repo of {of} could be read — {reasons}")
        raise ForgeError(f"{scope.owner} has no non-archived repos to triage")
    parsed_prs = join_open(parsed_prs, [pr for pr, _ in open_prs])
    links = invert(parsed_prs, scope)

    def linked(repo: str, number: int) -> list[PullRequest]:
        owner, name = repo.split("/", 1)
        return links.get(_ref(owner, name, number), [])

    out = [
        _issue(repo, i, linked(repo, i["number"]), state="open").model_copy(
            update={
                "dispatch_marker_at": markers.get((repo, i["number"])),
                "claims": claims.get((repo, i["number"]), []),
            }
        )
        for repo, i in raw_issues
    ]
    open_keys = {i.key for i in out}
    carry = {(i.repo.lower(), i.number): i for i in carried if i.state == "closed"}
    truncated = {w.target for w in warnings if w.source == "issues"}
    viewed = carried_n = 0
    unviewed: list[Unviewed] = []
    judged_prs: list[PullRequest] = []
    for repo, number in _judged_elsewhere(judged, open_keys, collected):
        if (listed := listed_prs.get(issue_key(repo, number))) is not None:
            judged_prs.append(listed)
            continue
        if repo not in truncated and (hit := carry.get((repo.lower(), number))) is not None:
            out.append(
                hit.model_copy(
                    update={"prs": linked(repo, number), "dispatch_marker_at": None, "claims": []}
                )
            )
            carried_n += 1
            continue
        viewed += 1
        try:
            raw = forge.view_issue(repo=repo, number=number)
        except ForgeError as exc:
            # Deleted, rate-limited, 5xx or no access — indistinguishable here, so
            # recorded, never dropped: `check` must not call it orphaned (r-p2-unviewed).
            unviewed.append(Unviewed(key=issue_key(repo, number), reason=str(exc)))
            continue
        if "/pull/" in str(raw.get("url", "")):
            # A PR past the PR list's limit: `gh issue view` resolves it anyway.
            unviewed.append(Unviewed(key=issue_key(repo, number), reason=PR_PAST_LIMIT))
            continue
        state: IssueState = "open" if str(raw.get("state", "")).upper() == "OPEN" else "closed"
        out.append(_issue(repo, {"number": number, **raw}, linked(repo, number), state=state))
    linked_prs = {(p.repo, p.number) for issue in out for p in issue.prs}
    unlinked = [
        p
        for p, refs in open_prs
        if not any(_in_scope(ref, scope) for ref in refs) and (p.repo, p.number) not in linked_prs
    ]
    batch_prs = _batch_prs(
        forge,
        batch_branches,
        collected,
        seen=[*linked_prs_all(out), *unlinked],
        known=list(known_batch_prs),
    )
    in_facts = {(p.repo, p.number) for p in [*linked_prs_all(out), *unlinked, *batch_prs]}
    judged_prs = [p for p in judged_prs if (p.repo, p.number) not in in_facts]
    facts = Facts(
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
        judged_prs=judged_prs,
        config=config,
        viewer=viewer,
        visibility=_visibility(forge, collected),
    )
    return facts, CollectStats(viewed=viewed, carried=carried_n, ignored=ignored)


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
    is refused naming the repo and the file, never half-read — which fails a
    repo-scope collect and skips just that repo in org scope (review r2p-f4).
    """
    return _read_config(forge, repo, lenient=False)[0]


def read_config_lenient(forge: Forge, repo: str) -> tuple[TriageConfig | None, tuple[str, ...]]:
    """`read_config` as the wave driver reads it (gh#998): an unknown top-level key
    is dropped and named, never refused (`parse_triage_config`)."""
    return _read_config(forge, repo, lenient=True)


def _read_config(
    forge: Forge, repo: str, *, lenient: bool
) -> tuple[TriageConfig | None, tuple[str, ...]]:
    try:
        body = forge.read_file_at_ref(repo=repo, path=CONFIG_PATH, ref=DEFAULT_BRANCH_REF)
    except ForgeError as exc:
        if _NOT_FOUND in str(exc):
            return None, ()
        raise
    try:
        return parse_triage_config(yaml.safe_load(body) or {}, lenient=lenient)
    except (yaml.YAMLError, ValidationError) as exc:
        raise TriageError(f"{repo}: {CONFIG_PATH} is not valid triage config: {exc}") from exc


def _comment_facts(
    forge: Forge, repo: str, raw: dict[str, Any], trusted: frozenset[str]
) -> tuple[str | None, list[IssueClaim]]:
    """An issue's latest fr-batch marker time (§3.E) and its claims (triage-claims §3.H).

    One comment read per issue labelled `fr:in-progress` or `fr:claimed`, none for the
    rest: both facts come from the same read. Only *trusted* authors' claim markers
    count (R17). Called inside the per-repo collect, so a failing read skips that repo
    in org scope.
    """
    names = {label["name"] for label in raw.get("labels") or []}
    if not names & {FR_IN_PROGRESS.name, FR_CLAIMED.name}:
        return None, []
    comments = forge.list_issue_comments(repo=repo, number=raw["number"])
    stamps = [
        stamp
        for c in comments
        if str(c.get("body") or "").lstrip().startswith(BATCH_MARKER_PREFIX)
        and (stamp := str(c.get("created_at") or ""))  # no stamp is no time (r2p-f13)
    ]
    read = read_claims(comments, trusted)
    if read.untrusted or read.malformed:
        # Once per issue (p1-r7): a peer whose markers are dropped must be visible.
        print(
            f"fr triage: {repo}#{raw['number']}: ignored {read.untrusted} untrusted, "
            f"{read.malformed} malformed claim marker(s)",
            file=sys.stderr,
        )
    claims = [to_issue_claim(c) for c in read.claims]
    return (max(stamps) if stamps else None), claims


def _created_since(pr: PullRequest, at: datetime) -> bool:
    """Whether *pr* was opened at or after *at*; unknown creation counts as yes."""
    try:
        created = datetime.fromisoformat(pr.created_at) if pr.created_at else None
    except ValueError:
        created = None
    if created is None or created.tzinfo is None:
        return True
    return created >= at


def _batch_prs(
    forge: Forge,
    branches: Iterable[tuple[str, str, datetime]],
    collected: list[str],
    *,
    seen: list[PullRequest],
    known: list[PullRequest],
) -> list[PullRequest]:
    """One head-branch lookup per dispatched, non-terminal batch (§3.A, §3.F).

    Skipped when a collected PR (*seen*) of THIS dispatch is already on the
    branch — a PR opened before the last dispatch belongs to an earlier one and
    must not hide the redispatch's PR (review r2p-f1) — or when *known* (the
    previous facts) holds a merged or closed PR of this dispatch whose identity
    was read: that batch is terminal, and its PR is carried over instead (review
    r2p-f3).
    """
    by_name = {repo.split("/", 1)[1].lower(): repo for repo in collected}
    found: list[PullRequest] = []
    for name, branch, at in sorted(set(branches)):
        repo = by_name.get(name.lower())
        if repo is None:
            continue
        ours = [
            p
            for p in [*seen, *known]
            if p.repo == repo and p.head_ref == branch and _created_since(p, at)
        ]
        if any(p in seen for p in ours):
            continue
        # A known PR whose author and origin were never read (facts from before gh#936)
        # is not carried over: no attribution would trust it, so it is read again.
        terminal = [
            p
            for p in ours
            if p in known
            and p.state in {"MERGED", "CLOSED"}
            and p.author is not None
            and p.cross_repo is not None
        ]
        if terminal:
            found.extend(terminal)
            continue
        raw = forge.list_prs_by_head(repo=repo, branch=branch)
        found.extend(pr for pr, _ in parse_prs(repo, raw))
    return found
