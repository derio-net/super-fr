"""Generate the triage-config-skew scenario fixture from the model's own serializer.

    uv run python tests/scenarios/fixtures/make_config_skew_facts.py

writes config-skew-facts.json beside this file: one repo whose `.fr/triage.yaml`
carried a key this `fr` ignored, and one repo that was skipped. Nothing here reaches a
forge.
"""

from __future__ import annotations

import json
from pathlib import Path

from fr.triage.model import Facts, Skipped

REPO = "example-org/widgets"


def facts() -> Facts:
    return Facts(
        scope="example-org--widgets",
        kind="repo",
        collected_at="2026-10-12T00:00:00Z",
        repos=[REPO, "example-org/gadgets"],
        issues=[],
        viewer="operator",
        config_ignored={REPO: ["future_key"]},
        skipped=[Skipped(repo="example-org/gadgets", reason="not valid triage config")],
    )


def render(f: Facts) -> str:
    return json.dumps(f.to_json(), indent=2) + "\n"


if __name__ == "__main__":
    out = Path(__file__).with_name("config-skew-facts.json")
    out.write_text(render(facts()), encoding="utf-8")
