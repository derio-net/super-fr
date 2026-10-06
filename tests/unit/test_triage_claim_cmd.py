"""`fr triage scope show` and the `fr triage claim` group (triage-claims §3.A, §3.E; R1, R7, R9)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_claim_cmd
from fr.triage.claims import Marker, parse_marker, render_marker
from fr.triage.model import Facts, Issue, Scope, load_judgements
from fr.triage.scope_config import scope_id
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

REPO = "derio-net/super-fr"
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
HOST = "0123456789abcdef"
LIVE, OLD = "s-aaaaaaaa", "s-bbbbbbbb"
LONG_AGO = datetime(2026, 9, 1, tzinfo=UTC)
FAR = datetime(2999, 1, 1, tzinfo=UTC)

JUDGEMENTS = """\
schema: 6
tiers: [{n: 1, title: Now}]
issues:
  "super-fr#1": {tier: 1}
  "super-fr#2": {tier: 1}
  "super-fr#3": {tier: 1}
  "super-fr#4": {tier: 1}
  "super-fr#5": {tier: 1}
batches:
  - {id: mine, title: mine, ids: ["super-fr#2", "super-fr#3", "super-fr#4"], wave: 1}
  - {id: spare, title: spare, ids: ["super-fr#1"]}
  - id: gone
    title: gone
    ids: ["super-fr#5"]
    wave: 1
    events:
      - {kind: dispatch, at: "2026-09-02T00:00:00Z", runner: r, handle: h, branch: feat/batch-gone}
      - {kind: cancel, at: "2026-09-03T00:00:00Z"}
