"""The board page (spec 2026-10-05-triage-batch-board §D): one deterministic HTML file.

Follows `fr.triage.render`'s rules: CSS and JS are module constants, every
forge- or judgement-sourced string goes through `html.escape`, and none reaches
the `<script>` element (the refresh interval travels as a `data-refresh`
attribute on `<body>`). Cards are `<details>`, so expanding works with scripts
off. The renderer reads no clock: `rendered_at` is passed in.

The copied command is `shlex.join(["fr", "triage", "batch", "focus", id, *scope_args])`
(plus `--closeout`), each word shell-quoted before the whole is HTML-escaped.
"""

from __future__ import annotations

import shlex
from collections.abc import Sequence
from datetime import UTC, datetime

from fr.triage.components import GUTTER_CSS, TOKENS_CSS
from fr.triage.kanban import Board, BoardStatus, Card, ColumnView, Member, PrView
from fr.triage.render import FONTS, _safe_url, esc, noun

STATUS_LABELS: dict[BoardStatus, str] = {
    "working": "working",
    "blocked": "blocked",
    "idle": "idle",
    "done": "done",
    "unknown": "unknown",
    "absent": "no session",
}

CSS = (
    TOKENS_CSS
    + """
* { box-sizing: border-box; }
body { margin: 0; background: var(--ground); color: var(--ink); font: 15px/1.45 var(--sans); }
main { padding: 20px; }
h1 { margin: 0 0 4px; font-size: 1.4rem; }
h2 { margin: 0 0 8px; font-size: .95rem; display: flex; justify-content: space-between; }
h4 { margin: 12px 0 4px; font-size: .78rem; text-transform: uppercase; letter-spacing: .04em;
  color: var(--muted); }
a { color: var(--accent); }
code, .mono { font-family: var(--mono); font-size: .85em; }
.meta, .hint, .notes { color: var(--muted); font-size: .85rem; }
.notes { margin: 8px 0; padding-left: 18px; }
.empty { margin: 32px 0; color: var(--muted); }
.board { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px;
  align-items: start; margin-top: 16px; }
.col { background: color-mix(in srgb, var(--line) 35%, transparent); border-radius: 8px;
  padding: 10px; min-width: 0; }
.count { color: var(--muted); font-weight: 400; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
  margin: 0 0 8px; overflow-wrap: anywhere; }
.card.needs-you { border-color: var(--sev-1); box-shadow: inset 4px 0 0 var(--sev-1); }
.card > summary { cursor: pointer; padding: 8px 10px; list-style: none; display: block; }
.card > summary::-webkit-details-marker { display: none; }
.card > summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.card .title { display: block; font-weight: 600; margin: 2px 0; }
.card .body { padding: 0 10px 10px; border-top: 1px solid var(--line); font-size: .88rem; }
.card ul, .card ol { margin: 0; padding-left: 18px; }
.card dl { margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 2px 10px; }
.card dt { color: var(--muted); }
.card dd { margin: 0; }
.pill { display: inline-block; font-size: .72rem; border-radius: 999px; padding: 0 8px;
  border: 1px solid var(--line); color: var(--muted); white-space: nowrap; }
.status-working { color: var(--accent); border-color: var(--accent); }
.status-blocked { color: var(--sev-1); border-color: var(--sev-1); font-weight: 600; }
.status-done { color: var(--live); border-color: var(--live); }
.stage-cancelled, .stage-abandoned, .stage-partial {
  color: var(--sev-2); border-color: var(--sev-2); }
.flag { color: var(--sev-1); }
.hint { display: block; margin-top: 2px; }
.needs-you .hint { color: var(--sev-1); font-weight: 600; }
button.jump { font: inherit; font-size: .78rem; color: var(--accent); background: transparent;
  border: 1px solid var(--accent); border-radius: 4px; padding: 0 8px; cursor: pointer; }
code.cmd { display: block; margin: 4px 0; padding: 4px 6px; background: var(--ground);
  border: 1px solid var(--line); border-radius: 4px; white-space: pre-wrap;
  overflow-wrap: anywhere; user-select: all; }
@media (max-width: 1100px) { .board { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 720px) { .board { grid-template-columns: minmax(0, 1fr); } }
"""
    + GUTTER_CSS
)

