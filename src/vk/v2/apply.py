"""Apply a Diff to GitHub. The only mutation path in v2.

`apply()` is the single point through which any GH-side change flows.
It consumes a `Diff` (produced by `vk.v2.diff.diff`), executes each
mutation through the `GhClient`, and accumulates failures rather than
short-circuiting — so one bad mutation doesn't strand the rest.

Properties enforced here:
  - **Idempotent.** Re-running with the same inputs is a no-op
    because diff() emits no mutations when state is already in sync.
  - **Managed-labels-only.** Operator labels are never touched;
    diff() filters by `MANAGED_LABEL_PREFIXES` and apply() trusts
    that filter.
  - **Dry-run is read-only.** `dry_run=True` returns the result
    without calling any mutation method.
  - **Confirmation is a CLI concern.** This library function executes
    every mutation it receives; the CLI wraps with prompt-before-
    destructive behavior. Don't add a `yes` flag here.
  - **Programmer errors propagate.** A novel `Mutation` subclass
    that we forgot to handle raises `_UnhandledMutationError` (subclass
    of `AssertionError`) and is NOT caught — those should crash the
    test suite rather than masquerade as a GH failure.
"""

from __future__ import annotations

from dataclasses import dataclass

from vk.v2.diff import (
    Diff,
    IssueBodyChange,
    IssueCreate,
    IssueLabelChange,
    IssueStateChange,
    Mutation,
    RepoLabelEnsure,
)
from vk.v2.ghclient import GhClient


class _UnhandledMutationError(AssertionError):
    """Raised when apply() encounters a Mutation subclass it doesn't handle.

    Programmer error. Not caught by the failure-accumulation except clause.
    """


@dataclass(frozen=True)
class ApplyFailure:
    mutation: Mutation
    error: str


@dataclass(frozen=True)
class ApplyResult:
    applied: tuple[Mutation, ...]
    failures: tuple[ApplyFailure, ...]
    created_issues: dict[int, str]  # phase_number -> issue URL
    dry_run: bool


def _execute_one(m: Mutation, gh: GhClient, created: dict[int, str]) -> None:
    """Dispatch a single mutation to the correct GhClient method.

    Side-effects only — appends to `created` for IssueCreate; raises
    `_UnhandledMutationError` if the type isn't handled (programmer error).
    """
    if isinstance(m, RepoLabelEnsure):
        gh.ensure_labels(m.repo, sorted(m.labels))
    elif isinstance(m, IssueCreate):
        url = gh.create_issue(m.repo, title=m.title, body=m.body, labels=m.labels)
        created[m.phase_number] = url
    elif isinstance(m, IssueLabelChange):
        gh.edit_issue_labels(m.repo, m.issue_number, add=m.add, remove=m.remove)
    elif isinstance(m, IssueStateChange):
        gh.edit_issue_state(
            m.repo,
            m.issue_number,
            state=m.new_state,
            reason=m.close_reason,
        )
    elif isinstance(m, IssueBodyChange):
        gh.edit_issue_body(m.repo, m.issue_number, m.new_body)
    else:
        raise _UnhandledMutationError(f"unknown mutation type: {type(m).__name__}")


def apply(d: Diff, gh: GhClient, *, dry_run: bool = False) -> ApplyResult:
    """Execute the diff. On dry_run, return mutations without calling gh."""
    if dry_run:
        return ApplyResult(
            applied=d.mutations,
            failures=(),
            created_issues={},
            dry_run=True,
        )

    applied: list[Mutation] = []
    failures: list[ApplyFailure] = []
    created: dict[int, str] = {}

    for m in d.mutations:
        try:
            _execute_one(m, gh, created)
            applied.append(m)
        except _UnhandledMutationError:
            # Programmer error — don't mask it as a GH failure.
            raise
        except Exception as e:  # noqa: BLE001 — accumulate gh-side failures
            failures.append(ApplyFailure(mutation=m, error=str(e)))

    return ApplyResult(
        applied=tuple(applied),
        failures=tuple(failures),
        created_issues=created,
        dry_run=False,
    )
