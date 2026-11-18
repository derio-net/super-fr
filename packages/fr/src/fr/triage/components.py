"""Page pieces every generated triage page shares (wave-driver R12, R16).

- **Colour tokens** with a light, a dark (`prefers-color-scheme`) and an explicit
  `:root[data-theme]` variant, generated from ONE pair of dicts so the three can never
  drift, plus the 16px side gutter at phone width. A page built on `TOKENS_CSS` and
  `GUTTER_CSS` needs no hand patch afterwards.
- **`tabs()`**, one tab component: a `tablist` of buttons with roving `tabindex`, one
  `tabpanel` each, panels toggled with the `hidden` attribute by `TABS_SCRIPT`. The
  markup is complete with scripts off: no panel carries `hidden` and the tab row is
  itself `hidden`, so every pane shows; the script hides all but the selected one and
  reveals the row. The board uses it for waves and the architecture page reuses it.

Untrusted text never reaches `TABS_SCRIPT`, which is a constant.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from pathlib import Path

    from fr.triage.model import Facts

LIGHT = {
    "ground": "#F4F5F2", "surface": "#FFFFFF", "ink": "#1B2021", "muted": "#5E6A66",
    "line": "#DCE0D9", "accent": "#2F6F5E", "live": "#6B4FA0",
    "sev-1": "#B03A2E", "sev-2": "#C2761B", "sev-3": "#4A6FA5", "sev-4": "#7B8783",
}  # fmt: skip
DARK = {
    "ground": "#14181A", "surface": "#1C2124", "ink": "#E7EBE8", "muted": "#9AA6A1",
    "line": "#2C3337", "accent": "#65B79B", "live": "#A58BD6",
    "sev-1": "#E4796A", "sev-2": "#DFA357", "sev-3": "#8AACDC", "sev-4": "#8F9A96",
}  # fmt: skip

FONT_TOKENS = (
    '--sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto,\n'
    '    "Helvetica Neue", Arial, sans-serif;\n'
    '  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas,\n'
    '    "Liberation Mono", monospace;'
)


class Legacy(NamedTuple):
    """What a page was called before it had one name (spec 2026-11-18-triage-pages-ux R3):
    its old file, removed by a render, and its old fragment directory, read when the new
    one is absent. Either may be None."""

    file: str | None
    dir: str | None


class Page(NamedTuple):
    key: str
    file: str
    title: str
    goal: str
    dir: str | None = None
    """The page's fragment directory (`<state>/<dir>/manifest.yaml`); None for a page that
    reads no manifest."""
    legacy: Legacy | None = None


PAGES = (
    Page(
        "backlog",
        "backlog.html",
        "Backlog",
        "What do I do next?",
        "backlog",
        Legacy("triage.html", "board"),
    ),
    Page(
        "issues",
        "issues.html",
        "Issues",
        "What is open, and how is it ranked?",
        "issues",
        Legacy(None, "board"),
    ),
    Page(
        "batches",
        "batches.html",
        "Batches",
        "What is running, and what needs me?",
        None,
        Legacy("board.html", None),
    ),
    Page(
        "origins",
        "origins.html",
        "Origins",
        "Where do defects come from, and what process change stops them?",
        "origins",
    ),
    Page(
        "architecture",
        "architecture.html",
        "Architecture",
        "What is the system, and where does it hurt?",
        "architecture",
    ),
    Page("history", "history.html", "History", "How did we get here?", "history"),
)
"""The six pages the triage engine writes, in nav order: one goal each (spec §A). This is
the registry (board-truth R9): a page is shown in a nav only when it is present, and every
file, directory and title a page is known by is read from here (triage-pages-ux R1)."""

_BY_KEY = {p.key: p for p in PAGES}


def page(key: str) -> Page:
    """The registry entry for *key*; a KeyError for a key no page has."""
    return _BY_KEY[key]


def _vars(tokens: dict[str, str]) -> str:
    return " ".join(f"--{name}: {value};" for name, value in tokens.items())


TOKENS_CSS = f"""
:root {{
  {_vars(LIGHT)}
  {FONT_TOKENS}
  color-scheme: light dark;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ {_vars(DARK)} }}
}}
:root[data-theme="light"] {{ {_vars(LIGHT)} color-scheme: light; }}
:root[data-theme="dark"] {{ {_vars(DARK)} color-scheme: dark; }}
"""

CHROME_CSS = """
nav.pages { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 10px 0 0; font-size: .9rem; }
nav.pages a { color: var(--muted); text-decoration: none; padding: 2px 0;
  border-bottom: 2px solid transparent; }
