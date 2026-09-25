"""The pure half of `batch dispatch` (spec 2026-09-25-triage-batches §3.C, §3.D, §3.E, §3.I).

The brief, the marker comment, the idempotency read of the marker, the
config-freshness rule and the live reservations: judgements and facts in,
text or answers out. The runner, the adapter and the checkout are the command
layer's (`fr.commands.triage_batch_cmd`); nothing here imports `fr_dispatch`,
runs a process or calls a forge.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

from fr.triage.batch import (
    batch_branch,
    batch_repo,
    derive_batch_stage,
    last_dispatch,
)
from fr.triage.errors import TriageError
from fr.triage.model import (
    Batch,
    Facts,
    Judgements,
    batch_marker,
    withdrawn_marker,
)

# Stages whose reservation still stands: the run was briefed with it and has
# not merged or been given up (§3.D "every live reservation").
LIVE_STAGES = frozenset({"dispatched", "pr-open"})
# `dispatch --yes` may start a batch only from these (§3.C step 6.1).
DISPATCHABLE = frozenset({"proposed", "cancelled", "abandoned"})

TRIAGE_CONFIG_PATH = ".fr/triage.yaml"


def render_brief(
    batch: Batch,
    judgements: Judgements,
    facts: Facts,
    *,
    repo: str,
    closing_refs: Sequence[str],
    reserved_version: str | None,
    model: str,
) -> str:
    """The launch brief (§3.C step 3): engine-owned, deterministic text.

    The same judgements and facts always give the same bytes. *closing_refs*
    come from the adapter (`GhClient.closing_ref`), one per member in member
    order, so the brief never hardcodes one forge's closing syntax.
    """
    titles = {i.key: i.title for i in facts.issues}
    lines = [
        f"/fr-goal {batch.title}",
        "",
        f"Batch `{batch.id}` of {repo}: {len(batch.ids)} issues, delivered as ONE pull request.",
    ]
    for key in batch.ids:
        j = judgements.issues.get(key)
        lines += ["", f"## {key}: {titles.get(key, '(title not collected)')}"]
        if j is not None and j.detail:
            lines.append(j.detail)
        if j is not None and j.note:
            lines.append(f"Note: {j.note}")
    if batch.rationale:
        lines += ["", "## Why these belong together", batch.rationale]
    lines += [
        "",
        "## Delivery rules",
        f"- Work on branch `{batch_branch(batch.id)}`.",
        "- Open a draft PR as soon as the spec is committed. Its body contains these "
        "lines, one per member, so every member closes when it merges:",
        *(f"  {ref}" for ref in closing_refs),
    ]
    if reserved_version is not None:
        lines.append(
            f"- Bump the version to `{reserved_version}` (reserved for this batch; "
            "do not pick another number)."
        )
    lines += [
        f"- Use `{model}` for every subagent and every model tier.",
        "- Do not name any member issue as a phase `tracking_issue` in the plan: the "
        "bridge would then own that issue's `fr:` labels.",
    ]
    return "\n".join(lines) + "\n"


def dispatch_comment(batch: Batch, item_id: str, key: str) -> str:
    """Member *key*'s comment (§3.E): marker first, then plain words naming the
    other members. No handle, no host, no local detail."""
    others = [k for k in batch.ids if k != key]
    company = f", with {', '.join(others)}" if others else ""
    return (
        f"{batch_marker(item_id)}\n"
        f"Dispatched as batch `{batch.id}` ({batch.title}){company}. "
        f"Branch `{batch_branch(batch.id)}`."
    )


def dispatched_already(comments: Iterable[dict[str, object]], item_id: str) -> bool:
    """True when a dispatch marker for *item_id* is newer than its latest
    withdrawal (comments oldest first).

    Makes the §3.E comment idempotent under `--repair`, while a redispatch after
    a cancel still posts a NEW marker: the old one predates the withdrawal
    (decision p2-withdrawn-marker).
    """
    latest = None
    for c in comments:
        body = str(c.get("body") or "").lstrip()
        if body.startswith(withdrawn_marker(item_id)):
            latest = "withdrawn"
        elif body.startswith(batch_marker(item_id)):
            latest = "dispatch"
    return latest == "dispatch"


def check_config_fresh(collected_at: str, last_change: datetime | None) -> None:
    """Refuse a collected `.fr/triage.yaml` older than the checkout's last change
    to it on `origin/<default>` (§3.I)."""
    if last_change is None:
        return
    try:
        collected = datetime.fromisoformat(collected_at)
    except ValueError as exc:
        raise TriageError(f"facts.json collected_at {collected_at!r} is unreadable") from exc
    if collected.tzinfo is None or last_change.tzinfo is None or collected < last_change:
        raise TriageError(
            f"the collected {TRIAGE_CONFIG_PATH} predates its last change on the default "
            f"branch ({last_change.isoformat()}); re-collect with `fr triage collect` first"
        )


def live_reservations(batches: Sequence[Batch], facts: Facts, repo: str, *, skip: str) -> list[str]:
    """Reserved versions of the repo's other batches still at dispatched / pr-open."""
    out: list[str] = []
    for b in batches:
        if b.id == skip or batch_repo(b, facts) != repo:
            continue
        event = last_dispatch(b)
        if event and event.reserved_version and derive_batch_stage(b, facts) in LIVE_STAGES:
            out.append(event.reserved_version)
    return out
