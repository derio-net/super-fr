"""Production GlabClient — wraps the `glab` CLI for GitLab-backed repos.

Conforms to `fr.ghclient.GhClient` structurally (Python Protocols don't
care about import names — see the design doc §3 for why the Protocol
stays named `GhClient`). Read methods (`view_issue`, `list_linked_prs`)
shape glab's JSON output into the contract that `observe`/`diff` expect.
Write methods delegate to `fr.glab`'s helpers, mirroring
`fr.real_ghclient.RealGhClient`'s structure so the two files diff cleanly.

GitLab-specific shape differences absorbed here (not leaked into shared
code — see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §4):
- Issue state is lowercase `opened`/`closed` (not GitHub's `OPEN`/`CLOSED`).
- Issue `labels` come back as a plain string array, not `[{name: ...}]`.
- `list_linked_prs` uses the REST `related_merge_requests` endpoint via
  `glab api` (no GraphQL query needed here, simpler than GitHub's path) —
  the repo path must be URL-encoded (`group/proj` -> `group%2Fproj`).
- Pipeline status is its own vocabulary (`success`/`failed`/`running`/
  `pending`/`created`/`canceled`/`skipped`), coerced by `_coerce_ci_state`
  — a separate table from `real_ghclient.py`'s GraphQL-enum one.
- Contents lookups (`glab api projects/:id/repository/files/:path`)
  return base64-encoded content, unlike GitHub's raw-media-type trick —
  `read_file` decodes it explicitly.
"""

from __future__ import annotations

import base64
import json
from typing import Any, cast
from urllib.parse import quote

from fr import glab as _glab
from fr.labels import LabelDef


class RealGlabClient:
    """Wraps `fr.glab` to satisfy the `GhClient` Protocol for GitLab repos."""

    def view_issue(self, repo: str, number: int) -> dict[str, Any]:
        raw = cast("dict[str, Any]", _glab.view_issue(repo, number))
        labels_raw = raw.get("labels", []) or []
        labels = [
            lbl["name"] if isinstance(lbl, dict) and "name" in lbl else lbl
            for lbl in labels_raw
        ]
        assignees_raw = raw.get("assignees", []) or []
        assignees = [
            a["username"] for a in assignees_raw if isinstance(a, dict) and "username" in a
        ]
        return {
            "state": "CLOSED" if raw.get("state") == "closed" else "OPEN",
            "labels": labels,
            "assignees": assignees,
            "body": raw.get("description", "") or "",
        }

    def list_linked_prs(self, repo: str, issue_number: int) -> list[dict[str, Any]]:
        """Return MRs related to this Issue, shaped for `observe._to_pr_observation`.

        Uses the REST `related_merge_requests` endpoint (a dedicated
        GitLab API, simpler than GitHub's GraphQL path). Fails soft: an
        unreachable query shouldn't blow up `fr apply --dry-run`.
        """
        encoded_repo = quote(repo, safe="")
        try:
            out = _glab._run_glab(
                ["api", f"projects/{encoded_repo}/issues/{issue_number}/related_merge_requests"]
            )
        except _glab.GlabError:
            return []
        nodes = json.loads(out) if out else []
        result: list[dict[str, Any]] = []
        for n in nodes:
            raw_state = n.get("state", "opened")
            merged = raw_state == "merged"
            state = "CLOSED" if raw_state in ("merged", "closed", "locked") else "OPEN"
            pipeline = n.get("pipeline") or {}
            ci = _coerce_ci_state(pipeline.get("status", ""))
            result.append(
                {
                    "url": n.get("web_url", ""),
                    "state": state,
                    "merged": merged,
                    "draft": bool(n.get("draft", False)),
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
        _glab.swap_issue_labels(
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
            _glab.close_issue(repo=repo, number=number)
            return
        if state == "OPEN":
            _glab.reopen_issue(repo=repo, number=number)
            return
        raise ValueError(f"unknown issue state: {state!r}")

    def edit_issue_body(self, repo: str, number: int, body: str) -> None:
        _glab.edit_issue_body(repo=repo, number=number, body=body)

    def create_issue(
        self,
        repo: str,
        *,
        title: str,
        body: str,
        labels: frozenset[str],
    ) -> str:
        return _glab.create_issue(
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
        _glab.ensure_labels(repo=repo, labels=defs)

    def comment_issue(self, repo: str, number: int, body: str) -> None:
        """Post a comment via `glab issue note` (glab's name for gh's
        `issue comment` — verified directly against `glab issue --help`)."""
        _glab._run_glab(["issue", "note", str(number), "--repo", repo, "--message", body])

    def file_exists(self, repo: str, path: str) -> bool:
        """Contents-API existence probe via `glab api
        projects/:id/repository/files/:path`. Any error reads as
        "not found" — the safe direction (spec-archival callers leave the
        spec in place on an unresolved lookup)."""
        encoded_repo = quote(repo, safe="")
        encoded_path = quote(path, safe="")
        try:
            _glab._run_glab(["api", f"projects/{encoded_repo}/repository/files/{encoded_path}"])
            return True
        except _glab.GlabError:
            return False

    def list_dir(self, repo: str, path: str) -> list[str]:
        """Entry names under `path` via the repository tree endpoint.
        `[]` on any GlabError — same fail-soft posture as `file_exists`."""
        encoded_repo = quote(repo, safe="")
        encoded_path = quote(path, safe="")
        try:
            out = _glab._run_glab(
                ["api", f"projects/{encoded_repo}/repository/tree?path={encoded_path}"]
            )
        except _glab.GlabError:
            return []
        entries = json.loads(out) if out else []
        return [e["name"] for e in entries if isinstance(e, dict) and "name" in e]

    def read_file(self, repo: str, path: str) -> str:
        """Raw file text via the repository files endpoint. GitLab's API
        returns base64-encoded content (unlike GitHub's raw-media-type
        trick) — decoded here."""
        encoded_repo = quote(repo, safe="")
        encoded_path = quote(path, safe="")
        out = _glab._run_glab(["api", f"projects/{encoded_repo}/repository/files/{encoded_path}"])
        data = json.loads(out)
        content = data.get("content", "")
        return base64.b64decode(content).decode("utf-8")


_CI_PASS = {"success"}
_CI_FAIL = {"failed", "canceled"}
_CI_PENDING = {"running", "pending", "created"}


def _coerce_ci_state(status: str) -> str:
    """Map GitLab's pipeline-status vocabulary -> fr's PASS/FAIL/PENDING/NONE.

    A distinct table from `real_ghclient.py`'s GraphQL-enum one — GitLab's
    pipeline states are lowercase and named differently (e.g. `skipped`
    maps to NONE here, not FAIL, since a skipped pipeline signals nothing
    ran rather than a failure)."""
    if status in _CI_PASS:
        return "PASS"
    if status in _CI_FAIL:
        return "FAIL"
    if status in _CI_PENDING:
        return "PENDING"
    return "NONE"