nav.pages a[aria-current="page"] { color: var(--ink); font-weight: 600;
  border-bottom-color: var(--accent); }
.goal { margin: 8px 0 0; font-size: 1.05rem; color: var(--ink); }
"""
"""The page chrome every page's CSS includes: nav bar and goal sentence."""

FOLD_CSS = """
details.fold { margin-top: 20px; background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; padding: 0 14px; }
details.fold > summary { cursor: pointer; padding: 10px 0; font-weight: 600; font-size: 1.05rem; }
details.fold > summary .count { font: 500 .8rem var(--mono); color: var(--muted);
  border: 1px solid var(--line); border-radius: 999px; padding: 0 8px; margin-left: 6px; }
details.fold[open] > summary { border-bottom: 1px solid var(--line); margin-bottom: 8px; }

details.fold > summary > h2, details.fold > summary > h3 { display: inline; margin: 0;
  font-size: 1.05rem; font-weight: 600; }
details.fold > summary > .count { margin-left: 8px; }
"""
"""The shared fold: a section-level `details` with a title and an optional count on its
summary line (triage-pages-ux R8)."""


BASE_CSS = """
* { box-sizing: border-box; }
html, body { margin: 0; overflow-x: hidden; }
body { background: var(--ground); color: var(--ink); font: 15px/1.5 var(--sans); }
main { max-width: 1040px; margin: 0 auto; padding: 0 16px 48px; }
a { color: var(--accent); }
code { font-family: var(--mono); font-size: .92em; overflow-wrap: anywhere; }
header.mast { padding: 28px 0 16px; border-bottom: 2px solid var(--ink); }
header.mast h1 { margin: 0 0 6px; font-size: 1.6rem; font-weight: 600; overflow-wrap: anywhere; }
.meta { color: var(--muted); font-size: .88rem; display: flex; flex-wrap: wrap; gap: 4px 16px; }
.notes { margin: 12px 0 0; padding: 0; list-style: none; font-size: .85rem; color: var(--sev-2); }
section { margin-top: 28px; }
section > h2 { margin: 0 0 8px; font-size: 1.15rem; font-weight: 600; }
.lede, .src { color: var(--muted); font-size: .85rem; margin: 0 0 10px; }
.quiet { color: var(--muted); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0; }
.chip { background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
  padding: 2px 10px; font-size: .85rem; }
.chip b { font-family: var(--mono); font-weight: 500; }
.scroll { overflow-x: auto; }
table { width: 100%; min-width: 560px; border-collapse: collapse; background: var(--surface);
  border: 1px solid var(--line); font-size: .88rem; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line);
  vertical-align: top; }
th { color: var(--muted); font-weight: 500; }
td.n, th.n { text-align: right; font-family: var(--mono); }
svg.chart { display: block; height: auto; }
svg.chart text { font-family: var(--mono); font-size: 10px; }
.stages summary { cursor: pointer; color: var(--muted); font-size: .85rem; }
.stage-list { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: .85rem;
  margin-top: 6px; }
.fragment { margin-top: 28px; }
"""
"""The prelude the architecture and history pages share (theme-built ground, masthead,
sections, tables); a page adds its own pieces after it."""

