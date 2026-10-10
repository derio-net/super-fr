"""`fr triage scope show` and the `fr triage claim` group (triage-claims §3.A, §3.E; R1, R7, R9)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
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
DEAD, ZOMBIE = "s-cccccccc", "s-dddddddd"  # gh#1123: stopped refreshing; one still fresh
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
  "super-fr#6": {tier: 1}
  "super-fr#7": {tier: 1}
  "super-fr#8": {tier: 1}
  "super-fr#9": {tier: 1}
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
        6: _marker(OLD, "dead", at=LONG_AGO, expires=datetime(2026, 9, 2, tzinfo=UTC)),
        7: _marker(DEAD, "dead", at=NOW - timedelta(hours=10), expires=NOW + timedelta(hours=14)),
        8: _marker(ZOMBIE, "z", at=NOW - timedelta(hours=10), expires=NOW + timedelta(hours=14)),
        9: _marker(ZOMBIE, "z", at=NOW - timedelta(hours=1), expires=NOW + timedelta(hours=23)),
    }
    client = FakeGhClient()
    client.comment_author = "operator"
    issues = []
    for n in range(1, 10):
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


# gh#1120: taking over an expired foreign claim, end to end through the CLI.


def _batch(tmp_path: Path, batch_id: str) -> Any:
    return next(
        b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == batch_id
    )


def test_batch_create_accepts_an_expired_held_member_and_names_the_take(
    world: tuple[Path, FakeGhClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path, client = world
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    code, out = _run(tmp_path, "batch", "create", "revive", "--title", "t", "--issue", "super-fr#6")
    assert code == 0, out
    assert _batch(tmp_path, "revive").ids == ["super-fr#6"]
    # the take is the operator's: create writes no claim over the expired one
    assert _writes(client) == []
    assert "fr triage claim take super-fr#6 --batch revive --yes" in " ".join(out.split())


def test_batch_create_still_refuses_a_live_held_member(
    world: tuple[Path, FakeGhClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path, client = world
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    text = (tmp_path / "judgements.yaml").read_text("utf-8")
    (tmp_path / "judgements.yaml").write_text(
        text.replace('ids: ["super-fr#1"]', 'ids: ["super-fr#5"]')
    )
    code, out = _run(tmp_path, "batch", "create", "grab", "--title", "t", "--issue", "super-fr#1")
    assert code == 2, out
    assert "claim take" not in out  # a live claim gets no take hint
    assert all(b.id != "grab" for b in load_judgements(tmp_path / "judgements.yaml").batches)


def test_batch_create_with_a_wave_claims_the_free_members_and_leaves_the_expired_one(
    world: tuple[Path, FakeGhClient], monkeypatch: pytest.MonkeyPatch, me: str
) -> None:
    tmp_path, client = world
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    text = (tmp_path / "judgements.yaml").read_text("utf-8")
    (tmp_path / "judgements.yaml").write_text(
        text.replace('ids: ["super-fr#1"]', 'ids: ["super-fr#5"]')
    )
    code, out = _run(
        tmp_path,
        "batch",
        "create",
        "revive",
        "--title",
        "t",
        "--issue",
        "super-fr#6",
        "--wave",
        "2",
        "--yes",
    )
    assert code == 0, out
    assert _batch(tmp_path, "revive").wave == 2
    assert [m.signer for m in _markers(client, 6)] == [OLD]


def test_batch_edit_add_issue_accepts_an_expired_held_member(
    world: tuple[Path, FakeGhClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path, client = world
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    code, out = _run(tmp_path, "batch", "edit", "spare", "--add-issue", "super-fr#6")
    assert code == 0, out
    assert _batch(tmp_path, "spare").ids == ["super-fr#1", "super-fr#6"]
    assert "fr triage claim take super-fr#6 --batch spare --yes" in " ".join(out.split())


def test_take_on_a_waveless_batch_records_the_take_and_sync_keeps_the_claim(
    world: tuple[Path, FakeGhClient], monkeypatch: pytest.MonkeyPatch, me: str
) -> None:
    tmp_path, client = world
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    code, out = _run(tmp_path, "batch", "create", "revive", "--title", "t", "--issue", "super-fr#6")
    assert code == 0, out
    code, out = _run(tmp_path, "claim", "take", "super-fr#6", "--batch", "revive", "--yes")
    assert code == 0, out
    event = _batch(tmp_path, "revive").events[-1]
    assert event.kind == "claim_taken" and event.keys == ["super-fr#6"]
    # facts as the next collect would show them: our claim, a day later
    later = datetime(2026, 9, 27, 6, 0, tzinfo=UTC)
    facts = json.loads((tmp_path / "facts.json").read_text("utf-8"))
    ours = next(m for m in _markers(client, 6) if m.signer == me)
    cid = next(c["id"] for c in client.issue_comments[(REPO, 6)] if parse_marker(c["body"]) == ours)
    six = next(i for i in facts["issues"] if i["number"] == 6)
    six["claims"] = [_facts_claim(ours, cid, NOW)]
    (tmp_path / "facts.json").write_text(json.dumps(facts), "utf-8")
    monkeypatch.setattr(triage_claim_cmd, "_now", lambda: later)
    code, out = _run(tmp_path, "claim", "sync")
    assert code == 0, out
    assert "release super-fr#6" not in out
    assert "refresh super-fr#6" in out


def test_held_line_names_a_take_sequence_that_works() -> None:
    from fr.triage.claims import Claim, held_line

    h = Claim(
        signer=OLD,
        batch="dead",
        claimed=LONG_AGO,
        heartbeat=LONG_AGO,
        expires=datetime(2026, 9, 2, tzinfo=UTC),
        comment_id=1,
        created_at=LONG_AGO,
    )
    line = " ".join(held_line("super-fr#6", h, NOW).split())
    assert "batch create" in line and "--add-issue" in line
    assert "fr triage claim take super-fr#6 --batch <id> --yes" in line
    assert "claim take" not in held_line("super-fr#6", h, LONG_AGO)


# gh#1123: retiring a dead scope's claims before they expire.


def test_take_stale_refuses_a_fresh_claim_and_takes_a_stale_one(
    world: tuple[Path, FakeGhClient], monkeypatch: pytest.MonkeyPatch, me: str
) -> None:
    tmp_path, client = world
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    # a stale (not yet expired) foreign claim is admitted into a batch, never claimed by it
    code, out = _run(
        tmp_path,
        "batch",
        "create",
        "revive",
        "--title",
        "t",
        "--issue",
        "super-fr#7",
        "--issue",
        "super-fr#9",
    )
    assert code == 2 and "super-fr#9" in out  # #9 is fresh: refused like any live claim
    code, out = _run(tmp_path, "batch", "create", "revive", "--title", "t", "--issue", "super-fr#7")
    assert code == 0, out
    assert "fr triage claim take super-fr#7 --batch revive --stale --yes" in " ".join(out.split())
    code, out = _run(tmp_path, "claim", "take", "super-fr#7", "--batch", "revive", "--yes")
    assert code == 2 and "--stale" in out
    code, out = _run(
        tmp_path, "claim", "take", "super-fr#7", "--batch", "revive", "--stale", "--yes"
    )
    assert code == 0, out
    theirs, mine = _markers(client, 7)
    assert (theirs.released, theirs.released_by) == (NOW, me)
    assert mine.signer == me


def test_take_stale_on_a_fresh_claim_is_refused(world: tuple[Path, FakeGhClient]) -> None:
    tmp_path, client = world
    code, out = _run(
        tmp_path, "claim", "take", "super-fr#1", "--batch", "spare", "--stale", "--yes"
    )
    assert code == 2 and "fresh" in out
    assert _writes(client) == []


def test_release_stale_releases_a_stale_foreign_claim(
    world: tuple[Path, FakeGhClient], me: str
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "claim", "release", "super-fr#7", "--yes")
    assert code == 2 and "--stale" in out
    code, out = _run(tmp_path, "claim", "release", "super-fr#7", "--stale", "--yes")
    assert code == 0, out
    (m,) = _markers(client, 7)
    assert (m.released, m.released_by) == (NOW, me)


def test_scope_retire_previews_then_releases_every_stale_claim(
    world: tuple[Path, FakeGhClient], me: str
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "scope", "retire", DEAD)
    assert code == 0, out
    assert "super-fr#7" in out and "--yes" in out
    assert client.calls == []
    code, out = _run(tmp_path, "scope", "retire", DEAD, "--yes")
    assert code == 0, out
    (m,) = _markers(client, 7)
    assert (m.released, m.released_by) == (NOW, me)
    assert "fr:claimed" not in client.issues[(REPO, 7)].labels


def test_scope_retire_refuses_while_one_claim_is_fresh_and_names_it(
    world: tuple[Path, FakeGhClient], me: str
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "scope", "retire", ZOMBIE, "--yes")
    assert code == 2
    assert "super-fr#9" in out and "--force" in out
    assert _writes(client) == []
    code, out = _run(tmp_path, "scope", "retire", ZOMBIE, "--force", "--yes")
    assert code == 0, out
    assert all(_markers(client, n)[0].released == NOW for n in (8, 9))


def test_scope_retire_refuses_this_scope_and_an_unknown_one(
    world: tuple[Path, FakeGhClient], me: str
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "scope", "retire", me, "--yes")
    assert code == 2 and "claim release" in out
    code, out = _run(tmp_path, "scope", "retire", "s-eeeeeeee", "--yes")
    assert code == 0 and "no claim" in out
    code, out = _run(tmp_path, "scope", "retire", "nonsense", "--yes")
    assert code == 2
    assert _writes(client) == []


def test_no_wave_keeps_a_taken_members_claim(
    world: tuple[Path, FakeGhClient], monkeypatch: pytest.MonkeyPatch, me: str
) -> None:
    """gh#1120: dropping the wave releases the batch's claims, never the operator's take."""
    tmp_path, client = world
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    code, out = _run(tmp_path, "batch", "create", "revive", "--title", "t", "--issue", "super-fr#6")
    assert code == 0, out
    code, out = _run(tmp_path, "claim", "take", "super-fr#6", "--batch", "revive", "--yes")
    assert code == 0, out
    code, out = _run(tmp_path, "batch", "edit", "revive", "--wave", "3")
    assert code == 0, out
    code, out = _run(tmp_path, "batch", "edit", "revive", "--no-wave")
    assert code == 0, out
    assert "release super-fr#6" not in out
