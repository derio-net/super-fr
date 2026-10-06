"""Main/subagent and per-unit usage split (cost-evidence spec §A-§B, R2-R4)."""

from __future__ import annotations

import pytest
from fr.usage.file import Figure, SessionEntry, session_entry
from fr.usage.model import Cost, Message, Tokens, UsageRecord
from fr.usage.rollup import OUTSIDE, message_dollars, rollup, windows_from_cursor
from fr.usage.split import UnitIndex

STARTED = "2026-10-06T10:00:00+00:00"
CURSOR = {
    "started": STARTED,
    "steps": {
        "brainstorm": {"at": "2026-10-06T10:10:00+00:00"},
        "implement": {"at": "2026-10-06T11:00:00+00:00"},
    },
}
FIELDS = ("turns", "input", "cache_write", "cache_read", "output")


def _msg(ts: str, *, agent_id: str | None = None, out: int = 10, model: str = "m1") -> Message:
    return Message(
        ts=ts,
        model=model,
        tokens=Tokens(input=1, cache_write_5m=2, cache_write_1h=1, cache_read=100, output=out),
        agent="main" if agent_id is None else "super-fr:fr-phase-executor",
        agent_id=agent_id,
    )


def _record(messages: tuple[Message, ...], usd: float | None = 3.0) -> UsageRecord:
    cost = (
        Cost()
        if usd is None
        else Cost(usd=usd, source="exact", by_model={"m1": usd - 0.5, "ghost": 0.5})
    )
    return UsageRecord(session="s", harness="claude-code", messages=messages, cost=cost)


MESSAGES = (
    _msg("2026-10-06T10:05:00Z", out=10),
    _msg("2026-10-06T10:06:00Z", agent_id="a1", out=20),
    _msg("2026-10-06T10:30:00Z", agent_id="a1", out=40),
    _msg("2026-10-06T10:40:00Z", out=80),
    _msg("2026-10-06T12:00:00Z", out=160),  # after every step: (outside run)
)


def test_message_dollars_equals_what_rollup_attributes_and_returns_the_remainder() -> None:
    record = _record(MESSAGES)
    dollars, remainder = message_dollars(record)
    assert len(dollars) == len(MESSAGES)
    assert remainder == pytest.approx(0.5)  # the billed model no message carries
    assert sum(dollars) + remainder == pytest.approx(3.0)
    assert sum(rollup([record]).by_model.values()) == pytest.approx(sum(dollars) + remainder)


def test_an_unpriced_session_has_no_message_dollars() -> None:
    assert message_dollars(_record(MESSAGES, usd=None)) == ([0.0] * 5, 0.0)


def _entry(usd: float | None) -> SessionEntry:
    return session_entry(_record(MESSAGES, usd), windows_from_cursor(CURSOR), UnitIndex())


def _add(a: Figure, b: Figure, name: str) -> float | None:
    x, y = getattr(a, name), getattr(b, name)
    return None if x is None or y is None else x + y


def test_steps_by_role_sum_back_to_each_step_priced() -> None:
    entry = _entry(3.0)
    main, sub = entry.steps_by_role["main"], entry.steps_by_role["subagent"]
    remainder = message_dollars(_record(MESSAGES))[1]
    for step, whole in entry.steps.items():
        zero = Figure(usd=0.0, turns=0, input=0, cache_write=0, cache_read=0, output=0)
        m, s = main.get(step, zero), sub.get(step, zero)
        assert _add(m, s, "turns") == whole.turns
        expected = whole.usd - (remainder if step == OUTSIDE else 0.0)
        assert _add(m, s, "usd") == pytest.approx(expected)
    assert main["brainstorm"].output == 10
    assert sub["brainstorm"].output == 20  # 10:06 only; 10:30 is past brainstorm's end
    assert sub["implement"].output == 40 and main["implement"].output == 80
    assert main[OUTSIDE].output == 160
    assert (main["brainstorm"].input, main["brainstorm"].cache_write) == (1, 3)
    assert main["brainstorm"].cache_read == 100


def test_steps_by_role_unpriced_has_dollars_none_everywhere_and_tokens_present() -> None:
    entry = _entry(None)
    figures = [f for role in entry.steps_by_role.values() for f in role.values()]
    assert figures and all(f.usd is None for f in figures)
    assert all(f.turns and f.output for f in figures)