GRID_CSS = """
.tablewrap { overflow-x: auto;
  /* scroll shadows: an edge with more table beyond it is shaded (review p2-r2) */
  background:
    linear-gradient(to right, var(--ground) 30%, transparent) left / 32px 100% no-repeat local,
    linear-gradient(to left, var(--ground) 30%, transparent) right / 32px 100% no-repeat local,
    radial-gradient(farthest-side at 0 50%, rgba(0,0,0,.25), transparent)
      left / 12px 100% no-repeat scroll,
    radial-gradient(farthest-side at 100% 50%, rgba(0,0,0,.25), transparent)
      right / 12px 100% no-repeat scroll; }
table.grid { border-collapse: collapse; width: 100%; min-width: 720px; font-size: .88rem; }
table.grid th, table.grid td { text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--line); padding: 4px 8px; }
table.grid th { color: var(--muted); font-weight: 500; white-space: nowrap; }
table.grid td.mono { overflow-wrap: anywhere; min-width: 7em; }
table.grid.narrow { min-width: 0; }
table.grid.narrow td { overflow-wrap: anywhere; }
@media (max-width: 480px) {
  table.grid.stack { min-width: 0; }
  table.grid.stack thead { position: absolute; width: 1px; height: 1px; overflow: hidden;
    clip: rect(0 0 0 0); white-space: nowrap; }
  table.grid.stack tbody, table.grid.stack tr, table.grid.stack td { display: block; }
  table.grid.stack tr { border-bottom: 1px solid var(--line); padding: 8px 0; }
  table.grid.stack td { border: 0; padding: 2px 0; text-align: left; min-width: 0;
    overflow-wrap: anywhere; }
  table.grid.stack td::before { content: attr(data-label); display: inline-block;
    width: 6.5em; color: var(--muted); font-family: var(--sans); }
}
"""
"""Wide data tables: a `.tablewrap` scrolls sideways, so a table keeps readable columns at
phone width (a 390px page never scrolls as a whole) instead of wrapping letter by letter;
`.narrow` is for a table of short columns that fits. `.stack` goes further for a table
whose rows read as records (the wave table, gh#1001): under 480px each row is a card and
each cell is labelled from its `data-label`, so nothing scrolls at all."""

GUTTER_CSS = """
@media (max-width: 480px) {
  main { padding-left: 16px; padding-right: 16px; }
}
"""

TABS_CSS = """
[hidden] { display: none !important; }
.tabs [role="tablist"] { display: flex; flex-wrap: wrap; gap: 4px; margin: 8px 0;
  border-bottom: 1px solid var(--line); }
.tabs [role="tab"] { font: inherit; font-size: .9rem; color: var(--muted);
  background: transparent; border: 1px solid transparent; border-bottom: 0;
  border-radius: 6px 6px 0 0; padding: 6px 14px; cursor: pointer; }
.tabs [role="tab"][aria-selected="true"] { color: var(--ink); background: var(--surface);
  border-color: var(--line); font-weight: 600; }
.tabs [role="tab"]:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.tabs [role="tabpanel"] { padding: 4px 0 8px; }
.tabs [role="tabpanel"] > h3 { margin: 12px 0 6px; font-size: 1rem; }
/* The heading names the panel with no script; once the tab row is the label it stays
   in the DOM for assistive tech but is visually hidden, so it does not repeat the tab. */
.tabs.js [role="tabpanel"] > h3.panel-label { position: absolute; width: 1px; height: 1px;
  margin: -1px; padding: 0; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;
  border: 0; }
"""

PAGE_CSS = TABS_CSS + FOLD_CSS
"""What every page's CSS includes after its own: the tab and fold styles (R17), so a
fragment's tab set or fold works on any page."""

