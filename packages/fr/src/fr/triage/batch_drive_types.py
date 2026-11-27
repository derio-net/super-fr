"""The drive pass's value types: the verdicts, the action kinds, a live PR, an admitted queue
entry and an action (spec 2026-11-27-triage-leaves-split R1). Split out of `batch_drive` so
its leaves can build actions without importing the pass, which re-exports every name here.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ChecksVerdict = Literal["green", "pending", "failing"]
ActionKind = Literal[
    "closeout",
    "adopt",
    "dispatch",
    "blocked",
    "held",
    "warn",
    "foreign",
    "close",
    "dedupe",
    "claim",
    "refresh",
    "release",
    "settle",
    "export",
    "export-reconcile",
    "export-closed",
    "conflict-probe",
    "archive-conflict",
    "export-conflict",
    "awaiting-live",
    "gate-pass",
    "ledger-unread",
    "post-merge",
    "closeout-held",
    "closeout-handback",
    "closeout-stuck",
    "closeout-unrecorded",
    "closeout-reopened",
    "closeout-merged",
    "closeout-pr-closed",
    "closeout-needs-review",
    "closeout-abandoned",
]

CONFLICTING = "CONFLICTING"
"""The forge's `mergeable` for a PR that cannot merge cleanly (merge-truth R12)."""


@dataclass(frozen=True)
class LivePr:
    """A PR as the forge shows it now: a batch PR, or an archive PR candidate."""

    number: int
    state: str  # OPEN | MERGED | CLOSED
    draft: bool
    head: str
    checks: ChecksVerdict = "green"
    failing: tuple[str, ...] = ()
    head_ref: str = ""
    files: tuple[str, ...] = ()
    # From the repo itself, by an allowed author (`fr.triage.batch.distrust`). False
    # unless the command checked it: an archive PR is attributed only when True (gh#936).
    trusted: bool = False
    # The branch the PR merges into, as the forge says now; "" when not read. An export
    # PR is reused or merged only into the default branch (p4-r15).
    base: str = ""
    # Its labels as read now; None when not read. `gate:devops` without `-passed` holds
    # the merge (fr-ops R14): the planner plans no merge or enqueue for it.
    labels: tuple[str, ...] | None = None
    # GitHub's `mergeable` (MERGEABLE | CONFLICTING | UNKNOWN) and `mergeStateStatus`, ""
    # when not read. A CONFLICTING archive or export PR is never merged (merge-truth R12);
    # a collected close-out's PR merges only once `MERGEABLE` (exit-gates R15).
    mergeable: str = ""
    merge_state: str = ""
    url: str = ""  # the PR's page; "" when not read (batch-merge-readiness R6's links)


@dataclass(frozen=True)
class Admitted:
    """A non-batch PR its own trust rule admitted to its repo's queue (R32): a collected
    close-out (`review_reasons` empty), an attributed archive PR (`archive_allowed`), a
    wave's state-export PR (`_export_row`'s checks) or a housekeeping PR with `approved-fr`
    recorded on the queue's events. *pr* is the PR at the head the rule judged, which is the
    head the queue builds; *batch* is the batch it is about, *wave* the wave whose queue it
    joins (None: between waves) and *at* when it was admitted, which orders it."""

    kind: Literal["closeout", "archive", "export", "housekeeping", "operator"]
    repo: str
    pr: LivePr
    batch: str = ""
    wave: int | None = None
    at: datetime | None = None

    @property
    def key(self) -> str:
        return f"{self.kind}#{self.pr.number}"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    batch: str
    detail: str
    pr: int | None = None
    head: str = ""
    recorded: bool = False  # closeout: the runner holds the tab; record the event only
    archived: int | None = None  # adopt: the close-out event's `archived`
    # close: the item ids whose sessions to close; closeout, closeout-handback,
    # closeout-stuck of a collected close-out: its member batch ids
    items: tuple[str, ...] = ()
    # export*, and a warn about one: the wave key (`batch` is then the repo); the
    # highest wave the export PR covers, which names its branch
    wave: str | None = None
    covers: tuple[str, ...] = ()  # export: every wave the PR records
    # claim, refresh, release, settle: the issue key; a collected close-out's actions: its
    # name, `closeout-<date>-<n>`
    key: str = ""
    red: bool = False  # warn: a failing batch PR, which the driver tries to recover (§C)
    checks: tuple[str, ...] = ()  # warn (red): the failing check names
    gate: str = ""  # gate-pass: the post-merge gate whose rows all read walked
    branch: str = ""  # archive-conflict: the archive PR's head branch (merge-truth R12)


def _wrong_base(live: LivePr, default: str) -> str:
    """Why *live* is not based on the default branch, or "" (p4-r15). An unknown base
    is never the default."""
    if default and live.base == default:
        return ""
    return f"is based on {live.base or 'an unknown branch'}, not {default or 'the default branch'}"
