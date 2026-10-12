"""Generate the triage-cancelled-terminal scenario fixture from the model's own serializer.

    uv run python tests/scenarios/fixtures/make_cancelled_terminal_facts.py

writes cancelled-terminal-facts.json beside this file: one repo scope with four open
issues, the members of two batches (one with a wave, one without) that were dispatched,
cancelled and had their claims released. Nothing here reaches a forge.
"""

from __future__ import annotations

import json
from pathlib import Path

from fr.triage.model import Facts, Issue

REPO = "example-org/widgets"


def facts() -> Facts:
    issues = [
        Issue(
            repo=REPO,
            number=n,
            title=f"member {n}",
            state="open",
            url=f"https://github.com/{REPO}/issues/{n}",
        )
        for n in (1, 2, 3, 4)
    ]
    return Facts(
        scope="example-org--widgets",
        kind="repo",
        collected_at="2026-10-12T00:00:00Z",
        repos=[REPO],
        issues=issues,
        viewer="operator",
    )


def render(f: Facts) -> str:
    return json.dumps(f.to_json(), indent=2) + "\n"


if __name__ == "__main__":
    out = Path(__file__).with_name("cancelled-terminal-facts.json")
    out.write_text(render(facts()), encoding="utf-8")
