"""fr.operator_input — the one source of the raw-input relay (spec 2026-09-28 §A, #778)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.journal.model import JournalEntry, JournalParseError, serialize_entry
from fr.operator_input import (
    OPERATOR_INPUT_RULE,
    OperatorInput,
    from_entries,
    load,
    to_brief,
    to_markdown,
)


def _entry(**kw: object) -> JournalEntry:
    base: dict[str, object] = dict(scope="spec", created="2026-09-28T00:00:00", title="t")
    return JournalEntry(**{**base, **kw})  # type: ignore[arg-type]


def _input(id: str, body: str, title: str = "raw") -> JournalEntry:
    return _entry(kind="discovery", id=id, body=body, title=title, input=True)


def _decision(id: str, body: str = "b", title: str = "d") -> JournalEntry:
    return _entry(kind="decision", id=id, body=body, title=title)


def test_from_entries_picks_inputs_and_decisions_in_order() -> None:
    entries = [
        _decision("d1"),
        _entry(kind="discovery", id="plain", body="x"),
        _input("i1", "one"),
        _entry(kind="finding", id="f", state="open"),
        _input("i2", "two"),
        _decision("d2"),
    ]
    oi = from_entries(entries)
    assert oi is not None
    assert [i[0] for i in oi.inputs] == ["i1", "i2"]
    assert [d[0] for d in oi.decisions] == ["d1", "d2"]


def test_from_entries_none_without_input() -> None:
    assert from_entries([_decision("d1")]) is None
    assert from_entries([]) is None


def _write_journal(root: Path, rel: str, entries: list[JournalEntry]) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# journal\n\n" + "\n".join(serialize_entry(e) for e in entries))


def test_load_active_archived_missing_and_unparseable(tmp_path: Path) -> None:
    spec = "docs/superpowers/specs/2026-01-01-x-design.md"
    assert load(tmp_path, spec) is None
    entries = [_input("i1", "hello"), _decision("d1")]
    _write_journal(tmp_path, "docs/superpowers/journals/specs/2026-01-01-x.md", entries)
    oi = load(tmp_path, spec)
    assert oi is not None and oi.inputs[0][2] == "hello"

    arch = tmp_path / "arch"
    _write_journal(arch, "docs/superpowers/implemented/journals/specs/2026-01-01-x.md", entries)
    assert load(arch, spec) is not None

    bad = tmp_path / "bad"
    p = bad / "docs/superpowers/journals/specs/2026-01-01-x.md"
    p.parent.mkdir(parents=True)
    p.write_text("<!-- fr:journal kind=nonsense -->\n")
    with pytest.raises(JournalParseError):
        load(bad, spec)


def test_to_brief_is_verbatim() -> None:
    oi = OperatorInput(inputs=(("i1", "T", "  body\n``` x\n"),), decisions=(("d1", "D", "why"),))
    assert to_brief(oi) == {
        "rule": OPERATOR_INPUT_RULE,
        "input": [{"id": "i1", "title": "T", "body": "  body\n``` x\n"}],
        "decisions": [{"id": "d1", "title": "D", "body": "why"}],
    }


def test_to_markdown_fences_bodies() -> None:
    body = "## Heading\n\ntext\n```py\ncode\n```\n"
    oi = OperatorInput(inputs=(("i1", "Raw", body),), decisions=(("d1", "Dec", "## sneaky"),))
    md = to_markdown(oi)
    assert md.startswith("## Operator input (read-only — the spec governs)")
    assert OPERATOR_INPUT_RULE in md
    assert "### i1 — Raw" in md
    assert "### Recorded answers" in md
    assert "#### d1 — Dec" in md
    assert body in md
    # body's longest backtick run is 3 -> fence is at least 4
    assert "````\n" + body in md
    in_fence = False
    fence = ""
    for line in md.splitlines():
        stripped = line.strip("`")
        if not in_fence and line.startswith("```") and not stripped:
            in_fence, fence = True, line
            continue
        if in_fence:
            if line == fence:
                in_fence = False
            continue
        if line.startswith("## "):
            assert line == "## Operator input (read-only — the spec governs)"
