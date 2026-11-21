"""The operator's view of the wave merge queue (spec 2026-11-19-wave-merge-queue R25, R28, R29):
the queue line, the halt's explicit retry, and the Needs.

Pure: every test builds a `QueueSnapshot` by hand, as `test_wave_queue_planner.py` does.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from fr.triage.approval import First
from fr.triage.batch_drive import LivePr
from fr.triage.kanban import build_board
from fr.triage.model import Batch, QueueRecord
from fr.triage.scope_config import scope_id
from fr.triage.views import NEED_LABELS, needs_you
from fr.triage.wave_queue import (
    Hold,
    QueueConfig,
    QueuePlan,
    QueueSnapshot,
    SlotCheck,
    plan_queue,
    queue_line,
    queue_view,
)

from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - the drive tests' fixtures
    _sandbox,
    checkout_fixture,
    runner_fixture,
    world_fixture,
)
from tests.unit.triage_board_fixtures import REPO as REPO_B
from tests.unit.triage_board_fixtures import batch as mk
from tests.unit.triage_board_fixtures import dispatch, facts, issue, j, judgements, pr

REPO = "derio-net/super-fr"
ME = "s-11111111"
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
AT = "2026-11-20T10:00:00Z"
MAIN = "m0" * 20
TRUSTED = ("bot",)


def _batch(bid: str, n: int, *, wave: int | None = 1) -> Batch:
    return Batch.model_validate({
        "id": bid, "title": bid, "ids": [f"super-fr#{n}"], "wave": wave,
        "events": [{"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake",
                    "handle": "h", "branch": f"feat/batch-{bid}"}],
    })  # fmt: skip


def _record(*events: dict[str, Any], wave: int | None = 1) -> QueueRecord:
    return QueueRecord.model_validate(
        {"repo": REPO, "wave": wave, "scope": ME, "base": MAIN, "events": list(events)}
    )


def _built(slot: int, sha: str, bid: str, parent: str = MAIN) -> dict[str, Any]:
    return {
        "kind": "queue_built", "at": AT, "slot": slot, "sha": sha, "entry": {"batch": bid},
        "head": f"head-{bid}", "patch_id": f"pid-{bid}", "base": MAIN, "parent": parent,
    }  # fmt: skip


def _qs(batches: Sequence[Batch], record: QueueRecord, **kw: Any) -> QueueSnapshot:
    stages = {b.id: "pr-open" for b in batches}
    live = {b.id: LivePr(number=100 + i, state="OPEN", draft=False, head=f"head-{b.id}",
                         checks="green") for i, b in enumerate(batches)}  # fmt: skip
    return QueueSnapshot(
        repo=REPO, scope=ME, config=QueueConfig(), now=NOW, batches=tuple(batches),
        stages=stages,  # type: ignore[arg-type]
        live=live, approvals={bid: First(p.head) for bid, p in live.items()},
        records=(record,), base=MAIN, hold_read=True, **kw,
    )  # fmt: skip


def _hold(state: str = "open") -> Hold:
    return Hold(state=state, scope=ME, wave=1, parent=MAIN, opened=NOW, refreshed=NOW)  # type: ignore[arg-type]


HALT = {"kind": "queue_halt", "at": AT, "state": "held", "detail": "GH013 push refused",
        "land": "push", "main": MAIN}  # fmt: skip
RETRY = {"kind": "queue_retry", "at": "2026-11-20T11:00:00Z", "detail": "operator"}


def _kinds(plan: QueuePlan) -> list[str]:
    return [a.kind for a in plan.actions]


# ------------------------------------------------------------ the halt's retry (R28)


def test_a_halted_queue_stays_halted_every_pass_and_names_the_retry_verb() -> None:
    batches = [_batch("a", 1)]
    qs = _qs(batches, _record({"kind": "queue_open", "at": AT}, HALT), hold=_hold())
    for _ in range(3):  # nothing the passes do lifts it
        plan = plan_queue(qs)
        assert _kinds(plan) == ["queue-need"]
        assert f"`fr triage batch queue-retry {REPO} --yes`" in plan.actions[0].detail


def test_the_retry_event_lifts_the_halt_and_the_next_pass_builds() -> None:
    batches = [_batch("a", 1)]
    qs = _qs(batches, _record({"kind": "queue_open", "at": AT}, HALT, RETRY), hold=_hold())
    assert "queue-build" in _kinds(plan_queue(qs))


def test_a_halt_after_the_retry_stops_the_queue_again() -> None:
    again = {**HALT, "at": "2026-11-20T11:30:00Z"}
    batches = [_batch("a", 1)]
    qs = _qs(batches, _record({"kind": "queue_open", "at": AT}, HALT, RETRY, again),
             hold=_hold())  # fmt: skip
    assert _kinds(plan_queue(qs)) == ["queue-need"]


# ------------------------------------------------------------ the queue line (R25)


def test_the_queue_line_names_the_wave_the_base_each_entry_what_landed_and_the_hold() -> None:
    batches = [_batch("a", 1), _batch("b", 2), _batch("c", 3, wave=2), _batch("z", 9)]
    stages = {"a": "pr-open", "b": "pr-open", "c": "pr-open", "z": "merged"}
    record = _record(
        {"kind": "queue_open", "at": AT},
        {"kind": "queue_land", "at": AT, "main": MAIN, "entries": [{"batch": "z"}]},
        _built(1, "s1" * 20, "a"),
        _built(2, "s2" * 20, "b", parent="s1" * 20),
    )
    slots = {"s1" * 20: SlotCheck("pending"), "s2" * 20: SlotCheck("green")}
    qs = _qs(batches, record, hold=_hold("open"), slots=slots)
    qs = QueueSnapshot(**{**qs.__dict__, "stages": stages})
    plan = plan_queue(qs)
    line = queue_line(plan)
    assert line.startswith(f"queue {REPO}: open wave 1 on {MAIN[:12]}")
    assert "a testing" in line and "b green" in line and "c waiting" in line
    assert "landed z" in line and line.endswith("hold open")
    assert queue_view(plan, qs=qs).entries[1] == ("b", "green")


def test_the_line_marks_an_ejected_entry_a_barrier_and_a_halt() -> None:
    batches = [_batch("a", 1)]
    record = _record({"kind": "queue_open", "at": AT},
                     {"kind": "queue_eject", "at": AT, "entry": {"batch": "a"}, "reason": "red",
                      "head": "head-a"}, HALT)  # fmt: skip
    qs = _qs(batches, record, hold=_hold())
    line = queue_line(plan_queue(qs))
    assert "halted (held)" in line and "a ejected" in line


# ------------------------------------------------------------ Needs you (R28)


def _board(*record_events: dict[str, Any]) -> tuple[Any, Any]:
    """A repo with one approved open PR whose queue record holds *record_events*."""
    p = pr(11, "feat/batch-a", labels=["approved-fr"])
    f = facts([issue(1, prs=[p])], schema=12, config={REPO_B: {"queue": {"ci": "push"}}})
    jd = judgements({"widgets#1": j(1)}, [mk("a", [1], events=[dispatch("a")])])
    record = QueueRecord.model_validate({
        "repo": REPO_B, "wave": None, "scope": scope_id(f.scope), "base": MAIN,
        "events": list(record_events),
    })  # fmt: skip
    return f, jd.model_copy(update={"queues": [record]})


def test_the_boards_needs_list_a_halted_queue_with_the_command_to_paste() -> None:
    """The Needs read the queue offline, from the judgements' own records and the config the
    facts carry: a halt is a `queue-need` that names the retry verb."""
    f, jd = _board({"kind": "queue_open", "at": AT}, HALT)
    (need,) = [n for n in needs_you(f, jd) if n.kind == "queue-need"]
    assert f"queue-retry {REPO_B} --yes" in need.text and "GH013 push refused" in need.text
    assert "queue-need" in NEED_LABELS
    f, jd = _board({"kind": "queue_open", "at": AT}, HALT, RETRY)
    assert not [n for n in needs_you(f, jd) if n.kind == "queue-need"]


def test_the_board_card_of_a_queued_approved_pr_never_reads_awaiting_approval() -> None:
    f, jd = _board({"kind": "queue_open", "at": AT})
    assert build_board(f, jd, {}).card("a").hint == "in merge queue"


# ------------------------------------------------------------ the wave report (R28)


def test_the_wave_report_lists_landed_ejected_and_deferred_with_cycles_time_and_approvals() -> None:
    from fr.triage.wave_report import render_markdown, wave_report

    def at(minute: int) -> str:
        return f"2026-11-20T10:{minute:02d}:00Z"

    record = _record(
        {"kind": "queue_open", "at": at(0)},
        {**_built(1, "s1" * 20, "a"), "at": at(1)},
        {**_built(2, "s2" * 20, "b", parent="s1" * 20), "at": at(2)},
        {"kind": "queue_eject", "at": at(5), "entry": {"batch": "b"}, "reason": "red",
         "head": "head-b"},
        {**_built(1, "s3" * 20, "a"), "at": at(6)},  # a rebuilt once: two cycles
        {"kind": "queue_land", "at": at(30), "main": "s3" * 20, "entries": [{"batch": "a"}]},
        {"kind": "queue_drain", "at": at(31), "main": "s3" * 20},
        {"kind": "queue_cleared", "at": at(40), "detail": "released v1.2.3"},
    )  # fmt: skip
    batch_a = Batch.model_validate({
        "id": "a", "title": "a", "ids": ["super-fr#1"], "wave": 1,
        "events": [{"kind": "approval", "at": at(1), "pr": 100, "head": "h1"}],
    })  # fmt: skip
    deferred = Batch.model_validate({
        "id": "d", "title": "d", "ids": ["super-fr#4"], "wave": 1,
        "events": [{"kind": "deferred", "at": at(3), "wave": 1}],
    })  # fmt: skip
    (report,) = wave_report([record], [batch_a, deferred])
    by_key = {p.key: p for p in report.prs}
    assert (by_key["a"].outcome, by_key["a"].cycles, by_key["a"].approvals) == ("landed", 2, 1)
    assert by_key["a"].wall is not None and by_key["a"].wall.total_seconds() == 29 * 60
    assert (by_key["b"].outcome, by_key["b"].detail) == ("ejected", "red")
    assert by_key["d"].outcome == "deferred"
    assert report.release.startswith("asked at ") and "released v1.2.3" in report.release
    text = render_markdown([report])
    assert text.startswith("## Wave merge queue report")
    assert "| a | landed | 2 | 29m | 1 |" in text
    assert "Closes" not in text  # `review_reasons` reads only the body's `Closes` lines


def test_an_empty_report_renders_nothing() -> None:
    from fr.triage.wave_report import render_markdown, wave_report

    assert render_markdown(wave_report([_record({"kind": "queue_open", "at": AT})])) == ""


def test_the_closeout_pr_body_carries_the_report_in_a_section_the_close_reader_skips() -> None:
    from fr.triage import batch_closeout as bc

    report = "## Wave merge queue report\n\n| a | landed |\n"
    member = bc.Member(batch="a", branch="feat/batch-a", closes=("o/r#1",), passed=True)
    plain = bc.pr_body([member], [], "o/r")
    body = bc.pr_body([member], [], "o/r", report)
    assert body.startswith(plain) and body.endswith("| a | landed |")
    assert bc.closes_from_body(body) == bc.closes_from_body(plain) == ("o/r#1",)
    assert bc.members_from_body(body) == ("a",)


def test_the_batches_page_shows_the_queue_line_and_the_wave_report() -> None:
    from datetime import UTC, datetime

    from fr.triage.kanban_render import render_board

    f, jd = _board(
        {"kind": "queue_open", "at": AT},
        {"kind": "queue_land", "at": "2026-11-20T10:30:00Z", "main": "a1" * 20,
         "entries": [{"batch": "a"}]},
        {"kind": "queue_drain", "at": "2026-11-20T10:31:00Z", "main": "a1" * 20},
    )  # fmt: skip
    board = build_board(f, jd, {})
    assert board.queue_lines and board.queue_lines[0].startswith(f"queue {REPO_B}:")
    assert "landed a" in board.queue_lines[0]
    html = render_board(board, scope_args=[], rendered_at=datetime(2026, 11, 20, tzinfo=UTC),
                        refresh=0, notes=[])  # fmt: skip
    assert '<section class="queue"><h2>Merge queue</h2>' in html and "landed a" in html
    assert "<th>CI cycles</th>" in html and "Release: asked at " in html


# ------------------------------------------------------------ the PR marker comment (R28)


class _FakeForge:
    """Just the comment surface of `GhClient`, over an in-memory PR thread."""

    def __init__(self) -> None:
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.calls: list[str] = []

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        self.calls.append(f"list {number}")
        return [dict(c) for c in self.comments.get(number, [])]

    def comment_pr(self, repo: str, pr: int, body: str) -> None:
        self.calls.append(f"create {pr}")
        thread = self.comments.setdefault(pr, [])
        thread.append({"id": 1000 + len(thread), "body": body, "author": "bot"})

    def edit_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        self.calls.append(f"edit {comment_id}")
        for thread in self.comments.values():
            for c in thread:
                if c["id"] == comment_id:
                    c["body"] = body


def _qs_view(record: QueueRecord, batches: Sequence[Batch], **kw: Any) -> QueuePlan:
    return plan_queue(_qs(batches, record, hold=_hold(), **kw))


def _states(record: QueueRecord, batches: Sequence[Batch], **kw: Any) -> list[Any]:
    from fr.triage.queue_comment import entry_comments

    qs = _qs(batches, record, hold=_hold(), **kw)
    return entry_comments(plan_queue(qs), record, {b.id: 100 + i for i, b in enumerate(batches)})


def test_the_marker_comment_is_created_once_and_edited_in_place_through_every_state() -> None:
    from fr.triage.queue_comment import MARKER, sync

    forge = _FakeForge()
    batches = [_batch("a", 1), _batch("b", 2)]
    queued = _record({"kind": "queue_open", "at": AT})
    testing = _record({"kind": "queue_open", "at": AT}, _built(1, "s1" * 20, "a"))
    ejected = _record(
        {"kind": "queue_open", "at": AT}, _built(1, "s1" * 20, "a"),
        {"kind": "queue_eject", "at": AT, "entry": {"batch": "a"}, "reason": "red",
         "head": "head-a"},
    )  # fmt: skip
    landed = _record(
        {"kind": "queue_open", "at": AT}, _built(1, "s1" * 20, "a"),
        {"kind": "queue_land", "at": AT, "main": "s1" * 20, "entries": [{"batch": "a"}]},
    )  # fmt: skip
    seen: list[str] = []
    for record in (queued, testing, ejected, landed):
        cs = [c for c in _states(record, batches) if c.key == "a"]
        assert len(cs) == 1 and cs[0].body.startswith(MARKER)
        seen.append(cs[0].body)
        sync(forge, REPO, cs, allowed=True, trusted=TRUSTED)
    assert "queued at position 1" in seen[0]
    assert "testing in combination s1s1s1s1s1s1" in seen[1]
    assert "ejected (red)" in seen[2] and "re-enters the queue" in seen[2]
    assert "landed at s1s1s1s1s1s1 (wave 1)" in seen[3]
    # one comment on PR 100, created once and edited three times, never a second one
    assert (
        forge.calls.count("create 100") == 1 and sum(c.startswith("edit") for c in forge.calls) == 3
    )
    assert len(forge.comments[100]) == 1 and "landed at" in forge.comments[100][0]["body"]


def test_an_unchanged_comment_costs_no_write_and_forge_comments_off_writes_nothing() -> None:
    from fr.triage.queue_comment import sync

    forge = _FakeForge()
    cs = [c for c in _states(_record({"kind": "queue_open", "at": AT}), [_batch("a", 1)])]
    assert len(sync(forge, REPO, cs, allowed=True, trusted=TRUSTED)) == 1
    assert (
        sync(forge, REPO, cs, allowed=True, trusted=TRUSTED) == []
    )  # reads, finds the same body, writes none
    assert forge.calls == ["list 100", "create 100", "list 100"]
    off = _FakeForge()
    assert (
        sync(off, REPO, cs, allowed=False, trusted=TRUSTED) == []
        and off.calls == []
        and off.comments == {}
    )


def test_a_comment_that_fails_to_write_is_said_and_never_stops_the_pass() -> None:
    from fr.triage.queue_comment import sync

    class Refusing(_FakeForge):
        def comment_pr(self, repo: str, pr: int, body: str) -> None:
            raise RuntimeError("HTTP 403")

    said: list[str] = []
    cs = _states(_record({"kind": "queue_open", "at": AT}), [_batch("a", 1), _batch("b", 2)])
    assert sync(Refusing(), REPO, cs, allowed=True, trusted=TRUSTED, say=said.append) == []
    assert len(said) == 2 and "HTTP 403" in said[0]


def test_a_marker_a_stranger_planted_first_is_never_edited_nor_taken_for_ours() -> None:
    from fr.triage.queue_comment import MARKER, sync

    forge = _FakeForge()
    forge.comments[100] = [
        {"id": 7, "body": f"{MARKER}\nforged", "author": "mallory", "association": "NONE"}
    ]
    cs = [c for c in _states(_record({"kind": "queue_open", "at": AT}), [_batch("a", 1)])]
    sync(forge, REPO, cs, allowed=True, trusted=TRUSTED)
    assert forge.comments[100][0]["body"].endswith("forged")  # untouched
    assert (
        len(forge.comments[100]) == 2 and "queued at position 1" in forge.comments[100][1]["body"]
    )
    sync(forge, REPO, cs, allowed=True, trusted=TRUSTED)
    assert "edit 7" not in forge.calls and len(forge.comments[100]) == 2


def test_a_waiting_pr_gets_no_comment_and_the_position_counts_entries_in_testing() -> None:
    batches = [_batch("a", 1), _batch("b", 2), _batch("c", 3, wave=2)]
    rec = _record({"kind": "queue_open", "at": AT}, _built(1, "s1" * 20, "a"))
    cs = {c.key: c.body for c in _states(rec, batches)}
    assert "c" not in cs  # it waits on a later queue: it is no entry
    assert "testing in combination" in cs["a"]
    assert "queued at position 2" in cs["b"]  # a, in testing, is position 1


def test_the_comment_reads_the_passes_own_view_so_it_agrees_with_the_pass_line() -> None:
    batches = [_batch("a", 1)]
    rec = _record({"kind": "queue_open", "at": AT}, _built(1, "s1" * 20, "a"))
    plan = _qs_view(rec, batches, slots={"s1" * 20: SlotCheck(verdict="failing")})
    from fr.triage.queue_comment import entry_comments

    (c,) = entry_comments(plan, rec, {"a": 100})
    assert plan.view is not None and plan.view.entries == (("a", "ejected"),)
    assert "a ejected" in queue_line(plan) and "ejected (red)" in c.body


def test_a_pr_that_leaves_the_queue_is_told_so_once() -> None:
    from fr.triage.queue_comment import CommentBook, sync

    forge = _FakeForge()
    book = CommentBook(REPO)
    rec = _record({"kind": "queue_open", "at": AT})
    batches = [_batch("a", 1)]
    plan = _qs_view(rec, batches)
    cs = book.comments(plan, rec, [rec], {"a": 100}, {})
    sync(forge, REPO, cs, allowed=True, trusted=TRUSTED, seen=book.seen)
    assert "queued at position 1" in forge.comments[100][0]["body"]
    cs = book.comments(plan, rec, [rec], {"a": 100}, {"a": "deferred by the operator"})
    sync(forge, REPO, cs, allowed=True, trusted=TRUSTED, seen=book.seen)
    assert "left the queue (deferred by the operator)" in forge.comments[100][0]["body"]
    before = list(forge.calls)
    cs = book.comments(plan, rec, [rec], {"a": 100}, {"a": "deferred by the operator"})
    assert sync(forge, REPO, cs, allowed=True, trusted=TRUSTED, seen=book.seen) == []
    assert forge.calls == before  # said once: no read, no write


def test_a_landed_comment_that_failed_to_write_is_retried_until_it_lands() -> None:
    from fr.triage.queue_comment import CommentBook, sync

    class Flaky(_FakeForge):
        fail = True

        def comment_pr(self, repo: str, pr: int, body: str) -> None:
            if self.fail and "landed at" in body:
                raise RuntimeError("HTTP 502")
            super().comment_pr(repo, pr, body)

    forge, book, said = Flaky(), CommentBook(REPO), []
    rec = _record(
        {"kind": "queue_open", "at": AT}, _built(1, "s1" * 20, "a"),
        {"kind": "queue_land", "at": AT, "main": "s1" * 20, "entries": [{"batch": "a"}]},
    )  # fmt: skip
    plan = _qs_view(rec, [_batch("a", 1)])
    cs = book.comments(plan, rec, [rec], {"a": 100}, {})  # the pass it landed in: PR still live
    sync(forge, REPO, cs, allowed=True, trusted=TRUSTED, seen=book.seen, say=said.append)
    assert said and forge.comments == {}
    forge.fail = False
    cs = book.comments(plan, rec, [rec], {}, {})  # next pass: the merged PR is no live PR
    sync(forge, REPO, cs, allowed=True, trusted=TRUSTED, seen=book.seen, say=said.append)
    assert "landed at" in forge.comments[100][0]["body"]


# ------------------------------------------------------------ the driver writes it (R28)


def _drive_twice(world: Any, tmp_path: Any) -> tuple[int, str]:
    """Two passes over one approved PR: the first opens the queue (the test's executor runs
    none of it, so the record is written by hand), the second has the PR as an entry."""
    from fr.commands.triage_batch_cmd import queue_writer
    from fr.commands.triage_cmd import _scope
    from fr.triage.model import QueueOpenEvent

    from tests.unit.test_triage_batch_drive_cmd import REPO as DRIVE_REPO
    from tests.unit.test_triage_batch_drive_cmd import _drive, _pr_open

    world.config = {"queue": {"ci": "push"}}
    _pr_open(world, tmp_path)
    assert _drive(tmp_path, "--once", "--yes")[0] in (0, 1, 3)
    sid = scope_id(_scope(DRIVE_REPO, None))
    queue_writer(tmp_path, DRIVE_REPO, sid)(
        QueueOpenEvent(kind="queue_open", at=NOW), wave=1, base=MAIN
    )
    return _drive(tmp_path, "--once", "--yes")


def _marker_bodies(world: Any) -> list[str]:
    return [c["body"] for c in world.comments.get(101, []) if c["body"].startswith("<!-- fr-queue")]


def test_the_driver_posts_one_marker_comment_a_queued_pr_and_edits_it_on_the_next_pass(
    tmp_path: Any, world: Any, checkout: Any, runner: Any
) -> None:
    from tests.unit.test_triage_batch_drive_cmd import _drive

    code, out = _drive_twice(world, tmp_path)
    assert code in (0, 3), out
    bodies = _marker_bodies(world)
    assert len(bodies) == 1 and "queued at position 1" in bodies[0]
    code, out = _drive(tmp_path, "--once", "--yes")  # nothing moved: no second comment
    assert code in (0, 3), out
    assert world.calls.count("comment_pr 101") == 1 and len(_marker_bodies(world)) == 1


def test_forge_comments_off_posts_no_queue_comment(
    tmp_path: Any, world: Any, checkout: Any, runner: Any
) -> None:
    world.files[".fr/settings.yaml"] = "forge:\n  comments: 'off'\n"
    _drive_twice(world, tmp_path)
    assert _marker_bodies(world) == [] and "comment_pr 101" not in world.calls
