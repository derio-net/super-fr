"""Issue-intake trust: which issues may be batched (spec 2026-11-17-triage-intake R2, R6).

On a public repo anyone can open an issue, and issue text reaches the implementing session's
launch brief. An issue is therefore ELIGIBLE only when at least one clause admits it:

- its author is one of `claim_trusted(config, viewer)` (case-insensitive);
- its author association is in `TRUSTED_ASSOCIATIONS` (OWNER, MEMBER, COLLABORATOR);
- it carries the operator's `ready-fr` label (`fr.labels.READY_FR`, compared
  case-insensitively, as the forge does) TOGETHER with a trusted admit marker whose digest
  equals the issue's current content digest (2026-11-22-triage-hardening R4,
  `fr.triage.admit`): `fr triage admit` writes both, and an edit after it voids the
  admission;
- its author is the debt workflow's bot (`BOT_LOGINS`) AND its body carries the debt-digest
  marker (`fr.triage.debt.has_marker`), the digest `check` already trusts. Any other
  bot-authored issue is judged like anyone's.

The rule FAILS CLOSED: an unread author, an unread association or an unread comment list
never admits an issue.
Everything here is pure; nothing reads the forge. There is no second trust list: the
associations are `fr.triage.claims.TRUSTED_ASSOCIATIONS` and the logins `claim_trusted`.
`rejected_members` is the ONE member rule that batch `create`, `edit`, `dispatch` and both
snapshot builders (the driver's and the board's) call (R6).
"""

from __future__ import annotations

from collections.abc import Iterable

from fr.debt.render import BOT_LOGINS
from fr.labels import READY_FR
from fr.triage.claims import TRUSTED_ASSOCIATIONS
from fr.triage.debt import has_marker
from fr.triage.model import Batch, Facts, Issue, TriageConfig, claim_trusted

NOT_COLLECTED = "not collected"
# What collect records in `Issue.admit_unread` when the adapter cannot list issue comments
# at all (glab, tea): the reason then says so rather than asking for another collect.
ADMIT_UNSUPPORTED = "this forge cannot list comments"


def intake_trusted(config: TriageConfig, viewer: str | None) -> frozenset[str]:
    """The logins intake admits, lowercased: exactly `claim_trusted(config, viewer)`. The
    debt workflow's bot is NOT here: it is admitted by `intake_reason` only with a digest."""
    return claim_trusted(config, viewer)


def _labelled(labels: Iterable[str]) -> bool:
    return READY_FR.name.lower() in {label.lower() for label in labels}


def _admitted_otherwise(
    author: str | None,
    association: str | None,
    trusted: frozenset[str],
    body: str,
) -> bool:
    """Whether a clause other than the `ready-fr` one admits the issue."""
    if author and author.lower() in trusted:
        return True
    if association is not None and association.upper() in TRUSTED_ASSOCIATIONS:
        return True
    return bool(author and author.lower() in BOT_LOGINS and has_marker(body))


def needs_admit_read(
    author: str | None,
    association: str | None,
    labels: Iterable[str],
    trusted: frozenset[str],
    body: str = "",
) -> bool:
    """Whether collect must read the issue's comments for an admit marker (R5): it carries
    `ready-fr` and no other clause admits it. Judged after the association is known."""
    return _labelled(labels) and not _admitted_otherwise(author, association, trusted, body)


def _admit_reason(key: str, admit_read: bool, admit_digest: str | None, unread: str | None) -> str:
    """Why a `ready-fr` issue is not admitted (2026-11-22-triage-hardening §B)."""
    if not admit_read and unread == ADMIT_UNSUPPORTED:
        return (
            f"labelled {READY_FR.name}, but {ADMIT_UNSUPPORTED}, so an admit marker cannot be read"
        )
    if not admit_read:
        return f"labelled {READY_FR.name}, comments not read: run fr triage collect again"
    if admit_digest is None:
        return f"labelled {READY_FR.name} without a trusted admit marker: run fr triage admit {key}"
    return f"edited after admission: run fr triage admit {key} again"


def intake_reason(
    author: str | None,
    association: str | None,
    labels: Iterable[str],
    trusted: frozenset[str],
    body: str = "",
    *,
    key: str = "<key>",
    content_digest: str | None = None,
    admit_digest: str | None = None,
    admit_read: bool = False,
    admit_unread: str | None = None,
) -> str | None:
    """None when the issue is eligible, else the reason it is not (R2). *body* is judged
    for the bot's digest marker: callers pass it before any withholding. The `ready-fr`
    label admits only with *admit_digest* (the latest trusted marker's) equal to
    *content_digest* (2026-11-22-triage-hardening R4)."""
    if _admitted_otherwise(author, association, trusted, body):
        return None
    if _labelled(labels):
        if admit_read and admit_digest is not None and admit_digest == content_digest:
            return None
        return _admit_reason(key, admit_read, admit_digest, admit_unread)
    if not author:
        return "author not read"
    if association is None:
        return f"author {author}: association not read"
    return f"author {author} is {association}"


def stored_reason(issue: Issue, config: TriageConfig, viewer: str | None) -> str | None:
    """`intake_reason` over a stored issue's own fields, with *config*'s trusted logins:
    what collect's withholding and `issue_reason` both judge."""
    return intake_reason(
        issue.author,
        issue.author_association,
        issue.labels,
        intake_trusted(config, viewer),
        issue.body,
        key=issue.key,
        content_digest=issue.content_digest,
        admit_digest=issue.admit_digest,
        admit_read=issue.admit_read,
        admit_unread=issue.admit_unread,
    )


def issue_reason(issue: Issue, facts: Facts) -> str | None:
    """`intake_reason` over a collected issue, with its repo's trusted logins."""
    return stored_reason(issue, facts.config_for(issue.repo), facts.viewer)


def rejected_members(batch: Batch, facts: Facts) -> list[tuple[str, str]]:
    """The members that keep *batch* from going out, as (key, reason) (R6).

    A member present in facts is rejected when it is ineligible, open or closed; one absent
    from facts is rejected as `not collected`.
    """
    by_key = {issue.key: issue for issue in facts.issues}
    rejected: list[tuple[str, str]] = []
    for key in batch.ids:
        issue = by_key.get(key)
        if issue is None:
            rejected.append((key, NOT_COLLECTED))
            continue
        reason = issue_reason(issue, facts)
        if reason is not None:
            rejected.append((key, reason))
    return rejected


def untrusted_issues(facts: Facts) -> list[tuple[Issue, str]]:
    """The open ineligible issues, each with its reason (R4)."""
    out: list[tuple[Issue, str]] = []
    for issue in facts.issues:
        if issue.state != "open":
            continue
        reason = issue_reason(issue, facts)
        if reason is not None:
            out.append((issue, reason))
    return out


def rejection_line(rejected: list[tuple[str, str]]) -> str:
    """The one sentence naming each rejected member with its reason, and the way out."""
    members = "; ".join(f"{key}: {reason}" for key, reason in rejected)
    return (
        f"members intake does not admit: {members}; an operator admits an issue with "
        "`fr triage admit <key>`"
    )


def rejected_by_batch(batches: Iterable[Batch], facts: Facts) -> dict[str, str]:
    """Batch id -> `rejection_line`, for each batch holding a rejected member: what both
    snapshot builders put in `Snapshot.rejected`, so the board, `drive --plan` and the live
    pass agree (R6)."""
    out: dict[str, str] = {}
    for batch in batches:
        if rejected := rejected_members(batch, facts):
            out[batch.id] = rejection_line(rejected)
    return out