def test_an_unavailable_entry_carries_neither_split() -> None:
    with pytest.raises(ValueError, match="unavailable"):
        SessionEntry(
            session="s",
            unavailable="x",
            steps_by_role={"main": {"a": Figure(usd=None, turns=1)}},
        )
    with pytest.raises(ValueError, match="unavailable"):
        SessionEntry(session="s", unavailable="x", units={"u": {"agent": Figure(turns=1)}})


# --- per-unit attribution (spec §B, R3) ---------------------------------------

from fr.usage.file import dump_usage, parse_usage, unit_index, units_by_agent  # noqa: E402


def _att(dispatched: str, returned: str | None, agent: str | None = None, **extra: object) -> dict:
    out: dict = {"dispatched": dispatched, "returned": returned}
    if agent:
        out["agent"] = agent
    return {**out, **extra}


def _cursor(**steps: dict) -> dict:
    return {"started": STARTED, "steps": steps}


T = "2026-10-06T"
UNIT_CURSOR = _cursor(
    **{
        "spec-review": {
            "units": {
                "step/spec-review": {
                    "attempts": [_att(f"{T}10:00:00+00:00", f"{T}10:10:00+00:00", "sr1")]
                }
            }
        },
        "implement-phase": {
            "units": {
                "phase/1/implement-phase": {
                    "attempts": [_att(f"{T}10:10:00+00:00", f"{T}10:30:00+00:00", "ex1")]
                },
                # a retry opened later, overlapping unit 2's interval's tail
                "phase/2/implement-phase": {
                    "attempts": [
                        _att(f"{T}10:30:00+00:00", f"{T}10:50:00+00:00", "ex2"),
                        _att(f"{T}10:40:00+00:00", f"{T}10:55:00+00:00", "ex2b"),
                    ]
                },
                "phase/3/implement-phase": {
                    "attempts": [
                        {"dispatched": f"{T}10:55:00+00:00", "synthesized": True},
                    ]
                },
            }
        },
        "review-phase": {
            "units": {
                "phase/1/review-phase": {
                    "attempts": [_att(f"{T}10:55:00+00:00", f"{T}11:00:00+00:00")],
                    "evidence": {"review": "r1", "reviewer": "rv1"},
                },
                "phase/4/review-phase": {
                    "attempts": [_att(f"{T}11:00:00+00:00", None)],  # held: open-ended
                },
            }
        },
    }
)
INDEX = unit_index(UNIT_CURSOR)


def _entry_for(*messages: Message, index: UnitIndex = INDEX, usd: float | None = 6.0):
    record = UsageRecord(
        session="s",
        harness="claude-code",
        messages=messages,
        cost=Cost() if usd is None else Cost(usd=usd, source="exact", by_model={"m1": usd}),
    )
    return record, session_entry(record, windows_from_cursor(CURSOR), index)


def test_the_index_maps_agents_roles_and_open_ended_intervals() -> None:
    assert INDEX.agents == {
        "sr1": "step/spec-review",
        "ex1": "phase/1/implement-phase",
        "ex2": "phase/2/implement-phase",
        "ex2b": "phase/2/implement-phase",
        "rv1": "phase/1/review-phase",
    }
    assert INDEX.roles["step/spec-review"] == "agent"
    assert INDEX.roles["phase/1/implement-phase"] == "executor"
    assert INDEX.roles["phase/1/review-phase"] == "reviewer"
    assert units_by_agent(UNIT_CURSOR) == INDEX.agents
    by_unit = {i.unit: i for i in INDEX.intervals if i.unit != "phase/2/implement-phase"}
    assert by_unit["phase/4/review-phase"].end is None
    assert "phase/3/implement-phase" not in {i.unit for i in INDEX.intervals}  # synthesized


def test_an_unreturned_attempt_that_is_not_the_last_is_not_open_ended() -> None:
    cursor = _cursor(
        **{
            "implement-phase": {
                "units": {
                    "phase/1/implement-phase": {
                        "attempts": [
                            _att(f"{T}10:00:00+00:00", None, "a"),
                            _att(f"{T}10:10:00+00:00", f"{T}10:20:00+00:00", "b"),
                        ]
                    }
                }
            }
        }
    )
    assert [(i.start.minute, i.end and i.end.minute) for i in unit_index(cursor).intervals] == [
        (10, 20)
    ]


