"""`fr triage batch defer`, `requeue` and `queue-retry` (spec 2026-11-19-wave-merge-queue R28,
R29). Every state directory is tmp_path; no forge is touched."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fr.cli import app
from fr.commands.triage_cmd import _scope
from fr.triage.model import (
    DeferredEvent,
    Facts,
    Issue,
    QueueRetryEvent,
    RequeuedEvent,
    load_judgements,
)
from fr.triage.scope_config import scope_id
from fr.triage.wave_queue import effective_wave, halted_queue, is_deferred
from typer.testing import CliRunner

REPO = "derio-net/super-fr"
FACTS_SCOPE = "derio-net--super-fr"

QUEUE_OPEN = {"repo": REPO, "wave": 2, "base": "b" * 40,
              "events": [{"kind": "queue_open", "at": "2026-11-20T10:00:00Z"}]}  # fmt: skip
HALT = {"kind": "queue_halt", "at": "2026-11-20T10:05:00Z", "state": "held",
        "detail": "GH013 push refused", "land": "push", "main": "b" * 40}  # fmt: skip


def _facts() -> Facts:
    return Facts(
        viewer="operator", schema=3, scope=FACTS_SCOPE, kind="repo",
        collected_at="2026-11-20T12:00:00+00:00", repos=[REPO],
        issues=[Issue(repo=REPO, number=n, title=f"issue {n}", state="open",
                      url=f"https://github.com/{REPO}/issues/{n}", author_association="OWNER")
                for n in (1, 2)],
        prs=[], config={},
    )  # fmt: skip


def _state(tmp_path: Path, queues: list[dict[str, Any]] | None = None) -> Path:
    doc: dict[str, Any] = {
        "schema": 13,
        "tiers": [{"n": 1, "title": "Now"}],
        "issues": {"super-fr#1": {"tier": 1}, "super-fr#2": {"tier": 1}},
        "batches": [
            {"id": "a", "title": "A", "ids": ["super-fr#1"], "wave": 1,
             "events": [{"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake",
                         "handle": "h", "branch": "feat/batch-a"}]},
            {"id": "m", "title": "M", "ids": ["super-fr#2"], "wave": 2,
             "events": [{"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake",
                         "handle": "h", "branch": "feat/batch-m"},
                        {"kind": "cancel", "at": "2026-11-20T09:30:00Z", "reason": "x"}]},
        ],
    }  # fmt: skip
    if queues:  # this host's id for the scope, read when the test runs (the suite fakes it)
        doc["queues"] = [{**q, "scope": scope_id(_scope(REPO, None))} for q in queues]
    (tmp_path / "judgements.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), "utf-8")
    (tmp_path / "facts.json").write_text(json.dumps(_facts().to_json()), "utf-8")
    return tmp_path


def _run(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, " ".join(result.output.split())


def _batch(tmp_path: Path, bid: str) -> Any:
    return next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == bid)


# ------------------------------------------------------------------ defer


def test_defer_writes_a_deferred_event_naming_the_wave_and_says_what_it_changed(
    tmp_path: Path,
) -> None:
    _state(tmp_path)
    code, out = _run(tmp_path, "defer", "a")
    assert code == 0, out
    assert "deferred batch a" in out and "out of wave 1" in out and "PR stays open" in out
    batch = _batch(tmp_path, "a")
    event = batch.events[-1]
    assert isinstance(event, DeferredEvent) and event.wave == 1
    assert is_deferred(batch)  # the planner now reads it as terminal for the drain


def test_defer_refuses_a_deferred_batch_and_a_closed_out_one(tmp_path: Path) -> None:
    _state(tmp_path)
    assert _run(tmp_path, "defer", "a")[0] == 0
    code, out = _run(tmp_path, "defer", "a")
    assert code == 2 and "already deferred" in out
    code, out = _run(tmp_path, "defer", "m")
    assert code == 2 and "nothing to defer" in out


# ------------------------------------------------------------------ requeue


def test_requeue_into_a_wave_writes_requeued_and_moves_the_effective_wave(tmp_path: Path) -> None:
    _state(tmp_path)
    assert _run(tmp_path, "defer", "a")[0] == 0
    code, out = _run(tmp_path, "requeue", "a", "--wave", "3")
    assert code == 0, out
    assert "requeued batch a" in out and "wave 3's queue" in out
    batch = _batch(tmp_path, "a")
    assert isinstance(batch.events[-1], RequeuedEvent) and batch.events[-1].wave == 3
    assert effective_wave(batch) == 3 and not is_deferred(batch)


def _opened(wave: int, *, drained: bool = False) -> dict[str, Any]:
    events = [{"kind": "queue_open", "at": "2026-11-20T10:00:00Z"}]
    if drained:
        events.append({"kind": "queue_drain", "at": "2026-11-20T11:00:00Z"})
    return {**QUEUE_OPEN, "wave": wave, "events": events}


def test_plain_requeue_joins_the_lowest_wave_whose_queue_has_not_opened(tmp_path: Path) -> None:
    _state(tmp_path, [_opened(1, drained=True)])  # wave 1 opened and drained; wave 2 has not
    assert _run(tmp_path, "defer", "a")[0] == 0
    code, out = _run(tmp_path, "requeue", "a")
    assert code == 0, out
    assert "wave 2's queue" in out and "next queue to open" in out
    assert effective_wave(_batch(tmp_path, "a")) == 2


def test_plain_requeue_with_every_wave_opened_is_a_between_waves_entry(tmp_path: Path) -> None:
    _state(tmp_path, [_opened(1, drained=True), _opened(2)])
    assert _run(tmp_path, "defer", "a")[0] == 0
    code, out = _run(tmp_path, "requeue", "a")
    assert code == 0, out
    assert "between-waves queue" in out and "next queue to open" in out
    assert effective_wave(_batch(tmp_path, "a")) is None


def test_requeue_to_a_wave_is_refused_once_its_queue_has_opened_even_if_drained(
    tmp_path: Path,
) -> None:
    for drained in (False, True):
        _state(tmp_path, [_opened(2, drained=drained)])
        code, out = _run(tmp_path, "requeue", "a", "--wave", "2")
        assert code == 2 and "queue for wave 2 has opened" in out
        assert _batch(tmp_path, "a").events[-1].kind == "dispatch"  # nothing written
    _state(tmp_path, [_opened(1, drained=True)])  # an unopened wave above the batch's own
    assert _run(tmp_path, "requeue", "a", "--wave", "2")[0] == 0


def test_requeue_to_a_wave_not_above_the_batchs_effective_wave_is_refused(tmp_path: Path) -> None:
    _state(tmp_path)
    assert _run(tmp_path, "defer", "a")[0] == 0
    for n in ("1", "0"):
        code, out = _run(tmp_path, "requeue", "a", "--wave", n)
        assert code == 2 and "above its wave 1" in out
    assert _batch(tmp_path, "a").events[-1].kind == "deferred"  # nothing written


# ------------------------------------------------------------------ queue-retry


def test_queue_retry_prints_the_plan_and_writes_only_with_yes(tmp_path: Path) -> None:
    record = {**QUEUE_OPEN, "events": [*QUEUE_OPEN["events"], HALT]}
    _state(tmp_path, [record])
    code, out = _run(tmp_path, "queue-retry", REPO)
    assert code == 0 and "GH013 push refused" in out and "nothing written" in out, out
    assert halted_queue(load_judgements(tmp_path / "judgements.yaml").queues[-1]) is not None
    code, out = _run(tmp_path, "queue-retry", REPO, "--yes")
    assert code == 0 and "retried 1" in out
    queues = load_judgements(tmp_path / "judgements.yaml").queues
    assert isinstance(queues[-1].events[-1], QueueRetryEvent)
    assert halted_queue(queues[-1]) is None
    code, out = _run(tmp_path, "queue-retry", REPO, "--yes")  # nothing halted any more
    assert code == 1 and "no halted merge queue" in out


def test_queue_retry_without_a_halted_queue_refuses(tmp_path: Path) -> None:
    _state(tmp_path, [QUEUE_OPEN])
    code, out = _run(tmp_path, "queue-retry", "--yes")
    assert code == 1 and "no halted merge queue" in out
