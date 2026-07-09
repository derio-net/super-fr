"""GhClient Protocol — the single seam between vk and the GitHub world.

The renderer/applier never call `gh` directly. They call methods on a
`GhClient` instance. Production passes a real wrapper; tests pass
`FakeGhClient`. This makes every code path testable without network or
process spawning.
"""

from __future__ import annotations

from typing import Any, Protocol


class GhClient(Protocol):
    def view_issue(self, repo: str, number: int) -> dict[str, Any]:
        """Return Issue state, labels, assignees as a dict."""
        ...

    def list_linked_prs(self, repo: str, issue_number: int) -> list[dict[str, Any]]:
        """Return PRs linked to the issue (via closingIssuesReferences or title pattern).

        Each dict has at minimum: `url`, `state` ("OPEN"|"CLOSED"), `merged` (bool),
        `draft` (bool), `ci` ("PASS"|"FAIL"|"PENDING"|"NONE"). The wrapper is
        responsible for shaping gh's GraphQL response into this contract.
        """
        ...

    def pr_status_by_url(self, url: str) -> dict[str, Any] | None:
        """Resolve a single PR/MR's merge/draft state from its own URL.

        Returns `{"state": "OPEN"|"CLOSED"|"MERGED", "draft": bool}`, or
        `None` on any not-found/error condition (fail soft — the caller,
        fr-vk's PR-merge poller, treats an unresolvable PR as "hold this
        card", not an error). Distinct from `list_linked_prs`: this method
        takes a PR URL directly rather than deriving PRs from an Issue, and
        its `state` vocabulary includes `MERGED` as a third value (not
        collapsed into `CLOSED`) since the caller branches on it
        separately. See docs/superpowers/specs/
        2026-07-09-multi-backend-git-host-adapters-design.md §6 — added
        specifically to let fr-vk's `pr_observe.py` stop shelling out to a
        literal `gh pr view` subprocess.
        """
        ...

    def edit_issue_labels(
        self,
        repo: str,
        number: int,
        *,
        add: frozenset[str],
        remove: frozenset[str],
    ) -> None: ...

    def edit_issue_state(
        self,
        repo: str,
        number: int,
        *,
        state: str,
        reason: str | None = None,
    ) -> None: ...

    def edit_issue_body(self, repo: str, number: int, body: str) -> None: ...

    def comment_issue(self, repo: str, number: int, body: str) -> None:
        """Post a comment on an Issue (`fr undispatch` leaves its trail here)."""
        ...

    def create_issue(
        self,
        repo: str,
        *,
        title: str,
        body: str,
        labels: frozenset[str],
    ) -> str:
        """Return URL of the created Issue."""
        ...

    def ensure_labels(self, repo: str, labels: list[Any]) -> None:
        """Create or update label definitions on the repo. Idempotent.

        `labels` may be a list of strings (label names) or LabelDef-shaped
        objects with `.name`/`.color`/`.description`. The wrapper coerces.
        """
        ...

    def file_exists(self, repo: str, path: str) -> bool:
        """True iff `path` exists on `repo`'s default branch (contents API).

        Read-only. Used by the spec-archival decision (`fr archive` /
        `fr migrate dirs`) to resolve cross-repo plan rows — the
        2026-06-05 spec's narrow gh-contents lookup.
        """
        ...

    def list_dir(self, repo: str, path: str) -> list[str]:
        """Names of the entries directly under `path` on `repo`'s default
        branch (contents API). Empty list when `path` is absent or not a
        directory. Read-only. Used by `fr spec status` to enumerate a
        cross-repo plan folder's `NN.yaml` files (#339).
        """
        ...

    def read_file(self, repo: str, path: str) -> str:
        """Raw text of `path` on `repo`'s default branch (contents API).

        Raises on absence / non-file (caller degrades the row). Read-only.
        Used by `fr spec status` to read a cross-repo plan's phase files (#339).
        """
        ...
