"""`github-rest`: a `GhClient` that reaches GitHub through REST routes only.

Spec 2026-10-07-cloud-triage §A (R1, R2). Every call is `gh api <REST route>`;
none is `gh api graphql` and none is a GraphQL-backed `gh` verb (`gh pr list
--json`, `gh issue view --json`, `gh pr checks`, ...), because a Claude Code cloud
session's proxy refuses GraphQL with HTTP 403 while it allows REST. Selected by
`forge.api: rest` (`fr.forgeapi`), through `fr.hostclient.client_for_backend`.

The records are the ones `fr.real_ghclient.RealGhClient` returns for the same
forge state, field for field, except the fields REST cannot express. The field
map lives in the pure helpers at the top of this module, each citing its §A row;
`tests/unit/test_github_rest_contract.py` holds the two backends to it.

Error contract (per method, never blanket): this client never falls back to
GraphQL and never turns a refusal into an empty answer. The methods whose
`GhClient` contract already answers None when the forge cannot say —
`pr_for_branch`, `issues_enabled`, `default_branch`, `pr_status_by_url` — keep
it; every other method raises `GhError`. A 404 on a lookup whose contract has a
"not there" answer (`file_exists`, `list_dir`) is that answer, never a 403.
"""

from __future__ import annotations

import functools
import json
import re
import urllib.parse
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

from fr import _hosts
from fr import gh as _gh
from fr.gh import GhError
from fr.ghclient import MERGE_METHODS, CommandRunner, HostRefusedError, run_cli
from fr.labels import LabelDef

GhRun = Callable[[list[str]], str]
"""How the client runs one `gh` command: argv without the leading `gh`, stdout
back, `GhError` on failure. `fr.gh._run_gh` by default; tests pass a fake."""

RAW_ACCEPT = "Accept: application/vnd.github.raw"

# ---------------------------------------------------------------------------
# The field map (spec §A), as pure helpers over REST records.
# ---------------------------------------------------------------------------

GITHUB_HOST = "github.com"

_CLOSING_KEYWORD = r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)"


@functools.lru_cache(maxsize=8)
def _closing_ref_pattern(host: str) -> re.Pattern[str]:
    """A closing keyword at a word boundary (so "prefixes #3" and "unresolved #5"
    are not refs), an optional colon, then ONE reference: `#n`, `owner/repo#n`,
    or an issue URL on *host* only (an issue on another host closes nothing)."""
    return re.compile(
        _CLOSING_KEYWORD
        + r":?\s+(?:"
        + rf"https?://{re.escape(host)}/(?P<url_repo>[\w.-]+/[\w.-]+)/issues/(?P<url_number>\d+)"
        + r"|(?<![\w/])(?P<repo>[\w.-]+/[\w.-]+)?#(?P<number>\d+)"
        + r")\b",
        re.IGNORECASE,
    )


def _prose(text: str) -> Iterator[str]:
    """*text*'s lines outside code: fenced blocks and inline code spans are
    skipped, as GitHub skips them. The whole text is read, as a merge reads it
    (`fr.record.pr_body._prose_lines`, `as_github`)."""
    from fr.record.pr_body import _prose_lines

    for prose in _prose_lines(text, as_github=True):
        if prose is not None:
            yield prose[1]


def _closing_refs(repo: str, *texts: str | None, host: str = GITHUB_HOST) -> list[dict[str, Any]]:
    """`closingIssuesReferences` (§A row 1): the issues a PR closes, parsed from
    its title and body as GitHub parses them — a closing keyword (`close[sd]?`,
    `fix(e[sd])?`, `resolve[sd]?`) at a word boundary, outside fenced and inline
    code, followed by a same-repo `#n`, an `owner/repo#n` or an issue URL on the
    repo's own GitHub *host*. Refs are built on *host* (a GHE host for a GHE
    client), never a hard-coded github.com. In first-seen order, each once.

    Gap: an issue linked by hand in the PR sidebar is invisible to REST, and the
    GraphQL node ids (`id`, `repository.id`, `owner.id`) are not produced; collect
    reads only owner login, repo name and number."""
    pattern = _closing_ref_pattern(host.lower())
    seen: list[tuple[str, int]] = []
    for text in texts:
        for line in _prose(text or ""):
            for m in pattern.finditer(line):
                target = m["url_repo"] or m["repo"] or repo
                number = int(m["url_number"] or m["number"])
                if (target.lower(), number) not in {(r.lower(), n) for r, n in seen}:
                    seen.append((target, number))
    out = []
    for target, number in seen:
        owner, name = target.split("/", 1)
        out.append(
            {
                "number": number,
                "repository": {"name": name, "owner": {"login": owner}},
                "url": f"https://{host}/{owner}/{name}/issues/{number}",
            }
        )
    return out


def _upper(value: object) -> str:
    return str(value).upper() if value else ""