# One constant script: copy buttons, the reload timer, and the expanded cards and scroll
# position kept across a reload. Nothing from the facts reaches it; the interval is read
# from `<body data-refresh>`. Every storage access is guarded (it throws in private modes).
SCRIPT = """
(function () {
  var KEY = "fr-board:" + location.pathname;
  function read() {
    try { return JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { return {}; }
  }
  function write(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* unavailable */ }
  }
  function cards() { return Array.prototype.slice.call(document.querySelectorAll("details.card")); }
  function save() {
    var open = cards().filter(function (c) { return c.open; }).map(function (c) { return c.id; });
    write({ open: open, y: window.scrollY });
  }
  var saved = read();
  (saved.open || []).forEach(function (id) {
    var card = document.getElementById(id);
    if (card && card.tagName === "DETAILS") { card.open = true; }
  });
  if (typeof saved.y === "number") { window.scrollTo(0, saved.y); }
  document.addEventListener("toggle", save, true);
  window.addEventListener("scroll", function () {
    if (!window.__frBoardTimer) {
      window.__frBoardTimer = setTimeout(function () { window.__frBoardTimer = 0; save(); }, 150);
    }
  });
  function select(code) {
    var range = document.createRange();
    range.selectNodeContents(code);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }
  function manual(button) {
    var code = document.getElementById(button.getAttribute("data-target"));
    var card = button.closest("details");
    if (card) { card.open = true; }
    if (code) { select(code); }
  }
  function confirmed(button) {
    var was = button.getAttribute("data-label") || button.textContent;
    button.setAttribute("data-label", was);
    button.textContent = "copied";
    setTimeout(function () { button.textContent = was; }, 1500);
  }
  Array.prototype.forEach.call(document.querySelectorAll("button.jump"), function (button) {
    button.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      var command = button.getAttribute("data-command") || "";
      try {
        navigator.clipboard.writeText(command).then(
          function () { confirmed(button); },
          function () { manual(button); }
        );
      } catch (err) { manual(button); }
    });
  });
  var seconds = parseInt(document.body.dataset.refresh, 10);
  if (seconds > 0) {
    setTimeout(function () {
      try { save(); } catch (e) { /* reload anyway */ }
      location.reload();
    }, seconds * 1000);
  }
})();
"""


