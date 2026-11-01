"""GhClient Protocol — the single seam between vk and the GitHub world.

The renderer/applier never call `gh` directly. They call methods on a
`GhClient` instance. Production passes a real wrapper; tests pass
`FakeGhClient`. This makes every code path testable without network or
process spawning.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

FORGE_PARITY_ISSUE = "gh#611"
"""Where the missing non-GitHub implementations are tracked (spec
2026-09-25-triage-batches §3.J, decision d6)."""

MERGE_METHODS = frozenset({"merge", "squash", "rebase"})


@dataclass(frozen=True)
class BaseRules:
    """What a base branch's rules require of a merge (2026-10-11-merge-train-safety §D,
    R12): *merge_queue* when a merge queue is required, *strict_checks* when a
    required status check must pass on a head that is up to date with the base."""

    merge_queue: bool = False
    strict_checks: bool = False


@dataclass(frozen=True)
class QueueState:
    """Where a PR stands with the base's merge queue (merge-train-safety §D, R13):
    *in_queue* None when the backend cannot say (REST), *auto_merge* whether auto-merge
    is set (from enqueue until GitHub merges the PR or clears it on ejection)."""

    in_queue: bool | None = None
    auto_merge: bool = False
    # False once the PR is merged or closed: such a PR never left a queue unmerged.
    open: bool = True


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


class ListingCapped(Exception):  # noqa: N818 — a signal carrying the partial answer, not a fault
    """A bulk issue listing hit its cap: `.issues` is what the scan found, and
    "nothing found" must not be read from it (no silent caps)."""

    def __init__(self, issues: list[dict[str, Any]], limit: int) -> None:
        super().__init__(f"listing capped at {limit} issues; the answer is partial")
        self.issues = issues
        self.limit = limit


def filter_issues_by_body(
    raw: list[dict[str, Any]], search: tuple[str, ...], limit: int
) -> list[dict[str, Any]]:
    """The scanned issues whose body holds any of *search*, oldest first.

    Raises `ListingCapped` (carrying the matches) when the scan hit *limit*:
    an issue past the cap is unseen, so the caller must not read "none found".
    """

    def digits(i: dict[str, Any]) -> bool:
        n = str(i.get("number", ""))
        return n.isascii() and n.isdigit()

    # A forge-returned number that is not plain digits is skipped, never `int()`ed.
    hits = [i for i in raw if digits(i) and any(s in (i.get("body") or "") for s in search)]
    hits.sort(key=lambda i: int(i["number"]))
    if len(raw) >= limit:
        raise ListingCapped(hits, limit)
    return hits


class HostRefusedError(Exception):
    """A forge adapter's host trust gate refused to point its CLI at a host
    the CLI is not logged into (spec 2026-10-06-forge-remainder §4.E; gh#1014).
    Each backend's refusal (`GhHostRefusedError`, `GlabHostRefusedError`) also
    subclasses that backend's own error, so existing `except` clauses still
    see it. Classify a refusal by THIS type, never by its message: the message
    names the host, and a host can be called anything (gh#1013)."""


class CommandRunner(Protocol):
    """How an adapter's lookup runs one CLI command (spec
    2026-10-06-forge-remainder §4.B). The isolation lifecycle injects its own
    `Runner`, so its network env and timeout apply; `None` means the adapter's
    default, `run_cli`.

    `env` is the adapter's overlay: the variables that point the CLI at its
    host (`GH_HOST`, `GITLAB_HOST`), to set ON TOP of whatever environment the
    runner would use anyway — None when there is nothing to add. A runner that
    drops it talks to whatever host the checkout's remote names, not the one
    the trust gate passed (gh#1015)."""

    def __call__(
        self, argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]: ...


# The exit a shell gives a command it cannot find: what `run_cli` answers for a
# missing binary, so a lookup reads it like any other failed call.
_NOT_FOUND_EXIT = 127


def run_cli(
    argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """The adapters' default `CommandRunner`. Never raises for a missing
    binary: it comes back as exit 127, which every lookup reads as `None`.
    `env` is the overlay (see `CommandRunner`); none passes `env=None`, so the
    child inherits this process's environment unchanged."""
    full = {**os.environ, **env} if env else None
    try:
        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=full)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(argv, _NOT_FOUND_EXIT, stdout="", stderr=str(exc))


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

    def pr_body(self, ref: str, *, cwd: Path) -> str:
        """The live body (GitLab: description) of one PR/MR, read fresh.

        `ref` is the PR's URL, number or head branch; a number or branch is
        resolved against the repository checked out at `cwd`. Raises the
        backend's own CLI error (`fr.hostclient.FORGE_ERRORS`) when the PR
        cannot be read. Implemented on every backend: `deliver`'s live-PR
        check (spec 2026-09-25 §5.C.4) reads through here, so a backend that
        lacked it could never deliver a run (gh#742).
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

    def edit_pr_labels(
        self, repo: str, pr: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        """Add and remove labels on a PR (exit-gates R7). On GitHub a PR is an
        issue, so this is the issue endpoint for the PR's number; a forge that
        cannot label a PR raises `UnsupportedForgeOperation`."""
        ...

    def comment_pr(self, repo: str, pr: int, body: str) -> None:
        """Comment on a PR (exit-gates §B); same forge rules as `edit_pr_labels`."""
        ...

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

    def edit_issue(self, repo: str, number: int, *, title: str, body: str) -> None:
        """Replace an Issue's title and body in one call (`fr debt issue`, R26)."""
        ...

    def list_open_issues_with_body(
        self, repo: str, *, search: tuple[str, ...], limit: int
    ) -> list[dict[str, Any]]:
        """Open issues whose body contains any of the *search* substrings, as
        `{number, title, body, labels}` oldest first. At most *limit* issues are
        scanned: a caller that gets back `limit` scanned issues must treat the
        answer as partial (the scan count is `len(raw)` before filtering, so
        implementations return the filtered list and raise `ListingCapped`
        carrying it when the cap was hit)."""
        ...

    def close_issue(self, repo: str, number: int, comment: str) -> None:
        """Comment on an Issue, then close it (`fr debt issue` at zero debt, R26)."""
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
        """Every comment on the issue, oldest first: `{author, body, created_at, id}`.

        `id` is the comment's numeric id (None when the forge gave none), the handle
        `edit_issue_comment` takes (spec 2026-10-06-triage-claims §3.C)."""
        ...

    def edit_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        """Replace the body of comment *comment_id* on *repo* (a triage claim's
        heartbeat and release edit their marker in place, never repost it)."""
        ...

    def list_prs_by_head(self, repo: str, branch: str) -> list[dict[str, Any]]:
        """Every PR (any state) whose head branch is *branch*, as `gh pr list`
        records with `fr.gh.PR_LIST_FIELDS` plus `headRefOid` and `files`."""
        ...

    def prs_for_commit(self, repo: str, sha: str) -> list[dict[str, Any]]:
        """The PRs that contain commit *sha* (`GET repos/{repo}/commits/{sha}/pulls`), as
        `{number, state, url, merged}` records; glab and tea raise `UnsupportedForgeOperation`
        (`fr gate backfill` maps a squash commit to its PR with it)."""
        ...

    def ref_kind(self, repo: str, number: int) -> Literal["issue", "pr"] | None:
        """Whether *repo*'s `#number` is an issue or a PR (`adopt --list` classifies the
        refs in a session label); None when the forge says neither."""
        ...

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        """`{state, draft, head_oid, head_ref, base_ref, mergeable, merge_state, merge_commit,
        title, body, labels}` of one PR, read fresh. `state` is OPEN | CLOSED | MERGED;
        `merge_commit` is the commit the merge made on the base ("" while unmerged); `labels`
        the label names (the merge paths read `approved-fr` here, live — 2026-10-11-merge-
        train-safety §A)."""
        ...

    def pr_ready(self, repo: str, number: int) -> None:
        """Mark draft PR *number* ready for review: the approval gate's one write before
        it lands an approved green draft (merge-train-safety §A "Merging", R3)."""
        ...

    def label_exists(self, repo: str, name: str) -> bool:
        """Whether *repo* defines label *name* (merge-train-safety §A "Label creation",
        R4). A missing label is False; any other failure raises."""
        ...

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        """The PR's REQUIRED checks: `{name, bucket, state}`, where `bucket` is
        pass | fail | pending | skipping | cancel. Empty when none are required, or
        when the head has no check yet: R4 (`batch_drive.checks_verdict`) tells
        those apart by reading `pr_checks`."""
        ...

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        """Every check on the PR's head, required or not, in the shape of
        `pr_required_checks`. Empty when none is reported (yet)."""
        ...

    def commit_checks(self, repo: str, sha: str) -> list[dict[str, Any]]:
        """Every check on commit *sha*: `{name, workflow, status, conclusion, url,
        base_sha}` — check runs (latest per workflow and name, so a failed attempt
        re-run green is one green record) and commit statuses (latest per
        context; `workflow` ""). `status` is `completed` once finished;
        `conclusion` GitHub's word (`success`, `failure`, `skipped`, ...), "" while
        unfinished; `base_sha` the PR base GitHub reports for the run ("" when
        none). Spec 2026-10-07-cloud-triage §I: CI as test evidence. Empty when
        nothing is reported (yet)."""
        ...

    def required_check_names(self, repo: str, base: str) -> list[str]:
        """The check NAMES branch *base* requires (classic protection's summary
        plus rulesets), sorted, whether or not any has reported on a commit: a
        required check not created yet is still named. Empty when none is
        required. Spec 2026-10-07-cloud-triage §I, gate checks (p2-r1)."""
        ...

    def base_rules(self, repo: str, branch: str) -> BaseRules:
        """The rules on *branch* (merge-train-safety §D, R12): a `merge_queue` rule, and a
        strict required-status-checks rule (rulesets, and classic protection's `strict`).
        A forge without the concepts has neither."""
        ...

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None:
        """`{number, url}` of the open PR whose head is *branch*, None when there
        is none. Reads no file list (§I step 6, p2-r7): `pr_view` gives the rest."""
        ...

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        """Merge the PR only if its head is still *head_sha*; *method* is one of
        `MERGE_METHODS`. Never bypasses branch protection: a refusal raises
        with the forge's own message."""
        ...

    def pr_enqueue(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        """Put the PR into the base's merge queue (auto-merge) only if its head is still
        *head_sha* (merge-train-safety §D, R13). A backend that cannot raises."""
        ...

    def pr_queue_state(self, repo: str, number: int) -> QueueState:
        """The PR's `QueueState` (§D): `in_queue` None where the backend cannot say."""
        ...

    def pr_dequeue(self, repo: str, number: int) -> None:
        """Take the PR out of the merge queue / clear its auto-merge (§D, R13: an approval
        removed after the enqueue is honoured). A backend that cannot raises."""
        ...

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int:
        """Open a ready (never draft) PR from *head* into *base*; its number. The
        driver's per-wave state export (pages-goal R13). A refusal raises with the
        forge's own message."""
        ...

    def create_pr(
        self, repo: str, *, head: str, base: str, title: str, body: str, draft: bool
    ) -> dict[str, Any]:
        """Open a PR from *head* into *base*, a draft when *draft*: `{number, url}`.
        Batch adopt's supersede (spec 2026-10-06-triage-batch-adopt §C). A refusal
        raises with the forge's own message."""
        ...

    def close_pr(self, repo: str, number: int) -> None:
        """Close PR *number* unmerged (batch adopt's supersede, §C)."""
        ...

    def open_pr_in_repo(self, repo: str, branch: str) -> dict[str, Any] | None:
        """`{number, url}` of the open PR whose head *branch* is in THIS repo (a
        fork's PR on the same name is skipped), None when there is none."""
        ...

    def authenticated_login(self) -> str:
        """The account the forge credentials act as (`fr debt issue` trusts only
        issues this account or the workflow bot wrote)."""
        ...

    def edit_pr(self, repo: str, number: int, *, body: str) -> None:
        """Replace PR *number*'s description (`fr debt archive-pr` refreshes its
        one draft PR, R12)."""
        ...

    def delete_branch(self, repo: str, branch: str) -> None:
        """Delete *branch* on the forge (batch adopt's old head, §C)."""
        ...

    def closing_ref(self, repo: str, number: int) -> str:
        """The PR-body line that closes issue *number* of *repo* on merge."""
        ...

    def repo_merge_methods(self, repo: str) -> dict[str, Any]:
        """`{default, allowed}`: the viewer's default merge method for *repo*
        (one of `MERGE_METHODS`, or None) and the methods the repo allows."""
        ...

    def dispatch_workflow(self, repo: str, workflow: str, *, inputs: dict[str, str]) -> None:
        """Trigger a `workflow_dispatch` workflow of *repo* (by file name) with
        *inputs*, on the repo's default branch. Fire and forget: the forge
        answers once the dispatch is accepted, not when the run finishes. A
        refusal raises with the forge's own message. Implemented for GitHub
        only (`fr verification prerelease`, spec 2026-10-06-verification-strategies §H)."""
        ...

    # ---- triage collect's reads (spec 2026-10-06-forge-remainder §4.A) ----
    # Implemented for GitHub with `fr.gh`'s records unchanged; the glab/tea
    # adapters raise `UnsupportedForgeOperation` for each (triage is
    # GitHub-only by its own scope).

    def list_repos(self, owner: str, limit: int) -> list[dict[str, Any]]:
        """Every repo of *owner*, archived ones included (`{name, isArchived}`),
        so the caller can count the raw list against *limit*."""
        ...

    def list_issues(
        self,
        repo: str,
        state: str,
        limit: int,
        fields: str | None = None,
        labels: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """One bulk issue list; *fields* None means the forge's default set, *labels*
        keeps only issues carrying all of them."""
        ...

    def list_prs(self, repo: str, state: str, limit: int) -> list[dict[str, Any]]: ...

    def list_open_prs(self, repo: str, limit: int) -> list[dict[str, Any]]: ...

    def read_file_at_ref(self, repo: str, path: str, ref: str) -> str:
        """Raw text of *path* at *ref*; raises the backend's error when absent."""
        ...

    def latest_release(self, repo: str) -> str | None:
        """The tag of *repo*'s latest published release (`GET repos/{repo}/releases/latest`),
        None when it has none (spec 2026-10-07-cloud-triage R17, R18: the fr version every
        session should run). Raises the backend's error on any other failure."""
        ...

    def viewer_login(self) -> str:
        """The login the forge CLI is authenticated as."""
        ...

    def rate_limit(self) -> dict[str, Any]:
        """The host's rate budgets (`GET /rate_limit`, which costs nothing): the raw
        `{"resources": {"core": {limit, remaining, reset}, "graphql": …}}` answer
        (spec 2026-10-12-quota-pacing R1)."""
        ...

    def probe(self, path: str, etag: str | None) -> tuple[bool, str | None]:
        """A conditional REST read of *path* sent with *etag*: `(changed, etag)`, where a
        304 is `(False, etag)`, a 200 `(True, its ETag)` and anything else, a failure
        included, `(True, None)` (spec 2026-10-12-quota-pacing R8). Never raises."""
        ...

    def view_issue_record(self, repo: str, number: int) -> dict[str, Any]:
        """The RAW issue record (on GitHub, `gh issue view --json
        ISSUE_VIEW_FIELDS`: title, url, label objects…) — distinct from the
        projected `view_issue` that observe, apply and the bridge rely on."""
        ...

    def default_branch(self, *, cwd: Path, run: CommandRunner | None = None) -> str | None:
        """The default branch of the repository checked out at *cwd*, as the
        forge reports it; None when the CLI fails, is missing or prints
        nothing usable. Never raises for a CLI failure (spec
        2026-10-06-forge-remainder R2)."""
        ...

    def pr_for_branch(
        self, branch: str, *, cwd: Path, run: CommandRunner | None = None
    ) -> dict[str, Any] | None:
        """The PR/MR whose head is *branch* in the repository at *cwd*:
        `{"state": "OPEN"|"MERGED"|"CLOSED", "url": str, "mergedAt": str|None,
        "updatedAt": str|None}`, each forge's own state vocabulary coerced to that
        one. None when there is none, or the CLI fails, is missing or prints something
        unparseable."""
        ...

    def issues_enabled(self, repo: str | None = None) -> bool | None:
        """Whether the forge has issues switched on for *repo* (`owner/repo`):
        True / False as the forge answers, None when it cannot say (no repo, a
        failed call, an unexpected shape, or a backend that cannot ask). Never
        raises — `fr init scaffold --tracking auto` reads None as
        inconclusive and refuses, naming the flag."""
        ...

    def repo_visibility(self, repo: str) -> str:
        """*repo*'s visibility as the forge reports it, lowercased: `public`, `private`
        or `internal` (spec 2026-10-07-cloud-triage §B, §C). Raises the backend's error
        when it cannot be read: the privacy guard refuses on an unreadable answer."""
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

    def edit_pr_labels(
        self, repo: str, pr: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        raise self._unsupported("edit_pr_labels")

    def comment_pr(self, repo: str, pr: int, body: str) -> None:
        raise self._unsupported("comment_pr")

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        raise self._unsupported("list_issue_comments")

    def edit_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        raise self._unsupported("edit_issue_comment")

    def list_prs_by_head(self, repo: str, branch: str) -> list[dict[str, Any]]:
        raise self._unsupported("list_prs_by_head")

    def prs_for_commit(self, repo: str, sha: str) -> list[dict[str, Any]]:
        raise self._unsupported("prs_for_commit")

    def ref_kind(self, repo: str, number: int) -> Literal["issue", "pr"] | None:
        raise self._unsupported("ref_kind")

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        raise self._unsupported("pr_view")

    def pr_ready(self, repo: str, number: int) -> None:
        raise self._unsupported("pr_ready")

    def label_exists(self, repo: str, name: str) -> bool:
        raise self._unsupported("label_exists")

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        raise self._unsupported("pr_required_checks")

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        raise self._unsupported("pr_checks")

    def commit_checks(self, repo: str, sha: str) -> list[dict[str, Any]]:
        raise self._unsupported("commit_checks")

    def required_check_names(self, repo: str, base: str) -> list[str]:
        raise self._unsupported("required_check_names")

    def pr_enqueue(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        raise self._unsupported("pr_enqueue")

    def pr_queue_state(self, repo: str, number: int) -> QueueState:
        return QueueState(None, False)  # no queue concept: not an error (§D)

    def pr_dequeue(self, repo: str, number: int) -> None:
        raise self._unsupported("pr_dequeue")

    def base_rules(self, repo: str, branch: str) -> BaseRules:
        return BaseRules()  # a forge without the concepts has neither: not an error (R12)

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None:
        raise self._unsupported("open_pr_for_head")

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        raise self._unsupported("pr_merge")

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int:
        raise self._unsupported("pr_create")

    def create_pr(
        self, repo: str, *, head: str, base: str, title: str, body: str, draft: bool
    ) -> dict[str, Any]:
        raise self._unsupported("create_pr")

    def close_pr(self, repo: str, number: int) -> None:
        raise self._unsupported("close_pr")

    def edit_pr(self, repo: str, number: int, *, body: str) -> None:
        raise self._unsupported("edit_pr")

    def open_pr_in_repo(self, repo: str, branch: str) -> dict[str, Any] | None:
        raise self._unsupported("open_pr_in_repo")

    def authenticated_login(self) -> str:
        raise self._unsupported("authenticated_login")

    def delete_branch(self, repo: str, branch: str) -> None:
        raise self._unsupported("delete_branch")

    def closing_ref(self, repo: str, number: int) -> str:
        raise self._unsupported("closing_ref")

    def repo_merge_methods(self, repo: str) -> dict[str, Any]:
        raise self._unsupported("repo_merge_methods")

    def dispatch_workflow(self, repo: str, workflow: str, *, inputs: dict[str, str]) -> None:
        raise self._unsupported("dispatch_workflow")

    # Triage collect's reads (spec 2026-10-06-forge-remainder §4.A).

    def list_repos(self, owner: str, limit: int) -> list[dict[str, Any]]:
        raise self._unsupported("list_repos")

    def list_issues(
        self,
        repo: str,
        state: str,
        limit: int,
        fields: str | None = None,
        labels: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        raise self._unsupported("list_issues")

    def list_prs(self, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        raise self._unsupported("list_prs")

    def list_open_prs(self, repo: str, limit: int) -> list[dict[str, Any]]:
        raise self._unsupported("list_open_prs")

    def read_file_at_ref(self, repo: str, path: str, ref: str) -> str:
        raise self._unsupported("read_file_at_ref")

    def latest_release(self, repo: str) -> str | None:
        raise self._unsupported("latest_release")

    def viewer_login(self) -> str:
        raise self._unsupported("viewer_login")

    def rate_limit(self) -> dict[str, Any]:
        raise self._unsupported("rate_limit")

    def probe(self, path: str, etag: str | None) -> tuple[bool, str | None]:
        raise self._unsupported("probe")

    def view_issue_record(self, repo: str, number: int) -> dict[str, Any]:
        raise self._unsupported("view_issue_record")

    def repo_visibility(self, repo: str) -> str:
        raise self._unsupported("repo_visibility")
