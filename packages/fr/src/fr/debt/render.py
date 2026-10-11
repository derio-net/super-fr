"""Text, Markdown and recoverable figures for a `DebtReport` (R2, R11).

The Markdown body carries two comments: the idempotence marker and the figures
as base64 JSON. Base64 holds no `-->`, so free text in a row note cannot end
the comment early; and the figures are counts, never free text.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any

from fr.acceptance.model import DEBT_STATUSES
from fr.debt.model import AcceptanceDebt, DebtReport

MARKER = "<!-- fr-technical-debt -->"
FIGURES_PREFIX = "<!-- fr-debt-figures:"
ROW_LIMIT = 50
BODY_LIMIT = 60000
CELL_LIMIT = 200
_FIGURES_RE = re.compile(r"<!-- fr-debt-figures:([A-Za-z0-9+/=]*) -->")


def figures(report: DebtReport) -> dict[str, Any]:
    """The counts a forge-only reader recovers without a checkout."""
    return {
        "schema": 1,
        "acceptance": dict(sorted(report.acceptance.by_status.items())),
        "acceptance_available": report.acceptance.available,
        "plans": {
            "archivable": len(report.plans.archivable),
            "stale": len(report.plans.stale),
            "manual_open": len(report.plans.manual_open),
        },
        "owed": len(report.owed),
        "total": report.debt_total(),
        "generated_at": report.generated_at,
    }


def parse_figures(body: str) -> dict[str, Any] | None:
    """The figures embedded in an issue body, or None (absent or unreadable)."""
    m = _FIGURES_RE.search(body or "")
    if not m:
        return None
    try:
        data = json.loads(base64.b64decode(m.group(1), validate=True))
    except (binascii.Error, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _encode(report: DebtReport) -> str:
    raw = json.dumps(figures(report), sort_keys=True).encode()
    return f"{FIGURES_PREFIX}{base64.b64encode(raw).decode()} -->"


def _cell(s: str) -> str:
    s = " ".join((s or "").split()).replace("|", "\\|").replace("<", "&lt;")
    return s if len(s) <= CELL_LIMIT else s[: CELL_LIMIT - 1] + "…"


def _walked(walked_at: str | None) -> str:
    return f"walked {walked_at[:10]}" if walked_at else "walked, undated"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows[:ROW_LIMIT]]
    if len(rows) > ROW_LIMIT:
        out.append(f"\n… {len(rows) - ROW_LIMIT} more — run `fr debt`")
    return out


def _counts_line(by_status: dict[str, int]) -> str:
    return ", ".join(f"{s} {n}" for s, n in sorted(by_status.items())) or "no rows"


def acceptance_section(acc: AcceptanceDebt) -> str:
    """`## Acceptance debt`: the section `fr acceptance digest` re-renders."""
    lines = ["## Acceptance debt", ""]
    if not acc.available:
        lines.append("Acceptance debt is unavailable: the matrix could not be read.")
        return "\n".join(lines)
    lines += [f"Counts: {_counts_line(acc.by_status)}.", ""]
    debt = [r for r in acc.rows if r.status in DEBT_STATUSES]
    if not debt:
        lines.append("No open acceptance debt.")
    else:
        lines += _table(
            ["id", "status", "acceptance", "notes"],
            [[r.id, r.status, r.acceptance, r.notes] for r in debt],
        )
    return "\n".join(lines)


def _plans_section(report: DebtReport) -> list[str]:
    p = report.plans
    lines = ["## Plans", ""]
    if not (p.archivable or p.stale or p.manual_open):
        return [*lines, "No plan debt."]
    if p.archivable:
        lines += ["### Merged complete, not archived", ""]
        lines += _table(
            ["plan", "merged", "command"],
            [
                [
                    a.name,
                    f"{a.age_days} days ago" if a.age_days is not None else "unknown",
                    f"`{a.command}`",
                ]
                for a in p.archivable
            ],
        )
        lines.append("")
    if p.stale:
        lines += [f"### In progress and stale (>{report.stale_days} days)", ""]
        lines += _table(
            ["plan", "idle", "basis"],
            [
                [s.name, f"{s.idle_days} days" if s.idle_days is not None else "unknown", s.basis]
                for s in p.stale
            ],
        )
        lines.append("")
    if p.manual_open:
        lines += ["### Merged, manual phases open", ""]
        lines += _table(
            ["plan", "open phases"],
            [[m.name, ", ".join(str(n) for n in m.phases)] for m in p.manual_open],
        )
    return lines


def _owed_section(report: DebtReport) -> list[str]:
    lines = ["## Owed", ""]
    if not report.owed:
        return [*lines, "Nothing owed."]
    return lines + _table(
        ["key", "source", "what", "how"],
        [[o.key, o.source, o.title, o.how] for o in report.owed],
    )


def markdown(report: DebtReport) -> str:
    """The `<repo>: Technical debt` issue body (R9, R11); under 60,000 chars."""
    lines = [f"# Technical debt ({report.generated_at[:10]})", ""]
    unavailable = [f"{k}: {v.why}" for k, v in report.sources.items() if v.state == "unavailable"]
    if unavailable:
        lines += ["Unavailable sources: " + "; ".join(unavailable), ""]
    if report.debt_total() == 0 and not unavailable and report.acceptance.available:
        lines += ["No technical debt.", ""]
    lines += [acceptance_section(report.acceptance), "", *_plans_section(report), ""]
    lines += [*_owed_section(report), "", MARKER, _encode(report), ""]
    lines.append("_generated by `fr debt`_")
    body = "\n".join(lines)
    if len(body) < BODY_LIMIT:
        return body
    return (
        body[: BODY_LIMIT - 400]
        + f"\n\n… truncated — run `fr debt`\n\n{MARKER}\n{_encode(report)}\n"
    )


def text(report: DebtReport) -> str:
    """The terminal rendering of `fr debt`."""
    acc = report.acceptance
    out = [f"Technical debt — {report.debt_total()} item(s), generated {report.generated_at}", ""]
    for name, st in report.sources.items():
        if st.state == "unavailable":
            out.append(f"! {name} unavailable: {st.why}")
    out.append("Acceptance:")
    if not acc.available:
        out.append("  unavailable (the matrix could not be read)")
    else:
        out.append(f"  {_counts_line(acc.by_status)}")
        out += [
            f"  {r.id} [{r.status}] {_cell(r.acceptance)}"
            for r in acc.rows
            if r.status in DEBT_STATUSES
        ]
        out += [f"  {r.id} [{_walked(r.walked_at)}]" for r in acc.rows if r.status == "walked"]
    out.append("Plans:")
    p = report.plans
    out += [
        f"  archivable {a.name}"
        + (f" (merged {a.age_days} days ago)" if a.age_days is not None else "")
        + f": {a.command}"
        for a in p.archivable
    ]
    out += [
        f"  stale {s.name}"
        + (f" ({s.idle_days} days idle, {s.basis})" if s.idle_days is not None else "")
        for s in p.stale
    ]
    out += [
        f"  manual-open {m.name}: phases {', '.join(str(n) for n in m.phases)}"
        for m in p.manual_open
    ]
    if not (p.archivable or p.stale or p.manual_open):
        out.append("  none")
    out.append("Owed:")
    out += [
        f"  {o.key} ({o.source}) {o.title}" + (f" — {o.how}" if o.how else "") for o in report.owed
    ]
    if not report.owed:
        out.append("  none")
    return "\n".join(out)