def test_subagent_messages_go_to_executor_reviewer_and_flat_agent_roles() -> None:
    _, entry = _entry_for(
        _msg(f"{T}10:05:00Z", agent_id="sr1"),
        _msg(f"{T}10:20:00Z", agent_id="ex1"),
        _msg(f"{T}10:57:00Z", agent_id="rv1"),
        _msg(f"{T}10:58:00Z", agent_id="rv1"),
    )
    assert entry.units["step/spec-review"]["agent"].turns == 1
    assert entry.units["phase/1/implement-phase"]["executor"].turns == 1
    assert entry.units["phase/1/review-phase"]["reviewer"].turns == 2
    assert UNATTRIBUTED_NOT_PRESENT not in entry.units


UNATTRIBUTED_NOT_PRESENT = "(unattributed)"


def test_an_unmatched_subagent_is_unattributed_with_role_subagent() -> None:
    _, entry = _entry_for(_msg(f"{T}10:20:00Z", agent_id="nobody"))
    assert entry.units == {
        "(unattributed)": {"subagent": entry.units["(unattributed)"]["subagent"]}
    }
    assert entry.units["(unattributed)"]["subagent"].turns == 1


def test_orchestrator_messages_use_half_open_intervals_so_a_shared_endpoint_counts_once() -> None:
    _, entry = _entry_for(
        _msg(f"{T}10:05:00Z"),  # inside spec-review
        _msg(f"{T}10:10:00Z"),  # shared endpoint: spec-review's return, not phase 1's dispatch
        _msg(f"{T}10:10:01Z"),  # just after: phase 1
    )
    assert entry.units["step/spec-review"]["orchestrator"].turns == 2
    assert entry.units["phase/1/implement-phase"]["orchestrator"].turns == 1


def test_a_retry_overlapping_a_later_unit_takes_the_message_once() -> None:
    _, entry = _entry_for(_msg(f"{T}10:45:00Z"))  # in ex2's and ex2b's intervals
    total = sum(f.turns for roles in entry.units.values() for f in roles.values())
    assert total == 1
    assert entry.units["phase/2/implement-phase"]["orchestrator"].turns == 1


def test_a_held_attempt_is_open_ended_and_a_synthesized_one_holds_nothing() -> None:
    _, entry = _entry_for(_msg(f"{T}13:00:00Z"), _msg(f"{T}10:56:00Z"))
    assert entry.units["phase/4/review-phase"]["orchestrator"].turns == 1
    assert "phase/3/implement-phase" not in entry.units
    assert entry.units["phase/1/review-phase"]["orchestrator"].turns == 1  # 10:56 in (10:55, 11:00]


def test_a_main_message_outside_every_interval_stays_in_its_step_only() -> None:
    record, entry = _entry_for(_msg(f"{T}09:00:00Z"), index=unit_index(_cursor()))
    assert entry.units == {}
    assert entry.steps_by_role["main"][OUTSIDE].turns == 1


def test_the_unit_figures_never_exceed_the_per_message_total() -> None:
    messages = (
        _msg(f"{T}10:05:00Z"),
        _msg(f"{T}10:20:00Z", agent_id="ex1"),
        _msg(f"{T}10:25:00Z", agent_id="ghost"),
        _msg(f"{T}09:00:00Z"),  # outside every interval
    )
    record, entry = _entry_for(*messages)
    figures = [f for roles in entry.units.values() for f in roles.values()]
    total_usd = sum(message_dollars(record)[0])
    assert sum(f.usd for f in figures) <= total_usd + 1e-9
    for name in FIELDS:
        assert sum(getattr(f, name) for f in figures) <= sum(
            getattr(f, name) for roles in entry.steps_by_role.values() for f in roles.values()
        )
    assert sum(f.turns for f in figures) == 3  # the early main message is the difference


def test_the_split_round_trips_through_the_file_and_carries_no_unit_without_an_index() -> None:
    from fr.usage.file import Capture, UsageFile, upsert_capture

    record, entry = _entry_for(_msg(f"{T}10:20:00Z", agent_id="ex1"))
    capture = Capture(
        host="h-00000000",
        harness="claude-code",
        mode="host-worktree",
        captured_at="2026-10-06T12:00:00+00:00",
        at=("deliver",),
        sessions=(entry,),
    )
    text = dump_usage(upsert_capture(UsageFile(run="r"), capture))
    assert parse_usage(text).captures[0].sessions[0] == entry
    bare = session_entry(record, windows_from_cursor(CURSOR))
    assert bare.steps_by_role == {} and bare.units == {}
