"""Debt-digest fixtures for the triage tests (debt-engine phase 5): bodies built the
way `fr.debt.render` embeds figures, on the fictional `example-org/widgets` repo."""

from __future__ import annotations

import base64
import json
from typing import Any

from fr.acceptance.model import DEBT_STATUSES
from fr.debt.render import FIGURES_PREFIX, MARKER

LEGACY = "<!-- fr-acceptance-digest -->"


BOT = "github-actions[bot]"


def figures(not_implemented: int = 30, **kw: Any) -> dict[str, Any]:
    acceptance = kw.pop("acceptance", {"ci": 40, "not-implemented": not_implemented})
    plans = kw.pop("plans", {"archivable": 2, "stale": 1, "manual_open": 0})
    owed = kw.pop("owed", 3)
    debt = sum(n for s, n in acceptance.items() if s in DEBT_STATUSES and isinstance(n, int))
    total = debt + plans["archivable"] + plans["stale"] + (owed if isinstance(owed, int) else 0)
    return {
        "schema": 1,
        "acceptance": acceptance,
        "acceptance_available": True,
        "plans": plans,
        "owed": owed,
        "owed_items": 3,
        "total": kw.pop("total", total),
        "generated_at": "2026-10-11T06:00:00+00:00",
        **kw,
    }


def digest(
    number: int,
    data: dict[str, Any] | None,
    *,
    marker: str = MARKER,
    author: str = BOT,
    repo: str = "example-org/widgets",
    **kw: Any,
) -> dict[str, Any]:
    """A debt-digest issue record by *author* (the workflow bot unless said otherwise)."""
    return {
        "repo": repo,
        "number": number,
        "title": "Technical debt",
        "state": "open",
        "url": f"https://github.com/{repo}/issues/{number}",
        "created_at": "2026-10-01T00:00:00Z",
        "author": author,
        "body": body(data, marker),
        **kw,
    }


def body(data: dict[str, Any] | None = None, marker: str = MARKER) -> str:
    text = f"{marker}\n\n## Technical debt\n\nsome table\n"
    if data is not None:
        raw = json.dumps(data, sort_keys=True).encode()
        text += f"\n{FIGURES_PREFIX}{base64.b64encode(raw).decode()} -->\n"
    return text
