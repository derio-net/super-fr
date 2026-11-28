"""The live re-read of admitted members before a batch starts (spec 2026-11-22-triage-hardening
R2, §B).

Collect admits a `ready-fr` issue while its latest trusted admit marker's digest equals its
content digest, but `batch dispatch` judges members from stored facts, and collect carries a
skipped repo's issues unchanged. An author who edits the issue after the last collect would
otherwise reach the launch brief with text no operator admitted. So, just before a batch is
started, every member whose eligibility rests on its admit marker alone
(`fr.triage.intake.admit_pinned`) is read again through the forge adapter and its content
digest recomputed; a mismatch or a failed read refuses the dispatch. A member admitted by a
trusted login or association is not re-read: its admission does not depend on its text.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from fr.ghclient import GhClient
from fr.triage.admit import content_digest, pinned
from fr.triage.collect import ClientForge
from fr.triage.errors import TriageError
from fr.triage.intake import admit_pinned
from fr.triage.model import Batch, Facts


def live_admission(
    forge: ClientForge,
    repo: str,
    number: int,
    raw: Mapping[str, Any],
    pr_authors: Collection[str],
) -> tuple[str, list[dict[str, Any]]]:
    """`(digest, pinned comments)` of the issue *raw* is the forge's record of: its comments
    are read here, so a failed read raises `TriageError` and no caller digests the title and
    body alone (2026-11-28-triage-privacy R3, R5). The one read `fr triage admit` and the
    dispatch re-read share."""
    comments = forge.list_issue_comments(repo=repo, number=number)
    digest = content_digest(
        str(raw.get("title") or ""),
        str(raw.get("body") or ""),
        comments=comments,
        pinned_authors=pr_authors,
    )
    return digest, [c for c in comments if pinned(c, pr_authors)]


def recheck_admitted(batch: Batch, facts: Facts, client: GhClient) -> None:
    """Raise `TriageError` naming each admit-pinned member of *batch* whose live title,
    body and outside comments no longer match its admit marker's digest, or which could not
    be read; return when every one still matches. Reads only."""
    by_key = {issue.key: issue for issue in facts.issues}
    forge = ClientForge(client)
    failed: list[str] = []
    for key in batch.ids:
        issue = by_key.get(key)
        if issue is None or not admit_pinned(issue, facts):
            continue
        again = f"run fr triage admit {issue.repo}#{issue.number}"
        try:
            raw = forge.view_issue(repo=issue.repo, number=issue.number)
            live, _ = live_admission(
                forge, issue.repo, issue.number, raw, facts.config_for(issue.repo).pr_authors
            )
        except TriageError as exc:
            failed.append(f"{key}: could not be read again ({exc}); {again} once it reads")
            continue
        if live != issue.admit_digest:
            failed.append(f"{key}: edited since its admission; {again} again")
    if failed:
        raise TriageError("admitted members changed or unreadable: " + "; ".join(failed))
