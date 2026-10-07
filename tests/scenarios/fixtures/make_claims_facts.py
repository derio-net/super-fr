"""Generate the triage-claims scenario fixtures from the model's own serializer.

    uv run python tests/scenarios/fixtures/make_claims_facts.py

writes claims-held-facts.json (widgets#1 under another scope's LIVE claim) and
claims-expired-facts.json (the same claim, expired) beside this file.
`tests/unit/test_triage_claims_fixtures.py` fails when the committed files drift from
what this produces. Nothing here is hand-composed and nothing reaches a forge.
"""

from __future__ import annotations

import json
from pathlib import Path

from fr.triage.model import Facts, Issue, IssueClaim

REPO = "example-org/widgets"
HOLDER = "s-aaaaaaaa"


def facts(expires: str) -> Facts:
    claim = IssueClaim(
        signer=HOLDER,
        batch="their-batch",
        claimed="2026-09-01T00:00:00Z",
        heartbeat="2026-09-01T00:00:00Z",
        expires=expires,
        comment_id=101,
        created_at="2026-09-01T00:00:00Z",
    )
    issues = [
        Issue(
            repo=REPO,
            number=1,
            title="claimed elsewhere",
            state="open",
            labels=["fr:claimed"],
            url=f"https://github.com/{REPO}/issues/1",
            claims=[claim],
        ),
        Issue(
            repo=REPO,
            number=2,
            title="free",
            state="open",
            url=f"https://github.com/{REPO}/issues/2",
        ),
    ]
    return Facts(
        scope="example-org--widgets",
        kind="repo",
        collected_at="2026-10-06T00:00:00Z",
        repos=[REPO],
        issues=issues,
        viewer="operator",
    )


FIXTURES = {
    "claims-held-facts.json": facts("2999-01-01T00:00:00Z"),
    "claims-expired-facts.json": facts("2026-09-02T00:00:00Z"),
}


def render(f: Facts) -> str:
    return json.dumps(f.to_json(), indent=2) + "\n"


if __name__ == "__main__":
    here = Path(__file__).parent
    for name, f in FIXTURES.items():
        (here / name).write_text(render(f), encoding="utf-8")
