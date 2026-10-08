"""Production GhClient — wraps the `gh` CLI for v2's read/write surface.

Conforms to `vk.ghclient.GhClient`. Read methods (`view_issue`,
`list_linked_prs`) shape gh's JSON output into the contract that
`observe`/`diff` expect. Write methods (`edit_issue_*`, `create_issue`,
`ensure_labels`) delegate to the same `vk.gh` helpers v1 uses, so
existing retry / auth behaviour comes along for free.

Intentionally thin — no caching, no batching, no rate-limit
accounting. Each call is an independent `gh` subprocess. If we ever
need bulk reads, GraphQL batching belongs in this module (not in
`observe`).
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any, Concatenate, ParamSpec, TypeVar, cast

from fr import gh as _gh
from fr.ghclient import MERGE_METHODS, CommandRunner, run_cli
from fr.labels import LabelDef

# Re-exported for `fr.triage.collect`, which reads the forge only through the
# adapter and so imports no `fr.gh` (spec 2026-10-06-forge-remainder §4.A).
ORIGINS_ISSUE_LIST_FIELDS = _gh.ORIGINS_ISSUE_LIST_FIELDS

# `gh pr checks` exits 8 when any check is still pending; its JSON is on stdout.
_CHECKS_PENDING_EXIT = 8
# gh's two "nothing here" answers, both exit 1: `no required checks reported`
# (checks exist, none required) and `no checks reported` (the head has none at
# all yet, as every head does for a moment after a push; gh#952, gh#947).
_NO_CHECKS = ("no required checks reported", "no checks reported")
_PR_URL = re.compile(r"/pull/(\d+)\s*$", re.MULTILINE)


def workflow_run_args(repo: str, workflow: str, inputs: dict[str, str]) -> list[str]:
    """The `gh` argv (without the leading `gh`) that dispatches *workflow* on
    the default branch with *inputs*. One builder, so `fr verification
    prerelease --dry-run` prints exactly what the real dispatch runs."""
    argv = ["workflow", "run", workflow, "--repo", repo]
    for key, value in inputs.items():
        argv += ["-f", f"{key}={value}"]
    return argv


_P = ParamSpec("_P")
_R = TypeVar("_R")


def _hosted(
    method: Callable[Concatenate[RealGhClient, _P], _R],
) -> Callable[Concatenate[RealGhClient, _P], _R]:
    """Run `method`'s `gh` calls against the client's host (`fr.gh.host_scope`,
    spec 2026-10-06-forge-remainder §4.E). Every method that reaches `fr.gh`
    carries it; `test_every_gh_method_is_hosted` keeps it that way."""

    @functools.wraps(method)
    def wrapper(self: RealGhClient, /, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        with _gh.host_scope(self._host):
            # The trust gate runs BEFORE the body: a soft-fail method catches
            # `GhError` and would turn a refused host into "no PR" / "no
            # file" (review p1-r1). `GhHostRefusedError` propagates instead.
            _gh.host_env()
            return method(self, *args, **kwargs)

    wrapper.__fr_hosted__ = True  # type: ignore[attr-defined]
    return wrapper


_COMMENT_ID = re.compile(r"#issuecomment-(\d+)$")


def _comment_id(url: object) -> int | None:
    """The numeric comment id GitHub puts at the end of a comment's url, else None
    (`gh issue view --json comments` carries `url`, never the REST id)."""
    if not isinstance(url, str):
        return None
    m = _COMMENT_ID.search(url)
    return int(m.group(1)) if m else None


class RealGhClient:
    """Wraps `vk.gh` to satisfy the `GhClient` Protocol.

    `host` names a GitHub Enterprise instance: every `gh` this client runs
    gets `GH_HOST=<host>`. None (the default) leaves gh's own host resolution
    alone — the SaaS path, unchanged. A host gh is not logged into
    (`fr.gh.known_hosts`) is never threaded: each call fails closed with
    `GhError` instead — checked at call time, so building a client reads
    nothing (plan journal `p1-gh-host-trust-gate`)."""

    def __init__(self, host: str | None = None) -> None:
        self._host = host

    @_hosted
    def view_issue(self, repo: str, number: int) -> dict[str, Any]:
        """Fetch state, labels, assignees, body for an Issue.

        gh returns labels as `[{name, ...}, ...]` and assignees as
        `[{login, ...}, ...]`; the v2 contract is plain string lists, so
        coerce here. State is already `OPEN`/`CLOSED` from gh.
        """
        out = _gh._run_gh(
            [
                "issue",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "state,labels,assignees,body",
            ]
        )
        raw: dict[str, Any] = json.loads(out)
        return {
            "state": raw.get("state", ""),
            "labels": [lbl["name"] for lbl in raw.get("labels", []) if "name" in lbl],
            "assignees": [a["login"] for a in raw.get("assignees", []) if "login" in a],
            "body": raw.get("body", ""),
        }

    @_hosted
    def list_linked_prs(self, repo: str, issue_number: int) -> list[dict[str, Any]]:
        """Return PRs that close this Issue, shaped for `observe._to_pr_observation`.

        Uses GraphQL `closingIssuesReferences` (the canonical reverse
        link). CI state comes from `statusCheckRollup`; we collapse to
        PASS/FAIL/PENDING/NONE.
        """
        owner, name = repo.split("/", 1)
        query = """
        query($owner: String!, $name: String!, $number: Int!) {
          repository(owner: $owner, name: $name) {
            issue(number: $number) {
              closedByPullRequestsReferences(first: 20, includeClosedPrs: true) {
                nodes {
                  url
                  state
                  merged
                  isDraft
                  statusCheckRollup { state }
                }
              }
            }
          }
        }
        """
        try:
            out = _gh._run_gh(
                [
                    "api",
                    "graphql",
                    "-f",
                    f"query={query}",
                    "-F",
                    f"owner={owner}",
                    "-F",
                    f"name={name}",
                    "-F",
                    f"number={issue_number}",
                ]
            )
        except _gh.GhError:
            # Fail soft: an unreachable PR query shouldn't blow up the
            # whole `fr apply --dry-run`. Return [] and let downstream
            # diff/render proceed without PR observations.
            return []
        data = json.loads(out)
        nodes = (
            data.get("data", {})
            .get("repository", {})
            .get("issue", {})
            .get("closedByPullRequestsReferences", {})
            .get("nodes", [])
        )
        result: list[dict[str, Any]] = []
        for n in nodes:
            rollup = (n.get("statusCheckRollup") or {}).get("state", "")
            ci = _coerce_ci_state(rollup)
            # GraphQL PullRequestState is OPEN / CLOSED / MERGED. Our
            # observe() contract is OPEN / CLOSED only — `merged` is a
            # separate boolean. Coerce MERGED → CLOSED so the validator
            # accepts it; the `merged` field below preserves the distinction.
            raw_state = n.get("state", "OPEN")
            state = "CLOSED" if raw_state == "MERGED" else raw_state
            result.append(
                {
                    "url": n.get("url", ""),
                    "state": state,
                    "merged": bool(n.get("merged", False)),
                    "draft": bool(n.get("isDraft", False)),
                    "ci": ci,
                }
            )
        return result

    @_hosted
    def pr_status_by_url(self, url: str) -> dict[str, Any] | None:
        """`gh pr view <url>` accepts a bare PR URL directly (unlike
        glab's `mr view` / tea's `pulls`, which require a repo + numeric
        id — see the sibling adapters). Fails soft: None on any error."""
        try:
            out = _gh._run_gh(["pr", "view", url, "--json", "state,isDraft"])
        except _gh.GhError:
            return None
        raw: dict[str, Any] = json.loads(out)
        return {"state": raw.get("state", "OPEN"), "draft": bool(raw.get("isDraft", False))}

    @_hosted
    def edit_issue_labels(
        self,
        repo: str,
        number: int,
        *,
        add: frozenset[str],
        remove: frozenset[str],
    ) -> None:
        _gh.swap_issue_labels(
            repo=repo,
            number=number,
            add=sorted(add),
            remove=sorted(remove),
        )

    @_hosted
    def edit_issue_state(
        self,
        repo: str,
        number: int,
        *,
        state: str,
        reason: str | None = None,
    ) -> None:
        if state == "CLOSED":
            _gh.close_issue(repo=repo, number=number)
            return
        if state == "OPEN":
            _gh._run_gh(["issue", "reopen", str(number), "--repo", repo])
            return
        raise ValueError(f"unknown issue state: {state!r}")

    @_hosted
    def edit_issue_body(self, repo: str, number: int, body: str) -> None:
        _gh.edit_issue_body(repo=repo, number=number, body=body)

    @_hosted
    def create_issue(
        self,
        repo: str,
        *,
        title: str,
        body: str,
        labels: frozenset[str],
    ) -> str:
        return _gh.create_issue(
            repo=repo,
            title=title,
            body=body,
            labels=sorted(labels),
        )

    @_hosted
    def ensure_labels(self, repo: str, labels: list[Any]) -> None:
        """Coerce `list[str]` or `list[LabelDef]` to LabelDefs, then delegate."""
        defs: list[LabelDef] = []
        for lbl in labels:
            if isinstance(lbl, LabelDef):
                defs.append(lbl)
            elif isinstance(lbl, str):
                # Plain name → default color/description
                defs.append(LabelDef(name=lbl, color="ededed", description=""))
            else:
                # Dict-shaped or other; pull what we can
                name = getattr(lbl, "name", None) or lbl["name"]
                color = getattr(lbl, "color", None) or lbl.get("color", "ededed")
                description = getattr(lbl, "description", None) or lbl.get("description", "")
                defs.append(LabelDef(name=name, color=color, description=description))
        _gh.ensure_labels(repo=repo, labels=defs)

    @_hosted
    def comment_issue(self, repo: str, number: int, body: str) -> None:
        """Post a comment via `gh issue comment`."""
        _gh._run_gh(["issue", "comment", str(number), "--repo", repo, "--body", body])

    @_hosted
    def file_exists(self, repo: str, path: str) -> bool:
        """Contents-API existence probe on the default branch.

        `gh api` exits non-zero on 404; any other error also reads as
        "not found" — the spec-archival callers treat unresolved as
        "leave the spec in place", which is the safe direction.
        """
        from fr.gh import GhError

        try:
            _gh._run_gh(["api", f"repos/{repo}/contents/{path}", "--silent"])
            return True
        except GhError:
            return False

    @_hosted
    def list_dir(self, repo: str, path: str) -> list[str]:
        """Entry names under `path` (contents API). `[]` on any GhError.

        A 404 (missing dir) reads as "no such dir" — the safe direction, same
        fail-soft posture as `file_exists`. The contents API returns a JSON
        array for a directory; `--jq .[].name` yields one name per line.
        """
        from fr.gh import GhError

        try:
            out = _gh._run_gh(["api", f"repos/{repo}/contents/{path}", "--jq", ".[].name"])
        except GhError:
            return []
        return [line for line in out.splitlines() if line.strip()]

    @_hosted
    def read_file(self, repo: str, path: str) -> str:
        """Raw file text (contents API, raw media type). Propagates GhError.

        The `application/vnd.github.raw` Accept header returns the file bytes
        directly, so there's no base64 to decode.
        """
        return _gh._run_gh(
            ["api", f"repos/{repo}/contents/{path}", "-H", "Accept: application/vnd.github.raw"]
        )

    # ---- batch operations (spec 2026-09-25-triage-batches §3.J) ----

    @_hosted
    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        out = _gh._run_gh(["issue", "view", str(number), "--repo", repo, "--json", "comments"])
        raw: dict[str, Any] = json.loads(out) if out else {}
        return [
            {
                # R17 (triage-claims): OWNER, MEMBER, COLLABORATOR, CONTRIBUTOR, NONE, ...
                "association": c.get("authorAssociation") or "",
                "author": (c.get("author") or {}).get("login", ""),
                "body": c.get("body", ""),
                "created_at": c.get("createdAt", ""),
                "id": _comment_id(c.get("url")),
            }
            for c in raw.get("comments") or []
        ]

    @_hosted
    def edit_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        _gh._run_gh(
            [
                "api",
                "-X",
                "PATCH",
                f"repos/{repo}/issues/comments/{comment_id}",
                "-f",
                f"body={body}",
            ]
        )

    @_hosted
    def list_prs_by_head(self, repo: str, branch: str) -> list[dict[str, Any]]:
        return _gh.list_prs_by_head(repo=repo, branch=branch)

    @_hosted
    def pr_body(self, ref: str, *, cwd: Path) -> str:
        return _gh.view_pr_body(ref, cwd=cwd)

    @_hosted
    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        out = _gh._run_gh(
            [
                "pr",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "state,isDraft,headRefOid,headRefName,baseRefName,mergeable,mergeStateStatus,"
                "mergeCommit,title,body",
            ]
        )
        raw: dict[str, Any] = json.loads(out)
        return {
            "state": raw.get("state", ""),
            "draft": bool(raw.get("isDraft", False)),
            "head_oid": raw.get("headRefOid", ""),
            "head_ref": raw.get("headRefName", ""),
            "base_ref": raw.get("baseRefName", ""),
            "mergeable": raw.get("mergeable") or "UNKNOWN",
            "merge_state": raw.get("mergeStateStatus") or "UNKNOWN",
            "merge_commit": (raw.get("mergeCommit") or {}).get("oid", ""),
            "title": raw.get("title", ""),
            "body": raw.get("body", ""),
        }

    def commit_checks(self, repo: str, sha: str) -> list[dict[str, Any]]:
        """Spec 2026-10-07-cloud-triage §I: the same REST routes as the
        `github-rest` backend (`gh api` works on either), on this client's host."""
        from fr.real_ghrestclient import RealGhRestClient

        return RealGhRestClient(host=self._host).commit_checks(repo, sha)

    def required_check_names(self, repo: str, base: str) -> list[str]:
        """Spec §I (p2-r1): the `github-rest` backend's REST routes, on this host."""
        from fr.real_ghrestclient import RealGhRestClient

        return RealGhRestClient(host=self._host).required_check_names(repo, base)

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None:
        """Spec §I (p2-r7): one REST page, no file list, on this host."""
        from fr.real_ghrestclient import RealGhRestClient

        return RealGhRestClient(host=self._host).open_pr_for_head(repo, branch)

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return self._checks(repo, number, required=True)

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return self._checks(repo, number, required=False)

    @_hosted
    def _checks(self, repo: str, number: int, *, required: bool) -> list[dict[str, Any]]:
        args = ["pr", "checks", str(number), "--repo", repo, *(["--required"] if required else [])]
        try:
            out = _gh._run_gh([*args, "--json", "name,bucket,state"])
        except _gh.GhError as exc:
            if exc.returncode == _CHECKS_PENDING_EXIT and exc.stdout.strip():
                out = exc.stdout
            elif any(phrase in str(exc).lower() for phrase in _NO_CHECKS):
                return []
            else:
                raise
        raw: list[dict[str, Any]] = json.loads(out) if out.strip() else []
        return [
            {"name": c.get("name", ""), "bucket": c.get("bucket", ""), "state": c.get("state", "")}
            for c in raw
        ]

    @_hosted
    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        if method not in MERGE_METHODS:
            raise ValueError(f"merge method must be one of {sorted(MERGE_METHODS)}, got {method!r}")
        # Never `--admin`: a protection refusal propagates as GhError, verbatim.
        _gh._run_gh(
            [
                "pr",
                "merge",
                str(number),
                "--repo",
                repo,
                f"--{method}",
                "--match-head-commit",
                head_sha,
            ]
        )

    @_hosted
    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int:
        # Never `--draft`: the driver merges it once green (pages-goal R13).
        made = self.create_pr(repo, head=head, base=base, title=title, body=body, draft=False)
        return int(made["number"])

    @_hosted
    def create_pr(
        self, repo: str, *, head: str, base: str, title: str, body: str, draft: bool
    ) -> dict[str, Any]:
        out = _gh._run_gh(
            ["pr", "create", "--repo", repo, "--head", head, "--base", base,
             "--title", title, "--body", body, *(["--draft"] if draft else [])]
        )  # fmt: skip
        found = _PR_URL.search(out)
        if found is None:
            # a forge write failure (p4-r4): every caller catches FORGE_ERRORS
            raise _gh.GhError(f"`gh pr create` printed no PR URL: {out.strip()!r}", stdout=out)
        url = out[: found.end()].strip().splitlines()[-1].strip()
        return {"number": int(found.group(1)), "url": url}

    @_hosted
    def close_pr(self, repo: str, number: int) -> None:
        _gh._run_gh(["pr", "close", str(number), "--repo", repo])

    @_hosted
    def delete_branch(self, repo: str, branch: str) -> None:
        ref = urllib.parse.quote(branch, safe="/")  # a `#` or `?` is URL syntax (p1-r7)
        _gh._run_gh(["api", "-X", "DELETE", f"repos/{repo}/git/refs/heads/{ref}"])

    def closing_ref(self, repo: str, number: int) -> str:
        return f"Closes {repo}#{number}"

    @_hosted
    def dispatch_workflow(self, repo: str, workflow: str, *, inputs: dict[str, str]) -> None:
        _gh._run_gh(workflow_run_args(repo, workflow, inputs))

    @_hosted
    def repo_merge_methods(self, repo: str) -> dict[str, Any]:
        out = _gh._run_gh(
            [
                "repo",
                "view",
                repo,
                "--json",
                "viewerDefaultMergeMethod,mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed",
            ]
        )
        raw: dict[str, Any] = json.loads(out)
        flags = (
            ("merge", "mergeCommitAllowed"),
            ("squash", "squashMergeAllowed"),
            ("rebase", "rebaseMergeAllowed"),
        )
        default = str(raw.get("viewerDefaultMergeMethod") or "").lower()
        return {
            "default": default if default in MERGE_METHODS else None,
            "allowed": [m for m, key in flags if raw.get(key)],
        }

    # Triage collect's reads: each delegates to `fr.gh`, so the records are
    # byte-identical to what collect read before (spec 2026-10-06 §4.A).

    @_hosted
    def list_repos(self, owner: str, limit: int) -> list[dict[str, Any]]:
        return cast(
            "list[dict[str, Any]]",
            _gh.list_repos(owner=owner, limit=limit, include_archived=True),
        )

    @_hosted
    def list_issues(
        self, repo: str, state: str, limit: int, fields: str | None = None
    ) -> list[dict[str, Any]]:
        if fields is None:
            return cast(
                "list[dict[str, Any]]", _gh.list_issues(repo=repo, state=state, limit=limit)
            )
        return cast(
            "list[dict[str, Any]]",
            _gh.list_issues(repo=repo, state=state, limit=limit, fields=fields),
        )

    @_hosted
    def list_prs(self, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        return cast("list[dict[str, Any]]", _gh.list_prs(repo=repo, state=state, limit=limit))

    @_hosted
    def list_open_prs(self, repo: str, limit: int) -> list[dict[str, Any]]:
        return cast("list[dict[str, Any]]", _gh.list_open_prs(repo=repo, limit=limit))

    @_hosted
    def read_file_at_ref(self, repo: str, path: str, ref: str) -> str:
        return _gh.read_file_at_ref(repo=repo, path=path, ref=ref)

    @_hosted
    def viewer_login(self) -> str:
        return _gh.viewer_login()

    @_hosted
    def view_issue_record(self, repo: str, number: int) -> dict[str, Any]:
        return cast("dict[str, Any]", _gh.view_issue(repo, number))

    @_hosted
    def default_branch(self, *, cwd: Path, run: CommandRunner | None = None) -> str | None:
        result = _gh_runner(run)(
            [
                "gh",
                "repo",
                "view",
                "--json",
                "defaultBranchRef",
                "--jq",
                ".defaultBranchRef.name",
            ],
            cwd=cwd,
        )
        out = (result.stdout or "").strip()
        return out if result.returncode == 0 and out else None

    @_hosted
    def pr_for_branch(
        self, branch: str, *, cwd: Path, run: CommandRunner | None = None
    ) -> dict[str, Any] | None:
        result = _gh_runner(run)(
            ["gh", "pr", "view", branch, "--json", "state,url,mergedAt"],
            cwd=cwd,
        )
        if result.returncode != 0 or not (result.stdout or "").strip():
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    @_hosted
    def issues_enabled(self, repo: str | None = None) -> bool | None:
        if not repo:
            return None
        try:
            raw = json.loads(_gh._run_gh(["repo", "view", repo, "--json", "hasIssuesEnabled"]))
        except (_gh.GhError, ValueError, OSError):
            return None
        value = raw.get("hasIssuesEnabled") if isinstance(raw, dict) else None
        return value if isinstance(value, bool) else None


_CI_PASS = {"SUCCESS"}
_CI_FAIL = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}
_CI_PENDING = {"PENDING", "EXPECTED", "QUEUED", "IN_PROGRESS"}


def _gh_runner(run: CommandRunner | None) -> Callable[..., subprocess.CompletedProcess[str]]:
    """*run* (else `run_cli`), handed the `GH_HOST` overlay — `_gh.host_env()`
    read at call time, so it is the calling method's `@_hosted` scope that
    applies. An injected runner is handed it too: returning *run* bare let the
    gate pass one host while gh talked to the remote's (gh#1015)."""
    runner = run or run_cli
    return lambda argv, *, cwd: runner(argv, cwd=cwd, env=_gh.host_env())


def _coerce_ci_state(rollup: str) -> str:
    """Map GraphQL StatusState → vk's PASS/FAIL/PENDING/NONE."""
    if rollup in _CI_PASS:
        return "PASS"
    if rollup in _CI_FAIL:
        return "FAIL"
    if rollup in _CI_PENDING:
        return "PENDING"
    return "NONE"
