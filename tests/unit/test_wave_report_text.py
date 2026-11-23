"""The close-out PR body's wave report (spec 2026-11-19-wave-merge-queue R28, §L): which queue
records it reads, and that it lists the close-out itself. Real records, no literal body."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fr.commands.triage_batch_cmd import _wave_report_text
from fr.commands.triage_cmd import _scope
from fr.triage.model import Judgements, RequeuedEvent, load_judgements
from fr.triage.scope_config import scope_id

from tests.unit.test_triage_batch_leave_wave import REPO, _state

AT = "2026-11-20T10:00:00Z"


def _queue(wave: int | None, *landed: str, scope: str | None = None) -> dict[str, Any]:
    events: list[dict[str, Any]] = [{"kind": "queue_open", "at": AT}]
    for bid in landed:
        events.append({"kind": "queue_land", "at": AT, "main": "c" * 40,
                       "entries": [{"batch": bid}]})  # fmt: skip
    rec: dict[str, Any] = {"repo": REPO, "wave": wave, "base": "b" * 40, "events": events}
    if scope is not None:
        rec["scope"] = scope
    return rec


def _judgements(tmp_path: Path, queues: list[dict[str, Any]], *, requeue: bool = False) -> Any:
    _state(tmp_path, queues)
    j = load_judgements(tmp_path / "judgements.yaml")
    _requeued = RequeuedEvent(kind="requeued", at=AT, wave=3)
    if requeue:  # a: wave 1 by its own, requeued into wave 3
        batches = [
            b.model_copy(update={"events": [*b.events, _requeued]}) if b.id == "a" else b
            for b in j.batches
        ]
        j = j.model_copy(update={"batches": batches})
    return j


def _text(j: Judgements, *ids: str) -> str:
    return _wave_report_text(j, REPO, [SimpleNamespace(batch=i) for i in ids],
                             scope=scope_id(_scope(REPO, None)))  # fmt: skip


def test_the_report_reads_the_members_effective_wave_not_their_own(tmp_path: Path) -> None:
    j = _judgements(tmp_path, [_queue(1, "a"), _queue(3, "a")], requeue=True)
    text = _text(j, "a")
    assert "wave 3" in text and "wave 1" not in text


def test_the_report_reads_this_scopes_records_only(tmp_path: Path) -> None:
    j = _judgements(tmp_path, [_queue(1, "a")])
    foreign = j.queues[0].model_copy(update={"scope": "s-99999999"})
    j = j.model_copy(update={"queues": [foreign, *j.queues]})
    assert _text(j, "a").count("| a | landed") == 1


def test_a_member_between_waves_selects_only_the_record_that_names_it(tmp_path: Path) -> None:
    j = _judgements(tmp_path, [_queue(None, "m"), _queue(None, "a")])
    text = _text(j, "a")  # `a` has a wave, so none of the between-waves records is its own
    assert "between waves" not in text
    j2 = _judgements(tmp_path, [_queue(None, "m"), _queue(None, "q")])
    j2 = j2.model_copy(update={"batches": [
        b.model_copy(update={"wave": None}) if b.id == "a" else b for b in j2.batches
    ]})  # fmt: skip
    assert _text(j2, "a") == ""  # no between-waves record names it
    j3 = _judgements(tmp_path, [_queue(None, "m"), _queue(None, "a")])
    j3 = j3.model_copy(update={"batches": [
        b.model_copy(update={"wave": None}) if b.id == "a" else b for b in j3.batches
    ]})  # fmt: skip
    text = _text(j3, "a")
    assert "| a | landed" in text and "| m |" not in text


def test_the_report_lists_the_close_out_itself_as_queued(tmp_path: Path) -> None:
    j = _judgements(tmp_path, [_queue(1, "a")])
    text = _wave_report_text(
        j, REPO, [SimpleNamespace(batch="a")], scope=scope_id(_scope(REPO, None))
    )
    assert "| a | landed" in text and "| closeout | queued" in text


def test_a_pr_ejected_then_deferred_is_listed_once_as_deferred(tmp_path: Path) -> None:
    from fr.triage.model import DeferredEvent
    from fr.triage.wave_report import wave_report

    queue = _queue(1)
    queue["events"] += [
        {"kind": "queue_eject", "at": "2026-11-20T10:30:00Z", "entry": {"batch": "a"},
         "reason": "red", "head": "h"},
    ]  # fmt: skip
    j = _judgements(tmp_path, [queue])
    late = DeferredEvent(kind="deferred", at="2026-11-20T11:00:00Z", wave=1)  # type: ignore[arg-type]
    early = DeferredEvent(kind="deferred", at="2026-11-20T10:10:00Z", wave=1)  # type: ignore[arg-type]
    for event, outcome in ((late, "deferred"), (early, "ejected")):  # the last state wins
        batches = [
            b.model_copy(update={"events": [*b.events, event]}) if b.id == "a" else b
            for b in j.batches
        ]
        (report,) = wave_report(j.queues, batches)
        assert [(p.key, p.outcome) for p in report.prs] == [("a", outcome)]