# Roving focus per the ARIA tabs pattern: arrows move and select, Home/End jump.
# Panels are toggled with the `hidden` attribute; with this script absent none is hidden.
TABS_SCRIPT = """
(function () {
  var groups = [];
  Array.prototype.forEach.call(document.querySelectorAll("[data-tabs]"), function (root) {
    var list = root.querySelector('[role="tablist"]');
    var tabs = Array.prototype.slice.call(list.querySelectorAll('[role="tab"]'));
    var panels = tabs.map(function (t) {
      return document.getElementById(t.getAttribute("aria-controls"));
    });
    root.classList.add("js");
    function select(i, focus) {
      tabs.forEach(function (t, j) {
        t.setAttribute("aria-selected", j === i ? "true" : "false");
        t.setAttribute("tabindex", j === i ? "0" : "-1");
        if (panels[j]) { panels[j].hidden = j !== i; }
      });
      if (focus) { tabs[i].focus(); }
    }
    groups.push({ panels: panels, select: select });
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { select(i, false); });
      t.addEventListener("keydown", function (e) {
        var n = tabs.length, to = -1;
        if (e.key === "ArrowRight") { to = (i + 1) % n; }
        else if (e.key === "ArrowLeft") { to = (i + n - 1) % n; }
        else if (e.key === "Home") { to = 0; }
        else if (e.key === "End") { to = n - 1; }
        if (to >= 0) { e.preventDefault(); select(to, true); }
      });
    });
    var start = tabs.findIndex(function (t) { return t.getAttribute("aria-selected") === "true"; });
    list.hidden = false;
    select(start < 0 ? 0 : start, false);
  });
  // A URL hash that names a tab panel, or an element inside one, selects that panel's tab
  // (an outer group first, so a nested one is reached), on load and on every hash change.
  function fromHash() {
    var id = "";
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { return; }
    var target = id ? document.getElementById(id) : null;
    if (!target) { return; }
    groups.forEach(function (g) {
      g.panels.forEach(function (p, i) {
        if (p && (p === target || p.contains(target))) { g.select(i, false); }
      });
    });
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a[href]") : null;
    // A new hash fires `hashchange`; only a link to the hash already shown fires nothing.
    if (a && a.hash && a.hash === location.hash && a.pathname === location.pathname) {
      fromHash();
    }
  });
  window.addEventListener("hashchange", fromHash);
  fromHash();
})();
"""

# Opens every `details` around the element the URL hash names (a fold, a card, a row), then
# scrolls to it, on load and on every hash change. A constant: no page text reaches it.
FOLD_SCRIPT = """
(function () {
  function reveal() {
    var id = "";
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { return; }
    var target = id ? document.getElementById(id) : null;
    if (!target) { return; }
    for (var n = target; n; n = n.parentElement) {
      if (n.tagName === "DETAILS") { n.open = true; }
    }
    target.scrollIntoView();
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a[href]") : null;
    if (a && a.hash && a.hash === location.hash && a.pathname === location.pathname) {
      reveal();
    }
  });
  window.addEventListener("hashchange", reveal);
  reveal();
})();
"""

PAGE_SCRIPT = TABS_SCRIPT + FOLD_SCRIPT
"""What every page's `<script>` ends with (R17): tabs, then folds, so a hash link selects
its tab before the fold script opens what is around it and scrolls."""


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def tabs(group: str, label: str, panels: Sequence[tuple[str, str, str]], selected: int) -> str:
    """A tab component: *panels* are `(key, tab label, panel html)`; *selected* is the
    index shown first. *group* and the keys make the ids (`<group>-tab-<key>`), so
    they must be slug-like; the labels are escaped here, the panel html is the
    caller's and must already be safe."""
    tab_html = []
    panel_html = []
    for i, (key, text, body) in enumerate(panels):
        on = i == selected
        tab_id, panel_id = f"{group}-tab-{key}", f"{group}-panel-{key}"
        tab_html.append(
            f'<button type="button" role="tab" id="{_esc(tab_id)}" data-key="{_esc(key)}" '
            f'aria-controls="{_esc(panel_id)}" aria-selected="{"true" if on else "false"}" '
            f'tabindex="{0 if on else -1}">{_esc(text)}</button>'
        )
        panel_html.append(
            f'<div role="tabpanel" id="{_esc(panel_id)}" aria-labelledby="{_esc(tab_id)}" '
            f'tabindex="0"><h3 class="panel-label">{_esc(text)}</h3>{body}</div>'
        )
    return (
        f'<div class="tabs" data-tabs>'
        f'<div role="tablist" aria-label="{_esc(label)}" hidden>{"".join(tab_html)}</div>'
        f"{''.join(panel_html)}</div>"
    )


