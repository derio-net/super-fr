"""Generate the post-merge-truth scenario fixtures from the model's own serializer.

    uv run python tests/scenarios/fixtures/make_settle_facts.py

writes settle-facts.json (three closed issues still labelled: #101 under this scope's own
claim as a member of a running batch, #102 with only an untrusted marker, #103 held by
another scope) and
retire-sync-facts.json (open #201 under a retired scope's expired claim) beside this file.
`tests/unit/test_triage_settle_fixtures.py` fails when the committed files drift from what
this produces. Nothing here is hand-composed and nothing reaches a forge.
"""

from __future__ import annotations

import json
from pathlib import Path

from fr.triage.model import Facts, Issue, IssueClaim, StaleInProgress

REPO = "derio-net/super-fr"
URL = f"https://github.com/{REPO}/issues"
DEAD = "s-dddddddd"


def _issue(n: int, state: str, **kw: object) -> Issue:
    return Issue(repo=REPO, number=n, title=f"issue {n}", state=state, url=f"{URL}/{n}", **kw)  # type: ignore[arg-type]


def _facts(**kw: object) -> Facts:
    return Facts(
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-10-14T00:00:00Z",
        repos=[REPO],
        viewer="operator",
        **kw,  # type: ignore[arg-type]
    )


def settle() -> Facts:
    hits = [
        StaleInProgress(
            key="super-fr#101", title="issue 101", url=f"{URL}/101", state="release-pending"
        ),
        StaleInProgress(key="super-fr#102", title="issue 102", url=f"{URL}/102", state="stale"),
        StaleInProgress(key="super-fr#103", title="issue 103", url=f"{URL}/103", state="held"),
    ]
    return _facts(issues=[_issue(101, "closed")], stale_in_progress=hits)


def retire_sync() -> Facts:
    claim = IssueClaim(
        signer=DEAD,
        batch="their-batch",
        claimed="2026-09-01T00:00:00Z",
        heartbeat="2026-09-01T00:00:00Z",
        expires="2026-09-02T00:00:00Z",
        comment_id=2001,
        created_at="2026-09-01T00:00:00Z",
    )
    return _facts(issues=[_issue(201, "open", labels=["fr:claimed"], claims=[claim])])


FIXTURES = {"settle-facts.json": settle(), "retire-sync-facts.json": retire_sync()}


def render(f: Facts) -> str:
    return json.dumps(f.to_json(), indent=2) + "\n"


if __name__ == "__main__":
    here = Path(__file__).parent
    for name, f in FIXTURES.items():
        (here / name).write_text(render(f), encoding="utf-8")