"""


@pytest.fixture
def me(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("FR_HOST_ID", HOST)
    return scope_id(Scope(kind="repo", target=REPO))


def _marker(signer: str, batch: str, *, at: datetime, expires: datetime) -> Marker:
    return Marker(signer=signer, batch=batch, claimed=at, heartbeat=at, expires=expires)


def _comment(m: Marker, cid: int, at: datetime) -> dict[str, Any]:
    return {"author": "operator", "body": render_marker(m), "created_at": at.isoformat(), "id": cid}


def _facts_claim(m: Marker, cid: int, at: datetime) -> dict[str, Any]:
    return {
        "signer": m.signer,
        "batch": m.batch,
        "claimed": m.claimed.isoformat(),
        "heartbeat": m.heartbeat.isoformat(),
        "expires": m.expires.isoformat(),
        "comment_id": cid,
        "created_at": at.isoformat(),
    }


@pytest.fixture
def world(tmp_path: Path, me: str, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, FakeGhClient]:
    markers = {
        1: _marker(LIVE, "theirs", at=LONG_AGO, expires=FAR),
        2: _marker(OLD, "old", at=LONG_AGO, expires=datetime(2026, 9, 2, tzinfo=UTC)),
        3: _marker(me, "mine", at=LONG_AGO, expires=FAR),
        5: _marker(me, "gone", at=LONG_AGO, expires=FAR),
    }
    client = FakeGhClient()
    client.comment_author = "operator"
    issues = []
    for n in range(1, 6):
        claimed = n in markers
        client.add_issue(REPO, n, labels={"fr:claimed"} if claimed else set())
        claims = []
        if claimed:
            client.issue_comments[(REPO, n)] = [_comment(markers[n], n, LONG_AGO)]
            claims = [_facts_claim(markers[n], n, LONG_AGO)]
        issues.append(
            Issue(
                repo=REPO,
                number=n,
                title=f"issue {n}",
                state="open",
                url=f"https://github.com/{REPO}/issues/{n}",
                labels=["fr:claimed"] if claimed else [],
                claims=claims,  # type: ignore[arg-type]
            )
        )
    facts = Facts(
        viewer="operator",
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-09-26T11:00:00+00:00",
        repos=[REPO],
        issues=issues,
    )
    (tmp_path / "facts.json").write_text(json.dumps(facts.to_json()), "utf-8")
    (tmp_path / "judgements.yaml").write_text(JUDGEMENTS, "utf-8")
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: client)
    monkeypatch.setattr(triage_claim_cmd, "_now", lambda: NOW)
    return tmp_path, client


def _run(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(app, ["triage", *args, "--repo", REPO, "--dir", str(tmp_path)])
    return result.exit_code, result.output


def _writes(client: FakeGhClient) -> list[str]:
    return [n for n, _ in client.calls if n != "list_issue_comments"]


def _markers(client: FakeGhClient, n: int) -> list[Marker]:
    out = []
    for c in client.issue_comments.get((REPO, n), []):
        if (m := parse_marker(c["body"])) is not None:
            out.append(m)
    return out


def test_scope_show_prints_name_id_state_dir_and_config(tmp_path: Path, me: str) -> None:
    (tmp_path / "scope.yaml").write_text("claim_expiry_hours: 6\n", "utf-8")
    code, out = _run(tmp_path, "scope", "show")
    assert code == 0, out
    assert "derio-net--super-fr" in out
    assert me in out
    assert str(tmp_path) in " ".join(out.split())
    assert "claim_expiry_hours: 6" in out
    assert "super-fr batches" in out


def test_claim_list_shows_the_three_sets(world: tuple[Path, FakeGhClient]) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "list")
    assert code == 0, out
    for label in ("held elsewhere", "expired claims", "claims owed"):
        assert label in out
    assert LIVE in out and OLD in out
    assert "super-fr#4" in out
    assert client.calls == []


def test_claim_sync_without_yes_prints_the_plan_and_writes_nothing(
    world: tuple[Path, FakeGhClient],
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "sync")
    assert code == 0, out
    assert "claim super-fr#4 for mine" in out
    assert "refresh super-fr#3" in out
    assert "release super-fr#5 (gone)" in out
    assert "held" in out and "super-fr#2" in out
    assert "--yes" in out
    assert client.calls == []


def test_claim_sync_yes_writes_claims_refreshes_releases_and_records(
    world: tuple[Path, FakeGhClient], me: str
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "sync", "--yes")
    assert code == 0, out
    (m4,) = _markers(client, 4)
    assert (m4.signer, m4.batch, m4.released) == (me, "mine", None)
    (m3,) = _markers(client, 3)
    assert m3.heartbeat == NOW
    (m5,) = _markers(client, 5)
    assert m5.released == NOW
    assert "fr:claimed" not in client.issues[(REPO, 5)].labels
    # #2 is held (an expired foreign claim): nothing written there
    assert [m.signer for m in _markers(client, 2)] == [OLD]
    gone = next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == "gone")
    event = gone.events[-1]
    assert event.kind == "claims_released" and event.keys == ["super-fr#5"]


def test_claim_take_refuses_a_live_claim(world: tuple[Path, FakeGhClient]) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "take", "super-fr#1", "--batch", "spare", "--yes")
    assert code == 2
    assert "live" in out
    assert _writes(client) == []


def test_claim_take_previews_then_takes_an_expired_claim(
    world: tuple[Path, FakeGhClient], me: str
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "take", "super-fr#2", "--batch", "mine")
    assert code == 0, out
    assert "--yes" in out and client.calls == []
    code, out = _run(tmp_path, "claim", "take", "super-fr#2", "--batch", "mine", "--yes")
    assert code == 0, out
    theirs, mine = _markers(client, 2)
    assert theirs.released == NOW and theirs.released_by == me
    assert (mine.signer, mine.batch) == (me, "mine")


def test_claim_take_needs_a_batch_of_this_scope_holding_the_issue(
    world: tuple[Path, FakeGhClient],
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "take", "super-fr#2", "--batch", "gone", "--yes")
    assert code == 2 and _writes(client) == []


def test_claim_release_own_any_time_foreign_only_expired(
    world: tuple[Path, FakeGhClient], me: str
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "release", "super-fr#3", "--yes")
    assert code == 0, out
    assert _markers(client, 3)[0].released == NOW
    code, out = _run(tmp_path, "claim", "release", "super-fr#1", "--yes")
    assert code == 2 and "live" in out
    code, out = _run(tmp_path, "claim", "release", "super-fr#2", "--yes")
    assert code == 0, out
    (m2,) = _markers(client, 2)
    assert m2.released == NOW and m2.released_by == me
    assert "fr:claimed" not in client.issues[(REPO, 2)].labels


def test_claim_release_without_yes_writes_nothing(world: tuple[Path, FakeGhClient]) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "release", "super-fr#3")
    assert code == 0 and "--yes" in out
    assert client.calls == []