def _rollup(
    check_runs: Iterable[dict[str, Any]],
    statuses: Iterable[dict[str, Any]],
    workflow_runs: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """`statusCheckRollup` (§A rows 2-3): `commits/{sha}/check-runs` plus
    `commits/{sha}/status`, in the rollup's entry shape. `status` and
    `conclusion` upper-cased; `startedAt`/`completedAt` empty for a run not yet
    started/finished (GraphQL's `0001-` zero time is never produced, and
    `collect._latest_runs` reads both the same). `workflowName` from the Actions
    run whose `check_suite_id` is the check run's suite; a check run with no
    Actions run (another app) gets the app's name."""
    by_suite = {r.get("check_suite_id"): str(r.get("name") or "") for r in workflow_runs}
    out: list[dict[str, Any]] = []
    for c in check_runs:
        suite = (c.get("check_suite") or {}).get("id")
        workflow = by_suite.get(suite)
        if workflow is None:
            workflow = str((c.get("app") or {}).get("name") or "")
        out.append(
            {
                "__typename": "CheckRun",
                "completedAt": c.get("completed_at") or "",
                "conclusion": _upper(c.get("conclusion")),
                "detailsUrl": c.get("details_url") or "",
                "name": c.get("name") or "",
                "startedAt": c.get("started_at") or "",
                "status": _upper(c.get("status")),
                "workflowName": workflow,
            }
        )
    for s in statuses:
        out.append(
            {
                "__typename": "StatusContext",
                "context": s.get("context") or "",
                "startedAt": s.get("created_at") or "",
                "state": _upper(s.get("state")),
                "targetUrl": s.get("target_url") or "",
            }
        )
    return out


_MERGEABLE: dict[object, str] = {True: "MERGEABLE", False: "CONFLICTING"}


def _merge_state(pull: dict[str, Any]) -> tuple[str, str]:
    """`mergeable`, `mergeStateStatus` (§A row 4) from `GET pulls/{n}`, mapped
    to the GraphQL enums; `null` while GitHub computes them → `UNKNOWN`."""
    mergeable = _MERGEABLE.get(pull.get("mergeable"), "UNKNOWN")
    state = _upper(pull.get("mergeable_state")) or "UNKNOWN"
    return mergeable, state


_DECISIVE = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}


def _review_decision(reviews: Iterable[dict[str, Any]]) -> str:
    """`reviewDecision` (§A row 5) from `GET pulls/{n}/reviews`: the latest
    decisive review per reviewer (a comment-only review neither grants nor
    withdraws one). Any outstanding CHANGES_REQUESTED wins, else any APPROVED,
    else "" (GraphQL's empty answer for no decision). Gap: GraphQL also answers
    REVIEW_REQUIRED from branch protection, which REST does not combine here."""
    latest: dict[str, str] = {}
    for r in reviews:
        state = _upper(r.get("state"))
        login = str((r.get("user") or {}).get("login") or "")
        if state in _DECISIVE:
            latest[login] = state
    decisions = set(latest.values())
    if "CHANGES_REQUESTED" in decisions:
        return "CHANGES_REQUESTED"
    if "APPROVED" in decisions:
        return "APPROVED"
    return ""


def _pr_state(pull: dict[str, Any]) -> str:
    if pull.get("merged_at"):
        return "MERGED"
    return _upper(pull.get("state")) or "OPEN"


def _author(user: dict[str, Any] | None) -> dict[str, Any] | None:
    """`author`: login, node id and bot flag. Gap: gh's `name` is not on REST
    list records, so it is absent."""
    if not user:
        return None
    return {
        "id": user.get("node_id") or "",
        "is_bot": user.get("type") == "Bot",
        "login": user.get("login") or "",
    }


def _cross_repo(pull: dict[str, Any]) -> bool:
    """`isCrossRepository` (§A row 6): head and base repos differ (a deleted
    fork's head has no repo: cross-repository)."""
    head = ((pull.get("head") or {}).get("repo") or {}).get("full_name")
    base = ((pull.get("base") or {}).get("repo") or {}).get("full_name")
    return head != base


def _pr_record(repo: str, pull: dict[str, Any], host: str = GITHUB_HOST) -> dict[str, Any]:
    """A REST pull as `fr.gh.PR_LIST_FIELDS` plus `headRefOid`; closing refs on *host*."""
    return {
        "author": _author(pull.get("user")),
        "closingIssuesReferences": _closing_refs(
            repo, pull.get("title"), pull.get("body"), host=host
        ),
        "createdAt": pull.get("created_at"),
        "headRefName": (pull.get("head") or {}).get("ref") or "",
        "headRefOid": (pull.get("head") or {}).get("sha") or "",
        "isCrossRepository": _cross_repo(pull),
        "isDraft": bool(pull.get("draft")),
        "mergedAt": pull.get("merged_at"),
        "number": pull["number"],
        "state": _pr_state(pull),
        "title": pull.get("title") or "",
        "url": pull.get("html_url") or "",
    }


_CHANGE_TYPE = {"removed": "DELETED"}


def _file_record(f: dict[str, Any]) -> dict[str, Any]:
    status = str(f.get("status") or "")
    return {
        "path": f.get("filename") or "",
        "additions": f.get("additions", 0),
        "deletions": f.get("deletions", 0),
        "changeType": _CHANGE_TYPE.get(status, status.upper()),
    }


def _label_record(label: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": label.get("node_id") or "",
        "name": label.get("name") or "",
        "description": label.get("description") or "",
        "color": label.get("color") or "",
    }


