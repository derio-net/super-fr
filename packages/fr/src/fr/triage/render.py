"""`render` — one self-contained, deterministic, safe HTML board (spec §3.G).

Follows `fr.acceptance.report`'s pattern: pure Python, CSS and JS as module
constants, `html.escape` on every forge-sourced string.

- **Built from the model.** `render` takes `fr.triage.model.Facts` and reads the
  derived `Issue.stage`; stage is never stored in `facts.json`, so a renderer
  reading raw JSON would find none (review r-p2-render-model).
- **Rows are rendered here**, grouped by tier with Unranked first, carrying the
  filter and sort keys as `data-*` attributes. `SCRIPT` only shows, hides and
  reorders them; the page is complete with JavaScript off.
- **Untrusted text is inert.** Titles, bodies, labels and URLs come from anyone
  who can file an issue. Every one is escaped, and no facts text is ever placed
  inside the `<script>` element — `SCRIPT` is a constant.
- **Deterministic.** No clock is read: the only timestamps shown are
  `collected_at` and `ranked_at`, which are data. Same inputs, same bytes.
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from fr.triage.check import CheckResult, classify

if TYPE_CHECKING:
    from fr.triage.model import Facts, Issue, Judgement, Judgements

_CODE = re.compile(r"`([^`\n]+)`")
# One pass over code OR bold, so two matches can never overlap and a code span is
# never rescanned for bold (review r-p3-inline-nesting).
_INLINE = re.compile(r"`([^`\n]+)`|\*\*([^*\n]+)\*\*")

CX_RANK = {"XS": 0, "S": 1, "S-M": 2, "M": 3, "L": 4, "-": 5}
IN_FLIGHT = frozenset({"pr-draft", "pr-ready"})
DONE = frozenset({"closed", "merged"})
UNTOUCHED = frozenset({"backlog", "blocked"})
EXCERPT = 600  # characters of an unranked issue's body shown on the page
SEVERITIES = 4  # tiers past the fourth share the last severity colour

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=IBM+Plex+Mono:wght@400;500&amp;family=IBM+Plex+Sans:wght@400;500;600"
    '&amp;display=swap">'
)

CSS = """
:root {
  --ground: #F4F5F2; --surface: #FFFFFF; --ink: #1B2021; --muted: #5E6A66;
  --line: #DCE0D9; --accent: #2F6F5E; --live: #6B4FA0;
  --sev-1: #B03A2E; --sev-2: #C2761B; --sev-3: #4A6FA5; --sev-4: #7B8783;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas,
    "Liberation Mono", monospace;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ground: #14181A; --surface: #1C2124; --ink: #E7EBE8; --muted: #9AA6A1;
    --line: #2C3337; --accent: #65B79B; --live: #A58BD6;
    --sev-1: #E4796A; --sev-2: #DFA357; --sev-3: #8AACDC; --sev-4: #8F9A96;
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; overflow-x: hidden; }
body { background: var(--ground); color: var(--ink); font: 15px/1.5 var(--sans); }
main { max-width: 1040px; margin: 0 auto; padding: 0 16px 48px; }
code, .mono { font-family: var(--mono); font-size: .92em; }
code { background: var(--ground); border: 1px solid var(--line); border-radius: 4px;
  padding: 0 4px; overflow-wrap: anywhere; }
a { color: var(--accent); }
header.mast { padding: 28px 0 16px; border-bottom: 2px solid var(--ink); }
header.mast h1 { margin: 0 0 6px; font-size: 1.6rem; font-weight: 600; letter-spacing: -.01em;
  overflow-wrap: anywhere; }
.meta { color: var(--muted); font-size: .88rem; display: flex; flex-wrap: wrap; gap: 4px 16px; }
.counts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.count { background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
  padding: 2px 10px; font-size: .85rem; }
.count b { font-family: var(--mono); font-weight: 500; }
.notes { margin: 12px 0 0; padding: 0; list-style: none; font-size: .85rem; color: var(--sev-2); }
.notes li { overflow-wrap: anywhere; }
.bar { position: sticky; top: 0; z-index: 2; background: var(--ground);
  border-bottom: 1px solid var(--line); padding: 10px 0; display: flex; flex-wrap: wrap;
  gap: 8px; align-items: center; }
.bar input, .bar select { font: inherit; color: var(--ink); background: var(--surface);
  border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; min-width: 0; }
