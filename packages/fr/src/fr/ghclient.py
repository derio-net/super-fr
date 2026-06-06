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