def _issue_record(issue: dict[str, Any]) -> dict[str, Any]:
    """A REST issue as every field `gh issue list/view --json` gives fr.
    `stateReason` (§A row 7) is `state_reason` upper-cased."""
    return {
        "body": issue.get("body") or "",
        "closed": issue.get("state") == "closed",
        "author": _author(issue.get("user")),
        "closedAt": issue.get("closed_at"),
        "createdAt": issue.get("created_at"),
        "labels": [_label_record(lbl) for lbl in issue.get("labels") or []],
        "number": issue["number"],
        "state": _upper(issue.get("state")),
        "stateReason": _upper(issue.get("state_reason")),
        "title": issue.get("title") or "",
        "updatedAt": issue.get("updated_at"),
        "url": issue.get("html_url") or "",
    }


_COMMENT_ID = re.compile(r"#issuecomment-(\d+)$")


def _comment_record(c: dict[str, Any]) -> dict[str, Any]:
    """`list_issue_comments`' record; the id from `html_url` (§A row 8), the same
    `#issuecomment-<id>` shape the GraphQL client parses."""
    m = _COMMENT_ID.search(str(c.get("html_url") or ""))
    return {
        "association": c.get("author_association") or "",
        "author": (c.get("user") or {}).get("login", ""),
        "body": c.get("body") or "",
        "created_at": c.get("created_at") or "",
        "id": int(m.group(1)) if m else None,
    }


_BUCKET = {
    "SUCCESS": "pass",
    "SKIPPED": "skipping",
    "NEUTRAL": "skipping",
    "CANCELLED": "cancel",
    "FAILURE": "fail",
    "ERROR": "fail",
    "TIMED_OUT": "fail",
    "ACTION_REQUIRED": "fail",
    "STARTUP_FAILURE": "fail",
    "STALE": "fail",
}


def _check_row(entry: dict[str, Any]) -> dict[str, Any]:
    """One rollup entry as `gh pr checks --json name,bucket,state` renders it."""
    if entry.get("__typename") == "StatusContext":
        name, state = entry.get("context") or "", entry.get("state") or ""
    else:
        name = entry.get("name") or ""
        state = (
            entry.get("conclusion") if entry.get("status") == "COMPLETED" else entry.get("status")
        ) or ""
    return {"name": name, "bucket": _BUCKET.get(state, "pending"), "state": state}


def _pr_base_sha(pulls: Iterable[dict[str, Any]] | None, sha: str) -> str:
    """The base sha of the PR whose head is *sha* in a check run's (or Actions
    run's) `pull_requests`; "" when no listed PR's head is *sha* (a merged PR, a
    push run, or a PR whose head has moved on: GitHub lists the PR as it is NOW,
    so another PR's base, or this PR's current one, may not be the base CI
    merged with — spec §I step 6, p2-r3)."""
    chosen = next((p for p in pulls or [] if (p.get("head") or {}).get("sha") == sha), None)
    return str(((chosen or {}).get("base") or {}).get("sha") or "")


def _commit_check_records(
    check_runs: Iterable[dict[str, Any]],
    statuses: Iterable[dict[str, Any]],
    workflow_runs: Iterable[dict[str, Any]],
    sha: str,
) -> list[dict[str, Any]]:
    """`GhClient.commit_checks` (spec 2026-10-07-cloud-triage §I): one record
    per check on *sha*, `{name, workflow, status, conclusion, url, base_sha}`,
    the latest per (workflow, name) as `collect._latest_runs` picks it (a
    failed attempt re-run green is one green record; a status context keeps
    its newest state). `status` and `conclusion` are GitHub's lower-case REST
    words (`completed`/`in_progress`/…, `success`/`failure`/…; "" while
    unfinished); a commit status maps `pending` to status `pending`, any other
    state to status `completed` with that state as its conclusion. `base_sha` is
    the PR's base sha as the check run (else its suite's Actions run) reports
    it — "" for a status context, or where GitHub names no PR."""
    from fr.triage.collect import _latest_runs

    runs, sts, actions = list(check_runs), list(statuses), list(workflow_runs)
    entries = _rollup(runs, sts, actions)
    source = {id(e): src for e, src in zip(entries, [*runs, *sts], strict=True)}
    suite_base = {
        r.get("check_suite_id"): _pr_base_sha(r.get("pull_requests"), sha) for r in actions
    }
    out: list[dict[str, Any]] = []
    for entry in _latest_runs(entries):
        src = source[id(entry)]
        if entry["__typename"] == "StatusContext":
            state = str(src.get("state") or "").lower()
            done = state != "pending"
            out.append(
                {
                    "name": entry["context"],
                    "workflow": "",
                    "status": "completed" if done else "pending",
                    "conclusion": state if done else "",
                    "url": entry["targetUrl"],
                    "base_sha": "",
                }
            )
            continue
        suite = (src.get("check_suite") or {}).get("id")
        out.append(
            {
                "name": entry["name"],
                "workflow": entry["workflowName"],
                "status": str(src.get("status") or "").lower(),
                "conclusion": str(src.get("conclusion") or "").lower(),
                "url": str(src.get("html_url") or src.get("details_url") or ""),
                "base_sha": _pr_base_sha(src.get("pull_requests"), sha)
                or suite_base.get(suite, ""),
            }
        )
    return out


