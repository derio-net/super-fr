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
