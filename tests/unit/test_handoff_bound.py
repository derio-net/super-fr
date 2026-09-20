"""Phase 1 walking skeleton (bounded-executor-handoff, P1.T1).

`build_plan_journal` writes a plan journal through the SAME serializer
`fr journal add` uses — never a hand-rolled markdown string — so a fixture
journal built by this helper cannot drift from what the CLI actually
produces. This test is the measurement harness's own smoke test: build a
journal, parse it back with the real parser, and compose a real handoff over
it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.journal.model import compose_handoff, parse_journal, serialize_entry

ENTRIES = [
    {"kind": "decision", "title": "chose x over y", "body": "because z", "phase": 1},
    {
        "kind": "finding",
        "title": "f1 breaks under load",
        "body": "repro steps",
        "phase": 2,
        "state": "open",
        "id": "f1",
    },
]


def test_build_plan_journal_composes_a_real_handoff(tmp_path: Path) -> None:
    from fr.test_support import build_plan_journal

    slug = "test-plan"
    path = build_plan_journal(tmp_path, slug, ENTRIES)

    assert path.exists()
    parsed = parse_journal(path.read_text())

    # Every entry round-trips, in order, with its kind/phase/state intact.
    # Asserting only the findings would let the decision vanish silently.
    assert [(e.kind, e.phase, e.state) for e in parsed] == [
        ("decision", 1, None),
        ("finding", 2, "open"),
    ]
    assert [e.title for e in parsed] == [e["title"] for e in ENTRIES]

    handoff = compose_handoff(parsed, phase=3, scope="plan", slug=slug)
    assert handoff.startswith("# Handoff (phase 3)")
    # The header alone is satisfied by an EMPTY entry list, so it proves
    # nothing on its own — pin that the built entries actually reach the
    # composed handoff.
    assert "f1 breaks under load" in handoff
    assert "chose x over y" in handoff


def test_the_builder_writes_what_the_real_serializer_writes(tmp_path: Path) -> None:
    """The point of the helper is that it IS the CLI's writer. Pin it against
    `serialize_entry` directly, so a future hand-rolled shortcut fails here
    rather than producing plausible-looking markdown."""
    from fr.test_support import build_plan_journal

    path = build_plan_journal(tmp_path, "test-plan", ENTRIES)
    text = path.read_text()
    for entry in parse_journal(text):
        assert serialize_entry(entry) in text


def test_duplicate_default_ids_are_refused_at_the_builder(tmp_path: Path) -> None:
    """Two entries differing only in `phase` must not collide. `parse_journal`
    rejects duplicate ids, so a colliding derivation would surface as a parse
    error far from its cause — the builder refuses at the door instead."""
    from fr.test_support import build_plan_journal

    same = {"kind": "finding", "title": "same", "body": "x", "state": "open"}
    path = build_plan_journal(tmp_path, "test-plan", [{**same, "phase": 1}, {**same, "phase": 2}])
    parsed = parse_journal(path.read_text())
    assert len({e.id for e in parsed}) == 2

    with pytest.raises(ValueError, match="duplicate entry id"):
        build_plan_journal(tmp_path, "other-plan", [{**same, "id": "dup"}, {**same, "id": "dup"}])


# --- Phase 2 (P2.T1): the state-first collapse. ---------------------------
#
# Spec §5.A1: an entry whose EFFECTIVE state is closed collapses to one line
# REGARDLESS of phase. Before this, effective state only routed a finding into
# `## Open findings`; past that, `relevant = {phase, *depends_on}` decided, so a
# `fixed` finding tagged to a dependency phase rendered in full — which is where
# ~30k of phase 6's real 83k handoff came from (§2).
#
# Decisions and discoveries stay dependency-scoped on purpose: a decision is
# never "closed" (it still constrains the phase depending on it) and a discovery
# is a trap paid for once. Only findings have a lifecycle that makes them
# historical.

COLLAPSE_ENTRIES = [
    {
        "kind": "finding",
        "id": "open-dep",
        "state": "open",
        "phase": 2,
        "title": "Still open on a dependency phase",
        "body": "OPEN-DEP-BODY",
    },
    {
        "kind": "finding",
        "id": "fixed-dep",
        "state": "fixed",
        "phase": 2,
        "title": "Fixed on a dependency phase",
        "body": "FIXED-DEP-BODY",
    },
    {
        "kind": "finding",
        "id": "refuted-dep",
        "state": "refuted",
        "phase": 2,
        "title": "Refuted on a dependency phase",
        "body": "REFUTED-DEP-BODY",
    },
    {
        "kind": "decision",
        "id": "dec-dep",
        "phase": 2,
        "title": "Decision on a dependency phase",
        "body": "DEC-DEP-BODY",
    },
    {
        "kind": "discovery",
        "id": "disc-dep",
        "phase": 2,
        "title": "Discovery on a dependency phase",
        "body": "DISC-DEP-BODY",
    },
    {
        "kind": "finding",
        "id": "was-open",
        "state": "open",
        "phase": 2,
        "title": "Opened then resolved",
        "body": "WAS-OPEN-BODY",
    },
    {
        "kind": "finding",
        "id": "res-dep",
        "state": "fixed",
        "phase": 2,
        "resolves": "was-open",
        "title": "resolves was-open: closed in phase 2",
        "body": "RES-DEP-BODY",
    },
    {
        "kind": "finding",
        "id": "fixed-far",
        "state": "fixed",
        "phase": 1,
        "title": "Fixed on a non-dependency phase",
        "body": "FIXED-FAR-BODY",
    },
]


def _collapse_handoff(tmp_path: Path) -> str:
    from fr.test_support import build_plan_journal

    path = build_plan_journal(tmp_path, "collapse", COLLAPSE_ENTRIES)
    return compose_handoff(
        parse_journal(path.read_text()), phase=3, depends_on=(2,), scope="plan", slug="collapse"
    )


def test_a_closed_finding_on_a_dependency_phase_collapses(tmp_path: Path) -> None:
    """(a) The defect §2 measured: phase 3 depends on phase 2, so `fixed-dep`
    used to render in full. Its state says it is history; its phase no longer
    overrides that."""
    out = _collapse_handoff(tmp_path)

    assert "FIXED-DEP-BODY" not in out
    assert "- fixed-dep · finding [fixed] · Fixed on a dependency phase (phase 2)" in out


def test_a_finding_still_open_on_a_dependency_phase_renders_in_full(tmp_path: Path) -> None:
    """(b) The rule keys on EFFECTIVE state, not on kind: an open finding is
    actionable anywhere and must survive the collapse untouched."""
    out = _collapse_handoff(tmp_path)

    assert "OPEN-DEP-BODY" in out
    assert "## Open findings" in out


def test_decisions_and_discoveries_on_a_dependency_phase_still_render_in_full(
    tmp_path: Path,
) -> None:
    """(c) Dependency scoping is deliberately UNCHANGED for these two kinds —
    they carry forward value (§5.A1). A test that let them collapse would be
    pinning a bound this spec explicitly declined to take."""
    out = _collapse_handoff(tmp_path)

    assert "DEC-DEP-BODY" in out
    assert "DISC-DEP-BODY" in out


def test_a_resolution_record_collapses_and_so_does_what_it_closed(tmp_path: Path) -> None:
    """(d) A resolution record is bookkeeping about a finding that is no longer
    actionable, so it collapses too — and `was-open`, closed by the fold rather
    than by its own `state` field, collapses with it. The titles survive, so the
    handoff still says both what was found and what became of it."""
    out = _collapse_handoff(tmp_path)

    assert "RES-DEP-BODY" not in out
    assert "WAS-OPEN-BODY" not in out
    assert "- res-dep · finding [fixed] · resolves was-open: closed in phase 2 (phase 2)" in out
    # The collapsed line reports the EFFECTIVE state. `was-open` carries
    # `state: open` on its own record — correctly, a journal is an append-only
    # log — but the fold closed it, so a handoff that printed `[open]` would
    # send an executor after a bug that no longer exists. That was finding
    # `78654207c227`, fixed in this phase's review.
    assert "- was-open · finding [fixed] · Opened then resolved (phase 2)" in out
    assert "- was-open · finding [open]" not in out


def test_a_refuted_finding_collapses_and_stays_refuted(tmp_path: Path) -> None:
    """The row's acceptance sentence names "fixed OR REFUTED finding", and
    until this test it named a state no test exercised.

    Two claims, because they can fail independently: a refuted finding is
    closed, so it collapses like a fixed one; and `refuted` is not folded away
    into `fixed`, because "we looked and it was not a bug" is a different fact
    from "we fixed it" and an executor re-reading the one-liner needs to know
    which.
    """
    out = _collapse_handoff(tmp_path)

    assert "REFUTED-DEP-BODY" not in out
    assert "- refuted-dep · finding [refuted] · Refuted on a dependency phase (phase 2)" in out


def test_a_closed_finding_on_a_non_dependency_phase_still_collapses(tmp_path: Path) -> None:
    """(e) No regression on the rule #465 already shipped."""
    out = _collapse_handoff(tmp_path)

    assert "FIXED-FAR-BODY" not in out
    assert "- fixed-far · finding [fixed] · Fixed on a non-dependency phase (phase 1)" in out


