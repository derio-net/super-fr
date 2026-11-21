"""The wave report (spec 2026-11-19-wave-merge-queue R28, §L): what one wave's merge queue
landed, ejected and deferred, what each PR cost, and the release the drain asked for.

Pure: `wave_report` reads queue records (and the batches' own events) and nothing else, so the
close-out PR's body and the Batches page print the same report from the same events.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from fr.triage.model import (
    ApprovalEvent,
    Batch,
    DeferredEvent,
    QueueApprovalEvent,
    QueueBuiltEvent,
    QueueClearedEvent,
    QueueDrainEvent,
    QueueEjectEvent,
    QueueLandEvent,
    QueueRecord,
    RequeuedEvent,
)

Outcome = Literal["landed", "ejected", "deferred"]

REPORT_TITLE = "## Wave merge queue report"
"""The PR body section's heading. `review_reasons` reads only the body's `Closes` lines, so a
section without one is ignored by it (R28)."""


@dataclass(frozen=True)
class PrReport:
    """One PR of the wave: how its queue ended (*outcome*), the CI cycles it took (every
    combination built for it), its wall time from first build to landing (or to its last
    event), the approvals recorded for it, and the detail (the landing's `main`, the ejection's
    reason)."""

    key: str
    outcome: Outcome
    cycles: int = 0
    wall: timedelta | None = None
    approvals: int = 0
    detail: str = ""


@dataclass(frozen=True)
class WaveReport:
    """One queue record's report: its repo and wave, every PR's line and the release the
    drain asked for ("": the queue has not drained)."""

    repo: str
    wave: int | None
    prs: tuple[PrReport, ...]
    release: str = ""


def _key(ref_batch: str | None, kind: str | None, pr: int | None) -> str:
    return ref_batch if ref_batch is not None else f"{kind}#{pr}"


def _wave_report(record: QueueRecord, batches: Sequence[Batch]) -> WaveReport:
    first: dict[str, datetime] = {}
    last: dict[str, datetime] = {}
    cycles: dict[str, int] = {}
    approvals: dict[str, int] = {}
    landed: dict[str, str] = {}
    ejected: dict[str, str] = {}
    drained = ""
    cleared = ""
    for event in record.events:
        if isinstance(event, QueueBuiltEvent):
            key = _key(event.entry.batch, event.entry.kind, event.entry.pr)
            first.setdefault(key, event.at)
            last[key] = event.at
            cycles[key] = cycles.get(key, 0) + 1
            ejected.pop(key, None)
        elif isinstance(event, QueueApprovalEvent):
            key = _key(event.entry.batch, event.entry.kind, event.entry.pr)
            approvals[key] = approvals.get(key, 0) + 1
        elif isinstance(event, QueueEjectEvent):
            key = _key(event.entry.batch, event.entry.kind, event.entry.pr)
            last[key] = event.at
            ejected[key] = event.reason
        elif isinstance(event, QueueLandEvent):
            for ref in event.entries:
                key = _key(ref.batch, ref.kind, ref.pr)
                last[key] = event.at
                landed[key] = event.main
                ejected.pop(key, None)
        elif isinstance(event, QueueDrainEvent):
            drained = event.main or ""
        elif isinstance(event, QueueClearedEvent):
            cleared = event.detail or "cleared"
    for batch in batches:  # a batch's own `approved-fr` records, one per approval event
        key = batch.id
        approvals[key] = approvals.get(key, 0) + sum(
            1 for e in batch.events if isinstance(e, ApprovalEvent)
        )
    prs: list[PrReport] = []
    for key in landed:
        prs.append(PrReport(key, "landed", cycles.get(key, 0), _wall(first, last, key),
                            approvals.get(key, 0), f"at {landed[key][:12]}"))  # fmt: skip
    for key, reason in ejected.items():
        prs.append(PrReport(key, "ejected", cycles.get(key, 0), _wall(first, last, key),
                            approvals.get(key, 0), reason))  # fmt: skip
    for batch in batches:  # deferred out of this wave: a `deferred` naming it, not undone
        if _deferred_from(batch, record.wave):
            prs.append(PrReport(batch.id, "deferred", cycles.get(batch.id, 0), None,
                                approvals.get(batch.id, 0), "left the wave"))  # fmt: skip
    release = ""
    if drained:
        release = f"asked at {drained[:12]}" + (f", {cleared}" if cleared else ", not cleared yet")
    return WaveReport(record.repo, record.wave, tuple(prs), release)


def _wall(first: dict[str, datetime], last: dict[str, datetime], key: str) -> timedelta | None:
    return last[key] - first[key] if key in first and key in last else None


def _deferred_from(batch: Batch, wave: int | None) -> bool:
    """*batch* has a `deferred` event naming *wave* that no later `requeued` undoes."""
    state = False
    for event in batch.events:
        if isinstance(event, DeferredEvent) and event.wave == wave:
            state = True
        elif isinstance(event, RequeuedEvent):
            state = False
    return state


def wave_report(
    records: Sequence[QueueRecord], batches: Sequence[Batch] = (), *, repo: str | None = None
) -> tuple[WaveReport, ...]:
    """One report per queue record of *records* (of *repo* when given), oldest first, with the
    deferred PRs read from *batches*. A record with nothing to report is left out."""
    out = [
        _wave_report(r, [b for b in batches if _in_wave(b, r.wave)])
        for r in records
        if repo is None or r.repo == repo
    ]
    return tuple(r for r in out if r.prs or r.release)


def _in_wave(batch: Batch, wave: int | None) -> bool:
    return any(isinstance(e, DeferredEvent) and e.wave == wave for e in batch.events) or (
        wave is not None and batch.wave == wave
    )


def span(wall: timedelta | None) -> str:
    """A wall time as the report prints it: `29m`, `1h 05m`, `-` when unknown."""
    if wall is None:
        return "-"
    minutes = int(wall.total_seconds() // 60)
    return f"{minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"


def render_markdown(reports: Sequence[WaveReport]) -> str:
    """The report as a Markdown section for a PR body: one table a wave. "" when empty."""
    if not reports:
        return ""
    lines = [REPORT_TITLE, ""]
    for report in reports:
        which = "between waves" if report.wave is None else f"wave {report.wave}"
        header = "| PR | outcome | CI cycles | wall time | approvals | detail |"
        lines += [f"{report.repo}, {which}:", "", header, "|---|---|---|---|---|---|"]
        lines += [
            f"| {p.key} | {p.outcome} | {p.cycles} | {span(p.wall)} | {p.approvals} | {p.detail} |"
            for p in report.prs
        ]
        lines += ["", f"Release: {report.release or 'none asked yet'}", ""]
    return "\n".join(lines).rstrip() + "\n"
