"""Debt digests on the board (debt-engine spec §C, R14-R16).

A debt digest is an open issue carrying the debt marker (`fr-technical-debt`, or the
legacy `fr-acceptance-digest`) as a line of its own. Its figures are parsed from the
body the facts already hold, at check and render time, so the facts schema is not
bumped. Issue bodies come from the forge: the numbers read here are coerced to plain
ints and used for display only, never for any decision.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fr.debt.render import MARKER, parse_figures

if TYPE_CHECKING:
    from fr.triage.model import Facts, Issue

LEGACY_MARKER = "<!-- fr-acceptance-digest -->"
MARKERS = (MARKER, LEGACY_MARKER)
PLAN_CATEGORIES = ("archivable", "stale", "manual_open")


def has_marker(body: str) -> bool:
    """Whether *body* carries a debt marker as a line of its own."""
    return any(line.strip() in MARKERS for line in (body or "").splitlines())


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def clean_figures(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """*raw* reduced to what the board may show: counts as ints, nothing else.
    A key or value of any other shape is dropped; None stays None."""
    if raw is None:
        return None
    acc = raw.get("acceptance")
    plans = raw.get("plans")
    return {
        "acceptance": {
            k: v
            for k, v in sorted((acc if isinstance(acc, dict) else {}).items())
            if isinstance(k, str) and k.replace("-", "").isalnum() and _count(v) is not None
        },
        "plans": {
            k: n
            for k in PLAN_CATEGORIES
            if (n := _count((plans if isinstance(plans, dict) else {}).get(k))) is not None
        },
        "owed": _count(raw.get("owed")),
        "total": _count(raw.get("total")),
        "generated_at": raw["generated_at"][:40]
        if isinstance(raw.get("generated_at"), str)
        else None,
    }


def issue_figures(issue: Issue) -> dict[str, Any] | None:
    """The cleaned figures embedded in *issue*'s body, or None."""
    return clean_figures(parse_figures(issue.body))


def digest_for(facts: Facts, repo: str) -> Issue | None:
    """The newest open debt digest of *repo* (highest number), or None."""
    from fr.triage.check import is_debt_digest

    mine = [i for i in facts.issues if i.repo == repo and is_debt_digest(i)]
    return max(mine, key=lambda i: i.number) if mine else None


def figures_by_repo(facts: Facts) -> dict[str, dict[str, Any]]:
    """Repo -> cleaned figures, for every collected repo whose digest embeds them."""
    out: dict[str, dict[str, Any]] = {}
    for repo in facts.collected:
        digest = digest_for(facts, repo)
        fig = issue_figures(digest) if digest is not None else None
        if fig is not None:
            out[repo] = fig
    return out