def pages_present(state_dir: Path, current: str, *also: str) -> tuple[str, ...]:
    """The keys of the pages present in *state_dir* (R9): those whose file exists there,
    plus *current* and *also*, the pages being rendered. Nothing else decides it, so every
    page a nav links has a file once the render finishes. Registry order."""
    writing = {current, *also}
    return tuple(p.key for p in PAGES if p.key in writing or (state_dir / p.file).is_file())


def fragment_dir(state_dir: Path, key: str) -> tuple[Path, str | None]:
    """The directory page *key* reads its manifest and fragments from, and a note when it
    is the page's old one (triage-pages-ux R3): the page's own directory when it exists,
    else its legacy directory when that exists, else its own (absent: the default order).
    A page with no fragment directory raises ValueError."""
    entry = page(key)
    if entry.dir is None:
        raise ValueError(f"the {entry.title} page reads no manifest")
    own = state_dir / entry.dir
    old = entry.legacy.dir if entry.legacy else None
    if own.is_dir() or old is None or not (state_dir / old).is_dir():
        return own, None
    note = (
        f"{entry.title}: no {entry.dir}/ directory, so its manifest and fragments are read "
        f"from {old}/; copy them to {entry.dir}/ to keep them once {old}/ is gone"
    )
    return state_dir / old, note


def remove_legacy(state_dir: Path, key: str) -> Path | None:
    """Delete page *key*'s old-named file from *state_dir* (triage-pages-ux R3), so no
    stale copy stays beside the page; the path removed, or None when there was none. A
    file that cannot be removed raises OSError, which the caller reports."""
    entry = page(key)
    if entry.legacy is None or entry.legacy.file is None:
        return None
    old = state_dir / entry.legacy.file
    if not old.is_file():
        return None
    old.unlink()
    return old


NAV_BLOCK = re.compile(r'<nav class="pages"[^\n>]*>[^\n]*?</nav>')
"""The one-line nav block `page_header` writes: what `refresh_navs` replaces and the
publish copy strips. fr's own markup, so it never spans a line."""


def nav_html(current: str, present: Sequence[str]) -> str:
    """The `<nav class="pages">` block alone: links to the *present* pages only, *current*
    marked `aria-current="page"`."""
    here = ' aria-current="page"'
    links = "".join(
        f'<a href="{_esc(p.file)}"{here if p.key == current else ""}>{_esc(p.title)}</a>'
        for p in PAGES
        if p.key in present
    )
    return f'<nav class="pages" aria-label="Triage pages">{links}</nav>'


def page_header(current: str, present: Sequence[str]) -> str:
    """The nav bar linking the *present* pages, *current* marked `aria-current="page"`,
    then the goal sentence of *current* (spec §A). Every renderer calls it after its
    masthead."""
    goal = page(current).goal
    return f'{nav_html(current, present)}<p class="goal">{_esc(goal)}</p>'


def strip_nav(page: str) -> str:
    """*page* without its nav block: the copy `--publish` hands over, whose siblings are
    not published (R10)."""
    return NAV_BLOCK.sub("", page)


def refresh_navs(state_dir: Path, current: str, warn: Callable[[str], None] | None = None) -> None:
    """After *current* is written, bring the nav of every other present page into
    agreement (R11): replace its nav block in place, atomically, skipping a page that is
    already current. A page with no nav block is left byte-identical and named to *warn*.
    The goal sentence is not touched.

    Every block of a page is replaced, the same as `strip_nav` removes every block. A page
    is written only if it still holds what was read: the file is read again just before the
    write and a change in between skips it silently (the other writer's own render
    refreshes the navs). A page that cannot be read or written is warned about, never
    raised, so the caller's own work (a snapshot, a publish) still happens."""
    from fr.artifacts.atomic import write_text_atomic

    present = pages_present(state_dir, current)
    for other in PAGES:
        if other.key == current or other.key not in present:
            continue
        path = state_dir / other.file
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            if warn:
                warn(f"{path}: nav not refreshed ({exc})")
            continue
        if NAV_BLOCK.search(text) is None:
            if warn:
                warn(f"{path}: no nav block found; left as it was")
            continue
        nav = nav_html(other.key, present)
        new = NAV_BLOCK.sub(lambda _m: nav, text)
        if new == text:
            continue
        try:
            if path.read_text(encoding="utf-8") != text:
                continue  # another render wrote it meanwhile; its own refresh covers the nav
            write_text_atomic(path, new)
        except (OSError, UnicodeDecodeError) as exc:
            if warn:
                warn(f"{path}: nav not refreshed ({exc})")