# --- P2.T1.S2: the load-bearing property (spec §5.A3). --------------------
#
# The spec's first draft asserted that handoff size stops growing with phase
# number; categorising phase 6's REAL handoff refuted that, because what remains
# after the collapse is decisions and discoveries from dependency phases —
# content a later phase genuinely needs. So the shipped bar is the property that
# is both true and load-bearing: a CLOSED entry contributes O(1) characters
# regardless of its body size.

_BIG = 20
_UNIT = "closed detail. "


def _sized_journal(root: Path, *, closed_mult: int, open_mult: int) -> str:
    """A ten-phase journal whose closed and open bodies scale independently.

    Every `fixed` finding sits on a phase the composed handoff DEPENDS on,
    which is precisely the shape that used to render in full.
    """
    from fr.test_support import build_plan_journal

    entries: list[dict[str, object]] = []
    for phase in range(1, 11):
        entries.append(
            {
                "kind": "finding",
                "id": f"fixed-{phase}",
                "state": "fixed",
                "phase": phase,
                "title": f"fixed finding from phase {phase}",
                "body": _UNIT * closed_mult,
            }
        )
        entries.append(
            {
                "kind": "decision",
                "id": f"dec-{phase}",
                "phase": phase,
                "title": f"decision from phase {phase}",
                "body": "rationale. " * 3,
            }
        )
    entries.append(
        {
            "kind": "finding",
            "id": "still-open",
            "state": "open",
            "phase": 4,
            "title": "the one thing still actionable",
            "body": _UNIT * open_mult,
        }
    )
    path = build_plan_journal(root, "sized", entries)
    return compose_handoff(
        parse_journal(path.read_text()),
        phase=10,
        depends_on=tuple(range(1, 10)),
        scope="plan",
        slug="sized",
    )


