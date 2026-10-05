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
from collections.abc import Sequence
from typing import NamedTuple

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


class Page(NamedTuple):
    key: str
    file: str
    title: str
    goal: str


PAGES = (
    Page("board", "triage.html", "Board", "What do I do next?"),
    Page(
        "origins",
        "origins.html",
        "Origins",
        "Where do defects come from, and what process change stops them?",
    ),
    Page(
        "architecture",
        "architecture.html",
        "Architecture",
        "What is the system, and where does it hurt?",
    ),
    Page("history", "history.html", "History", "How did we get here?"),
)
"""The four pages the triage engine writes, in nav order: one goal each (spec §A)."""


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
details.fold { margin-top: 20px; background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; padding: 0 14px; }
details.fold > summary { cursor: pointer; padding: 10px 0; font-weight: 600; font-size: 1.05rem; }
details.fold > summary .count { font: 500 .8rem var(--mono); color: var(--muted);
  border: 1px solid var(--line); border-radius: 999px; padding: 0 8px; margin-left: 6px; }
details.fold[open] > summary { border-bottom: 1px solid var(--line); margin-bottom: 8px; }
"""
"""The page chrome every page's CSS includes: nav bar, goal sentence, collapsed sections."""

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

# Roving focus per the ARIA tabs pattern: arrows move and select, Home/End jump.
# Panels are toggled with the `hidden` attribute; with this script absent none is hidden.
TABS_SCRIPT = """
(function () {
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
})();
"""


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


def page_header(current: str) -> str:
    """The nav bar linking the four pages, *current* marked `aria-current="page"`, then
    the goal sentence of *current* (spec §A). Every renderer calls it after its masthead."""
    links = "".join(
        f'<a href="{_esc(p.file)}"{" aria-current=\"page\"" if p.key == current else ""}>'
        f"{_esc(p.title)}</a>"
        for p in PAGES
    )
    goal = next(p.goal for p in PAGES if p.key == current)
    return (
        f'<nav class="pages" aria-label="Triage pages">{links}</nav>'
        f'<p class="goal">{_esc(goal)}</p>'
    )


def collapsed(id_: str, title: str, count: int | None, body: str) -> str:
    """A closed-by-default section: the title and, when known, an item count show on the
    summary line. *title* is escaped here; *body* is the caller's and must be safe."""
    n = "" if count is None else f' <span class="count">{count}</span>'
    return (
        f'<details id="{_esc(id_)}" class="fold"><summary>{_esc(title)}{n}</summary>'
        f"{body}</details>"
    )
