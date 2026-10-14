"""The driver's collected close-out (spec 2026-10-14-exit-gates R15, R27, §D).

`drive_pass` step 2 plans at most ONE `closeout` per repo, covering every landed batch
that is not gated, not held and not closed out, and none while a previous collected
close-out (its start marker) is under way. Step 3 plans per marker, never per member:
membership is what the verb recorded, or what the PR body lists after a crash. The pass
is pure: these tests hand-build the `Snapshot`; the executor tests run the drive command
over the in-memory forge.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.triage.batch_drive import (
    attributed,
    closeout_event,
    collected_item_id,
    drive_pass,
)
from fr.triage.model import CollectedCloseout, load_judgements

from tests.unit.test_triage_batch_closeout_cmd import _landed as _world_landed
from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive import NOW, REPO, _dispatched, _kinds, _live, _snap
from tests.unit.test_triage_batch_drive_cmd import (
    DriveCheckout,
    World,
    _drive,
    _lines,
    _sandbox,  # noqa: F401 - the drive tests' autouse sandbox
    checkout_fixture,  # noqa: F401 - registered as `checkout`
    runner_fixture,  # noqa: F401 - registered as `runner`
    world_fixture,  # noqa: F401 - registered as `world`
)

DAY = NOW.date().isoformat()
FIRST = f"chore/closeout-{DAY}-1"
ITEM = f"{REPO}/run/closeout-{DAY}-1"


def _landed(*bids: str, **kw: Any) -> Any:
    batches = [_dispatched(b, i, events=kw.pop(f"{b}_events", [])) for i, b in enumerate(bids, 1)]
    merged_at = {b: NOW - timedelta(hours=1) for b in bids}
    return _snap(batches, dict.fromkeys(bids, "merged"), merged_at=merged_at, **kw)


def _recorded(archive: str = FIRST, run: str | None = "r", **kw: Any) -> list[dict[str, Any]]:
    return [{"kind": "closeout", "at": "2026-10-02T11:00:00Z", "runner": "fake",
             "handle": f"{REPO}/run/{archive.removeprefix('chore/')}", "run": run,
             "archive": archive, **kw}]  # fmt: skip


def _marker(**kw: Any) -> CollectedCloseout:
    kw.setdefault("at", datetime(2026, 10, 2, 11, 0, tzinfo=UTC))
    kw.setdefault("runner", "fake")
    return CollectedCloseout(repo=REPO, item=ITEM, branch=FIRST, **kw)


def _hold(reason: str = "`fr archive` exited 2: Test Plan step 2 has no outcome") -> dict[str, Any]:
    return {"kind": "closeout_hold", "at": "2026-10-02T11:30:00Z", "item": ITEM, "reason": reason}


# ------------------------------------------------------------- step 2 (R15)


def test_three_landed_batches_in_one_repo_get_one_collected_closeout() -> None:
    plan = drive_pass(_landed("a", "b", "c"))

    (action,) = [a for a in plan.actions if a.kind == "closeout"]
    assert action.items == ("a", "b", "c")
    assert action.key == f"closeout-{DAY}-1"
    assert collected_item_id(REPO, action.key) in action.detail
    assert plan.summary.closing == 3


def test_two_repos_get_one_collected_closeout_each() -> None:
    snap = _landed("a", "b", repos={"a": REPO, "b": "derio-net/other"})
    assert sorted(a.items for a in drive_pass(snap).actions if a.kind == "closeout") == [
        ("a",), ("b",)]  # fmt: skip


def test_none_starts_while_a_previous_collected_closeout_is_under_way() -> None:
    plan = drive_pass(_landed("a", "b", closeouts=(_marker(planned=["a"]),)))
    assert [a for a in plan.actions if a.kind == "closeout"] == []


def test_the_next_collected_closeout_takes_the_next_number_once_the_last_merged() -> None:
    snap = _landed("a", "b", a_events=_recorded(archived=900),
                   closeouts=(_marker(pr=900, merged=True),))  # fmt: skip
    (action,) = [a for a in drive_pass(snap).actions if a.kind == "closeout"]
    assert action.items == ("b",) and action.key == f"closeout-{DAY}-2"


def test_p6_r1_a_live_session_of_the_next_item_is_never_started_twice() -> None:
    snap = _landed("a", existing=frozenset({ITEM}))
    assert [a for a in drive_pass(snap).actions if a.kind == "closeout"] == []


def test_a_gated_batch_never_joins_a_collected_closeout() -> None:
    from fr.triage.batch_drive import GateLedger

    snap = _landed("a", "b", ledgers={"b": GateLedger(pr=7, labels=frozenset({"gate:tester"}))})
    assert [a.items for a in drive_pass(snap).actions if a.kind == "closeout"] == [("a",)]


def test_p6_r3_a_held_batch_is_a_need_never_a_member_and_the_board_agrees(
    tmp_path: Path, world: World
) -> None:
    from fr.triage.views import needs_you

    snap = _landed("a", "b", b_events=[_hold()])
    plan = drive_pass(snap)
    assert [a.items for a in plan.actions if a.kind == "closeout"] == [("a",)]
    (held,) = [a for a in plan.actions if a.kind == "closeout-held"]
    assert "Test Plan step 2" in held.detail and "fr triage batch closeout b --yes" in held.detail

    # the board's facts-only plan reads the same hold from the judgements
    from tests.unit.test_triage_batch_drive_cmd import _batch, _dispatch_event, _state

    hold = ("      - {kind: closeout_hold, at: '2026-10-02T11:30:00Z', item: x, "
            "reason: archive held}\n")  # fmt: skip
    world.issues.update({1: "closed", 2: "closed"})
    for n, bid in ((101, "b1"), (102, "b2")):
        world.pr(n, f"feat/batch-{bid}", [n - 100], state="MERGED",
                 merged_at=(NOW - timedelta(hours=1)).isoformat())  # fmt: skip
    b1 = _batch("b1", 1, events=_dispatch_event("b1"))
    b2 = _batch("b2", 2, events=_dispatch_event("b2") + hold)
    path = _state(tmp_path, world, b1, b2) / "judgements.yaml"
    path.write_text(path.read_text("utf-8").replace("schema: 3\n", "schema: 10\n", 1), "utf-8")
    rows = [n for n in needs_you(world.facts(), load_judgements(path)) if n.kind == "closeout-held"]
    assert [(n.ref, "fr triage batch closeout b2 --yes" in n.text) for n in rows] == [("b2", True)]


# -------------------------------------------------------- attributed (§D)


def test_attributed_accepts_the_shared_head_for_a_trusted_author_even_with_no_run() -> None:
    batch = _dispatched("d", 1, skill="debug", events=_recorded(run=None))
    event = closeout_event(batch)
    assert event is not None
    assert attributed(_live(900, "h900", head_ref=FIRST, trusted=True), batch, event)
    assert not attributed(_live(901, "h", head_ref=FIRST, trusted=False), batch, event)
    other = _live(902, "h", head_ref=f"chore/closeout-{DAY}-2", trusted=True)
    assert not attributed(other, batch, event)


# ------------------------------------------- step 3: one step per marker (§D)


FILES = (
    "D\tdocs/superpowers/runs/r.yaml",
    "A\tdocs/superpowers/implemented/runs/r.yaml",
    "M\tdocs/acceptance/matrix.yaml",
)


def _shared(**kw: Any) -> Any:
    kw.setdefault("mergeable", "MERGEABLE")
    kw.setdefault("files", ("docs/superpowers/implemented/plans/p/_meta.yaml",))
    kw.setdefault("trusted", True)
    return _live(900, kw.pop("head", "h900"), head_ref=FIRST, base="main", **kw)


def _anchored(members: tuple[str, ...], **kw: Any) -> CollectedCloseout:
    """The marker as the verb records it after its push (R15's trust anchor)."""
    kw.setdefault("files", list(FILES))
    return _marker(pr=900, head="h900", members=list(members), **kw)


def _under_way(pr: Any, *bids: str, handbacks: list[dict[str, Any]] | None = None,
               **kw: Any) -> Any:  # fmt: skip
    """*bids* closed out onto PR #900; the driver's own reads agree with the record."""
    events = {f"{b}_events": [*_recorded(), *(handbacks or [])] for b in bids}
    reads: dict[str, Any] = {
        "collected_diff": {ITEM: frozenset(FILES)}, "collected_commits": {ITEM: ("h900",)},
        "collected_narrowed": {ITEM: frozenset()}, "collected_body_closes": {ITEM: frozenset()},
    }  # fmt: skip
    for key in list(reads):
        if key in kw:
            reads[key] = kw.pop(key)
    marker = kw.pop("marker", _anchored(bids))
    return _landed(*bids, closeouts=(marker,), collected_prs={ITEM: pr}, **reads, **events,
                   **kw)  # fmt: skip


def _kinds_of(snap: Any) -> list[str]:
    return [k for k, _ in _kinds(drive_pass(snap).actions)]


def test_a_green_mergeable_recorded_pr_is_readied_and_merged_at_the_recorded_head() -> None:
    plan = drive_pass(_under_way(_shared(draft=True), "a", "b", "c"))
    (merge,) = [a for a in plan.actions if a.kind == "archive"]
    assert (merge.pr, merge.head, merge.items, merge.draft, merge.key) == (
        900, "h900", ("a", "b", "c"), True, ITEM)  # fmt: skip


def test_a_collected_pr_not_yet_known_mergeable_waits() -> None:
    plan = drive_pass(_under_way(_shared(mergeable="UNKNOWN"), "a"))
    assert [a for a in plan.actions if a.kind in ("archive", "closeout-handback")] == []


# p6b-r1: the forge's file list is a writer's; only the driver's own diff counts


def test_p6b_r1_a_code_change_the_forge_file_list_hides_is_never_auto_merged() -> None:
    """Attack: push a code change onto the recorded file set's branch while the forge's
    `files` still shows only docs (truncated or stale): the driver's own diff sees it."""
    hidden = frozenset({*FILES, "A\tpackages/fr/src/fr/backdoor.py"})
    snap = _under_way(_shared(files=("docs/superpowers/runs/r.yaml",)), "a",
                      collected_diff={ITEM: hidden})  # fmt: skip
    plan = drive_pass(snap)
    assert "archive" not in [a.kind for a in plan.actions]
    (need,) = [a for a in plan.actions if a.kind == "closeout-needs-review"]
    assert "packages/fr/src/fr/backdoor.py" in need.detail


@pytest.mark.parametrize("path", [
    "docs/superpowers/workflows/fr-goal.yaml", "docs/superpowers/verifications/x.yaml",
    "docs/superpowers/plans/p/_meta.yaml", ".github/workflows/ci.yml",
])  # fmt: skip
def test_p6b_r1_only_an_archives_paths_are_ever_auto_merged(path: str) -> None:
    """Attack: the recorded set itself carries a non-archive path (a manifest the driver
    resolves, a live plan modified rather than moved): never merged without approval."""
    files = [*FILES, f"M\t{path}"]
    snap = _under_way(_shared(), "a", marker=_anchored(("a",), files=files),
                      collected_diff={ITEM: frozenset(files)})  # fmt: skip
    assert "archive" not in _kinds_of(snap) and "closeout-needs-review" in _kinds_of(snap)


def test_p6b_r1_an_unreadable_diff_is_never_auto_merged() -> None:
    snap = _under_way(_shared(), "a", collected_diff={ITEM: None})
    assert "archive" not in _kinds_of(snap) and "closeout-needs-review" in _kinds_of(snap)


# p6b-r3: membership is the verb's record, never the PR body


def test_p6b_r3_an_unrecorded_pr_is_a_need_never_reconciled_from_its_body() -> None:
    """Attack: open a PR on the marker's branch whose body lists any batches: the driver
    records nothing from it and merges nothing."""
    snap = _landed("a", "b", closeouts=(_marker(pr=900, planned=["a", "b"]),),
                   collected_prs={ITEM: _shared()})  # fmt: skip
    plan = drive_pass(snap)
    (need,) = [a for a in plan.actions if a.kind == "closeout-unrecorded"]
    assert f"--branch {FIRST} --yes" in need.detail
    assert [a for a in plan.actions if a.kind in ("archive", "closeout")] == []


# p6b-r4: only the head the verb pushed, from the repo itself, alone past the base


@pytest.mark.parametrize(("pr", "reads"), [
    (_shared(head="h999"), {}),  # a commit pushed after the verb's: another head
    (_shared(), {"collected_commits": {ITEM: ("h900", "h0ld")}}),  # an extra commit
    (_shared(trusted=False), {}),  # a fork's PR, or a foreign author's, on the branch name
])  # fmt: skip
def test_p6b_r4_any_head_commit_or_author_but_the_verbs_is_never_auto_merged(
    pr: Any, reads: dict[str, Any]
) -> None:
    snap = _under_way(pr, "a", **reads)
    assert "archive" not in _kinds_of(snap) and "closeout-needs-review" in _kinds_of(snap)


# p6b-r5: Closes is the recorded set, against today's narrowing, in this repo only


@pytest.mark.parametrize(("body", "narrowed"), [
    ({f"{REPO}#7", f"{REPO}#99"}, frozenset()),  # an issue added to the body
    ({f"{REPO}#7", "derio-net/other#7"}, frozenset()),  # another repo's issue
    ({f"{REPO}#7"}, frozenset({f"{REPO}#7"})),  # narrowed since the record
])  # fmt: skip
def test_p6b_r5_a_body_closing_anything_but_the_recorded_issues_is_never_auto_merged(
    body: set[str], narrowed: frozenset[str]
) -> None:
    snap = _under_way(_shared(), "a", marker=_anchored(("a",), closes=[f"{REPO}#7"]),
                      collected_body_closes={ITEM: frozenset(body)},
                      collected_narrowed={ITEM: narrowed})  # fmt: skip
    assert "archive" not in _kinds_of(snap) and "closeout-needs-review" in _kinds_of(snap)


def test_p6b_r5_the_recorded_closes_merge() -> None:
    snap = _under_way(_shared(), "a", marker=_anchored(("a",), closes=[f"{REPO}#7"]),
                      collected_body_closes={ITEM: frozenset({f"{REPO}#7"})})  # fmt: skip
    assert "archive" in _kinds_of(snap)


def test_a_conflicting_collected_pr_is_handed_back_once_to_its_session() -> None:
    plan = drive_pass(_under_way(_shared(mergeable="CONFLICTING"), "a", "b"))
    (back,) = [a for a in plan.actions if a.kind == "closeout-handback"]
    assert (back.key, back.head, back.items, back.checks) == (ITEM, "h900", ("a", "b"),
                                                              ("merge conflict",))  # fmt: skip


def test_a_red_collected_pr_is_handed_back_naming_its_failing_checks() -> None:
    pr = _shared(checks="failing", failing=("lint", "test"))
    (back,) = [a for a in drive_pass(_under_way(pr, "a")).actions if a.kind == "closeout-handback"]
    assert back.checks == ("lint", "test")


def _handback(head: str, delivered: str = "session") -> dict[str, Any]:
    return {"kind": "closeout_handback", "at": "2026-10-02T11:30:00Z", "item": ITEM, "pr": 900,
            "head": head, "reason": "merge conflict", "delivered": delivered}  # fmt: skip


def test_a_hand_back_at_this_head_is_never_repeated() -> None:
    snap = _under_way(_shared(mergeable="CONFLICTING"), "a", "b", handbacks=[_handback("h900")])
    kinds = _kinds_of(snap)
    assert "closeout-handback" not in kinds and "closeout-stuck" not in kinds


def test_a_second_failure_at_a_later_head_is_a_stuck_need() -> None:
    """R27: the budget is ONE per close-out item, counted across its members."""
    snap = _landed("a", "b", closeouts=(_anchored(("a", "b")),),
                   collected_prs={ITEM: _shared(mergeable="CONFLICTING", head="h901")},
                   a_events=[*_recorded(), _handback("h900")], b_events=_recorded())  # fmt: skip
    plan = drive_pass(snap)
    (stuck,) = [a for a in plan.actions if a.kind == "closeout-stuck"]
    assert stuck.key == ITEM and stuck.items == ("a", "b")
    assert plan.summary.blocked == 1


def test_a_hand_back_no_session_took_is_a_stuck_need_at_once() -> None:
    snap = _under_way(_shared(mergeable="CONFLICTING"), "a", handbacks=[_handback("h900", "none")])
    assert "closeout-stuck" in _kinds_of(snap)


# p6b-r10: the budget is the item's, members or not; a reopened PR is never merged


def test_p6b_r10_the_hand_back_budget_holds_with_no_member_event() -> None:
    """Attack: a member's events lost (or none recorded) must not reset the budget."""
    marker = _anchored(("a",), handed=["h900"])
    snap = _landed("a", closeouts=(marker,),
                   collected_prs={ITEM: _shared(mergeable="CONFLICTING", head="h901")})  # fmt: skip
    assert "closeout-stuck" in _kinds_of(snap) and "closeout-handback" not in _kinds_of(snap)


def test_p6b_r10_a_closed_then_reopened_pr_is_a_need_and_never_merged() -> None:
    snap = _landed("a", closeouts=(_anchored(("a",), closed=True),),
                   collected_reopened={ITEM: _shared()})  # fmt: skip
    kinds = _kinds_of(snap)
    assert "closeout-reopened" in kinds and "archive" not in kinds


# p6b-r6: a hand run that died with nothing pushed never wedges the repo


def test_p6b_r6_a_stale_hand_marker_with_no_branch_and_no_pr_is_abandoned() -> None:
    snap = _landed("a", closeouts=(_marker(runner="hand", planned=["a"]),),
                   closeout_probed=frozenset({ITEM}))  # fmt: skip
    assert "closeout-abandoned" in _kinds_of(snap)


def test_p6_r5_a_collected_pr_closed_unmerged_ends_the_closeout_and_its_batches_are_owed() -> None:
    closed = _shared(state="CLOSED")
    plan = drive_pass(_under_way(closed, "a"))
    (ended,) = [a for a in plan.actions if a.kind == "closeout-pr-closed"]
    assert ended.key == ITEM
    # recorded closed: the next pass re-collects a, on the next number
    after = _landed("a", a_events=_recorded(), closeouts=(_marker(pr=900, closed=True),))
    (again,) = [a for a in drive_pass(after).actions if a.kind == "closeout"]
    assert again.items == ("a",) and again.key == f"closeout-{DAY}-2"


def test_the_closeout_hand_back_budget_is_its_own_and_conflict_decisions_is_unchanged() -> None:
    from fr.triage.batch_drive import HANDBACKS_PER_DISPATCH, conflict_decision

    assert HANDBACKS_PER_DISPATCH == 2
    assert conflict_decision([], "h", ["p"], []).kind == "handback"


# ------------------------------------------------------- the event (schema 10)


def test_the_closeout_events_move_the_judgements_schema() -> None:
    from fr.triage.model import JUDGEMENTS_READS, JUDGEMENTS_SCHEMA, Judgements

    assert JUDGEMENTS_SCHEMA == 10 and JUDGEMENTS_READS[-1] == 10
    judged = {"tiers": [{"n": 1, "title": "Now"}], "issues": {"super-fr#1": {"tier": 1}}}
    batch = {"id": "a", "title": "a", "ids": ["super-fr#1"],
             "events": [*_recorded(), _handback("h900"), _hold()]}  # fmt: skip
    got = Judgements.model_validate({"schema": 10, **judged, "batches": [batch]})
    assert [e.kind for e in got.batches[0].events][1:] == ["closeout_handback", "closeout_hold"]
    with pytest.raises(ValueError, match="schema"):
        Judgements.model_validate({"schema": 9, **judged, "batches": [batch]})
    with pytest.raises(ValueError, match="schema 10"):
        Judgements.model_validate({"schema": 9, "closeouts": [_marker().model_dump(mode="json")]})
    older = {**batch, "events": _recorded()}
    assert Judgements.model_validate({"schema": 9, **judged, "batches": [older]}).schema_ == 9


# ------------------------------------------------------ the executor (§E)

CMD_DAY = "2026-10-02"  # the drive tests' NOW
CMD_BRANCH = f"chore/closeout-{CMD_DAY}-1"
CMD_ITEM = f"{REPO}/run/closeout-{CMD_DAY}-1"


def test_p6_r1_the_driver_records_a_start_marker_and_never_a_members_event(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _world_landed(world, tmp_path, "b1", "b2", "b3")
    checkout.released = True

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    (item,) = runner.dispatched
    assert item.id == CMD_ITEM
    assert f"fr triage batch closeout b1 b2 b3 --branch {CMD_BRANCH} --yes" in item.payload["brief"]
    judgements = load_judgements(tmp_path / "judgements.yaml")
    assert [e.kind for b in judgements.batches for e in b.events] == ["dispatch"] * 3
    (marker,) = judgements.closeouts
    assert (marker.item, marker.branch, marker.planned) == (CMD_ITEM, CMD_BRANCH,
                                                            ["b1", "b2", "b3"])  # fmt: skip
    code, out = _drive(tmp_path, "--once", "--yes")  # under way: nothing starts again
    assert len(runner.dispatched) == 1 and _lines(out, "closeout") == []


def _started(world: World, tmp_path: Path, *bids: str, checkout: Any = None,
             **pr: Any) -> Path:  # fmt: skip
    """*bids* landed and closed out by the verb onto PR #900, open on the shared branch,
    with the verb's record (head, members, diff, closes) on the marker."""
    from tests.unit.test_triage_batch_drive_cmd import _batch, _dispatch_event, _state

    rec = (f"      - {{kind: closeout, at: '2026-10-02T11:00:00Z', runner: fake, "
           f"handle: {CMD_ITEM}, archive: {CMD_BRANCH}}}\n")  # fmt: skip
    batches = []
    for i, bid in enumerate(bids, 1):
        world.issues[i] = "closed"
        world.pr(100 + i, f"feat/batch-{bid}", [i], state="MERGED",
                 merged_at=(NOW - timedelta(hours=1)).isoformat())  # fmt: skip
        batches.append(_batch(bid, i, events=_dispatch_event(bid) + rec))
    body = f"<!-- fr:closeout-members {','.join(bids)} -->\nCloses {REPO}#7"
    world.pr(900, CMD_BRANCH, [], **{"mergeable": "MERGEABLE", "body": body,
                                     "files": ["docs/superpowers/runs/r.yaml"], **pr})  # fmt: skip
    target = _state(tmp_path, world, *batches)
    path = target / "judgements.yaml"
    files = list(FILES)
    if checkout is not None:  # the driver's own diff: what is really on the head
        checkout.status["sha-900"] = frozenset(pr.pop("diff", files))
    marker = CollectedCloseout(repo=REPO, item=CMD_ITEM, branch=CMD_BRANCH, runner="fake",
                               at=datetime(2026, 10, 2, 11, 0, tzinfo=UTC), pr=900,
                               head="sha-900", members=list(bids), files=files,
                               closes=[f"{REPO}#7"])  # fmt: skip
    import yaml

    block = yaml.safe_dump({"closeouts": [marker.model_dump(mode="json", exclude_defaults=True)]},
                           sort_keys=False)  # fmt: skip
    path.write_text(path.read_text("utf-8").replace("schema: 3\n", "schema: 10\n", 1) + block)
    return target


def test_p6_r8_the_driver_merges_the_collected_pr_then_unlabels_what_it_closed(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _started(world, tmp_path, "b1", "b2", checkout=checkout, draft=True)

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert world.calls.index("pr_ready 900") < world.calls.index("pr_merge 900")
    assert world.calls.count("pr_merge 900") == 1
    assert "label 7" in world.calls  # fr:awaiting-live off the issue its body Closes
    judgements = load_judgements(tmp_path / "judgements.yaml")
    assert {b.id: closeout_event(b).archived for b in judgements.batches} == {  # type: ignore[union-attr]
        "b1": 900, "b2": 900}  # fmt: skip
    assert judgements.closeouts[0].merged


def test_p6_r6_a_collected_pr_touching_code_is_never_auto_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _started(
        world, tmp_path, "b1", checkout=checkout, diff=[*FILES, "A\tscripts/x.sh"]
    )  # the forge's file list says docs only
    code, out = _drive(tmp_path, "--once", "--yes")
    assert "pr_merge 900" not in world.calls
    (line,) = _lines(out, "closeout-needs-review")
    assert "scripts/x.sh" in line


def test_a_conflicting_collected_pr_is_handed_back_once_and_recorded_on_each_member(
    tmp_path: Path, world: World, checkout: DriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import triage_batch_cmd

    from tests.unit.test_triage_batch_drive_cmd import MessengerRunner

    messenger = MessengerRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: messenger)
    _started(world, tmp_path, "b1", "b2", checkout=checkout, mergeable="CONFLICTING")

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    ((item, text),) = messenger.messages
    assert item == CMD_ITEM and CMD_BRANCH in text and "PR #900" in text
    backs = {
        b.id: [(e.item, e.head) for e in b.events if e.kind == "closeout_handback"]  # type: ignore[union-attr]
        for b in load_judgements(tmp_path / "judgements.yaml").batches
    }
    assert backs == dict.fromkeys(("b1", "b2"), [(CMD_ITEM, "sha-900")])
    _drive(tmp_path, "--once", "--yes")
    assert len(messenger.messages) == 1


def test_p6_r5_a_closed_collected_pr_is_recorded_once_and_its_batches_are_owed(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _started(world, tmp_path, "b1", checkout=checkout, state="CLOSED")
    checkout.released = True

    code, out = _drive(tmp_path, "--once", "--yes")

    assert len(_lines(out, "closeout-pr-closed")) == 1, out
    assert load_judgements(tmp_path / "judgements.yaml").closeouts[0].closed
    code, out = _drive(tmp_path, "--once", "--yes")  # owed again: a fresh close-out
    assert _lines(out, "closeout-pr-closed") == []
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/closeout-{CMD_DAY}-2"]


def test_a_hand_back_no_session_took_is_a_need_on_the_board(tmp_path: Path, world: World) -> None:
    from fr.triage.views import NEED_LABELS, needs_you

    target = _started(world, tmp_path, "b1", "b2", mergeable="CONFLICTING")
    path = target / "judgements.yaml"
    none = (f"      - {{kind: closeout_handback, at: '2026-10-02T11:30:00Z', item: {CMD_ITEM}, "
            "pr: 900, head: sha-900, reason: merge conflict, delivered: none}\n")  # fmt: skip
    end = f"archive: {CMD_BRANCH}}}\n"
    path.write_text(path.read_text("utf-8").replace(end, end + none))
    needs = [
        n for n in needs_you(world.facts(), load_judgements(path)) if n.kind == "closeout-stuck"
    ]
    assert len(needs) == 1 and "PR #900" in needs[0].text
    assert {"closeout-stuck", "closeout-held", "closeout-pr-closed",
            "closeout-needs-review"} <= NEED_LABELS.keys()  # fmt: skip


def test_p6b_r2_a_collected_pr_with_no_check_results_is_never_green(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """Attack: a head no CI ever reported on (checks never registered, or results only for
    another head) must not read green and merge."""
    _started(world, tmp_path, "b1", checkout=checkout)
    world.checks[900] = []
    world.all_checks[900] = {"pass": 0, "fail": 0, "pending": 0}

    code, out = _drive(tmp_path, "--once", "--yes")

    assert "pr_merge 900" not in world.calls, out