SKEW_CSS = (
    ".skew { margin: 12px 0; padding: 10px 14px; border: 1px solid var(--line);"
    " border-left: 4px solid var(--sev-1); border-radius: 6px; font-size: .9rem; }"
    " .skew ul { margin: 6px 0 0; padding-left: 18px; }"
    " .skew li { overflow-wrap: anywhere; }"
)


def skew_banner(facts: Facts) -> str:
    """The version-skew banner (R5): "" when nothing was skipped or ignored, else a
    `role="alert"` block naming each repo's ignored `.fr/triage.yaml` keys and each
    skipped repo with its reason. Everything is escaped."""
    from fr.triage.check import skew_entries

    ignored, skipped = skew_entries(facts)
    if not ignored and not skipped:
        return ""
    items = [
        f"<li><b>{_esc(repo)}</b>: ignored {_esc(', '.join(keys))} — written for a newer fr:"
        " upgrade fr to read them</li>"
        for repo, keys in ignored
    ] + [f"<li><b>{_esc(repo)}</b>: skipped — {_esc(reason)}</li>" for repo, reason in skipped]
    return (
        '<div class="skew" role="alert"><strong>This page is not the whole truth.</strong>'
        f"<ul>{''.join(items)}</ul></div>"
    )


def fold(
    id_: str,
    title: str,
    count: int | None,
    body: str,
    *,
    open_: bool = False,
    heading: str | None = None,
) -> str:
    """A section-level collapsible (triage-pages-ux R8): the title and, when known, an item
    count show on the summary line. It starts open when *open_*. *heading* (`h2`, `h3`)
    keeps the title a heading inside the summary, so the section stays a landmark and its
    *id_* a link target. *title* is escaped here; *body* is the caller's and must be safe."""
    if heading is not None and heading not in ("h2", "h3", "h4"):
        raise ValueError(f"a fold heading is h2, h3 or h4, not {heading!r}")
    label = _esc(title) if heading is None else f"<{heading}>{_esc(title)}</{heading}>"
    n = "" if count is None else f' <span class="count">{count}</span>'
    return (
        f'<details id="{_esc(id_)}" class="fold"{" open" if open_ else ""}>'
        f"<summary>{label}{n}</summary>{body}</details>"
    )


Moment = datetime
"""The type of a render's moment, for a module that must not import a clock module itself
(render.py, whose clock-freedom a test checks structurally)."""


def when(moment: datetime) -> str:
    """A moment as the board spells it everywhere: `YYYY-MM-DD HH:MM UTC`."""
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def rendered_by(moment: datetime | None, command: str) -> str:
    """The masthead's one render line (triage-pages-ux R5): `rendered <when> by <command>`,
    or `rendered by <command>` with no moment. *command* is fr's own text, escaped here."""
    when_ = "" if moment is None else f"{when(moment)} "
    return f"<span>rendered {when_}by <code>{_esc(command)}</code></span>"


def stamp_text(text: str) -> str:
    """A forge timestamp as `when` spells it; *text* itself (unescaped) when unreadable."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return text
    return when(moment) if moment.tzinfo else text


def wave_href(key: str, finished: bool) -> str:
    """Where wave *key* is shown (triage-pages-ux R12): its tab on History when finished,
    else its tab on the Backlog. The ids are `tabs()`'s: `<group>-panel-<key>`."""
    frag = urllib.parse.quote(key, safe="-_.")
    if finished:
        return f"{page('history').file}#history-wave-panel-{frag}"
    return f"{page('backlog').file}#wave-panel-{frag}"


