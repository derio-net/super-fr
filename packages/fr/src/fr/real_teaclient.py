"""Production TeaClient — wraps the `tea` CLI for Gitea-backed repos.

Conforms to `fr.ghclient.GhClient` structurally. Read methods shape tea's
JSON output into the contract that `observe`/`diff` expect. Write methods
delegate to `fr.tea`'s helpers, mirroring `fr.real_ghclient.RealGhClient`'s
structure.

Gitea-specific shape notes (verified against Gitea's live swagger spec —
see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §5):
- Issue state is lowercase `open`/`closed`.
- Issue `labels`/`assignees` ARE full objects (like GitHub's `[{name:...}]`
  / `[{login:...}]`), NOT plain strings (unlike GitLab's).
- `list_linked_prs` has no dedicated "related PRs" endpoint. Implemented
  via the issue's timeline (`tea api '/repos/{o}/{r}/issues/{n}/timeline'`),
  keeping only events whose `ref_issue` is populated AND
  `ref_issue.pull_request` is non-null (Gitea's Issue.pull_request, a
  PullRequestMeta, is only present when the referenced Issue is actually a
  PR). Deduplicated by URL since one PR can generate multiple timeline
  events. CI/Actions status is NOT attempted — every entry reports
  `ci: "NONE"`, a deliberate scope limit (see the spec).
- Contents lookups mirror GitHub's shape closely (base64-encoded content
  + `encoding` field, same as GitHub's Contents API, NOT GitLab's
  differently-shaped endpoint).
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any, cast

from fr import tea as _tea
from fr.labels import LabelDef

# Gitea-specific PR URL shape (https://{host}/{owner}/{repo}/pulls/{n}).
# Gitea has no GitLab-style arbitrary subgroup nesting, so a plain
# two-segment repo capture is sufficient — deliberately not shared with
# fr._urls (issue-URL-only) or fr.real_glabclient's MR-URL pattern (which
# needs the lazy-quantifier trick GitLab's nesting requires).
_PR_URL_RE = re.compile(r"^https://[^/]+/([^/]+/[^/]+)/pulls/(\d+)/?$")


class RealTeaClient:
    """Wraps `fr.tea` to satisfy the `GhClient` Protocol for Gitea repos."""

    def view_issue(self, repo: str, number: int) -> dict[str, Any]:
        raw = cast("dict[str, Any]", _tea.view_issue(repo, number))
        labels_raw = raw.get("labels", []) or []
        labels = [
            lbl["name"] if isinstance(lbl, dict) and "name" in lbl else lbl for lbl in labels_raw
        ]
        assignees_raw = raw.get("assignees", []) or []
        assignees = [a["login"] for a in assignees_raw if isinstance(a, dict) and "login" in a]
        return {
            "state": "CLOSED" if raw.get("state") == "closed" else "OPEN",
            "labels": labels,
            "assignees": assignees,
            "body": raw.get("body", "") or "",
        }

    def list_linked_prs(self, repo: str, issue_number: int) -> list[dict[str, Any]]:
        """PRs referencing this Issue, derived from its timeline (no
        dedicated endpoint exists — see module docstring). Fails soft."""
        owner_name = repo
        try:
            out = _tea._run_tea(["api", f"/repos/{owner_name}/issues/{issue_number}/timeline"])
        except _tea.TeaError:
            return []
        events = json.loads(out) if out else []
        seen_urls: set[str] = set()
        result: list[dict[str, Any]] = []
        for event in events:
            ref_issue = event.get("ref_issue")
            if not isinstance(ref_issue, dict):
                continue
            pr_meta = ref_issue.get("pull_request")
            if not isinstance(pr_meta, dict):
                continue  # a referencing Issue, not a PR — excluded
            url = ref_issue.get("html_url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            merged = bool(pr_meta.get("merged", False))
            raw_state = ref_issue.get("state", "open")
            state = "CLOSED" if merged or raw_state == "closed" else "OPEN"
            result.append(
                {
                    "url": url,
                    "state": state,
                    "merged": merged,
                    "draft": bool(pr_meta.get("draft", False)),
                    "ci": "NONE",  # deliberate scope limit — see module docstring
                }
            )
        return result

    def pr_status_by_url(self, url: str) -> dict[str, Any] | None:
        """tea's `pulls` command doesn't accept a bare URL either (same
        reasoning as GitLab's `mr view`) — parse (repo, index) from the
        URL, then query by index. Fails soft: None on any error or
        unparseable URL."""
        m = _PR_URL_RE.match(url)
        if not m:
            return None
        repo, index = m.group(1), m.group(2)
        try:
            out = _tea._run_tea(["pulls", index, "--repo", repo, "--output", "json"])
        except _tea.TeaError:
            return None
        raw = json.loads(out)
        merged = bool(raw.get("merged", False))
        state = "MERGED" if merged else ("CLOSED" if raw.get("state") == "closed" else "OPEN")
        return {"state": state, "draft": bool(raw.get("draft", False))}

    def edit_issue_labels(
        self,
        repo: str,
        number: int,
        *,
        add: frozenset[str],
        remove: frozenset[str],
    ) -> None:
        _tea.swap_issue_labels(
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
            _tea.close_issue(repo=repo, number=number)
            return
        if state == "OPEN":
            _tea.reopen_issue(repo=repo, number=number)
            return
        raise ValueError(f"unknown issue state: {state!r}")

    def edit_issue_body(self, repo: str, number: int, body: str) -> None:
        _tea.edit_issue_body(repo=repo, number=number, body=body)

    def create_issue(
        self,
        repo: str,
        *,
        title: str,
        body: str,
        labels: frozenset[str],
    ) -> str:
        return _tea.create_issue(
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
                defs.append(LabelDef(name=lbl, color="ededed", description=""))
            else:
                name = getattr(lbl, "name", None) or lbl["name"]
                color = getattr(lbl, "color", None) or lbl.get("color", "ededed")
                description = getattr(lbl, "description", None) or lbl.get("description", "")
                defs.append(LabelDef(name=name, color=color, description=description))
        _tea.ensure_labels(repo=repo, labels=defs)

    def comment_issue(self, repo: str, number: int, body: str) -> None:
        """Post a comment via `tea comments add <n> <body> --repo <repo>`."""
        _tea._run_tea(["comments", "add", str(number), body, "--repo", repo])

    def file_exists(self, repo: str, path: str) -> bool:
        """Contents-API existence probe. Any error reads as "not found"
        — the safe direction (same posture as the GitHub/GitLab adapters)."""
        try:
            _tea._run_tea(["api", f"/repos/{repo}/contents/{path}"])
            return True
        except _tea.TeaError:
            return False

    def list_dir(self, repo: str, path: str) -> list[str]:
        """Entry names under `path`. `[]` on any TeaError."""
        try:
            out = _tea._run_tea(["api", f"/repos/{repo}/contents/{path}"])
        except _tea.TeaError:
            return []
        entries = json.loads(out) if out else []
        if not isinstance(entries, list):
            return []
        return [e["name"] for e in entries if isinstance(e, dict) and "name" in e]

    def read_file(self, repo: str, path: str) -> str:
        """Raw file text. Gitea's Contents API mirrors GitHub's shape
        closely (base64-encoded `content` + `encoding` field)."""
        out = _tea._run_tea(["api", f"/repos/{repo}/contents/{path}"])
        data = json.loads(out)
        content = data.get("content", "")
        return base64.b64decode(content).decode("utf-8")