def _ci(rollup: list[dict[str, Any]]) -> str:
    """`list_linked_prs`' `ci`: PASS / FAIL / PENDING / NONE over the latest run of
    each check (the GraphQL rollup's `state`, collapsed as `_coerce_ci_state`)."""
    from fr.triage.collect import _latest_runs

    rows = [_check_row(e)["bucket"] for e in _latest_runs(rollup)]
    if not rows:
        return "NONE"
    if any(b in {"fail", "cancel"} for b in rows):
        return "FAIL"
    if any(b == "pending" for b in rows):
        return "PENDING"
    return "PASS"


def _pr_url_parts(url: str) -> tuple[str, int] | None:
    m = re.match(r"^https?://[^/]+/([\w.-]+/[\w.-]+)/pull/(\d+)", url.strip())
    return (m.group(1), int(m.group(2))) if m else None


def _q(segment: str) -> str:
    return urllib.parse.quote(segment, safe="")


def _is_404(exc: GhError) -> bool:
    text = f"{exc} {exc.stderr}".lower()
    return "http 404" in text or "not found" in text


def _is_absent_label(exc: GhError) -> bool:
    """The 404 GitHub answers a label removal when the issue does not carry the
    label: message "Label does not exist" (captured,
    `tests/fixtures/github_rest/refused/label-remove-absent.*`)."""
    return _is_404(exc) and "label does not exist" in f"{exc} {exc.stderr} {exc.stdout}".lower()


STATE_REASONS = frozenset({"completed", "not_planned", "reopened"})
"""GitHub's `state_reason` spellings (§A)."""


def _state_reason(reason: str) -> str:
    """*reason* in GitHub's spelling: `not planned` / `NOT_PLANNED` → `not_planned`.
    An unknown reason raises before any call is made."""
    spelled = re.sub(r"[\s-]+", "_", reason.strip().lower())
    if spelled not in STATE_REASONS:
        raise ValueError(
            f"unknown issue close reason {reason!r}: GitHub takes one of {sorted(STATE_REASONS)}"
        )
    return spelled


def _project(record: dict[str, Any], fields: str) -> dict[str, Any]:
    """*record* cut to *fields*. A field the REST record cannot produce raises, as
    `gh --json` does on an unknown field, rather than answering None for it."""
    wanted = [f for f in fields.split(",") if f]
    unknown = [f for f in wanted if f not in record]
    if unknown:
        raise GhError(
            f'Unknown JSON field: "{unknown[0]}" (the github-rest record has: '
            f"{', '.join(sorted(record))})"
        )
    return {f: record[f] for f in wanted}


# ---------------------------------------------------------------------------
# The client.
# ---------------------------------------------------------------------------


