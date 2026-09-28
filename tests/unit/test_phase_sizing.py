"""`fr.phase_sizing` — which asks each agentic phase serves (spec
2026-09-28-phase-sizing-design.md §A, Test Plan items 1–2)."""

from __future__ import annotations

from fr.acceptance.model import parse_matrix
from fr.journal.model import JournalEntry
from fr.phase_sizing import (
    WAIVING,
    PhaseAsks,
    SplitDecision,
    phase_asks,
    split_decisions,
)
from fr.types import PhaseHeader

SPEC = "docs/superpowers/specs/x-design.md"
SPEC_REF = f"super-fr:{SPEC}"
PLAN = "2026-09-28-x"


def _matrix(rows: dict[str, list[str]]) -> object:
    """A matrix whose row `id` cites each `R<n>` in its list."""
    lines = ["org: derio-net", "repo: super-fr", "rows:"]
    for rid, reqs in rows.items():
        lines += [
            f"  - id: {rid}",
            "    capability: Cap",
            "    acceptance: A",
            "    origin:",
            *[f"    - super-fr:{SPEC}#{r}" for r in reqs],
            "    levels: {}",
            "    status: not-implemented",
            "    notes: ''",
        ]
    return parse_matrix("\n".join(lines) + "\n")


def _phase(n: int, *rows: str, tag: str = "agentic") -> PhaseHeader:
    return PhaseHeader(number=n, title=f"P{n}", tag=tag, acceptance=rows)  # type: ignore[arg-type]


def _decision(n: int, title: str, *, plan: str = PLAN, kind: str = "decision") -> JournalEntry:
    return JournalEntry(
        kind=kind,  # type: ignore[arg-type]
        scope="spec",
        id=f"phase-split-{plan}-p{n}",
        created="2026-09-28T00:00:00+00:00",
        title=title,
    )


def _by_number(result: list[PhaseAsks]) -> dict[int, PhaseAsks]:
    return {pa.number: pa for pa in result}


# ── phase_asks ──────────────────────────────────────────────────────────────


def test_two_phases_sharing_an_ask_own_only_their_other_one() -> None:
    m = _matrix({"a": ["R1", "R2"], "b": ["R1", "R3"]})
    got = _by_number(phase_asks([_phase(1, "a"), _phase(2, "b")], m, SPEC_REF, {}))
    assert got[1].asks == {"R1", "R2"}
    assert got[1].own == {"R2"}
    assert got[2].asks == {"R1", "R3"}
    assert got[2].own == {"R3"}


def test_a_manual_phase_neither_holds_nor_removes_an_ask() -> None:
    m = _matrix({"a": ["R1"], "b": ["R1"]})
    result = phase_asks([_phase(1, "a"), _phase(2, "b", tag="manual")], m, SPEC_REF, {})
    assert [pa.number for pa in result] == [1]
    assert result[0].own == {"R1"}


def test_an_unknown_row_id_contributes_nothing() -> None:
    m = _matrix({"a": ["R1"]})
    got = _by_number(phase_asks([_phase(1, "a", "ghost")], m, SPEC_REF, {}))
    assert got[1].asks == {"R1"}


def test_an_origin_naming_the_archived_spec_twin_counts() -> None:
    archived = SPEC.replace("docs/superpowers/specs/", "docs/superpowers/implemented/specs/")
    m = parse_matrix(
        "org: derio-net\nrepo: super-fr\nrows:\n"
        "  - id: a\n    capability: C\n    acceptance: A\n"
        f"    origin:\n    - super-fr:{archived}#R4\n"
        "    levels: {}\n    status: not-implemented\n    notes: ''\n"
    )
    got = phase_asks([_phase(1, "a")], m, SPEC_REF, {})
    assert got[0].asks == {"R4"}


def test_a_fragment_that_is_not_a_requirement_id_is_not_an_ask() -> None:
    m = parse_matrix(
        "org: derio-net\nrepo: super-fr\nrows:\n"
        "  - id: a\n    capability: C\n    acceptance: A\n"
        f"    origin:\n    - super-fr:{SPEC}#L12\n    - super-fr:{SPEC}\n"
        "    - other:docs/y.md#R1\n"
        "    levels: {}\n    status: not-implemented\n    notes: ''\n"
    )
    assert phase_asks([_phase(1, "a")], m, SPEC_REF, {})[0].asks == frozenset()


def test_twenty_rows_in_one_phase_give_one_phase_with_all_their_asks() -> None:
    rows = {f"r{i}": [f"R{i}"] for i in range(1, 21)}
    m = _matrix(rows)
    result = phase_asks([_phase(1, *rows)], m, SPEC_REF, {})
    assert len(result) == 1
    assert result[0].asks == {f"R{i}" for i in range(1, 21)}
    assert result[0].own == result[0].asks


def test_a_waived_phase_does_not_take_a_shared_ask_away() -> None:
    """Review s2: R1 split by tier — p1 keeps R1 as its own ask."""
    m = _matrix({"a": ["R1"], "b": ["R1"]})
    decisions = {2: SplitDecision(number=2, reason="tier", title="tier: hard", malformed=False)}
    got = _by_number(phase_asks([_phase(1, "a"), _phase(2, "b")], m, SPEC_REF, decisions))
    assert got[1].own == {"R1"}
    assert got[2].own == frozenset()  # p2 passes by its waiver, not by an ask


def test_an_ask_decision_does_not_exclude_the_phase() -> None:
    m = _matrix({"a": ["R1"], "b": ["R1"]})
    decisions = {2: SplitDecision(number=2, reason="ask", title="ask: x", malformed=False)}
    got = _by_number(phase_asks([_phase(1, "a"), _phase(2, "b")], m, SPEC_REF, decisions))
    assert got[1].own == frozenset()


def test_waiving_is_the_three_non_ask_tokens() -> None:
    assert WAIVING == {"tier", "risk-first", "review-size"}


# ── split_decisions ───────────────────────────────────────────────────────


def test_each_reason_token_maps_to_its_reason() -> None:
    entries = [
        _decision(2, "ask: the second ask"),
        _decision(3, "tier: needs the hard tier"),
        _decision(4, "risk-first: land the parser first"),
        _decision(5, "review-size: 2k lines"),
    ]
    got = split_decisions(entries, PLAN)
    assert {n: d.reason for n, d in got.items()} == {
        2: "ask",
        3: "tier",
        4: "risk-first",
        5: "review-size",
    }
    assert not any(d.malformed for d in got.values())
    assert got[3].title == "tier: needs the hard tier"


def test_an_unknown_prefix_is_malformed_not_absent() -> None:
    got = split_decisions([_decision(2, "because: reasons")], PLAN)
    assert got[2].malformed is True
    assert got[2].reason is None


def test_other_kinds_and_other_plans_are_ignored() -> None:
    entries = [
        _decision(2, "ask: x", kind="discovery"),
        _decision(3, "ask: x", plan="2026-01-01-other"),
        JournalEntry(
            kind="decision",
            scope="spec",
            id=f"skeleton-override-{PLAN}",
            created="2026-09-28T00:00:00+00:00",
            title="ask: nope",
        ),
    ]
    assert split_decisions(entries, PLAN) == {}


def test_a_plan_slug_prefix_of_another_does_not_match() -> None:
    """`phase-split-<plan>-p2` of plan `x-2` must not be read for plan `x`."""
    entries = [_decision(2, "ask: x", plan=f"{PLAN}-2")]
    assert split_decisions(entries, PLAN) == {}