def test_a_closed_entry_costs_a_constant_regardless_of_its_body_size(tmp_path: Path) -> None:
    """Spec §5.A3's bar: two journals identical except that every CLOSED
    finding's body is 20x longer in the second."""
    small = _sized_journal(tmp_path / "small", closed_mult=1, open_mult=1)
    big = _sized_journal(tmp_path / "big", closed_mult=_BIG, open_mult=1)

    # 64 chars of slack, not 0: the collapsed one-liner carries the entry's
    # id/title, and a body-length change can shift nothing else. Real
    # un-collapsed growth here is thousands of chars, so the constant only has
    # to be far below that.
    assert len(big) - len(small) < 64, (
        f"growing 10 closed findings' bodies {_BIG}x grew the handoff by "
        f"{len(big) - len(small)} chars: closed entries are not O(1)"
    )


def test_but_growing_an_open_findings_body_does_grow_the_handoff(tmp_path: Path) -> None:
    """The inverse guard, without which the test above passes vacuously — a
    `compose_handoff` that returned a constant string, or one that dropped
    closed entries AND open ones, would satisfy it."""
    small = _sized_journal(tmp_path / "small", closed_mult=1, open_mult=1)
    wide = _sized_journal(tmp_path / "wide", closed_mult=1, open_mult=_BIG)

    # Minus a small allowance: asserting the EXACT delta makes any future
    # whitespace change in `serialize_entry` fail this test spuriously, which
    # would look like a regression in the bound and is not.
    assert len(wide) - len(small) >= len(_UNIT) * (_BIG - 1) - 8, (
        "an OPEN finding's body must still reach the executor in full"
    )