.bar input { flex: 1 1 180px; }
.chip { font: inherit; font-size: .82rem; color: var(--muted); background: var(--surface);
  border: 1px solid var(--line); border-radius: 999px; padding: 3px 10px; cursor: pointer; }
.chip[aria-pressed="true"] { color: var(--surface); background: var(--accent);
  border-color: var(--accent); }
section.tier { margin-top: 28px; }
.tier-head { display: flex; gap: 12px; align-items: baseline; }
.tier-chip { flex: none; font-family: var(--mono); font-weight: 500; width: 28px; height: 28px;
  line-height: 28px; text-align: center; border-radius: 6px; color: var(--surface);
  background: var(--sev); }
.tier-head h2 { margin: 0; font-size: 1.15rem; font-weight: 600; }
.tier-desc { margin: 2px 0 10px 40px; color: var(--muted); font-size: .9rem; }
.unranked .tier-desc { color: var(--ink); }
.empty { margin-left: 40px; color: var(--muted); font-size: .9rem; }
.sev-1 { --sev: var(--sev-1); } .sev-2 { --sev: var(--sev-2); }
.sev-3 { --sev: var(--sev-3); } .sev-4 { --sev: var(--sev-4); }
.sev-u { --sev: var(--accent); }
details.row { background: var(--surface); border: 1px solid var(--line);
  border-left: 4px solid var(--sev); border-radius: 6px; margin: 6px 0; }
details.row[data-done="1"] { opacity: .62; }
details.row > summary { list-style: none; cursor: pointer; padding: 8px 12px; display: flex;
  flex-wrap: wrap; gap: 4px 10px; align-items: baseline; }
details.row > summary::-webkit-details-marker { display: none; }
.num { font-family: var(--mono); color: var(--muted); flex: 0 1 auto; min-width: 0;
  overflow-wrap: anywhere; }
.title { flex: 1 1 260px; min-width: 0; overflow-wrap: anywhere; font-weight: 500; }
.tags { display: flex; flex-wrap: wrap; gap: 4px; }
.tag { font-size: .75rem; color: var(--muted); border: 1px solid var(--line); border-radius: 4px;
  padding: 0 6px; }
.tag.ok { color: var(--accent); border-color: var(--accent); }
.cx { font-family: var(--mono); font-size: .75rem; border: 1px solid var(--ink);
  border-radius: 4px; padding: 0 6px; }
.pill { font-size: .75rem; border-radius: 999px; padding: 1px 9px; color: var(--surface);
  background: var(--muted); white-space: nowrap; }
.pill.stage-pr-draft, .pill.stage-pr-ready { background: var(--live); }
.pill.stage-merged { background: var(--accent); }
.pill.stage-blocked { background: var(--sev-2); }
.pill.stage-closed { background: var(--sev-4); }
.pill.stage-backlog { background: transparent; color: var(--muted);
  border: 1px solid var(--line); }
.detail { padding: 4px 12px 12px; border-top: 1px dashed var(--line); font-size: .92rem; }
.detail p { margin: 8px 0; overflow-wrap: anywhere; }
.detail .body { white-space: pre-wrap; overflow-wrap: anywhere; font-family: var(--mono);
  font-size: .8rem; color: var(--muted); background: var(--ground); border-radius: 4px;
  padding: 8px; margin: 8px 0; }
.patterns article { background: var(--surface); border: 1px solid var(--line);
  border-radius: 6px; padding: 10px 12px; margin: 6px 0; }