class RealGhRestClient:
    """`GhClient` over `gh api` REST routes (spec 2026-10-07-cloud-triage §A).

    `host` is a GitHub Enterprise host, threaded as `GH_HOST` through
    `fr.gh.host_scope`, behind the same trust gate as `RealGhClient`. `run` is
    how one `gh` command runs (`GhRun`); `fr.gh._run_gh` when None."""

    PER_PAGE = 100

    def __init__(self, host: str | None = None, run: GhRun | None = None) -> None:
        self._host = host
        self._run = run

    @property
    def _web_host(self) -> str:
        """The host issue URLs live on: the GHE host, else github.com."""
        return self._host or GITHUB_HOST

    # ---- transport ----

    def _gh(self, args: list[str]) -> str:
        with _gh.host_scope(self._host):
            _gh.host_env()  # the trust gate, before any process starts
            return (self._run or _gh._run_gh)(args)

    def _api(
        self,
        route: str,
        *,
        method: str = "GET",
        fields: dict[str, Any] | None = None,
        accept: str | None = None,
    ) -> Any:
        """One `gh api` call; its JSON (None for an empty answer). String fields
        go as `-f` (never read as a file), bools and ints as typed `-F`, a list
        as repeated `-f key[]=v`."""
        argv = ["api"]
        if method != "GET":
            argv += ["-X", method]
        if accept:
            argv += ["-H", accept]
        argv.append(route)
        for key, value in (fields or {}).items():
            if isinstance(value, bool):
                argv += ["-F", f"{key}={'true' if value else 'false'}"]
            elif isinstance(value, int):
                argv += ["-F", f"{key}={value}"]
            elif isinstance(value, list):
                for item in value:
                    argv += ["-f", f"{key}[]={item}"]
            else:
                argv += ["-f", f"{key}={value}"]
        out = self._gh(argv)
        if accept:
            return out
        return json.loads(out) if out.strip() else None

    def _paged(
        self,
        route: str,
        *,
        limit: int | None = None,
        key: str | None = None,
        keep: Callable[[dict[str, Any]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        """Every record of a list route, `per_page=PER_PAGE`, page by page, until
        a short page or *limit* kept records. *key* names the list inside an
        object answer (`check_runs`); *keep* filters before counting."""
        out: list[dict[str, Any]] = []
        sep = "&" if "?" in route else "?"
        page = 1
        while limit is None or len(out) < limit:
            answer = self._api(f"{route}{sep}per_page={self.PER_PAGE}&page={page}")
            items = (answer or {}).get(key, []) if key else (answer or [])
            out += [i for i in items if keep is None or keep(i)]
            if len(items) < self.PER_PAGE:
                break
            page += 1
        return out if limit is None else out[:limit]

    def _repo_of(self, cwd: Path) -> str:
        slug = _hosts.origin_slug(cwd)
        if not slug:
            raise GhError(f"cannot tell the GitHub repo of {cwd} (no `origin` remote)")
        return slug

    # ---- shared reads ----

    def _pull(self, repo: str, number: int) -> dict[str, Any]:
        return dict(self._api(f"repos/{repo}/pulls/{number}"))

    def _rollup_for(self, repo: str, sha: str) -> list[dict[str, Any]]:
        runs = self._paged(f"repos/{repo}/commits/{sha}/check-runs", key="check_runs")
        status = self._api(f"repos/{repo}/commits/{sha}/status") or {}
        actions = (
            self._paged(f"repos/{repo}/actions/runs?head_sha={sha}", key="workflow_runs")
            if runs
            else []
        )
        return _rollup(runs, status.get("statuses") or [], actions)

    def _files(self, repo: str, number: int) -> list[dict[str, Any]]:
        return [_file_record(f) for f in self._paged(f"repos/{repo}/pulls/{number}/files")]

    def _pulls_by_head(self, repo: str, branch: str) -> list[dict[str, Any]]:
        owner = repo.split("/", 1)[0]
        head = urllib.parse.quote(f"{owner}:{branch}", safe=":/")
        return self._paged(f"repos/{repo}/pulls?head={head}&state=all")

    # ---- GhClient: issues ----

    def view_issue(self, repo: str, number: int) -> dict[str, Any]:
        raw = self._api(f"repos/{repo}/issues/{number}")
        return {
            "state": _upper(raw.get("state")),
            "labels": [lbl["name"] for lbl in raw.get("labels") or [] if "name" in lbl],
            "assignees": [a["login"] for a in raw.get("assignees") or [] if "login" in a],
            "body": raw.get("body") or "",
        }

    def view_issue_record(self, repo: str, number: int) -> dict[str, Any]:
        return _project(
            _issue_record(self._api(f"repos/{repo}/issues/{number}")), _gh.ISSUE_VIEW_FIELDS
        )

    def list_issues(
        self, repo: str, state: str, limit: int, fields: str | None = None
    ) -> list[dict[str, Any]]:
        raw = self._paged(
            f"repos/{repo}/issues?state={state}",
            limit=limit,
            keep=lambda i: "pull_request" not in i,
        )
        return [_project(_issue_record(i), fields or _gh.ISSUE_LIST_FIELDS) for i in raw]

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        return [_comment_record(c) for c in self._paged(f"repos/{repo}/issues/{number}/comments")]

    def list_linked_prs(self, repo: str, issue_number: int) -> list[dict[str, Any]]:
        """PRs that close the issue: the PRs its timeline cross-references whose
        title or body closes it (`_closing_refs`). Same sidebar gap as §A row 1.

        Title, body, state, draft and merged come from the timeline event's own
        `source.issue`; `pulls/{n}` is read only for a PR that closes the issue
        (for its head sha, which the CI rollup needs). A PR that only mentions
        the issue is never fetched, so a cross-repo mention the token may not
        read (403) cannot fail the call."""
        events = self._paged(f"repos/{repo}/issues/{issue_number}/timeline")
        seen: set[tuple[str, int]] = set()
        out: list[dict[str, Any]] = []
        for e in events:
            src = (e.get("source") or {}).get("issue") or {}
            if e.get("event") != "cross-referenced" or "pull_request" not in src:
                continue
            src_repo = str((src.get("repository") or {}).get("full_name") or repo)
            key = (src_repo.lower(), int(src["number"]))
            if key in seen:
                continue
            seen.add(key)
            closes = _closing_refs(src_repo, src.get("title"), src.get("body"), host=self._web_host)
            target = {(f"{r['repository']['owner']['login']}/{r['repository']['name']}".lower(),
                       r["number"]) for r in closes}  # fmt: skip
            if (repo.lower(), issue_number) not in target:
                continue
            head_sha = self._pull(src_repo, int(src["number"]))["head"]["sha"]
            out.append(
                {
                    "url": src.get("html_url", ""),
                    "state": "CLOSED" if src.get("state") == "closed" else "OPEN",
                    "merged": bool((src.get("pull_request") or {}).get("merged_at")),
                    "draft": bool(src.get("draft")),
                    "ci": _ci(self._rollup_for(src_repo, head_sha)),
                }
            )
        return out

    # ---- GhClient: pull requests ----

    def list_prs(self, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        rest_state = {"merged": "closed"}.get(state, state)
        keep = (lambda p: bool(p.get("merged_at"))) if state == "merged" else None
        raw = self._paged(f"repos/{repo}/pulls?state={rest_state}", limit=limit, keep=keep)
        fields = _gh.PR_LIST_FIELDS.split(",")
        return [{f: _pr_record(repo, p, self._web_host)[f] for f in fields} for p in raw]

    def list_open_prs(self, repo: str, limit: int) -> list[dict[str, Any]]:
        """`fr.gh.OPEN_PR_LIST_FIELDS`: the list fields plus files, checks,
        merge state and review decision, read per open PR (as GraphQL's are)."""
        out = []
        for p in self._paged(f"repos/{repo}/pulls?state=open", limit=limit):
            pull = self._pull(repo, p["number"])
            mergeable, merge_state = _merge_state(pull)
            reviews = self._paged(f"repos/{repo}/pulls/{p['number']}/reviews")
            record = _pr_record(repo, pull, self._web_host)
            record.update(
                files=self._files(repo, p["number"]),
                statusCheckRollup=self._rollup_for(repo, record["headRefOid"]),
                mergeable=mergeable,
                mergeStateStatus=merge_state,
                reviewDecision=_review_decision(reviews),
            )
            out.append(record)
        return out

    def list_prs_by_head(self, repo: str, branch: str) -> list[dict[str, Any]]:
        out = []
        for p in self._pulls_by_head(repo, branch):
            record = _pr_record(repo, p, self._web_host)
            record["files"] = self._files(repo, p["number"])
            out.append(record)
        return out

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        pull = self._pull(repo, number)
        mergeable, merge_state = _merge_state(pull)
        return {
            "state": _pr_state(pull),
            "draft": bool(pull.get("draft")),
            "head_oid": pull["head"]["sha"],
            "head_ref": pull["head"]["ref"],
            "base_ref": pull["base"]["ref"],
            "mergeable": mergeable,
            "merge_state": merge_state,
            # REST names a test-merge commit while a PR is open; GraphQL only a real one.
            "merge_commit": (pull.get("merge_commit_sha") or "") if pull.get("merged_at") else "",
            "title": pull.get("title") or "",
            "body": pull.get("body") or "",
        }

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        from fr.triage.collect import _latest_runs

        pull = self._pull(repo, number)
        return [_check_row(e) for e in _latest_runs(self._rollup_for(repo, pull["head"]["sha"]))]

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        """`gh pr checks --required` (§A): the checks whose names the base branch
        requires — classic protection's contexts, read from `GET branches/{base}`
        (its `protection` summary needs no admin, unlike the
        `.../protection/required_status_checks` route, which a cloud session's
        token is refused), plus any ruleset's `required_status_checks` rule."""
        pull = self._pull(repo, number)
        required = set(self.required_check_names(repo, pull["base"]["ref"]))
        if not required:
            return []
        from fr.triage.collect import _latest_runs

        rollup = _latest_runs(self._rollup_for(repo, pull["head"]["sha"]))
        return [row for row in map(_check_row, rollup) if row["name"] in required]

    def required_check_names(self, repo: str, base: str) -> list[str]:
        """The names *base* requires (spec §I, p2-r1): classic protection's
        contexts from `GET branches/{base}` (its `protection` summary needs no
        admin, unlike `.../protection/required_status_checks`, which a cloud
        session's token is refused) plus every ruleset's `required_status_checks`
        rule. Names only: no commit is read, so a check not created yet counts.
        `RealGhClient.required_check_names` is this method."""
        b = _q(base)
        branch = self._api(f"repos/{repo}/branches/{b}") or {}
        required_cfg = (branch.get("protection") or {}).get("required_status_checks") or {}
        required = set(required_cfg.get("contexts") or [])
        required |= {c.get("context") for c in required_cfg.get("checks") or []}
        for rule in self._api(f"repos/{repo}/rules/branches/{b}") or []:
            if rule.get("type") == "required_status_checks":
                params = rule.get("parameters") or {}
                required |= {c.get("context") for c in params.get("required_status_checks") or []}
        return sorted(str(n) for n in required if n)

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None:
        """`{number, url}` of *branch*'s open PR from one `pulls?head=&state=open`
        page — no per-PR file list (p2-r7). `RealGhClient` calls this too."""
        owner = repo.split("/", 1)[0]
        head = urllib.parse.quote(f"{owner}:{branch}", safe=":/")
        pulls = self._paged(f"repos/{repo}/pulls?head={head}&state=open", limit=1)
        if not pulls:
            return None
        return {"number": int(pulls[0]["number"]), "url": str(pulls[0].get("html_url") or "")}

    def commit_checks(self, repo: str, sha: str) -> list[dict[str, Any]]:
        """Every check on *sha* (spec §I): `commits/{sha}/check-runs?filter=latest`,
        `commits/{sha}/status`, and the Actions runs naming each run's workflow.
        `RealGhClient.commit_checks` is this method: REST works on either backend."""
        runs = self._paged(f"repos/{repo}/commits/{sha}/check-runs?filter=latest", key="check_runs")
        status = self._api(f"repos/{repo}/commits/{sha}/status") or {}
        actions = (
            self._paged(f"repos/{repo}/actions/runs?head_sha={sha}", key="workflow_runs")
            if runs
            else []
        )
        return _commit_check_records(runs, status.get("statuses") or [], actions, sha)

    def pr_status_by_url(self, url: str) -> dict[str, Any] | None:
        """None on any failure, as the `GhClient` contract says (fr-vk holds the card)."""
        parts = _pr_url_parts(url)
        if parts is None:
            return None
        try:
            pull = self._pull(*parts)
        except GhError as exc:
            if isinstance(exc, HostRefusedError):
                raise
            return None
        return {"state": _pr_state(pull), "draft": bool(pull.get("draft"))}

    def pr_body(self, ref: str, *, cwd: Path) -> str:
        parts = _pr_url_parts(ref)
        if parts is not None:
            return str(self._pull(*parts).get("body") or "")
        repo = self._repo_of(cwd)
        if ref.isdigit():
            return str(self._pull(repo, int(ref)).get("body") or "")
        pulls = self._pulls_by_head(repo, ref)
        if not pulls:
            raise GhError(f"no pull requests found for branch {ref!r} in {repo}")
        chosen = next((p for p in pulls if p.get("state") == "open"), pulls[0])
        return str(chosen.get("body") or "")

    def pr_for_branch(
        self, branch: str, *, cwd: Path, run: CommandRunner | None = None
    ) -> dict[str, Any] | None:
        """None when there is no PR or the call fails (the `GhClient` contract).
        `owner/repo` comes from the checkout's `origin` URL."""
        slug = _hosts.origin_slug(cwd)
        if not slug:
            return None
        owner = slug.split("/", 1)[0]
        head = urllib.parse.quote(f"{owner}:{branch}", safe=":/")
        route = f"repos/{slug}/pulls?head={head}&state=all&per_page={self.PER_PAGE}&page=1"
        with _gh.host_scope(self._host):
            result = (run or run_cli)(["gh", "api", route], cwd=cwd, env=_gh.host_env())
        if result.returncode != 0 or not (result.stdout or "").strip():
            return None
        try:
            pulls = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(pulls, list) or not pulls:
            return None
        chosen = next((p for p in pulls if p.get("state") == "open"), pulls[0])
        return {
            "state": _pr_state(chosen),
            "url": chosen.get("html_url", ""),
            "mergedAt": chosen.get("merged_at"),
        }

    # ---- GhClient: repo and files ----

    def default_branch(self, *, cwd: Path, run: CommandRunner | None = None) -> str | None:
        """None when it cannot say (the `GhClient` contract)."""
        slug = _hosts.origin_slug(cwd)
        if not slug:
            return None
        with _gh.host_scope(self._host):
            result = (run or run_cli)(
                ["gh", "api", f"repos/{slug}", "--jq", ".default_branch"],
                cwd=cwd,
                env=_gh.host_env(),
            )
        out = (result.stdout or "").strip()
        return out if result.returncode == 0 and out else None

    def issues_enabled(self, repo: str | None = None) -> bool | None:
        """None when it cannot say (the `GhClient` contract)."""
        if not repo:
            return None
        try:
            raw = self._api(f"repos/{repo}")
        except GhError as exc:
            if isinstance(exc, HostRefusedError):
                raise
            return None
        value = raw.get("has_issues") if isinstance(raw, dict) else None
        return value if isinstance(value, bool) else None

    def repo_visibility(self, repo: str) -> str:
        """`visibility` of `GET repos/{repo}`, else `private` read as public/private."""
        raw = self._api(f"repos/{repo}")
        value = raw.get("visibility") if isinstance(raw, dict) else None
        if isinstance(value, str) and value:
            return value.lower()
        if isinstance(raw, dict) and isinstance(raw.get("private"), bool):
            return "private" if raw["private"] else "public"
        raise GhError(f"GET repos/{repo}: no visibility in the answer")

    def repo_merge_methods(self, repo: str) -> dict[str, Any]:
        """`allowed` from the repo's `allow_*` flags. Gap: REST has no
        `viewerDefaultMergeMethod`, so `default` is None."""
        raw = self._api(f"repos/{repo}")
        flags = (
            ("merge", "allow_merge_commit"),
            ("squash", "allow_squash_merge"),
            ("rebase", "allow_rebase_merge"),
        )
        return {"default": None, "allowed": [m for m, key in flags if raw.get(key)]}

    def list_repos(self, owner: str, limit: int) -> list[dict[str, Any]]:
        try:
            raw = self._paged(f"orgs/{owner}/repos", limit=limit)
        except GhError as exc:
            if not _is_404(exc):
                raise
            raw = self._paged(f"users/{owner}/repos", limit=limit)
        return [{"name": r.get("name", ""), "isArchived": bool(r.get("archived"))} for r in raw]

    def list_labels(self, repo: str) -> list[dict[str, str | None]]:
        """`fr.gh.list_labels`' records (`name`, `color`, `description`); not a
        `GhClient` method."""
        return [
            {
                "name": lbl.get("name"),
                "color": lbl.get("color"),
                "description": lbl.get("description"),
            }
            for lbl in self._paged(f"repos/{repo}/labels")
        ]

    def viewer_login(self) -> str:
        return str(self._api("user")["login"])

    def file_exists(self, repo: str, path: str) -> bool:
        try:
            self._api(f"repos/{repo}/contents/{path}")
        except GhError as exc:
            if _is_404(exc):
                return False
            raise
        return True

    def list_dir(self, repo: str, path: str) -> list[str]:
        try:
            raw = self._api(f"repos/{repo}/contents/{path}")
        except GhError as exc:
            if _is_404(exc):
                return []
            raise
        return [str(e["name"]) for e in raw] if isinstance(raw, list) else []

    def read_file(self, repo: str, path: str) -> str:
        return str(self._api(f"repos/{repo}/contents/{path}", accept=RAW_ACCEPT))

    def read_file_at_ref(self, repo: str, path: str, ref: str) -> str:
        endpoint = f"repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}?ref={_q(ref)}"
        return str(self._api(endpoint, accept=RAW_ACCEPT + "+json"))

    def closing_ref(self, repo: str, number: int) -> str:
        return f"Closes {repo}#{number}"

    # ---- GhClient: writes ----

    def edit_issue_labels(
        self, repo: str, number: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        if add:
            self._api(
                f"repos/{repo}/issues/{number}/labels",
                method="POST",
                fields={"labels": sorted(add)},
            )
        for name in sorted(remove):
            try:
                self._api(f"repos/{repo}/issues/{number}/labels/{_q(name)}", method="DELETE")
            except GhError as exc:
                # `gh issue edit --remove-label` is idempotent: GitHub's 404
                # "Label does not exist" is the label already gone (§A). Any
                # other 404 (no such issue, no such repo) still raises.
                if not _is_absent_label(exc):
                    raise

    def edit_issue_state(
        self, repo: str, number: int, *, state: str, reason: str | None = None
    ) -> None:
        if state not in {"OPEN", "CLOSED"}:
            raise ValueError(f"unknown issue state: {state!r}")
        fields: dict[str, Any] = {"state": state.lower()}
        if reason:
            fields["state_reason"] = _state_reason(reason)
        self._api(f"repos/{repo}/issues/{number}", method="PATCH", fields=fields)

    def edit_issue_body(self, repo: str, number: int, body: str) -> None:
        self._api(f"repos/{repo}/issues/{number}", method="PATCH", fields={"body": body})

    def comment_issue(self, repo: str, number: int, body: str) -> None:
        self._api(f"repos/{repo}/issues/{number}/comments", method="POST", fields={"body": body})

    def create_issue(self, repo: str, *, title: str, body: str, labels: frozenset[str]) -> str:
        fields: dict[str, Any] = {"title": title, "body": body}
        if labels:
            fields["labels"] = sorted(labels)
        made = self._api(f"repos/{repo}/issues", method="POST", fields=fields)
        return str(made["html_url"])

    def ensure_labels(self, repo: str, labels: list[Any]) -> None:
        """Create each label, or update it when it exists (`gh label create
        --force`'s idempotence, spelled as REST)."""
        for lbl in labels:
            if isinstance(lbl, str):
                ld = LabelDef(name=lbl, color="ededed", description="")
            elif isinstance(lbl, LabelDef):
                ld = lbl
            else:
                ld = LabelDef(
                    name=getattr(lbl, "name", None) or lbl["name"],
                    color=getattr(lbl, "color", None) or lbl.get("color", "ededed"),
                    description=getattr(lbl, "description", None) or lbl.get("description", ""),
                )
            fields = {"color": ld.color, "description": ld.description}
            try:
                self._api(f"repos/{repo}/labels", method="POST", fields={"name": ld.name, **fields})
            except GhError as exc:
                if "already_exists" not in f"{exc} {exc.stderr} {exc.stdout}":
                    raise
                self._api(f"repos/{repo}/labels/{_q(ld.name)}", method="PATCH", fields=fields)

    def edit_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        self._api(
            f"repos/{repo}/issues/comments/{comment_id}", method="PATCH", fields={"body": body}
        )

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        """`PUT pulls/{n}/merge` with `sha`: GitHub refuses when the head moved."""
        if method not in MERGE_METHODS:
            raise ValueError(f"merge method must be one of {sorted(MERGE_METHODS)}, got {method!r}")
        self._api(
            f"repos/{repo}/pulls/{number}/merge",
            method="PUT",
            fields={"merge_method": method, "sha": head_sha},
        )

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int:
        made = self.create_pr(repo, head=head, base=base, title=title, body=body, draft=False)
        return int(made["number"])

    def create_pr(
        self, repo: str, *, head: str, base: str, title: str, body: str, draft: bool
    ) -> dict[str, Any]:
        made = self._api(
            f"repos/{repo}/pulls",
            method="POST",
            fields={"head": head, "base": base, "title": title, "body": body, "draft": draft},
        )
        return {"number": int(made["number"]), "url": str(made["html_url"])}

    def close_pr(self, repo: str, number: int) -> None:
        self._api(f"repos/{repo}/pulls/{number}", method="PATCH", fields={"state": "closed"})

    def delete_branch(self, repo: str, branch: str) -> None:
        ref = urllib.parse.quote(branch, safe="/")
        self._api(f"repos/{repo}/git/refs/heads/{ref}", method="DELETE")

    def dispatch_workflow(self, repo: str, workflow: str, *, inputs: dict[str, str]) -> None:
        """`POST actions/workflows/{file}/dispatches` on the default branch."""
        ref = str(self._api(f"repos/{repo}")["default_branch"])
        fields: dict[str, Any] = {"ref": ref}
        fields.update({f"inputs[{k}]": v for k, v in inputs.items()})
        self._api(
            f"repos/{repo}/actions/workflows/{_q(workflow)}/dispatches",
            method="POST",
            fields=fields,
        )