def test_a_reopening_resolution_record_renders_in_full(tmp_path: Path) -> None:
    """A resolution record that RE-OPENS must not collapse.

    `fr journal add --resolves <id> --state open` is a documented path, and it
    is the one shape where "a resolution record is history" is false. Collapsed,
    the only text explaining why the finding is actionable again is lost, while
    the original report still renders in full under its stale state — the
    executor is told to act on something and not told what changed.
    """
    from fr.test_support import build_plan_journal

    path = build_plan_journal(
        tmp_path,
        "reopen-plan",
        [
            {
                "kind": "finding",
                "id": "f1",
                "phase": 1,
                "state": "fixed",
                "title": "Originally reported",
                "body": "ORIGINAL-REPORT-BODY",
            },
            {
                "kind": "finding",
                "id": "rec",
                "phase": 2,
                "state": "open",
                "resolves": "f1",
                "title": "regressed under load",
                "body": "REOPEN-REASON-BODY",
            },
        ],
    )
    out = compose_handoff(
        parse_journal(path.read_text()),
        phase=3,
        scope="plan",
        slug="reopen-plan",
        depends_on=(1, 2),
    )

    assert "REOPEN-REASON-BODY" in out, "the reason a finding re-opened must reach the executor"
    assert "ORIGINAL-REPORT-BODY" in out, "so must the original report it re-opens"


def test_a_finding_dominated_journal_flattens(tmp_path: Path) -> None:
    """The ceiling the spec commits to in §5.A3 and §7.

    Distinct from the O(1) test, which holds body size against itself. Here the
    ENTRY COUNT grows: a journal whose history is all closed findings composes
    to roughly the same handoff at phase 10 as at phase 2, because every one of
    those entries costs a line. This is the claim "the handoff flattens on a
    finding-dominated journal", and it is what makes the bound a bound rather
    than a smaller slope.
    """
    from fr.test_support import build_plan_journal

    entries: list[dict] = []
    for n in range(1, 10):
        entries.append(
            {
                "kind": "finding",
                "id": f"f{n}",
                "phase": n,
                "state": "fixed",
                "title": f"closed in phase {n}",
                "body": "a long finding body. " * 40,
            }
        )
    path = build_plan_journal(tmp_path, "flat-plan", entries)
    parsed = parse_journal(path.read_text())

    early = compose_handoff(parsed, phase=2, scope="plan", slug="flat-plan", depends_on=(1,))
    late = compose_handoff(
        parsed, phase=10, scope="plan", slug="flat-plan", depends_on=tuple(range(1, 10))
    )

    assert len(late) <= len(early) * 1.15, (
        f"a finding-dominated journal must flatten: phase 2 = {len(early)}, "
        f"phase 10 = {len(late)} chars"
    )
