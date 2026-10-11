"""The archive sweep behind `fr debt archive-pr` (spec 2026-10-11-debt-engine R12).

Pure selection and rendering; the git and forge steps live in the command so a
test can see each one. Nothing here writes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from fr.debt.model import ArchivablePlan, DebtReport

BRANCH = "chore/debt-archive-sweep"
PR_TITLE = "chore: archive merged plans (debt sweep)"
MARKER = "<!-- fr-debt-archive-sweep -->"
HELD_REASON = "held: Test Plan outcomes missing"
SAFE_REF = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]*$")
"""A ref or branch name that cannot be read as an option (no leading `-`)."""
SAFE_PLAN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


@dataclass
class Sweep:
    """Who the sweep archived, held, or could not archive."""

    archived: list[ArchivablePlan] = field(default_factory=list)
    held: list[tuple[ArchivablePlan, list[str]]] = field(default_factory=list)
    failed: list[tuple[ArchivablePlan, str]] = field(default_factory=list)


def select(report: DebtReport) -> list[ArchivablePlan]:
    """Archivable plans merged for MORE than `stale_days`. The floor is
    deliberate: the batch driver starts a close-out at merge, and sweeping a
    just-merged plan would archive it out from under its own close-out
    (#660/#664). A merge age that is unknown is not old enough."""
    return [
        p
        for p in report.plans.archivable
        if p.age_days is not None and p.age_days > report.stale_days and SAFE_PLAN.match(p.name)
    ]


def token_note(*, own_token: bool) -> str:
    if own_token:
        return "Opened with `FR_DEBT_TOKEN`, so CI runs on this PR."
    return (
        "Opened with the workflow's own token (`FR_DEBT_TOKEN` is not set), so CI will not "
        "run on this PR until someone pushes to the branch."
    )


def pr_body(sweep: Sweep, *, stale_days: int, own_token: bool) -> str:
    lines = [
        f"Plans merged complete and unarchived for more than {stale_days} days "
        "(`fr debt archive-pr`). Review, mark ready and merge; this job never does.",
        "",
        "## Archived",
        "",
    ]
    lines += [
        f"- `{p.name}`" + (f" (merged {p.age_days} days ago)" if p.age_days is not None else "")
        for p in sweep.archived
    ] or ["- none"]
    if sweep.held:
        lines += ["", f"## {HELD_REASON}", ""]
        for p, why in sweep.held:
            lines += [f"- `{p.name}`", "", "  ```", *[f"  {ln}" for ln in why], "  ```"]
    if sweep.failed:
        lines += ["", "## Not archived", ""]
        lines += [f"- `{p.name}`: {' '.join(why.split())[:300]}" for p, why in sweep.failed]
    lines += ["", token_note(own_token=own_token), "", MARKER]
    return "\n".join(lines)
