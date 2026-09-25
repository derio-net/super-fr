"""GhClient Protocol — the single seam between vk and the GitHub world.

The renderer/applier never call `gh` directly. They call methods on a
`GhClient` instance. Production passes a real wrapper; tests pass
`FakeGhClient`. This makes every code path testable without network or
process spawning.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

FORGE_PARITY_ISSUE = "gh#611"
"""Where the missing non-GitHub implementations are tracked (spec
2026-09-25-triage-batches §3.J, decision d6)."""

MERGE_METHODS = frozenset({"merge", "squash", "rebase"})


class UnsupportedForgeOperation(Exception):  # noqa: N818 — the name the spec (§3.J) fixes
    """A `GhClient` method this backend declares it does not implement.

    Raised by the glab/tea adapters one method at a time (spec
    2026-09-25-triage-batches §3.J), so the unsupported cells of the forge
    parity table are readable in the adapters themselves rather than as a
    `backend != "github"` check scattered through callers. Callers turn it
    into exit 2 with its message; it is never a silent no-op.
    """

    def __init__(self, op: str, backend: str, tracked_by: str = FORGE_PARITY_ISSUE) -> None:
        self.op = op
        self.backend = backend
        self.tracked_by = tracked_by
        super().__init__(
            f"`{op}` is not supported on the {backend} backend yet (tracked in {tracked_by})"
        )


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

    # ---- batch operations (spec 2026-09-25-triage-batches §3.J) ----
    # Implemented for GitHub; the glab/tea adapters raise
    # `UnsupportedForgeOperation` for each (gh#611).

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        """Every comment on the issue, oldest first: `{author, body, created_at}`."""
        ...

    def list_prs_by_head(self, repo: str, branch: str) -> list[dict[str, Any]]:
        """Every PR (any state) whose head branch is *branch*, as `gh pr list`
        records with `fr.gh.PR_LIST_FIELDS` plus `headRefOid`."""
        ...

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        """`{state, draft, head_oid, head_ref, mergeable, merge_state}` of one PR,
        read fresh. `state` is OPEN | CLOSED | MERGED."""
        ...

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        """The PR's REQUIRED checks: `{name, bucket, state}`, where `bucket` is
        pass | fail | pending | skipping | cancel. Empty when none are required."""
        ...

    def wait_required_checks(
        self,
        repo: str,
        number: int,
        *,
        interval: float = 30.0,
        timeout: float = 3600.0,
        sleep: Callable[[float], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Poll `pr_required_checks` until none is pending, or *timeout* seconds of
        waiting have passed; return the last answer either way (the caller reads
        the buckets)."""
        ...

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        """Merge the PR only if its head is still *head_sha*; *method* is one of
        `MERGE_METHODS`. Never bypasses branch protection: a refusal raises
        with the forge's own message."""
        ...

    def closing_ref(self, repo: str, number: int) -> str:
        """The PR-body line that closes issue *number* of *repo* on merge."""
        ...


class UnsupportedBatchOps:
    """The §3.J batch operations, each declared unsupported for `backend`.

    Mixed into `RealGlabClient` and `RealTeaClient` (spec
    2026-09-25-triage-batches §3.J): one method per operation, each raising
    `UnsupportedForgeOperation` naming itself, so a backend that gains one
    overrides exactly that method and the rest stay declared. This is the
    surface gh#611's forge parity table reads.
    """

    backend: str = "unknown"

    def _unsupported(self, op: str) -> UnsupportedForgeOperation:
        return UnsupportedForgeOperation(op, self.backend)

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        raise self._unsupported("list_issue_comments")

    def list_prs_by_head(self, repo: str, branch: str) -> list[dict[str, Any]]:
        raise self._unsupported("list_prs_by_head")

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        raise self._unsupported("pr_view")

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        raise self._unsupported("pr_required_checks")

    def wait_required_checks(
        self,
        repo: str,
        number: int,
        *,
        interval: float = 30.0,
        timeout: float = 3600.0,
        sleep: Callable[[float], None] | None = None,
    ) -> list[dict[str, Any]]:
        raise self._unsupported("wait_required_checks")

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        raise self._unsupported("pr_merge")

    def closing_ref(self, repo: str, number: int) -> str:
        raise self._unsupported("closing_ref")
