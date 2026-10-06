"""The history page, `fr triage history render` (spec 2026-10-05-triage-pages-goal, R8, §F)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from fr.cli import app
from fr.triage.fragments import Entry, Resolved
from fr.triage.history import GENERATED, render_history
from fr.triage.model import Facts, Judgements
from fr.triage.snapshot import Snapshot, store_snapshot, take_snapshot
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import batch, busy, dispatch, facts, issue, j, judgements

SCOPE = "example-org/widgets"
CANCEL = {"kind": "cancel", "at": "2026-10-02T10:00:00Z", "reason": "no longer wanted"}
CLOSEOUT = {
    "kind": "closeout",
    "at": "2026-10-03T10:00:00Z",
    "runner": "fake",
    "handle": "h",
    "archived": 12,
}


def _finished() -> tuple[Facts, Judgements]:
    """Waves 1 and 2 are finished; wave 3 is still live."""
    f = facts([issue(n) for n in range(1, 5)])
    jd = judgements(
        {f"widgets#{n}": j() for n in range(1, 5)},
        [
            batch("a", [1], wave=1, events=[dispatch("a"), CANCEL]),
            batch("b", [2], wave=2, events=[dispatch("b"), CLOSEOUT]),
            batch("b2", [3], wave=2, events=[dispatch("b2"), CANCEL]),
            batch("c", [4], wave=3, events=[dispatch("c")]),
        ],
    )
    return f, jd


def _snapshots(f: Facts, jd: Judgements, n: int) -> list[tuple[datetime, Snapshot]]:
    base = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
    return [
        (base + timedelta(days=step), take_snapshot(f, jd, acceptance=None)) for step in range(n)
    ]


def _resolved(*entries: Entry, fragments: dict[str, str] | None = None) -> Resolved:
    return Resolved(order=list(entries) or [Entry(g) for g in GENERATED], fragments=fragments or {})


def _page(f: Facts, jd: Judgements, *, snaps: int = 2, resolved: Resolved | None = None) -> str:
    return render_history(
        f, jd, snapshots=_snapshots(f, jd, snaps), resolved=resolved or _resolved(), notes=[]
    )


def test_the_history_page_opens_with_its_nav_and_goal() -> None:
    page = _page(*_finished())
    assert 'aria-current="page"' in page
    assert re.search(r'<a [^>]*href="history.html"[^>]*aria-current="page"', page)
    assert 'class="goal">How did we get here?<' in page
    assert "<title>History · example-org--widgets</title>" in page


def test_the_timeline_is_the_moved_snapshot_timeline() -> None:
    page = _page(*_finished(), snaps=3)
    tl = page[page.index('id="snapshot-timeline"') : page.index('id="finished-waves"')]
    assert len(re.findall(r'role="tabpanel"', tl)) == 3
    assert re.search(r'aria-selected="true"[^>]*>2026-09-27', tl)  # newest first shown
    assert "UTC" in tl


def test_finished_waves_are_tabs_with_the_highest_finished_selected() -> None:
    page = _page(*_finished())
    sect = page[page.index('id="finished-waves"') :]
    assert "data-tabs" in sect
    assert re.search(r'id="history-wave-tab-2"[^>]*aria-selected="true"', sect)
    assert re.search(r'id="history-wave-tab-1"[^>]*aria-selected="false"', sect)
    assert "history-wave-tab-3" not in sect  # wave 3 still has live work: not finished


def test_batch_links_point_at_the_board() -> None:
    page = _page(*_finished())
    sect = page[page.index('id="finished-waves"') :]
    assert 'href="triage.html#batch-a"' in sect and 'href="triage.html#batch-b"' in sect
    assert 'href="#batch-' not in sect


def test_with_no_finished_wave_the_page_says_so() -> None:
    f, jd = busy()
    page = _page(f, jd)
    sect = page[
        page.index('id="finished-waves"') : page.index(
            "</section>", page.index('id="finished-waves"')
        )
    ]
    assert "No wave is finished yet" in sect
    assert "data-tabs" not in sect


def test_manifest_fragments_render_at_their_position() -> None:
    f, jd = _finished()
    resolved = _resolved(
        Entry("timeline"),
        Entry("note.html", "Old story", True),
        Entry("finished-waves"),
        fragments={"note.html": "<p>FRAG</p>"},
    )
    page = _page(f, jd, resolved=resolved)
    at = [page.index(x) for x in ('id="snapshot-timeline"', "FRAG", 'id="finished-waves"')]
    assert at == sorted(at)
    assert '<details id="fragment-note-html" class="fold">' in page and "Old story" in page


# ------------------------------------------------------------------ the command


def _state(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    f, jd = _finished()
    (state / "facts.json").write_text(json.dumps(f.to_json()), encoding="utf-8")
    (state / "judgements.yaml").write_text(
        yaml.safe_dump(jd.model_dump(mode="json", by_alias=True, exclude_none=True)),
        encoding="utf-8",
    )
    return state


def _run(state: Path, *extra: str):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(
        app, ["triage", "history", "render", "--repo", SCOPE, "--dir", str(state), *extra]
    )


def test_the_command_writes_history_html_and_prints_the_path(tmp_path: Path) -> None:
    state = _state(tmp_path)
    f, jd = _finished()
    for step in range(2):
        snap = take_snapshot(f, jd, acceptance=None).model_copy(update={"figures": {"open": step}})
        store_snapshot(state, snap, datetime(2026, 9, 25 + step, 9, 0, tzinfo=UTC))
    result = _run(state)
    assert result.exit_code == 0, result.output
    out = state / "history.html"
    assert out.is_file() and str(out) in result.output.replace("\n", "")
    page = out.read_text(encoding="utf-8")
    assert len(re.findall(r'id="snapshot-tab-', page)) == 2
    assert "history-wave-tab-2" in page


def test_the_command_reads_the_history_manifest(tmp_path: Path) -> None:
    state = _state(tmp_path)
    hdir = state / "history"
    hdir.mkdir()
    (hdir / "manifest.yaml").write_text(
        "sections:\n  - timeline\n  - finished-waves\n  - fragment: why.html\n    title: Why\n"
        "    collapsed: true\n  - gone.html\n  - waves\n",
        encoding="utf-8",
    )
    (hdir / "why.html").write_text("<p>WHY</p>", encoding="utf-8")
    result = _run(state)
    assert result.exit_code == 0, result.output
    page = (state / "history.html").read_text(encoding="utf-8")
    assert "<p>WHY</p>" in page and "gone.html" in page
    assert "`waves`, which is now on the board page" in page


def test_the_command_refuses_a_malformed_fragment_and_writes_nothing(tmp_path: Path) -> None:
    state = _state(tmp_path)
    hdir = state / "history"
    hdir.mkdir()
    (hdir / "manifest.yaml").write_text("sections:\n  - bad.html\n", encoding="utf-8")
    (hdir / "bad.html").write_text("<div>open", encoding="utf-8")
    result = _run(state)
    assert result.exit_code == 2 and "bad.html" in result.output
    assert not (state / "history.html").exists()


def test_the_command_without_facts_names_collect(tmp_path: Path) -> None:
    state = tmp_path / "empty"
    state.mkdir()
    result = _run(state)
    assert result.exit_code == 2 and "collect" in result.output
