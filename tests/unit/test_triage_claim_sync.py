"""`claim sync` settles closed issues (post-merge truth R1, R2, R4; spec 2026-10-14-merge-truth)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_claim_cmd
from fr.triage import claim_sync as cs
from fr.triage.claims import Marker, parse_marker, render_marker
from fr.triage.model import Batch, Facts, Issue, Scope, StaleInProgress, load_judgements
from fr.triage.scope_config import ScopeConfig, scope_id
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

REPO = "derio-net/super-fr"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
HOST = "0123456789abcdef"
LONG_AGO = datetime(2026, 10, 1, tzinfo=UTC)
FAR = datetime(2999, 1, 1, tzinfo=UTC)
STRANGER = "s-99999999"

JUDGEMENTS = """\
schema: 6
tiers: [{n: 1, title: Now}]
issues:
  "super-fr#10": {tier: 1}
  "super-fr#11": {tier: 1}
  "super-fr#12": {tier: 1}
batches:
  - {id: mine, title: mine, ids: ["super-fr#10", "super-fr#11", "super-fr#12"], wave: 1}
"""


@pytest.fixture
def me(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("FR_HOST_ID", HOST)
    return scope_id(Scope(kind="repo", target=REPO))


def _marker(signer: str, batch: str = "mine") -> Marker:
    return Marker(signer=signer, batch=batch, claimed=LONG_AGO, heartbeat=NOW, expires=FAR)


def _issue(n: int, state: str, claims: list[Marker] | None = None) -> Issue:
    return Issue(
        repo=REPO,
        number=n,
        title=f"issue {n}",
        state=state,  # type: ignore[arg-type]
        url=f"https://github.com/{REPO}/issues/{n}",
        labels=["fr:claimed"] if claims else [],
        claims=[
            {
                "signer": m.signer,
                "batch": m.batch,
                "claimed": m.claimed.isoformat(),
                "heartbeat": m.heartbeat.isoformat(),
                "expires": m.expires.isoformat(),
                "comment_id": 100 + n,
                "created_at": LONG_AGO.isoformat(),
            }
            for m in claims or []
        ],  # type: ignore[misc]
    )


def _hit(n: int, state: str) -> StaleInProgress:
    return StaleInProgress(
        key=f"super-fr#{n}",
        title=f"issue {n}",
        url=f"https://github.com/{REPO}/issues/{n}",
        state=state,  # type: ignore[arg-type]
    )


def _facts(me: str) -> Facts:
    """#10 closed member (own claim stands), #11 open member (own claim, fresh), #12 not held;
    closed non-member #13 (stale), #14 closed and held by a stranger."""
    return Facts(
        viewer="operator",
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-10-14T11:00:00+00:00",
        repos=[REPO],
        issues=[_issue(10, "closed"), _issue(11, "open", [_marker(me)])],
        stale_in_progress=[_hit(10, "release-pending"), _hit(13, "stale"), _hit(14, "held")],
    )


def _env(me: str, facts: Facts) -> cs.ClaimEnv:
    return cs.ClaimEnv(
        me=me, config=ScopeConfig(), facts=facts, client_for=lambda r: FakeGhClient()
    )


def _batches(tmp_path: Path) -> list[Batch]:
    (tmp_path / "judgements.yaml").write_text(JUDGEMENTS, "utf-8")
    return load_judgements(tmp_path / "judgements.yaml").batches


def test_sync_plans_a_settle_per_stale_and_release_pending_closed_hit(
    me: str, tmp_path: Path
) -> None:
    plan = cs.plan_sync(_env(me, _facts(me)), _batches(tmp_path), NOW)
    settles = {(o.key, o.batch) for o in plan.ops if o.kind == "settle"}
    assert settles == {("super-fr#10", "mine"), ("super-fr#13", None)}


def test_a_settle_serves_the_batch_that_owes_the_key_not_the_first_listing_it(
    me: str, tmp_path: Path
) -> None:
    """p1-r3: an earlier, idle batch lists the key too; the wave's batch owes it."""
    (tmp_path / "judgements.yaml").write_text(
        JUDGEMENTS.replace(
            "batches:\n",
            'batches:\n  - {id: old, title: old, ids: ["super-fr#10"]}\n',
        ),
        "utf-8",
    )
    batches = load_judgements(tmp_path / "judgements.yaml").batches
    assert [b.id for b in batches] == ["old", "mine"]
    plan = cs.plan_sync(_env(me, _facts(me)), batches, NOW)
    settles = {(o.key, o.batch) for o in plan.ops if o.kind == "settle"}
    assert ("super-fr#10", "mine") in settles


