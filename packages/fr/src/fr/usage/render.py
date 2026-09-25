"""Render a `Rollup`: a plain table (PR bodies, terminals) or one HTML page.

Every missing figure renders `—`: an unavailable session, a session with no
harness dollar figure, a share of nothing. Never `0`, never `$0.00` — a zero
would claim a measurement nobody made.
"""

from __future__ import annotations

import html
import io
from collections.abc import Mapping

from rich.console import Console
from rich.table import Table

from fr.usage.rollup import Rollup, SessionRow

DASH = "—"
ACTIVITIES = ("paperwork", "implementation", "other")


def _usd(value: float | None) -> str:
    if value is None:
        return DASH
    if 0 < value < 0.005:
        # a real, sub-cent figure: `$0.00` would read as a measured zero
        return "<$0.01"
    return f"${value:,.2f}"


def _pct(part: float | None, whole: float | None) -> str:
    if part is None or not whole:
        return DASH
    return f"{100 * part / whole:.1f}%"


def _session_cells(row: SessionRow) -> list[str]:
    note = row.unavailable or ("coarse attribution" if row.attribution == "coarse" else "")
    shares = [
        _pct(row.by_activity.get(a, 0.0), row.usd) if row.usd is not None else DASH
        for a in ACTIVITIES
    ]
    return [row.session[:8], row.harness, _usd(row.usd), row.source, *shares, note]


def _table(title: str, headers: list[str], rows: list[list[str]]) -> Table:
    table = Table(title=title, title_justify="left")
    for i, header in enumerate(headers):
        table.add_column(header, justify="left" if i == 0 else "right")
    for row in rows:
        table.add_row(*row)
    return table


def _dollar_rows(values: Mapping[str, float], total: float | None) -> list[list[str]]:
    ordered = sorted(values.items(), key=lambda kv: -kv[1])
    return [[name, _usd(value), _pct(value, total)] for name, value in ordered]


def _activity_rows(result: Rollup, total: float | None) -> list[list[str]]:
    """Activity rows with their turns — an activity with turns but no dollars
    (every message unpriced) still gets a row, its dollars `—`."""
    names = sorted(
        set(result.by_activity) | set(result.turns_by_activity),
        key=lambda n: (-result.by_activity.get(n, 0.0), n),
    )
    rows = []
    for name in names:
        usd = result.by_activity.get(name)
        rows.append([name, _usd(usd), _pct(usd, total), str(result.turns_by_activity.get(name, 0))])
    return rows


def _step_rows(result: Rollup, bar: bool) -> list[list[str]]:
    rows = []
    for step in dict.fromkeys([*result.by_step, *result.turns_by_step]):
        split = result.by_step.get(step, {})
        step_total = sum(split.values()) if split else None
        row = [
            html.escape(step) if bar else step,
            _usd(step_total),
            str(result.turns_by_step.get(step, 0)),
            *(_pct(split.get(a, 0.0), step_total) for a in ACTIVITIES),
        ]
        if bar:
            row.append(_bar(split, step_total))
        rows.append(row)
    return rows


def render_table(result: Rollup) -> str:
    total = result.total
    buffer = io.StringIO()
    console = Console(file=buffer, width=120, no_color=True, highlight=False)
    console.print(
        _table(
            "Sessions",
            ["session", "harness", "usd", "source", *ACTIVITIES, "note"],
            [_session_cells(row) for row in result.sessions],
        )
    )
    console.print(
        _table("By model", ["model", "usd", "share"], _dollar_rows(result.by_model, total))
    )
    console.print(
        _table("By activity", ["activity", "usd", "share", "turns"], _activity_rows(result, total))
    )
    console.print(
        _table("By sub-activity", ["sub", "usd", "share"], _dollar_rows(result.by_sub, total))
    )
    if result.by_step or result.turns_by_step:
        console.print(
            _table("By step", ["step", "usd", "turns", *ACTIVITIES], _step_rows(result, bar=False))
        )
    console.print(f"Total: {_usd(total)} (harness-reported; split by fixed price ratios)")
    return buffer.getvalue()


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>fr usage report</title>
<style>
body{{font:14px/1.45 system-ui,sans-serif;margin:2rem auto;max-width:72rem;
  padding:0 1rem;color:#222}}
h1{{font-size:1.4rem}} h2{{font-size:1.05rem;margin-top:2rem}}
table{{border-collapse:collapse;width:100%}}
th,td{{padding:.3rem .6rem;border-bottom:1px solid #ddd;text-align:right}}
th:first-child,td:first-child{{text-align:left}}
.bar{{display:flex;height:.9rem;min-width:12rem}} .bar span{{display:block}}
.paperwork{{background:#c0504d}} .implementation{{background:#4f81bd}} .other{{background:#bbb}}
.note{{color:#666;font-size:.9em}}
</style></head><body>
<h1>fr usage report</h1>
<p>Total <b>{total}</b> — harness-reported dollars, split across activities by
price-weighted tokens (fixed ratios input 1, cache write 5m 1.25 / 1h 2,
cache read 0.1, output 5). <span class="paperwork">&nbsp;&nbsp;</span> paperwork
<span class="implementation">&nbsp;&nbsp;</span> implementation
<span class="other">&nbsp;&nbsp;</span> other. — means no figure, never zero.</p>
<h2>Sessions</h2>
<table><tr><th>session</th><th>harness</th><th>usd</th><th>source</th><th>paperwork</th>
<th>implementation</th><th>other</th><th>split</th><th>note</th></tr>
{sessions}
</table>
<h2>By activity</h2>
<table><tr><th>activity</th><th>usd</th><th>share</th><th>turns</th></tr>{activities}</table>
<h2>By sub-activity</h2>
<table><tr><th>sub</th><th>usd</th><th>share</th></tr>{subs}</table>
<h2>By model</h2>
<table><tr><th>model</th><th>usd</th><th>share</th></tr>{models}</table>
{steps}
</body></html>
"""


def _bar(split: Mapping[str, float], whole: float | None) -> str:
    if not whole:
        return DASH
    spans = "".join(
        f'<span class="{a}" style="width:{100 * split.get(a, 0.0) / whole:.2f}%"></span>'
        for a in ACTIVITIES
    )
    return f'<div class="bar">{spans}</div>'


def _rows(rows: list[list[str]]) -> str:
    return "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)


def _escaped(rows: list[list[str]]) -> list[list[str]]:
    return [[html.escape(cell) for cell in row] for row in rows]


def render_html(result: Rollup) -> str:
    total = result.total
    sessions = []
    for row in result.sessions:
        cells = [html.escape(c) for c in _session_cells(row)]
        note = cells.pop()
        cells += [_bar(row.by_activity, row.usd), f'<span class="note">{note}</span>']
        sessions.append(cells)
    steps = ""
    if result.by_step or result.turns_by_step:
        steps = (
            "<h2>By step</h2><table><tr><th>step</th><th>usd</th><th>turns</th><th>paperwork</th>"
            "<th>implementation</th><th>other</th><th>split</th></tr>"
            + _rows(_step_rows(result, bar=True))
            + "</table>"
        )
    return _PAGE.format(
        total=_usd(total),
        sessions=_rows(sessions),
        activities=_rows(_escaped(_activity_rows(result, total))),
        subs=_rows(_escaped(_dollar_rows(result.by_sub, total))),
        models=_rows(_escaped(_dollar_rows(result.by_model, total))),
        steps=steps,
    )
