"""The history page, `fr triage history render` (spec 2026-10-05-triage-pages-goal, R8, §F).

The page answers "How did we get here?": the snapshot timeline (stepping through the stored
snapshots shows what the board showed then), then the **finished waves** as tabs (the
board's own wave table, its batch links pointing at `triage.html`), then the authored
fragments `history/manifest.yaml` places among them. A wave is finished when every batch in
it is terminal (`batch_drive.finished_waves`, the one predicate); a finished wave shows here
and not on the board.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from fr.triage.batch import BATCH_STAGES
from fr.triage.components import (
    BASE_CSS,
    CHROME_CSS,
    GUTTER_CSS,
    TABS_CSS,
    TABS_SCRIPT,
    TOKENS_CSS,
    page_header,
    tabs,
)
from fr.triage.fragments import Resolved, splice
from fr.triage.model import Facts, Judgements
from fr.triage.render import FONTS, _wave_table, esc
from fr.triage.snapshot import Snapshot, diff_snapshots
from fr.triage.views import batch_stages, finished_waves, preselected_wave, waves

DASH = "—"
PAGE_FILE = "history.html"
HISTORY_DIR = "history"
BOARD_FILE = "triage.html"

GENERATED = ("timeline", "finished-waves")
MOVED = {"waves": "board"}  # a section an old manifest may name that the board owns

CSS = (
    TOKENS_CSS
    + BASE_CSS
    + """
.mono { font-family: var(--mono); font-size: .92em; }
.tablewrap { overflow-x: auto; }
table.grid { border-collapse: collapse; width: 100%; font-size: .88rem; }
table.grid th, table.grid td { text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--line); padding: 4px 8px; overflow-wrap: anywhere; }
table.grid th { color: var(--muted); font-weight: 500; }
.pill { font-size: .75rem; border-radius: 999px; padding: 1px 9px; color: var(--surface);
  background: var(--muted); white-space: nowrap; }
.pill.bstage-dispatched, .pill.bstage-pr-open { background: var(--live); }
.pill.bstage-merged { background: var(--accent); }
.pill.bstage-partial { background: var(--sev-2); }
.pill.bstage-cancelled, .pill.bstage-abandoned { background: var(--sev-4); }
.pill.bstage-proposed { background: transparent; color: var(--muted);
  border: 1px solid var(--line); }
"""
    + CHROME_CSS
    + TABS_CSS
    + GUTTER_CSS
)


def _stamp(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _list(items: Sequence[str]) -> str:
    return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def _stage_counts(batches: Mapping[str, str]) -> str:
    """Batches per stage, with the per-batch list folded away (gh#917).

    A stage an older fr stored that `BATCH_STAGES` no longer names still counts, last.
    """
    if not batches:
        return '<p class="quiet">no batches</p>'
    counts = Counter(batches.values())
    order: list[str] = [s for s in BATCH_STAGES if s in counts]
    order += sorted(s for s in counts if s not in BATCH_STAGES)
    chips = "".join(f'<span class="chip">{esc(s)} <b>{counts[s]}</b></span>' for s in order)
    listing = "".join(
        f"<span><code>{esc(b)}</code> {esc(s)}</span>" for b, s in sorted(batches.items())
    )
    return (
        f'<div class="chips">{chips}</div><details class="stages">'
        f"<summary>All {len(batches)} {'batch' if len(batches) == 1 else 'batches'}</summary>"
        f'<div class="stage-list">{listing}</div></details>'
    )


def _snapshot_panel(snap: Snapshot, previous: Snapshot | None) -> str:
    rows = []
    for name, value in snap.figures.items():
        before = previous.figures.get(name) if previous is not None else None
        change = DASH if before is None else f"{value - before:+d}"
        rows.append(
            f'<tr><td>{esc(name)}</td><td class="n">{value}</td><td class="n">{change}</td></tr>'
        )
    table = (
        '<div class="scroll"><table><thead><tr><th>Figure</th><th class="n">Then</th>'
        f'<th class="n">Change</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )
    diff = diff_snapshots(previous, snap)
    parts = ['<p class="src">Measured then: the figures and batch stages this snapshot stored.</p>']
    parts.append(table)
    parts.append(_stage_counts(snap.batches))
    if diff is None:
        parts.append('<p class="lede">The earliest snapshot: nothing earlier to compare.</p>')
    elif diff.empty:
        parts.append('<p class="lede">Nothing changed since the snapshot before.</p>')
    else:
        for title, items in (
            ("Merged or closed", diff.merged_or_closed),
            ("Filed", diff.filed),
            ("Batch stage changes", diff.stage_changes),
            ("Acceptance rows moved", diff.acceptance_moved),
        ):
            if items:
                parts.append(f"<h4>{title}</h4>{_list(items)}")
    return "".join(parts)


def _timeline(snapshots: Sequence[tuple[datetime, Snapshot]]) -> str:
    head = '<section id="snapshot-timeline"><h2>Snapshot timeline</h2>'
    if not snapshots:
        return (
            f'{head}<p class="quiet">No snapshots yet: `fr triage render` stores one each '
            "time the board changes, and the timeline steps through them.</p></section>"
        )
    panels = [
        (f"s{i}", _stamp(when), _snapshot_panel(snap, snapshots[i - 1][1] if i else None))
        for i, (when, snap) in enumerate(snapshots)
    ]
    note = ""
    if len(snapshots) == 1:
        note = (
            '<p class="lede">Only one snapshot is stored, so there is nothing to step '
            "through yet; the next render that changes the board adds a step.</p>"
        )
    return f"{head}{note}{tabs('snapshot', 'Snapshots', panels, len(panels) - 1)}</section>"


def _finished_waves(facts: Facts, judgements: Judgements) -> str:
    head = '<section id="finished-waves"><h2>Finished waves</h2>'
    done = finished_waves(judgements.batches, batch_stages(facts, judgements))
    grouped = {k: v for k, v in waves(judgements).items() if k in done}
    if not grouped:
        return f'{head}<p class="quiet">No wave is finished yet.</p></section>'
    picked = preselected_wave(facts, judgements, among=done)
    keys = list(grouped)
    selected = keys.index(str(picked)) if picked is not None else len(keys) - 1
    panels = [
        (key, f"Wave {key}", _wave_table(batches, facts, judgements, BOARD_FILE))
        for key, batches in grouped.items()
    ]
    return f"{head}{tabs('history-wave', 'Finished waves', panels, selected)}</section>"


def render_history(
    facts: Facts,
    judgements: Judgements,
    *,
    snapshots: Sequence[tuple[datetime, Snapshot]],
    resolved: Resolved,
    notes: Sequence[str] = (),
) -> str:
    """The page: same inputs, same bytes. The timeline, the finished waves and the authored
    fragments in the order *resolved* (the manifest) gives."""
    generated = {
        "timeline": lambda: _timeline(snapshots),
        "finished-waves": lambda: _finished_waves(facts, judgements),
    }
    body = splice(resolved, generated)
    title = f"History · {facts.scope}"
    notes_html = "".join(f"<li>{esc(n)}</li>" for n in notes)
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n{FONTS}\n<style>{CSS}</style>\n</head>\n<body>\n<main>\n"
        f'<header class="mast"><h1>{esc(title)}</h1><div class="meta">'
        f"<span>collected {esc(facts.collected_at)}</span>"
        "<span>rendered by <code>fr triage history render</code></span></div>"
        f'<ul class="notes">{notes_html}</ul></header>\n'
        f"{page_header('history')}\n"
        + "\n".join(body)
        + f"\n</main>\n<script>{TABS_SCRIPT}</script>\n</body>\n</html>\n"
    )
