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
from fr.debt.model import AcceptanceDebt, DebtReport, SourceStatus

MARKER = "<!-- fr-technical-debt -->"
BOT_LOGINS = frozenset({"github-actions[bot]", "github-actions", "app/github-actions"})
"""The workflow's own bot: the one author besides the viewer whose digest is trusted."""
FIGURES_PREFIX = "<!-- fr-debt-figures:"
ROW_LIMIT = 50
BODY_LIMIT = 60000
CELL_LIMIT = 200
_FIGURES_RE = re.compile(r"<!-- fr-debt-figures:([A-Za-z0-9+/=]*) -->")


_URL_CREDS = re.compile(r"(?<=://)[^/\s@]+@")
_TOKENS = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{10,})"
)
_HOME = re.compile(r"(?:/Users|/home)/[^/\s]+")


def redact(text: str) -> str:
    """*text* with URL credentials, token-shaped strings and home paths removed.
    Applied to everything fr echoes from a forge or a subprocess, and to every
    cell published in a body."""
    text = _URL_CREDS.sub("***@", text)
    text = _TOKENS.sub("***", text)
    return _HOME.sub("~", text)


def source_category(name: str, st: SourceStatus) -> str:
    """The fixed, publishable category of a source's state. The detailed reason
    stays in `fr debt`'s terminal output and the CI log, never in a body."""
    why = st.why.lower()
    if st.state == "unavailable":
        if "offline" in why:
            return "offline"
        if "tracking" in why:
            return "tracking none"
        if name == "matrix":
            return "matrix unreadable"
        return "forge error" if name == "forge" else f"{name} unavailable"
    if "fetch failed" in why:
        return "fetch failed"
    if "partial" in why:
        return "partial: listing cap reached"
    if "unreadable" in why:
        return "unreadable, skipped"
    return "see `fr debt`"


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
        "owed": report.owed_counted(),
        "owed_items": len(report.owed),
        "total": report.debt_total(),
        "generated_at": report.generated_at,
    }


BODY_READ_LIMIT = 64 * 1024
"""A body longer than this is never searched for figures: the renderer's own bodies stop at
`BODY_LIMIT`, so anything larger was not written by it."""
PAYLOAD_LIMIT = 8 * 1024
"""The base64 payload of a figures block, before it is decoded."""
_SHORT = 200


def _scalar(v: Any) -> bool:
    return v is None or isinstance(v, (bool, int)) or (isinstance(v, str) and len(v) <= _SHORT)


def _flat(data: dict[str, Any]) -> bool:
    """Whether *data* is a flat dict of ints and short strings, or one level of such
    dicts (the `acceptance` and `plans` counts): nothing deeper, no lists."""
    for k, v in data.items():
        if not isinstance(k, str) or len(k) > _SHORT:
            return False
        if isinstance(v, dict):
            if not all(
                isinstance(k2, str) and len(k2) <= _SHORT and _scalar(v2) for k2, v2 in v.items()
            ):
                return False
        elif not _scalar(v):
            return False
    return True


def parse_figures(body: str) -> dict[str, Any] | None:
    """The figures embedded in an issue body, or None (absent, unreadable or out of
    bounds). The input is bounded BEFORE it is decoded, because a body is forge text."""
    if not body or len(body) > BODY_READ_LIMIT:
        return None
    # The LAST block: the renderer appends it after every free-text section.
    found = _FIGURES_RE.findall(body)
    if not found:
        return None
    m_group = found[-1]
    if len(m_group) > PAYLOAD_LIMIT:
        return None
    try:
        data = json.loads(base64.b64decode(m_group, validate=True))
    except (binascii.Error, ValueError):
        return None
    return data if isinstance(data, dict) and _flat(data) else None


def _encode(report: DebtReport) -> str:
    raw = json.dumps(figures(report), sort_keys=True).encode()
    return f"{FIGURES_PREFIX}{base64.b64encode(raw).decode()} -->"


def _cell(s: str) -> str:
    s = redact(" ".join((s or "").split())).replace("|", "\\|").replace("<", "&lt;")
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
    unavailable = [
        f"{k}: {source_category(k, v)}"
        for k, v in report.sources.items()
        if v.state == "unavailable"
    ]
    if unavailable:
        lines += ["Unavailable sources: " + "; ".join(unavailable), ""]
    partial = [
        f"{k}: {source_category(k, v)}"
        for k, v in report.sources.items()
        if v.state == "read" and v.why
    ]
    if partial:
        lines += ["Notes: " + "; ".join(partial), ""]
    if report.debt_total() == 0 and not unavailable and report.acceptance.available:
        lines += ["No technical debt.", ""]
    lines += [acceptance_section(report.acceptance), "", *_plans_section(report), ""]
    lines += _owed_section(report)
    tail = f"\n\n{MARKER}\n{_encode(report)}\n\n_generated by `fr debt`_"
    body = "\n".join(lines)
    if len(body) + len(tail) < BODY_LIMIT:
        return body + tail
    room = BODY_LIMIT - len(tail) - 100
    return body[:room] + "\n\n… truncated — run `fr debt`" + tail


def text(report: DebtReport) -> str:
    """The terminal rendering of `fr debt`."""
    acc = report.acceptance
    out = [f"Technical debt — {report.debt_total()} item(s), generated {report.generated_at}", ""]
    for name, st in report.sources.items():
        if st.state == "unavailable":
            out.append(f"! {name} unavailable: {redact(st.why)}")
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
