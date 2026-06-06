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

import json
from typing import Any

from fr import gh as _gh
from fr.labels import LabelDef


class RealGhClient:
    """Wraps `vk.gh` to satisfy the `GhClient` Protocol."""

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
            # whole `vk apply --dry-run`. Return [] and let downstream
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

    def edit_issue_body(self, repo: str, number: int, body: str) -> None:
        _gh.edit_issue_body(repo=repo, number=number, body=body)

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

    def comment_issue(self, repo: str, number: int, body: str) -> None:
        """Post a comment via `gh issue comment`."""
        _gh._run_gh(["issue", "comment", str(number), "--repo", repo, "--body", body])

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


_CI_PASS = {"SUCCESS"}
_CI_FAIL = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}
_CI_PENDING = {"PENDING", "EXPECTED", "QUEUED", "IN_PROGRESS"}


def _coerce_ci_state(rollup: str) -> str:
    """Map GraphQL StatusState → vk's PASS/FAIL/PENDING/NONE."""
    if rollup in _CI_PASS:
        return "PASS"
    if rollup in _CI_FAIL:
        return "FAIL"
    if rollup in _CI_PENDING:
        return "PENDING"
    return "NONE"
