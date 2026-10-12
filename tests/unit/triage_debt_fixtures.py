"""Debt-digest fixtures for the triage tests (debt-engine phase 5): bodies built the
way `fr.debt.render` embeds figures, on the fictional `example-org/widgets` repo."""

from __future__ import annotations

import base64
import json
from typing import Any

from fr.debt.render import FIGURES_PREFIX, MARKER

LEGACY = "<!-- fr-acceptance-digest -->"


def figures(not_implemented: int = 30, **kw: Any) -> dict[str, Any]:
    return {
        "schema": 1,
        "acceptance": kw.pop("acceptance", {"ci": 40, "not-implemented": not_implemented}),
        "acceptance_available": True,
        "plans": kw.pop("plans", {"archivable": 2, "stale": 1, "manual_open": 0}),
        "owed": kw.pop("owed", 3),
        "owed_items": 3,
        "total": 36,
        "generated_at": "2026-10-11T06:00:00+00:00",
        **kw,
    }


def body(data: dict[str, Any] | None = None, marker: str = MARKER) -> str:
    text = f"{marker}\n\n## Technical debt\n\nsome table\n"
    if data is not None:
        raw = json.dumps(data, sort_keys=True).encode()
        text += f"\n{FIGURES_PREFIX}{base64.b64encode(raw).decode()} -->\n"
    return text