def _when(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _stamp(text: str) -> str:
    """A forge timestamp as `_when` spells it; the escaped text itself when unreadable."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return esc(text)
    return _when(moment) if moment.tzinfo else esc(text)


def _link(text: str, url: str | None) -> str:
    safe = _safe_url(url) if url else None
    if safe is None:
        return esc(text)
    return f'<a href="{safe}" rel="noopener noreferrer">{esc(text)}</a>'


def _command(batch_id: str, scope_args: Sequence[str], *, closeout: bool) -> str:
    words = ["fr", "triage", "batch", "focus", batch_id, *scope_args]
    if closeout:
        words.append("--closeout")
    return shlex.join(words)


def _jump(batch_id: str, scope_args: Sequence[str], *, closeout: bool) -> str:
    target = f"cmd-{batch_id}{'-closeout' if closeout else ''}"
    command = _command(batch_id, scope_args, closeout=closeout)
    return (
        f'<button type="button" class="jump" data-command="{esc(command)}" '
        f'data-target="{esc(target)}">jump</button>'
    )


def _code(batch_id: str, scope_args: Sequence[str], *, closeout: bool) -> str:
    target = f"cmd-{batch_id}{'-closeout' if closeout else ''}"
    command = _command(batch_id, scope_args, closeout=closeout)
    return f'<code class="cmd" id="{esc(target)}">{esc(command)}</code>'


def _status(status: BoardStatus) -> str:
    return f'<span class="pill status-{status}">{STATUS_LABELS[status]}</span>'


def _member(member: Member) -> str:
    return (
        f'<li>{_link(member.title, member.url)} <span class="pill">{esc(member.stage)}</span></li>'
    )


def _checks(checks: dict[str, int] | None) -> str:
    if not checks:
        return "no checks"
    return " · ".join(f"{n} {esc(name)}" for name, n in sorted(checks.items(), reverse=True))


def _pr(pr: PrView) -> str:
    word = "draft" if pr.draft else "ready"
    rows = [
        ("PR", f"{_link(f'#{pr.number}', pr.url)} {esc(pr.state.lower())}, {word}"),
        ("Checks", _checks(pr.checks)),
        ("Mergeable", esc(pr.mergeable or "—")),
        ("Review", esc(pr.review or "—")),
    ]
    return "<h4>Pull request</h4>" + _dl(rows)


def _dl(rows: Sequence[tuple[str, str]]) -> str:
    return "<dl>" + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>"


def _setting(value: str | None, is_default: bool) -> str:
    if value is None:
        return "—"
    return f"{esc(value)} (default)" if is_default else esc(value)


def _lifecycle(card: Card) -> str:
    after = ", ".join(f"{esc(d.batch_id)} ({esc(d.state)})" for d in card.after) or "—"
    flag = ' <span class="flag">blocked</span>' if card.blocked else ""
    rows = [
        ("Wave", esc(str(card.wave)) if card.wave is not None else "—"),
        ("After", after + flag),
        ("Branch", esc(card.branch) if card.branch else "—"),
        ("Reserved version", esc(card.reserved_version) if card.reserved_version else "—"),
        ("Runner", esc(card.runner) if card.runner else "—"),
        ("Harness", _setting(card.harness.value, card.harness.is_default)),
        ("Model", _setting(card.model.value, card.model.is_default)),
        ("Skill", esc(card.skill)),
        ("Rationale", esc(card.rationale) if card.rationale else "—"),
    ]
    return "<h4>Lifecycle</h4>" + _dl(rows)


def _timeline(card: Card) -> str:
    if not card.events:
        return '<h4>Timeline</h4><p class="meta">No events yet.</p>'
    items = "".join(
        f'<li><span class="mono">{esc(e.kind)}</span> {_when(e.at)}'
        f"{' · ' + esc(e.detail) if e.detail else ''}</li>"
        for e in card.events
    )
    return f"<h4>Timeline</h4><ol>{items}</ol>"


def _body(card: Card, scope_args: Sequence[str]) -> str:
    bid = card.batch.id
    parts = [
        "<h4>Issues</h4><ul>" + "".join(_member(m) for m in card.members) + "</ul>",
    ]
    if card.pr is not None:
        parts.append(_pr(card.pr))
    parts.append(_lifecycle(card))
    parts.append(_timeline(card))
    if card.status is not None:
        session = f"<p>{_status(card.status)}</p>"
        if card.show_jump:
            session += f"<p>{_code(bid, scope_args, closeout=False)}</p>"
        parts.append("<h4>Session</h4>" + session)
    if card.closeout_status is not None:
        closeout = f"<p>{_status(card.closeout_status)}"
        if card.show_closeout_jump:
            closeout += f" {_jump(bid, scope_args, closeout=True)}"
        closeout += "</p>"
        if card.show_closeout_jump:
            closeout += f"<p>{_code(bid, scope_args, closeout=True)}</p>"
        parts.append("<h4>Close-out session</h4>" + closeout)
    return f'<div class="body">{"".join(parts)}</div>'


def _card(card: Card, scope_args: Sequence[str]) -> str:
    bid = card.batch.id
    classes = "card needs-you" if card.needs_you else "card"
    count = len(card.members)
    meta = [f"{count} {noun(count, 'issue')}"]
    if card.wave is not None:
        meta.insert(0, f"wave {card.wave}")
    pills = ""
    if card.status is not None:
        pills += " " + _status(card.status)
    if card.pill:
        pills += f' <span class="pill stage-{esc(card.pill)}">{esc(card.pill)}</span>'
    if card.blocked:
        pills += ' <span class="pill flag">blocked</span>'
    jump = " " + _jump(bid, scope_args, closeout=False) if card.show_jump else ""
    summary = (
        f'<summary><span class="mono">{esc(bid)}</span>'
        f'<span class="title">{esc(card.batch.title)}</span>'
        f'<span class="meta">{esc(" · ".join(meta))}</span>{pills}{jump}'
        f'<span class="hint">{esc(card.hint)}</span></summary>'
    )
    return (
        f'<details class="{classes}" id="card-{esc(bid)}" data-batch="{esc(bid)}">'
        f"{summary}{_body(card, scope_args)}</details>"
    )


def _column(column: ColumnView, scope_args: Sequence[str]) -> str:
    cards = "".join(_card(c, scope_args) for c in column.cards)
    return (
        f'<section class="col" data-column="{esc(column.key)}">'
        f'<h2>{esc(column.title)} <span class="count">{len(column.cards)}</span></h2>'
        f"{cards}</section>"
    )


def render_board(
    board: Board,
    *,
    scope_args: Sequence[str],
    rendered_at: datetime,
    refresh: int,
    notes: Sequence[str],
) -> str:
    """The board page: same inputs, same bytes. *scope_args* are the `--repo`/`--org`
    (and `--dir`, when given) words the copied commands carry; *refresh* is the reload
    interval in seconds, 0 for none."""
    if board.batch_count:
        body = (
            '<div class="board">'
            + "".join(_column(c, scope_args) for c in board.columns)
            + "</div>"
        )
    else:
        body = '<p class="empty">No batches in judgements.yaml: nothing to show yet.</p>'
    note_list = (
        '<ul class="notes">' + "".join(f"<li>{esc(n)}</li>" for n in notes) + "</ul>"
        if notes
        else ""
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Batch board · {esc(board.scope)}</title>\n"
        f"{FONTS}\n<style>{CSS}</style>\n</head>\n"
        f'<body data-refresh="{max(0, int(refresh))}">\n<main>\n'
        f"<header><h1>Batch board</h1>"
        f'<p class="meta">{esc(board.scope)} · rendered {_when(rendered_at)} · '
        f"facts collected {_stamp(board.collected_at)}</p>{note_list}</header>\n"
        f"{body}\n"
        '<footer class="meta">Rendered by <code>fr triage board</code> from facts.json and '
        "judgements.yaml.</footer>\n"
        f"</main>\n<script>{SCRIPT}</script>\n</body>\n</html>\n"
    )