def batch_href(batch_id: str) -> str:
    """Where batch *batch_id*'s card is: on the Backlog (R12)."""
    return f"{page('backlog').file}#batch-{urllib.parse.quote(batch_id, safe='-_.')}"


_REF = re.compile(r"(?<![\w/.&#-])(?:([A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+)#|#)(\d{1,9})\b")
"""`owner/repo#n` or a bare `#n`, in text that is already escaped. The lookbehind keeps it out
of a longer word, a path, an entity (`&#x27;`) and another `#`."""


@dataclass(frozen=True)
class Linker:
    """Where each PR or issue reference links (triage-pages-ux R11), built once per render
    from the page's inputs. *urls* maps a lower-cased `owner/repo#n` the inputs hold to that
    item's own url, *bases* each repo to its url base (the issue or PR url up to `/issues/`
    or `/pull/`), and *single* is the one repo of a single-repo scope (a bare `#n` is there,
    nowhere else). Only https urls from the inputs are kept: no href is ever built from
    prose, only from one of these or from a github.com base plus a number."""

    urls: Mapping[str, str]
    bases: Mapping[str, str]
    single: str | None = None
    keys: Mapping[str, str] = field(default_factory=dict)
    """Each issue or PR the inputs hold by its judgement key (`<repo-name>#<n>`, normalised)
    to its own url: what `key_link` renders a key in a list from."""

    @classmethod
    def from_facts(cls, facts: Facts) -> Linker:
        from fr.triage.model import issue_key

        urls: dict[str, str] = {}
        bases: dict[str, str] = {}
        keys: dict[str, str] = {}

        def add(repo: str, number: int, url: str) -> None:
            if not url.startswith("https://"):
                return
            urls.setdefault(f"{repo.lower()}#{number}", url)
            keys.setdefault(issue_key(repo, number), url)
            for marker in ("/issues/", "/pull/"):
                if marker in url:
                    bases.setdefault(repo.lower(), url.split(marker, 1)[0])
                    break

        for issue in facts.issues:
            add(issue.repo, issue.number, issue.url)
            for pr in issue.prs:
                add(pr.repo, pr.number, pr.url)
        for pr in (*facts.prs, *facts.batch_prs, *facts.judged_prs):
            add(pr.repo, pr.number, pr.url)
        single = facts.repos[0].lower() if facts.kind == "repo" and len(facts.repos) == 1 else None
        return cls(urls, bases, single, keys)

    def key_link(self, key: str) -> str:
        """Judgement key *key* for a list: a link to the item's own url when the inputs hold
        it (an https url only), else the escaped key as text."""
        from fr.triage.model import normalize_key

        url = self.keys.get(normalize_key(key))
        if url is None:
            return _esc(key)
        return f'<a href="{_esc(url)}" rel="noopener noreferrer">{_esc(key)}</a>'

    def key_links(self, keys: Sequence[str]) -> str:
        """`key_link` of each of *keys*, comma-separated."""
        return ", ".join(self.key_link(k) for k in keys)

    def href(self, repo: str, number: int) -> str | None:
        """The link for `repo#number` (unescaped), or None: the item's own url when the
        inputs hold it, else `<base>/issues/<n>` on a github.com base (GitHub redirects a
        PR there), else nothing."""
        repo = repo.lower()
        known = self.urls.get(f"{repo}#{number}")
        if known is not None:
            return known
        base = self.bases.get(repo)
        if base is not None and urllib.parse.urlsplit(base).hostname == "github.com":
            return f"{base}/issues/{number}"
        return None

    def prose(self, escaped: str) -> str:
        """*escaped* (text already HTML-escaped, outside any code span) with each reference
        that has a link turned into one; every other character is returned as it was."""

        def link(m: re.Match[str]) -> str:
            repo = m.group(1) or self.single
            href = None if repo is None else self.href(repo, int(m.group(2)))
            if href is None:
                return m.group(0)
            return f'<a href="{_esc(href)}" rel="noopener noreferrer">{m.group(0)}</a>'

        return _REF.sub(link, escaped)
