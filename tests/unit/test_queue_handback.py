"""Tests for `fr.triage.queue_handback` (spec 2026-11-24-wave-queue-gaps R1-R6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fr.triage import queue_handback
from fr.triage.handback_rules import conflict_decision, handbacks_since, spends_handback
from fr.triage.model import ConflictEvent, DispatchEvent
from fr.triage.queue_handback import brief_mode, reissue_due, stack_target
from fr.triage.wave_queue import Combo, QueueConfig, Replay


def test_the_module_names_its_spec() -> None:
    assert "2026-11-24-wave-queue-gaps" in (queue_handback.__doc__ or "")
    assert "R1-R6" in (queue_handback.__doc__ or "")


# ------------------------------------------------- the stack target and the mode (R1)


AT = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
BASE = "b" * 40
S1 = "1" * 40
S2 = "2" * 40
H = "h" * 40


def _rep(*combos: Combo, base: str = BASE, ejected: dict[str, str] | None = None) -> Replay:
    return Replay(base, {c.slot: c for c in combos}, (), frozenset(), ejected or {}, {}, {})


def _combo(slot: int, sha: str, parent: str, chain: tuple[str, ...], base: str = BASE) -> Combo:
    return Combo(slot, sha, parent, chain, tuple("x" * 40 for _ in chain), base)


def test_the_stack_target_is_the_last_standing_combination() -> None:
    rep = _rep(_combo(1, S1, BASE, ("a",)), _combo(2, S2, S1, ("a", "b")))

    assert stack_target(rep) == (S2, 2)


def test_the_stack_target_is_the_base_when_no_combination_stands() -> None:
    assert stack_target(_rep()) == (BASE, None)


def test_a_combination_holding_an_ejected_entry_or_on_another_base_does_not_stand() -> None:
    rep = _rep(
        _combo(1, S1, BASE, ("a",)),
        _combo(2, S2, S1, ("a", "b")),
        ejected={"b": H},
    )
    assert stack_target(rep) == (S1, 1)
    stale = _rep(_combo(1, S1, "o" * 40, ("a",), base="o" * 40))
    assert stack_target(stale) == (BASE, None)


@pytest.mark.parametrize(
    ("land", "method", "mode"),
    [
        ("push", "merge", "slot"),
        ("push", "squash", "slot"),
        ("push", "rebase", "main"),
        ("merge", "merge", "main"),
        ("merge", "squash", "main"),
        ("push", "", "main"),
    ],
)
def test_the_brief_names_the_slot_only_under_push_with_merge_or_squash(
    land: str, method: str, mode: str
) -> None:
    assert brief_mode(QueueConfig(land=land), method) == mode  # type: ignore[arg-type]


# ------------------------------------------------- the lineage-aware skip (R2, R3)


def _conflict(head: str, *, onto: str | None = None, reissue: bool = False,
              at: datetime = AT, delivered: str = "session") -> ConflictEvent:  # fmt: skip
    return ConflictEvent(
        kind="conflict",
        at=at,
        head=head,
        paths=["a.py"],
        delivered=delivered,
        onto=onto,
        reissue=reissue,
    )  # type: ignore[arg-type]


def _dispatch() -> DispatchEvent:
    return DispatchEvent(kind="dispatch", at=AT - timedelta(hours=1), runner="fake", handle="h",
                         branch="feat/batch-b1")  # fmt: skip


def test_a_head_whose_onto_still_leads_is_skipped() -> None:
    events = [_dispatch(), _conflict(H, onto=S1)]

    assert not reissue_due(events, H, True)
    assert conflict_decision(events, H, ["a.py"], [], leads=True).kind == "skip"


def test_a_head_whose_onto_no_longer_leads_is_reissued() -> None:
    events = [_dispatch(), _conflict(H, onto=S1)]

    assert reissue_due(events, H, False)
    assert conflict_decision(events, H, ["a.py"], [], leads=False).kind == "reissue"


@pytest.mark.parametrize("leads", [True, False, None])
def test_a_head_whose_event_names_no_onto_is_skipped_as_today(leads: bool | None) -> None:
    events = [_dispatch(), _conflict(H)]

    assert not reissue_due(events, H, leads)
    assert conflict_decision(events, H, ["a.py"], [], leads=leads).kind == "skip"


def test_an_unreadable_lead_reissues_nothing() -> None:
    events = [_dispatch(), _conflict(H, onto=S1)]

    assert not reissue_due(events, H, None)
    assert conflict_decision(events, H, ["a.py"], [], leads=None).kind == "skip"


def test_the_latest_event_at_the_head_decides() -> None:
    events = [
        _dispatch(),
        _conflict(H, onto=S1),
        _conflict(H, onto=S2, reissue=True, at=AT + timedelta(minutes=1)),
    ]
    assert reissue_due(events, H, False)
    assert not reissue_due(events, "o" * 40, False)


def test_reissues_spend_no_handback() -> None:
    later = AT + timedelta(minutes=1)
    events = [
        _dispatch(),
        _conflict(H, onto=S1),
        _conflict(H, onto=S2, reissue=True, at=later),
        _conflict(H, onto=BASE, reissue=True, at=later + timedelta(minutes=1)),
    ]

    assert handbacks_since(events, spends_handback) == 1
    assert conflict_decision(events, "n" * 40, ["a.py"], []).kind == "handback"


# ------------------------------------------------- the conflict brief (R1)


def _batch() -> object:
    from fr.triage.model import Batch

    return Batch.model_validate({"id": "b1", "title": "Fix it", "ids": ["super-fr#1"]})


def _brief(**over: object) -> str:
    from fr.triage.queue_handback import conflict_brief

    kw: dict[str, object] = {
        "pr": 101, "head": "sha-101", "paths": ("src/a.py",), "branch": "feat/batch-b1",
        "base": "origin/main", "mirrors": (), **over,
    }  # fmt: skip
    return conflict_brief(_batch(), **kw)  # type: ignore[arg-type]


def test_the_slot_brief_fetches_the_slot_and_merges_its_sha() -> None:
    text = _brief(onto=S2, onto_ref="fr-queue/derio-net/slot-2")

    assert "git fetch origin fr-queue/derio-net/slot-2" in text
    assert f"git merge {S2}" in text
    assert "git merge origin/main" not in text
    assert "what `main` becomes when the entries ahead" in text
    assert "stop and wait for a re-issued brief" in text
    assert text.startswith("Merge conflict on batch b1: ")
    assert "head sha-101, conflicts with" in text  # fr-herdr reads the head from this


def test_the_main_brief_reads_as_today() -> None:
    today = _brief()

    assert _brief(onto=BASE, onto_ref="origin/main") == today
    assert "git fetch origin && git merge origin/main" in today
    assert "re-issued" not in today


def test_conflict_brief_is_still_importable_from_batch_dispatch() -> None:
    from fr.triage import batch_dispatch, queue_handback

    assert batch_dispatch.conflict_brief is queue_handback.conflict_brief