.patterns h3 { margin: 0 0 4px; font-size: 1rem; }
footer { margin-top: 40px; color: var(--muted); font-size: .8rem; }
@media (max-width: 480px) {
  main { padding: 0 10px 32px; }
  .tier-desc, .empty { margin-left: 0; }
  .title { flex-basis: 100%; }
}
"""

# The viewer's script: shows, hides and reorders rows by their data-*
# attributes. A constant — no facts text ever reaches a <script> element.
# localStorage holds only the viewer's own chips and sort, inside try/catch.
SCRIPT = """
(function () {
  var KEY = "fr-triage:view";
  var q = document.getElementById("q"), sort = document.getElementById("sort");
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip"));
  var rows = Array.prototype.slice.call(document.querySelectorAll("details.row"));
  var TESTS = {
    inflight: function (r) { return r.dataset.inflight === "1"; },
    untouched: function (r) { return r.dataset.untouched === "1"; },
    verified: function (r) { return r.dataset.verified === "1"; },
    small: function (r) { return r.dataset.cx === "XS" || r.dataset.cx === "S"; },
    done: function (r) { return r.dataset.done === "1"; }
  };
  var ORDERS = {
    priority: function (a, b) { return a.dataset.order - b.dataset.order; },
    cheap: function (a, b) {
      return (a.dataset.cxrank - b.dataset.cxrank) || (a.dataset.order - b.dataset.order);
    },
    oldest: function (a, b) {
      return a.dataset.filed < b.dataset.filed ? -1 : a.dataset.filed > b.dataset.filed ? 1
        : a.dataset.num - b.dataset.num;
    },
    number: function (a, b) { return a.dataset.num - b.dataset.num; }
  };
  function active() {
    return chips.filter(function (c) { return c.getAttribute("aria-pressed") === "true"; })
      .map(function (c) { return c.dataset.filter; });
  }
  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify({ sort: sort.value, chips: active() }));
    } catch (e) { /* storage unavailable: the view is simply not remembered */ }
  }
  function load() {
    try {
      var v = JSON.parse(localStorage.getItem(KEY) || "{}");
      if (v.sort && ORDERS[v.sort]) { sort.value = v.sort; }
      (v.chips || []).forEach(function (f) {
        chips.forEach(function (c) {
          if (c.dataset.filter === f) { c.setAttribute("aria-pressed", "true"); }
        });
      });
    } catch (e) { /* a bad or blocked store falls back to the defaults */ }
  }
  function apply() {
    var needle = q.value.trim().toLowerCase(), on = active();
    rows.forEach(function (r) {
      var show = (!needle || r.dataset.search.indexOf(needle) !== -1) &&
        on.every(function (f) { return TESTS[f](r); });
      r.hidden = !show;
    });
    Array.prototype.forEach.call(document.querySelectorAll(".rows"), function (list) {
      var mine = Array.prototype.slice.call(list.children);
      mine.sort(ORDERS[sort.value] || ORDERS.priority);
      mine.forEach(function (r) { list.appendChild(r); });
    });
  }
  chips.forEach(function (c) {
    c.addEventListener("click", function () {
      c.setAttribute("aria-pressed", c.getAttribute("aria-pressed") === "true" ? "false" : "true");
      save(); apply();
    });
  });
  q.addEventListener("input", apply);
  sort.addEventListener("change", function () { save(); apply(); });
  load(); apply();
})();
"""

FILTER_BAR = """<div class="bar" role="toolbar" aria-label="Filter and sort">
<input id="q" type="search" placeholder="Search number, title, theme" aria-label="Search">
<select id="sort" aria-label="Sort">
<option value="priority">priority</option>
<option value="cheap">cheapest first</option>
<option value="oldest">oldest</option>
<option value="number">number</option>
</select>
<button class="chip" type="button" data-filter="inflight" aria-pressed="false">in-flight</button>
<button class="chip" type="button" data-filter="untouched" aria-pressed="false">untouched</button>
<button class="chip" type="button" data-filter="verified" aria-pressed="false">verified</button>
<button class="chip" type="button" data-filter="small" aria-pressed="false">XS&amp;S only</button>
<button class="chip" type="button" data-filter="done" aria-pressed="false">done</button>
</div>"""

UNRANKED_TITLE = "Unranked — not yet triaged"
UNRANKED_DESC = (
    "These open issues carry no judgement, so the board "
    "cannot place them. Run the <code>fr-triage</code> skill to rank them."
)


def noun(n: int, word: str) -> str:
    """*word* as a count of *n* needs it: `repo` for one, `repos` otherwise."""
    return word if n == 1 else f"{word}s"


def plural(n: int, word: str) -> str:
    """`1 repo`, `2 repos` (review r-p3-copy)."""
    return f"{n} {noun(n, word)}"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def inline(text: str) -> str:
    """Escape first, then allow exactly `code` and **bold** (spec §3.D).

    A single left-to-right pass: code content is literal, and code inside bold
    nests validly (`<strong><code>x</code></strong>`) because only the bold
    span's own text is scanned for code.
    """

    def tag(m: re.Match[str]) -> str:
        if m.group(1) is not None:
            return f"<code>{m.group(1)}</code>"
        return "<strong>" + _CODE.sub(r"<code>\1</code>", m.group(2)) + "</strong>"

    return _INLINE.sub(tag, esc(text))


def _capitalise(s: str) -> str:
    return s[:1].upper() + s[1:]


def _safe_url(url: str) -> str | None:
    """An issue or PR URL fit for an href: https only, escaped."""
    return esc(url) if url.startswith("https://") else None


def _row(
    issue: Issue,
    *,
    judgement: Judgement | None,
    tier: str,
    order: int,
    show_repo: bool,
    patterns: list[str],
) -> str:
    stage = issue.stage
    cx = judgement.cx if judgement else "-"
    theme = judgement.theme if judgement else ""
    verified = bool(judgement and judgement.verified)
    filed = (issue.created_at or "")[:10]
    label = issue.key if show_repo else f"#{issue.number}"
    attrs = {
        "data-key": issue.key,
        "data-tier": tier,
        "data-stage": stage,
        "data-cx": cx,
        "data-cxrank": str(CX_RANK[cx]),
        "data-theme": theme,
        "data-num": str(issue.number),
        "data-filed": filed,
        "data-order": str(order),
        "data-verified": "1" if verified else "0",
        "data-inflight": "1" if stage in IN_FLIGHT else "0",
        "data-untouched": "1" if stage in UNTOUCHED else "0",
        "data-done": "1" if stage in DONE else "0",
        "data-search": f"{issue.key} #{issue.number} {issue.title} {theme}".lower(),
    }
    tags: list[str] = []
    if theme:
        tags.append(f'<span class="tag">{esc(theme)}</span>')
    if filed:
        tags.append(f'<span class="tag mono">{esc(filed)}</span>')
    if verified:
        tags.append('<span class="tag ok">verified in code</span>')
    tags.extend(f'<span class="tag mono">PR #{pr.number}</span>' for pr in issue.prs)
    detail: list[str] = []
    if judgement and judgement.detail:
        detail.append(f"<p>{inline(judgement.detail)}</p>")
    if judgement and judgement.note:
        detail.append(f'<p class="note"><strong>Note.</strong> {inline(judgement.note)}</p>')
    detail.extend(f'<p class="pattern">Pattern: {p}</p>' for p in patterns)
    if judgement is None and issue.body:
        excerpt = issue.body[:EXCERPT] + ("…" if len(issue.body) > EXCERPT else "")
        detail.append(f'<div class="body">{esc(excerpt)}</div>')
    if issue.labels:
        labels = ", ".join(esc(label_) for label_ in issue.labels)
        detail.append(f"<p>Labels: {labels}</p>")
    links = []
    if (url := _safe_url(issue.url)) is not None:
        links.append(f'<a href="{url}" rel="noopener noreferrer">issue #{issue.number}</a>')
    for pr in issue.prs:
        if (pr_url := _safe_url(pr.url)) is not None:
            links.append(
                f'<a href="{pr_url}" rel="noopener noreferrer">PR #{pr.number}</a> '
                f'<span class="mono">{esc(pr.state.lower())}</span>'
            )
    if links:
        detail.append(f"<p>{' · '.join(links)}</p>")
    attr_s = " ".join(f'{k}="{esc(v)}"' for k, v in attrs.items())
    cx_chip = f'<span class="cx">{esc(cx)}</span>' if judgement else ""
    return (
        f'<details class="row" {attr_s}>'
        f'<summary><span class="num">{esc(label)}</span>'
        f'<span class="title">{esc(issue.title)}</span>'
        f'<span class="tags">{"".join(tags)}</span>{cx_chip}'
        f'<span class="pill stage-{stage}">{stage}</span></summary>'
        f'<div class="detail">{"".join(detail)}</div></details>'
    )


def _section(tier: str, chip: str, sev: str, title: str, desc: str, rows: list[str]) -> str:
    extra = " unranked" if tier == "unranked" else ""
    body = (
        f'<div class="rows">{"".join(rows)}</div>'
        if rows
        else '<p class="empty">No issues in this tier.</p>'
    )
    return (
        f'<section class="tier {sev}{extra}" data-tier="{esc(tier)}">'
        f'<div class="tier-head"><span class="tier-chip">{esc(chip)}</span>'
        f"<h2>{esc(title)}</h2></div>"
        f'<p class="tier-desc">{desc}</p>{body}</section>'
    )


def _masthead(facts: Facts, judgements: Judgements, result: CheckResult) -> str:
    open_n = sum(1 for i in facts.issues if i.state == "open")
    in_flight = sum(1 for i in facts.issues if i.stage in IN_FLIGHT)
    ranked = judgements.ranked_at.isoformat() if judgements.ranked_at else "never"
    counts = [
        ("open", open_n),
        ("unranked", len(result.unranked)),
        ("in flight", in_flight),
        ("settled", len(result.settled)),
        (noun(len(facts.collected), "repo"), len(facts.collected)),
    ]
    notes = [_capitalise(w.describe(esc(w.target))) + "." for w in facts.warnings]
    notes += [f"Skipped {esc(s.repo)}: {esc(s.reason)}" for s in facts.skipped]
    notes += [f"Unreachable judgement {esc(u.key)}: {esc(u.reason)}" for u in result.unreachable]
    notes += [
        f"Orphaned judgement {esc(k)}: it names no repo this collect read"
        " (a typo or a renamed repo)."
        for k in result.orphaned
    ]
    notes_html = (
        '<ul class="notes">' + "".join(f"<li>{n}</li>" for n in notes) + "</ul>" if notes else ""
    )
    return (
        '<header class="mast">'
        f"<h1>Backlog triage · {esc(facts.scope)}</h1>"
        '<div class="meta">'
        f'<span>collected <span class="mono">{esc(facts.collected_at)}</span></span>'
        f'<span>ranked <span class="mono">{esc(ranked)}</span></span>'
        f"<span>{esc(facts.kind)} scope</span></div>"
        '<div class="counts">'
        + "".join(f'<span class="count"><b>{n}</b> {label}</span>' for label, n in counts)
        + f"</div>{notes_html}</header>"
    )


def _patterns(judgements: Judgements) -> str:
    if not judgements.patterns:
        return ""
    items = "".join(
        f"<article><h3>{esc(p.title)}</h3>"
        f'<p class="mono">{esc(", ".join(p.ids))}</p><p>{inline(p.body)}</p></article>'
        for p in judgements.patterns
    )
    return f'<section class="patterns"><h2>Patterns</h2>{items}</section>'


def render(facts: Facts, judgements: Judgements) -> str:
    """The board for *facts* and *judgements*: same inputs, same bytes."""
    show_repo = facts.kind == "org"
    result = classify(facts, judgements)  # the one classification, shared below
    patterns_by_key: dict[str, list[str]] = {}
    for p in judgements.patterns:
        for key in p.ids:
            patterns_by_key.setdefault(key, []).append(esc(p.title))
    by_key = {i.key: i for i in facts.issues}
    order = 0

    def row(issue: Issue, judgement: Judgement | None, tier: str) -> str:
        nonlocal order
        order += 1
        return _row(
            issue,
            judgement=judgement,
            tier=tier,
            order=order,
            show_repo=show_repo,
            patterns=patterns_by_key.get(issue.key, []),
        )

    sections = [
        _section(
            "unranked",
            "?",
            "sev-u",
            UNRANKED_TITLE,
            UNRANKED_DESC,
            [row(i, None, "unranked") for i in result.unranked],
        )
    ]
    for pos, tier in enumerate(sorted(judgements.tiers, key=lambda t: t.n)):
        rows = [
            row(by_key[key], j, str(tier.n))
            for key, j in judgements.issues.items()
            if j.tier == tier.n and key in by_key
        ]
        sev = f"sev-{min(pos + 1, SEVERITIES)}"
        sections.append(
            _section(str(tier.n), str(tier.n), sev, tier.title, inline(tier.description), rows)
        )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Backlog triage · {esc(facts.scope)}</title>\n"
        f"{FONTS}\n<style>{CSS}</style>\n</head>\n<body>\n<main>\n"
        f"{_masthead(facts, judgements, result)}\n{FILTER_BAR}\n"
        + "\n".join(sections)
        + f"\n{_patterns(judgements)}\n"
        "<footer>Rendered by <code>fr triage render</code> from facts.json and "
        "judgements.yaml. Stages are derived from the forge; re-run "
        "<code>fr triage collect</code> to refresh.</footer>\n"
        f"</main>\n<script>{SCRIPT}</script>\n</body>\n</html>\n"
    )
