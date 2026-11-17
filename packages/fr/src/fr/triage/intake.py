"""Issue-intake trust: which issues may be batched (spec 2026-11-17-triage-intake R2, R6).

On a public repo anyone can open an issue, and issue text reaches the implementing session's
launch brief. An issue is therefore ELIGIBLE only when at least one clause admits it:

- its author is one of `claim_trusted(config, viewer)` or the debt workflow's bot
  (`BOT_LOGINS`, whose digest `check` already trusts; case-insensitive);
- its author association is in `TRUSTED_ASSOCIATIONS` (OWNER, MEMBER, COLLABORATOR);
- it carries the operator's `ready-fr` label (`fr.labels.READY_FR`), which only an account
  with triage permission can apply.

The rule FAILS CLOSED: an unread author or an unread association never admits an issue.
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
from fr.triage.model import Batch, Facts, Issue, TriageConfig, claim_trusted

NOT_COLLECTED = "not collected"


def intake_trusted(config: TriageConfig, viewer: str | None) -> frozenset[str]:
    """The logins intake admits, lowercased: `claim_trusted(config, viewer)` plus the debt
    workflow's own bot (`fr.triage.debt.BOT_LOGINS`), whose digest `check` already trusts: its
    body must survive collect or the digest would never be read."""
    return claim_trusted(config, viewer) | BOT_LOGINS


def intake_reason(
    author: str | None,
    association: str | None,
    labels: Iterable[str],
    trusted: frozenset[str],
) -> str | None:
    """None when the issue is eligible, else the reason it is not (R2)."""
    if author and author.lower() in trusted:
        return None
    if association is not None and association.upper() in TRUSTED_ASSOCIATIONS:
        return None
    if READY_FR.name in set(labels):
        return None
    if not author:
        return "author not read"
    if association is None:
        return f"author {author}: association not read"
    return f"author {author} is {association}"


def issue_reason(issue: Issue, facts: Facts) -> str | None:
    """`intake_reason` over a collected issue, with its repo's trusted logins."""
    trusted = intake_trusted(facts.config_for(issue.repo), facts.viewer)
    return intake_reason(issue.author, issue.author_association, issue.labels, trusted)


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
