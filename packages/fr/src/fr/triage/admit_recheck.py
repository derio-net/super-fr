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

from fr.ghclient import GhClient
from fr.triage.admit import content_digest
from fr.triage.collect import ClientForge
from fr.triage.errors import TriageError
from fr.triage.intake import admit_pinned
from fr.triage.model import Batch, Facts


def recheck_admitted(batch: Batch, facts: Facts, client: GhClient) -> None:
    """Raise `TriageError` naming each admit-pinned member of *batch* whose live title and
    body no longer match its admit marker's digest, or which could not be read; return when
    every one still matches. Reads only."""
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
        except TriageError as exc:
            failed.append(f"{key}: could not be read again ({exc}); {again} once it reads")
            continue
        live = content_digest(str(raw.get("title") or ""), str(raw.get("body") or ""))
        if live != issue.admit_digest:
            failed.append(f"{key}: edited since its admission; {again} again")
    if failed:
        raise TriageError("admitted members changed or unreadable: " + "; ".join(failed))