def test_sync_never_refreshes_a_member_facts_show_closed(me: str, tmp_path: Path) -> None:
    plan = cs.plan_sync(_env(me, _facts(me)), _batches(tmp_path), NOW)
    assert [o.kind for o in plan.ops if o.key == "super-fr#10"] == ["settle"]


def test_sync_keeps_the_due_refresh_for_a_member_facts_do_not_hold(me: str, tmp_path: Path) -> None:
    plan = cs.plan_sync(_env(me, _facts(me)), _batches(tmp_path), NOW)
    assert [o.kind for o in plan.ops if o.key == "super-fr#12"] == ["refresh"]


def test_a_non_settle_op_still_needs_its_batch() -> None:
    with pytest.raises(ValueError):
        cs.ClaimOp("claim", "super-fr#1", None)
    assert cs.ClaimOp("settle", "super-fr#1", None).batch is None


@pytest.fixture
def world(tmp_path: Path, me: str, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, FakeGhClient]:
    client = FakeGhClient()
    client.comment_author = "operator"
    for n, state in ((10, "CLOSED"), (11, "OPEN"), (12, "OPEN"), (13, "CLOSED"), (14, "CLOSED")):
        client.add_issue(REPO, n, state=state, labels={"fr:claimed", "fr:in-progress"})
    for n, signer in ((10, me), (14, STRANGER)):
        client.issue_comments[(REPO, n)] = [
            {
                "author": "operator",
                "body": render_marker(_marker(signer)),
                "created_at": LONG_AGO.isoformat(),
                "id": 100 + n,
            }
        ]
    client.issue_comments[(REPO, 13)] = [
        {
            "author": "stranger",
            "body": render_marker(_marker(STRANGER)),
            "created_at": LONG_AGO.isoformat(),
            "id": 113,
        }
    ]
    (tmp_path / "facts.json").write_text(json.dumps(_facts(me).to_json()), "utf-8")
    (tmp_path / "judgements.yaml").write_text(JUDGEMENTS, "utf-8")
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: client)
    monkeypatch.setattr(triage_claim_cmd, "_now", lambda: NOW)
    return tmp_path, client


def _run(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(app, ["triage", *args, "--repo", REPO, "--dir", str(tmp_path)])
    return result.exit_code, result.output


def test_sync_yes_settles_and_records_claims_released_for_members(
    world: tuple[Path, FakeGhClient], me: str
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "sync", "--yes")
    assert code == 0, out
    for n in (10, 13):
        assert not {"fr:claimed", "fr:in-progress"} & client.issues[(REPO, n)].labels
    assert {"fr:claimed", "fr:in-progress"} <= client.issues[(REPO, 14)].labels  # held
    (m10,) = [parse_marker(c["body"]) for c in client.issue_comments[(REPO, 10)]]
    assert m10 is not None and m10.released == NOW
    mine = next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == "mine")
    event = mine.events[-1]
    assert event.kind == "claims_released" and event.keys == ["super-fr#10"]


def test_execute_release_removes_labels_in_exactly_one_edit(
    world: tuple[Path, FakeGhClient], me: str
) -> None:
    _, client = world
    client.issues[(REPO, 11)].labels.update({"fr:claimed", "fr:in-progress"})
    client.issue_comments[(REPO, 11)] = [
        {
            "author": "operator",
            "body": render_marker(_marker(me)),
            "created_at": LONG_AGO.isoformat(),
            "id": 111,
        }
    ]
    env = cs.ClaimEnv(me=me, config=ScopeConfig(), facts=_facts(me), client_for=lambda r: client)
    result = cs.execute(env, [cs.ClaimOp("release", "super-fr#11", "mine")], NOW + timedelta(0))
    assert not result.failed
    removals = [c for n, c in client.calls if n == "edit_issue_labels" and c["remove"]]
    assert [c["remove"] for c in removals] == [frozenset({"fr:claimed", "fr:in-progress"})]
