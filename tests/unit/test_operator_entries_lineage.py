"""`fr.triage.operator_entries.lineage_reads` over a fake driver and clone (spec
2026-11-24-wave-queue-gaps §A, R1, R4, R5; review p1-r4, p1-r7).

The read decides which repos are asked (R1's land and method), which commits count as built
(every `queue_built` of this scope's records for the repo), the target (the last standing
combination, or `main` when the record's base is stale), caches each answer per
(sha, target), and never caches a `GitError` (R5).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fr.triage.batch_drive import LivePr
from fr.triage.gitseam import GitError
from fr.triage.model import Batch, QueueBlock, QueueRecord
from fr.triage.operator_entries import lineage_reads

REPO = "derio-net/super-fr"
AT = "2026-11-24T12:00:00Z"
MAIN = "m" * 40
S1, S2, OLD = "1" * 40, "2" * 40, "0" * 40
ONTO = "o" * 40


class Clone:
    def __init__(self) -> None:
        self.asked: list[tuple[str, str, str, frozenset[str]]] = []
        self.carry: dict[str, tuple[str, ...]] = {}
        self.lead: dict[str, bool] = {}
        self.broken: set[str] = set()

    def carried(self, head: str, target: str, built: Any) -> tuple[str, ...]:
        self.asked.append(("carried", head, target, frozenset(built)))
        if head in self.broken:
            raise GitError("bad object")
        return self.carry.get(head, ())

    def leads(self, onto: str, target: str) -> bool:
        self.asked.append(("leads", onto, target, frozenset()))
        if onto in self.broken:
            raise GitError("bad object")
        return self.lead.get(onto, True)


class Driver:
    def __init__(self, records: list[QueueRecord], *, land: str = "push",
                 method: str = "squash") -> None:  # fmt: skip
        self.records, self.land, self.method, self.clone = records, land, method, Clone()

    def _queue_block(self, facts: Any, repo: str) -> QueueBlock:
        return QueueBlock(ci="push", land=self.land)  # type: ignore[arg-type]

    def _queue_records(self, judgements: Any, repo: str) -> list[QueueRecord]:
        return self.records

    def _queue_refusal(self, facts: Any, repo: str) -> str | None:
        return None

    def _ctx_or_hold(self, facts: Any, repo: str) -> Any:
        return SimpleNamespace(method=self.method)

    def _fetched_reader(self, repo: str) -> Clone:
        return self.clone


def _built(slot: int, sha: str, bid: str, base: str = MAIN) -> dict[str, Any]:
    return {"kind": "queue_built", "at": AT, "slot": slot, "sha": sha, "entry": {"batch": bid},
            "head": f"head-{bid}", "patch_id": "p", "base": base, "parent": base}  # fmt: skip


def _record(*events: dict[str, Any], base: str = MAIN, wave: int = 1) -> QueueRecord:
    return QueueRecord.model_validate({"repo": REPO, "wave": wave, "scope": "me", "base": base,
                                       "events": [{"kind": "queue_open", "at": AT},
                                                  *events]})  # fmt: skip


def _judgements(onto: str | None = None) -> Any:
    events = [] if onto is None else [{"kind": "conflict", "at": AT, "head": "head-b",
                                        "paths": ["x.py"], "delivered": "session",
                                        "handle": "h", "onto": onto}]  # fmt: skip
    batch = Batch.model_validate({"id": "b", "title": "b", "ids": ["super-fr#2"],
                                  "events": events})  # fmt: skip
    return SimpleNamespace(batches=[batch])  # `lineage_reads` reads only the batches


def _facts(*others: tuple[int, str]) -> Any:
    prs = [SimpleNamespace(repo=REPO, state="OPEN", head_oid=h, number=n) for n, h in others]
    return SimpleNamespace(prs=prs)


LIVE = {"b": LivePr(number=101, state="OPEN", draft=False, head="head-b", checks="green")}


def _read(driver: Driver, *, onto: str | None = None, base: str = MAIN, facts: Any = None,
          live: dict[str, LivePr] | None = None) -> dict[str, Any]:  # fmt: skip
    return lineage_reads(driver, facts or _facts(), _judgements(onto), {"b": REPO},
                         LIVE if live is None else live, {REPO: base}, ())  # fmt: skip


@pytest.mark.parametrize(("land", "method"), [("merge", "squash"), ("push", "rebase")])
def test_outside_push_with_merge_or_squash_nothing_is_asked(land: str, method: str) -> None:
    driver = Driver([_record(_built(1, S1, "a"))], land=land, method=method)
    out = _read(driver, onto=ONTO)
    assert driver.clone.asked == []
    assert REPO not in out["queue_carries"] and REPO not in out["queue_leads"]
    assert out["queue_methods"].get(REPO, method) == method


def test_the_built_set_is_every_record_of_the_scope_and_the_target_the_last_standing() -> None:
    old = _record(_built(1, OLD, "z"), wave=1)
    driver = Driver([old, _record(_built(1, S1, "a"), _built(2, S2, "c"))])
    driver.clone.carry["head-b"] = (OLD,)
    driver.clone.lead[ONTO] = False
    out = _read(driver, onto=ONTO)
    assert out["queue_methods"] == {REPO: "squash"}
    assert out["queue_carries"][REPO] == {"b": (OLD,)}
    assert out["queue_leads"][REPO] == {"b": False}
    ((_, _, target, built), (_, onto, ltarget, _)) = driver.clone.asked
    assert (target, built) == (S2, frozenset({OLD, S1, S2}))
    assert (onto, ltarget) == (ONTO, S2)


def test_a_stale_record_base_targets_main_now() -> None:
    driver = Driver([_record(_built(1, S1, "a", base=OLD), base=OLD)])
    _read(driver, base=MAIN)
    assert {t for _, _, t, _ in driver.clone.asked} == {MAIN}


def test_each_answer_is_cached_per_sha_and_target() -> None:
    driver = Driver([_record(_built(1, S1, "a"))])
    _read(driver, onto=ONTO)
    _read(driver, onto=ONTO)
    assert len(driver.clone.asked) == 2  # one carried, one leads: the second pass is cached
    driver.records = [_record(_built(1, S1, "a"), _built(2, S2, "c"))]  # the target moved
    _read(driver, onto=ONTO)
    assert len(driver.clone.asked) == 4


def test_a_git_error_is_none_and_never_cached() -> None:
    driver = Driver([_record(_built(1, S1, "a"))])
    driver.clone.broken = {"head-b", ONTO}
    out = _read(driver, onto=ONTO)
    assert out["queue_carries"][REPO] == {"b": None}
    assert out["queue_leads"][REPO] == {"b": None}
    driver.clone.broken = set()
    again = _read(driver, onto=ONTO)
    assert again["queue_carries"][REPO] == {"b": ()} and again["queue_leads"][REPO] == {"b": True}


def test_a_closed_or_headless_pr_and_no_onto_ask_nothing() -> None:
    driver = Driver([_record(_built(1, S1, "a"))])
    closed = {"b": LivePr(number=101, state="MERGED", draft=False, head="head-b", checks="green")}
    assert _read(driver, live=closed)["queue_carries"][REPO] == {}
    out = _read(driver)  # no conflict event: no onto to ask about
    assert out["queue_leads"][REPO] == {} and out["queue_carries"][REPO] == {"b": ()}


def test_a_non_batch_prs_head_is_read_by_head() -> None:  # p1-r4
    driver = Driver([_record(_built(1, S1, "a"))])
    driver.clone.carry["head-hk"] = (OLD,)
    driver.clone.broken = {"head-x"}
    out = _read(driver, facts=_facts((101, "head-b"), (7, "head-hk"), (8, "head-x")))
    assert out["queue_head_carries"][REPO] == {"head-hk": (OLD,), "head-x": None}


def test_an_admitted_entry_takes_its_carry_by_the_head_it_is_built_at() -> None:  # p1-r4
    from fr.triage.batch_drive import Admitted, _carries

    hk = LivePr(number=7, state="OPEN", draft=False, head="head-hk", checks="green")
    other = LivePr(number=8, state="OPEN", draft=False, head="unread", checks="green")
    snap = SimpleNamespace(queue_carries={REPO: {"b": ()}},
                           queue_head_carries={REPO: {"head-hk": (OLD,)}})  # fmt: skip
    got = _carries(snap, REPO, [Admitted("housekeeping", REPO, hk),  # type: ignore[arg-type]
                                Admitted("export", REPO, other)])  # fmt: skip
    # l-errors-r3: an admitted head the read did not reach is unknown (None: held, R5), never
    # read as carrying nothing
    assert got == {"b": (), "housekeeping#7": (OLD,), "export#8": None}
    unread_repo = SimpleNamespace(queue_carries={}, queue_head_carries={})
    assert _carries(unread_repo, REPO, [Admitted("export", REPO, other)]) == {}  # type: ignore[arg-type]


# ------------------------------------------------------------ lens review (errors, tests)


def test_only_the_latest_handbacks_onto_at_a_head_is_asked() -> None:  # l-tests-r1
    events = [
        {"kind": "conflict", "at": AT, "head": "head-b", "paths": ["x.py"],
         "delivered": "session", "handle": "h", "onto": OLD},
        {"kind": "conflict", "at": "2026-11-24T12:05:00Z", "head": "head-b", "paths": ["x.py"],
         "delivered": "session", "handle": "h", "onto": ONTO, "reissue": True},
    ]  # fmt: skip
    batch = Batch.model_validate({"id": "b", "title": "b", "ids": ["super-fr#2"],
                                  "events": events})  # fmt: skip
    driver = Driver([_record(_built(1, S1, "a"))])
    lineage_reads(driver, _facts(), SimpleNamespace(batches=[batch]), {"b": REPO}, LIVE,
                  {REPO: MAIN}, ())  # fmt: skip
    assert [(k, sha) for k, sha, _, _ in driver.clone.asked if k == "leads"] == [("leads", ONTO)]


def test_an_admitted_entrys_live_head_is_read_even_when_facts_hold_another() -> None:  # l-errors-r3
    driver = Driver([_record(_built(1, S1, "a"))])
    driver.clone.carry["head-op-live"] = (OLD,)
    op = LivePr(number=9, state="OPEN", draft=False, head="head-op-live", checks="green")
    hk = LivePr(number=7, state="OPEN", draft=False, head="head-hk-live", checks="green")
    reads = {"queue_operator": {REPO: ((op, None),)}, "queue_housekeeping": {REPO: ((hk, None),)}}
    out = lineage_reads(driver, _facts((9, "head-op-collected")), _judgements(), {"b": REPO},
                        LIVE, {REPO: MAIN}, (), reads=reads)  # fmt: skip
    heads = out["queue_head_carries"][REPO]
    assert heads["head-op-live"] == (OLD,) and heads["head-hk-live"] == ()
    assert "head-op-collected" in heads
