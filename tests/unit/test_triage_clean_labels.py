"""The closed-but-in-progress set and `fr triage clean-labels` (board-truth §B; R2, R3)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.gh import GhError
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient
from fr.triage.check import classify, clean_label_targets
from fr.triage.claims import Marker, render_marker
from fr.triage.model import Facts
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.triage_board_fixtures import facts as make_facts
from tests.unit.triage_board_fixtures import judgements

REPO = "example-org/widgets"


def _entry(n: int, state: str) -> dict[str, Any]:
    return {
        "key": f"widgets#{n}",
        "title": f"issue {n}",
        "url": f"https://github.com/{REPO}/issues/{n}",
        "closed_at": "2026-10-01T00:00:00Z",
        "state": state,
    }


def _facts(*entries: dict[str, Any]) -> Facts:
    return make_facts([], stale_in_progress=list(entries))


def test_check_json_lists_the_whole_set_with_each_entrys_state() -> None:
    f = _facts(_entry(1, "stale"), _entry(2, "release-pending"), _entry(3, "held"))
    got = classify(f, judgements({})).to_json()["closed_in_progress"]
    assert [(e["key"], e["state"]) for e in got] == [
        ("widgets#1", "stale"),
        ("widgets#2", "release-pending"),
        ("widgets#3", "held"),
    ]


def test_the_one_target_predicate_is_the_stale_entries_only() -> None:
    f = _facts(_entry(1, "stale"), _entry(2, "release-pending"), _entry(3, "held"))
    assert [t.key for t in clean_label_targets(f)] == ["widgets#1"]


def test_check_text_lists_stale_then_release_pending_and_held_apart(tmp_path: Path) -> None:
    f = _facts(_entry(3, "held"), _entry(2, "release-pending"), _entry(1, "stale"))
    (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), "utf-8")
    out = (
        CliRunner().invoke(app, ["triage", "check", "--repo", REPO, "--dir", str(tmp_path)]).output
    )
    section = out[out.index("closed in progress") :]
    assert section.index("widgets#1") < section.index("widgets#2") < section.index("widgets#3")
    assert "release-pending" in section and "held" in section


def test_the_triage_page_folds_the_set_and_the_board_notes_the_command() -> None:
    from fr.triage.render import render

    f = _facts(_entry(1, "stale"), _entry(2, "held"))
    page = render(f, judgements({}))
    assert 'id="closed-in-progress"' in page and "widgets#1" in page and "widgets#2" in page
    assert "<details" in page[page.index('id="closed-in-progress"') - 20 :]
    clean = render(_facts(), judgements({}))
    assert 'id="closed-in-progress"' not in clean


def test_the_board_note_fires_on_stale_or_release_pending_and_names_the_rule() -> None:
    from fr.commands.triage_kanban_cmd import in_progress_note

    f = _facts(_entry(1, "stale"), _entry(2, "release-pending"), _entry(3, "held"))
    note = in_progress_note(f, ["--repo", REPO])
    assert note is not None and "2 closed issues" in note
    assert "claim sync --repo example-org/widgets --yes" in note and "drive" in note
    assert "fr triage clean-labels --repo example-org/widgets --yes" in note
    only_pending = in_progress_note(_facts(_entry(2, "release-pending")), ["--repo", REPO])
    assert only_pending is not None and "1 closed issue " in only_pending
    assert in_progress_note(_facts(_entry(3, "held")), ["--repo", REPO]) is None


def test_every_surface_states_the_same_clearing_rule(tmp_path: Path) -> None:
    from fr.triage.check import CLEARING_RULE
    from fr.triage.render import render

    f = _facts(_entry(1, "stale"), _entry(2, "release-pending"))
    page = render(f, judgements({}))
    assert "claim sync --yes" in page and "clean-labels --yes" in page
    (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), "utf-8")
    out = (
        CliRunner().invoke(app, ["triage", "check", "--repo", REPO, "--dir", str(tmp_path)]).output
    )
    flat = " ".join(out.split())
    assert "claim sync --yes" in flat and "clean-labels --yes" in flat
    assert "claim sync --yes" in CLEARING_RULE and "clean-labels --yes" in CLEARING_RULE


# ------------------------------------------------------------- the verb


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, FakeGhClient]:
    monkeypatch.setenv("FR_HOST_ID", "0123456789abcdef")
    client = FakeGhClient()
    for n in (1, 2, 3, 4, 5, 6):
        client.add_issue(REPO, n, labels={"fr:in-progress"}, state="CLOSED")
    client.issues[(REPO, 2)].state = "OPEN"  # reopened since collect
    client.issues[(REPO, 3)].labels.add("fr:claimed")  # claimed since collect, by another scope
    t = datetime(2026, 10, 1, tzinfo=UTC)
    rival = Marker(signer="s-22222222", batch="b", claimed=t, heartbeat=t, expires=t)
    client.issue_comments[(REPO, 3)] = [
        {"author": "operator", "body": render_marker(rival), "created_at": t.isoformat(), "id": 1}
    ]
    f = make_facts(
        [],
        stale_in_progress=[
            _entry(1, "stale"),
            _entry(2, "stale"),
            _entry(3, "stale"),
            _entry(4, "release-pending"),
            _entry(5, "held"),
            _entry(6, "stale"),
        ],
    )
    (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), "utf-8")
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: client)
    return tmp_path, client


def _run(tmp_path: Path, *args: str) -> tuple[int, str]:
    r = CliRunner().invoke(
        app, ["triage", "clean-labels", "--repo", REPO, "--dir", str(tmp_path), *args]
    )
    return r.exit_code, r.output


def _edits(client: FakeGhClient) -> list[dict[str, Any]]:
    return [c for n, c in client.calls if n == "edit_issue_labels"]


def test_without_yes_it_names_each_stale_target_and_writes_nothing(
    world: tuple[Path, FakeGhClient],
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path)
    assert code == 0, out
    for n in (1, 2, 3, 6):
        assert f"widgets#{n}" in out
    assert "widgets#4" not in out and "widgets#5" not in out
    assert "nothing written" in out
    assert client.calls == []


def test_with_yes_it_rereads_each_target_and_removes_the_label_from_the_rest(
    world: tuple[Path, FakeGhClient],
) -> None:
    tmp_path, client = world
    code, out = _run(tmp_path, "--yes")
    assert code == 0, out
    assert "fr:in-progress" not in client.issues[(REPO, 1)].labels
    assert "fr:in-progress" not in client.issues[(REPO, 6)].labels
    # re-read: #2 is open again, #3 is held by another scope now; both left alone
    assert "fr:in-progress" in client.issues[(REPO, 2)].labels
    assert "fr:in-progress" in client.issues[(REPO, 3)].labels
    assert "skipped widgets#2" in out and "skipped widgets#3" in out
    # release-pending and held are never targets
    assert "fr:in-progress" in client.issues[(REPO, 4)].labels
    assert "fr:in-progress" in client.issues[(REPO, 5)].labels
    assert [c["number"] for c in _edits(client)] == [1, 6]
    both = frozenset({"fr:claimed", "fr:in-progress"})
    assert all(c["remove"] == both for c in _edits(client) if c["remove"])
    assert sum(1 for line in out.splitlines() if "widgets#" in line) == 4  # one outcome each


def test_clean_labels_removes_both_labels_and_no_longer_skips_fr_claimed(
    world: tuple[Path, FakeGhClient],
) -> None:
    tmp_path, client = world
    client.add_issue(REPO, 7, labels={"fr:in-progress", "fr:claimed"}, state="CLOSED")
    f = make_facts([], stale_in_progress=[_entry(7, "stale")])
    (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), "utf-8")
    code, out = _run(tmp_path, "--yes")
    assert code == 0, out
    assert not {"fr:claimed", "fr:in-progress"} & client.issues[(REPO, 7)].labels
    assert "skipped" not in out
    removals = [c["remove"] for c in _edits(client) if c["remove"]]
    assert removals == [frozenset({"fr:claimed", "fr:in-progress"})]


def test_a_per_issue_failure_is_reported_the_rest_continue_and_the_exit_is_nonzero(
    world: tuple[Path, FakeGhClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path, client = world
    real = client.edit_issue_labels

    def flaky(repo: str, number: int, *, add: frozenset[str], remove: frozenset[str]) -> None:
        if number == 1:
            raise GhError("boom")
        real(repo, number, add=add, remove=remove)

    monkeypatch.setattr(client, "edit_issue_labels", flaky)
    code, out = _run(tmp_path, "--yes")
    assert code != 0
    assert "boom" in out
    assert "fr:in-progress" not in client.issues[(REPO, 6)].labels


@pytest.mark.parametrize("client_cls", [RealGlabClient, RealTeaClient], ids=["glab", "tea"])
def test_glab_and_tea_are_refused_before_any_read_or_write(
    world: tuple[Path, FakeGhClient], monkeypatch: pytest.MonkeyPatch, client_cls: Any
) -> None:
    tmp_path, fake = world
    real = client_cls()  # constructed, never called: any forge call would fail loudly
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: real)
    code, out = _run(tmp_path, "--yes")
    assert code == 2 and real.backend in out and "clean-labels" in out
    assert fake.calls == []


def test_the_closed_in_progress_section_comes_first_in_the_text_report(tmp_path: Path) -> None:
    f = _facts(_entry(1, "stale"))
    (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), "utf-8")
    out = (
        CliRunner().invoke(app, ["triage", "check", "--repo", REPO, "--dir", str(tmp_path)]).output
    )
    assert out.index("closed in progress") < out.index("unranked")
